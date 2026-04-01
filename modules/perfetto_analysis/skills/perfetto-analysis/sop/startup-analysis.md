# 启动分析 SOP

## 目录

- [分析目标](#分析目标)
- [适用场景](#适用场景)
- [前置检查](#前置检查)
- [分析流程](#分析流程)
  - [冷启动分析](#冷启动分析)
  - [热启动分析](#热启动分析)
  - [启动响应时延（图标到动画）](#启动响应时延图标到动画)
  - [重启解锁分析](#重启解锁分析)
- [启动期间 CPU 状态检查](#启动期间-cpu-状态检查)
- [关键指标](#关键指标)
- [常见耗时模式](#常见耗时模式)

## 分析目标

测量应用启动各阶段耗时，定位冷/热启动、启动响应、重启解锁场景的性能瓶颈。

## 适用场景

- 应用冷启动慢
- 应用热启动闪白屏
- 点击图标到启动动画出现慢（启动响应）
- 重启后解锁桌面慢/空白

关键词：启动慢、冷启动、热启动、TTID、TTFD、解锁慢、白屏

## 前置检查

1. `pa_trace_overview` 确认 trace 包含目标应用和 system_server
2. 对于冷启动，确认 trace 起始时间早于应用进程创建
3. 对于重启解锁，必须使用专用抓取工具（标准方法在重启后会断开）

## 分析流程

### 冷启动分析

```sql
-- Perfetto stdlib 查询（如可用）
SELECT * FROM android_startups WHERE package = '<包名>'

-- 手动查找启动标记
SELECT s.ts/1e6 as ts_ms, s.dur/1e6 as dur_ms, s.name
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
WHERE s.name LIKE '%bindApplication%'
   OR s.name LIKE '%activityStart%'
   OR s.name LIKE '%launching%'
   OR s.name LIKE '%reportFullyDrawn%'
ORDER BY s.ts
```

关键时间节点：
1. `startActivityInner` → 启动请求发出
2. `bindApplication` → 进程创建
3. `activityStart` / `activityResume` → Activity 生命周期
4. 首帧绘制完成 → TTID
5. `reportFullyDrawn` → TTFD

### 热启动分析

热启动不创建新进程，直接走 activityResume。在 `focused app` 泳道中查看焦点切换时间。

注意：如果应用由多个 activity 组成（如 Settings），则无法使用 startingwindow 快速显示，需等待应用第一帧真窗，耗时更长。

### 启动响应时延（图标到动画）

**起始点**：actionup（点击图标抬手）
**终止点**：启动动画第一帧上屏

定位步骤：
1. `focused app` 泳道确认焦点切换窗口
2. launcher `animator` 泳道定位动画范围
3. 搜索 `AIDL::java::IRemoteTransition::startAnimation::server` 确认动画起始
4. 从 startAnimation 往前追踪唤醒链，定位各阶段耗时

### 重启解锁分析

入口关键字：`keyguardgoingaway`

从此 tag 往前追踪唤醒逻辑，主要耗时环节：

| 环节 | 关键字 | 说明 |
|------|--------|------|
| 系统初始化 | `onBootCompleted` | 存储管理/HAL 就绪 |
| 长 binder 调用 | system_server ↔ keyguard | 解锁流程 binder 耗时 |
| 桌面初始化 | launcher 主线程 | 插件/图标绑定 |

首次快速解锁时，解锁流程被系统初始化阻塞是常见现象（等待 `onBootCompleted`）。

## 启动期间 CPU 状态检查

当主线程 Running 时间占比较高时（>40%），需进一步检查 CPU 是否为瓶颈：

1. **查询主线程运行在哪个核心**：确认是否调度到大核
2. **查询核心频率**：确认是否拉满频率
3. **判断依据**：
   - 主线程在小核 + 频率未拉满 → CPU 调度策略问题，尝试 Perflock 提频验证
   - 主线程在大核 + 频率已拉满 → 代码本身耗时，需优化应用初始化逻辑
   - Runnable 占比 > 10% → CPU 争抢严重，查看同时段其他高负载进程

SQL 查询见 [sql-patterns.md — CPU 频率查询](../sql-patterns.md#cpu-频率查询)。
设备调优方法见 [ref/device-tuning.md](../ref/device-tuning.md)。

## 关键指标

| 指标 | 说明 | 参考值 |
|------|------|--------|
| TTID | Time To Initial Display，首帧显示 | < 500ms（冷启动） |
| TTFD | Time To Fully Drawn，完全绘制 | 应用定义 |
| 启动响应 | 点击到动画出现 | < 200ms |
| 解锁时延 | 滑动到桌面显示 | < 1s（非首次） |

## 常见耗时模式

| 模式 | 特征 | 根因方向 |
|------|------|---------|
| BlockIO 阻塞 | D-State 出现在 startActivity 路径 | 磁盘读 apk/资源，io 维度分析 |
| 多 activity 启动 | 无法用 startingwindow，需等真窗 | 应用架构，无法优化 |
| 桌面 getResources 竞争 | launcher-loader 与 startActivity 同时读 apk | 桌面侧改用缓存图标 |
| 重启初始化未完成 | onBootCompleted 前解锁被阻塞 | 延迟 2s 解锁可规避 |
| 桌面 widget 加载慢 | launcher 主线程初始化耗时长 | 减少 widget 数量 |
