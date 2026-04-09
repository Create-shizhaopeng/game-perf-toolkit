# Perfetto Analysis 模块 — 分析子系统详细设计

## 目录

- [文档目的](#文档目的)
- [系统全景](#系统全景)
  - [分层架构](#分层架构)
  - [数据流](#数据流)
- [编排层 — AnalysisOrchestrator](#编排层--analysisorchestrator)
  - [职责](#编排层职责)
  - [生命周期](#生命周期)
  - [单条分析流程](#单条分析流程)
  - [批量分析流程](#批量分析流程)
  - [中止机制](#中止机制)
- [Agent 层 — Pydantic AI Agent](#agent-层--pydantic-ai-agent)
  - [MainAgent — 场景路由](#mainagent--场景路由)
  - [SubAgent — 工具驱动分析](#subagent--工具驱动分析)
  - [ReviewAgent — 交叉评审](#reviewagent--交叉评审)
  - [Agent 与 LLM 的交互模型](#agent-与-llm-的交互模型)
- [工具层 — pa_* 工具集](#工具层--pa-工具集)
  - [工具清单](#工具清单)
  - [ToolReturn 机制](#toolreturn-机制)
  - [工具压缩策略](#工具压缩策略)
  - [流式输出](#流式输出)
- [服务层 — PerfettoAnalysisService](#服务层--perfettoanalysisservice)
  - [职责](#服务层职责)
  - [公共 API](#公共-api)
  - [AnalysisToolkit](#analysistoolkit)
  - [MCP/Engine 路由](#mcpengine-路由)
- [引擎层 — engine/](#引擎层--engine)
  - [解析器 parser.py](#解析器-parserpy)
  - [分析器注册表](#分析器注册表)
  - [10 个分析维度](#10-个分析维度)
  - [存储层 storage.py](#存储层-storagepy)
- [SOP 知识体系](#sop-知识体系)
  - [SOP 目录结构](#sop-目录结构)
  - [场景-SOP 映射](#场景-sop-映射)
  - [加载机制](#加载机制)
- [上下文预算管理](#上下文预算管理)
  - [预算控制策略](#预算控制策略)
  - [ResultCompressor](#resultcompressor)
  - [ToolReturn 压缩流程](#toolreturn-压缩流程)
- [降级与容错](#降级与容错)
  - [降级策略矩阵](#降级策略矩阵)
  - [报告完成标签](#报告完成标签)
- [报告生成](#报告生成)
  - [报告结构](#报告结构)
  - [Jinja2 模板](#jinja2-模板)
  - [Fallback 内嵌模板](#fallback-内嵌模板)
- [辅助子系统](#辅助子系统)
  - [PackageMappingDB](#packagemappingdb)
  - [FeatureFlagManager](#featureflagmanager)
- [数据模型总览](#数据模型总览)
  - [Agent 层模型 (Pydantic)](#agent-层模型-pydantic)
  - [服务层模型](#服务层模型)
- [已知问题与不一致](#已知问题与不一致)
  - [严重问题 (HIGH)](#严重问题-high)
  - [中等问题 (MEDIUM)](#中等问题-medium)
  - [低优先级 (LOW)](#低优先级-low)
- [附录 — 文件依赖关系](#附录--文件依赖关系)

---

## 文档目的

本文档对 `modules/perfetto_analysis/` 模块的**分析子系统**做完整的架构和实现细节记录。覆盖从 GUI/CLI 触发分析到最终 HTML 报告生成的全链路，包含每一层的设计意图、接口契约、数据流、降级策略和已知问题。

**阅读对象**：开发者在修改分析逻辑、扩展分析维度、优化 LLM 集成前应阅读此文档。

**文档版本**：2026-04-09，基于 `dev` 分支最新代码。

---

## 系统全景

### 分层架构

```
┌───────────────────────────────────────────────────────────┐
│                     GUI / CLI 入口                         │
│  gui_tab.py (AnalysisWorker QThread)  |  cli_commands.py  │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│              编排层 (Orchestrator)                         │
│  agent/orchestrator.py                                    │
│  管理 MainAgent → SubAgent × N → ReviewAgent 生命周期     │
│  异步 (asyncio)，超时/中止/降级控制                        │
└───────────────────────┬───────────────────────────────────┘
                        │ 创建 & 运行 Pydantic AI Agent
                        ▼
┌───────────────────────────────────────────────────────────┐
│              Agent 层 (Pydantic AI)                        │
│  agent/agents.py — Agent 工厂                              │
│  agent/tools.py  — 9 个 pa_* 工具 (ToolReturn)            │
│  agent/prompts.py — SOP 加载                               │
└───────────────────────┬───────────────────────────────────┘
                        │ 工具调用
                        ▼
┌───────────────────────────────────────────────────────────┐
│              服务层 (Service)                               │
│  service.py — 同步 API 门面                                │
│  analysis_toolkit.py — 原子分析 + MCP/Engine 路由          │
│  analysis_mode.py — 维度级路由策略                          │
│  result_compressor.py — 结果压缩                           │
└───────────────────────┬───────────────────────────────────┘
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
┌──────────────────┐  ┌──────────────────┐
│   引擎层 Engine   │  │  MCP Client      │
│   engine/*.py     │  │  mcp_client.py   │
│   本地解析分析     │  │  (桩实现)         │
│   20 个文件       │  │  全部返回 None    │
└──────────────────┘  └──────────────────┘
```

### 数据流

```
用户请求 (trace_path + intent)
    │
    ▼
Orchestrator.analyze_single()
    │
    ├─→ MainAgent.run(prompt)
    │     输入: 用户意图 + trace 路径 + 进程名 (纯文本)
    │     输出: AnalysisRouting { scene, sop_name, process_name, reasoning }
    │
    ├─→ load_sop(scene) → SOP Markdown 内容
    │
    ├─→ SubAgent.run(prompt, tools, usage_limits)
    │     │
    │     ├─ LLM 选择工具 → pa_trace_overview(trace) → ToolReturn
    │     ├─ LLM 选择工具 → pa_detect_jank(trace) → ToolReturn
    │     ├─ LLM 选择工具 → pa_analyze_dimension(trace, "cpu") → ToolReturn
    │     ├─ ... (由 LLM 自主决策调用顺序和次数)
    │     └─ LLM 输出结论文本
    │
    ├─→ generate_html_report()
    │     │
    │     ├─ 保存 raw_data/*.json
    │     └─ 渲染 report.html
    │
    └─→ AnalysisReport { task_id, html_path, summary, ... }
```

---

## 编排层 — AnalysisOrchestrator

**文件**: `src/agent/orchestrator.py`

### 编排层职责

`AnalysisOrchestrator` 是一个**纯 Python 编排器**（非 Agent），管理 Pydantic AI Agent 实例的创建、运行和结果收集。主要职责：

1. 接收分析请求，创建 task_id
2. 协调 MainAgent → SubAgent → ReviewAgent 的执行顺序
3. 管理超时 (`asyncio.wait_for`)、中止 (`_abort_flag`)、异常降级
4. 生成 HTML 报告并返回 `AnalysisReport`
5. 记录 token 消耗和包名映射

### 生命周期

```python
orchestrator = AnalysisOrchestrator(
    llm_manager=llm_manager,      # 全局 LLMManager (QObject)
    pa_service=pa_service,         # PerfettoAnalysisService 实例
    config=AnalysisConfig(),       # 可选配置
    output_base="",                # 报告输出根目录 (自动检测)
    package_db=package_db,         # 可选 PackageMappingDB
)
```

**创建时机**：`plugin.py` 的 `on_startup()` 中，当 `context` 中存在 `llm_manager` 时创建。

### 单条分析流程

```python
async def analyze_single(
    trace_path: str,
    user_intent: str,
    process_name: str = "",
    on_status: StatusCallback | None = None,   # (task_id, status, detail)
    on_stream: StreamCallback | None = None,   # (task_id, role, content)
) -> AnalysisReport
```

**执行步骤**：

| 步骤 | 状态 | 调用 | 超时 |
|------|------|------|------|
| 1. 场景路由 | ROUTING | `_route_scene()` → MainAgent | `analysis_timeout_sec` (默认 300s) |
| 2. 工具分析 | ANALYZING | `_run_sub_agent()` → SubAgent | `analysis_timeout_sec` |
| 3. 生成报告 | REPORTING | `_generate_report()` | 无额外超时 |
| 4. 后处理 | COMPLETED | `_record_tokens()` + `_learn_package()` | — |

每个步骤前检查 `_abort_flag`，如果为 True 则返回空 `AnalysisReport(task_id=task_id)`。

### 批量分析流程

```python
async def analyze_batch(
    tasks: list[AnalysisTask],
    on_status: StatusCallback | None = None,
    on_stream: StreamCallback | None = None,
) -> list[AnalysisReport]
```

- `parallel_count <= 1`：串行逐个 `analyze_single`
- `parallel_count > 1`：按 `parallel_count` 分批，使用 `asyncio.gather(..., return_exceptions=True)` 并行执行
- **Review**：仅当 `len(reports) > 1` 且未中止时触发 `_run_review()`

### 中止机制

- `request_abort()`：设置 `_abort_flag = True`
- `reset_abort()`：重置标志
- 各阶段主动检查 `_abort_flag`，一旦为 True 立即返回
- **限制**：已提交给 Pydantic AI 的 `agent.run()` 调用无法被提前中断，需等待其自然结束或超时

---

## Agent 层 — Pydantic AI Agent

**文件**: `src/agent/agents.py`

### MainAgent — 场景路由

```python
def create_main_agent(model: Any) -> Agent
```

| 属性 | 值 |
|------|-----|
| output_type | `AnalysisRouting` (结构化输出) |
| tools | **无** |
| instructions | "根据用户意图判断分析场景。场景: jank/anr/memory/startup/cpu/general。输出 scene, sop_name, process_name, reasoning。" |

**输入 prompt** (由 orchestrator 构建)：

```
用户意图: {user_intent}
Trace 路径: {trace_path}
目标进程: {process_name or '未指定'}
请分析用户意图并路由到合适的分析场景。
```

**输出**：`AnalysisRouting` Pydantic 模型

| 字段 | 说明 |
|------|------|
| `scene` | 分析场景标识: jank/anr/memory/startup/cpu/general |
| `sop_name` | SOP 文件名，优先用于 SOP 加载（兜底用 scene 查表） |
| `process_name` | 检测到的目标进程 |
| `reasoning` | 路由理由 |

**设计说明**：MainAgent 无工具，纯文本路由。orchestrator 预先调用 `get_trace_overview()` 获取 trace 元信息（进程列表、帧数、时长等），拼入 prompt 辅助路由判断。

### SubAgent — 工具驱动分析

```python
def create_sub_agent(
    model: Any,
    sop_content: str,
    pa_service: Any,
    compressor: Any = None,
) -> Agent
```

| 属性 | 值 |
|------|-----|
| output_type | 无 (自由文本) |
| tools | 9 个 `pa_*` 工具函数 |
| instructions | 基础指令 + 完整 SOP 内容 (或"自主判断"提示) |
| usage_limits | `request_limit=100` |

**Instructions 构成**：

```
"你是 Perfetto trace 分析专家。中文输出。"
+ "\n\n" + sop_content (完整 SOP Markdown)    // 或 "请根据 trace 数据自主判断分析路径。"
```

**Prompt** (由 orchestrator 构建)：

```
请分析以下 trace，并输出**人类可读的中文分析报告**:
- Trace 路径: {trace_path}
- 目标进程: {process_name or '自动检测'}
- 分析场景: {scene}

报告格式要求:
1. **问题概述**: 简要描述发现的问题
2. **根因分析**: 列出每个根因的详细分析和证据
3. **关键数据**: 提供支撑结论的量化数据
4. **优化建议**: 给出具体可操作的优化方案

注意：调用工具后请尽快归纳结论，避免过多重复调用。
```

**返回值提取**：

```python
output = result.output if hasattr(result, "output") else str(result)
conclusion = str(output) if output else "分析完成，未生成结论。"
```

### ReviewAgent — 交叉评审

```python
def create_review_agent(model: Any) -> Agent
```

| 属性 | 值 |
|------|-----|
| output_type | 无 (自由文本) |
| tools | 无 |
| instructions | 交叉评审指令 (一致性检查、共性识别、矛盾判断) |

**触发条件**：批量分析 `len(reports) > 1` 且未中止。

**输入**：各报告的 `summary` 拼接为 "## Trace 1\n{summary}\n\n## Trace 2\n{summary}..."

### Agent 与 LLM 的交互模型

```
Orchestrator
    │
    ├─ _get_model() → LiteLLMModel
    │    ├─ 从 llm_manager.get_config() 获取 provider/model_name/api_key
    │    ├─ _to_litellm_model() 构造 LiteLLM 路由名 (如 "zai/glm-4-plus")
    │    └─ 返回 LiteLLMModel 实例 (或 None 导致降级)
    │
    └─ 传入 Agent() 构造函数
         └─ Pydantic AI 通过 LiteLLM → 实际 LLM Provider API
```

**模型路由映射** (`_to_litellm_model`)：

```python
prefix_map = {"glm": "zai/", "claude": ""}
```

---

## 工具层 — pa_* 工具集

**文件**: `src/agent/tools.py`

### 工具清单

| # | 工具名 | 参数 | 实际调用 | 说明 |
|---|--------|------|----------|------|
| 1 | `pa_trace_overview` | trace_path, process_name="" | `service.get_trace_overview()` | trace 元数据 |
| 2 | `pa_detect_jank` | trace_path, process_name="" | `service.parse_only()` | 丢帧检测 |
| 3 | `pa_analyze_dimension` | trace_path, dimension, process_name="", compact=True | `service.analyze_dimensions([dimension])` | 单维度分析 |
| 4 | `pa_list_dimensions` | (无) | 硬编码 10 维度 | 列出维度 |
| 5 | `pa_get_history` | limit=20 | `service.get_analysis_history()[:limit]` | 分析历史 |
| 6 | `pa_find_slices` | trace_path, slice_name, process_name="" | `service.find_slices_tool()` | 搜索 slice |
| 7 | `pa_execute_sql` | trace_path, sql | `service.execute_sql_tool()` | SQL 查询 |
| 8 | `pa_analyze_anr` | trace_path, process_name="" | `service.analyze_anr()` / 降级 thread+binder+lock | ANR 分析 |
| 9 | `pa_analyze_memory` | trace_path, process_name="" | `service.analyze_memory()` / 降级 gc | 内存分析 |

### ToolReturn 机制

所有工具（`pa_list_dimensions` 除外）通过 `_make_tool_return()` 统一返回 `ToolReturn` 对象：

```python
ToolReturn(
    return_value=compressed_summary,   # 给 LLM 的压缩文本 (≤300 token)
    metadata={"raw": raw_data, "tool_name": name},  # 原始数据 (不送 LLM)
)
```

**关键设计**：
- `return_value` 是 LLM 在后续对话中看到的工具返回值 —— 经过 `ResultCompressor.compress_tool_output()` 压缩
- `metadata` 保留完整原始数据 —— 存在于 Pydantic AI 运行时，不计入 LLM 上下文
- 错误通过 `_make_error_return()` 返回：`return_value=f"错误: {error}"`

### 工具压缩策略

| 工具 | 策略名 | 压缩逻辑 |
|------|--------|----------|
| `pa_detect_jank` | `_compress_jank` | 按 jank_num 排序 → Top-5 严重帧 + 统计摘要 (总数/平均/最大耗时) |
| `pa_analyze_dimension` | `_compress_dimension` | 提取 issues 列表 → 每维度前 3 个问题描述 (≤100字) |
| 其他工具 | `_compress_generic` | dict → JSON 截断; list → "共 N 项。前 3 项: ..."; str → 直接截断 |

**Token 预算**：默认 300 token，换算为 `300 × 2.5 = 750 字符` 硬截断。

### 流式输出

```python
_stream_callback: Callable | None  # 全局回调
set_tool_stream_callback(callback)  # 设置
_notify_tool_call(tool_name, args)  # 工具调用时：🔧 调用 pa_xxx(...)
_notify_tool_result(tool_name, result)  # 工具完成时：✅/❌ pa_xxx 返回/错误
```

---

## 服务层 — PerfettoAnalysisService

**文件**: `src/service.py`

### 服务层职责

同步 API 门面，供 GUI、CLI、Agent 工具调用。封装 engine 解析能力和 MCP 客户端，管理分析配置和历史记录。

### 公共 API

**管道操作**：

| 方法 | 说明 |
|------|------|
| `analyze(trace_path, process_name, on_progress)` | 完整 Phase1 + Phase2 + 报告 |
| `parse_only(trace_path, process_name, on_progress)` | 仅 Phase1 丢帧解析 |
| `analyze_dimensions(trace_path, process_name, dimensions, on_progress)` | 按维度分析 |
| `list_dimensions()` | 返回可用维度列表 |

**原子工具** (Agent 工具层直接调用)：

| 方法 | 说明 |
|------|------|
| `get_trace_overview(trace_path, process)` → `TraceOverview` | trace 元数据 |
| `detect_jank_frames(trace_path, process, time_range)` | 丢帧检测 |
| `analyze_dimension(trace_path, process, dimension, time_range)` → `DimensionResult` | 单维度 |
| `get_cpu_overview(trace_path, process)` | CPU 概览 (MCP) |
| `find_slices_tool(trace_path, pattern, process, compact)` | slice 搜索 |
| `execute_sql_tool(trace_path, sql, compact)` | SQL 查询 |
| `thread_state_summary(trace_path, process, time_range, compact)` | 线程状态 |
| `cpu_freq_analysis(trace_path, process, time_range, compact)` | CPU 频率 |
| `analyze_anr(trace_path, process)` | ANR 分析 |
| `analyze_memory(trace_path, process)` | 内存分析 |
| `compress_results(trace_overview, dimension_results, jank_frames)` → `CompressedSummary` | 结果压缩 |

**历史管理**：

| 方法 | 说明 |
|------|------|
| `get_analysis_history()` | 查询分析记录 (DB + 磁盘扫描合并) |
| `delete_analysis_record(task_id, trace_path, report_dir)` | 删除记录 |
| `export_report(trace_path, output_dir, on_progress)` | 导出已有报告 |
| `regenerate_report(trace_path, on_progress)` | 重新生成报告 (不重新分析) |

### AnalysisToolkit

**文件**: `src/analysis_toolkit.py`

在 `service.py` 中通过 `_get_toolkit()` 懒加载创建。封装原子分析能力，核心职责是 **MCP vs Engine 路由**。

```python
class AnalysisToolkit:
    def __init__(self, config, mcp_client=None, flag_manager=None): ...

    def get_trace_overview(self, trace_path, process=None) -> TraceOverview: ...
    def detect_jank_frames(self, trace_path, process, time_range=None) -> list[dict]: ...
    def analyze_dimension(self, trace_path, process, dimension, time_range=None) -> DimensionResult: ...
    def find_slices(self, trace_path, pattern, process=None, compact=False) -> dict | None: ...
    def execute_sql(self, trace_path, sql, compact=False) -> dict | None: ...
    # ... 更多方法
```

### MCP/Engine 路由

**文件**: `src/analysis_mode.py`

```
AnalysisConfig.analysis_mode (全局: mcp_preferred / engine_only / mcp_only)
    │
    ▼
FeatureFlagManager.get_mode_for_dimension(dimension)
    │
    ├─ 检查 config.dimension_overrides[dimension] → 有则用
    ├─ 查 DIMENSION_ROUTING[dimension].default_mode
    │    ├─ ENGINE_ONLY / MCP_ONLY → 直接使用
    │    └─ MCP_PREFERRED → 用全局 mode
    └─ 兜底 → 全局 mode
```

**DIMENSION_ROUTING 映射表**：

| 维度 | MCP 工具 | 默认模式 |
|------|----------|----------|
| cpu | (无) | ENGINE_ONLY |
| thread | thread_contention_analyzer | MCP_PREFERRED |
| binder | binder_transaction_profiler | MCP_PREFERRED |
| hotspot | main_thread_hotspot_slices | MCP_ONLY |
| io | (无) | ENGINE_ONLY |
| gc | (无) | ENGINE_ONLY |
| gpu | (无) | ENGINE_ONLY |
| sf | (无) | ENGINE_ONLY |
| input | (无) | ENGINE_ONLY |
| lock | (无) | ENGINE_ONLY |
| summary | (无) | ENGINE_ONLY |
| cpu_global | cpu_utilization_profiler | MCP_ONLY |

**当前状态**：MCP Client 为桩实现 (`mcp_client.py` 所有方法返回 `None`)，所有 MCP_PREFERRED 路由自动降级到 engine，MCP_ONLY 维度返回空数据。

---

## 引擎层 — engine/

**文件**: `src/engine/*.py` (20 个文件)

### 解析器 parser.py

Phase 1 核心：使用 Perfetto TraceProcessor 执行 SQL 查询提取 VSync 周期、帧时间线，定位丢帧帧。

关键步骤：
1. 打开 trace 文件创建 TraceProcessor 实例
2. 检测进程名和应用类型 (`app_type.py`)
3. 初始化 CPU 拓扑 (`cpu_topology.py`)
4. 定位帧边界 (`frame_boundary.py`)
5. 按帧遍历，计算帧耗时，标记 Jank 帧
6. 将解析结果写入模块本地 SQLite

### 分析器注册表

`dimension_registry.py` 定义各维度的 FR 编号、依赖关系、描述。`analyzer.py` 注册并调度维度分析器。

### 10 个分析维度

| 维度 | 文件 | 分析内容 |
|------|------|----------|
| cpu | `cpu_analysis.py` | CPU 频率变化、调度延迟、大小核分布 |
| thread | `thread_analysis.py` | 线程状态分布 (Running/S/R/D/R+)、唤醒链 |
| binder | `binder_analysis.py` | Binder 事务耗时、池饱和度 |
| io | `io_analysis.py` | 文件 IO、D-State 阻塞时长 |
| gc | `gc_analysis.py` | GC 暂停时间、频率 |
| gpu | `gpu_analysis.py` | GPU 渲染管线耗时 |
| sf | `sf_analysis.py` | SurfaceFlinger 合成延迟 |
| input | `input_analysis.py` | 输入事件分发延迟 |
| lock | `lock_analysis.py` | Java Monitor 竞争、持锁时长 |
| summary | `summary_analysis.py` | 全 trace 综合摘要 |

### 存储层 storage.py

模块本地 SQLite 数据库 (`data/perfetto_analysis.db`)。表结构包含：
- trace 运行记录
- VSync 周期数据
- Jank 帧详情
- 维度分析结果

迁移脚本位于 `src/migrations/`：
- `001_create_tables.sql` — 基础表
- `002_add_process_name.sql` — 添加进程名字段
- `003_add_mode_dimensions.sql` — 添加分析模式和维度字段

---

## SOP 知识体系

**文件**: `src/agent/prompts.py` + `skills/perfetto-analysis/sop/*.md`

### SOP 目录结构

```
skills/perfetto-analysis/
├── SKILL.md                         # 技能入口 (场景路由表)
├── tool-catalog.md                  # 工具使用手册
├── sql-patterns.md                  # SQL 模式库
├── sop/
│   ├── jank-analysis.md             # Jank 分析 SOP
│   ├── anr-analysis.md              # ANR 分析 SOP
│   ├── memory-analysis.md           # 内存分析 SOP
│   ├── startup-analysis.md          # 启动分析 SOP
│   ├── general-analysis.md          # 通用分析 SOP
│   ├── io-block-analysis.md         # IO 阻塞分析 SOP
│   ├── input-latency.md             # 输入延迟分析 SOP (未映射)
│   ├── response-latency.md          # 响应延迟分析 SOP (未映射)
│   └── rotation-analysis.md         # 转屏分析 SOP (未映射)
├── patterns/
│   └── root-cause-patterns.md       # 根因模式库
├── ref/
│   ├── device-tuning.md             # 设备调优参考
│   └── environment-setup.md         # 环境配置
└── cases/
    ├── TEMPLATE.md                  # 案例模板
    ├── 2026-04-01-lolm-false-positive.md
    └── face-unlock-audio-stutter.md
```

### 场景-SOP 映射

**定义**: `prompts.py` 的 `_SCENE_SOP_MAP`

| 场景 (scene) | SOP 文件名 | 实际文件 | 状态 |
|--------------|-----------|----------|------|
| jank | jank-analysis.md | 存在 | ✅ 正常 |
| anr | anr-analysis.md | 存在 | ✅ 正常 |
| memory | memory-analysis.md | 存在 | ✅ 正常 |
| startup | startup-analysis.md | 存在 | ✅ 正常 |
| cpu | jank-analysis.md (复用) | 存在 | ✅ 正常 |
| io | io-block-analysis.md | 存在 | ✅ 正常 (已修正) |
| general | general-analysis.md | 存在 | ✅ 正常 |

**未映射的 SOP**：`input-latency.md`、`response-latency.md`、`rotation-analysis.md` 已有 SOP 文件但未注册到 `_SCENE_SOP_MAP`。

### 加载机制

```python
def load_sop(scene: str) -> str:
    # 1. 查 _SCENE_SOP_MAP 获取文件名
    # 2. 拼路径: skills/perfetto-analysis/sop/{filename}
    # 3. 文件存在 → 读取全文返回 (不截断)
    # 4. 文件不存在 → 返回 "" + 日志警告
```

**完整 SOP 加载**：不做截断，直接嵌入 SubAgent 的 `instructions`。SOP 文档的完整性决定了 LLM 分析的引导质量。

---

## 上下文预算管理

### 预算控制策略

分析过程中的 LLM 上下文由以下部分构成：

| 组成部分 | Token 估算 | 控制策略 |
|----------|-----------|----------|
| System Instructions (基础 + SOP) | ~2000-5000 | SOP 完整加载，无截断 |
| 工具定义 (9 个工具 Schema) | ~500-800 | 精简 docstring (单行) |
| User Prompt | ~200-300 | 固定模板 |
| 工具返回值 (累积) | **每次 ≤300 token** | `ToolReturn` + `ResultCompressor` |
| LLM 历史输出 (累积) | 不可控 | `request_limit=100` 限制总轮数 |

**核心策略**：通过 `ToolReturn` 机制将每次工具返回值控制在 ~300 token (≈750 字符)，避免多轮工具调用后上下文爆炸。

### ResultCompressor

**文件**: `src/result_compressor.py`

两个主要功能：

1. **`compress()`** — 将完整分析结果压缩为 `CompressedSummary` (Pydantic 模型)
2. **`compress_tool_output()`** — 将工具原始返回值压缩为文本摘要 (用于 ToolReturn)

```python
class ResultCompressor:
    _COMPRESS_STRATEGIES = {
        "pa_detect_jank": _compress_jank,          # Top-5 + 统计
        "pa_analyze_dimension": _compress_dimension, # issues + top 指标
    }

    def compress_tool_output(self, tool_name, raw_output, token_budget=300) -> str:
        # 1. 查策略表 → 有则用专用策略
        # 2. 无则用 _compress_generic (JSON 截断)
        # 3. 最终硬截断: token_budget × 2.5 字符
```

### ToolReturn 压缩流程

```
pa_service.xxx(trace_path, ...)
    │ 返回原始数据 (dict/list/dataclass, 可能 5K-20K token)
    ▼
_make_tool_return(tool_name, raw, compressor)
    │
    ├─ compressor.compress_tool_output(tool_name, raw, 300)
    │    │
    │    ├─ 策略查找: pa_detect_jank → _compress_jank
    │    │              pa_analyze_dimension → _compress_dimension
    │    │              其他 → _compress_generic
    │    │
    │    └─ 硬截断: min(result, 750 chars)
    │
    └─ ToolReturn(
         return_value=compressed_text,  # ≤750 字符 → LLM 可见
         metadata={"raw": raw_data},    # 完整数据 → 应用层保留
       )
```

---

## 降级与容错

### 降级策略矩阵

| 异常条件 | 检测方式 | 行为 | completion 标记 |
|----------|---------|------|-----------------|
| Pydantic AI 未安装 | `ImportError` | `_fallback_engine_analysis()` | `engine_fallback` |
| LLM Provider 未配置 | `_get_model()` 返回 None | Pydantic AI 运行时错误 → Exception | `FAILED` |
| LLM 请求次数超限 | `UsageLimitExceeded` / "request_limit" | 返回部分结论 | `llm_partial` |
| 上下文超长 | `_is_context_overflow()` 关键词匹配 | 返回部分结论 | `llm_partial` |
| 分析超时 | `asyncio.TimeoutError` | 返回空报告 | `TIMEOUT` |
| 用户中止 | `_abort_flag` 检查 | 返回空报告 | `CANCELLED` |
| Jinja2 不可用 | `ImportError` | 使用内嵌 HTML 模板 | — |
| MCP 工具不可用 | MCP Client 返回 None | 降级到 Engine | `degraded` (维度级) |

**上下文超限检测** (`_is_context_overflow`)：

```python
overflow_keywords = ["max length", "context", "too long", "token limit", "exceeds"]
return any(kw in str(exc).lower() for kw in overflow_keywords)
```

### 报告完成标签

**定义**: `report.py` 的 `_COMPLETION_LABELS`

| 标识 | 显示文本 | 触发条件 |
|------|---------|----------|
| `llm_complete` | "LLM 分析完成" | SubAgent 正常完成 |
| `llm_partial` | "LLM 部分完成（因请求限制）" | UsageLimitExceeded 或上下文超限 |
| `engine_fallback` | "引擎分析（Pydantic AI 不可用）" | ImportError 或 Model 不可用 (None) |

---

## 报告生成

**文件**: `src/agent/report.py`

### 报告结构

```
{trace_stem}_{YYYYMMDD_HHmmss}/
├── report.html              # HTML 分析报告
└── raw_data/
    ├── conclusion.json      # LLM 结论文本
    ├── token_used.json      # Token 消耗量
    ├── completion.json      # 完成状态标记
    ├── quality_warnings.json # 结论质量自检警告
    └── tool_calls.json      # 工具调用历史 (含原始数据)
```

**工具调用历史**：通过 `_extract_tool_history()` 从 Pydantic AI 的 `result.all_messages()` 提取，包含每个工具的调用参数、压缩返回值和原始数据 (`raw_data`)。

### Jinja2 模板

**文件**: `templates/report.html`

- 响应式布局，grid 元信息区
- 变量：`trace_name`, `scene`, `process_name`, `conclusion`, `timestamp`, `raw_data`, `completion_label`
- `raw_data` 中每个 key 渲染为 `raw_data/{key}.json` 链接

### Fallback 内嵌模板

当 Jinja2 不可用或模板渲染失败时，使用 `_fallback_render()` 生成完整 HTML。包含：
- 元信息表 (Trace 文件、场景、进程、时间)
- 完成状态徽章 (绿色/橙色)
- 结论区 (Markdown → HTML 简易转换)
- 原始数据引用

---

## 辅助子系统

### PackageMappingDB

**文件**: `src/agent/package_db.py`

SQLite 存储包名与进程名的映射关系，通过分析学习自动积累。

**表结构**：`pa_package_mappings` (PK: package_name + process_name)

| 列 | 类型 | 说明 |
|----|------|------|
| package_name | TEXT | 包名 (如 com.tencent.tmgp.cod) |
| process_name | TEXT | 进程名 (如 com.tencent.tmgp.cod:main) |
| app_label | TEXT | 应用显示名 |
| hit_count | INTEGER | 命中次数 |
| last_used | TEXT | 最后使用时间 |

**API**：`learn()`, `lookup()`, `suggest()`, `export_json()`, `import_json()`, `get_all()`, `delete()`

### FeatureFlagManager

**文件**: `src/analysis_mode.py`

基于 `AnalysisConfig` 解析维度级分析模式。优先级：`dimension_overrides` > `DIMENSION_ROUTING.default_mode` > `global_mode`。

---

## 数据模型总览

### Agent 层模型 (Pydantic)

**文件**: `src/agent/__init__.py`

| 模型 | 用途 | 关键字段 |
|------|------|----------|
| `AnalysisStatus` | 任务状态枚举 | PENDING → ROUTING → ANALYZING → REVIEWING → REPORTING → COMPLETED/FAILED/CANCELLED/TIMEOUT |
| `AgentRole` | Agent 角色枚举 | MAIN / SUB / REVIEW |
| `AnalysisTask` | 分析任务 | id, trace_path, process_name, user_intent, scene, status |
| `AnalysisReport` | 分析报告元数据 | task_id, html_path, raw_data_dir, summary, trace_overview, root_causes |
| `OrchestrationConfig` | Agent 编排配置 | parallel_count, analysis_timeout_sec, auto_open_report |
| `AnalysisRouting` | MainAgent 输出 | scene, sop_name (优先SOP), process_name, reasoning |
| `PackageMapping` | 包名映射 | package_name, app_name, process_names, source **(未使用)** |
| `ConversationMessage` | 对话消息 | id, task_id, role, content **(未使用)** |

### 服务层模型

**文件**: `src/models.py`

| 模型 | 类型 | 用途 |
|------|------|------|
| `AnalysisMode` | Enum | MCP_PREFERRED / ENGINE_ONLY / MCP_ONLY |
| `AnalysisConfig` | Pydantic | 服务层配置 (output_dir, db_path, 阈值等) |
| `TraceOverview` | dataclass | trace 元数据 |
| `DimensionResult` | dataclass | 单维度分析结果 |
| `CompressedSummary` | Pydantic | 压缩后的分析摘要 |
| `TraceInfo` | Pydantic | trace 基础信息 |
| `RootCause` | Pydantic | 根因描述 |
| `ThreadStateSummary` | Pydantic | 线程状态统计 |
| `CpuFreqAnalysis` | Pydantic | CPU 频率分析 |
| `AnalysisResult` | dataclass | 完整分析结果 |
| `AnalysisChainStep/Result` | dataclass | 分析链路记录 |

**注意**：Agent 层配置已命名为 `OrchestrationConfig`（区别于 `models.py` 中的服务层 `AnalysisConfig`）。

---

## 已知问题与不一致

> **更新说明**：以下标记 ✅ 已修复的问题在 2026-04-09 修复。

### 严重问题 (HIGH)

| # | 问题 | 状态 | 修复说明 |
|---|------|------|----------|
| **H1** | SOP 文件名不匹配 (io) | ✅ 已修复 | `prompts.py` 映射修正为 `io-block-analysis.md` |
| **H2** | `_get_model()` 返回 None 导致崩溃 | ✅ 已修复 | `_route_scene()` 和 `_run_sub_agent()` 中检查 None，走 ImportError 降级路径 |
| **H3** | `engine_degraded` 标签不可达 | ✅ 已修复 | 移除死标签，修正 `_run_sub_agent` docstring |

### 中等问题 (MEDIUM)

| # | 问题 | 状态 | 修复说明 |
|---|------|------|----------|
| **M1** | MainAgent 不感知 trace | ✅ 已修复 | orchestrator 预调 `get_trace_overview()` 拼入 MainAgent prompt；修正 docstring |
| **M2** | `sop_name` 字段未使用 | ✅ 已修复 | `load_sop()` 优先使用 `sop_name`，兜底用 scene 查 `_SCENE_SOP_MAP` |
| **M3** | MCP Client 全桩实现 | 保持现状 | 规划到未来迭代，当前所有 MCP 路由自动降级到 engine |
| **M4** | 表名前缀 `pe_` 冲突 | ✅ 已修复 | 重命名为 `pa_package_mappings`，含旧表自动迁移 |
| **M5** | 单条分析无评审 | ✅ 已修复 | 添加 `_check_conclusion_quality()` 轻量规则自检 |
| **M6** | 工具原始数据未写入报告 | ✅ 已修复 | 通过 `_extract_tool_history()` 从 `result.all_messages()` 提取，写入 `raw_data/tool_calls.json` |
| **M7** | 两个同名 `AnalysisConfig` | ✅ 已修复 | Agent 层改名 `OrchestrationConfig` |
| **M8** | docstring 与实现不一致 | ✅ 已修复 | 修正为准确描述：ImportError→engine，超限→llm_partial |

### 低优先级 (LOW)

| # | 问题 | 状态 | 影响 |
|---|------|------|------|
| **L1** | `ConversationMessage`、`PackageMapping` 未使用 | ✅ 已修复 | 移除死代码模型 |
| **L2** | `pa_get_history` 全量加载后截断 | ✅ 已修复 | 服务层支持 `limit` 参数，SQL 加 LIMIT + 文件扫描提前终止 |
| **L3** | `_pa_compress_results` 是桩 | ✅ 已修复 | 移除桩函数和 plugin 注册（压缩已内置到 ToolReturn） |
| **L4** | SQL f-string 拼接 process | ✅ 已修复 | `app_type.py` 中 process_name 单引号转义 |
| **L5** | AGENTS.md 工具清单过时 | ✅ 已修复 | 更新为实际 9 个工具 + ToolReturn 说明 |
| **L6** | 3 个 SOP 文件未注册映射 | ✅ 已修复 | 补充 input-latency/response-latency/rotation 到 `_SCENE_SOP_MAP` |

---

## 附录 — 文件依赖关系

```
plugin.py
  ├→ service.py
  │    ├→ analysis_toolkit.py
  │    │    ├→ engine/parser.py (Phase 1)
  │    │    ├→ engine/analyzer.py (Phase 2)
  │    │    ├→ engine/app_type.py
  │    │    ├→ engine/cpu_topology.py
  │    │    ├→ engine/{cpu,thread,binder,io,gc,gpu,sf,input,lock,summary}_analysis.py
  │    │    ├→ engine/frame_boundary.py
  │    │    ├→ engine/storage.py
  │    │    ├→ engine/export.py + report_writer.py
  │    │    ├→ mcp_client.py (桩)
  │    │    └→ analysis_mode.py (路由策略)
  │    ├→ result_compressor.py
  │    └→ models.py
  └→ agent/orchestrator.py
       ├→ agent/agents.py
       │    └→ agent/tools.py
       │         └→ result_compressor.py
       ├→ agent/prompts.py
       │    └→ skills/perfetto-analysis/sop/*.md
       ├→ agent/report.py
       │    └→ templates/report.html
       └→ agent/package_db.py
```
