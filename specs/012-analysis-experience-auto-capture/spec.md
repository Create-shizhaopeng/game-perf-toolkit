# Feature Specification: 分析经验自动沉淀 (G1)

**Feature Branch**: `012-analysis-experience-auto-capture`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "G1 分析经验自动沉淀：SubAgent 输出结构化后自动提取经验写入 pa_learnings 表"

## User Scenarios & Testing

### User Story 1 - SubAgent 结构化输出 (Priority: P1)

SubAgent 完成 trace 分析后，输出 Pydantic 结构化模型（`AnalysisOutput`），包含问题定义、根因列表和详细报告，取代当前的自由文本结论。

**Why this priority**: 结构化输出是经验提取（US2）和 HTML 报告生成（US3）的前置依赖，没有结构化数据就无法自动提取经验。

**Independent Test**: 对任意 trace 运行 SubAgent 分析，验证 `result.output` 为 `AnalysisOutput` 实例，且包含 `scene`、`root_causes`、`overall_conclusion` 字段。

**Acceptance Scenarios**:

1. **Given** SubAgent 完成分析, **When** 获取输出, **Then** 输出为 `AnalysisOutput` 类型，含 `user_intent_summary`、`trace_info`、`scene`、`overall_conclusion`、`root_causes` 和 `detailed_report` 字段
2. **Given** SubAgent 分析遇到解析失败, **When** Pydantic 无法将 LLM 输出转为 `AnalysisOutput`, **Then** 系统使用降级兜底 `_fallback_output` 生成含原始文本的 `AnalysisOutput`
3. **Given** SubAgent 发现多个根因, **When** 输出 `root_causes`, **Then** 每个 `RootCauseItem` 包含 `tag`、`severity`、`qualitative`、`evidence`、`reasoning` 字段

---

### User Story 2 - 经验自动提取 (Priority: P1)

分析完成后，编排器自动从 `AnalysisOutput` 的结构化字段中提取高价值经验（根因标签、结论、定量数据），写入 `pa_learnings` 数据库表，无需额外 LLM 调用。

**Why this priority**: 这是 G1 的核心价值——将一次性分析结论沉淀为可复用的长期记忆。

**Independent Test**: 完成一次带根因的分析后，查询 `pa_learnings` 表验证有对应记录，且 `root_cause_tags`、`insight`、`key_metrics` 非空。

**Acceptance Scenarios**:

1. **Given** SubAgent 输出含 ≥1 个 `RootCauseItem`, **When** 分析流程完成, **Then** `pa_learnings` 表新增一条记录，`root_cause_tags` 包含各根因的 `tag`
2. **Given** SubAgent 输出无 `root_causes`（空列表）, **When** 分析流程完成, **Then** 不写入 `pa_learnings`（避免低价值数据）
3. **Given** 同一 trace 被分析两次, **When** 两次分析均有根因, **Then** `pa_learnings` 表有两条独立记录（不去重，保留分析演化历史）

---

### User Story 3 - 结构化 HTML 报告 (Priority: P2)

基于 `AnalysisOutput` 的三区块结构生成 HTML 报告：Section 1（问题定义）、Section 2（分析摘要与根因表格）、Section 3（详细分析报告）。

**Why this priority**: HTML 报告是用户直接感知的分析产出，但其实现可在 US1/US2 之后独立迭代。

**Independent Test**: 完成分析后打开生成的 HTML 报告，验证包含问题定义、根因表格和详细分析三个区块。

**Acceptance Scenarios**:

1. **Given** `AnalysisOutput` 含完整数据, **When** 生成 HTML 报告, **Then** 报告包含 Section 1（用户问题 + trace 信息）、Section 2（结论 + 根因表格）、Section 3（详细报告）
2. **Given** `AnalysisOutput` 为降级兜底输出, **When** 生成 HTML 报告, **Then** Section 1 显示"结构化解析失败"提示，Section 3 包含完整原始文本

---

### Edge Cases

- SubAgent 输出的 `AnalysisOutput` 中 `quantitative` 字段缺失或为空 dict，经验提取应正常处理（`key_metrics` 为空 JSON）
- SubAgent 因 `request_limit` 截断提前结束，`root_causes` 可能不完整，经验提取应基于已有数据正常工作
- `pa_learnings` 表 INSERT 失败（DB 锁定等）不应导致整体分析流程失败，应静默降级
- `confidence` 计算中，所有 `RootCauseItem.severity` 都为未知值时，应使用默认置信度 0.3

## Requirements

### Functional Requirements

- **FR-001**: 系统 MUST 定义 `RootCauseItem` Pydantic 模型，包含 `tag`、`severity`、`qualitative`、`evidence`、`reasoning` 必填字段和 `quantitative`（Optional dict）、`suggestion`（Optional str）选填字段
- **FR-002**: 系统 MUST 定义 `AnalysisOutput` Pydantic 模型，作为 SubAgent 的 `output_type`，包含 Section 1/2/3 对应字段
- **FR-003**: SubAgent Agent 创建时 MUST 设置 `output_type=AnalysisOutput` + `retries=1`，使 Pydantic AI 强制 LLM 输出结构化数据并自动重试一次解析失败
- **FR-004**: 系统 MUST 实现 `_fallback_output` 函数，在 Pydantic AI 重试后仍解析失败时，catch 异常将原始文本降级为 `AnalysisOutput`
- **FR-005**: 系统 MUST 在 `pa_learnings` 表不存在时自动创建（`CREATE TABLE IF NOT EXISTS`）
- **FR-006**: 编排器 MUST 在分析完成（`_finalize`）阶段调用 `_extract_learnings` 从 `AnalysisOutput` 提取经验
- **FR-007**: `_extract_learnings` MUST 无需额外 LLM 调用，直接从结构化字段读取
- **FR-008**: `_extract_learnings` MUST 仅在 `root_causes` 非空时写入 `pa_learnings`
- **FR-009**: 系统 MUST 实现 `_calc_initial_confidence` 基于根因严重度和证据完整性计算初始置信度
- **FR-010**: `pa_learnings` 写入失败 MUST NOT 导致分析流程中断，MUST 静默降级并记录日志
- **FR-011**: HTML 报告生成 MUST 基于 `AnalysisOutput` 的结构化字段，`detailed_report` 中的占位符标记（如 `{{chart:cpu_freq}}`）MUST 在报告生成时替换为实际图表
- **FR-012**: 编排器中现有的自由文本结论处理逻辑 MUST 适配为从 `AnalysisOutput` 读取

### Key Entities

- **RootCauseItem**: 单个根因分析，包含标签（tag）、严重度（severity）、定性描述、定量数据、证据和推理链
- **AnalysisOutput**: SubAgent 结构化输出，分三个区块：问题定义、分析摘要（含根因列表）、详细报告
- **pa_learnings**: 经验存储表，关联分析任务，记录场景、根因标签、洞察、定量指标、置信度、引用计数

## Clarifications

### Session 2026-04-09

- Q: SubAgent output_type=AnalysisOutput 设置后，LLM 无法输出符合 schema 的 JSON 时的处理策略？ → A: A+C 组合方案——设 output_type=AnalysisOutput + retries=1，pydantic-ai 自动重试一次解析失败；如果重试后仍失败，catch 异常后调用 _fallback_output 降级为自由文本包装
- Q: AnalysisOutput.detailed_report 是否需要支持可视化标记？ → A: 支持占位符标记（如 `{{chart:cpu_freq}}`），文字描述+占位符，报告生成时替换为实际图表

## Success Criteria

### Measurable Outcomes

- **SC-001**: 每次分析完成后，如果发现根因，`pa_learnings` 表在 1 秒内新增对应记录
- **SC-002**: 经验提取过程零额外 LLM token 消耗（直接从结构化字段读取）
- **SC-003**: `AnalysisOutput` Pydantic 解析失败率 ≤ 20%（降级兜底正常工作）
- **SC-004**: HTML 报告包含完整的三区块结构，信息无遗漏
- **SC-005**: `pa_learnings` 写入异常不影响分析主流程成功率
