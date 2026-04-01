# Tasks: Perfetto 分析 Agent 化 — MCP 混合架构

**Input**: Design documents from `modules/perfetto_analysis/specs/002-agent-mcp-hybrid/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: 包含测试任务（spec SC-002 要求回归测试）。

**Organization**: 任务按 User Story 分组，每个 Story 可独立实现和测试。

## 目录

- [Format: `[ID] [P?] [Story] Description`](#format-id-p-story-description)
- [Phase 1: Setup (Shared Infrastructure)](#phase-1-setup-shared-infrastructure)
- [Phase 2: Foundational (Blocking Prerequisites)](#phase-2-foundational-blocking-prerequisites)
- [Phase 3: User Story 1 - 混合分析原子工具集 (Priority: P1) MVP](#phase-3-user-story-1---混合分析原子工具集-priority-p1--mvp)
- [Phase 4: User Story 2 - 分析结果压缩输出 (Priority: P1)](#phase-4-user-story-2---分析结果压缩输出-priority-p1)
- [Phase 5: User Story 5 - Agent 编排集成 (Priority: P1)](#phase-5-user-story-5---agent-编排集成-priority-p1)
- [Phase 6: User Story 3 - Feature Flag 运行时切换 (Priority: P2)](#phase-6-user-story-3---feature-flag-运行时切换-priority-p2)
- [Phase 7: User Story 4 - 多场景分析入口 (Priority: P2)](#phase-7-user-story-4---多场景分析入口-priority-p2)
- [Phase 8: Polish & Testing](#phase-8-polish--testing)
- [Dependencies & Execution Order](#dependencies--execution-order)
  - [Phase Dependencies](#phase-dependencies)
  - [User Story Dependencies](#user-story-dependencies)
  - [Parallel Opportunities](#parallel-opportunities)
- [Parallel Example: Foundational Phase](#parallel-example-foundational-phase)
- [Implementation Strategy](#implementation-strategy)
  - [MVP First (US1 + US2 + US5)](#mvp-first-us1--us2--us5)
  - [Incremental Delivery](#incremental-delivery)
- [Notes](#notes)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 配置文件更新，为新功能预置默认值

- [x] T001 ✅ 更新 `modules/perfetto_analysis/data/config.json` 增加 `analysis_mode`（默认 "mcp_preferred"）、`dimension_overrides`（默认 {}）、`mcp_timeout_ms`（默认 10000）配置项

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 核心数据模型和基础设施，所有 User Story 均依赖

**⚠️ CRITICAL**: 所有 User Story 任务必须等此阶段完成后方可开始

- [x] T002 ✅ 扩展 `modules/perfetto_analysis/src/models.py`：新增 `AnalysisMode` 枚举、`DimensionResult`、`TraceOverview`、`CompressedSummary`、`AnalysisScenario`、`ThreadStateSummary`（含 `to_compact_dict()`）、`CpuFreqAnalysis`（含 `to_compact_dict()`）；扩展 `AnalysisConfig` 新增 `analysis_mode`、`dimension_overrides`、`mcp_timeout_ms` 字段
- [x] T003 [P] ✅ 创建 `modules/perfetto_analysis/src/analysis_mode.py`：`FeatureFlagManager` + 维度级路由表
- [x] T004 [P] ✅ 创建 `modules/perfetto_analysis/src/mcp_client.py`：`McpAnalysisClient` 类，含所有 MCP 调用方法和异常捕获

**Checkpoint**: 基础设施就绪 — 可以开始实现 User Story

---

## Phase 3: User Story 1 - 混合分析原子工具集 (Priority: P1) 🎯 MVP

**Goal**: 暴露独立可调用的原子分析工具，每个工具支持 MCP/引擎路由和可选 time_range，Agent 可按需组合调用

**Independent Test**: 单独调用 `get_trace_overview()`、`detect_jank_frames()`、`analyze_dimension("thread", time_range)` 验证每个工具独立可用

### Implementation for User Story 1

- [x] T005 [US1] ✅ 创建 `modules/perfetto_analysis/src/analysis_toolkit.py`：`AnalysisToolkit` 类，含 get_trace_overview / detect_jank_frames / analyze_dimension / get_cpu_overview / find_slices / execute_sql 等核心方法
- [x] T005a [US1] ✅ 在 `AnalysisToolkit` 中新增 `thread_state_summary(trace_path, process, time_range?, compact?)` 方法
- [x] T005b [US1] ✅ 在 `AnalysisToolkit` 中新增 `cpu_freq_analysis(trace_path, process, time_range?, compact?)` 方法
- [x] T005c [US1] ✅ 原子工具支持 `compact=True` 参数：ThreadStateSummary/CpuFreqAnalysis 通过 `to_compact_dict()`，find_slices/execute_sql 通过 `_compact_rows()` 截断
- [x] T006 [US1] ✅ service.py 新增所有原子工具公共方法（含 thread_state_summary 和 cpu_freq_analysis），委托 AnalysisToolkit

**Checkpoint**: 每个原子工具可独立调用并返回正确结果，analyze_dimension 正确执行 MCP/引擎降级

---

## Phase 4: User Story 2 - 分析结果压缩输出 (Priority: P1)

**Goal**: 将一组原子工具的分析结果压缩为结构化 JSON 摘要，供 agent_chat 使用

**Independent Test**: 对比压缩摘要与全量报告，确认 Top N 根因未丢失且字符数 ≤ 全量报告 30%

### Implementation for User Story 2

- [x] T007 [US2] ✅ 创建 `modules/perfetto_analysis/src/result_compressor.py`：ResultCompressor 类
- [x] T008 [US2] ✅ service.py 新增 `compress_results()` 公共方法

**Checkpoint**: compress_results() 可接收任意组合的工具结果并生成 CompressedSummary JSON

---

## Phase 5: User Story 5 - Agent 编排集成 (Priority: P1)

**Goal**: 将所有原子工具注册为 agent_tools，编写 SOP 文档指导 Agent 的分析编排策略

**Independent Test**: Agent 可通过自然语言触发正确的工具调用链，SOP 文档可被 Agent 加载并指导分析流程

### Implementation for User Story 5

- [x] T009 [US5] ✅ plugin.py 注册 16 个 agent_tools（含 pa_thread_state_summary 和 pa_cpu_freq_analysis）
- [x] T010 [P] [US5] ✅ 已完成 — `skills/perfetto-analysis/sop/jank-analysis.md`：卡顿分析 SOP（含 CPU 维度深度分析、SF 维度、IO 交叉引用）
- [x] T011 [P] [US5] ✅ 已完成 — `skills/perfetto-analysis/sop/general-analysis.md`：通用分析 SOP（含场景路由交叉引用 SKILL.md）
- [x] T012 [US5] ✅ models.py 已有 `AnalysisChainStep` 和 `AnalysisChainResult` 数据模型
- [x] T013 [US5] ✅ analysis_toolkit.py 已集成 `_record_step()` 链路记录 + `get_chain_result()` 方法

**Checkpoint**: Agent 通过 agent_tools 调用原子工具完成卡顿分析，SOP 指导 Agent 的工具编排策略，分析链路可追溯

---

## Phase 6: User Story 3 - Feature Flag 运行时切换 (Priority: P2)

**Goal**: 通过配置项和 CLI 参数控制分析模式，支持运行时切换，engine_only 模式行为与改造前完全一致

**Independent Test**: 切换 config 中 feature flag 为 engine_only 后执行分析，结果与改造前 `analyze()` 一致

### Implementation for User Story 3

- [x] T014 [P] [US3] ✅ service.py 已有 `set_analysis_mode()` 和 `get_analysis_mode()` 方法
- [x] T015 [US3] ✅ cli_commands.py 已有 `--mode` 选项和 `config` 子命令
- [x] T015a [US3] ✅ 引擎 `parser.py` 输出增强：检测到 `refresh_rate_switches` 时增加 `mixed_refresh_rates: true`、`refresh_rate_segments`（含 hz、start_ns、end_ns、duration_s）

**Checkpoint**: CLI `analysis analyze --mode engine_only` 运行结果与改造前一致

---

## Phase 7: User Story 4 - 多场景分析入口 (Priority: P2)

**Goal**: 除卡顿分析外支持 ANR 检测和内存泄漏检测，不可用场景返回明确提示

**Independent Test**: 使用包含 ANR 数据的 trace 执行 ANR 分析，验证 MCP 工具返回结果

### Implementation for User Story 4

- [x] T016 [US4] ✅ mcp_client.py 已有 detect_anrs / analyze_anr_root_cause / detect_memory_leaks / analyze_heap_dominator
- [x] T017 [US4] ✅ analysis_toolkit.py 已有 analyze_anr / analyze_memory / check_scenario_availability
- [x] T018 [US4] ✅ service.py 已有 analyze_anr / analyze_memory 公共方法
- [x] T019 [US4] ✅ plugin.py 已注册 pa_analyze_anr / pa_analyze_memory agent tools
- [x] T020 [P] [US4] ✅ 已完成 — `skills/perfetto-analysis/sop/anr-analysis.md`：ANR 分析 SOP
- [x] T021 [P] [US4] ✅ 已完成 — `skills/perfetto-analysis/sop/memory-analysis.md`：内存分析 SOP

**Checkpoint**: analyze_anr() 和 analyze_memory() 在对应 trace 上返回结果，不支持的 trace 返回明确提示

---

## Phase 8: Polish & Testing

**Purpose**: 全面测试和回归验证

- [x] T022 [P] ✅ `test_mcp_client.py`：12 个测试（默认返回 / mock 成功 / 超时 / time_range 传递 / 自定义超时）
- [x] T023 [P] ✅ `test_toolkit.py`：22 个测试（路由 / 降级 / time_range / 合并 / 链路 + 新增 thread_state_summary / cpu_freq_analysis / compact 模式）
- [x] T024 [P] ✅ `test_compressor.py`：15 个测试（severity / root_cause / health_summary / data_completeness / 压缩比）
- [x] T025 ✅ `test_regression.py`：5 个测试（engine_only 路由 / source 标注 / MCP 优先 / dimension_override）；真实 trace 性能基准需后续补充

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖 — 立即开始
- **Foundational (Phase 2)**: 依赖 Phase 1 完成 — **阻塞所有 User Story**
- **US1 (Phase 3)**: 依赖 Phase 2 完成
- **US2 (Phase 4)**: 依赖 Phase 3 完成（需要 DimensionResult 输出来压缩）
- **US5 (Phase 5)**: 依赖 Phase 3 + Phase 4 完成（需要原子工具 + 压缩能力注册为 agent_tools）
- **US3 (Phase 6)**: 依赖 Phase 2 完成，可与 Phase 3/4/5 并行
- **US4 (Phase 7)**: 依赖 Phase 2 完成，可与 Phase 3/4/5 并行
- **Polish & Testing (Phase 8)**: 依赖所有目标 User Story 完成

### User Story Dependencies

- **US1 (P1)**: Phase 2 完成后即可开始 — 不依赖其他 Story
- **US2 (P1)**: 依赖 US1（需要 DimensionResult 和 TraceOverview 作为压缩器输入）
- **US5 (P1)**: 依赖 US1 + US2（需要原子工具 + 压缩能力来注册和编写 SOP）
- **US3 (P2)**: Phase 2 完成后即可开始 — 不依赖 US1/US2/US5
- **US4 (P2)**: Phase 2 完成后即可开始 — 不依赖其他 Story

### Parallel Opportunities

- **Phase 2**: T003 和 T004 可并行（不同文件，均仅依赖 T002）
- **Phase 5**: T010 和 T011 可并行（不同 SOP 文档，无依赖）
- **Phase 6 + Phase 7**: US3 和 US4 可并行（独立 Story，不同关注点）
- **Phase 7**: T020 和 T021 可并行（不同 SOP 文档）
- **Phase 8**: T022、T023、T024 可并行（不同测试文件，无依赖）

---

## Parallel Example: Foundational Phase

```text
# Phase 2 中 T002 完成后可并行的任务：
Task T003: "创建 analysis_mode.py — FeatureFlagManager + 路由表"
Task T004: "创建 mcp_client.py — McpAnalysisClient 核心方法"

# Phase 5 中可并行的 SOP 文档：
Task T010: "创建 jank-analysis.md — 卡顿分析 SOP"
Task T011: "创建 general-analysis.md — 通用分析 SOP"

# Phase 8 中可并行的测试任务：
Task T022: "test_mcp_client.py — MCP 调用 mock 测试"
Task T023: "test_toolkit.py — 原子工具集测试"
Task T024: "test_compressor.py — 压缩器测试"
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US5)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational（**CRITICAL — 阻塞所有 Story**）
3. Complete Phase 3: US1 — 原子工具集
4. **STOP and VALIDATE**: 逐个调用原子工具验证独立可用
5. Complete Phase 4: US2 — 压缩摘要
6. **STOP and VALIDATE**: 验证 CompressedSummary 信息覆盖度
7. Complete Phase 5: US5 — Agent 编排集成
8. **STOP and VALIDATE**: 通过自然语言验证 Agent 正确编排工具链

### Incremental Delivery

1. Setup + Foundational → 基础设施就绪
2. US1 → 原子工具可用 → 验证（核心 MVP!）
3. US2 → 压缩摘要可用 → 验证
4. US5 → Agent 编排集成 → 验证端到端
5. US3 → Feature Flag 运行时切换 → 验证 engine_only 回归
6. US4 → ANR/Memory 场景 → 验证多场景
7. Testing → 全面回归 → 交付

---

## Notes

- [P] tasks = 不同文件、无依赖关系
- [Story] 标签映射到 spec.md 中的 User Story
- 所有文件路径相对于项目根目录 `lv-game-toolkit/`
- 现有引擎代码（`src/engine/`）不修改核心算法
- 现有 `analyze()` / `parse_only()` 方法不修改
- MCP 调用通过 Cursor IDE MCP 协议
- SOP 文档存放在 `skills/perfetto-analysis/sop/`，通过 `sync_skills.py` 同步到 `.cursor/skills/`
- 每完成一个 Checkpoint 应运行已有测试确认无回归
