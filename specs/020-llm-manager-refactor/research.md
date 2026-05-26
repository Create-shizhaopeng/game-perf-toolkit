# Research: LLM Manager 模块重构

**Created**: 2026-05-25
**Feature**: [spec.md](spec.md)

## Decision Log

### R1: LiteLLM `api_base` 参数支持

**Decision**: 通过 `litellm.acompletion(api_base=url)` 传递自定义 base URL。

**Rationale**: LiteLLM 对所有 Provider 原生支持 `api_base` 参数，覆盖默认 API 地址。已通过阅读 LiteLLM 文档和项目现有 `litellm_provider.py` 代码（第 81-220 行 `stream_chat()` 方法）确认。`api_base=None` 时使用 LiteLLM 内置默认地址，不需要额外判断逻辑。

**Alternatives considered**:
- 使用环境变量覆盖（如 `OPENAI_BASE_URL`）→ 不够灵活，多 Provider 无法各自独立配置
- 使用 LiteLLM 的自定义 provider 注册 → 过度复杂，`api_base` 已满足需求

---

### R2: Anthropic Extended Thinking via LiteLLM

**Decision**: 通过 `litellm.acompletion(thinking={"type": "enabled", "budget_tokens": N})` 启用。

**Rationale**: LiteLLM 原生支持 Anthropic extended thinking 参数。查阅 LiteLLM 文档确认参数格式：
- `thinking={"type": "enabled", "budget_tokens": 4000}` → 模型在回答前进行 ≤4000 tokens 的推理
- 不传 `thinking` 参数时，模型使用标准模式
- thinking budget 最小值 1024，推荐值 4000-16000
- 对不支持 thinking 的 Provider（GLM），不传此参数即可

**Alternatives considered**:
- 使用 Anthropic SDK 直接调用 → 破坏 LiteLLM 统一调用体系
- 在 system prompt 中嵌入 "Think step by step" → 不是真正的 extended thinking，效果差

---

### R3: Token 用量 SQLite 表设计

**Decision**: 通过 `DatabaseManager` 走标准迁移路径，新建 `llm_token_usage` 表。

**Rationale**: 项目已有 `DatabaseManager` 统一管理 SQLite，支持模块级迁移。参考 `modules/device_disguise/` 模块（manifest.json 中 `database.migrations` 字段 + `src/migrations/` 目录）。

```sql
CREATE TABLE llm_token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    conversation_id TEXT,
    trace_id TEXT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_llm_token_conv ON llm_token_usage(conversation_id);
CREATE INDEX idx_llm_token_trace ON llm_token_usage(trace_id);
CREATE INDEX idx_llm_token_timestamp ON llm_token_usage(timestamp);
```

**Alternatives considered**:
- 在 `toolkit_config.json` 中追加 JSON 数组记录 → 大量数据后性能差，无法按维度聚合查询
- 用 loguru 日志文件记录 → 非结构化，统计分析困难
- 不使用 DatabaseManager 直接 sqlite3 → 不符合项目规范

---

### R4: 模块 manifest.json 设计

**Decision**: 参照现有模块标准填写，`provides.gui: true`（注册 Provider 管理对话框入口，无独立 Tab）。

**Rationale**: llm_manager 不创建左侧导航 Tab，但通过设置面板的「管理 Provider」按钮间接提供 GUI。`register_gui_tab()` 返回 `None`（无独立 Tab）。Service 注册到 `ServiceRegistry` 供其他模块调用。

```json
{
  "name": "llm_manager",
  "display_name": "LLM 管理器",
  "version": "0.1.0",
  "entry": "src.plugin",
  "service_entry": "src.service",
  "dependencies": { "toolkit_modules": [] },
  "provides": { "gui": false, "agent_tools": false },
  "events": { "emits": ["llm.provider_changed"], "listens": [] },
  "database": { "migrations": "src/migrations/", "tables": ["llm_token_usage"] }
}
```

**Alternatives considered**:
- 将 GUI 完全放在 `toolkit/gui/` 中 → 违反模块隔离原则，且后续飞书集成不便
- 注册独立 Tab → 不需要，Provider 管理是低频操作

---

### R5: ToolkitDialog 继承模式

**Decision**: `ProviderManageDialog` 继承 `ToolkitDialog`，使用 `DialogCloseButton`。

**Rationale**: 项目规范要求所有对话框继承 `ToolkitDialog`（`toolkit/gui/toolkit_dialog.py`）。参考 `LLMSettingsDialog`（`toolkit/gui/llm_settings_dialog.py`）的实现模式：
1. 继承 `ToolkitDialog`
2. 自定义标题栏（QLabel + DialogCloseButton）
3. 内容通过 `self.content_layout` 添加（QVBoxLayout）
4. 按钮使用已有的 objectName（`#primaryBtn`, `#secondaryBtn`, `#dangerBtn`, `#ghostBtn`）

---

### R6: ConfigManager 路径解析

**Decision**: 配置文件直接通过 `app_paths.get_exe_dir() / "data" / "config" / "llm_providers.json"` 读写，不通过 `ConfigManager`。

**Rationale**: `ConfigManager` 管理 `toolkit_config.json` 的键值对读写，有 `get(key)` / `set(key, value)` 接口。但 llm_providers.json 是一个独立的完整 JSON 文档（数组嵌套结构），不适合用 `ConfigManager` 的扁平键值模型。直接用 `Path` + Pydantic 的 `model_validate_json` / `model_dump_json` 读写更合适。

**Alternatives considered**:
- 通过 `ConfigManager.set("llm_providers", data)` → 会把整个大 JSON 写入 `toolkit_config.json`，导致文件过大，不符合"独立配置文件"的需求
- 扩展 `ConfigManager` 支持多文件 → 过度设计，直接读写 JSON 文件简单且符合单一职责

---

### R7: Server 侧 Service API 设计

**Decision**: `LLMManagerService` 作为模块 service_entry 注册到 ServiceRegistry，提供 Provider CRUD + 配置加载接口。

**Rationale**: 参考 `PerfettoCaptureService`（`modules/perfetto_capture/src/service.py`）的注册模式。其他模块通过 `ServiceRegistry.get("llm_manager_service")` 获取服务实例。主要暴露方法：
- `load_providers()` → `LLMProvidersConfig`
- `get_active_provider_config()` → `tuple[ProviderConfig, ModelConfig]`
- `add_provider(ProviderConfig)` / `remove_provider(id)` / `update_provider(ProviderConfig)`
- `list_providers(enabled_only=True)` → `list[ProviderConfig]`
