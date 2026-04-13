# Tasks: SubAgent 推理链重构

**Input**: Design documents from `/specs/011-subagent-reasoning-chain/`  
**Prerequisites**: plan.md, spec.md

## 目录

- [Format](#format)
- [Phase 1 Setup](#phase-1-setup)
- [Phase 2 Foundational](#phase-2-foundational-blocking-prerequisites)
- [Phase 3 US1 场景感知预取](#phase-3-user-story-1---场景感知预取-priority-p1--mvp)
- [Phase 4 US2 结构化压缩](#phase-4-user-story-2---结构化压缩-priority-p1)
- [Phase 5 US3 推理链引导](#phase-5-user-story-3---推理链引导-priority-p1)
- [Phase 6 US4 插桩观测](#phase-6-user-story-4---插桩观测-priority-p2)
- [Phase 7 US5 安全网](#phase-7-user-story-5---安全网-priority-p2)
- [Phase 8 Polish](#phase-8-polish--cross-cutting-concerns)
- [Dependencies](#dependencies--execution-order)

## Format

`[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: User story label (US1-US5)

---

## Phase 1: Setup

**Purpose**: 数据模型和基础设施准备

- [ ] T001 新增 `CompressionProfile`、`SceneMeta`、`PrefetchSpec` Pydantic 模型到 `modules/perfetto_analysis/src/agent/__init__.py`
- [ ] T002 [P] 新增 `pa_telemetry` 表 CREATE TABLE 到 `modules/perfetto_analysis/src/engine/storage.py`
- [ ] T003 [P] 为 `skills/perfetto-analysis/sop/jank-analysis.md` 添加 YAML frontmatter 作为参考实现，必须包含: `scene`, `display_name`, `priority_dims`, `secondary_dims`, `optional_dims`, `prefetch[]`（tool + inject_as）

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 所有 User Story 共享的前置基础

**⚠️ CRITICAL**: 所有 User Story 均依赖此阶段完成

- [ ] T004 修复 `pa_detect_jank` 中 AnalysisResult 被 str() 序列化的 bug，改为提取 `parse_result` dict 返回结构化数据，文件 `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T005 [P] 修复 `pa_analyze_dimension` 中 `compact=True` 误传到 `on_progress` 回调参数的 bug，文件 `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T006 [P] 在 `prompts.py` 中实现 SOP frontmatter 解析，加载场景元数据（scene, priority_dims, prefetch），文件 `modules/perfetto_analysis/src/agent/prompts.py`
- [ ] T007 在 `PerfettoAnalysisService` 中添加 `_analysis_cache` dict 和缓存读写方法，文件 `modules/perfetto_analysis/src/service.py`

**Checkpoint**: Bug 已修复，SOP 元数据可加载，缓存基础设施就绪

---

## Phase 3: User Story 1 - 场景感知预取 (Priority: P1) 🎯 MVP

**Goal**: 编排器在 SubAgent 运行前根据场景自动预取关键数据

**Independent Test**: 提交一个卡顿 trace，验证编排器自动识别 jank 场景并预取 detect_jank 数据

### Implementation for User Story 1

- [ ] T008 [US1] 在编排器中实现 Phase 1 预取流程：根据 `SceneMeta.prefetch` 配置调用工具并写入缓存，文件 `modules/perfetto_analysis/src/agent/orchestrator.py`
- [ ] T009 [US1] 实现预取结果注入 SubAgent prompt 的"已知信息"区块，文件 `modules/perfetto_analysis/src/agent/orchestrator.py`
- [ ] T010 [US1] 实现缓存命中逻辑：工具执行前先查 `_analysis_cache`，命中则直接返回，文件 `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T011 [US1] 处理自动抓取场景：Phase 0 从 `pa_analysis_tasks` 表读取预填字段（`jank_count`、`process_name`、`dimensions`）注入 MainAgent 输入，文件 `modules/perfetto_analysis/src/agent/orchestrator.py`
- [ ] T012 [US1] 处理 MCP 不可用降级：预取工具调用失败时回退到引擎路径，文件 `modules/perfetto_analysis/src/agent/orchestrator.py`

**Checkpoint**: 编排器能自动预取数据并注入 SubAgent prompt，缓存避免重复查询

---

## Phase 4: User Story 2 - 结构化压缩 (Priority: P1)

**Goal**: 工具返回值按注册的压缩策略处理，异常数据完整保留

**Independent Test**: 对含 CPU 限频的 trace 分析，验证 degraded 维度数据完整保留在压缩结果中

### Implementation for User Story 2

- [ ] T013 [US2] 定义 `COMPRESSION_PROFILES` 注册表，为每个 pa_* 工具注册压缩策略，文件 `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T014 [US2] 实现 `degraded_aware` 压缩策略：`degraded=True` 的维度保留完整数据，`degraded=False` 精简为摘要，文件 `modules/perfetto_analysis/src/result_compressor.py`
- [ ] T015 [US2] 实现 `jank_records` 压缩策略：保留 jank_records 完整，精简 vsync_cycles 等大数据，文件 `modules/perfetto_analysis/src/result_compressor.py`
- [ ] T016 [US2] 将工具返回的 `_make_tool_return` 函数改为查找 `COMPRESSION_PROFILES` 并应用对应策略，文件 `modules/perfetto_analysis/src/agent/tools.py`
- [ ] T017 [US2] 工具查询结果写入 `_analysis_cache` 和 DB，文件 `modules/perfetto_analysis/src/agent/tools.py`

**Checkpoint**: 工具返回值按策略压缩，degraded 维度数据 100% 保留

---

## Phase 5: User Story 3 - 推理链引导 (Priority: P1)

**Goal**: SubAgent 按 Phase A/B/C 推理链执行结构化分析

**Independent Test**: 对任意 trace 分析，观察 SubAgent 工具调用序列呈现"先排查→后验证→最后输出"层次

### Implementation for User Story 3

- [ ] T018 [US3] 在 `agents.py` 中重构 SubAgent 的 instructions 组装逻辑：注入推理链模板（Phase A/B/C）+ 场景优先级维度，文件 `modules/perfetto_analysis/src/agent/agents.py`
- [ ] T019 [US3] 实现推理链 prompt 模板（5 部分：角色定义 + 已知信息占位 + 场景SOP规则占位 + 维度优先级占位 + 行为约束），文件 `modules/perfetto_analysis/src/agent/prompts.py`
- [ ] T020 [US3] 实现 MainAgent 动态路由：分析用户意图后匹配 SOP 场景，文件 `modules/perfetto_analysis/src/agent/agents.py`

**Checkpoint**: SubAgent 按推理链结构执行分析，维度调用顺序符合场景优先级

---

## Phase 6: User Story 4 - 插桩观测 (Priority: P2)

**Goal**: 每次分析自动记录遥测数据到 DB

**Independent Test**: 运行一次分析后查询 `pa_telemetry` 表验证数据完整

### Implementation for User Story 4

- [ ] T021 [US4] 在编排器 `_finalize` 阶段实现遥测数据采集（工具调用次数/明细、token 消耗、耗时），文件 `modules/perfetto_analysis/src/agent/orchestrator.py`
- [ ] T022 [US4] 实现遥测数据写入 `pa_telemetry` 表，文件 `modules/perfetto_analysis/src/agent/orchestrator.py`
- [ ] T023 [US4] 从 pydantic-ai Agent 运行结果中提取 token usage 数据，文件 `modules/perfetto_analysis/src/agent/orchestrator.py`

**Checkpoint**: 分析完成后 pa_telemetry 表有对应记录

---

## Phase 7: User Story 5 - 安全网 (Priority: P2)

**Goal**: SubAgent request_limit 设为 50，防止 LLM 失控调用

**Independent Test**: 设置低 request_limit 验证达到上限后正常终止

### Implementation for User Story 5

- [ ] T024 [US5] 在 SubAgent 创建时设置 `request_limit=50`，文件 `modules/perfetto_analysis/src/agent/agents.py`
- [ ] T025 [US5] 在推理链 prompt 中加入收敛引导（不写具体调用次数），文件 `modules/perfetto_analysis/src/agent/prompts.py`

**Checkpoint**: SubAgent 50 次请求后自动终止，已有结果可用

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 跨 Story 的改进和文档更新

- [ ] T026 [P] 为所有 SOP 文件补充 YAML frontmatter（scene, priority_dims, prefetch），文件 `skills/perfetto-analysis/sop/*.md`
- [ ] T027 [P] 更新 AGENTS.md 中的工具集描述（压缩策略变更、新增缓存机制），文件 `modules/perfetto_analysis/AGENTS.md`
- [ ] T028 更新设计文档反映实际实现（压缩策略从 issues/severity 改为 degraded_aware），文件 `modules/perfetto_analysis/docs/agent-memory-evolution.md`
- [ ] T029 [P] 验证端到端流程：手动分析和自动抓取分析均走统一 Phase 0→1→SubAgent 流程

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 无依赖，立即开始
- **Phase 2 (Foundational)**: 依赖 Phase 1 完成 — **阻塞所有 User Story**
- **Phase 3-5 (US1/US2/US3)**: 均依赖 Phase 2 完成
  - US1 (预取) 和 US2 (压缩) 可并行
  - US3 (推理链) 依赖 US1 完成（推理链 prompt 需要注入预取结果）
- **Phase 6-7 (US4/US5)**: 依赖 Phase 3 完成（插桩需要预取流程已就绪）
  - US4 和 US5 可并行
- **Phase 8 (Polish)**: 依赖所有 User Story 完成

### Execution Order (Sequential)

```
Phase 1 → Phase 2 → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3)
                                                        ↓
                                          Phase 6 (US4) + Phase 7 (US5)
                                                        ↓
                                                   Phase 8 (Polish)
```

### Task Summary

| Phase | Task Count | 说明 |
|-------|-----------|------|
| Phase 1 Setup | 3 | 数据模型 + DB + SOP 格式 |
| Phase 2 Foundational | 4 | Bug 修复 + SOP 解析 + 缓存 |
| Phase 3 US1 | 5 | 预取流程 |
| Phase 4 US2 | 5 | 结构化压缩 |
| Phase 5 US3 | 3 | 推理链 prompt |
| Phase 6 US4 | 3 | 插桩遥测 |
| Phase 7 US5 | 2 | 安全网 |
| Phase 8 Polish | 4 | 文档 + 验证 |
| **Total** | **29** | |
