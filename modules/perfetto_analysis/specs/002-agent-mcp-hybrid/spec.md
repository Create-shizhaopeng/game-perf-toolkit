# Feature Specification: Perfetto 分析 Agent 化 — MCP 混合架构

**Feature Branch**: `002-agent-mcp-hybrid`  
**Spec Location**: `modules/perfetto_analysis/specs/002-agent-mcp-hybrid/`  
**Created**: 2026-03-31  
**Status**: Draft  
**Input**: Perfetto 分析模块 Agent 化改造，采用 MCP 混合架构，支持多性能场景分析

## 目录

- [User Scenarios & Testing](#user-scenarios--testing-mandatory)
- [Requirements](#requirements-mandatory)
- [Assumptions](#assumptions)
- [Clarifications](#clarifications)
- [Success Criteria](#success-criteria-mandatory)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 混合分析原子工具集 (Priority: P1)

系统提供一组原子分析工具，每个工具支持 MCP 优先 + 引擎降级、可选 time_range 过滤。Agent（或用户）可按需调用单个或多个工具，而非固定执行全量维度。原子工具包括：trace 元数据查询、卡顿帧检测、单维度分析、灵活 SQL 查询等。现有 `analyze()` 方法保留不变，供 CLI/GUI 直接调用。

**Why this priority**: 原子工具是所有分析场景的基础构件，Agent 编排和多场景扩展均依赖它们

**Independent Test**: 单独调用 `get_trace_overview()`、`detect_jank_frames()`、`analyze_dimension("thread", time_range)` 等工具，验证每个工具独立可用且 MCP/引擎降级正常

**Acceptance Scenarios**:

1. **Given** 一个 trace 文件, **When** 调用 `get_trace_overview()`, **Then** 返回 trace 元数据（duration、processes、frame_count、检测到的场景阶段）
2. **Given** 一个 trace 和进程名, **When** 调用 `detect_jank_frames(time_range=可选)`, **Then** 返回 jank 帧列表（含每帧的时间窗口信息）
3. **Given** 一个 jank 帧的 time_range, **When** 调用 `analyze_dimension("thread", time_range)`, **Then** MCP 优先返回线程竞争分析，失败时降级到引擎
4. **Given** 每个工具返回结果, **Then** 结果中标注数据来源（mcp / engine / degraded / unavailable）

---

### User Story 2 — 分析结果压缩输出 (Priority: P1)

分析完成后，系统生成结构化的压缩摘要（而非全量报告），供 agent_chat 调用时作为上下文输入。摘要包含：关键指标汇总、Top N 根因归因、建议方向，总 token 量控制在可接受范围内。

**Why this priority**: agent_chat 的上下文窗口有限，过多的分析数据会导致 LLM 幻觉，直接影响策略生成质量

**Independent Test**: 对比压缩摘要与全量报告的信息覆盖度，确认关键根因未丢失且 token 量显著降低

**Acceptance Scenarios**:

1. **Given** 一次完整分析结果, **When** 生成压缩摘要, **Then** 摘要包含卡顿帧数/帧率/刷新率基础信息、Top 3 卡顿根因、各维度健康度评级
2. **Given** 压缩摘要, **When** agent_chat 读取, **Then** 无需再回查全量报告即可生成性能优化策略
3. **Given** 全量报告约 300+ 行 Markdown, **When** 压缩后, **Then** 摘要不超过 80 行结构化文本

---

### User Story 3 — MCP/引擎切换的 Feature Flag (Priority: P2)

通过配置项控制每个分析维度是使用 MCP 优先还是纯引擎模式，支持在运行时切换。现有引擎代码完整保留，不删除不修改核心逻辑。

**Why this priority**: 确保改造过程不影响现有功能的稳定性，同时支持渐进式切换验证

**Independent Test**: 在 config 中切换 feature flag 后，分别运行 MCP 模式和引擎模式，验证两者均可正常输出

**Acceptance Scenarios**:

1. **Given** feature flag 设为 "mcp_preferred", **When** 执行分析, **Then** MCP 工具优先调用，失败时降级到引擎
2. **Given** feature flag 设为 "engine_only", **When** 执行分析, **Then** 完全使用引擎，行为与改造前一致
3. **Given** feature flag 设为 "mcp_only", **When** MCP 返回空数据, **Then** 该维度标记为"数据不可用"而非降级

---

### User Story 4 — 多场景分析入口 (Priority: P2)

除卡顿分析外，系统支持 ANR 检测与根因分析、内存泄漏检测等新场景。新场景通过 MCP 工具实现，引擎不需要新增这些能力。

**Why this priority**: 扩展模块的分析覆盖面，为后续 Agent 编排层提供多场景工具集

**Independent Test**: 使用包含 ANR 数据的 trace 执行 ANR 分析，验证 MCP 工具正确返回结果

**Acceptance Scenarios**:

1. **Given** 一个包含 ANR 的 trace, **When** 用户请求 ANR 分析, **Then** 系统调用 MCP detect_anrs + anr_root_cause_analyzer 返回根因
2. **Given** 一个包含 heap graph 的 trace, **When** 用户请求内存分析, **Then** 系统调用 MCP memory_leak_detector + heap_dominator_tree_analyzer
3. **Given** trace 不包含所需数据, **When** 用户请求新场景分析, **Then** 系统返回"该 trace 不包含所需数据"的明确提示

---

### User Story 5 — Agent 编排集成（LLM 驱动分析） (Priority: P1)

Agent（Cursor LLM）理解用户自然语言意图后，查询 trace 元数据确定分析场景和时间范围，按需编排原子工具完成分析并组装结论。Agent 通过 SOP/Skills 获取分析策略指导，不依赖固定流水线。取代原有的全量一键分析模式，成为主要分析入口。

时间范围确定策略：Agent 默认通过 trace 元数据理解场景后自动确定时间范围；无法确定时向用户询问；用户也可直接指定分析范围。

**Why this priority**: Agent 自主编排是核心使用模式，取代固定流水线。用户直接与 Agent 交互，Agent 决定调用哪些工具

**Independent Test**: 给定自然语言分析请求（如"分析启动动画 5s-15s 的卡顿"），Agent 正确识别时间范围、选择相关维度、调用原子工具并输出结论

**Acceptance Scenarios**:

1. **Given** 用户输入"分析这个 trace 的启动动画卡顿", **When** Agent 处理, **Then** Agent 先调用 `get_trace_overview()` → 识别动画阶段时间范围 → 调用 `detect_jank_frames(time_range)` → 对每个 jank 帧调用 `analyze_dimension()` → 压缩结果 → 输出根因
2. **Given** 用户输入"只看 5s 到 10s 的 CPU 情况", **When** Agent 处理, **Then** Agent 直接调用 `analyze_dimension("cpu", time_range={5s, 10s})`
3. **Given** 用户输入"检查是否有 ANR", **When** Agent 处理, **Then** Agent 自动调用 ANR 相关 MCP 工具并返回结果
4. **Given** Agent 无法确定时间范围, **When** trace 包含多个不相关场景, **Then** Agent 向用户询问具体分析哪个阶段
5. **Given** Agent 分析完成, **When** 输出结果, **Then** 结果包含可追溯的分析链路（调用了哪些工具、时间范围、各工具返回了什么）

---

### Edge Cases

- MCP Server 连接断开或超时时，所有维度降级到引擎模式
- trace 文件损坏或不完整时，引擎的 TraceProcessor 报错后系统返回明确错误信息
- MCP 工具返回格式异常时（非预期 JSON 结构），降级到引擎且记录异常日志
- 多个 jank 帧时间窗口重叠时，MCP 工具的 time_range 参数处理
- CPU 分析维度因 MCP 不支持 time_range，始终使用引擎
- Agent 无法从 trace 元数据中判断场景阶段时，需向用户询问时间范围
- 用户指定的 time_range 超出 trace 实际时间范围时，返回明确错误

## Requirements *(mandatory)*

### Functional Requirements

#### 原子工具集

- **FR-001**: 系统 MUST 提供原子分析工具集（`get_trace_overview` / `detect_jank_frames` / `analyze_dimension` / `find_slices` / `execute_sql`），每个工具独立可调用，支持可选 time_range 参数
- **FR-001a**: 每个原子工具 MUST 在每个分析维度支持 MCP 优先 + 引擎降级的双通道执行
- **FR-002**: 系统 MUST 在 MCP 工具返回空数据（totalCount=0 或 success=false）时自动降级到引擎分析
- **FR-003**: 系统 MUST 在分析结果中标注每个维度的数据来源（"mcp"、"engine"、"degraded"）
- **FR-004**: 系统 MUST 支持通过配置切换分析模式（mcp_preferred / engine_only / mcp_only）

#### Agent 辅助数据准备工具

- **FR-001b**: 系统 MUST 提供 `pa_thread_state_summary(trace_path, process, time_range?)` 工具，返回主线程各状态（Running/S/R/D/R+）的耗时和占比，格式化为结构化输出
- **FR-001c**: 系统 MUST 提供 `pa_cpu_freq_analysis(trace_path, process, time_range?)` 工具，返回主线程运行的 CPU 核心分布和各核心频率统计（min/max/avg）
- **FR-001d**: 每个原子工具 MUST 支持 `compact=True` 参数，compact 模式返回摘要（关键指标 + 行数 + 样本），默认 `compact=False` 返回全量数据

#### MCP 集成

- **FR-005**: 系统 MUST 调用 `thread_contention_analyzer` 并传入 jank 时间窗口的 time_range
- **FR-006**: 系统 MUST 调用 `binder_transaction_profiler` 并传入 jank 时间窗口的 time_range
- **FR-007**: 系统 MUST 调用 `main_thread_hotspot_slices` 并传入 jank 时间窗口的 time_range
- **FR-008**: CPU 分析维度 MUST 使用引擎（MCP cpu_utilization_profiler 不支持 time_range）
- **FR-009**: 系统 MUST 调用 `cpu_utilization_profiler` 生成全 trace CPU 概览
- **FR-010**: 系统 MUST 支持调用 `find_slices` 和 `execute_sql_query` 用于按需灵活查询

#### 多场景扩展

- **FR-011**: 系统 MUST 支持 ANR 场景：通过 `detect_anrs` + `anr_root_cause_analyzer` 实现
- **FR-012**: 系统 MUST 支持内存场景：通过 `memory_leak_detector` + `heap_dominator_tree_analyzer` 实现
- **FR-013**: 系统 MUST 对不可用的场景（trace 缺少必要数据）返回明确的可用性检查结果

#### 结果压缩

- **FR-014**: 系统 MUST 生成结构化压缩摘要，包含：基础信息、卡顿概览、Top N 根因、维度健康度
- **FR-015**: 压缩摘要 MUST 可以作为独立的分析结论使用，无需回查全量报告
- **FR-016**: 压缩摘要 MUST 标注数据来源和分析完整度（是否有维度因降级或不可用而缺失）

#### 代码隔离

- **FR-017**: 现有引擎分析逻辑 MUST NOT 被删除或修改核心算法
- **FR-018**: 新旧代码路径 MUST 通过 feature flag 隔离，支持运行时切换
- **FR-019**: feature flag 的默认值 MUST 为 "mcp_preferred"（新行为），可配置回退到 "engine_only"（旧行为）
- **FR-019a**: 引擎 CLI 输出在检测到 `refresh_rate_switches` 时 MUST 增加 `mixed_refresh_rates: true`、`segments`（含各段 Hz 和 duration_s）和切换时间点信息

#### Agent 编排（P1 阶段）

- **FR-020**: 所有原子分析工具 MUST 注册为 agent_tools，供 Cursor LLM 直接调用
- **FR-020a**: Agent MUST 能通过 `get_trace_overview()` 查询 trace 元数据以确定分析场景和时间范围
- **FR-020b**: Agent 在无法从元数据确定时间范围时 MUST 向用户询问
- **FR-021**: Agent 层 MUST 输出可追溯的分析链路（工具调用序列 + 各步骤结果摘要）
- **FR-022**: Agent 层的输出 MUST 包含置信度标注（分析数据完整度对结论可靠性的影响）
- **FR-023**: 分析 SOP/Skills MUST 以文档形式存在于模块中，Agent 按需加载以指导编排策略

### Key Entities

- **AnalysisMode**: 分析模式枚举（mcp_preferred, engine_only, mcp_only）
- **DimensionResult**: 单个维度的分析结果，包含数据来源标注（source: mcp/engine/degraded/unavailable）
- **CompressedSummary**: 压缩摘要数据结构，包含基础信息、根因列表、健康度评级
- **AnalysisScenario**: 分析场景定义（jank, anr, memory, startup 等），包含所需 MCP 工具和引擎维度的映射
- **AnalysisToolkit**: 原子工具集管理器，暴露 `get_trace_overview` / `detect_jank_frames` / `analyze_dimension` 等工具，统一处理 MCP/引擎路由
- **ThreadStateSummary**: 主线程状态分布 Pydantic 模型（Running/S/R/D/R+ 各状态耗时和占比）
- **CpuFreqAnalysis**: CPU 核心分布与频率统计 Pydantic 模型（各核心 min/max/avg 频率）
- **AnalysisChainStep**: 分析链路单步记录（tool_name / input_params / output_summary / duration_ms / source）
- **AnalysisChainResult**: 完整分析链路（steps 列表 + 置信度 + 最终结论）

## Assumptions

- Perfetto MCP Server 在 Cursor IDE 环境中始终可用（作为 MCP 插件加载）
- MCP 工具的 time_range 参数格式为 `{"start_ms": number, "end_ms": number}`
- 引擎的 TraceProcessor 与 MCP 的 TraceProcessor 可能使用不同的实例（各自独立加载 trace）
- Agent 层由 Cursor LLM 承担，复用模块已有的 agent_tools 注册机制，不需要独立的 LLM 调用
- 压缩摘要的目标 token 量与 agent_chat 的上下文窗口限制相关，具体阈值待 agent_chat spec 确定
- 分析 SOP/Skills 为 Markdown 文档，Agent 按场景加载对应文档获取编排策略

## Clarifications

### C1: MCP 运行环境

**问题**：Perfetto MCP Server 是否需要支持非 Cursor 环境独立运行？
**决策**：当前仅在 Cursor IDE 中使用，后续再考虑独立运行支持。

### C2: Trace 加载策略

**问题**：引擎和 MCP 各自独立加载 trace 文件是否可接受？
**决策**：可接受，当前性能不是瓶颈。引擎和 MCP 使用各自独立的 TraceProcessor 实例。

### C3: 压缩摘要格式

**问题**：压缩摘要使用什么格式？
**决策**：使用结构化 JSON 格式，后续 agent_chat 兼容此格式。格式设计遵循 LLM 语义理解优化原则：

```json
{
  "trace_info": {
    "file": "string",
    "process": "string",
    "duration_s": "number",
    "refresh_rate_hz": "number",
    "frame_count": "number",
    "jank_count": "number",
    "avg_fps": "number"
  },
  "severity": "CRITICAL | HIGH | MEDIUM | LOW",
  "root_causes": [
    {
      "rank": "number",
      "cause": "一句话根因描述",
      "evidence": "支撑证据",
      "severity": "CRITICAL | HIGH | MEDIUM | LOW",
      "dimension": "维度名称"
    }
  ],
  "health_summary": {
    "<dimension>": {
      "status": "OK | WARNING | CRITICAL | UNAVAILABLE",
      "note": "一行说明"
    }
  },
  "data_completeness": {
    "degraded_dimensions": ["降级的维度列表"],
    "mcp_source": ["使用 MCP 的维度"],
    "engine_source": ["使用引擎的维度"]
  }
}
```

**设计原则**：扁平化关键信息、根因按严重度排序且自带证据、健康度一行总结、数据完整度透明。

### C4: 编排架构模式

**问题**：分析流程是固定流水线（一键全量维度）还是 Agent 驱动编排（按需调用原子工具）？
**决策**：取消固定流水线模式。模块提供原子分析工具集（MCP/引擎的原子能力），所有维度和时间范围由 Agent（Cursor LLM）根据 SOP/Skills 动态编排。原因：
1. 实际 trace 常包含多个不相关场景（如冷启动 + 动画），全量分析会引入大量噪声
2. Agent 需要理解用户意图后选择性分析，而非盲目跑全量
3. SOP/Skills 以文档形式持续积累分析经验，Agent 按场景加载

**影响**：US1 从"一键分析"改为"原子工具集"，US5 从 P3 提升到 P1

### C5: 时间范围确定策略

**问题**：分析的时间范围由谁决定？
**决策**：三种模式并存：
1. **Agent 自动确定**（默认）：Agent 调用 `get_trace_overview()` 理解 trace 内容后，结合用户意图自动确定时间范围
2. **用户显式指定**：用户直接给出时间范围（如"分析 5s 到 10s"）
3. **Agent 询问用户**：Agent 无法判断时主动询问用户

### Session 2026-04-01

- Q: Agent 编排分析时，线程状态分布、CPU 频率等重复性数据计算应如何处理？ → A: 新增 `pa_thread_state_summary` 和 `pa_cpu_freq_analysis` 原子工具，封装 SQL 查询 + 格式化
- Q: 原子工具返回结果的 compact 模式如何设计？ → A: 每个原子工具增加 `compact=True` 参数，compact 返回摘要 + 行数 + 样本，全量可选
- Q: 引擎检测到混合刷新率时应如何处理？ → A: 引擎输出增加 `mixed_refresh_rates` 字段和 `segments` 详情，同时提供刷新率切换时间点
- Q: 知识文档（SOP/patterns/cases）是否纳入 spec 管理？ → A: 知识文档不纳入 spec（通过 Skill 管理流程维护），封装为工具的代码开发纳入 spec
- Q: 新增原子工具和引擎改进归属哪个 User Story？ → A: 新原子工具归 US1（原子工具集扩展），引擎输出改进归 US3（Feature Flag）

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 对同一 trace 文件，混合模式的分析覆盖维度 ≥ 纯引擎模式（MCP 提供的 main_thread_hotspot 等为增量）
- **SC-002**: 当 MCP 工具不可用时，降级到引擎的行为与改造前一致（回归测试通过率 100%）
- **SC-003**: 压缩摘要的信息量覆盖全量报告中所有"根因级"发现的 ≥ 95%
- **SC-004**: 压缩摘要字符数 ≤ 全量报告的 30%
- **SC-005**: feature flag 切换后，两种模式均在 5 秒内完成相同 trace 的分析（22MB 级别）
- **SC-006**: 新增 ANR/Memory 场景在对应 trace 上成功返回分析结果
- **SC-007**: 每个原子工具独立注册为 agent_tool，Agent 可通过自然语言触发正确的工具调用链
- **SC-008**: Agent 在 trace 包含多场景时能通过 `get_trace_overview()` 正确识别并仅分析用户关注的场景
