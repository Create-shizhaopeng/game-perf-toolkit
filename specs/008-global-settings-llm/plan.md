# Implementation Plan: 全局设置与 LLM 能力抽象

**Branch**: `008-global-settings-llm` | **Date**: 2026-04-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/008-global-settings-llm/spec.md`

## 目录

- [Summary](#summary)
- [Technical Context](#technical-context)
- [Constitution Check](#constitution-check)
- [Project Structure](#project-structure)
  - [Documentation](#documentation-this-feature)
  - [Source Code](#source-code)
- [Design](#design)
  - [LLM 核心层](#llm-核心层-toolkitcorellm)
  - [LLM Manager](#llm-manager)
  - [配置持久化](#配置持久化)
  - [配置自动迁移](#配置自动迁移)
  - [标题栏设置入口](#标题栏设置入口)
  - [LLM 配置对话框](#llm-配置对话框)
  - [状态栏 LLM 指示器](#状态栏-llm-指示器)
  - [智能切换-失败降级](#智能切换失败降级)
  - [Token 预算管理](#token-预算管理)
  - [agent_chat 迁移](#agent_chat-迁移)
  - [组件交互流程](#组件交互流程)
- [Complexity Tracking](#complexity-tracking)

## Summary

将标题栏主题切换按钮替换为设置按钮（齿轮图标），点击弹出菜单包含「主题切换」和「LLM 模型设置」。LLM Provider 实现（GLMProvider、ClaudeProvider）从 `modules/agent_chat/src/llm/` 迁移到 `toolkit/core/llm/`，框架通过 `LLMManager` 管理 Provider 生命周期和配置持久化。各模块通过 `context['llm_manager']` 获取 LLM 能力。底部状态栏右侧显示上下文窗口空心圆环、token 用量和可点击切换的模型名称。

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: PyQt6, anthropic, zhipuai, pydantic 2.0+
**Storage**: `data/config.json`（复用现有 ConfigManager，LLM 配置嵌套在 `llm` 键下）
**Testing**: pytest
**Target Platform**: Windows desktop (PyInstaller onedir)
**Project Type**: desktop-app
**Performance Goals**: LLM 配置保存/加载 <100ms；状态栏更新 <16ms（60fps）
**Constraints**: 多模块并发请求时线程安全；API Key 明文存储（与现有行为一致）
**Scale/Scope**: 初期 2 个 Provider（GLM、Claude），6+ 个模块可能使用 LLM 能力

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 状态 | 说明 |
|------|------|------|
| I. Plugin-First | ✅ PASS | LLM 是框架级基础设施，非模块。放在 `toolkit/core/llm/` 符合框架扩展定位 |
| II. Three-Surface Unity | ✅ PASS | LLMManager 提供 Service 层 API，GUI/CLI/Agent 三端可通过 context 访问 |
| III. Agent-Driven Design | ✅ PASS | Agent 通过 `context['llm_manager']` 获取 Provider，支持动态编排 |
| IV. Dependency Inversion | ✅ PASS | LLM 接口协议放在 `toolkit.sdk.protocols`，实现在 `toolkit.core.llm/`。模块通过 context 获取实例，不直接导入 core 实现 |
| V. Presentation Separation | ✅ PASS | LLMManager 是纯服务层；LLM 设置对话框和状态栏指示器是纯 GUI 层 |
| VI. Open-Closed | ⚠ JUSTIFIED | 此功能修改 `toolkit/core/` 和 `toolkit/sdk/`，但这是框架能力扩展而非模块行为，符合"核心框架由主负责人维护"的协作模式 |
| VII. Spec-Driven | ✅ PASS | 遵循 speckit 完整工作流 |

## Project Structure

### Documentation (this feature)

```text
specs/008-global-settings-llm/
├── spec.md
├── plan.md              # 本文件
├── research.md          # Phase 0 — 无需外部调研（所有技术栈已确定）
├── data-model.md        # Phase 1 — 数据模型定义
├── quickstart.md        # Phase 1 — 快速上手指南
└── tasks.md             # Phase 2 — 任务清单（由 speckit.tasks 生成）
```

### Source Code

```text
toolkit/
├── core/
│   ├── llm/                          # [新增] LLM 核心基础设施
│   │   ├── __init__.py               # 公共导出
│   │   ├── base.py                   # LLMProvider ABC（从 agent_chat 迁移）
│   │   ├── glm_provider.py           # GLMProvider 实现（从 agent_chat 迁移）
│   │   ├── claude_provider.py        # ClaudeProvider 实现（从 agent_chat 迁移）
│   │   ├── manager.py                # LLMManager — Provider 生命周期、配置、信号
│   │   ├── models.py                 # 模型上下文窗口映射表（LLMConfig 定义在 toolkit.sdk.models）
│   │   └── migration.py              # agent_chat 旧配置自动迁移
│   ├── config_manager.py             # [修改] 扩展 LLM 配置读写方法
│   └── __init__.py                   # [修改] 导出 LLMManager
├── gui/
│   ├── widgets/
│   │   ├── title_bar.py              # [修改] ThemeButton → SettingsButton
│   │   ├── llm_settings_dialog.py    # [新增] LLM 配置对话框
│   │   └── llm_status_widget.py      # [新增] 状态栏 LLM 指示器
│   ├── main_window.py                # [修改] 集成 LLMManager、设置菜单、状态栏
│   └── styles.py                     # [修改] 新增 LLM 相关组件样式
├── sdk/
│   ├── protocols.py                  # [修改] 新增 LLMProviderProtocol
│   └── models.py                     # [修改] 新增 LLMConfig
├── app.py                            # [修改] 初始化 LLMManager，注入 context
modules/
└── agent_chat/
    └── src/
        ├── gui_tab.py                # [修改] 移除「模型配置」Tab
        ├── service.py                # [修改] 从 context 获取 LLM Provider
        └── llm/                      # [保留] 可能的 agent_chat 专属 LLM 扩展
```

**Structure Decision**: 采用框架层扩展方案。LLM 基础设施作为 `toolkit/core/llm/` 子包添加，接口协议添加到 `toolkit/sdk/protocols.py`。模块通过 context 依赖注入获取能力，不破坏现有模块独立性。

## Design

### LLM 核心层 (toolkit/core/llm/)

**LLMProvider ABC** — 从 `modules/agent_chat/src/llm/base.py` 迁移，保持接口不变：

```python
class LLMProvider(ABC):
    @abstractmethod
    async def stream_chat(
        self, messages: list[dict],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str = "",
    ) -> AsyncIterator[StreamChunk]: ...

    def count_tokens(self, messages: list[dict]) -> int: ...

    @abstractmethod
    def get_available_models(self) -> list[str]: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...
```

**SDK Protocol** — 在 `toolkit.sdk.protocols` 添加 `LLMProviderProtocol` 供模块类型标注：

```python
@runtime_checkable
class LLMProviderProtocol(Protocol):
    async def stream_chat(self, messages: list[dict], ...) -> AsyncIterator: ...
    def get_available_models(self) -> list[str]: ...
    @property
    def provider_name(self) -> str: ...
```

### LLM Manager

`LLMManager` 是框架层的 LLM 能力管理中心，提供以下职责：

1. **Provider 管理**: 根据 LLMConfig 创建/切换 Provider 实例
2. **配置持久化**: 通过 ConfigManager 读写 `data/config.json` 中的 `llm` 键
3. **Token 跟踪**: 维护应用级会话的 token 累计用量
4. **信号通知**: 通过 pyqtSignal 通知 GUI 和模块

```python
class LLMManager(QObject):
    config_changed = pyqtSignal(object)       # LLMConfig
    provider_changed = pyqtSignal(str)         # provider_name
    token_updated = pyqtSignal(int, int)       # used, budget
    budget_alert = pyqtSignal(float)           # current_ratio
    error_occurred = pyqtSignal(str, str)       # error_type, message
    degradation_occurred = pyqtSignal(str, str) # from_provider, to_provider

    def __init__(self, config_manager: ConfigManager):
        self._config = self._load_config()
        self._provider: LLMProvider | None = None
        self._session_tokens = 0
        self._budget_alerted = False
        self._lock = threading.Lock()

    def get_provider(self) -> LLMProvider | None: ...
    def get_config(self) -> LLMConfig: ...
    def update_config(self, config: LLMConfig) -> None: ...
    def switch_model(self, model_name: str) -> None: ...
    def record_tokens(self, count: int) -> None: ...
    def reset_session(self) -> None: ...
    def get_context_window_size(self) -> int: ...
    def get_context_usage_ratio(self) -> float: ...
```

**线程安全**: `get_provider` 和 `record_tokens` 使用 `threading.Lock` 保护。Provider 实例化在主线程，调用在工作线程。

### 配置持久化

LLM 配置嵌套在 `data/config.json` 的 `llm` 键下：

```json
{
  "theme": "dark",
  "llm": {
    "provider": "glm",
    "glm_api_key": "xxx",
    "claude_api_key": "yyy",
    "model_name": "glm-4-plus",
    "temperature": 0.7,
    "max_tokens": 4096,
    "smart_switch": false,
    "token_budget": 100000,
    "budget_alert_threshold": 0.8
  }
}
```

ConfigManager 扩展方法：

```python
def get_llm_config(self) -> dict: ...
def set_llm_config(self, config: dict) -> None: ...
```

### 配置自动迁移

`migration.py` 在首次启动时检测 `modules/agent_chat/data/config.json`，如果存在且框架级 `llm` 配置为空，则：

1. 读取 agent_chat 的 `provider`、`api_key`、`model_name` 等字段
2. 映射到框架级 LLMConfig 格式
3. 写入 `data/config.json` 的 `llm` 键
4. 标记迁移完成（`llm._migrated: true`），防止重复迁移
5. 旧配置文件不存在时安静跳过

### 标题栏设置入口

**SettingsButton** 替换 ThemeButton：

1. 自定义绘制齿轮图标（QPainter），适配深浅色主题
2. 点击弹出 QMenu：
   - 「主题切换」→ 发射 `theme_toggled` 信号
   - 「LLM 模型设置」→ 发射 `llm_settings_requested` 信号

**TitleBar 修改**：
- `ThemeButton` → `SettingsButton`
- 新增 `llm_settings_requested` 信号
- `set_theme()` 更新 SettingsButton 样式

**MainWindow 修改**：
- 连接 `llm_settings_requested` → 打开 LLM 设置对话框
- `_toggle_theme()` 逻辑不变

### LLM 配置对话框

`LLMSettingsDialog(QDialog)` — 独立窗口，内容：

1. **Provider 选择区**: GLM / Claude 互斥按钮（QPushButton checkable）
2. **API Key 输入**: 密码框 + 显示/隐藏切换，每个 Provider 独立 Key
3. **模型选择**: 可编辑 QComboBox，根据 Provider 动态更新列表
4. **Temperature 滑块**: QSlider + QLabel 显示值（0.0 ~ 1.0）
5. **智能切换**: QCheckBox，勾选后启用失败降级
6. **Token 预算**: QSpinBox（步长 10000），设置会话预算上限
7. **告警阈值**: QSpinBox（百分比，10% 步长），默认 80%
8. **底部按钮**: 保存 / 取消

打开时加载当前 LLMConfig，保存时调用 `llm_manager.update_config()`。

### 状态栏 LLM 指示器

`LLMStatusWidget(QWidget)` — 水平布局，从左到右：

1. **ContextRing**: 自定义 QWidget，QPainter 绘制空心圆环
   - 外径 16px，线宽 2px
   - 空白部分表示剩余上下文窗口
   - 填充部分根据 `context_usage_ratio` 着色（<80% 绿色, <95% 黄色, >=95% 红色）
   
2. **TokenLabel**: QLabel，显示 `"1.2k / 100k"`
   - 数字自动缩写（k/M 单位）
   
3. **ModelLabel**: QLabel，显示模型名（如 `claude-sonnet-4-20250514`）
   - cursor 指针样式，hover 高亮
   - 点击弹出 QMenu 列出当前 Provider 可用模型
   - 选择后调用 `llm_manager.switch_model()`

**信号连接**:
- `llm_manager.token_updated` → 更新 ContextRing 和 TokenLabel
- `llm_manager.provider_changed` → 更新 ModelLabel 文本
- `llm_manager.config_changed` → 刷新全部组件

**未配置状态**: 不显示 ContextRing 和 TokenLabel，ModelLabel 显示「未配置 LLM」（灰色斜体），点击直接打开 LLM 设置对话框。

### 智能切换（失败降级）

当 `smart_switch` 启用时，LLMManager 在 Provider 请求失败后执行降级：

1. 捕获 `stream_chat` 的异常（超时、认证失败、API 错误）
2. 检查备用 Provider 是否有可用的 API Key
3. 临时切换到备用 Provider，发射 `degradation_occurred` 信号
4. 状态栏显示 3 秒临时通知（如「已降级到 GLM」）
5. 不修改持久化配置（降级是临时行为）

实现方式：在 `LLMManager` 包装一个 `smart_stream_chat()` 方法：

```python
async def smart_stream_chat(self, messages, **kwargs):
    try:
        async for chunk in self._provider.stream_chat(messages, **kwargs):
            yield chunk
    except Exception as e:
        if self._config.smart_switch and self._get_fallback_provider():
            self.degradation_occurred.emit(
                self._config.provider, fallback.provider_name
            )
            async for chunk in fallback.stream_chat(messages, **kwargs):
                yield chunk
        else:
            self.error_occurred.emit(type(e).__name__, str(e))
            raise
```

### Token 预算管理

1. `LLMManager.record_tokens(count)`: 累加 `_session_tokens`，发射 `token_updated`
2. 当 `_session_tokens / _config.token_budget >= _config.budget_alert_threshold` 时：
   - 发射 `budget_alert` 信号（仅首次触发，避免重复弹窗）
   - MainWindow 弹出 QMessageBox.warning，用户可选择：
     - 「继续」→ 设置 `_budget_alerted = True`，后续不再弹窗
     - 「暂停」→ 设置 `_budget_paused = True`，后续请求被拦截并返回友好提示
3. `reset_session()`: 重置 `_session_tokens = 0`、`_budget_alerted = False`、`_budget_paused = False`

### agent_chat 迁移

1. **gui_tab.py**: `_SettingsDialog` 移除「模型配置」Tab（`_build_model_tab`），保留 SOP 管理、MCP 管理、高级设置
2. **service.py**: `_init_provider()` 改为从 `context['llm_manager'].get_provider()` 获取 Provider，移除本地 Provider 实例化逻辑
3. **models.py**: `AgentConfig` 移除 `provider`、`api_key`、`model_name`、`glm_api_key`、`claude_api_key`、`temperature` 等 LLM 相关字段
4. **llm/ 目录**: 保留为兼容层或完全移除（Provider 实现已在 toolkit/core/llm/）

### 组件交互流程

```
启动流程:
  app.py → ConfigManager.load()
         → LLMManager(config_manager)
           → migration.check_and_migrate()
           → _load_config() → _init_provider()
         → context['llm_manager'] = llm_manager
         → MainWindow(context)
           → TitleBar(SettingsButton)
           → StatusBar(LLMStatusWidget)
             → llm_manager signals 连接

配置修改流程:
  用户点击齿轮 → QMenu → 「LLM 模型设置」
    → LLMSettingsDialog(llm_manager.get_config())
    → 用户修改 → 保存
    → llm_manager.update_config(new_config)
      → config_manager.set_llm_config(...)
      → _init_provider()
      → config_changed.emit()
      → provider_changed.emit()
    → LLMStatusWidget 刷新
    → 各模块 service 下次调用时获取新 Provider

快捷切换流程:
  用户点击状态栏模型名 → QMenu(available_models)
    → 选择模型
    → llm_manager.switch_model(model_name)
      → update_config(config with new model_name)
      → provider_changed.emit()
    → ModelLabel 更新

LLM 调用流程:
  module.service → context['llm_manager'].get_provider()
    → provider.stream_chat(messages)
    → 每次 response → llm_manager.record_tokens(count)
      → token_updated.emit(used, budget)
      → LLMStatusWidget 更新
    → 若失败 + smart_switch → 自动降级
      → degradation_occurred.emit()
      → 状态栏临时通知
```

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| 修改 toolkit/core/ 和 toolkit/sdk/ | LLM 是框架级基础设施能力，非模块功能 | 作为独立模块实现会导致所有模块依赖该模块，违反模块独立性原则 |
