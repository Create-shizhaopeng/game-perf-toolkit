# Tasks: 全局设置与 LLM 能力抽象

**Input**: Design documents from `/specs/008-global-settings-llm/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md

## 目录

- [Phase 1: Setup](#phase-1-setup-shared-infrastructure)
- [Phase 2: Foundational](#phase-2-foundational-blocking-prerequisites)
- [Phase 3: US1 - 标题栏设置入口](#phase-3-user-story-1---标题栏设置入口-priority-p1--mvp)
- [Phase 4: US2 - LLM 模型配置](#phase-4-user-story-2---llm-模型配置-priority-p1)
- [Phase 5: US4 - 状态栏 LLM 信息与快捷切换](#phase-5-user-story-4---状态栏-llm-信息与快捷切换-priority-p1)
- [Phase 6: US3 - 跨模块 LLM 能力调用](#phase-6-user-story-3---跨模块-llm-能力调用-priority-p2)
- [Phase 7: Polish](#phase-7-polish--cross-cutting-concerns)
- [Dependencies & Execution Order](#dependencies--execution-order)
- [Implementation Strategy](#implementation-strategy)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 创建目录结构和 SDK 层接口定义

- [x] T001 Create `toolkit/core/llm/` directory with `__init__.py`
- [x] T002 [P] Add `LLMProviderProtocol` to `toolkit/sdk/protocols.py`，定义 `stream_chat`、`count_tokens`、`get_available_models`、`provider_name` 接口
- [x] T003 [P] Add `LLMConfig` model to `toolkit/sdk/models.py`，包含 provider、api_key、model_name、temperature、max_tokens、smart_switch、token_budget、budget_alert_threshold 字段
- [x] T004 Update `toolkit/sdk/__init__.py` 导出 `LLMProviderProtocol` 和 `LLMConfig`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: LLM 核心基础设施，所有 User Story 的前置依赖

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Migrate `LLMProvider` ABC from `modules/agent_chat/src/llm/base.py` to `toolkit/core/llm/base.py`，同时迁移 `StreamChunk` 和 `ToolDefinition` 模型
- [x] T006 [P] Migrate `GLMProvider` from `modules/agent_chat/src/llm/glm_provider.py` to `toolkit/core/llm/glm_provider.py`，更新 import 路径
- [x] T007 [P] Migrate `ClaudeProvider` from `modules/agent_chat/src/llm/claude_provider.py` to `toolkit/core/llm/claude_provider.py`，更新 import 路径
- [x] T008 Create `toolkit/core/llm/models.py`，定义模型上下文窗口大小映射表（MODEL_CONTEXT_WINDOWS: dict[str, int]），复用 `toolkit.sdk.models.LLMConfig`（不重复定义）
- [x] T009 Implement `LLMManager` in `toolkit/core/llm/manager.py`：构造函数接收 ConfigManager，实现 `get_provider()`、`get_config()`、`update_config()`、`switch_model()`、`record_tokens()`、`reset_session()`、`get_context_window_size()`、`get_context_usage_ratio()`，管理 Provider 状态（UNCONFIGURED/READY/DEGRADED/ERROR/BUDGET_PAUSED），定义所有 pyqtSignal（config_changed、provider_changed、token_updated、budget_alert、error_occurred、degradation_occurred）
- [x] T010 Extend `ConfigManager` in `toolkit/core/config_manager.py`：添加 `get_llm_config()` 和 `set_llm_config()` 方法，读写 `llm` 键
- [x] T011 Update `toolkit/core/llm/__init__.py` 导出 `LLMProvider`、`GLMProvider`、`ClaudeProvider`、`LLMManager`、`StreamChunk`、`ToolDefinition`
- [x] T012 Update `toolkit/core/__init__.py` 导出 `LLMManager`
- [x] T013 Wire `LLMManager` into `toolkit/app.py`：在 context 中注入 `llm_manager`，传入 ConfigManager 实例

**Checkpoint**: LLM 核心层可用 — 可通过 `context['llm_manager'].get_provider()` 获取 Provider 实例

---

## Phase 3: User Story 1 - 标题栏设置入口 (Priority: P1) 🎯 MVP

**Goal**: 标题栏主题按钮替换为设置按钮，点击弹出菜单包含「主题切换」和「LLM 模型设置」

**Independent Test**: 启动应用，点击标题栏齿轮图标，验证下拉菜单显示两个选项，主题切换正常工作

### Implementation for User Story 1

- [ ] T014 [US1] Create `SettingsButton` class in `toolkit/gui/widgets/title_bar.py`：QPainter 绘制齿轮图标，适配深浅色主题，点击弹出 QMenu
- [ ] T015 [US1] Modify `TitleBar` in `toolkit/gui/widgets/title_bar.py`：替换 `ThemeButton` 为 `SettingsButton`，保留 `theme_toggled` 信号，新增 `llm_settings_requested` 信号
- [ ] T016 [US1] Add SettingsButton 和 QMenu 样式到 `toolkit/gui/styles.py`（深色/浅色两套主题）
- [ ] T017 [US1] Connect signals in `toolkit/gui/main_window.py`：`theme_toggled` → `_toggle_theme()`，`llm_settings_requested` → 打开 LLM 设置对话框（占位）

**Checkpoint**: 标题栏设置按钮可用，主题切换行为不变，LLM 设置菜单项可点击（暂无对话框）

---

## Phase 4: User Story 2 - LLM 模型配置 (Priority: P1)

**Goal**: 通过标题栏设置入口打开 LLM 配置对话框，支持 Provider 选择、API Key 输入、模型选择、Temperature 调整、智能切换、Token 预算配置

**Independent Test**: 打开 LLM 设置对话框，配置 Provider 和 API Key，保存后重启应用验证配置持久化

### Implementation for User Story 2

- [ ] T018 [US2] Create `LLMSettingsDialog(QDialog)` in `toolkit/gui/widgets/llm_settings_dialog.py`：
  - Provider 选择区（GLM / Claude 互斥按钮）
  - API Key 密码框（每个 Provider 独立，带显示/隐藏切换）
  - 模型选择 QComboBox（根据 Provider 动态切换列表）
  - Temperature QSlider（0.0 ~ 1.0）
  - 智能切换 QCheckBox
  - Token 预算 QSpinBox
  - 告警阈值 QSpinBox（百分比）
  - 保存 / 取消按钮
- [ ] T019 [US2] Add LLMSettingsDialog 样式到 `toolkit/gui/styles.py`
- [ ] T020 [US2] Wire LLMSettingsDialog in `toolkit/gui/main_window.py`：`llm_settings_requested` → 创建并显示 `LLMSettingsDialog(llm_manager)`，保存时调用 `llm_manager.update_config()`

**Checkpoint**: LLM 配置对话框可用，配置可保存/加载/持久化

---

## Phase 5: User Story 4 - 状态栏 LLM 信息与快捷切换 (Priority: P1)

**Goal**: 底部状态栏右侧显示上下文圆环、token 用量、可点击模型名，支持快捷切换模型

**Independent Test**: 启动应用后查看状态栏显示模型信息，点击模型名弹出下拉切换

### Implementation for User Story 4

- [ ] T021 [US4] Create `ContextRingWidget(QWidget)` in `toolkit/gui/widgets/llm_status_widget.py`：QPainter 绘制空心圆环，支持 `set_ratio(float)` 更新占用比例，颜色分级（<80% 绿, <95% 黄, >=95% 红）
- [ ] T022 [US4] Create `LLMStatusWidget(QWidget)` in `toolkit/gui/widgets/llm_status_widget.py`：水平布局包含 ContextRing、TokenLabel（已使用/预算）、ModelLabel（可点击弹出 QMenu），连接 LLMManager 信号
- [ ] T023 [US4] Add LLMStatusWidget 样式到 `toolkit/gui/styles.py`
- [ ] T024 [US4] Integrate `LLMStatusWidget` into status bar in `toolkit/gui/main_window.py`：放置在版本号左侧，连接 `llm_manager` 信号（token_updated、provider_changed、config_changed）

**Checkpoint**: 状态栏 LLM 指示器可用，实时反映配置和 token 状态，模型可快捷切换

---

## Phase 6: User Story 3 - 跨模块 LLM 能力调用 (Priority: P2)

**Goal**: agent_chat 和其他模块通过框架接口使用 LLM，agent_chat 移除自身 LLM 配置 UI，首次启动自动迁移旧配置

**Independent Test**: agent_chat 通过全局配置正常对话，旧 API Key 自动迁移到全局配置

### Implementation for User Story 3

- [ ] T025 [US3] Implement config migration in `toolkit/core/llm/migration.py`：检测 `modules/agent_chat/data/config.json`，迁移 LLM 字段到框架配置，标记 `_migrated`
- [ ] T026 [US3] Call migration in `LLMManager.__init__()` in `toolkit/core/llm/manager.py`
- [ ] T027 [US3] Modify `AgentService._init_provider()` in `modules/agent_chat/src/service.py`：从 `context['llm_manager'].get_provider()` 获取 Provider，移除本地实例化逻辑
- [ ] T028 [US3] Update `AgentService` 的 token 记录：每次 LLM 响应后调用 `llm_manager.record_tokens()`
- [ ] T029 [US3] Remove「模型配置」Tab from `_SettingsDialog._build_model_tab()` in `modules/agent_chat/src/gui_tab.py`
- [ ] T030 [US3] Update `AgentConfig` in `modules/agent_chat/src/models.py`：移除 `provider`、`api_key`、`model_name`、`glm_api_key`、`claude_api_key`、`temperature` 等 LLM 相关字段
- [ ] T031 [US3] Update `modules/agent_chat/src/llm/__init__.py`：改为从 `toolkit.core.llm` 重新导出，保持向后兼容
- [ ] T031b [US3] Wire `provider_changed` signal in `modules/agent_chat/src/service.py`：监听 `llm_manager.provider_changed` 信号，刷新内部 Provider 引用

**Checkpoint**: agent_chat 通过全局 LLM 配置正常工作，旧配置自动迁移

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 智能切换、预算管理、主题适配、清理

- [ ] T032 Implement `smart_stream_chat()` in `toolkit/core/llm/manager.py`：包装 `stream_chat` 的异步生成器，捕获异常后检查备用 Provider API Key 是否可用，临时切换 Provider 重试，发射 `degradation_occurred` 信号，不修改持久化配置
- [ ] T033 Implement token budget alert logic in `toolkit/core/llm/manager.py`：到达阈值时发射 `budget_alert`，处理暂停/继续逻辑
- [ ] T034 [P] Wire budget alert to UI in `toolkit/gui/main_window.py`：`budget_alert` → QMessageBox 告警，用户选择继续或暂停
- [ ] T035 [P] Wire degradation notification to status bar in `toolkit/gui/main_window.py`：`degradation_occurred` → 状态栏 3 秒临时通知
- [ ] T036 Verify theme consistency for all new widgets（深色/浅色切换时 SettingsButton、LLMSettingsDialog、LLMStatusWidget 样式正确适配）
- [ ] T037 Run `quickstart.md` validation：验证模块获取 LLM Provider 的代码示例可正常运行

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始
- **Foundational (Phase 2)**: 依赖 Phase 1 完成，BLOCKS 所有 User Story
- **US1 (Phase 3)**: 依赖 Phase 2 完成
- **US2 (Phase 4)**: 依赖 Phase 3 完成（需要设置按钮已就位）
- **US4 (Phase 5)**: 依赖 Phase 2 完成，可与 Phase 3/4 并行
- **US3 (Phase 6)**: 依赖 Phase 2 完成，建议在 Phase 4 之后执行（确保全局配置 UI 可用后再迁移）
- **Polish (Phase 7)**: 依赖 Phase 2~6 全部完成

### User Story Dependencies

- **US1 (标题栏设置入口)**: 依赖 Foundational — 无跨 Story 依赖
- **US2 (LLM 模型配置)**: 依赖 US1（设置菜单入口）
- **US4 (状态栏指示器)**: 依赖 Foundational — 可与 US1/US2 并行
- **US3 (跨模块调用)**: 依赖 Foundational — 建议在 US2 之后（配置 UI 就绪）

### Parallel Opportunities

- T002 和 T003 可并行（不同文件）
- T006 和 T007 可并行（不同 Provider 文件）
- US4 (Phase 5) 可与 US1/US2 (Phase 3/4) 并行
- T034 和 T035 可并行（不同信号处理）

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 1: Setup（T001~T004）
2. Complete Phase 2: Foundational（T005~T013）— **CRITICAL**
3. Complete Phase 3: US1 标题栏设置入口（T014~T017）
4. **STOP and VALIDATE**: 验证齿轮按钮、下拉菜单、主题切换

### Incremental Delivery

1. Setup + Foundational → LLM 核心可用
2. US1 → 设置入口就位 → **MVP**
3. US2 → LLM 配置可保存 → 可手动配置并验证
4. US4 → 状态栏信息 → 用户体验完整
5. US3 → agent_chat 迁移 → 跨模块集成
6. Polish → 智能切换、预算管理 → 生产就绪

---

## Notes

- [P] 标记的任务操作不同文件，无依赖，可并行执行
- [Story] 标签映射到 spec.md 中的 User Story 编号
- 每个 Phase 完成后需验证 Checkpoint
- Provider 迁移时注意保持 `stream_chat` 接口签名不变
- agent_chat 的 `llm/` 目录保留为兼容层（重新导出），避免影响其他可能的引用
