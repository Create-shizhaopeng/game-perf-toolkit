# 输入时延分析 SOP

## 目录

- [分析目标](#分析目标)
- [适用场景](#适用场景)
- [前置检查](#前置检查)
- [分析流程](#分析流程)
  - [端到端时延拆解](#端到端时延拆解)
  - [各阶段定位方法](#各阶段定位方法)
- [常见时延模式](#常见时延模式)
- [优化方向参考](#优化方向参考)

## 分析目标

测量 input 事件从硬件产生到画面上屏的端到端时延，定位各阶段耗时瓶颈。

## 适用场景

- 手写笔书写有延迟感
- 触控滑动响应慢
- 拖拽操作不跟手
- 游戏操作输入延迟

关键词：笔写时延、触控延迟、不跟手、输入延迟、input latency

## 前置检查

1. `pa_trace_overview` 确认 trace 包含目标应用
2. 确认 trace 中有 inputreader/inputdispatcher 线程数据
3. 确认 SurfaceFlinger 进程可见
4. 对于笔写场景，确认应用进程中有触控事件处理的 slice

## 分析流程

### 端到端时延拆解

```
inputreader → inputdispatcher → app 消费 → app 绘制 → buffer 入队
→ SF 消费 buffer → HWC 合成 → 上屏
```

总时延 = 各阶段耗时之和。

| 阶段 | 说明 | 正常耗时 |
|------|------|---------|
| inputreader | 硬件事件到内核 | < 1ms |
| inputdispatcher 分发 | 事件路由到目标窗口 | < 2ms |
| app 消费 input | 应用处理触摸事件 | < 5ms |
| app 绘制 | RenderThread 执行绘制 | < 16ms (1 VSync) |
| buffer 入队 | dequeueBuffer → queueBuffer | < 1ms |
| SF 消费 | vsync-sf 周期消费 buffer | 0-16ms |
| HWC 合成上屏 | 硬件合成 | < 4ms |

### 各阶段定位方法

**1. inputreader → app 消费**

```sql
-- 查找 inputreader 中的事件
SELECT s.ts/1e6 as ts_ms, s.dur/1e6 as dur_ms, s.name
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
WHERE t.name = 'InputReader'
ORDER BY s.ts DESC LIMIT 30
```

在应用进程中找到对应的 input 消费 slice，记录 input id 进行匹配。

**2. buffer 队列状态**

查看目标应用的 buffer counter track。buffer count 变化规律：
- app 绘制完成 → count +1
- SF 消费 → count -1
- count > 1 → 存在 buffer 堆积，当前帧需等到下一个 vsync-sf

```sql
-- 查看 buffer 状态变化
SELECT c.ts/1e6 as ts_ms, c.value as buffer_count
FROM counter c
JOIN counter_track ct ON c.track_id = ct.id
WHERE ct.name LIKE '%BufferQueueProducer%' OR ct.name LIKE '%buffer%'
ORDER BY c.ts
```

**3. SF 消费到上屏**

在 SurfaceFlinger 进程中查看 vsync-sf 信号和帧合成时序。关键关注：
- vsync-sf 信号周期是否稳定
- buffer 被消费到 HWC 提交的间隔

## 常见时延模式

| 模式 | 特征 | 根因 |
|------|------|------|
| buffer 堆积 | buffer count 持续 > 1 | app 绘制太快或 SF 消费慢 |
| SF 周期错过 | buffer 在 vsync-sf 边界后入队 | app 绘制完成时间晚于 SF 截止点 |
| app 处理慢 | input 消费到绘制开始间隔长 | 应用逻辑复杂 |
| 输入事件延迟分发 | inputdispatcher 到 app 消费间隔大 | 系统负载高 |

## 优化方向参考

- **单帧方案**（singleBuffer）：使 buffer 及时消费，在 `singleBuffer_whitelist.txt` 中添加目标 activity
- **笔写预测**：应用层预测笔迹轨迹，减少感知延迟
- **RenderThread 优化**：减少绘制耗时，控制在 1 VSync 周期内
- **CPU 提频**：确保绘制期间 CPU 频率足够
