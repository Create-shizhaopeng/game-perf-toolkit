# Implementation Plan: Perfetto 分析 Agent 化 — MCP 混合架构

**Branch**: `005-agent-mcp-hybrid` | **Date**: 2026-03-31 | **Spec**: [spec.md](spec.md)

## 目录

- [Summary](#summary)
- [Technical Context](#technical-context)
- [Architecture Design](#architecture-design)
  - [核心分层](#核心分层)
  - [原子工具集](#原子工具集)
  - [MCP 集成层](#mcp-集成层)
  - [降级策略](#降级策略)
  - [压缩摘要生成](#压缩摘要生成)
  - [Feature Flag 机制](#feature-flag-机制)
  - [Agent 编排集成](#agent-编排集成)
- [Project Structure](#project-structure)
- [实现阶段](#实现阶段)
- [关键设计决策](#关键设计决策)
- [风险与缓解](#风险与缓解)

## Summary

对 perfetto_analysis 模块进行 Agent 化改造：取消固定全量分析流水线，改为暴露原子分析工具集（每个维度独立可调用，支持 time_range），由 Agent（Cursor LLM）根据用户意图和 SOP/Skills 动态编排。在 MCP/引擎双通道基础上实现降级能力，增加分析结果压缩输出。现有引擎代码通过 feature flag 隔离，不删除不修改核心算法。

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: perfetto (TraceProcessor), Pydantic, pluggy; MCP 通过外部进程调用  
**Storage**: SQLite (module DB) + JSON (结果文件)  
**Testing**: pytest + unittest.mock  
**Target Platform**: Windows 10+ (Cursor IDE 环境)  
**Project Type**: 插件模块（toolkit 框架内）  
**Performance Goals**: 22MB trace 单维度分析 < 3s  
**Constraints**: 现有引擎代码不可修改核心算法；MCP 调用可能超时；Agent 编排由 Cursor LLM 承担

## Architecture Design

### 核心分层

```text
┌─────────────────────────────────────────┐
│          Cursor LLM (Agent)             │  编排层（Cursor 内置）
│  理解意图 → 加载 SOP → 编排工具调用     │
├─────────────────────────────────────────┤
│         agent_tools 注册层              │  plugin.py 注册原子工具
├─────────────────────────────────────────┤
│         PerfettoAnalysisService         │  服务层（扩展新方法）
│  analyze() | get_trace_overview()       │
│  detect_jank_frames() | analyze_dim()   │
├─────────────────────────────────────────┤
│         AnalysisToolkit                 │  新增：原子工具集
│  ┌──────────┐  ┌──────────┐            │
│  │ MCP 通道  │  │ 引擎通道  │            │
│  │ (优先)    │  │ (降级)    │            │
│  └──────────┘  └──────────┘            │
├─────────────────────────────────────────┤
│         ResultCompressor                │  新增：结果压缩器
│  工具结果集合 → CompressedSummary       │
├─────────────────────────────────────────┤
│         FeatureFlagManager              │  新增：Feature Flag 管理
│  mcp_preferred / engine_only / mcp_only │
└─────────────────────────────────────────┘
```

### 原子工具集

`AnalysisToolkit` 暴露以下独立可调用的工具，每个工具支持可选 `time_range` 参数：

```text
AnalysisToolkit
├── get_trace_overview(trace_path, process?) → TraceOverview
│   返回 trace 元数据：duration、processes、frame_count、场景阶段列表
│
├── detect_jank_frames(trace_path, process, time_range?) → list[JankFrame]
│   使用引擎的 VSync/Buffer 方式检测卡顿帧，返回帧列表（含时间窗口）
│
├── analyze_dimension(trace_path, process, dimension, time_range?) → DimensionResult
│   对指定维度执行分析（MCP/引擎路由），返回带 source 标注的结果
│   dimension: cpu / thread / binder / hotspot / io / gc / gpu / sf / input / lock
│
├── get_cpu_overview(trace_path, process) → dict | None
│   调用 MCP cpu_utilization_profiler，返回全 trace CPU 概览
│
├── find_slices(trace_path, pattern, process?) → dict | None
│   调用 MCP find_slices，按名称模式搜索 slice
│
└── execute_sql(trace_path, sql) → dict | None
    调用 MCP execute_sql_query，执行任意 SQL
```

**设计原则**：
- 每个工具独立可调用，无隐含依赖关系
- Agent 自由组合工具以实现不同分析流程
- 现有 `analyze()` 保留不变（调用引擎的全量流水线），`analyze_hybrid()` 不再需要

### MCP 集成层

MCP 工具通过 Cursor IDE 的 MCP 协议调用。模块需要一个 **MCP Client 抽象层** 封装调用逻辑。

```text
McpAnalysisClient
├── analyze_thread_contention(trace_path, process, time_range) → dict | None
├── analyze_binder(trace_path, process, time_range) → dict | None
├── get_main_thread_hotspots(trace_path, process, time_range) → dict | None
├── get_cpu_utilization(trace_path, process) → dict | None
├── detect_anrs(trace_path, process) → dict | None
├── detect_memory_leaks(trace_path, process) → dict | None
├── find_slices(trace_path, pattern, process) → dict | None
└── execute_sql(trace_path, sql) → dict | None
```

每个方法：
- 成功返回结构化 dict
- 失败/超时/空数据返回 None（触发降级）
- 自动处理 MCP 连接异常

### 降级策略

```text
对 analyze_dimension() 调用：
1. 检查 FeatureFlag
   ├── engine_only → 直接使用引擎
   ├── mcp_only → 仅使用 MCP（失败标记 UNAVAILABLE）
   └── mcp_preferred → 进入步骤 2
2. 调用 MCP 工具
   ├── 返回有效数据 → 标记 source="mcp"
   └── 返回 None → 进入步骤 3
3. 降级到引擎
   ├── 引擎分析成功 → 标记 source="degraded"
   └── 引擎也失败 → 标记 source="unavailable"
```

**维度级路由表**（基于 Demo 实测结果）：

| 维度 | MCP 工具 | 支持 time_range | 默认策略 |
|------|---------|----------------|---------|
| cpu | engine cpu_analysis.py | N/A | engine_only（MCP 不支持 time_range） |
| thread | thread_contention_analyzer | ✅ | mcp_preferred |
| binder | binder_transaction_profiler | ✅ | mcp_preferred |
| hotspot | main_thread_hotspot_slices | ✅ | mcp_only（引擎无此能力） |
| io | engine io_analysis.py | N/A | engine_only（MCP 无等效工具） |
| gc | engine gc_analysis.py | N/A | engine_only |
| gpu | engine gpu_analysis.py | N/A | engine_only |
| sf | engine sf_analysis.py | N/A | engine_only |
| input | engine input_analysis.py | N/A | engine_only |
| lock | engine lock_analysis.py | N/A | engine_only |
| summary | engine summary_analysis.py | N/A | engine_only |
| cpu_global | cpu_utilization_profiler | ❌ | mcp_only（全 trace 概览） |

### 压缩摘要生成

`ResultCompressor` 从一组原子工具的分析结果中提取关键信息：

**输入**：一组 `DimensionResult` + TraceOverview + 可选的 jank 帧列表  
**输出**：`CompressedSummary` (JSON，参见 spec Clarifications C3)

**提取逻辑**：
1. `trace_info` — 从 TraceOverview 直接提取
2. `severity` — 基于 jank_count 和 max_jank_num 计算
3. `root_causes` — 遍历各维度结果，按严重度排序，取 Top N
4. `health_summary` — 每个维度生成 OK/WARNING/CRITICAL 状态
5. `data_completeness` — 统计各维度的数据来源标注

### Feature Flag 机制

扩展现有 `AnalysisConfig` (Pydantic model)：

```python
class AnalysisConfig(BaseModel):
    # ... 现有字段 ...
    analysis_mode: Literal["mcp_preferred", "engine_only", "mcp_only"] = "mcp_preferred"
    dimension_overrides: dict[str, str] = {}  # 维度级覆盖，如 {"cpu": "engine_only"}
    mcp_timeout_ms: int = 10000  # MCP 调用超时
```

配置存储在 `data/config.json`，支持运行时通过 service API 修改。

### Agent 编排集成

Agent 编排由 Cursor LLM 承担，模块侧需要：

1. **agent_tools 注册**：将所有原子工具注册为 agent_tools，供 LLM 直接调用
2. **SOP 文档**：为每个分析场景（卡顿、ANR、Memory）编写 SOP 文档
3. **Skill 定义**：创建 Cursor Skill 文件指导 Agent 的分析编排策略

```text
Agent 编排流程（由 Cursor LLM 执行）：
1. 用户输入分析请求（自然语言）
2. Agent 加载对应场景的 SOP/Skill
3. Agent 调用 get_trace_overview() 理解 trace 内容
4. Agent 根据意图 + 元数据确定时间范围
   ├── 可自动确定 → 直接使用
   └── 无法确定 → 向用户询问
5. Agent 按需调用 detect_jank_frames() + analyze_dimension() 等工具
6. Agent 调用 compress_results() 生成摘要
7. Agent 基于摘要推理结论并输出
```

**SOP 文档结构**（存放在 `modules/perfetto_analysis/docs/sop/`）：

```text
docs/sop/
├── jank-analysis.md        # 卡顿分析 SOP
├── anr-analysis.md         # ANR 分析 SOP
├── memory-analysis.md      # 内存分析 SOP
└── general-analysis.md     # 通用分析 SOP（场景不明时的引导）
```

每个 SOP 包含：分析目标、前置检查、工具调用顺序、结果解读指引、常见模式识别。

## Project Structure

### 新增文件

```text
modules/perfetto_analysis/src/
├── mcp_client.py          # MCP 工具调用抽象层
├── analysis_toolkit.py    # 原子工具集（替代 hybrid_orchestrator）
├── result_compressor.py   # 结果压缩器
└── analysis_mode.py       # Feature Flag + 降级逻辑

modules/perfetto_analysis/docs/sop/
├── jank-analysis.md       # 卡顿分析 SOP
├── anr-analysis.md        # ANR 分析 SOP
├── memory-analysis.md     # 内存分析 SOP
└── general-analysis.md    # 通用分析 SOP

modules/perfetto_analysis/tests/
├── test_mcp_client.py     # MCP 调用 mock 测试
├── test_toolkit.py        # 原子工具集测试
├── test_compressor.py     # 压缩器测试
└── data/
    └── launcher慢划*.perfetto-trace  # 已有测试 trace
```

### 修改文件（最小改动）

```text
modules/perfetto_analysis/src/
├── service.py             # 增加原子工具入口方法（analyze() 不变）
├── models.py              # 扩展 AnalysisConfig + 新增模型
├── plugin.py              # 注册原子 agent_tools
├── cli_commands.py        # 增加 --mode 参数
└── data/config.json       # 增加 analysis_mode 配置
```

## 实现阶段

### Phase 1: 基础设施（P1 核心）

1. **models.py 扩展** — AnalysisMode 枚举、DimensionResult 模型、CompressedSummary 模型、TraceOverview 模型
2. **mcp_client.py** — MCP 调用抽象层（含超时和异常处理）
3. **analysis_mode.py** — Feature Flag 读取和维度级路由逻辑

### Phase 2: 原子工具集（P1 核心）

4. **analysis_toolkit.py** — AnalysisToolkit 类，暴露所有原子工具方法
5. **service.py 集成** — 新增 `get_trace_overview()` / `detect_jank_frames()` / `analyze_dimension()` 等公共方法
6. **降级逻辑** — 每个 analyze_dimension 调用执行 MCP/引擎路由 + 降级

### Phase 3: 结果压缩（P1 核心）

7. **result_compressor.py** — 工具结果集合 → CompressedSummary
8. **severity 计算逻辑** — 基于 jank_count、jank_num、各维度异常阈值
9. **root_cause 提取逻辑** — 遍历维度结果提取关键发现

### Phase 4: Agent 编排集成（P1 核心）

10. **plugin.py** — 注册所有原子工具为 agent_tools
11. **SOP 文档** — 编写卡顿分析、通用分析 SOP
12. **service.py** — 新增 `compress_results()` 公共方法供 Agent 按需调用

### Phase 5: Feature Flag + CLI（P2）

13. **CLI 参数** — `--mode mcp_preferred|engine_only|mcp_only`
14. **运行时切换** — `set_analysis_mode()` / `get_analysis_mode()` API
15. **config 子命令** — `analysis config show/set`

### Phase 6: 多场景扩展（P2）

16. **ANR 场景** — mcp_client 中 ANR 相关方法 + service 入口 + SOP
17. **Memory 场景** — mcp_client 中内存分析方法 + service 入口 + SOP
18. **场景可用性检查** — trace 元数据检测 + 友好提示

### Phase 7: 测试与验证

19. **单元测试** — mcp_client mock、toolkit 降级、compressor
20. **集成测试** — 使用真实 trace 端到端验证
21. **回归测试** — engine_only 模式与改造前行为一致

## 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 编排模式 | Agent 驱动（Cursor LLM） | 取代固定流水线，Agent 按意图选择性分析，减少噪声 |
| 工具集设计 | 原子工具独立可调用 | 每个工具无隐含依赖，Agent 自由组合 |
| MCP 调用方式 | 模块内封装 McpAnalysisClient | 隔离 MCP 依赖，便于 mock 测试 |
| 降级触发条件 | MCP 返回 None / totalCount=0 / 超时 | 基于 demo 实测的失败模式 |
| Feature Flag 粒度 | 全局模式 + 维度级覆盖 | 灵活性与简洁性平衡 |
| 压缩摘要格式 | JSON | LLM 语义理解效率最高 |
| 现有代码隔离 | analyze() 不变，新增原子工具方法 | 零风险回归 |
| 分析策略传递 | SOP 文档 + Cursor Skills | 策略与代码解耦，持续积累可维护 |

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| MCP Server 不可用 | 所有 MCP 维度降级 | 全局降级到 engine_only，记录日志 |
| MCP 调用延迟高 | 分析总耗时增加 | 设置超时（默认 10s），超时即降级 |
| MCP 输出格式变更 | 解析失败 | mcp_client 做 schema 验证，异常时降级 |
| 压缩摘要信息丢失 | agent_chat 缺少关键上下文 | SC-003 要求覆盖 ≥ 95% 根因级发现 |
| Agent 编排不稳定 | 工具调用链不一致 | SOP 文档提供标准化分析步骤，减少 LLM 随意性 |
| SOP 维护成本 | 文档与代码脱节 | SOP 作为 spec 验收项，每次改动同步更新 |
