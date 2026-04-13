# Task Breakdown: Review 增强 (G4)

**Branch**: `015-review-enhancement` | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

## 目录

- [Phase 1: Setup](#phase-1-setup)
- [Phase 2: Foundational �?模型定义](#phase-2-foundational--模型定义)
- [Phase 3: US1 �?结构�?Review 输入/输出](#phase-3-us1--结构�?review-输入输出)
- [Phase 4: US2 �?场景感知触发](#phase-4-us2--场景感知触发)
- [Phase 5: US3 �?置信度校准闭环](#phase-5-us3--置信度校准闭�?
- [Phase 6: Polish](#phase-6-polish)
- [Dependencies](#dependencies)

## Phase 1: Setup

- [x] T001 创建 G4 测试文件 `modules/perfetto_analysis/tests/test_g4_review_enhancement.py`，包含基础 fixtures �?import

## Phase 2: Foundational �?模型定义

- [x] T002 [P] �?`modules/perfetto_analysis/src/agent/__init__.py` 新增 `ConfidenceAdjustment` Pydantic 模型：`trace_index: int`, `tag: str`, `adjustment: float`, `reason: str`
- [x] T003 [P] �?`modules/perfetto_analysis/src/agent/__init__.py` 新增 `ReviewResult` Pydantic 模型：`cross_consistency: str`, `common_patterns: list[str]`, `contradictions: list[str]`, `confidence_adjustments: list[ConfidenceAdjustment]`, `overall_assessment: str`
- [x] T004 �?`modules/perfetto_analysis/src/agent/__init__.py` �?`AnalysisReport` 模型中新�?`analysis_output: AnalysisOutput | None = None` 字段

## Phase 3: US1 �?结构�?Review 输入/输出

**Goal**: ReviewAgent 从截断文本改为基�?AnalysisOutput 的完整结构化输入，输出为 ReviewResult�?

**Independent Test**: 提供一�?AnalysisOutput �?ReviewAgent �?确认输出�?ReviewResult�?

- [x] T005 [US1] 修改 `modules/perfetto_analysis/src/agent/agents.py` �?`create_review_agent`：增�?`review_type` 参数，使�?`output_type=ReviewResult`，按 review_type 选择不同 instructions
- [x] T006 [US1] 修改 `modules/perfetto_analysis/src/agent/orchestrator.py` �?`_run_review` 方法：输入改为从 `AnalysisReport.analysis_output` 组装结构�?prompt，返�?`ReviewResult | None`，失败时安全降级
- [x] T007 [US1] 修改 `modules/perfetto_analysis/src/agent/orchestrator.py` �?`_generate_report` 方法：将 `analysis_output` 赋值到 `AnalysisReport.analysis_output` 字段，确保数据透传�?Review 阶段

## Phase 4: US2 �?场景感知触发

**Goal**: Review 触发改为场景感知，同场景 cross_compare、跨场景仅低置信�?individual_review、单 trace self_check�?

**Independent Test**: 传入不同场景组合�?AnalysisOutput 列表 �?确认触发类型正确�?

- [x] T008 [US2] �?`modules/perfetto_analysis/src/agent/orchestrator.py` 新增 `_should_review(reports) -> (bool, str)` 静态方法，实现三种触发模式判断逻辑
- [x] T009 [US2] 修改 `modules/perfetto_analysis/src/agent/orchestrator.py` �?`analyze_batch` 方法（约 L217-220）：�?`_should_review` 替代原有 `len(reports) > 1` 硬编码判断，�?review_type 传给 `_run_review`

## Phase 5: US3 �?置信度校准闭�?

**Goal**: ReviewResult 中的 confidence_adjustments �?root_cause_tag 精确匹配写回 pa_learnings.confidence�?

**Independent Test**: Review 返回�?tag 的置信度调整 �?确认 pa_learnings.confidence �?tag 精确更新�?

- [x] T010 [US3] �?`modules/perfetto_analysis/src/agent/orchestrator.py` 新增 `_apply_confidence_calibration(reports, review_result)` 方法，按 task_id + `instr(root_cause_tags, tag)` 精确匹配 pa_learnings 记录并更�?confidence（值域 [0.0, 1.0]，单次调�?[-0.3, +0.3]�?
- [x] T011 [US3] �?`_run_review` 方法中调�?`_apply_confidence_calibration`，Review 成功返回 ReviewResult 后执行校�?

## Phase 6: Polish

- [x] T012 编写 G4 单元测试 `modules/perfetto_analysis/tests/test_g4_review_enhancement.py`：覆�?ReviewResult/ConfidenceAdjustment 模型验证、_should_review 各触发模式、_apply_confidence_calibration 精确匹配逻辑、_run_review 降级场景
- [x] T013 运行 G4 单元测试并确保全部通过
- [x] T014 运行全量回归测试 `python scripts/run_all_tests.py`，确保零回归
- [x] T015 更新 `modules/perfetto_analysis/AGENTS.md`，增�?G4 Review 增强特性描�?
- [x] T016 更新 `modules/perfetto_analysis/docs/agent-memory-evolution.md`，标�?G4 为已实现

## Dependencies

```text
Phase 1 (Setup)
  └─�?Phase 2 (Models: T002-T004)
        └─�?Phase 3 (US1: T005-T007) ─�?Phase 4 (US2: T008-T009)
                                          └─�?Phase 5 (US3: T010-T011)
                                                └─�?Phase 6 (Polish: T012-T016)
```

**Parallel Opportunities**:
- T002 �?T003（独立模型定义）
- T015 �?T016（独立文档更新）

**MVP Scope**: Phase 1-3 (结构�?Review 输入/输出) �?最核心的改进，后续 Phase 可独立增量交付�?
