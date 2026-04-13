# 时间窗口分析 — CPU/GPU 技术实现

## 目录

- [概述](#概述)
- [调用链总览](#调用链总览)
- [时间区域机制](#时间区域机制)
  - [时间参数约定](#时间参数约定)
  - [双模式分发](#双模式分发)
  - [统一窗口分析入口](#统一窗口分析入口)
  - [时间戳转换](#时间戳转换)
- [CPU 分析实现](#cpu-分析实现)
  - [入口与结构](#入口与结构)
  - [CPU 频率分析](#cpu-频率分析)
  - [大小核调度分析](#大小核调度分析)
  - [调度延迟分析](#调度延迟分析)
  - [CPU 拓扑初始化](#cpu-拓扑初始化)
- [GPU 分析实现](#gpu-分析实现)
  - [入口与结构](#gpu-入口与结构)
  - [DrawFrame 分析](#drawframe-分析)
  - [dequeueBuffer 分析](#dequeuebuffer-分析)
  - [GPU Render Stage 探测](#gpu-render-stage-探测)
- [维度注册与路由](#维度注册与路由)
  - [维度注册表](#维度注册表)
  - [路由配置](#路由配置)
- [SQL 查询参考](#sql-查询参考)
- [已知限制与改进方向](#已知限制与改进方向)

## 概述

Perfetto 分析引擎支持对 trace 文件的**指定时间区域**进行 CPU 和 GPU 维度分析。时间区域通过 `time_range: {"start_ms": float, "end_ms": float}` 参数传入，引擎自动将毫秒值转换为纳秒，然后在所有 SQL 查询中注入时间过滤条件。

核心文件：

| 文件 | 职责 |
|------|------|
| `src/analysis_toolkit.py` | 时间窗口分发、引擎调度入口 |
| `src/analysis_mode.py` | 维度路由配置（ENGINE_ONLY / MCP_PREFERRED） |
| `src/engine/analyzer.py` | 维度注册表、逐帧分析编排器 |
| `src/engine/cpu_analysis.py` | CPU 频率 / 大小核 / 调度延迟分析 |
| `src/engine/gpu_analysis.py` | GPU DrawFrame / dequeueBuffer 分析 |
| `src/engine/cpu_topology.py` | CPU 集群拓扑初始化 |
| `src/engine/parser.py` | Trace 解析、TraceProcessor 实例化 |

## 调用链总览

```
用户/Agent/Plugin
    │
    ▼
service.analyze_dimension(trace_path, process, dimension, time_range)
    │
    ▼
AnalysisToolkit.analyze_dimension()
    │  根据 DIMENSION_ROUTING 查路由
    │  CPU/GPU → ENGINE_ONLY 通道
    ▼
AnalysisToolkit._engine_analyze(trace_path, process, dimension, time_range)
    │
    │  1. parser.parse_trace_with_tp() → 获取 tp 实例 + parse_result
    │  2. 校验 time_range 是否在 trace 范围内
    │
    ├── 有 time_range ──→ _engine_analyze_window()
    │                        │  查 upid → target_utids
    │                        │  初始化 CPU topology
    │                        │  调用 _DIMENSION_ANALYZERS[dim]
    │                        ▼
    │                     analyze_cpu() / analyze_gpu()
    │                        │
    │                        ▼
    │                     tp.query(SQL with window_start_ns/window_end_ns)
    │
    └── 无 time_range ──→ analyzer.analyze_jank()
                            │  逐帧计算 vsync 窗口
                            │  对每帧调用同样的维度分析函数
                            ▼
                         _analyze_single_jank()
                            │  window = [ajt1 - 2*vsync, sjt2 + vsync]
                            ▼
                         analyze_cpu() / analyze_gpu()
```

## 时间区域机制

### 时间参数约定

时间区域统一使用字典格式，单位为**毫秒**（相对于 trace 内部时间轴）：

```python
time_range = {
    "start_ms": 1045001.971,  # 窗口起始（毫秒）
    "end_ms":   1045002.305,  # 窗口结束（毫秒）
}
```

内部转换常量：

```python
_MS_TO_NS = 1_000_000  # 毫秒 → 纳秒
```

### 双模式分发

`_engine_analyze` 方法是引擎分析的核心分发点（`analysis_toolkit.py` L635-721）：

```python
def _engine_analyze(self, trace_path, process, dimension, time_range):
    parse_result, tp = parser.parse_trace_with_tp(trace_path, ...)

    # 校验：time_range 是否与 trace 时间范围重叠
    if time_range:
        tr_start = parse_result.get("trace_start_ns") or 0
        tr_end = parse_result.get("trace_end_ns") or 0
        req_start_ns = int(time_range["start_ms"] * _MS_TO_NS)
        req_end_ns = int(time_range["end_ms"] * _MS_TO_NS)
        if tr_end > 0 and (req_start_ns > tr_end or req_end_ns < tr_start):
            return DimensionResult(dimension=dimension, source="unavailable",
                                   error="time_range 超出 trace 范围")

    # 分发
    if time_range:
        window_start_ns = int(time_range["start_ms"] * _MS_TO_NS)
        window_end_ns = int(time_range["end_ms"] * _MS_TO_NS)
        data = self._engine_analyze_window(tp, parse_result, process, dimension,
                                            window_start_ns, window_end_ns)
    else:
        # 逐帧分析模式
        analysis = analyzer.analyze_jank(tp, parse_result, ...)
        data = {"per_jank_count": ..., "per_jank_results": [...]}
```

**两条路径的区别**：

| 特性 | 指定 time_range | 无 time_range（按帧分析） |
|------|-----------------|--------------------------|
| 窗口来源 | 用户显式传入的 ms 区间 | 每个 jank 帧的 vsync 前后自动计算 |
| 分析粒度 | 整个区域一次性分析 | 逐帧分析，结果按帧聚合 |
| 输出结构 | 单个维度 data dict | `per_jank_results` 数组 |

### 统一窗口分析入口

`_engine_analyze_window`（`analysis_toolkit.py` L723-772）是所有维度共用的窗口分析方法：

```python
def _engine_analyze_window(self, tp, parse_result, process, dimension,
                            window_start_ns, window_end_ns):
    # 1. 懒加载维度注册表
    if not _DIMENSION_ANALYZERS:
        _register_builtin_dimensions()

    # 2. 查找目标进程的 upid 和所有线程 utid
    analyzer_fn = _DIMENSION_ANALYZERS.get(dimension)
    upid = app_type_mod.find_target_upid(tp, process)
    target_utids = [r.utid for r in tp.query(f"SELECT utid FROM thread WHERE upid = {upid}")]

    # 3. 初始化 CPU 拓扑
    topology = cpu_topo_mod.init_cpu_topology(tp)

    # 4. 调用具体维度分析函数
    return analyzer_fn(
        tp=tp,
        window_start_ns=window_start_ns,
        window_end_ns=window_end_ns,
        target_utids=target_utids,
        topology=topology,
        upid=upid,
        slow_binder_ms=self._cfg.slow_binder_threshold_ms,
        sched_latency_ms=self._cfg.sched_latency_threshold_ms,
    )
```

### 时间戳转换

Perfetto trace 内部使用 **BOOTTIME 纳秒**作为时间戳。如果需要从墙钟时间（REALTIME）转换，需要获取 clock_snapshot 中的偏移量：

```python
# 获取 BOOTTIME → REALTIME 偏移
rt_rows = tp.query("SELECT clock_value FROM clock_snapshot WHERE clock_id = 1 AND snapshot_id = 0 LIMIT 1")
bt_rows = tp.query("SELECT clock_value FROM clock_snapshot WHERE clock_id = 6 AND snapshot_id = 0 LIMIT 1")
realtime_offset_ns = int(rt_rows[0].clock_value) - int(bt_rows[0].clock_value)

# 绝对时间 → trace 内部时间
trace_internal_ns = absolute_realtime_ns - realtime_offset_ns
```

其中：
- `clock_id = 1`：REALTIME（Unix 纪元毫秒）
- `clock_id = 6`：BOOTTIME（设备启动后纳秒）

## CPU 分析实现

### 入口与结构

`cpu_analysis.py` 的入口函数 `analyze_cpu` 编排三个子分析（L34-79）：

```python
def analyze_cpu(
    tp: Any,
    window_start_ns: int,
    window_end_ns: int,
    target_utids: list[int],
    topology: dict[str, Any] | None = None,
    sched_latency_ms: float = 1.0,
    **kwargs: Any,
) -> dict[str, Any]:
    result = {
        "freq_analysis": {},       # CPU 频率与爬升
        "cluster_analysis": {},    # 大小核调度
        "sched_latency": {},       # 调度延迟
        "degraded": False,         # 是否降级
    }
    freq_data = _analyze_cpu_freq(tp, window_start_ns, window_end_ns, topology)
    cluster_data = _analyze_cluster_scheduling(tp, ..., target_utids, topology)
    sched_data = _analyze_sched_latency(tp, ..., target_utids, sched_latency_ms)
    return result
```

### CPU 频率分析

`_analyze_cpu_freq`（L82-188）使用 **3 段 fallback SQL 查询**，按优先级尝试，命中即停：

**查询 1**（首选）— `cpu_counter_track` + GLOB 模糊匹配：

```sql
SELECT ct.cpu, c.ts, CAST(c.value AS INTEGER) as freq_khz
FROM counter c
JOIN cpu_counter_track ct ON c.track_id = ct.id
WHERE ct.name GLOB '*freq*' AND ct.name NOT GLOB '*gpu*'
  AND c.ts >= {start_ns} AND c.ts <= {end_ns}
ORDER BY ct.cpu, c.ts
```

**查询 2**（精确名称匹配）：

```sql
WHERE ct.name IN ('cpufreq', 'cpu_freq', 'cpu_frequency')
  AND c.ts >= {start_ns} AND c.ts <= {end_ns}
```

**查询 3**（兜底 — 从 `counter_track` 名称解析 CPU 编号）：

```sql
SELECT CAST(SUBSTR(t.name, INSTR(t.name, 'cpu') + 3) AS INTEGER) as cpu, ...
FROM counter c JOIN counter_track t ON c.track_id = t.id
WHERE (t.name GLOB '*cpufreq*' OR t.name GLOB '*cpu_frequency*' OR t.name GLOB '*cpu*freq*')
  AND t.name NOT GLOB '*gpu*'
  AND c.ts >= {start_ns} AND c.ts <= {end_ns}
```

分析后进行**频率爬升检测**：连续 ≥3 次递增判定为 ramp-up，记录每步详情（from_khz, to_khz, step_dur_us）。

输出结构：

```json
{
  "freq_events": [{"cpu": 0, "ts_ns": ..., "freq_khz": 2400000, "cluster": "little"}],
  "ramp_ups": [{"cpu": 0, "start_freq_khz": 2400000, "end_freq_khz": 3532800, "steps": 3, "total_dur_us": 3614.2, "step_details": [...]}],
  "stats": {"min_freq_khz": ..., "max_freq_khz": ..., "per_cpu": {...}}
}
```

### 大小核调度分析

`_analyze_cluster_scheduling`（L191-260）查询 `thread_state` 表中的 `Running` 状态，使用**半开区间重叠**时间过滤：

```sql
SELECT ts.ts, ts.dur, ts.cpu, ts.utid, t.name as thread_name
FROM thread_state ts
JOIN thread t ON ts.utid = t.utid
WHERE ts.utid IN ({utid_list})
  AND ts.state = 'Running'
  AND ts.ts + ts.dur > {start_ns}   -- slice 结束时间 > 窗口开始
  AND ts.ts < {end_ns}               -- slice 开始时间 < 窗口结束
ORDER BY ts.utid, ts.ts
```

> **时间过滤说明**：`ts + dur > start AND ts < end` 是标准的半开区间重叠判定——只要 thread_state 事件与窗口有任何重叠就会被选中，即使事件跨越窗口边界。

分析逻辑：
1. 按 CPU 编号映射到集群类型（little/mid/big）
2. 累加各集群运行时间占比
3. 检测相邻调度的 CPU 迁移（同集群 vs 跨集群）

输出结构：

```json
{
  "cluster_time_ns": {"little": 123456, "big": 789012},
  "cluster_pct": {"little": 13.5, "big": 86.5},
  "migrations_same_cluster": 5,
  "migrations_cross_cluster": 2,
  "migration_details": [{"utid": ..., "from_cluster": "little", "to_cluster": "big", ...}]
}
```

### 调度延迟分析

`_analyze_sched_latency`（L263-319）查询 `R` / `R+` 状态（线程在就绪队列等待被调度执行）：

```sql
SELECT ts.ts, ts.dur, ts.cpu, ts.utid, t.name as thread_name
FROM thread_state ts
JOIN thread t ON ts.utid = t.utid
WHERE ts.utid IN ({utid_list})
  AND ts.state IN ('R', 'R+')
  AND ts.ts + ts.dur > {start_ns}
  AND ts.ts < {end_ns}
ORDER BY ts.dur DESC
```

分析逻辑：
1. 收集所有调度延迟时长
2. 计算分位数统计（P50/P90/P99/Max）
3. 标记超过阈值（默认 1ms）的异常条目

输出结构：

```json
{
  "stats": {"count": 42, "p50_us": 15.2, "p90_us": 89.5, "p99_us": 1250.0, "max_us": 3200.0},
  "anomaly_count": 3,
  "anomalies": [{"utid": ..., "thread_name": "RenderThread", "dur_us": 3200.0, ...}]
}
```

### CPU 拓扑初始化

`cpu_topology.py` 的 `init_cpu_topology` 使用两级 fallback（L10-20）：

**优先方案**：Perfetto stdlib 的 `android_cpu_cluster_type` 表：

```sql
INCLUDE PERFETTO MODULE android.cpu.cluster_type;
SELECT cpu, cluster_type FROM android_cpu_cluster_type ORDER BY cpu;
```

**兜底方案**：从各 CPU 最大频率推断分组（频率相同的 CPU 归为同一集群，按频率从低到高标记为 little/mid/big）。

集群命名规则：
- 1 个集群 → `big`
- 2 个集群 → `little`, `big`
- 3 个集群 → `little`, `mid`, `big`
- 4+ 个集群 → `little`, `mid_1`, ..., `mid_N`, `big`

## GPU 分析实现

### GPU 入口与结构

`gpu_analysis.py` 的 `analyze_gpu`（L9-105）：

```python
def analyze_gpu(
    tp: Any,
    window_start_ns: int,
    window_end_ns: int,
    target_utids: list[int],
    upid: int | None = None,
) -> dict[str, Any]:
    result = {
        "draw_frames": [],              # DrawFrame slice 列表
        "dequeue_buffers": [],          # dequeueBuffer slice 列表
        "draw_frame_stats": {},         # DrawFrame 统计
        "dequeue_stats": {},            # dequeueBuffer 统计
        "render_stage_available": False, # 是否有 GPU render stage 数据
    }
```

线程过滤支持两种模式：
- 有 `target_utids` → `t.utid IN (utid_list)`
- 仅有 `upid` → `t.upid = {upid}`

### DrawFrame 分析

```sql
SELECT s.ts, s.dur, s.name
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
WHERE {where_clause}
  AND s.name GLOB '*DrawFrame*'
  AND s.ts >= {window_start_ns} AND s.ts <= {window_end_ns}
ORDER BY s.ts
```

> **注意**：GPU 分析使用 `s.ts >= start AND s.ts <= end`（按 slice 起点完全落在窗口内过滤），与 CPU 的半开区间重叠过滤不同。

统计输出：count, avg_us, P99_us, max_us。

### dequeueBuffer 分析

```sql
SELECT s.ts, s.dur
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
WHERE {where_clause}
  AND s.name GLOB '*dequeueBuffer*'
  AND s.ts >= {window_start_ns} AND s.ts <= {window_end_ns}
ORDER BY s.ts
```

统计输出同上。

### GPU Render Stage 探测

```sql
SELECT 1 FROM gpu_slice LIMIT 1
```

仅检测 `gpu_slice` 表是否存在且有数据，标记 `render_stage_available`。该表通常由 GPU profiling 工具（如 AGI）产生。

## 维度注册与路由

### 维度注册表

`analyzer.py` 使用全局字典 `_DIMENSION_ANALYZERS` 管理维度 → 分析函数映射（L16-107）：

```python
_DIMENSION_ANALYZERS: dict[str, Any] = {}

def _register_builtin_dimensions():
    _DIMENSION_ANALYZERS["thread"] = _wrap_thread_analyzer(thread_analysis)
    _DIMENSION_ANALYZERS["cpu"]    = _wrap_cpu_analyzer(cpu_analysis)
    _DIMENSION_ANALYZERS["binder"] = _wrap_binder_analyzer(binder_analysis)
    _DIMENSION_ANALYZERS["io"]     = _wrap_io_analyzer(io_analysis)
    _DIMENSION_ANALYZERS["gc"]     = _wrap_optional_analyzer(gc_analysis, "analyze_gc", "gc")
    _DIMENSION_ANALYZERS["gpu"]    = _wrap_optional_analyzer(gpu_analysis, "analyze_gpu", "gpu")
    _DIMENSION_ANALYZERS["sf"]     = _wrap_optional_analyzer(sf_analysis, "analyze_sf", "sf")
    _DIMENSION_ANALYZERS["input"]  = _wrap_optional_analyzer(input_analysis, "analyze_input", "input")
    _DIMENSION_ANALYZERS["lock"]   = _wrap_optional_analyzer(lock_analysis, "analyze_lock", "lock")
```

所有包装函数统一签名：`(tp, window_start_ns, window_end_ns, target_utids, **kw) → dict`。

### 路由配置

`analysis_mode.py` 的 `DIMENSION_ROUTING` 控制每个维度的分析通道（L25-90）：

| 维度 | MCP 工具 | 支持 time_range | 默认模式 |
|------|---------|----------------|---------|
| `cpu` | 无 | 否 | ENGINE_ONLY |
| `gpu` | 无 | 否 | ENGINE_ONLY |
| `thread` | `thread_contention_analyzer` | 是 | MCP_PREFERRED |
| `binder` | `binder_transaction_profiler` | 是 | MCP_PREFERRED |
| `hotspot` | `main_thread_hotspot_slices` | 是 | MCP_ONLY |
| `io` | 无 | 否 | ENGINE_ONLY |
| `gc` | 无 | 否 | ENGINE_ONLY |
| `sf` | 无 | 否 | ENGINE_ONLY |
| `input` | 无 | 否 | ENGINE_ONLY |
| `lock` | 无 | 否 | ENGINE_ONLY |

**`supports_time_range` 含义**：仅影响 MCP 通道是否向外部工具传递 `time_range` 参数；引擎通道始终支持 `time_range`（通过 `_engine_analyze_window`）。

## SQL 查询参考

### 时间过滤的两种写法

**1. 精确匹配（slice 起点在窗口内）** — GPU 使用：

```sql
AND s.ts >= {window_start_ns} AND s.ts <= {window_end_ns}
```

**2. 半开区间重叠（slice 与窗口有任何重叠）** — CPU thread_state 使用：

```sql
AND ts.ts + ts.dur > {start_ns}  -- slice 结束 > 窗口开始
AND ts.ts < {end_ns}              -- slice 开始 < 窗口结束
```

### 完整 SQL 清单

| 用途 | 表 | 关键条件 | 文件 |
|------|----|---------|------|
| CPU 频率变化 | `counter` + `cpu_counter_track` | `name GLOB '*freq*'`, ts 区间 | `cpu_analysis.py` |
| 大小核运行时间 | `thread_state` + `thread` | `state='Running'`, utid 过滤 | `cpu_analysis.py` |
| 调度延迟 | `thread_state` + `thread` | `state IN ('R','R+')`, dur DESC | `cpu_analysis.py` |
| DrawFrame 耗时 | `slice` + `thread_track` + `thread` | `name GLOB '*DrawFrame*'` | `gpu_analysis.py` |
| dequeueBuffer 耗时 | `slice` + `thread_track` + `thread` | `name GLOB '*dequeueBuffer*'` | `gpu_analysis.py` |
| GPU slice 存在性 | `gpu_slice` | `LIMIT 1` | `gpu_analysis.py` |
| CPU 拓扑 | `android_cpu_cluster_type` | stdlib module | `cpu_topology.py` |
| 每 CPU 最大频率 | `counter` + `cpu_counter_track` | `MAX(c.value) GROUP BY cpu` | `cpu_topology.py` |
| 进程查找 | `process` | `name = process_name` | `app_type.py` |
| 线程查找 | `thread` | `upid = target_upid` | `analysis_toolkit.py` |
| 时钟偏移 | `clock_snapshot` | `clock_id = 1 / 6` | `parser.py` |

## 已知限制与改进方向

### 当前限制

1. **Agent 工具未暴露 time_range**：`pa_analyze_dimension` 闭包未传递 `time_range` 参数，Agent 只能发起全 trace 分析
2. **GPU 时间过滤不一致**：GPU 使用精确匹配（`ts >= start AND ts <= end`），可能遗漏跨越窗口边界的 DrawFrame
3. **MCP CPU 利用率无时间窗口**：`cpu_utilization_profiler` MCP 工具只支持全 trace 画像
4. **cluster_analysis 依赖 target_utids**：无目标进程时跳过大小核调度分析
5. **频率数据 fallback**：3 段 SQL 增加了首次查询延迟，但保证了跨 Android 版本兼容性

### 改进方向

- 为 `pa_analyze_dimension` Agent 工具增加 `time_range` 参数
- 统一 CPU/GPU 的时间过滤策略（建议全部使用半开区间重叠）
- 为 `cpu_utilization_profiler` MCP 工具添加可选的 `time_range` 参数
- 增加 GPU 频率分析（需要 `gpu_counter_track` 支持）
