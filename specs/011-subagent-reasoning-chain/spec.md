# Feature Specification: SubAgent 推理链重构

**Feature Branch**: `011-subagent-reasoning-chain`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "G0 SubAgent 推理链重构：统一分析流程、结构化压缩、插桩观测"

## 目录

- [User Scenarios & Testing](#user-scenarios--testing)
- [Requirements](#requirements)
- [Success Criteria](#success-criteria)
- [Assumptions](#assumptions)
- [Clarifications](#clarifications)

## User Scenarios & Testing

### User Story 1 - 场景感知预取提升分析准确性 (Priority: P1)

作为 Perfetto 分析用户，当我提交一个 trace 文件并描述分析意图时，系统根据我的意图自动识别分析场景（卡顿/ANR/启动/CPU/通用），并在 SubAgent 深度分析前预取该场景最关键的数据，使 SubAgent 一开始就拥有高质量上下文而非从零探索。

**Why this priority**: 预取是所有后续改进（结构化压缩、经验注入、Review）的基础。没有准确的场景路由和高质量预取数据，后续优化无法生效。

**Independent Test**: 提交一个已知存在 CPU 限频问题的卡顿 trace，验证系统能自动识别为 jank 场景、预取 detect_jank 数据、并在 SubAgent prompt 中注入卡顿帧窗口信息。

**Acceptance Scenarios**:

1. **Given** 用户提交 trace 并输入"分析卡顿原因", **When** MainAgent 路由, **Then** 场景被识别为 `jank`，编排器自动调用 `detect_jank` 预取卡顿帧窗口
2. **Given** trace 来自自动抓取模块（DB 中已有 jank_count 和 process_name）, **When** 触发分析, **Then** 编排器直接从 DB 读取预填信息注入 Phase 0，不跳过任何分析步骤
3. **Given** 用户意图模糊（如"看看这个 trace"）, **When** MainAgent 无法确定场景, **Then** 路由到 `general` 场景，预取全面 trace 概览
4. **Given** 预取结果已写入缓存, **When** SubAgent 在深度分析阶段调用相同工具和参数, **Then** 直接返回缓存数据，不重复查询 trace 文件

---

### User Story 2 - 结构化压缩保留关键异常信息 (Priority: P1)

作为 Perfetto 分析用户，当 SubAgent 调用分析工具时，系统根据引擎的异常标记（severity）决定压缩策略——异常信息完整保留，正常信息精简摘要——而非当前固定截断到 300 token 导致关键异常被丢失。

**Why this priority**: 与 Story 1 同等重要，直接影响 SubAgent 的推理质量。当前 300 token 一刀切是分析浅层化的核心原因之一。

**Independent Test**: 对一个已知存在 3 个 CPU 限频 CRITICAL issue 的 trace 运行分析，验证压缩后的工具返回值完整包含所有 CRITICAL/HIGH 的异常详情。

**Acceptance Scenarios**:

1. **Given** 引擎分析结果包含 3 个 CRITICAL 和 2 个 WARNING 级别 issue, **When** 结构化压缩执行, **Then** 所有 CRITICAL/HIGH/WARNING 的 issue 详情完整保留在压缩结果中
2. **Given** 引擎分析结果全部正常（无异常 issue）, **When** 结构化压缩执行, **Then** 返回精简摘要（一句话"N 个维度正常"+ 关键极端值指标）
3. **Given** 工具返回的原始数据无 severity 标记（如 `pa_execute_sql`）, **When** 压缩执行, **Then** 按 500 token 上限截断
4. **Given** 工具查询结果, **When** 分析完成, **Then** 原始结果已写入缓存和 DB，可供后续经验提取使用

---

### User Story 3 - 推理链引导 SubAgent 结构化思考 (Priority: P1)

作为 Perfetto 分析用户，当 SubAgent 执行分析时，它按照 Phase A（根因排查）→ Phase B（交叉验证）→ Phase C（输出报告）的推理链执行，而非当前的无引导自由探索，确保分析过程有层次、有收敛。

**Why this priority**: 推理链是 SubAgent 深度分析的骨架，与 Story 1/2 共同构成 G0 的核心价值。

**Independent Test**: 对任意 trace 执行分析，观察 SubAgent 的工具调用序列是否呈现"先排查→后验证→最后输出"的层次结构，而非随机跳跃式调用。

**Acceptance Scenarios**:

1. **Given** SubAgent 收到场景为 `jank` 的推理链 prompt, **When** 执行分析, **Then** 优先调用 cpu/thread/binder 维度分析（priority_dims），再按需调用 gpu/sf/io（secondary_dims）
2. **Given** SubAgent 在 Phase A 已找到 ≥2 个 CRITICAL 根因, **When** 还剩低优先级维度未分析, **Then** SubAgent 可跳过剩余维度直接进入 Phase B 交叉验证
3. **Given** SubAgent 完成所有分析, **When** 输出 Phase C 报告, **Then** 每个根因包含 tag、severity、定性描述、定量数据、证据和推理过程

---

### User Story 4 - 插桩观测记录分析遥测数据 (Priority: P2)

作为系统开发者，当每次分析完成后，系统自动记录工具调用次数/明细、token 消耗、分析耗时等遥测数据到数据库，便于后续优化分析效率和成本。

**Why this priority**: 插桩不影响用户可见功能，但为后续 G3（淘汰评分）和性能调优提供数据基础。

**Independent Test**: 运行一次分析后查询 `pa_telemetry` 表，验证包含完整的工具调用记录和 token 消耗数据。

**Acceptance Scenarios**:

1. **Given** 一次分析完成, **When** 查询 `pa_telemetry` 表, **Then** 包含该次分析的 trace_id、scene、model_name、tool_call_count、tool_calls_detail、token 消耗、elapsed_sec
2. **Given** SubAgent 调用了 8 次工具, **When** 遥测写入, **Then** `tool_calls_detail` JSON 数组包含 8 条记录，每条含 tool 名和 elapsed_ms

---

### User Story 5 - 安全网防止 LLM 失控调用 (Priority: P2)

作为系统用户，当 SubAgent 因 LLM 推理异常进入死循环调用时，系统在 50 次请求后自动终止分析并输出已有结果，而非无限消耗 token。

**Why this priority**: 防护性功能，对正常分析无影响，但避免极端情况下的资源浪费。

**Independent Test**: 设置较低的 request_limit（如 5），验证 SubAgent 达到上限后正常终止并返回已有分析结果。

**Acceptance Scenarios**:

1. **Given** `request_limit=50`, **When** SubAgent 工具调用次数达到 50 次, **Then** 分析终止，已有结果仍然可用
2. **Given** 正常分析（工具调用 <30 次）, **When** 分析完成, **Then** request_limit 不影响分析过程

---

### Edge Cases

- **MainAgent 路由失败**：如果 MainAgent 返回不在 SCENE_CONFIG 中的场景，回退到 `general` 场景
- **预取阶段工具异常**：如果预取工具调用失败（如 trace 文件损坏），SubAgent 仍能以无预取数据模式运行（降级到当前行为）
- **缓存键冲突**：同一 trace 被不同进程名分析时，缓存键包含 process_name 避免数据污染
- **空 trace**：trace 文件不包含目标维度数据时（如游戏 trace 无 FrameTimeline），引擎返回空结果，压缩器输出"该维度无数据"

## Requirements

### Functional Requirements

- **FR-001**: 编排器 MUST 在 SubAgent 运行前执行场景感知预取（Phase 0 路由 + Phase 1 预取）
- **FR-002**: MainAgent MUST 分析用户意图并匹配到 SOP 定义的分析场景，不限于固定场景列表
- **FR-003**: 编排器 MUST 根据匹配的 SOP 场景元数据（优先维度、预取策略）动态组装 SubAgent prompt
- **FR-004**: 预取结果 MUST 写入会话级缓存（`_analysis_cache`），SubAgent 工具调用时先查缓存
- **FR-005**: 工具返回值 MUST 按注册的压缩策略处理：`degraded=True` 的维度数据完整保留，`degraded=False` 的精简为摘要
- **FR-006**: `pa_execute_sql`、`pa_find_slices` 返回值 MUST 按 500 token 上限截断
- **FR-013**: `pa_detect_jank` MUST 返回结构化的 `jank_records` 数据（修复当前 str() 序列化 bug）
- **FR-014**: `pa_analyze_dimension` 的 `compact` 参数 MUST 正确传递（修复当前参数位置错误）
- **FR-007**: SubAgent prompt MUST 包含推理链结构（Phase A/B/C）和场景特化优先级维度
- **FR-008**: SubAgent prompt MUST NOT 包含具体工具调用次数限制
- **FR-009**: SubAgent 的 `request_limit` MUST 设为 50（安全网）
- **FR-010**: 每次分析完成后 MUST 将遥测数据写入 `pa_telemetry` 表
- **FR-011**: 工具查询结果 MUST 写入缓存，缓存生命周期与单次分析会话一致
- **FR-012**: 自动抓取触发的分析 MUST 从 DB 读取预填信息（jank_count, process_name）注入 Phase 0

### Key Entities

- **SCENE_CONFIG**: 场景维度优先级配置，key 为场景名，value 含 priority_dims/secondary_dims/optional_dims
- **_analysis_cache**: 会话级工具结果缓存，key 格式 `{trace_path}:{dimension}:{process_name}`
- **pa_telemetry**: 分析遥测记录表，记录工具调用、token 消耗、耗时等数据

## Success Criteria

### Measurable Outcomes

- **SC-001**: 分析结果中异常信息保留率从当前的 ~60%（300 token 截断导致丢失）提升到 100%（`degraded=True` 的维度数据完整保留，卡顿帧 `jank_records` 完整保留）
- **SC-002**: SubAgent 重复工具调用率降低到 0%（缓存命中直接返回）
- **SC-003**: 每次分析完成后 `pa_telemetry` 表有对应记录，数据完整率 100%
- **SC-004**: 分析流程一致性：所有分析（手动/自动）遵循相同的 Phase 0→1→SubAgent 流程

## Assumptions

- MainAgent 使用的 LLM 具备基础的意图分类能力（已有 AnalysisRouting 模型验证）
- `pydantic-ai` 框架支持 `request_limit` 参数控制工具调用次数上限
- 缓存仅用于单次分析会话内，不需要持久化或跨会话共享

## Clarifications

### Session 2026-04-09

- Q: 引擎层是否产出 `issues`/`severity` 字段供结构化压缩使用？ → A: 否。引擎各维度使用 `degraded` (bool) + `degraded_reason` (str) 标记异常，无统一 `issues` 列表。压缩策略改为基于工具级压缩策略注册表，不依赖统一 `issues` 字段。
  - `pa_analyze_dimension`: `degraded_aware` 策略（degraded=True 的维度保留完整数据，degraded=False 精简为摘要）
  - `pa_detect_jank`: 保留 `jank_records` 完整结构（需修复当前 str() 序列化 bug）
  - `pa_trace_overview` / `pa_list_dimensions`: 保留全部（数据量小）
  - `pa_execute_sql` / `pa_find_slices`: 按 500 token 截断
  - `pa_analyze_anr` / `pa_analyze_memory`: 保留全部（MCP 返回量小）
- Q: 调研中发现的代码 Bug 是否纳入 G0 修复范围？ → A: 是。`pa_detect_jank` 的 str() 序列化丢失和 `pa_analyze_dimension` 的 compact 参数误传需在 G0 中修复，否则结构化压缩无法正确工作。
- Q: SCENE_CONFIG 是否应固定为 5 个场景？ → A: 否。改为 LLM 动态路由方案：MainAgent 分析用户意图后匹配 SOP 场景，动态组装场景定制 prompt 创建 SubAgent。SCENE_CONFIG 不再是硬编码常量，而是从 SOP 元数据（场景名、优先维度等）动态加载。后续迭代方向：强 MainAgent + 多专业 SubAgent 架构。
- Q: MCP stub 下 ANR/启动/内存场景的预取如何处理？ → A: 复用现有降级逻辑。MCP 不可用时自动降级到引擎路径（如 ANR → thread+binder+lock 维度分析），预取结果仍写入缓存供 SubAgent 使用。
