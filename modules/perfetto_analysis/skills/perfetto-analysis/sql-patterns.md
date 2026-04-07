# 常用 SQL 查询模式

本文件收录 Perfetto trace 分析中高频使用的 SQL 查询模板。
Agent 在需要自定义数据探索时可参考此处。

## 目录

- [进程发现](#进程发现)
- [渲染管线识别](#渲染管线识别)
- [游戏帧间隔分析](#游戏帧间隔分析)
- [线程状态分布](#线程状态分布)
- [阻塞链追踪（waker）](#阻塞链追踪waker)
- [Binder 调用延迟](#binder-调用延迟)
- [时间区间重叠检测](#时间区间重叠检测)
- [RSS 内存趋势](#rss-内存趋势)
- [CPU 频率查询](#cpu-频率查询)
- [D-State（IO Block）检测](#d-stateio-block检测)
- [IO 请求量统计（block_rq_insert）](#io-请求量统计block_rq_insert)
- [SurfaceFlinger 关键 slice 查询](#surfaceflinger-关键-slice-查询)
- [HWC Binder 耗时查询](#hwc-binder-耗时查询)
- [冷启动检测](#冷启动检测)

## 进程发现

```sql
SELECT p.name, p.pid, COUNT(s.id) as slice_count
FROM process p LEFT JOIN thread t ON p.upid = t.upid
LEFT JOIN thread_track tt ON t.utid = tt.utid
LEFT JOIN slice s ON tt.id = s.track_id
WHERE p.name IS NOT NULL
GROUP BY p.name ORDER BY slice_count DESC LIMIT 20
```

## 渲染管线识别

```sql
-- 检查游戏渲染管线
SELECT s.name, COUNT(*) as cnt FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
JOIN process p ON t.upid = p.upid
WHERE p.name = '<进程名>'
  AND s.name IN ('eglSwapBuffers', 'vkQueuePresentKHR',
                 'Choreographer#doFrame')
GROUP BY s.name

-- 检查特征线程
SELECT t.name FROM thread t
JOIN process p ON t.upid = p.upid
WHERE p.name = '<进程名>'
  AND t.name IN ('UnityMain', 'GameThread', 'RenderThread',
                 '1.ui', '1.raster', 'CrRendererMain')
```

## 游戏帧间隔分析

```sql
WITH swap AS (
  SELECT ts, dur, LAG(ts) OVER (ORDER BY ts) as prev_ts
  FROM slice s
  JOIN thread_track tt ON s.track_id = tt.id
  JOIN thread t ON tt.utid = t.utid
  JOIN process p ON t.upid = p.upid
  WHERE s.name = 'eglSwapBuffers' AND p.name = '<进程名>'
)
SELECT
  ts/1e6 as ts_ms,
  (ts - prev_ts)/1e6 as interval_ms,
  CASE
    WHEN (ts - prev_ts)/1e6 > <vsync_ms * 3> THEN 'SEVERE'
    WHEN (ts - prev_ts)/1e6 > <vsync_ms * 2> THEN 'MAJOR'
    WHEN (ts - prev_ts)/1e6 > <vsync_ms * 1.5> THEN 'MINOR'
  END as severity
FROM swap
WHERE prev_ts IS NOT NULL AND (ts - prev_ts)/1e6 > <vsync_ms * 1.5>
ORDER BY interval_ms DESC
```

阈值 1.5× VSync 与引擎 jank_1 判定标准一致。

## 线程状态分布

```sql
SELECT state, SUM(dur)/1e6 as total_ms,
  ROUND(SUM(dur)*100.0/SUM(SUM(dur)) OVER(), 2) as pct
FROM thread_state ts
JOIN thread t ON ts.utid = t.utid
JOIN process p ON t.upid = p.upid
WHERE p.name = '<进程名>' AND t.is_main_thread = 1
  AND ts.ts BETWEEN <start_ns> AND <end_ns>
GROUP BY state ORDER BY total_ms DESC
```

## 阻塞链追踪（waker）

```sql
SELECT
  ts.ts/1e6 as blocked_ts_ms,
  ts.dur/1e6 as blocked_dur_ms,
  ts.state,
  waker_t.name as waker_thread,
  waker_p.name as waker_process
FROM thread_state ts
JOIN thread t ON ts.utid = t.utid
JOIN process p ON t.upid = p.upid
LEFT JOIN thread waker_t ON ts.waker_utid = waker_t.utid
LEFT JOIN process waker_p ON waker_t.upid = waker_p.upid
WHERE p.name = '<进程名>' AND t.name = '<线程名>'
  AND ts.state IN ('S', 'D')
  AND ts.dur > 1000000  -- > 1ms
  AND ts.ts BETWEEN <start_ns> AND <end_ns>
ORDER BY ts.dur DESC LIMIT 20
```

## Binder 调用延迟

```sql
SELECT
  reply.dur/1e6 as binder_dur_ms,
  caller_t.name as caller_thread,
  server_p.name as server_process
FROM slice reply
JOIN thread_track tt ON reply.track_id = tt.id
JOIN thread caller_t ON tt.utid = caller_t.utid
JOIN process caller_p ON caller_t.upid = caller_p.upid
LEFT JOIN flow f ON reply.id = f.slice_in
LEFT JOIN slice call ON f.slice_out = call.id
LEFT JOIN thread_track stt ON call.track_id = stt.id
LEFT JOIN thread server_t ON stt.utid = server_t.utid
LEFT JOIN process server_p ON server_t.upid = server_p.upid
WHERE caller_p.name = '<进程名>' AND reply.name LIKE 'binder reply%'
  AND reply.dur > 2000000  -- > 2ms
ORDER BY reply.dur DESC LIMIT 20
```

## 时间区间重叠检测

```sql
SELECT a.name, b.name,
  ROUND((MIN(a.ts+a.dur, b.ts+b.dur) - MAX(a.ts, b.ts))/1e6, 2) as overlap_ms
FROM slice a JOIN slice b
  ON b.ts < a.ts + a.dur AND b.ts + b.dur > a.ts
WHERE overlap_ms > 0.5
```

## RSS 内存趋势

```sql
SELECT ts/1e6 as ts_ms, value/1024/1024 as rss_mb
FROM counter c
JOIN counter_track ct ON c.track_id = ct.id
JOIN process_counter_track pct ON ct.id = pct.id
JOIN process p ON pct.upid = p.upid
WHERE p.name = '<进程名>' AND ct.name = 'mem.rss'
ORDER BY ts
```

## CPU 频率查询

```sql
-- 目标进程主线程运行期间的 CPU 频率
WITH main_running AS (
  SELECT ts.ts, ts.dur, ts.cpu
  FROM thread_state ts
  JOIN thread t ON ts.utid = t.utid
  JOIN process p ON t.upid = p.upid
  WHERE p.name = '<进程名>' AND t.is_main_thread = 1
    AND ts.state = 'Running'
    AND ts.ts BETWEEN <start_ns> AND <end_ns>
)
SELECT
  mr.cpu,
  COUNT(*) as running_segments,
  SUM(mr.dur)/1e6 as total_running_ms,
  AVG(mr.dur)/1e6 as avg_segment_ms
FROM main_running mr
GROUP BY mr.cpu ORDER BY total_running_ms DESC
```

```sql
-- 指定 CPU 核心在时间窗口内的频率分布
SELECT c.ts/1e6 as ts_ms, c.value as freq_khz
FROM counter c
JOIN cpu_counter_track ct ON c.track_id = ct.id
WHERE ct.name = 'cpufreq' AND ct.cpu = <cpu_id>
  AND c.ts BETWEEN <start_ns> AND <end_ns>
ORDER BY c.ts
```

判断依据：如果主线程 Running 在小核（低频 CPU）上，且频率未拉满，可能存在调度策略或 Perflock 未生效的问题。

## D-State（IO Block）检测

```sql
-- 目标进程中持续 > 1ms 的 D-State，含唤醒链信息
SELECT ts.ts/1e6 as ts_ms, ts.dur/1e6 as dur_ms,
  t.name as thread_name,
  waker_t.name as waker_thread, waker_p.name as waker_process
FROM thread_state ts
JOIN thread t ON ts.utid = t.utid
JOIN process p ON t.upid = p.upid
LEFT JOIN thread waker_t ON ts.waker_utid = waker_t.utid
LEFT JOIN process waker_p ON waker_t.upid = waker_p.upid
WHERE p.name = '<进程名>' AND ts.state = 'D'
  AND ts.dur > 1000000
  AND ts.ts BETWEEN <start_ns> AND <end_ns>
ORDER BY ts.dur DESC LIMIT 20
```

## IO 请求量统计（block_rq_insert）

```sql
-- 时间窗口内的块设备 IO 请求，需 trace 包含 block ftrace 事件
SELECT ts/1e6 as ts_ms, dur/1e6 as dur_ms,
  EXTRACT_ARG(arg_set_id, 'bytes') as bytes
FROM raw
WHERE name = 'block_rq_insert'
  AND ts BETWEEN <start_ns> AND <end_ns>
ORDER BY ts
```

对比测试机和对比机同阶段的 `bytes` 总和，判断是否存在异常 IO 量。

## SurfaceFlinger 关键 slice 查询

```sql
-- SF 主线程合成相关 slice
SELECT s.name, s.ts/1e6 as ts_ms, s.dur/1e6 as dur_ms
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
JOIN process p ON t.upid = p.upid
WHERE p.name = '/system/bin/surfaceflinger'
  AND s.name IN ('onMessageReceived', 'handleMessageRefresh',
    'HIDL::IComposerClient::executeCommands::client',
    'doComposition', 'postComposition')
  AND s.ts BETWEEN <start_ns> AND <end_ns>
ORDER BY s.ts
```

## HWC Binder 耗时查询

```sql
-- HWC 合成请求的 binder 耗时
SELECT s.name, s.ts/1e6 as ts_ms, s.dur/1e6 as dur_ms
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
WHERE t.name LIKE 'HwBinder%'
  AND s.name IN ('HWCSession::CommitOrPrepare', 'HWCSession::PresentDisplay',
    'HWC::DisplayBufferCommit', 'DisplayBufferCommit', 'DRMAtomicReq::Commit')
  AND s.dur > 2000000  -- > 2ms
  AND s.ts BETWEEN <start_ns> AND <end_ns>
ORDER BY s.dur DESC
```

## 冷启动检测

```sql
SELECT s.ts/1e6 as ts_ms, s.dur/1e6 as dur_ms, s.name
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
WHERE t.name = 'system_server' OR t.tid = 0
  AND s.name LIKE '%bindApplication%'
     OR s.name LIKE '%activityStart%'
     OR s.name LIKE '%launching%'
ORDER BY s.ts
```
