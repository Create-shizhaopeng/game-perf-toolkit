# 响应时延分析 SOP

## 目录

- [分析目标](#分析目标)
- [适用场景](#适用场景)
- [前置检查](#前置检查)
- [分析流程](#分析流程)
  - [确定起止点](#确定起止点)
  - [唤醒链追踪](#唤醒链追踪)
  - [耗时拆解](#耗时拆解)
- [Back/Home 键返回专项](#backhome-键返回专项)
- [常见耗时模式](#常见耗时模式)

## 分析目标

定位用户操作（触摸/按键）到画面响应之间的时延瓶颈，拆解每个阶段的耗时，找到可优化的关键路径。

## 适用场景

- 点按 Back 键返回桌面慢
- 点击 Home 键返回桌面慢
- 点击按钮/图标后界面响应迟缓
- 手势操作（滑动返回、上滑回桌面）响应慢

关键词：响应慢、反应慢、点击延迟、操作卡顿、返回慢

## 前置检查

1. `pa_trace_overview` 获取元数据，确认 trace 包含目标应用和桌面进程
2. 确认 trace 覆盖了操作前后至少 1-2 秒
3. 确认 system_server 进程存在且有 `focused app` 泳道数据

## 分析流程

### 确定起止点

| 操作类型 | 起始点 | 终止点 |
|---------|--------|--------|
| 按键返回 | actionup 事件（抬手） | 返回动画第一帧上屏 |
| 点击启动 | actionup 事件 | 启动动画第一帧上屏 |
| 手势操作 | 手势识别完成 | 过渡动画第一帧上屏 |

**起始点定位**：
```sql
-- 查找 input 事件
SELECT s.ts/1e6 as ts_ms, s.dur/1e6 as dur_ms, s.name
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
WHERE t.name = 'InputReader' OR t.name = 'InputDispatcher'
  AND s.ts BETWEEN <range_start_ns> AND <range_end_ns>
ORDER BY s.ts DESC LIMIT 20
```

**终止点定位**：搜索 `AIDL::java::IRemoteTransition::startAnimation::server`，该 slice 之后桌面绘制的第一帧即为动画起始。

### 唤醒链追踪

从终止点（startAnimation）开始往前逐步追踪唤醒者：

```sql
-- 查找线程的唤醒链
SELECT
  ts.ts/1e6 as ts_ms, ts.dur/1e6 as dur_ms, ts.state,
  t.name as thread, p.name as process,
  waker_t.name as waker_thread, waker_p.name as waker_process
FROM thread_state ts
JOIN thread t ON ts.utid = t.utid
JOIN process p ON t.upid = p.upid
LEFT JOIN thread waker_t ON ts.waker_utid = waker_t.utid
LEFT JOIN process waker_p ON waker_t.upid = waker_p.upid
WHERE p.name = '<进程名>' AND t.name = '<线程名>'
  AND ts.state IN ('S', 'D')
  AND ts.ts BETWEEN <start_ns> AND <end_ns>
ORDER BY ts.ts DESC LIMIT 20
```

典型唤醒链路径：
```
startAnimation ← onTransactionReady ← finishDrawing ← 桌面activityResume
← activityPaused ← inputdispatcher ← systemui ← actionup
```

### 耗时拆解

按阶段拆解总时延：

| 阶段 | 关键字/事件 | 正常耗时 |
|------|-----------|---------|
| input 分发 | inputdispatcher → app | < 5ms |
| app 处理 input | PerformClick → binder 调用 | < 10ms |
| systemui 处理 | ISystemUiProxy → 内部逻辑 | < 15ms |
| system_server 派发 | inputdispatcher 注入 | < 5ms |
| 前台 app pause | activityPause | < 30ms |
| 桌面 resume | activityResume | < 20ms |
| 桌面首帧绘制 | drawFrame → finishDrawing | < 16ms |
| transition 准备 | onTransactionReady | < 10ms |
| 动画回调 | startAnimation | < 5ms |

超出正常耗时的阶段即为瓶颈，需进一步用 `pa_analyze_dimension` 分析。

## Back/Home 键返回专项

**完整流程**（10 步）：

1. 桌面 taskbar 接收触摸事件（`InputFlinger Taskbar touch`）
2. 桌面 actionup → binder 异步调用 systemui（关键字：`ViewRootImpl$ViewRootHandler: View$PerformClick`）
3. systemui 处理（关键字：`AIDL::java::ISystemUiProxy::#45::server`）
4. systemui 内部逻辑
5. systemui → system_server inputdispatcher
6. system_server → 前台 app activityPause
7. activityPaused → 桌面 activityResume
8. 桌面首帧绘制 → `finishDrawing: com.zui.launcher`
9. `onTransactionReady` → `AIDL::java::IRemoteTransition::startAnimation::server`
10. 桌面做返回动画（`animator` 泳道可定位动画范围）

**关键泳道**：
- `focused app`（system_server）：橙色条带，标注应用焦点切换时间点
- `transition`（system_server）：显示 transition 起止
- `animator`（launcher）：显示动画持续范围

## 常见耗时模式

| 模式 | 特征 | 根因方向 |
|------|------|---------|
| systemui 拉起时机晚 | 联想在 actionup 才拉起 systemui（对比 oppo 在 actiondown 时） | 流程设计差异 |
| activityPause 慢 | 前台 app 的 onPause 回调耗时长 | 应用侧优化 |
| 桌面首帧绘制慢 | drawFrame 耗时长，RenderThread 忙 | 渲染管线 / GPU |
| binder 阻塞 | 任一阶段间的 binder 调用耗时 > 5ms | binder 维度分析 |
| BlockIO 阻塞 | D-State 出现在关键路径上 | io 维度分析 |
| 双 activity 启动 | 目标 app 含多个 activity，无法使用 startingwindow | 应用侧，无法优化 |
