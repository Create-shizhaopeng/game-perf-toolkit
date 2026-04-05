# Tasks: LLM Prompt 预算管理

**Input**: Design documents from `specs/010-prompt-budget-management/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

## 目录

- [Phase 1: Foundational](#phase-1-foundational-blocking-prerequisites)
- [Phase 2: US1 — 工具返回值压缩](#phase-2-user-story-1--工具返回值压缩-priority-p1--mvp)
- [Phase 3: US2 — 冗余工具清理与 SOP 完整加载](#phase-3-user-story-2--冗余工具清理与-sop-完整加载-priority-p1)
- [Phase 4: US3 — 上下文超限接续与降级](#phase-4-user-story-3--上下文超限接续与降级-priority-p2)
- [Phase 5: Polish & 验证](#phase-5-polish--验证)
- [Dependencies & Execution Order](#dependencies--execution-order)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: 扩展 ResultCompressor 以支持工具输出压缩，这是所有 User Story 的前置依赖。

- [ ] T001 扩展 ResultCompressor 增加 `compress_tool_output()` 方法，支持按工具类型和 token 预算压缩 in `modules/perfetto_analysis/src/result_compressor.py`
- [ ] T002 在 `compress_tool_output()` 中实现 pa_detect_jank 压缩策略: Top-5 严重 jank + 统计摘要（总数/平均耗时/最大耗时），结果不超过 300 token in `modules/perfetto_analysis/src/result_compressor.py`
- [ ] T003 在 `compress_tool_output()` 中实现 pa_analyze_dimension 压缩策略: 保留 issues + top 指标，去除原始详情 in `modules/perfetto_analysis/src/result_compressor.py`
- [ ] T004 在 `compress_tool_output()` 中实现通用截断策略: 按 token 预算截断非特殊工具的返回值 in `modules/perfetto_analysis/src/result_compressor.py`

**Checkpoint**: ResultCompressor 扩展完成，可为 tools.py 改造提供压缩能力

---

## Phase 2: User Story 1 — 工具返回值压缩 (Priority: P1) 🎯 MVP

**Goal**: 所有 pa_* 工具返回 ToolReturn，压缩后摘要给 LLM，原始数据通过 metadata 保留。

**Independent Test**: 使用包含大量丢帧的 trace 执行分析，验证 LLM 收到压缩摘要且无 "Prompt exceeds max length" 错误。

### Implementation for User Story 1

- [ ] T005 [US1] 在 `build_analysis_tools()` 中引入 ResultCompressor 实例，作为工具闭包的共享依赖 in `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T006 [US1] 改造 `pa_trace_overview` 返回 ToolReturn（数据量小，return_value 保持原样，metadata 存原始数据） in `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T007 [US1] 改造 `pa_detect_jank` 返回 ToolReturn，return_value 为 compress_tool_output 压缩后的 Top-5 + 统计摘要 in `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T008 [US1] 改造 `pa_analyze_dimension` 返回 ToolReturn，return_value 为压缩后的 issues + top 指标摘要 in `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T009 [P] [US1] 改造 `pa_list_dimensions` 返回 ToolReturn（数据量小，原样保留） in `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T010 [P] [US1] 改造 `pa_get_history` 返回 ToolReturn，return_value 为最近 N 条摘要 in `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T011 [P] [US1] 改造 `pa_find_slices` 返回 ToolReturn，return_value 为通用截断后的摘要 in `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T012 [P] [US1] 改造 `pa_execute_sql` 返回 ToolReturn，return_value 为通用截断后的摘要 in `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T013 [P] [US1] 改造 `pa_analyze_anr` 返回 ToolReturn，return_value 为压缩后的 ANR 分析摘要 in `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T014 [P] [US1] 改造 `pa_analyze_memory` 返回 ToolReturn，return_value 为压缩后的内存分析摘要 in `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T015 [US1] 改造工具错误处理: 所有工具异常时返回 ToolReturn(return_value="错误: {msg}", metadata={"error": str})；工具返回 None/空 dict 时返回 ToolReturn(return_value="工具未返回数据") in `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T016 [US1] 验证 `_notify_tool_result` 回调仍然正常工作（使用 metadata 中的 raw 数据通知） in `modules/perfetto_analysis/src/agent/tools.py`

**Checkpoint**: 所有工具返回 ToolReturn，LLM 收到压缩摘要。可独立验证此 Story。

---

## Phase 3: User Story 2 — 冗余工具清理与 SOP 完整加载 (Priority: P1)

**Goal**: 移除冗余工具，SOP 通过 SKILL 路由完整加载不截断。

**Independent Test**: 发起 jank 分析，验证工具列表不包含 pa_analyze_full/pa_cpu_overview，SOP 完整加载。

### Implementation for User Story 2

- [ ] T017 [US2] 从 `build_analysis_tools()` 返回列表中移除 `pa_analyze_full` 和 `pa_cpu_overview` 函数定义 in `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T017a [P] [US2] 精简保留工具的 docstring 为单行描述（FR-007），确保 Pydantic AI 生成的 schema 紧凑 in `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T018 [US2] 移除 `prompts.py` 中的 `_DEFAULT_SOP` 变量和 3000 字符截断逻辑 in `modules/perfetto_analysis/src/agent/prompts.py`
- [ ] T019 [US2] 修改 `load_sop()`: SOP 文件不存在时返回空字符串并记录 warning（不使用默认兜底） in `modules/perfetto_analysis/src/agent/prompts.py`
- [ ] T020 [US2] 更新 `jank-analysis.md` 中 `pa_cpu_overview` 引用为 `pa_analyze_dimension(cpu)` in `modules/perfetto_analysis/skills/perfetto-analysis/sop/jank-analysis.md`
- [ ] T021 [US2] 检查并更新其他 SOP 文件中对 `pa_analyze_full` 和 `pa_cpu_overview` 的引用 in `modules/perfetto_analysis/skills/perfetto-analysis/sop/*.md`

**Checkpoint**: 冗余工具已移除，SOP 完整加载。可独立验证此 Story。

---

## Phase 4: User Story 3 — 上下文超限接续与降级 (Priority: P2)

**Goal**: LLM 调用失败时不终止分析，渐进降级到 engine 分析。

**Independent Test**: 模拟上下文超限异常，验证降级到 engine 并生成包含降级标注的报告。

### Implementation for User Story 3

- [ ] T022 [US3] 在 `_run_sub_agent()` 中增加 context overflow 异常识别逻辑（匹配 litellm.BadRequestError + "max length" / "context" 关键字） in `modules/perfetto_analysis/src/agent/orchestrator.py`
- [ ] T023 [US3] 实现渐进降级: context overflow 时通过 on_stream 通知用户，降级到 `_fallback_engine_analysis()` in `modules/perfetto_analysis/src/agent/orchestrator.py`
- [ ] T024 [US3] 在 `_generate_report()` 和 `report.py` 中增加分析完成度标注（LLM 完成 / 部分完成 / engine 降级） in `modules/perfetto_analysis/src/agent/orchestrator.py` and `modules/perfetto_analysis/src/agent/report.py`

**Checkpoint**: 上下文超限时系统不崩溃，降级到 engine 并生成标注报告。

---

## Phase 5: Polish & 验证

**Purpose**: 测试、文档更新、端到端验证

- [ ] T025 [P] 编写 ResultCompressor.compress_tool_output() 单元测试: 200 条 jank → Top-5 + 统计; 字典 → issues + top; 错误 → 原样; 空 → 提示 in `modules/perfetto_analysis/tests/test_result_compressor.py`
- [ ] T026 [P] 编写 ToolReturn 集成测试: 验证各工具返回 ToolReturn 格式正确、return_value 不超过 300 token in `modules/perfetto_analysis/tests/test_tool_return.py`
- [ ] T027 [P] 编写降级测试: 模拟 litellm.BadRequestError → 验证 fallback engine 触发 in `modules/perfetto_analysis/tests/test_orchestrator_degradation.py`
- [ ] T028 端到端验证: 启动应用，发起 jank 分析，确认无 "Prompt exceeds max length" 错误
- [ ] T029 更新 `doc/experience/development-pitfalls.md` 补充 P34 解决方案（ToolReturn 压缩工具返回值）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Foundational)**: 无依赖 — 可立即开始
- **Phase 2 (US1)**: 依赖 Phase 1 完成 — T001-T004 MUST 先完成
- **Phase 3 (US2)**: 依赖 Phase 2 完成（tools.py 改造完成后再移除冗余工具）
- **Phase 4 (US3)**: 可与 Phase 3 并行（改造 orchestrator.py 不依赖 tools.py 变更）
- **Phase 5 (Polish)**: 依赖 Phase 2-4 完成

### User Story Dependencies

- **US1 (工具返回值压缩)**: 核心 MVP — 依赖 Foundational
- **US2 (冗余清理 + SOP)**: 依赖 US1（tools.py 改造完成后再删除工具）
- **US3 (超限降级)**: 独立于 US1/US2（改造 orchestrator.py 降级逻辑）

### Within Each User Story

- T005 (引入 ResultCompressor) → T006-T016 (逐个工具改造)
- T009-T014 标记 [P]：改造不同工具函数，互不依赖

### Parallel Opportunities

- Phase 1: T002-T004 可并行（不同压缩策略，同文件不同方法）
- Phase 2: T009-T014 可并行（不同工具函数改造）
- Phase 4 与 Phase 3 可并行
- Phase 5: T025-T027 可并行（不同测试文件）

---

## Parallel Example: User Story 1

```bash
# 先完成基础任务:
T005: 引入 ResultCompressor 实例

# 然后并行改造各工具:
T009: pa_list_dimensions  (小数据，原样保留)
T010: pa_get_history       (摘要保留)
T011: pa_find_slices       (通用截断)
T012: pa_execute_sql       (通用截断)
T013: pa_analyze_anr       (ANR 摘要)
T014: pa_analyze_memory    (内存摘要)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: ResultCompressor 扩展
2. Complete Phase 2: 工具返回 ToolReturn
3. **STOP and VALIDATE**: 端到端测试 jank 分析，确认无超长错误
4. 如 MVP 通过 → 继续 US2 + US3

### Incremental Delivery

1. Phase 1 → ResultCompressor 扩展完成
2. Phase 2 → 工具返回值压缩生效 → 验证 MVP
3. Phase 3 → 冗余清理 + SOP 完整加载 → 验证分析质量
4. Phase 4 → 超限降级 → 验证鲁棒性
5. Phase 5 → 测试 + 文档
