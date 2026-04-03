# Data Model: 全局设置与 LLM 能力抽象

**Feature**: 008-global-settings-llm | **Date**: 2026-04-03

## 目录

- [LLMConfig](#llmconfig)
- [StreamChunk](#streamchunk)
- [ToolDefinition](#tooldefinition)
- [LLMProvider ABC](#llmprovider-abc)
- [LLMProviderProtocol](#llmproviderprotocol)
- [LLMManager](#llmmanager)
- [状态与生命周期](#状态与生命周期)
- [配置持久化格式](#配置持久化格式)

## LLMConfig

LLM 全局配置模型。持久化到 `data/config.json` 的 `llm` 键下。

| 字段 | 类型 | 默认值 | 约束 | 说明 |
|------|------|--------|------|------|
| `provider` | `str` | `"glm"` | `"glm"` \| `"claude"` | 当前选用的 Provider |
| `glm_api_key` | `str` | `""` | 非空时视为已配置 | GLM API Key |
| `claude_api_key` | `str` | `""` | 非空时视为已配置 | Claude API Key |
| `model_name` | `str` | `"glm-4-plus"` | - | 当前选用的模型名称 |
| `temperature` | `float` | `0.7` | `0.0 <= v <= 1.0` | 生成温度 |
| `max_tokens` | `int` | `4096` | `>= 256` | 单次回复最大 token 数 |
| `smart_switch` | `bool` | `False` | - | 是否启用失败降级 |
| `token_budget` | `int` | `100000` | `>= 1000` | 会话 token 预算上限 |
| `budget_alert_threshold` | `float` | `0.8` | `0.1 <= v <= 1.0` | 预算告警阈值（百分比） |

```python
class LLMConfig(BaseModel):
    provider: str = Field(default="glm", pattern=r"^(glm|claude)$")
    glm_api_key: str = ""
    claude_api_key: str = ""
    model_name: str = "glm-4-plus"
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=256)
    smart_switch: bool = False
    token_budget: int = Field(default=100000, ge=1000)
    budget_alert_threshold: float = Field(default=0.8, ge=0.1, le=1.0)

    def get_api_key(self, provider: str | None = None) -> str:
        p = provider or self.provider
        return self.glm_api_key if p == "glm" else self.claude_api_key

    def is_configured(self) -> bool:
        return bool(self.get_api_key())
```

**唯一性**: 全局唯一实例，由 LLMManager 持有。
**生命周期**: 应用启动时从 ConfigManager 加载，配置变更时持久化。

## StreamChunk

LLM 流式响应块。从 agent_chat 迁移，保持不变。

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `str` | `"text"` \| `"tool_call"` \| `"usage"` \| `"error"` |
| `content` | `str` | 文本内容 |
| `tool_name` | `str \| None` | 工具名称（仅 tool_call 类型） |
| `tool_args` | `dict \| None` | 工具参数（仅 tool_call 类型） |
| `tool_call_id` | `str \| None` | 工具调用 ID |
| `usage` | `dict \| None` | token 使用信息（仅 usage 类型） |

## ToolDefinition

工具定义。从 agent_chat 迁移，保持不变。

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 工具名称 |
| `description` | `str` | 工具描述 |
| `parameters` | `dict` | JSON Schema 参数定义 |

## LLMProvider ABC

LLM Provider 抽象基类。从 `modules/agent_chat/src/llm/base.py` 迁移到 `toolkit/core/llm/base.py`。

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `stream_chat(messages, tools?, system_prompt?)` | `AsyncIterator[StreamChunk]` | 流式对话接口 |
| `count_tokens(messages)` | `int` | 估算 token 数 |
| `get_available_models()` | `list[str]` | 可用模型列表 |
| `provider_name` (property) | `str` | Provider 标识符 |

**关系**: GLMProvider 和 ClaudeProvider 继承 LLMProvider。

## LLMProviderProtocol

SDK 层 Protocol，供模块类型标注。

```python
@runtime_checkable
class LLMProviderProtocol(Protocol):
    async def stream_chat(
        self, messages: list[dict],
        tools: list | None = None,
        system_prompt: str = "",
    ) -> AsyncIterator: ...

    def count_tokens(self, messages: list[dict]) -> int: ...
    def get_available_models(self) -> list[str]: ...

    @property
    def provider_name(self) -> str: ...
```

## LLMManager

框架层 LLM 管理器。继承 QObject 以支持信号机制。

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `get_provider()` | `LLMProvider \| None` | 获取当前 Provider 实例（线程安全） |
| `get_config()` | `LLMConfig` | 获取当前配置副本 |
| `update_config(config)` | `None` | 更新配置并持久化 |
| `switch_model(model_name)` | `None` | 快捷切换模型 |
| `record_tokens(count)` | `None` | 记录 token 使用（线程安全） |
| `reset_session()` | `None` | 重置会话 token 计数 |
| `get_context_window_size()` | `int` | 获取当前模型上下文窗口大小 |
| `get_context_usage_ratio()` | `float` | 获取上下文占用比例 |
| `smart_stream_chat(messages, **kw)` | `AsyncIterator[StreamChunk]` | 带降级的流式对话 |

| 信号 | 参数 | 说明 |
|------|------|------|
| `config_changed` | `LLMConfig` | 配置变更 |
| `provider_changed` | `str` | Provider 切换 |
| `token_updated` | `int, int` | used, budget |
| `budget_alert` | `float` | 当前比例 |
| `error_occurred` | `str, str` | error_type, message |
| `degradation_occurred` | `str, str` | from_provider, to_provider |

## 状态与生命周期

```text
LLMManager 状态:
  UNCONFIGURED → READY → DEGRADED → READY
                       → ERROR → READY (retry or config change)
                       → BUDGET_PAUSED → READY (user continue or reset)

  UNCONFIGURED: 无有效 API Key
  READY: Provider 实例正常可用
  DEGRADED: 智能切换已降级到备用 Provider（临时状态）
  ERROR: Provider 请求失败且无法降级
  BUDGET_PAUSED: 用户选择暂停后续请求
```

## 配置持久化格式

`data/config.json` 结构（LLM 相关部分）:

```json
{
  "theme": "dark",
  "adb_path": "",
  "language": "zh_CN",
  "log_level": "INFO",
  "window": { "width": 1200, "height": 800 },
  "llm": {
    "provider": "glm",
    "glm_api_key": "",
    "claude_api_key": "",
    "model_name": "glm-4-plus",
    "temperature": 0.7,
    "max_tokens": 4096,
    "smart_switch": false,
    "token_budget": 100000,
    "budget_alert_threshold": 0.8,
    "_migrated": false
  }
}
```

`_migrated` 为内部标记，不暴露给 LLMConfig 模型。由 migration.py 直接操作 ConfigManager。
