# Tasks: 分析经验自动沉淀 (G1)

**Input**: Design documents from `/specs/012-analysis-experience-auto-capture/`  
**Prerequisites**: plan.md, spec.md

## 目录

- [Format](#format)
- [Phase 1 数据模型](#phase-1-数据模型)
- [Phase 2 SubAgent 结构化输出 (US1)](#phase-2-subagent-结构化输出-us1)
- [Phase 3 经验自动提取 (US2)](#phase-3-经验自动提取-us2)
- [Phase 4 HTML 报告重构 (US3)](#phase-4-html-报告重构-us3)
- [Phase 5 Polish](#phase-5-polish)
- [Dependencies](#dependencies--execution-order)

## Format

`[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: User story label (US1-US3)

---

## Phase 1: 数据模型

**Purpose**: Pydantic 模型和数据库表准备

- [x] T001 新增 `RootCauseItem` Pydantic 模型到 `src/agent/__init__.py`，包含 tag、severity、qualitative、evidence、reasoning 必填字段和 quantitative(dict)、suggestion(str) 选填字段
- [x] T002 新增 `AnalysisOutput` Pydantic 模型到 `src/agent/__init__.py`，包含 user_intent_summary、trace_info、scene、overall_conclusion、root_causes(list[RootCauseItem])、detailed_report 字段
- [x] T003 [P] 新增 `pa_learnings` 表 CREATE TABLE 到 `src/engine/storage.py`，含 task_id、trace_id、scene、device_model(nullable)、process_name、root_cause_tags、insight、key_metrics、confidence、hit_count、last_used、created_at、promoted、archived 字段。device_model 来源优先级：trace 文件名解析 > pa_analysis_tasks 表 > 留空
- [x] T004 [P] 新增 `insert_learning` 函数到 `src/engine/storage.py`

**Checkpoint**: Pydantic 模型可 import，pa_learnings 表可创建和写入

---

## Phase 2: SubAgent 结构化输出 (US1)

**Purpose**: SubAgent 输出改为 Pydantic 结构化模型

**Independent Test**: 对任意 trace 运行 SubAgent，验证 result.output 为 AnalysisOutput 实例

- [x] T005 [US1] 修改 `create_sub_agent` 设置 `output_type=AnalysisOutput` + `retries=1`，文件 `src/agent/agents.py`
- [x] T006 [US1] 实现 `_fallback_output` 函数：解析失败时将原始文本包装为 AnalysisOutput（root_causes=[]），文件 `src/agent/orchestrator.py`
- [x] T007 [US1] 修改 `_run_sub_agent` 的输出处理逻辑：try-catch 解析异常后调用 _fallback_output，正常路径从 result.output 获取 AnalysisOutput，返回 dict 中新增 `analysis_output` 字段存放 AnalysisOutput 对象（保留 `conclusion` 向后兼容）。UsageLimitExceeded 路径同样适配 _fallback_output，文件 `src/agent/orchestrator.py`
- [x] T008 [US1] 适配 `_check_conclusion_quality` 和 `_generate_report` 优先从 `result["analysis_output"]` 读取字段，`conclusion` 作为降级回退，文件 `src/agent/orchestrator.py`

**Checkpoint**: SubAgent 输出为 AnalysisOutput 或降级兜底，后续流程正常

---

## Phase 3: 经验自动提取 (US2)

**Purpose**: 分析完成后自动提取经验写入 DB

**Independent Test**: 完成一次有根因的分析后查询 pa_learnings 表验证记录

- [x] T009 [US2] 实现 `_extract_learnings` 函数：从 AnalysisOutput 的 root_causes 提取 root_cause_tags、insight、key_metrics，文件 `src/agent/orchestrator.py`
- [x] T010 [US2] 实现 `_calc_initial_confidence` 函数：基于 severity 权重和 evidence 完整性计算置信度，文件 `src/agent/orchestrator.py`
- [x] T011 [US2] 在 `analyze_single` 的 finalize 阶段集成经验提取：仅当 root_causes 非空时调用 _extract_learnings + insert_learning。device_model 通过 `_resolve_device_model(trace_path, task_id)` 提取（优先文件名解析，回退 pa_analysis_tasks 表），文件 `src/agent/orchestrator.py`
- [x] T012 [US2] 经验写入失败的静默降级：try-except 包裹 INSERT，日志记录但不中断主流程，文件 `src/agent/orchestrator.py`

**Checkpoint**: 有根因的分析自动写入 pa_learnings，无根因的分析不写入

---

## Phase 4: HTML 报告重构 (US3)

**Purpose**: 基于 AnalysisOutput 三区块生成 HTML 报告

**Independent Test**: 生成的 HTML 报告包含问题定义、根因表格和详细分析三个区块

- [x] T013 [US3] 重构 `generate_html_report` 接受 AnalysisOutput 参数，基于三区块结构生成 HTML，文件 `src/agent/report.py`
- [x] T014 [US3] Section 2 根因表格渲染：每个 RootCauseItem 渲染为表格行（tag、severity、qualitative、evidence），文件 `src/agent/report.py`
- [x] T015 [US3] Section 3 占位符替换框架：识别 `{{chart:key_name}}` 占位符并替换为"图表待实现"占位 HTML，文件 `src/agent/report.py`
- [x] T016 [US3] 适配 `_generate_report` 调用方传入 AnalysisOutput 对象，文件 `src/agent/orchestrator.py`

**Checkpoint**: HTML 报告包含三区块结构，占位符有基础替换框架

---

## Phase 5: Polish

**Purpose**: 测试和文档更新

- [x] T017 [P] 编写 G1 单元测试：覆盖 RootCauseItem/AnalysisOutput 模型验证、_extract_learnings、_calc_initial_confidence、_fallback_output、pa_learnings INSERT，文件 `tests/test_g1_experience_capture.py`
- [x] T018 [P] 更新 AGENTS.md 中的 Agent 编排描述，反映 AnalysisOutput 结构化输出和经验提取流程
- [x] T019 更新设计文档 `agent-memory-evolution.md` 标记 G1 为已实现

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (数据模型)**: 无依赖，立即开始
- **Phase 2 (US1)**: 依赖 Phase 1 完成（需要 AnalysisOutput 模型）
- **Phase 3 (US2)**: 依赖 Phase 2 完成（需要 AnalysisOutput 作为输入）
- **Phase 4 (US3)**: 依赖 Phase 2 完成（需要 AnalysisOutput 作为输入），可与 Phase 3 并行
- **Phase 5 (Polish)**: 依赖 Phase 2/3/4 全部完成

### Execution Order

```
Phase 1 → Phase 2 (US1) → Phase 3 (US2) + Phase 4 (US3) → Phase 5
```

### Task Summary

| Phase | Task Count | 说明 |
|-------|-----------|------|
| Phase 1 数据模型 | 4 | Pydantic 模型 + DB 表 |
| Phase 2 US1 | 4 | SubAgent 结构化输出 |
| Phase 3 US2 | 4 | 经验自动提取 |
| Phase 4 US3 | 4 | HTML 报告重构 |
| Phase 5 Polish | 3 | 测试 + 文档 |
| **Total** | **19** | |
