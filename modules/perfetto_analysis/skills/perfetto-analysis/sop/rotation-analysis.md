---
scene: rotation
display_name: 转屏分析
priority_dims: [thread, sf]
secondary_dims: [cpu, gpu]
optional_dims: [binder, input]
prefetch:
  - tool: trace_overview
    inject_as: trace_info
---

# 转屏/配置变更分析 SOP

## 目录

- [分析目标](#分析目标)
- [适用场景](#适用场景)
- [前置检查](#前置检查)
- [分析流程](#分析流程)
  - [确定转屏时间窗口](#确定转屏时间窗口)
  - [唤醒链追踪（传感器到转屏决策）](#唤醒链追踪传感器到转屏决策)
  - [应用 configchange 耗时](#应用-configchange-耗时)
  - [转屏动画耗时](#转屏动画耗时)
- [耗时拆解](#耗时拆解)
- [常见耗时模式](#常见耗时模式)

## 分析目标

定位屏幕旋转（或其他配置变更）从传感器触发到动画完成的耗时瓶颈。

## 适用场景

- 屏幕旋转响应慢
- 横竖屏切换动画卡顿
- 折叠屏展开/折叠后界面刷新慢

关键词：旋转慢、转屏、横竖屏、配置变更、configchange

## 前置检查

1. `pa_trace_overview` 确认 trace 包含 system_server 和前台应用
2. 确认 trace 覆盖转屏操作前后各 1-2 秒
3. 确认 system_server 中有 `transition` 泳道数据

## 分析流程

### 确定转屏时间窗口

在 system_server 中：
- `transition` tag 有独立泳道，显示转屏 transition 的起止时间
- `focused app` 泳道标注转屏时的前台应用

```sql
-- 搜索转屏相关 slice
SELECT s.ts/1e6 as ts_ms, s.dur/1e6 as dur_ms, s.name
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
JOIN process p ON t.upid = p.upid
WHERE p.name = 'system_server'
  AND (s.name LIKE '%updateGlobalConfiguration%'
       OR s.name LIKE '%transition%'
       OR s.name LIKE '%configChanged%')
ORDER BY s.ts
```

### 唤醒链追踪（传感器到转屏决策）

从 `updateGlobalConfiguration` slice 往前追踪唤醒链：

```
updateGlobalConfiguration ← system_server 内部线程
← AlarmManager / HandlerManager ← sensorservice
← 硬件传感器
```

使用唤醒链 SQL（见 sql-patterns.md）逐级追踪 waker。

### 应用 configchange 耗时

从 `updateGlobalConfiguration` 到转屏动画之间，需等待前台应用完成 configchange：

1. 在前台应用进程主线程中查找 `configChanged` / `onConfigurationChanged` 相关 slice
2. 应用完成 configchange 后会绘制新布局的第一帧
3. RenderThread 帧提交完成后通知系统

```sql
-- 查找应用的 configchange 处理
SELECT s.ts/1e6 as ts_ms, s.dur/1e6 as dur_ms, s.name
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
JOIN process p ON t.upid = p.upid
WHERE p.name = '<前台应用包名>'
  AND (s.name LIKE '%configChange%' OR s.name LIKE '%onConfiguration%')
ORDER BY s.ts
```

### 转屏动画耗时

应用首帧完成后系统开始转屏动画，可在 system_server 的 `transition` 泳道确认动画时长。

## 耗时拆解

| 阶段 | 正常耗时 | 定位方法 |
|------|---------|---------|
| 传感器 → sensorservice | < 5ms | 唤醒链末端 |
| sensorservice → updateGlobalConfiguration | < 10ms | 唤醒链 |
| updateGlobalConfiguration 处理 | < 10ms | slice dur |
| 应用 configchange | 取决于应用复杂度 | 应用主线程 slice |
| 应用首帧绘制 | < 16ms | RenderThread |
| 转屏动画 | 200-300ms（设计值） | transition 泳道 |

## 常见耗时模式

| 模式 | 特征 | 根因方向 |
|------|------|---------|
| 应用 configchange 慢 | 应用主线程 configchange slice 耗时长 | 应用布局复杂/资源重加载 |
| CPU 频率不足 | 转屏期间 CPU 未提频 | 尝试拉满 CPU 频率验证 |
| 传感器延迟 | sensorservice 到 updateGlobalConfiguration 间隔大 | 硬件/驱动层 |
| 多窗口模式 | 多个应用需要同时处理 configchange | 系统架构限制 |

## 深入分析资源

分析过程中需要深入了解时，调用 `pa_read_knowledge` 获取知识资产:
- 根因模式库: `pa_read_knowledge("patterns/root-cause-patterns.md")`
- SQL 查询模板: `pa_read_knowledge("sql-patterns.md")`
