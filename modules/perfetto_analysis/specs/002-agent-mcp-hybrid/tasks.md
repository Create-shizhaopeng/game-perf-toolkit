# Tasks: Perfetto 分析 Agent 化 — MCP 混合架构

**Input**: Design documents from `modules/perfetto_analysis/specs/002-agent-mcp-hybrid/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: 包含测试任务（spec SC-002 要求回归测试）。

**Organization**: 任务按 User Story 分组，每个 Story 可独立实现和测试。

## 目录

- [Format: `[ID] [P?] [Story] Description`](#format-id-p-story-description)
- [Phase 1: Setup (Shared Infrastructure)](#phase-1-setup-shared-infrastructure)
- [Phase 2: Foundational (Blocking Prerequisites)](#phase-2-foundational-blocking-prerequisites)
- [Phase 3: User Story 1 - 混合分析原子工具集 (Priority: P1)](#phase-3-user-story-1---混合分析原子工具集-priority-p1)
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

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 配置文件更新，为新功能预置默认值

- [ ] T001 更新 `modules/perfetto_analysis/data/config.json` 增加 `analysis_mode`（默认 "mcp_preferred"）、`dimension_overrides`（默认 {}）、`mcp_timeout_ms`（默认 10000）配置项

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 核心数据模型和基础设施，所有 User Story 均依赖

**⚠️ CRITICAL**: 所有 User Story 任务必须等此阶段完成后方可开始

- [ ] T002 扩展 `modules/perfetto_analysis/src/models.py`：新增 `AnalysisMode` 枚举（mcp_preferred / engine_only / mcp_only）、`DimensionResult` 数据模型（含 `source: str` 标注字段和 `data: dict` 结果字段）、`TraceOverview` 模型（duration_s / processes / frame_count / refresh_rate_hz / scenario_phases）、`CompressedSummary` Pydantic 模型（按 spec C3 JSON schema 定义）、`AnalysisScenario` 数据模型（场景名 / 所需 MCP 工具列表 / 引擎维度映射，用于 US4 多场景分析）；扩展 `AnalysisConfig` 新增 `analysis_mode`、`dimension_overrides`、`mcp_timeout_ms` 字段
- [ ] T003 [P] 创建 `modules/perfetto_analysis/src/analysis_mode.py`：实现 `FeatureFlagManager`（读取 AnalysisConfig 中的 mode 设置）和维度级路由表（基于 plan.md 降级策略表，定义每个维度的默认策略和 MCP 工具映射，返回 "engine_only" / "mcp_preferred" / "mcp_only"）
- [ ] T004 [P] 创建 `modules/perfetto_analysis/src/mcp_client.py`：实现 `McpAnalysisClient` 类，包含 `analyze_thread_contention()`、`analyze_binder()`、`get_main_thread_hotspots()`、`get_cpu_utilization()`、`find_slices()`、`execute_sql()` 方法；每个方法返回 `dict | None`（成功返回结构化数据，失败/超时/空数据返回 None）；实现 MCP 连接异常捕获和可配置超时（默认 10s）

**Checkpoint**: 基础设施就绪 — 可以开始实现 User Story

---

## Phase 3: User Story 1 - 混合分析原子工具集 (Priority: P1) 🎯 MVP

**Goal**: 暴露独立可调用的原子分析工具，每个工具支持 MCP/引擎路由和可选 time_range，Agent 可按需组合调用

**Independent Test**: 单独调用 `get_trace_overview()`、`detect_jank_frames()`、`analyze_dimension("thread", time_range)` 验证每个工具独立可用

### Implementation for User Story 1

- [ ] T005 [US1] 创建 `modules/perfetto_analysis/src/analysis_toolkit.py`：实现 `AnalysisToolkit` 类，核心方法包括：(1) `get_trace_overview(trace_path, process?)` — 调用引擎 parser 获取 trace 元数据（duration、processes、frame_count、refresh_rate、场景阶段列表），返回 TraceOverview；(2) `detect_jank_frames(trace_path, process, time_range?)` — 调用引擎的 VSync/Buffer 卡顿检测，可选 time_range 过滤，返回 jank 帧列表；当多个 jank 帧时间窗口重叠时合并为一个窗口；(3) `analyze_dimension(trace_path, process, dimension, time_range?)` — 根据 FeatureFlagManager 路由到 MCP 或引擎，执行单维度分析，返回 DimensionResult（含 source 标注）；对 time_range 做边界验证（超出 trace 时间范围时返回明确错误）；(4) `get_cpu_overview(trace_path, process)` — 调用 MCP cpu_utilization_profiler 返回全 trace CPU 概览；(5) `find_slices(trace_path, pattern, process?)` — 透传到 McpAnalysisClient；(6) `execute_sql(trace_path, sql)` — 透传到 McpAnalysisClient
- [ ] T006 [US1] 修改 `modules/perfetto_analysis/src/service.py`：新增 `get_trace_overview()`、`detect_jank_frames()`、`analyze_dimension()`、`get_cpu_overview()`、`find_slices()`、`execute_sql()` 公共方法，内部委托 AnalysisToolkit；实例化 AnalysisToolkit 时注入 McpAnalysisClient 和 FeatureFlagManager；现有 `analyze()` 方法不修改

**Checkpoint**: 每个原子工具可独立调用并返回正确结果，analyze_dimension 正确执行 MCP/引擎降级

---

## Phase 4: User Story 2 - 分析结果压缩输出 (Priority: P1)

**Goal**: 将一组原子工具的分析结果压缩为结构化 JSON 摘要，供 agent_chat 使用

**Independent Test**: 对比压缩摘要与全量报告，确认 Top N 根因未丢失且字符数 ≤ 全量报告 30%

### Implementation for User Story 2

- [ ] T007 [US2] 创建 `modules/perfetto_analysis/src/result_compressor.py`：实现 `ResultCompressor` 类，输入为 `TraceOverview` + `list[DimensionResult]` + 可选 jank 帧列表，输出 `CompressedSummary`；包含：(1) `trace_info` 提取（从 TraceOverview）；(2) `severity` 计算（基于 jank_count 和 max_jank_num 映射到 CRITICAL/HIGH/MEDIUM/LOW）；(3) `root_causes` 提取（遍历 DimensionResult 按严重度排序取 Top N，每个含 rank/cause/evidence/severity/dimension）；(4) `health_summary` 生成（每维度 OK/WARNING/CRITICAL/UNAVAILABLE + 一行说明）；(5) `data_completeness` 统计（degraded_dimensions / mcp_source / engine_source 列表）
- [ ] T008 [US2] 修改 `modules/perfetto_analysis/src/service.py`：新增 `compress_results(trace_overview, dimension_results, jank_frames?)` 公共方法，内部调用 ResultCompressor 返回 CompressedSummary

**Checkpoint**: compress_results() 可接收任意组合的工具结果并生成 CompressedSummary JSON

---

## Phase 5: User Story 5 - Agent 编排集成 (Priority: P1)

**Goal**: 将所有原子工具注册为 agent_tools，编写 SOP 文档指导 Agent 的分析编排策略

**Independent Test**: Agent 可通过自然语言触发正确的工具调用链，SOP 文档可被 Agent 加载并指导分析流程

### Implementation for User Story 5

- [ ] T009 [US5] 修改 `modules/perfetto_analysis/src/plugin.py`：在 `register_agent_tools()` 中注册以下原子工具 — `pa_trace_overview`（获取 trace 元数据）、`pa_detect_jank`（检测卡顿帧）、`pa_analyze_dimension`（单维度分析，参数含 dimension + time_range）、`pa_cpu_overview`（CPU 全局概览）、`pa_find_slices`（搜索 slice）、`pa_execute_sql`（执行 SQL）、`pa_compress_results`（压缩结果）；保留现有 `pa_analyze` 和 `pa_parse` 工具不变
- [ ] T010 [P] [US5] 创建 `modules/perfetto_analysis/docs/sop/jank-analysis.md`：卡顿分析 SOP，包含分析目标、前置检查（get_trace_overview 确认场景）、工具调用顺序（detect_jank → 确定 time_range → analyze_dimension 逐维度 → compress_results）、结果解读指引、常见卡顿模式识别（主线程耗时、Binder 阻塞、GPU 瓶颈等）
- [ ] T011 [P] [US5] 创建 `modules/perfetto_analysis/docs/sop/general-analysis.md`：通用分析 SOP，包含场景不明时的引导流程（get_trace_overview → 场景分类 → 加载对应场景 SOP → 如无匹配则按用户意图选择工具组合）；显式包含"当 Agent 无法从元数据确定时间范围时，MUST 向用户询问"的交互步骤
- [ ] T012 [US5] 在 `modules/perfetto_analysis/src/models.py` 中新增 `AnalysisChainStep` 数据模型（tool_name / input_params / output_summary / duration_ms / source）和 `AnalysisChainResult` 模型（steps 列表 + 最终结论 + 置信度标注），用于分析链路追溯
- [ ] T013 [US5] 修改 `modules/perfetto_analysis/src/analysis_toolkit.py`：在 `analyze_dimension()`、`detect_jank_frames()`、`get_cpu_overview()` 等工具方法中集成 AnalysisChainStep 记录能力（每次调用记录 tool_name / input_params / output_summary / duration_ms / source），提供 `get_chain_result()` 方法返回当前分析会话的完整 AnalysisChainResult

**Checkpoint**: Agent 通过 agent_tools 调用原子工具完成卡顿分析，SOP 指导 Agent 的工具编排策略，分析链路可追溯

---

## Phase 6: User Story 3 - Feature Flag 运行时切换 (Priority: P2)

**Goal**: 通过配置项和 CLI 参数控制分析模式，支持运行时切换，engine_only 模式行为与改造前完全一致

**Independent Test**: 切换 config 中 feature flag 为 engine_only 后执行分析，结果与改造前 `analyze()` 一致

### Implementation for User Story 3

- [ ] T014 [P] [US3] 修改 `modules/perfetto_analysis/src/service.py`：新增 `set_analysis_mode(mode, dimension_overrides=None)` 和 `get_analysis_mode()` 方法，支持运行时修改 AnalysisConfig 中的模式设置并持久化到 config.json
- [ ] T015 [US3] 修改 `modules/perfetto_analysis/src/cli_commands.py`：(1) `analyze` 命令新增 `--mode` 选项（mcp_preferred / engine_only / mcp_only，默认从 config 读取）；(2) 新增 `config` 子命令，支持 `analysis config show`（显示当前 analysis_mode 及维度覆盖）和 `analysis config set --mode <mode>`（运行时修改）

**Checkpoint**: CLI `analysis analyze --mode engine_only` 运行结果与改造前一致

---

## Phase 7: User Story 4 - 多场景分析入口 (Priority: P2)

**Goal**: 除卡顿分析外支持 ANR 检测和内存泄漏检测，不可用场景返回明确提示

**Independent Test**: 使用包含 ANR 数据的 trace 执行 ANR 分析，验证 MCP 工具返回结果

### Implementation for User Story 4

- [ ] T016 [US4] 修改 `modules/perfetto_analysis/src/mcp_client.py`：新增 `detect_anrs()`、`analyze_anr_root_cause()`、`detect_memory_leaks()`、`analyze_heap_dominator()` 方法
- [ ] T017 [US4] 修改 `modules/perfetto_analysis/src/analysis_toolkit.py`：新增 `analyze_anr(trace_path, process)` 和 `analyze_memory(trace_path, process)` 方法（调用对应 MCP 方法）；新增 `check_scenario_availability(trace_path, scenario)` 方法（基于 trace 元数据和 AnalysisScenario 定义判断场景是否可行，不可行时返回明确原因）
- [ ] T018 [US4] 修改 `modules/perfetto_analysis/src/service.py`：新增 `analyze_anr()` 和 `analyze_memory()` 公共方法；不可用场景返回包含明确错误信息的结果
- [ ] T019 [US4] 修改 `modules/perfetto_analysis/src/plugin.py`：注册 `pa_analyze_anr`（ANR 检测分析）和 `pa_analyze_memory`（内存泄漏分析）agent tools
- [ ] T020 [P] [US4] 创建 `modules/perfetto_analysis/docs/sop/anr-analysis.md`：ANR 分析 SOP
- [ ] T021 [P] [US4] 创建 `modules/perfetto_analysis/docs/sop/memory-analysis.md`：内存分析 SOP

**Checkpoint**: analyze_anr() 和 analyze_memory() 在对应 trace 上返回结果，不支持的 trace 返回明确提示

---

## Phase 8: Polish & Testing

**Purpose**: 全面测试和回归验证

- [ ] T022 [P] 创建 `modules/perfetto_analysis/tests/test_mcp_client.py`：McpAnalysisClient 单元测试（mock MCP 调用返回值，测试正常返回 / None 返回 / 超时 / 异常场景）
- [ ] T023 [P] 创建 `modules/perfetto_analysis/tests/test_toolkit.py`：AnalysisToolkit 单元测试（测试每个原子工具的独立调用、MCP/引擎路由、降级流程、time_range 过滤及边界验证、重叠时间窗口合并、数据来源标注、AnalysisChainStep 记录）
- [ ] T024 [P] 创建 `modules/perfetto_analysis/tests/test_compressor.py`：ResultCompressor 单元测试（severity 计算 / root_cause 排序 / health_summary 生成 / data_completeness 统计 / 压缩比验证）
- [ ] T025 创建 `modules/perfetto_analysis/tests/test_regression.py`：回归测试 — 使用真实 trace，验证 engine_only 模式下原子工具结果与现有 `analyze()` 输出一致（SC-002 要求通过率 100%）

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
- SOP 文档存放在 `docs/sop/`，随场景积累持续新增
- 每完成一个 Checkpoint 应运行已有测试确认无回归
