# Feature Specification: 全局设置与 LLM 能力抽象

**Feature Branch**: `008-global-settings-llm`
**Created**: 2026-04-03
**Status**: Draft
**Input**: User description: "全局设置与 LLM 能力抽象：标题栏设置入口（主题切换+LLM模型设置），LLM Provider 接口下沉到主框架供跨模块使用"

## 目录

- [User Scenarios & Testing](#user-scenarios--testing)
  - [User Story 1 - 标题栏设置入口](#user-story-1---标题栏设置入口-priority-p1)
  - [User Story 2 - LLM 模型配置](#user-story-2---llm-模型配置-priority-p1)
  - [User Story 3 - 跨模块 LLM 能力调用](#user-story-3---跨模块-llm-能力调用-priority-p2)
  - [User Story 4 - 状态栏 LLM 信息与快捷切换](#user-story-4---状态栏-llm-信息与快捷切换-priority-p1)
  - [Edge Cases](#edge-cases)
- [Requirements](#requirements)
  - [Functional Requirements](#functional-requirements)
  - [Key Entities](#key-entities)
- [Success Criteria](#success-criteria)
- [Assumptions](#assumptions)
- [Clarifications](#clarifications)

## User Scenarios & Testing

### User Story 1 - 标题栏设置入口 (Priority: P1)

用户点击标题栏原主题切换按钮的位置，弹出下拉菜单，包含「主题切换」和「LLM 模型设置」两个选项。点击「主题切换」切换深浅色主题（与当前行为一致）。点击「LLM 模型设置」打开 LLM 配置面板。

**Why this priority**: 设置入口是所有后续功能的基础交互框架，需要先就位。

**Independent Test**: 启动应用后点击标题栏设置按钮，验证下拉菜单显示两个选项并可正常响应点击。

**Acceptance Scenarios**:

1. **Given** 应用已启动，**When** 用户点击标题栏设置按钮，**Then** 弹出下拉菜单显示「主题切换」和「LLM 模型设置」
2. **Given** 下拉菜单已弹出，**When** 用户点击「主题切换」，**Then** 主题在深色/浅色之间切换（与当前行为一致）
3. **Given** 下拉菜单已弹出，**When** 用户点击「LLM 模型设置」，**Then** 弹出 LLM 配置面板

---

### User Story 2 - LLM 模型配置 (Priority: P1)

用户通过标题栏设置入口打开 LLM 配置面板，可以选择 LLM Provider（GLM / Claude）、输入 API Key、选择模型、调整 Temperature 等参数。配置保存后对所有模块生效。

**Why this priority**: LLM 配置是跨模块能力的核心，需要从 agent_chat 模块提取到框架层。

**Independent Test**: 打开 LLM 配置面板，修改 Provider 和 API Key 后保存，验证配置持久化且下次启动仍然生效。

**Acceptance Scenarios**:

1. **Given** LLM 配置面板已打开，**When** 用户切换 Provider 为 Claude 并输入 API Key，**Then** 可用模型列表更新为 Claude 系列模型
2. **Given** 用户已配置 LLM 参数，**When** 用户点击保存，**Then** 配置持久化到本地，关闭面板后重新打开时配置保持不变
3. **Given** LLM 配置已保存，**When** 用户重启应用，**Then** 上次保存的配置自动加载

---

### User Story 3 - 跨模块 LLM 能力调用 (Priority: P2)

各模块（如 perfetto_analysis、agent_chat）通过框架提供的统一接口获取已配置的 LLM Provider，无需各自管理 API Key 和 Provider 实例化逻辑。agent_chat 模块的 LLM 设置 UI 移除，改为使用框架全局配置。

**Why this priority**: 这是 LLM 能力复用的基础，但需要 US1 和 US2 先就位。

**Independent Test**: agent_chat 模块通过框架接口获取 LLM Provider 后能正常进行对话。

**Acceptance Scenarios**:

1. **Given** 全局 LLM 已配置且 API Key 有效，**When** agent_chat 模块请求 LLM Provider，**Then** 获得可用的 Provider 实例并正常对话
2. **Given** 全局 LLM 未配置（无 API Key），**When** 模块请求 LLM Provider，**Then** 返回明确的错误提示引导用户配置
3. **Given** agent_chat 旧版设置界面，**When** 完成迁移后，**Then** agent_chat 的模型配置 Tab 页移除，由全局设置替代

---

### User Story 4 - 状态栏 LLM 信息与快捷切换 (Priority: P1)

底部状态栏右侧从左到右显示：上下文窗口空心圆环（类 Cursor 样式）→ 本次会话 token 用量（已使用/预算上限）→ 模型名称（可点击切换）→ 版本号。用户点击模型名称弹出下拉列表快捷切换模型。

**Why this priority**: 状态栏提供即时信息反馈和快速操作入口，提升使用效率。

**Independent Test**: 启动应用后查看底部状态栏右侧显示上下文圆环、token 用量和模型名称，点击模型名称弹出模型列表并可切换。

**Acceptance Scenarios**:

1. **Given** 应用已启动且 LLM 已配置，**When** 用户查看底部状态栏，**Then** 右侧显示上下文圆环、token 用量（格式：已使用/预算）和模型名称
2. **Given** LLM 正在处理请求，**When** token 消耗增加，**Then** 上下文圆环实时更新占用比例，token 用量数字实时更新
3. **Given** 底部状态栏显示模型名称，**When** 用户点击模型名称，**Then** 弹出当前 Provider 可用模型的下拉列表
4. **Given** 模型下拉列表已弹出，**When** 用户选择另一个模型，**Then** 模型立即切换并持久化，状态栏更新显示新模型名称
5. **Given** LLM 未配置（无 API Key），**When** 用户查看状态栏，**Then** 显示「未配置 LLM」提示

---

### Edge Cases

- 用户未配置任何 LLM API Key 时，依赖 LLM 的功能 MUST 显示友好提示而非崩溃
- 配置文件损坏或格式异常时 MUST 使用默认值并记录日志
- API Key 格式校验：空值、超长值、非法字符均不应导致崩溃
- 多模块同时请求 LLM Provider 时 MUST 线程安全
- 模型快捷切换时，如果有正在进行的 LLM 请求，MUST 不影响已发起的请求
- agent_chat 旧配置文件不存在时，自动迁移逻辑 MUST 安静跳过不报错
- 状态栏 token 显示：在无 LLM 活动时显示「0 tokens」或上次会话的累计值
- Token 预算告警：当会话 token 用量达到预算的告警阈值（用户可配置，默认 80%）时，立即弹出告警提示。当前进行中的请求不中断，用户可选择「继续后续请求」或「暂停新请求」
- 智能切换降级时 MUST 在状态栏显示临时通知（如「已降级到 GLM」），降级期间所有模块共享降级后的 Provider
- LLM API 超时/认证失败/限流时，LLM Manager MUST 统一捕获并通过信号通知模块，模块不需自行处理 LLM 异常
- Token 计数为应用级会话（启动到关闭），所有模块 LLM 调用累加

## Requirements

### Functional Requirements

- **FR-001**: 标题栏原主题切换按钮位置 MUST 替换为设置按钮（齿轮图标），点击弹出下拉菜单
- **FR-002**: 下拉菜单 MUST 包含「主题切换」和「LLM 模型设置」两个选项
- **FR-003**: 「主题切换」选项 MUST 保持与当前相同的深浅色切换行为
- **FR-004**: 「LLM 模型设置」选项 MUST 打开 LLM 配置面板
- **FR-005**: LLM 配置面板 MUST 支持选择 Provider（GLM / Claude）
- **FR-006**: LLM 配置面板 MUST 支持输入各 Provider 的 API Key
- **FR-007**: LLM 配置面板 MUST 根据选中的 Provider 显示可用模型列表
- **FR-008**: LLM 配置面板 MUST 支持调整 Temperature（0.0 ~ 1.0）
- **FR-009**: LLM 配置 MUST 持久化到框架级配置文件中
- **FR-010**: 框架 MUST 提供统一接口供模块获取已配置的 LLM Provider 实例
- **FR-011**: agent_chat 模块 MUST 移除自身的 LLM 模型配置 Tab，改为使用全局配置
- **FR-012**: agent_chat 模块的其他设置项（SOP 管理、MCP 管理、高级设置）MUST 保留在模块自身的设置中
- **FR-013**: 底部状态栏右侧 MUST 显示当前 LLM 模型名称（可点击）
- **FR-014**: 底部状态栏 MUST 显示当前会话的 token 使用量，格式为「已使用/预算上限」
- **FR-015**: 底部状态栏 MUST 在 token 用量左侧显示上下文窗口空心圆环，实时反映上下文占用比例
- **FR-016**: 点击状态栏模型名称 MUST 弹出当前 Provider 可用模型列表，支持快捷切换
- **FR-017**: 模型快捷切换后 MUST 立即持久化并通知已注册的模块
- **FR-018**: LLM 未配置时状态栏 MUST 显示「未配置 LLM」提示
- **FR-019**: LLM 配置面板 MUST 支持「智能切换」选项（主 Provider 失败时自动降级到备用 Provider）
- **FR-020**: LLM 配置面板 MUST 支持设置 token 预算上限
- **FR-021**: 每个 Provider 的 API Key MUST 独立存储，切换 Provider 时不丢失已保存的 Key
- **FR-022**: 首次启动时 MUST 自动检测 agent_chat 旧版 LLM 配置并迁移到框架级配置
- **FR-023**: Token 用量达到预算告警阈值（用户可配置，默认 80%）时 MUST 立即弹出告警，当前请求不中断，用户可选择继续或暂停后续请求
- **FR-024**: 智能切换降级发生时 MUST 在状态栏显示临时通知

### Key Entities

- **LLM 配置 (LLMConfig)**: Provider 类型、API Key（按 Provider 分别存储）、模型名称、Temperature、Max Tokens、Token 预算上限、预算告警阈值（默认 80%）、智能切换开关
- **LLM Provider 接口**: 统一的流式对话接口（stream_chat）、可用模型列表查询、Provider 名称标识
- **设置菜单**: 标题栏设置按钮及其下拉菜单项
- **LLM Manager**: 框架层 LLM 管理器，管理 Provider 生命周期、配置持久化、配置变更通知
- **状态栏 LLM 指示器**: 底部状态栏右侧的模型信息组件，显示模型名+token 用量，支持点击快捷切换

## Success Criteria

### Measurable Outcomes

- **SC-001**: 用户可在 1 次点击内完成 LLM 模型切换（状态栏模型名 → 选择模型）
- **SC-002**: agent_chat 通过全局配置进行对话的延迟与直接配置时无差异
- **SC-003**: 配置保存后重启应用，100% 场景下配置正确恢复
- **SC-004**: 所有依赖 LLM 的模块可通过统一接口获取 Provider，无需自行管理 API Key

## Assumptions

- LLM Provider 类型初期仅支持 GLM 和 Claude，后续可扩展
- API Key 以明文存储在本地配置文件中（与当前 agent_chat 行为一致）
- LLM Provider 的具体实现代码（GLMProvider、ClaudeProvider）迁移到 toolkit/core/llm/，各模块通过框架层接口获取 LLM 能力
- 框架级 LLM 配置文件使用 `data/config.json`（复用现有 ConfigManager）

## Clarifications

### Session 2026-04-03

- Q: LLM Provider 代码归属位置？ → A: 选项 B — Provider 实现迁移到 toolkit/core/llm/，agent_chat 改为引用框架层接口。各模块通过 toolkit.core.llm 获取 LLM 能力，不依赖 agent_chat。
- Q: agent_chat 现有 LLM 配置迁移策略？ → A: 选项 A — 首次启动自动检测 agent_chat 旧配置并迁移到框架级配置，用户无感知。
- Q: LLM 配置面板 UI 形式？ → A: 弹出对话框（独立窗口，类似 agent_chat 现有设置对话框）。
- Q: agent_chat「智能切换」功能归属？ → A: 上升到全局 LLM 设置。
- Q: 模块获取 LLM Provider 的方式？ → A: 通过 context 字典（`context['llm_manager']`），与现有 ConfigManager、AdbManager 传递模式一致。
- Q: API Key 存储策略？ → A: 每个 Provider 独立存储 API Key，切换 Provider 时不丢失。
- Q: Max Tokens 管理方式？ → A: 全局设默认值，模块调用时可覆盖。不在 LLM 设置对话框中显示，但在底部状态栏显示 token 使用信息。
- Q: 标题栏设置按钮图标？ → A: 齿轮图标。
- Q: 底部状态栏内容？ → A: 右侧显示当前模型名称 + token 使用量，支持快捷切换。
- Q: 快捷切换模型交互方式？ → A: 点击状态栏模型名弹出下拉列表切换。
- Q: 状态栏 token 显示范围？ → A: 当前会话累计，格式为「已使用/预算上限」。预算上限为用户设置的 token 预算。
- Q: 上下文窗口显示？ → A: 在 token 用量左侧显示空心圆环，表示当前上下文窗口占用比例（类似 Cursor 的样式）。
- Q: 状态栏右侧布局顺序？ → A: 上下文圆环 → token 用量文本 → 模型名称（可点击切换） → 版本号。
- Q:「智能切换」全局层行为？ → A: 失败降级 — 主 Provider 请求失败时自动切换到备用 Provider。
- Q: Token 预算告警时机？ → A: 到达预算的可配置阈值（默认 80%）时立即弹出告警，当前请求不中断。用户选择继续或暂停后续请求。
- Q:「会话」定义？ → A: 应用级会话 — 启动到关闭为一个会话，所有模块的 LLM 调用 token 累加。
- Q: LLM API 错误处理？ → A: LLM Manager 统一捕获错误并通过 pyqtSignal 通知调用模块，模块只需监听信号。
