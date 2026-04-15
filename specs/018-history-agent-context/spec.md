# Feature Specification: 历史文件选中联动 Agent 对话上下文

**Feature Branch**: `018-history-agent-context`  
**Created**: 2026-04-14  
**Status**: Draft  
**Input**: 用户在左侧历史面板中右键选择"发送到 Agent 对话"，将文件信息注入右侧 Agent Chat 对话上下文

## 目录

- [User Scenarios & Testing](#user-scenarios--testing-mandatory)
  - [User Story 1 - 右键发送文件到 Agent 对话](#user-story-1---右键发送文件到-agent-对话-priority-p1)
  - [User Story 2 - Agent 利用上下文进行分析对话](#user-story-2---agent-利用上下文进行分析对话-priority-p2)
  - [User Story 3 - 管理已注入的上下文](#user-story-3---管理已注入的上下文-priority-p2)
  - [Edge Cases](#edge-cases)
- [Requirements](#requirements-mandatory)
  - [Functional Requirements](#functional-requirements)
  - [Key Entities](#key-entities)
- [Clarifications](#clarifications)
- [Success Criteria](#success-criteria-mandatory)
  - [Measurable Outcomes](#measurable-outcomes)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 右键发送文件到 Agent 对话 (Priority: P1)

用户在左侧"抓取历史"或"分析历史"面板中右键点击一个条目，弹出上下文菜单中选择"发送到 Agent 对话"。操作后：
1. 右侧面板自动打开（如未打开）
2. Agent Chat 输入框上方出现**上下文区域**，显示选中文件的文件名和路径（支持多文件列表）
3. 输入框获得焦点，用户可以直接输入分析指令

**Why this priority**: 这是核心交互能力，将历史文件与 Agent 对话连接的唯一入口。

**Independent Test**: 右键任意历史条目 → 选择"发送到 Agent 对话" → 验证右侧面板正确展示上下文区域和文件信息。

**Acceptance Scenarios**:

1. **Given** 左侧"抓取历史"面板有 trace 数据, **When** 用户右键点击一个 trace 条目并选择"发送到 Agent 对话", **Then** 右侧面板自动打开，输入框上方显示上下文区域（包含文件名和路径），输入框获得焦点
2. **Given** 左侧"分析历史"面板有分析记录, **When** 用户右键点击一个分析条目并选择"发送到 Agent 对话", **Then** 右侧面板自动打开，输入框上方显示上下文区域（包含分析结果目录路径），输入框获得焦点
3. **Given** 右侧面板已打开且已有上下文, **When** 用户从历史面板再次发送一个不同的文件, **Then** 新文件追加到上下文区域，不覆盖已有上下文

---

### User Story 2 - Agent 利用上下文进行分析对话 (Priority: P2)

当用户发送消息时，如果当前存在已注入的文件上下文，系统自动将文件路径信息拼接到用户本轮消息尾部，使 Agent 能够理解用户正在讨论哪些文件。

**Why this priority**: 上下文联动的最终价值 — 让 Agent 在对话中识别具体文件。

**Independent Test**: 注入上下文后发送"分析这个 trace" → 验证 LLM 请求中包含文件路径信息。

**Acceptance Scenarios**:

1. **Given** 上下文区域显示一个 trace 文件, **When** 用户输入"帮我分析这个 trace"并发送, **Then** LLM 请求中用户消息尾部包含该 trace 文件路径信息
2. **Given** 上下文区域显示多个文件, **When** 用户发送消息, **Then** LLM 请求中用户消息尾部包含全部活跃文件路径信息
3. **Given** 没有上下文, **When** 用户直接发送消息, **Then** LLM 请求不包含额外的文件上下文信息

---

### User Story 3 - 管理已注入的上下文 (Priority: P2)

上下文区域中的每个文件项都支持单独移除：点击该项右侧关闭按钮（×）或在右侧区域选中该项后按 Backspace/Delete 删除。清除后，后续对话消息不再包含被删除文件的上下文信息。

**Why this priority**: 用户需要控制上下文的生命周期，避免过期上下文干扰对话。

**Independent Test**: 注入上下文 → 点击关闭按钮 → 验证上下文区域中的目标项消失，后续消息不含该文件信息。

**Acceptance Scenarios**:

1. **Given** 上下文区域已显示多个文件项, **When** 用户点击其中一个文件项的关闭按钮, **Then** 仅该文件项被移除，其他上下文保留
2. **Given** 上下文区域中某文件项被选中, **When** 用户按 Backspace 或 Delete, **Then** 该文件项被移除
3. **Given** 当前会话上下文已被全部清除, **When** 用户发送消息, **Then** LLM 请求中不包含之前的文件上下文

---

### Edge Cases

- 选中的文件路径不存在（已被手动删除）时，上下文区域仍显示路径但标注"文件不存在"
- 右侧 Agent Chat 尚未初始化时收到 EventBus 事件，需缓存等待初始化完成后处理
- 文件路径包含中文或特殊字符时，显示和传递均正常
- 同一文件重复发送时，不重复追加（按 `file_path` 去重）
- 上下文按会话隔离：切换会话时显示各自上下文，新会话默认空上下文

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: "抓取历史"面板右键菜单 MUST 增加"发送到 Agent 对话"选项
- **FR-002**: "分析历史"面板右键菜单 MUST 增加"发送到 Agent 对话"选项
- **FR-003**: 点击"发送到 Agent 对话"后，系统 MUST 通过 EventBus 发布 `history.send_to_agent` 事件，payload MUST 包含 `file_path`（str）、`file_name`（str）、`context_type`（"trace"|"analysis"），并 MAY 包含 `missing`（bool）
- **FR-004**: Agent Chat 模块 MUST 监听 `history.send_to_agent` 事件
- **FR-005**: 收到事件后，Agent Chat MUST 在输入框上方展示上下文区域，显示文件名和路径，并支持多文件列表
- **FR-006**: 如果右侧面板未打开，系统 MUST 自动打开右侧面板
- **FR-007**: 上下文区域中的每个文件项 MUST 包含关闭按钮（×），点击后仅移除该文件项
- **FR-008**: 上下文区域中被选中的文件项 MUST 支持按 Backspace/Delete 快捷删除
- **FR-009**: 用户发送消息时，如果存在活跃上下文，系统 MUST 将全部活跃文件路径拼接到用户本轮消息尾部后再发起 LLM 请求
- **FR-010**: 上下文 MUST 按会话隔离并跨消息保持，直到用户手动清除；切换会话后 MUST 恢复该会话各自上下文
- **FR-011**: 新建会话时 MUST 初始化为空上下文，不继承其他会话上下文

### Key Entities

- **FileContext**: 注入到 Agent 对话的文件上下文信息
  - `context_id`: str — 上下文项唯一标识
  - `file_path`: str — 文件绝对路径
  - `file_name`: str — 显示用文件名
  - `context_type`: str — "trace" 或 "analysis"
- **ContextBar**: Agent Chat 输入框上方的上下文区域 UI 组件（多文件列表，支持点击 × / Backspace/Delete 删除）

## Clarifications

- **Q: 上下文触发方式？** A: 仅通过右键菜单"发送到 Agent 对话"显式触发，不做单击自动注入
- **Q: 上下文信息粒度？** A: 仅显示文件名和路径，不显示设备型号、SoC 等元信息
- **Q: EventBus 是否已有？** A: 已有，通过 `context["event_bus"]` 全局可用，事件命名规范为 `{模块名}.{动作}`
- **Q: 上下文作用域？** A: 按会话隔离；当前会话保留上下文，新会话独立且初始为空
- **Q: 注入到 LLM 请求的格式？** A: 将上下文路径拼接到用户本轮消息尾部
- **Q: 单会话上下文数量？** A: 支持多文件；发送新文件为追加，按路径去重
- **Q: 上下文删除方式？** A: 支持点击文件项的 × 删除；在右侧区域选中文件项后按 Backspace/Delete 删除

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 右键"发送到 Agent 对话"后，右侧面板在 1 秒内打开并显示上下文区域
- **SC-002**: 上下文区域正确显示文件名和路径
- **SC-003**: 多文件上下文下，LLM 请求中用户消息尾部包含全部活跃文件路径，且无重复路径
- **SC-004**: 删除指定上下文文件项后，后续消息不再包含该文件路径
- **SC-005**: 切换会话后，上下文区域恢复该会话自身上下文；新建会话默认为空上下文
