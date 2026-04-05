# Feature Specification: LLM Prompt 预算管理

**Feature Branch**: `010-prompt-budget-management`
**Created**: 2026-04-05
**Updated**: 2026-04-05
**Status**: Clarified (v3 — LLM 自主决策 + 工具返回值压缩)
**Input**: User description: "LLM Prompt Budget Management — 为 Perfetto 分析 Agent 提供动态上下文窗口管理，解决 GLM-4-Plus 等模型的 prompt 超长问题"
**Design Reference**: [design-discussion.md](design-discussion.md)

## 目录

- [User Scenarios & Testing](#user-scenarios--testing-mandatory)
  - [User Story 1 — 工具返回值压缩](#user-story-1--工具返回值压缩-priority-p1)
  - [User Story 2 — 冗余工具清理与 SOP 完整加载](#user-story-2--冗余工具清理与-sop-完整加载-priority-p1)
  - [User Story 3 — 上下文超限接续与降级](#user-story-3--上下文超限接续与降级-priority-p2)
  - [Edge Cases](#edge-cases)
- [Requirements](#requirements-mandatory)
  - [Functional Requirements](#functional-requirements)
  - [Key Entities](#key-entities)
- [Success Criteria](#success-criteria-mandatory)
- [Assumptions](#assumptions)
- [Clarifications](#clarifications)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 工具返回值压缩 (Priority: P1)

用户发起 Perfetto trace 分析。LLM（SubAgent）根据 SKILL 路由的场景 SOP 自主决定分析路径和工具调用顺序。每个 pa_* 工具调用返回的原始数据经过 ResultCompressor 压缩后再回传给 LLM。LLM 只看到统计摘要 + Top-5 关键条目，原始大数据通过 ToolReturn.metadata 保留给应用层。

**Why this priority**: 实际测量显示初始 prompt 仅 ~5K token（远低于 128K 上限），真正的瓶颈是工具返回值（如丢帧列表、线程统计）在对话历史中的累积。压缩工具返回值是解决 "Prompt exceeds max length" 的根本方案。

**Independent Test**: 使用包含大量丢帧的 trace 执行分析，验证 LLM 收到的工具返回值为压缩摘要（统计 + Top-5），分析正常完成且不报超长错误。

**Acceptance Scenarios**:

1. **Given** LLM 调用 pa_detect_jank 返回 200 条丢帧记录，**When** ToolReturn 处理后，**Then** LLM 收到的 return_value 仅包含 Top-5 严重条目 + 统计摘要（总数、平均耗时、最大耗时），原始数据存入 metadata
2. **Given** LLM 调用 pa_analyze_dimension 返回字典数据，**When** ToolReturn 处理后，**Then** LLM 收到保留 issues 和 top 指标的摘要，去除原始详情
3. **Given** 工具返回错误，**When** ToolReturn 处理后，**Then** 错误信息原样保留（不压缩），方便 LLM 判断是否重试或切换策略
4. **Given** LLM 连续调用 4 个工具，**When** 对话历史累积时，**Then** 总上下文不超出模型限制，因为每次工具返回值已被压缩

---

### User Story 2 — 冗余工具清理与 SOP 完整加载 (Priority: P1)

移除与 pa_analyze_dimension 功能重叠的冗余工具（pa_analyze_full、pa_cpu_overview），减少工具 schema 在 prompt 中的占用。同时，取消 SOP 3000 字符截断限制，通过 SKILL 路由完整加载场景 SOP，让 LLM 获得完整的分析方法论。不再使用默认 SOP 兜底。

**Why this priority**: 移除 3 个冗余工具可节省 ~1000 token 的 schema 空间。完整 SOP 使 LLM 获得更好的分析指导，提升分析质量。

**Independent Test**: 发起 jank 分析，验证 LLM 只能看到 8 个工具（非 11 个），SOP 完整加载且未截断。

**Acceptance Scenarios**:

1. **Given** SubAgent 创建时，**When** 注册工具列表，**Then** 不包含 pa_analyze_full 和 pa_cpu_overview（功能已被 pa_analyze_dimension 覆盖）
2. **Given** MainAgent 路由到 jank 场景，**When** 加载 SOP，**Then** 完整加载 jank-analysis.md 内容（无截断），通过 SKILL 路由而非默认 SOP
3. **Given** MainAgent 路由到未知场景，**When** SKILL 路由无匹配 SOP，**Then** 分析仍可进行（LLM 自主判断），但流式输出通知用户"未找到匹配的分析 SOP"

---

### User Story 3 — 上下文超限接续与降级 (Priority: P2)

当 LLM 调用因上下文超限而失败时，系统不终止整个分析流程。使用已有的工具返回结果继续生成报告，并在报告中标注哪些维度因上下文限制未完成。如果 LLM 完全不可用，自动降级到 fallback engine 分析。

**Why this priority**: 保证分析流程的鲁棒性——即使 LLM 能力受限，用户也能得到有价值的分析结果。

**Independent Test**: 模拟上下文超限异常，验证系统用已有工具结果生成报告、标注缺失维度。

**Acceptance Scenarios**:

1. **Given** LLM 在第 3 次工具调用后因上下文超限失败，**When** 系统处理异常，**Then** 使用前 2 次工具返回的数据生成报告，标注"因上下文限制，后续分析未完成"
2. **Given** LLM 首次调用即因上下文超限失败，**When** 降级触发，**Then** 使用 fallback engine 直接分析并通知用户"模型上下文不足，已降级为引擎分析"
3. **Given** 上下文超限发生，**When** 系统处理时，**Then** 通过流式输出实时通知用户当前状态和降级原因
4. **Given** 降级到 engine 分析，**When** 分析完成，**Then** 报告标注"本次分析由引擎完成，非 LLM 分析"

---

### Edge Cases

- ResultCompressor 压缩后结果仍然较大：增加 token 预算硬限制（默认 ~300 token/工具返回），超限截断
- 工具调用本身超时（非上下文超限）：区分超时和超限异常，超时重试一次
- LLM 返回空结果（工具调用成功但 LLM 无结论）：记录为"分析未产出结论"，仍生成包含工具原始数据的报告
- 冗余工具移除后现有 SOP 中引用了被移除的工具名（如 pa_cpu_overview）：更新所有 SOP 文件，将引用替换为 pa_analyze_dimension(cpu)
- SKILL 路由未匹配到 SOP 文件：LLM 自主分析，不使用 SOP 指导
- 工具返回值为 None 或空 dict：ToolReturn 返回 "工具未返回数据" 字符串

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 所有 pa_* 工具 MUST 返回 `ToolReturn` 对象，`return_value` 为 ResultCompressor 压缩后的统计摘要 + Top-5 关键条目，`metadata` 保留原始数据
- **FR-002**: ResultCompressor MUST 支持 token 预算控制（每次压缩结果不超过 300 token）
- **FR-003**: LLM（SubAgent）MUST 自主决定分析路径和工具调用顺序，系统不预设步骤序列
- **FR-004**: MainAgent 路由场景后，MUST 通过 SKILL 路由加载对应场景的 SOP 文件，完整嵌入 SubAgent instructions（不截断）
- **FR-005**: 不再提供默认 SOP 兜底，未匹配 SOP 时 LLM 自主分析
- **FR-006**: 功能被 pa_analyze_dimension 完全覆盖的冗余工具 MUST 移除（pa_analyze_full, pa_cpu_overview）
- **FR-007**: 保留工具的 docstring MUST 精简为单行描述
- **FR-008**: LLM 调用失败（上下文超限、API 错误）时 MUST 使用已有工具返回数据继续生成报告，不终止分析
- **FR-009**: LLM 完全不可用时 MUST 自动降级到 fallback engine 分析
- **FR-010**: 降级/失败发生时 MUST 通过 on_stream 回调实时通知用户
- **FR-011**: 最终报告 MUST 标注分析是由 LLM 完成还是 engine 降级完成，以及是否有维度因上下文限制未完成
- **FR-012**: 更新所有 SOP 文件中对被移除工具的引用
- **FR-013**: 工具返回值压缩 MUST 直接替换当前方案，不保留旧的无压缩模式（fallback engine 已有兜底）

### Key Entities

- **ToolReturn**: Pydantic AI 原生组件，`return_value` 为压缩摘要给 LLM，`metadata` 为原始数据给应用
- **ResultCompressor**: 已有组件，需扩展支持 token 预算控制和 Top-5 压缩策略
- **SCENE_SOP_MAP**: 场景到 SOP 文件的映射，通过 SKILL 路由确定
- **StepResult**: 单次工具调用结果（工具名、状态、压缩摘要、token 消耗）

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 使用 GLM-4-Plus (128K 上下文) 进行 jank 场景分析时，不再出现 "Prompt exceeds max length" 错误
- **SC-002**: 每次工具返回值经压缩后 token 数 <= 300（统计摘要 + Top-5 关键条目）
- **SC-003**: LLM 连续调用 5 个工具后，累积上下文仍在模型限制内
- **SC-004**: SOP 完整加载（不截断），LLM 分析质量提升（定性评估）
- **SC-005**: 上下文超限时系统不崩溃，降级到 engine 分析并生成有价值的报告
- **SC-006**: 冗余工具移除后（11 → 9 个），工具 schema 占用减少约 20%

## Assumptions

- 中文文本 token 估算使用 ~2 token/字符（保守值）
- 英文文本 token 估算使用 ~0.3 token/字符
- Pydantic AI v1.77+ 已安装且 ToolReturn API 稳定
- ResultCompressor 的 Top-5 + 统计摘要策略对大多数分析场景能提供 LLM 足够的分析信息
- MCP 打通作为独立需求，不在本次范围内
- 初始 prompt（instructions + 工具 schema + 用户 prompt）约 ~5K token，远低于模型上下文限制，不是瓶颈

## Clarifications

### Session 2026-04-05

- Q: 步骤间上下文传递策略？ → A: 滚动窗口 + 全局摘要（最近 2 步完整结果 + 更早步骤合并为一行摘要）
- Q: 分析步骤由谁决定？ → A: LLM 自主决策，系统不预设步骤序列。SubAgent 由 SKILL 赋予能力，调用工具的顺序由具体场景动态决定
- Q: 实际瓶颈在哪里？ → A: 实际测量显示初始 prompt 仅 ~5K token，真正瓶颈是工具返回值在对话历史中的累积
- Q: 工具返回值压缩粒度？ → A: 统计摘要 + Top-5 关键条目（~300 token/次）
- Q: SOP 如何加载？ → A: 不需要默认 SOP，全部通过 SKILL 路由到各场景 SOP（完整加载，不截断）
- Q: 是否保留旧的无压缩模式？ → A: 直接替换，fallback engine 已有兜底

### Previous (v1/v2)

- **C1**: SOP 加载方式 → 通过 SKILL 路由完整加载场景 SOP
- **C2**: 工具结果压缩 → ToolReturn + ResultCompressor（Top-5 + 统计）
- **C3**: 上下文超限处理 → 永不中断 + 渐进降级
- **C4**: MCP 打通 → 不在本次范围，后续独立迭代
- **C5**: LLM 自主决策 → 不限制工具使用顺序，不预设步骤
