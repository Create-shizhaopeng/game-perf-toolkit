# Feature Specification: 历史面板批量操作与 Perfetto AI 分析接入

**Feature Branch**: `009-history-batch-analysis`  
**Created**: 2026-04-03  
**Status**: Draft  
**Input**: 历史面板支持多选、批量删除和批量分析；接入 Pydantic AI 多 Agent 编排引擎，实现 LLM 驱动的 Perfetto 分析

## 目录

- [User Scenarios & Testing](#user-scenarios--testing-mandatory)
  - [User Story 1 — 历史面板多选与批量删除](#user-story-1--历史面板多选与批量删除-priority-p1)
  - [User Story 2 — 对话式 AI 分析（单条）](#user-story-2--对话式-ai-分析单条-priority-p1)
  - [User Story 3 — 批量 AI 分析](#user-story-3--批量-ai-分析-priority-p1)
  - [User Story 4 — 外部 trace 拖入管理](#user-story-4--外部-trace-拖入管理-priority-p1)
  - [User Story 5 — 分析历史与报告查看](#user-story-5--分析历史与报告查看-priority-p1)
  - [User Story 6 — 包名数据库](#user-story-6--包名数据库-priority-p2)
  - [Edge Cases](#edge-cases)
- [Requirements](#requirements-mandatory)
  - [Functional Requirements](#functional-requirements)
  - [Key Entities](#key-entities)
- [Success Criteria](#success-criteria-mandatory)
  - [Measurable Outcomes](#measurable-outcomes)
- [Assumptions](#assumptions)
- [Clarifications](#clarifications)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 历史面板多选与批量删除 (Priority: P1)

用户在历史记录面板中批量清理不再需要的 trace 文件和会话。通过 Ctrl+点击（离散多选）和 Shift+点击（连续范围多选）选中多个项目，一键删除所有选中项。

**Why this priority**: 历史记录随时间积累占用大量磁盘空间，批量删除是最基础的管理需求。

**Independent Test**: 打开历史面板，使用 Ctrl/Shift 选中多个项目，点击删除，确认后所有选中项被删除。

**Acceptance Scenarios**:

1. **Given** 历史面板中有多个会话和 trace, **When** 用户 Ctrl+点击选中 3 个 trace, **Then** 3 个 trace 高亮显示为选中状态
2. **Given** 已选中多个项目, **When** 用户点击删除按钮, **Then** 弹出确认对话框，显示待删除项数量和总大小
3. **Given** 确认删除, **When** 选中项既包含会话也包含 trace, **Then** 会话级删除删除该会话下所有 trace，trace 级删除仅删除单个文件

---

### User Story 2 — 对话式 AI 分析（单条） (Priority: P1)

用户在历史面板的右栏对话区域中选中一个 trace，trace 路径自动带入对话输入框。用户描述分析意图（如"分析卡顿原因"、"检查内存泄漏"），AI 在对话区域中流式输出分析过程（思考→工具调用→结论），分析完成后生成 HTML 报告并用系统浏览器打开。

**Why this priority**: 打通 capture → analysis 的核心链路，用 LLM 驱动分析是整个功能的基石。

**Independent Test**: 选中一个 trace，在对话框中输入"分析卡顿原因"，对话区域展示 AI 分析过程，完成后浏览器打开 HTML 报告。

**Acceptance Scenarios**:

1. **Given** 用户在左栏选中一个 trace, **When** 查看右栏对话输入框, **Then** trace 路径已自动带入
2. **Given** trace 来自 jank 监控（有目标进程元数据）, **When** 自动带入, **Then** 输入框同时标注目标进程，无额外提示
3. **Given** trace 为用户手动添加（无元数据）, **When** 自动带入, **Then** 输入框显示置灰提示"请描述分析场景和目标进程"
4. **Given** 用户输入分析意图并发送, **When** AI 分析进行中, **Then** 右栏对话区域流式展示分析过程（思考推理、工具调用、中间结果）
5. **Given** 分析完成, **When** AI 输出最终结论, **Then** 生成 HTML 报告文件，自动用系统浏览器打开
6. **Given** 分析完成, **When** 查看结果目录, **Then** 报告存放在独立分析文件夹中（HTML + 原始数据子文件夹）

---

### User Story 3 — 批量 AI 分析 (Priority: P1)

用户选中多个 trace 后发起批量分析，系统为每个 trace 创建独立的 Sub Agent 进行分析，各 Agent 之间上下文完全隔离。分析完成后 Review Agent 对结果做交叉评审，最终为每个 trace 生成独立的 HTML 报告。

**Why this priority**: 自动 jank 抓取会一次性产生多个 trace，用户需要高效地批量分析。

**Independent Test**: 选中 3 个 trace，在对话框中输入"分析所有 trace 的卡顿原因"，系统依次分析并生成 3 份独立报告。

**Acceptance Scenarios**:

1. **Given** 用户选中 3 个 trace 并发送分析请求, **When** 分析开始, **Then** 系统为每个 trace 分配独立 Sub Agent，默认串行执行
2. **Given** 批量分析进行中, **When** 查看右栏对话区域, **Then** 展示每个 trace 的分析状态（排队中/分析中/评审中/完成/失败）
3. **Given** 某个 trace 分析失败, **When** 其余 trace 继续, **Then** 失败的 trace 标记失败原因，不影响其余分析
4. **Given** 所有 Sub Agent 完成, **When** Review Agent 启动, **Then** 对各 trace 的分析结论做一致性检查和交叉验证
5. **Given** 批量分析全部完成, **When** 查看结果, **Then** 每个 trace 有独立的 HTML 报告和原始数据文件夹

---

### User Story 4 — 外部 trace 拖入管理 (Priority: P1)

用户将外部 trace 文件拖入历史面板左栏顶部的"用户 trace"区域，系统自动将文件移动到托管目录并纳入管理。用户随后可以从列表中选中并触发分析。

**Why this priority**: 用户经常需要分析非本工具抓取的 trace 文件，需要统一的管理入口。

**Independent Test**: 从文件管理器拖入一个 .perfetto-trace 文件到历史面板顶部区域，文件被纳入管理列表。

**Acceptance Scenarios**:

1. **Given** 历史面板已打开, **When** 用户将外部 trace 文件拖入左栏顶部"用户 trace"区域, **Then** 文件移动到托管目录，并出现在列表顶部
2. **Given** 用户拖入的 trace 无元数据, **When** 选中并触发分析, **Then** 对话框置灰提示用户描述分析场景
3. **Given** 拖入的文件不是有效的 trace 格式, **When** 拖入, **Then** 提示格式不支持

---

### User Story 5 — 分析历史与报告查看 (Priority: P1)

历史面板左栏分为上下两部分（可拖动分割），上半部为 trace 管理，下半部为分析历史。分析历史展示所有已完成的分析任务，与 trace 历史格式一致——每个分析结果是一个文件夹节点，包含 HTML 报告和原始数据子文件夹。

**Why this priority**: 用户需要查阅和管理历史分析结果。

**Independent Test**: 打开历史面板，在左栏下半部看到分析历史列表，双击某个分析结果在浏览器中打开 HTML 报告。

**Acceptance Scenarios**:

1. **Given** 有已完成的分析任务, **When** 打开历史面板, **Then** 左栏下半部展示分析历史，格式与 trace 历史一致
2. **Given** 分析历史中有一条记录, **When** 用户双击, **Then** 系统浏览器打开该 trace 的 HTML 报告
3. **Given** 用户选中分析记录, **When** 点击"目录"按钮, **Then** 打开分析结果文件夹（含 HTML 和原始数据子目录）
4. **Given** 左栏上下两部分, **When** 用户拖动分割线, **Then** 两部分高度随之调整

---

### User Story 6 — 包名数据库 (Priority: P2)

系统维护一个包名数据库，记录应用名称与进程名的映射关系。数据库从历史分析中自动学习新的包名映射，支持 JSON 格式导出和导入，方便团队成员共享配置。

**Why this priority**: 提升分析效率，减少用户重复输入进程名；团队共享进一步降低使用门槛。

**Independent Test**: 分析一个新 trace 后，目标进程自动加入包名数据库；导出 JSON 后另一个团队成员导入，包名映射立即可用。

**Acceptance Scenarios**:

1. **Given** 用户分析了一个包含新包名的 trace, **When** 分析完成, **Then** 包名和进程名自动记录到数据库
2. **Given** 用户手动添加的 trace, **When** AI 自动检测到进程名, **Then** 弹出确认"是否记录该包名映射"
3. **Given** 包名数据库有记录, **When** 用户导出 JSON, **Then** 生成可分享的 JSON 文件
4. **Given** 收到团队成员的 JSON 文件, **When** 导入, **Then** 新包名映射合并到本地数据库（冲突时保留本地版本）

---

### Edge Cases

- 分析过程中应用退出：分析任务中断，下次打开显示为"中断"状态，用户可选择重新分析
- 批量删除中包含正在被分析的 trace：跳过正在分析的 trace，删除其余项，提示用户
- 拖入超大 trace 文件（>1GB）：显示移动进度条，避免 UI 阻塞
- LLM 服务不可用：提示用户检查 LLM 配置，分析按钮保持可用但发送后报错
- 多个用户同时分析同一个 trace：允许，生成独立的分析结果文件夹（按时间戳区分）
- 历史面板宽度被拖到极窄：设置最小宽度限制（左栏 280px + 右栏 320px = 最小 600px）
- 分析报告 HTML 中引用的原始数据路径使用相对路径，确保文件夹整体可迁移
- 分析中 token 消耗达到全局预算阈值：立即告警，当前请求继续，用户决定后续请求是否继续
- 单次分析超时（5 分钟无新输出）：自动中止该 Agent，标记为超时失败

## Requirements *(mandatory)*

### Functional Requirements

**历史面板布局（左右双栏）**

- **FR-001**: 历史面板 MUST 采用左右双栏布局——左栏为列表管理区，右栏为 AI 对话区
- **FR-002**: 左栏 MUST 分为上下两部分（trace 管理 / 分析历史），中间有可拖动的分割线
- **FR-003**: 左栏顶部 MUST 有一个"用户 trace"拖入区域，支持文件拖放
- **FR-004**: 右栏 MUST 包含对话历史显示区域和底部输入框
- **FR-005**: 历史面板 MUST 支持手动拖动左边缘加宽（始终贴右侧），最小宽度 600px

**多选与批量操作**

- **FR-006**: 左栏 trace 列表 MUST 支持多选模式（Ctrl+点击离散多选、Shift+点击连续范围多选）
- **FR-007**: 操作按钮 MUST 根据多选情况更新提示（如"删除 3 项"、"分析 2 个 trace"）
- **FR-008**: 批量删除 MUST 弹出确认对话框，显示待删除项的数量和总大小

**对话式分析**

- **FR-009**: 选中 trace 后 MUST 自动将 trace 路径带入右栏输入框
- **FR-010**: 对于有目标进程元数据的 trace，输入框 MUST 自动标注目标进程
- **FR-011**: 对于无元数据的 trace，输入框 MUST 显示置灰提示引导用户描述场景和目标进程
- **FR-012**: 用户发送分析请求后，右栏 MUST 流式展示 AI 分析过程（思考推理、工具调用、中间结果、最终结论）
- **FR-013**: 分析过程中用户 MUST 能取消分析

**多 Agent 分析引擎**

- **FR-014**: 系统 MUST 使用 Pydantic AI 框架构建多 Agent 编排引擎
- **FR-015**: Main Agent MUST 负责用户意图分析、场景路由、任务分配和结果汇总
- **FR-016**: 每个 trace 的分析 MUST 由独立的 Sub Agent 执行，各 Agent 上下文完全隔离
- **FR-017**: Sub Agent MUST 能加载不同的 prompt/skill，根据场景（卡顿/ANR/内存等）使用对应 SOP
- **FR-018**: 批量分析完成后 MUST 启动 Review Agent 对结果做交叉评审和一致性检查
- **FR-019**: 批量分析默认串行执行，用户可配置并行数

**分析结果与报告**

- **FR-020**: 每个 trace 的分析结果 MUST 存放在独立文件夹中（`output/analysis/<trace_stem>_<YYYYMMDD_HHmmss>/`）
- **FR-021**: 分析文件夹 MUST 包含 HTML 报告文件和原始数据子文件夹
- **FR-022**: HTML 报告 MUST 包含最终结论和推理出结论的原始数据
- **FR-023**: 分析完成后 MUST 自动用系统默认浏览器打开 HTML 报告
- **FR-024**: HTML 报告中引用原始数据 MUST 使用相对路径，确保整体可迁移

**分析历史**

- **FR-025**: 左栏下半部 MUST 展示所有已完成/失败/进行中的分析任务
- **FR-026**: 分析历史的展示格式 MUST 与 trace 历史一致（树形结构，文件夹节点 + 子文件节点）
- **FR-027**: 双击分析记录 MUST 在系统浏览器中打开 HTML 报告
- **FR-028**: 分析历史 MUST 支持删除操作（删除分析结果文件夹）

**数据管理**

- **FR-029**: 工具抓取的 trace MUST 在数据库中记录元数据（含目标进程、设备信息等）
- **FR-030**: 分析状态 MUST 在 trace 节点旁显示标记（未分析/分析中/完成 ✅/失败 ❌）
- **FR-031**: 系统 MUST 维护包名数据库，记录应用名称与进程名的映射关系
- **FR-032**: 包名数据库 MUST 从历史分析中自动学习新映射
- **FR-033**: 包名数据库 MUST 支持 JSON 格式导出和导入

**Token 控制**

- **FR-034**: 分析 MUST 复用全局 LLMManager 的 token 预算
- **FR-035**: 单次分析 MUST 有超时机制（5 分钟无新输出则中止）

**架构变更**

- **FR-036**: 现有的 Perfetto 分析 tab（`PerfettoAnalysisTab`）MUST 被移除，保留底层分析服务和 CLI 命令
- **FR-037**: 拖入外部 trace 时 MUST 自动移动到托管目录并纳入管理

### Key Entities

- **HistorySession**: 一次抓取会话，包含设备信息、时间、多个 trace 文件
- **HistoryTrace**: 单个 trace 文件，属于某个 Session，包含文件路径、大小、分析状态、目标进程元数据
- **AnalysisTask**: 一次分析任务，包含 trace 路径、分析意图、状态（排队中/分析中/评审中/完成/失败）、结果文件夹路径
- **AnalysisReport**: 分析报告，包含 HTML 文件路径、原始数据文件夹路径、结论摘要
- **PackageMapping**: 包名映射记录，包含应用名称、进程名、来源（自动学习/手动添加）、更新时间
- **AgentRole**: Agent 角色枚举（MainAgent / SubAgent / ReviewAgent）
- **ConversationMessage**: 对话消息，包含角色（user/assistant/tool/system）、内容、时间戳；当 role=tool 时包含 tool_name(str) 和 tool_result(dict)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户可以在 3 次点击内完成多选 + 批量删除操作
- **SC-002**: 单条 trace 从选中到 AI 分析启动不超过 2 秒
- **SC-003**: 批量分析 5 个 trace 时，每个 trace 的分析状态实时可见
- **SC-004**: 分析完成后 HTML 报告自动在浏览器中打开，用户无需手动查找文件
- **SC-005**: 已分析的 trace 在历史面板中 100% 可通过状态标记识别
- **SC-006**: 外部 trace 拖入后 3 秒内出现在管理列表中
- **SC-007**: 包名数据库导出的 JSON 文件可以被其他团队成员成功导入
- **SC-008**: 对话区域的 AI 流式输出延迟不超过首 token 500ms

## Assumptions

- Pydantic AI 及 pydantic-ai-litellm 包可正常安装并与现有 LiteLLM + LLMManager 集成
- 现有 pa_* 工具（14 个）可通过 Pydantic AI 的 toolsets API 注册为 Agent 工具
- 现有 perfetto_analysis 的分析引擎、服务层和 SOP 文档可被 Sub Agent 直接调用
- HTML 报告模板可基于现有 Markdown 报告模板转换生成
- 分析结果文件夹结构参考现有 perfetto_analysis 的输出目录设计
- 移除 PerfettoAnalysisTab 后，perfetto_analysis 插件的 `register_gui_tab` 钩子不再注册 GUI tab，但其余钩子（CLI、Agent 工具、事件监听）保持不变

## Clarifications

### Session 2026-04-03

- Q: 对话输入框的交互模型 → A: 右栏对话区域流式展示 AI 分析过程（思考→工具调用→结论），左右双栏布局
- Q: 分析的 token 控制与超时策略 → A: 复用全局 LLMManager 的 token 预算 + 单次分析 5 分钟超时
- Q: 取消分析 tab 后现有 GUI 组件处理 → A: 保留底层分析服务和 CLI 命令，仅移除 GUI tab

### 技术选型决策

| 决策 | 选择 | 原因 |
|---|---|---|
| 多 Agent 框架 | Pydantic AI | 轻量库模式，Pydantic 生态一致，适合桌面应用 |
| 分析触发方式 | 对话式（类 Cursor） | 自然语言描述意图，LLM 自动路由场景 |
| 结果呈现 | HTML + 系统浏览器 | 便于分享和离线查看 |
| 批量策略 | 独立 Sub Agent | 上下文隔离，提高分析准确度 |
| 并行策略 | 默认串行，用户可配 | 资源友好，兼顾灵活性 |
| 面板布局 | 左右双栏滑出面板 | 左栏管理，右栏对话，空间利用最大化 |
| 旧分析 tab | 移除 GUI，保留服务/CLI | 服务层是 Agent 工具链的基础 |
| token 控制 | 全局预算 + 单次超时 | 与已有 LLMManager 预算体系一致 |
