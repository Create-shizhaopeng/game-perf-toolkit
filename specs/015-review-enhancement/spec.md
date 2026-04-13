# Feature Specification: Review 增强 (G4)

**Feature Branch**: `015-review-enhancement`
**Created**: 2026-04-13
**Status**: Draft
**Input**: G4 Review 增强 — 基于 AnalysisOutput 结构化数据改造 ReviewAgent 评审流程，场景感知触发，置信度校准闭环

## 目录

- [User Scenarios & Testing](#user-scenarios--testing)
  - [User Story 1 - 结构化 Review 输入](#user-story-1---结构化-review-输入-priority-p1)
  - [User Story 2 - 场景感知触发](#user-story-2---场景感知触发-priority-p2)
  - [User Story 3 - 置信度校准闭环](#user-story-3---置信度校准闭环-priority-p3)
  - [Edge Cases](#edge-cases)
- [Requirements](#requirements)
  - [Functional Requirements](#functional-requirements)
  - [Key Entities](#key-entities)
- [Success Criteria](#success-criteria)
- [Assumptions](#assumptions)
- [Constraints](#constraints)
- [Clarifications](#clarifications)

## User Scenarios & Testing

### User Story 1 - 结构化 Review 输入 (Priority: P1)

ReviewAgent 从原来的 `summary[:200]` 文本输入改为基于 `AnalysisOutput` 的完整结构化输入，Review 评审输出为 `ReviewResult` 结构化模型，包含交叉一致性评价、共性问题、矛盾点和整体评审意见。

**Why this priority**: ReviewAgent 需要完整结构化数据才能做出有意义的评审。

**Independent Test**: 提供一组 `AnalysisOutput` → ReviewAgent → 确认输出为结构化 `ReviewResult`。

**Acceptance Scenarios**:

1. **Given** 一个包含根因列表的 `AnalysisOutput`，**When** ReviewAgent 执行评审，**Then** 返回包含 `overall_assessment` 和 `confidence_adjustments` 字段的 `ReviewResult`。
2. **Given** `AnalysisOutput` 中根因缺少证据字段，**When** ReviewAgent 评审，**Then** `ReviewResult.contradictions` 中指出证据不足。

---

### User Story 2 - 场景感知触发 (Priority: P2)

Review 触发逻辑改为场景感知：批量分析仅同场景 trace 触发交叉对比 Review；不同场景的 trace 仅在低置信度时触发单独自检，避免无意义的跨场景对比。

**Why this priority**: 防止不同场景交叉对比引入上下文污染，降低分析准确度。

**Independent Test**: 传入不同场景的 `AnalysisOutput` 列表 → 确认不触发 `cross_compare`，仅低置信度的触发 `individual_review`。

**Acceptance Scenarios**:

1. **Given** 批量分析产生 3 个同场景的 `AnalysisOutput`，**When** 判断 Review 触发，**Then** 返回 `(True, "cross_compare")`。
2. **Given** 批量分析产生 3 个不同场景的 `AnalysisOutput`，**When** 判断 Review 触发，**Then** 不触发 `cross_compare`，仅对低置信度的单独触发 `individual_review`。
3. **Given** 单个 `AnalysisOutput` 有 ≥ 3 个根因，**When** 判断 Review 触发，**Then** 返回 `(True, "self_check")`。
4. **Given** 单个 `AnalysisOutput` 高置信度且根因 < 3，**When** 判断 Review 触发，**Then** 返回 `(False, "")`。

---

### User Story 3 - 置信度校准闭环 (Priority: P3)

ReviewAgent 评审结果中的 `confidence_adjustments` 写回 `pa_learnings.confidence`，形成 G1(经验写入) → G4(Review 校准) → G3(淘汰/晋升) 的反馈闭环。

**Why this priority**: 置信度校准提升整个经验生命周期的质量。

**Independent Test**: Review 返回置信度调整 → 确认 `pa_learnings.confidence` 被更新。

**Acceptance Scenarios**:

1. **Given** ReviewAgent 返回 `confidence_adjustments: [{trace_index: 0, tag: "cpu_binderclock", adjustment: +0.1}]`，**When** 系统执行校准，**Then** 匹配 task_id + root_cause_tags 包含该 tag 的 pa_learnings 记录，confidence 增加 0.1（上限 1.0）。
2. **Given** ReviewAgent 返回负调整 `-0.2`，**When** 系统执行，**Then** 对应 learning 的 `confidence` 降低但不低于 0.0。

---

### Edge Cases

- `AnalysisOutput` 的 `root_causes` 为空时，Review 跳过根因评审部分
- LLM 调用失败时，Review 安全跳过，不影响分析结果输出
- `confidence_adjustments` 引用的 `trace_index` 越界时忽略该调整
- 批量分析中仅有 1 个 trace 时等同于单 trace 逻辑
- `ReviewResult` 解析失败时降级为原文本输出

## Requirements

### Functional Requirements

- **FR-001**: ReviewAgent 的输入 MUST 基于 `AnalysisOutput` 的结构化字段（`overall_conclusion`、`root_causes`、`scene`），而非截断文本
- **FR-002**: ReviewAgent 的输出 MUST 使用 `ReviewResult` Pydantic 模型，包含 `cross_consistency`、`common_patterns`、`contradictions`、`confidence_adjustments`、`overall_assessment` 字段
- **FR-003**: 系统 MUST 实现 `_should_review(outputs) -> (bool, str)` 函数，根据场景一致性和置信度判断 Review 触发类型
- **FR-004**: 批量分析中所有 trace 同场景时 MUST 触发 `cross_compare` 类型 Review
- **FR-005**: 批量分析中 trace 跨场景时 MUST NOT 触发 `cross_compare`，仅对平均置信度 < 0.5 的 `AnalysisOutput` 触发 `individual_review`
- **FR-006**: 单 trace 分析中，根因 ≥ 3 或平均置信度 < 0.5 时 MUST 触发 `self_check`
- **FR-007**: ReviewAgent 评审后 MUST 将 `confidence_adjustments` 按 `tag`(root_cause_tag) 精确匹配写回 `pa_learnings.confidence`，值域 [0.0, 1.0]
- **FR-008**: Review 过程中 LLM 调用失败时 MUST 安全降级，不影响分析结果的正常输出
- **FR-009**: `create_review_agent` MUST 使用 `output_type=ReviewResult` 实现结构化输出

## Key Entities

- **ReviewResult**: Pydantic 模型，ReviewAgent 的结构化评审输出
- **_should_review**: 场景感知的 Review 触发判断函数
- **confidence_adjustments**: 置信度调整列表，每项含 `trace_index`、`tag`(root_cause_tag)、`adjustment`、`reason`；按 root_cause_tag 精确匹配 pa_learnings 记录

## Success Criteria

### Measurable Outcomes

- **SC-001**: ReviewAgent 输出的 `ReviewResult` 中 90% 以上的评审意见可被人工验证为有效
- **SC-002**: 批量同场景 Review 能识别出 trace 间的共性问题和矛盾
- **SC-003**: 置信度校准后的经验在后续 G2/G3 流程中表现更合理（高质量分析的置信度趋高，低质量的趋低）

## Assumptions

- G1 的 `AnalysisOutput` 和 `RootCauseItem` 模型已稳定
- G1 的 `pa_learnings` 表已包含 `confidence` 字段
- 现有 `create_review_agent` 可修改为接受 `output_type` 参数
- LLM 模型可通过现有 `LLMManager` 获取

## Constraints

- Review 流程 MUST NOT 阻塞分析结果的返回
- Review LLM 调用失败 MUST NOT 导致整体分析失败
- 置信度调整值 MUST 限制在 [-0.3, +0.3] 范围内，防止单次 Review 过度影响
- 跨场景 trace MUST NOT 进行交叉对比

## Clarifications

1. **Q1: confidence_adjustments 映射方式** — 选择 B: 按 root_cause_tag 精确调整。`confidence_adjustments` 每项增加 `tag` 字段（对应 `pa_learnings.root_cause_tags`），系统按 task_id + tag 精确匹配到具体的 learning 记录进行校准，避免批量"连坐"误调。
2. **Q2: Review 在批量分析中的执行时机** — 选择 A: 全部分析完成后统一 Review。与 `cross_compare` 模式一致，Review 需要看到所有同场景 trace 的分析结果后才能做交叉对比。G1 写入 learning 的初始 confidence 由 LLM 给出，Review 校准后调整即可。
3. **Q3: cross_consistency 字段在非 cross_compare 模式下的行为** — `self_check` 和 `individual_review` 模式下 `cross_consistency` 保持默认空字符串（模型 `default=""` 已覆盖），Review 指令中不提及交叉对比相关字段。
