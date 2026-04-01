# Perfetto 分析模块 — Agent 工具目录

## 目录

- [概述](#概述)
- [工具选择决策](#工具选择决策)
- [Agent 工具（pa_* 系列）](#agent-工具pa_-系列)
  - [pa_trace_overview](#pa_trace_overview)
  - [pa_detect_jank](#pa_detect_jank)
  - [pa_analyze_dimension](#pa_analyze_dimension)
  - [pa_cpu_overview](#pa_cpu_overview)
  - [pa_thread_state_summary](#pa_thread_state_summary)
  - [pa_cpu_freq_analysis](#pa_cpu_freq_analysis)
  - [pa_find_slices](#pa_find_slices)
  - [pa_execute_sql](#pa_execute_sql)
  - [pa_analyze_anr](#pa_analyze_anr)
  - [pa_analyze_memory](#pa_analyze_memory)
  - [pa_compress_results](#pa_compress_results)
  - [pa_analyze](#pa_analyze)
  - [pa_parse](#pa_parse)
  - [pa_analyze_dims](#pa_analyze_dims)
  - [pa_list_dims](#pa_list_dims)
  - [pa_history](#pa_history)
- [CLI 命令](#cli-命令)
- [MCP 工具（Perfetto MCP Server）](#mcp-工具perfetto-mcp-server)
- [引擎能力概述](#引擎能力概述)
  - [分析维度](#分析维度)
  - [帧边界识别](#帧边界识别)
  - [已知局限](#已知局限)
- [MCP vs 引擎对比](#mcp-vs-引擎对比)
- [SOP 文档索引](#sop-文档索引)

## 概述

本模块提供两套分析通道：**引擎**（本地 Python 分析器）和 **MCP**（Perfetto MCP Server）。`pa_*` 系列 Agent 工具在内部自动路由，优先使用 MCP，失败时降级到引擎。

**调用层级**：Agent 工具 → `service.py` → `analysis_toolkit.py` → MCP / 引擎

**分析模式**（通过 `config.json` 的 `analysis_mode` 控制）：

| 模式 | 行为 |
|------|------|
| `mcp_preferred`（默认）| MCP 优先，失败降级引擎 |
| `engine_only` | 仅引擎 |
| `mcp_only` | 仅 MCP，失败返回 unavailable |

## 工具选择决策

```
用户请求分析 trace
│
├── 需要快速概览？
│   └── pa_trace_overview（引擎）
│
├── 需要卡顿检测？
│   └── pa_detect_jank（引擎，基于 VSync 周期）
│       ⚠️ 游戏 trace 的 FrameTimeline 可能为空
│       → 降级方案：pa_find_slices 搜索 eglSwapBuffers
│         + pa_execute_sql 计算帧间隔
│
├── 需要单维度深入？
│   └── pa_analyze_dimension（MCP/引擎路由）
│       支持 time_range 限定分析窗口
│
├── 需要全局 CPU 概览？
│   └── pa_cpu_overview（MCP）
│
├── 需要主线程状态分布？
│   └── pa_thread_state_summary（MCP SQL）
│       Running 高 → 调 pa_cpu_freq_analysis 检查核心/频率
│
├── 需要 CPU 核心与频率分析？
│   └── pa_cpu_freq_analysis（MCP SQL）
│
├── 需要搜索特定 slice？
│   └── pa_find_slices（MCP）
│
├── 需要自定义 SQL？
│   └── pa_execute_sql（MCP）
│
├── 需要 ANR 分析？
│   └── pa_analyze_anr（MCP）
│
├── 需要内存分析？
│   └── pa_analyze_memory（MCP）
│
├── 需要完整流水线分析 + 报告？
│   └── pa_analyze（引擎全流程）
│
└── 需要压缩结果给 agent_chat？
    └── pa_compress_results
```

## Agent 工具（pa_* 系列）

### pa_trace_overview

获取 trace 元数据概览。

| 属性 | 值 |
|------|------|
| 数据源 | 引擎 |
| 用途 | 分析前的首要步骤，了解 trace 时长、帧数、进程列表 |

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| trace_path | string | ✅ | trace 文件路径 |
| process_name | string | | 目标进程名 |

**返回**：`TraceOverview`（duration_s, processes, frame_count, refresh_rate_hz）

### pa_detect_jank

检测卡顿帧，可选时间范围过滤。

| 属性 | 值 |
|------|------|
| 数据源 | 引擎 |
| 用途 | 定位丢帧位置和时间窗口，为后续维度分析提供目标 |

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| trace_path | string | ✅ | trace 文件路径 |
| process_name | string | | 目标进程名 |
| time_range | object | | `{"start_ms": float, "end_ms": float}` |

**返回**：卡顿帧列表，每帧含 `window_start_ms`、`window_end_ms`、`jank_type`

**能力边界**：
- 依赖 VSync 周期数据（`actual_frame_timeline_slice` 表）
- 游戏进程通常绕过 Choreographer，此表为空 → 返回空列表
- 游戏 trace 的替代方案：用 `pa_find_slices` 搜索 `eglSwapBuffers` 或 `vkQueuePresentKHR`，再用 `pa_execute_sql` 计算帧间隔

### pa_analyze_dimension

单维度分析（自动 MCP/引擎路由）。

| 属性 | 值 |
|------|------|
| 数据源 | MCP 优先，引擎降级 |
| 用途 | 对卡顿帧的时间窗口做深度分析 |

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| trace_path | string | ✅ | trace 文件路径 |
| dimension | string | ✅ | 分析维度（见下表） |
| process_name | string | | 目标进程名 |
| time_range | object | | `{"start_ms": float, "end_ms": float}` |

**可用维度与路由**：

| 维度 | MCP 工具 | 引擎 | 说明 |
|------|----------|------|------|
| cpu | cpu_utilization_profiler | ✅ | CPU 使用率、频率、调度 |
| thread | thread_contention_analyzer | ✅ | 线程状态、阻塞、竞争 |
| binder | binder_transaction_profiler | ✅ | Binder IPC 延迟 |
| hotspot | main_thread_hotspot_slices | ❌ | 主线程热点函数（MCP 独有）|
| io | ❌ | ✅ | IO 阻塞分析（引擎独有）|
| gc | ❌ | ✅ | GC 停顿分析（引擎独有）|
| gpu | ❌ | ✅ | GPU 完成时间分析（引擎独有）|
| sf | ❌ | ✅ | SurfaceFlinger 合成分析（引擎独有）|
| input | ❌ | ✅ | 输入延迟分析（引擎独有）|
| lock | ❌ | ✅ | 锁竞争分析（引擎独有）|
| summary | ❌ | ✅ | 全维度汇总（引擎独有）|

**返回**：`DimensionResult`（dimension, source, data, error, duration_ms）

- `source` 标注数据来源：`mcp` / `engine` / `degraded`（MCP 失败降级）/ `unavailable`

### pa_cpu_overview

获取全 trace CPU 全局概览。

| 属性 | 值 |
|------|------|
| 数据源 | MCP |
| 用途 | 了解整体 CPU 使用情况、线程分布、频率状态 |

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| trace_path | string | ✅ | trace 文件路径 |
| process_name | string | | 目标进程名 |

### pa_thread_state_summary

查询主线程各状态（Running/Sleeping/Runnable/D-State/R+）的耗时和占比。

| 属性 | 值 |
|------|------|
| 数据源 | MCP（execute_sql_query） |
| 用途 | 分析主线程在指定时间段内的状态分布，判断瓶颈类型（CPU 密集/等待/IO 阻塞） |

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| trace_path | string | ✅ | trace 文件路径 |
| process_name | string | | 目标进程名 |
| time_range | object | | 可选时间范围 `{start_ms, end_ms}` |
| compact | boolean | | 仅返回摘要（默认 false） |

**返回**：`ThreadStateSummary` Pydantic 模型（或 compact 模式的 dict），含各状态耗时、占比、主导状态。

**使用场景**：Skill Step 5（线程状态分布后的分支决策树）——根据 Running/Sleeping/Runnable/D-State 占比决定下一步分析方向。

### pa_cpu_freq_analysis

查询主线程运行的 CPU 核心分布和各核心频率统计（min/max/avg）。

| 属性 | 值 |
|------|------|
| 数据源 | MCP（execute_sql_query） |
| 用途 | 当 Running 占比高时，判断是否因 CPU 调度到小核或频率未拉满导致性能不足 |

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| trace_path | string | ✅ | trace 文件路径 |
| process_name | string | | 目标进程名 |
| time_range | object | | 可选时间范围 `{start_ms, end_ms}` |
| compact | boolean | | 仅返回摘要（默认 false） |

**返回**：`CpuFreqAnalysis` Pydantic 模型（或 compact 模式的 dict），含各核心运行时间占比、频率范围、主要核心。

**使用场景**：与 `pa_thread_state_summary` 配合——当 Running 占比 > 40% 时调用，检查 CPU 频率是否受限。

### pa_find_slices

按名称模式搜索 slice。

| 属性 | 值 |
|------|------|
| 数据源 | MCP |
| 用途 | 探索 trace 中的特定事件（如 eglSwapBuffers、doFrame） |

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| trace_path | string | ✅ | trace 文件路径 |
| pattern | string | ✅ | 名称匹配模式 |
| process_name | string | | 目标进程名 |

### pa_execute_sql

对 trace 执行任意 Perfetto SQL 查询。

| 属性 | 值 |
|------|------|
| 数据源 | MCP |
| 用途 | 灵活查询，当其他工具无法满足需求时使用 |

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| trace_path | string | ✅ | trace 文件路径 |
| sql | string | ✅ | Perfetto SQL 语句 |

**常用查询模板**：

```sql
-- 查询进程列表
SELECT name, pid FROM process WHERE name IS NOT NULL ORDER BY pid

-- 查询 trace 时间范围
SELECT MIN(ts)/1e6 as start_ms, MAX(ts)/1e6 as end_ms FROM slice

-- 游戏帧间隔检测（eglSwapBuffers）
WITH swap AS (
  SELECT ts, LAG(ts) OVER (ORDER BY ts) as prev_ts
  FROM slice s
  JOIN thread_track tt ON s.track_id = tt.id
  JOIN thread t ON tt.utid = t.utid
  JOIN process p ON t.upid = p.upid
  WHERE s.name = 'eglSwapBuffers' AND p.name = '<进程名>'
)
SELECT (ts - prev_ts)/1e6 as interval_ms
FROM swap WHERE prev_ts IS NOT NULL AND (ts - prev_ts)/1e6 > 20
ORDER BY interval_ms DESC
```

### pa_analyze_anr

检测 ANR 事件并分析根因。

| 属性 | 值 |
|------|------|
| 数据源 | MCP |
| 用途 | ANR 检测和根因定位 |

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| trace_path | string | ✅ | trace 文件路径 |
| process_name | string | | 目标进程名 |

### pa_analyze_memory

检测内存泄漏并分析堆支配树。

| 属性 | 值 |
|------|------|
| 数据源 | MCP |
| 用途 | 内存泄漏和堆分析 |

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| trace_path | string | ✅ | trace 文件路径 |
| process_name | string | | 目标进程名 |

### pa_compress_results

将分析结果压缩为结构化摘要。

| 属性 | 值 |
|------|------|
| 数据源 | 本地计算 |
| 用途 | 生成供 agent_chat 使用的精简上下文 |

**注意**：当前为占位注册。实际压缩需通过 `PerfettoAnalysisService.compress_results()` 传入 `TraceOverview` 和 `DimensionResult` 列表。

### pa_analyze

完整分析流水线（Phase 1 + Phase 2 + 报告导出）。

| 属性 | 值 |
|------|------|
| 数据源 | 引擎 |
| 用途 | 一次性完成全部分析并生成报告 |

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| trace_path | string | ✅ | trace 文件路径 |
| process_name | string | | 目标进程名（空则自动检测）|

**返回**：`AnalysisResult`（jank_times, frame_num, report_path, dimensions_completed）

### pa_parse

仅执行 Phase 1 丢帧解析，不做 Phase 2 维度分析。

**⚠️ 适用场景**：仅用于**卡顿/掉帧**分析（jank-analysis SOP）。响应时延、启动性能、转屏等场景不应使用此工具，应直接使用 `pa_execute_sql` 查询对应的 slice 和时间窗口。

| 属性 | 值 |
|------|------|
| 数据源 | 引擎 |
| 用途 | 快速了解丢帧数量和帧率 |

**参数**：同 `pa_analyze`

### pa_analyze_dims

按指定维度列表分析 trace。

| 属性 | 值 |
|------|------|
| 数据源 | 引擎 |
| 用途 | 选择性分析特定维度 |

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| trace_path | string | ✅ | trace 文件路径 |
| process_name | string | | 目标进程名 |
| dimensions | string[] | | 维度列表（空则全部）|

### pa_list_dims

列出所有可用分析维度及说明。无参数。

### pa_history

查询分析历史记录。无参数。

## CLI 命令

通过 `python -m toolkit.app analysis <command>` 调用。

| 命令 | 说明 |
|------|------|
| `analysis info` | 模块信息与配置 |
| `analysis parse <trace>` | Phase 1 丢帧解析 |
| `analysis export <trace>` | 完整分析 + 导出报告 |
| `analysis analyze <trace> --dims cpu thread` | 指定维度分析 |
| `analysis dims` | 列出可用维度 |
| `analysis report` | 从 DB 导出报告 |
| `analysis history` | 查看历史记录 |
| `analysis config show` | 显示分析模式配置 |
| `analysis config set <mode>` | 设置分析模式 |

所有命令支持 `--json` 参数输出 JSON 格式。

## MCP 工具（Perfetto MCP Server）

以下 MCP 工具可通过 `pa_*` Agent 工具间接调用，也可由 Agent 直接调用。

| MCP 工具 | 对应 pa_* 工具 | time_range 支持 |
|----------|---------------|----------------|
| frame_performance_summary | — | ❌ |
| detect_jank_frames | pa_detect_jank（备选通道） | ❌ |
| cpu_utilization_profiler | pa_cpu_overview / pa_analyze_dimension(cpu) | ❌ |
| thread_contention_analyzer | pa_analyze_dimension(thread) | ✅ |
| binder_transaction_profiler | pa_analyze_dimension(binder) | ✅ |
| main_thread_hotspot_slices | pa_analyze_dimension(hotspot) | ✅ |
| find_slices | pa_find_slices | ✅ |
| execute_sql_query | pa_execute_sql | N/A |
| detect_anrs | pa_analyze_anr（内部调用） | ❌ |
| anr_root_cause_analyzer | pa_analyze_anr（内部调用） | ❌ |
| memory_leak_detector | pa_analyze_memory（内部调用） | ❌ |
| heap_dominator_tree_analyzer | pa_analyze_memory（内部调用） | ❌ |

**直接调用 MCP vs 使用 pa_* 工具**：
- `pa_*` 工具：自动路由、降级、chain step 记录、引擎独有维度
- 直接 MCP：无降级、无记录，但参数更灵活（如 MCP 的 `severity_filter`、`group_by`）

## 引擎能力概述

### 分析维度

引擎提供 9 个分析维度 + Summary，每个维度在 `src/engine/` 中有独立分析器：

| 维度 | 文件 | 核心能力 |
|------|------|----------|
| cpu | cpu_analysis.py | 线程 Running/Runnable 时间、CPU 频率、调度延迟、核心分布 |
| thread | thread_analysis.py | 线程状态分布（R/S/D/T）、D-state 阻塞归因 |
| binder | binder_analysis.py | Binder 调用延迟、线程池使用、Server 侧耗时 |
| io | io_analysis.py | IO 等待时间、D-state 阻塞 |
| gc | gc_analysis.py | GC 暂停次数/时长、STW 影响 |
| gpu | gpu_analysis.py | GPU 完成时间、GPU fence 等待 |
| sf | sf_analysis.py | SurfaceFlinger 合成耗时、帧提交延迟 |
| input | input_analysis.py | 输入事件传递延迟 |
| lock | lock_analysis.py | 锁竞争时间、等待链 |
| summary | summary_analysis.py | 全维度汇总统计 |

### 帧边界识别

引擎在 `src/engine/frame_boundary.py` 中支持按 App 类型识别帧边界：

| App 类型 | 帧边界标记 | 说明 |
|----------|-----------|------|
| app | `Choreographer#doFrame` slice | 标准 Android UI 应用 |
| game | `eglSwapBuffers` / `vkQueuePresentKHR` slice | OpenGL / Vulkan 游戏 |
| camera | Choreographer 优先，降级到 eglSwapBuffers | 相机预览 |

**引擎类型推断线索**（trace 中的线程名）：

| 引擎 | 特征线程 |
|------|----------|
| Unity | `UnityMain`, `UnityChoreograp`, `UnityGfxDeviceW` |
| Unreal | `GameThread`, `RenderThread`, `RHIThread` |
| 自研 | 无标准线程名，需查看 `eglSwapBuffers` 所在线程 |

### 已知局限

1. **`pa_detect_jank` 对游戏 trace 可能返回空列表**
   - 原因：依赖 VSync 周期数据，游戏绕过 Choreographer
   - `frame_boundary.py` 有游戏帧边界识别，但未接入 `detect_jank_frames()` 主流程
   - 替代方案：使用 `pa_find_slices`/`pa_execute_sql` 手动计算帧间隔

2. **MCP `detect_jank_frames` 同样依赖 FrameTimeline**
   - 游戏 trace 返回 0 帧
   - 需结合引擎或自定义 SQL 补充

3. **`pa_compress_results` 当前为占位实现**
   - 需通过 service 层直接调用 `compress_results()`

## MCP vs 引擎对比

| 能力 | MCP | 引擎 | 推荐 |
|------|-----|------|------|
| 帧性能概览 | ✅ frame_performance_summary | ✅ pa_parse | MCP（更快） |
| 卡顿帧检测 | ⚠️ 仅 Choreographer 管线 | ⚠️ 同 MCP（VSync 依赖） | 引擎（有 frame_boundary 扩展点）|
| CPU 分析 | ✅ 含频率分析 | ✅ 含调度延迟和核心分布 | 互补 |
| 线程竞争 | ✅ 含 monitor_contention | ✅ 含状态分布 | MCP（更丰富） |
| Binder | ✅ 含 AIDL 分组 | ✅ 含线程池饱和检测 | MCP（group_by 灵活） |
| 主线程热点 | ✅ main_thread_hotspot_slices | ❌ | MCP 独有 |
| IO 阻塞 | ❌ | ✅ | 引擎独有 |
| GC 分析 | ❌ | ✅ | 引擎独有 |
| GPU 分析 | ❌ | ✅ | 引擎独有 |
| SF 合成 | ❌ | ✅ | 引擎独有 |
| 输入延迟 | ❌ | ✅ | 引擎独有 |
| 锁分析 | ❌ | ✅ | 引擎独有 |
| ANR 检测 | ✅ | ❌ | MCP 独有 |
| 内存分析 | ✅ | ❌ | MCP 独有 |
| 任意 SQL | ✅ | ❌ | MCP 独有 |

## SOP 文档索引

SOP 场景路由详见 [SKILL.md Step 2 场景路由表](SKILL.md#分析流程)，此处不重复列出。
