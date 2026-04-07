# IO Block 分析 SOP

## 目录

- [分析目标](#分析目标)
- [适用场景](#适用场景)
- [前置条件](#前置条件)
- [分析流程](#分析流程)
  - [Step 1：定位 D-State 区域](#step-1定位-d-state-区域)
  - [Step 2：确定阻塞文件](#step-2确定阻塞文件)
  - [Step 3：判断 IO 竞争](#step-3判断-io-竞争)
  - [Step 4：判断高负载影响](#step-4判断高负载影响)
- [常见 IO Block 模式](#常见-io-block-模式)

## 分析目标

定位线程进入 D-State（Uninterruptible Sleep IO）的根因，区分文件读取瓶颈、IO 竞争、CPU 高负载等不同原因。

## 适用场景

- 卡顿分析中 `pa_analyze_dimension(io)` 报告 D-State 异常
- 冷启动过程中线程被 IO 阻塞
- 用户报告操作卡顿，thread 维度显示大量 D-State

## 前置条件

1. Trace 中需包含 IO 相关 ftrace 事件（f2fs、block 层），详见 [ref/environment-setup.md](../ref/environment-setup.md#ftrace-io-配置)
2. 如需映射具体文件，需要设备 root 权限获取 inode 映射表
3. 获取 trace 元数据：`pa_trace_overview`

## 分析流程

### Step 1：定位 D-State 区域

使用 SQL 查询目标线程的 D-State（IO 阻塞）：

```sql
SELECT ts/1e6 as ts_ms, dur/1e6 as dur_ms, state,
  waker_t.name as waker_thread, waker_p.name as waker_process
FROM thread_state ts
JOIN thread t ON ts.utid = t.utid
JOIN process p ON t.upid = p.upid
LEFT JOIN thread waker_t ON ts.waker_utid = waker_t.utid
LEFT JOIN process waker_p ON waker_t.upid = waker_p.upid
WHERE p.name = '<进程名>' AND ts.state = 'D'
  AND ts.dur > 1000000  -- > 1ms
  AND ts.ts BETWEEN <start_ns> AND <end_ns>
ORDER BY ts.dur DESC LIMIT 20
```

工具：`pa_execute_sql` 或参考 [sql-patterns.md](../sql-patterns.md#阻塞链追踪waker)

### Step 2：确定阻塞文件

当 trace 包含 f2fs/erofs 事件时，可通过 inode 映射定位具体文件：

1. **查找 readpages 事件**：在 systrace 格式中搜索 `<tid>.*erofs_readpages` 或 `f2fs_readpage`
2. **提取 inode (nid)**：从匹配事件中获取 `nid` 字段
3. **获取 inode 映射表**（需 root）：
```bash
adb root && adb shell \
  "find /system /vendor /product /data -exec stat -c '%d %i %s %n' {} \;" \
  > /sdcard/inode.txt
adb pull /sdcard/inode.txt
```
4. **匹配文件**：用 nid 在 `inode.txt` 中搜索，第三列为文件大小

> 此步骤需要 systrace 格式文本和设备 root，在纯 Perfetto 分析场景下可能无法执行，标注为"需设备配合"。

### Step 3：判断 IO 竞争

确认同一时间窗口内是否有其他线程在大量 IO 操作：

```sql
-- 统计时间窗口内各进程的 D-State 总时长
SELECT p.name, t.name as thread_name,
  COUNT(*) as d_state_count,
  SUM(ts.dur)/1e6 as total_d_ms
FROM thread_state ts
JOIN thread t ON ts.utid = t.utid
JOIN process p ON t.upid = p.upid
WHERE ts.state = 'D'
  AND ts.ts BETWEEN <start_ns> AND <end_ns>
GROUP BY p.name, t.name
ORDER BY total_d_ms DESC LIMIT 20
```

如果 trace 包含 `block_rq_insert` 事件，可进一步量化：

```sql
SELECT ts/1e6 as ts_ms, dur/1e6 as dur_ms,
  EXTRACT_ARG(arg_set_id, 'bytes') as bytes
FROM raw
WHERE name = 'block_rq_insert'
  AND ts BETWEEN <start_ns> AND <end_ns>
ORDER BY ts
```

对比测试机和对比机同阶段的 IO 请求量（`bytes` 总和），判断是否存在异常 IO。

### Step 4：判断高负载影响

追踪 D-State 的唤醒链，判断是 IO 硬件慢还是 CPU 负载延迟：

1. **查看 waker 线程状态**：Step 1 查询结果中的 `waker_thread`
2. **判断依据**：
   - waker 线程长时间 Runnable → **CPU 负载高**，IO 完成中断信号延迟送达
   - waker 线程正常 Running → **IO 硬件/驱动层面慢**

```sql
-- 检查 waker 线程在 IO block 期间的 Runnable 时间
SELECT ts.state, SUM(ts.dur)/1e6 as total_ms
FROM thread_state ts
JOIN thread t ON ts.utid = t.utid
WHERE t.name = '<waker_thread_name>'
  AND ts.ts BETWEEN <io_block_start_ns> AND <io_block_end_ns>
GROUP BY ts.state
```

## 常见 IO Block 模式

| 模式 | 特征 | 验证方法 |
|------|------|----------|
| 文件未 pin 到内存 | 系统文件被回收后需从磁盘重新读取 | 对比 pinner 白名单，检查文件是否在 `mlock` 中 |
| IO 竞争 | 同时间窗口多线程大量 IO 操作 | Step 3 的 D-State 统计和 block_rq_insert 对比 |
| CPU 高负载导致 IO 完成延迟 | waker 线程 Runnable 时间长 | Step 4 的唤醒链分析 |
| 存储硬件/驱动慢 | waker 线程 Running 正常，IO 时间仍长 | 排除软件因素后，对比不同设备的 IO 延迟 |

> **常见解决方案**：将高频读取的系统文件加入 pinner 白名单，`mlock` 到内存防止被回收。
