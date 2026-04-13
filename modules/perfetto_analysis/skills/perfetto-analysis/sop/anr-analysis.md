---
scene: anr
display_name: ANR分析
priority_dims: [thread, binder, lock]
secondary_dims: [cpu, io]
optional_dims: [gc, input]
prefetch:
  - tool: trace_overview
    inject_as: trace_info
---

# ANR 分析 SOP

## 目录

- [分析目标](#分析目标)
- [ANR 类型速查](#anr-类型速查)
- [前置检查](#前置检查)
- [分析流程](#分析流程)
  - [Step 1: 确认 ANR 类型和时间点](#step-1-确认-anr-类型和时间点)
  - [Step 2: 定位主线程阻塞状态](#step-2-定位主线程阻塞状态)
  - [Step 3: 按阻塞类型深入分析](#step-3-按阻塞类型深入分析)
  - [Step 4: 关联日志和堆栈](#step-4-关联日志和堆栈)
- [常见根因模式](#常见根因模式)
- [输出模板](#输出模板)
- [补充数据源](#补充数据源)

## 分析目标

检测 Perfetto trace 中的 ANR（Application Not Responding）事件，定位根因并提供修复建议。

## ANR 类型速查

| ANR 类型 | 关键词 | 超时阈值 | 常见原因 |
|---------|-------|---------|---------|
| Input dispatching timed out | MotionEvent/KeyEvent | 5s | 主线程阻塞无法处理输入 |
| Service timeout | ANR executing service | 前台20s/后台200s | Service.onStartCommand 执行超时 |
| Broadcast timeout | BroadcastReceiver | 前台10s/后台60s | onReceive 执行超时 |
| ContentProvider timeout | ContentProvider | 10s | query/insert 等操作超时 |

## 前置检查

1. **确认数据完整性**：
   - `pa_trace_overview` 确认 trace 包含目标进程
   - 检查 trace 时间范围是否覆盖 ANR 时间点
   - 如有 ANR 日志（am_anr），提取精确时间戳

2. **计算 trace 内相对时间**：
   - 从 ANR 日志获取系统时间（如 20:20:04.886）
   - 从 trace 中查询 slice/thread_state 的时间范围
   - 建立系统时间与 trace 时间戳的映射关系

## 分析流程

### Step 1: 确认 ANR 类型和时间点

1. 如有 `android_anrs` 表，优先查询：
   ```sql
   SELECT * FROM android_anrs
   ```

2. 若无 ANR 表，从日志提取关键信息：
   - ANR 类型（Input/Service/Broadcast/ContentProvider）
   - 触发时间和等待时长
   - 相关 Activity/Service 名称

3. 转换为 trace 内时间戳后，定义分析窗口（ANR 时间点前 5-10s）

### Step 2: 定位主线程阻塞状态

查询主线程在 ANR 窗口内的长时间睡眠：

```sql
SELECT t.tid, t.name, ts.state, ts.ts/1e9 as ts_s, ts.dur/1e6 as dur_ms,
       ts.blocked_function, ts.waker_utid
FROM thread_state ts
JOIN thread t ON ts.utid = t.utid
WHERE t.tid = <主线程tid>
  AND ts.state = 'S'
  AND ts.dur > 100e6  -- >100ms
  AND ts.ts >= <anr_time - 10s>
ORDER BY ts.dur DESC
LIMIT 20
```

**关键指标**：
- 连续 Sleep > 5s（Input ANR 阈值）
- 连续 Sleep > 10-20s（Service/Broadcast ANR 阈值）
- D-State（IO 阻塞）占比 > 5%

### Step 3: 按阻塞类型深入分析

根据主线程状态分布，选择分析路径：

| 阻塞类型 | 识别特征 | 深入分析 |
|---------|---------|---------|
| **信号等待** | blocked_function 含 sigsuspend/futex | 查看关联线程状态，定位等待的信号源 |
| **Binder 阻塞** | 含 binder_thread_read/binder_wait | `pa_analyze_dimension("binder")` 查看对端 |
| **锁竞争** | futex_wait_queue + monitor_contention | `thread_contention_analyzer` 定位持锁线程 |
| **IO 阻塞** | D-State + sched_blocked_reason | 查看 IO 操作和文件路径 |
| **游戏引擎挂起** | 多个引擎线程同时停止 | 对比关键线程的最后活动时间 |

**游戏引擎挂起检测 SQL**：

```sql
SELECT t.tid, t.name,
       MIN(ts.ts)/1e9 as first_ts_s,
       MAX(ts.ts)/1e9 as last_ts_s,
       SUM(CASE WHEN ts.state = 'S' THEN ts.dur ELSE 0 END)/1e9 as total_sleep_s
FROM thread_state ts
JOIN thread t ON ts.utid = t.utid
JOIN process p ON t.upid = p.upid
WHERE p.pid = <pid>
  AND (t.name LIKE 'Unity%' OR t.name LIKE '%Main%' OR t.tid = <主线程tid>)
GROUP BY t.tid, t.name
ORDER BY last_ts_s DESC
```

若多个关键线程的 `last_ts_s` 相同且之后都进入无限期睡眠，说明存在全局同步问题。

### Step 4: 关联日志和堆栈

1. **ANR dump 堆栈分析**：
   - 检查主线程的 native 堆栈（libc、libunity、libgame 等）
   - 识别同步原语：sigsuspend、pthread_cond_wait、futex、sem_wait
   - 多个线程卡在同一代码路径暗示全局锁/屏障问题

2. **Waiting Channels 分析**：
   - `sigsuspend` - 等待信号
   - `futex_wait_queue` - 等待 mutex/condition
   - `binder_thread_read` - 等待 Binder 响应
   - `do_epoll_wait` - 正常的事件循环等待
   - `ptrace_stop` - 被调试器暂停

3. **系统日志关联**：
   - 检查 ANR 前后的 lowmemorykiller、GC、thermal throttling 日志
   - 检查 InputDispatcher 日志确认输入事件分发情况

## 常见根因模式

| 模式 | 识别特征 | 根因 |
|-----|---------|-----|
| **单点 Binder 阻塞** | 主线程 binder_wait + 对端进程慢响应 | 同步 Binder 调用阻塞，对端服务响应慢 |
| **锁竞争死锁** | 多线程 futex_wait + monitor_contention | synchronized 块导致互相等待 |
| **游戏引擎全局挂起** | 所有引擎线程同时 sigsuspend | 引擎内部同步机制异常 |
| **IO 阻塞** | 主线程 D-State + 文件/网络操作 | 主线程执行同步 IO |
| **GC 暂停** | GC STW 时间 + 主线程 Suspended | 频繁或长时间 GC 停顿 |
| **内存压力** | lowmemorykiller 触发 + 高 RSS | 系统内存紧张导致调度延迟 |

## 输出模板

```markdown
## ANR 分析结论

### 基本信息
- **ANR 类型**: <Input/Service/Broadcast/ContentProvider>
- **触发时间**: <系统时间> / <trace 内时间戳>
- **进程**: <包名> (pid: <pid>)
- **等待事件**: <事件类型和详情>

### 根因定位
1. **[CRITICAL/HIGH/MEDIUM] <根因描述>**
   - 证据: <数据支撑>
   - 阻塞时长: <duration>
   - 影响线程: <线程列表>

### 时间线
```
<时间戳1> - <事件1>
<时间戳2> - <事件2>
...
```

### 关键数据
| 维度 | 指标 | 值 | 状态 |
|------|-----|-----|------|
| 主线程状态 | 最大连续 Sleep | <ms> | <状态> |
| ... | ... | ... | ... |

### 排查建议
1. <建议1>
2. <建议2>
```

## 补充数据源

若 trace 信息不足，可请求用户提供：

| 数据 | 获取方式 | 用途 |
|-----|---------|-----|
| ANR trace 文件 | `/data/anr/` 目录 | 完整的 ANR dump 堆栈 |
| mainlog | `adb logcat -d` | 系统日志上下文 |
| events log | `adb logcat -b events -d` | am_anr 事件详情 |
| tombstone | `/data/tombstones/` | Native crash 堆栈（若伴随崩溃）|
| 符号表 | 开发者提供 | 定位 libunity.so 等 so 的具体函数 |

**建议的 trace 采集配置**（用于复现分析）：
- 包含 `android.monitor_contention` 数据源
- 包含 `linux.ftrace` 的 `sched_blocked_reason` 事件
- 采集时长覆盖 ANR 前后各 10s

## 深入分析资源

分析过程中需要深入了解时，调用 `pa_read_knowledge` 获取知识资产:
- 根因模式库: `pa_read_knowledge("patterns/root-cause-patterns.md")`
- SQL 查询模板: `pa_read_knowledge("sql-patterns.md")`
