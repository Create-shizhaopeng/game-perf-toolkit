# ANR 分析 SOP

## 目录

- [分析目标](#分析目标)
- [前置检查](#前置检查)
- [分析流程](#分析流程)
- [结果解读](#结果解读)

## 分析目标

检测 Perfetto trace 中的 ANR（Application Not Responding）事件，定位根因并提供修复建议。

## 前置检查

1. 调用 `pa_trace_overview` 确认 trace 包含目标进程
2. 确认用户关注的是 ANR 问题（而非卡顿或内存）

## 分析流程

1. 调用 `pa_analyze_anr` 执行 ANR 检测和根因分析
2. 如果检测到 ANR：
   - 查看 root_cause 中的详细分析
   - 可补充调用 `pa_analyze_dimension("thread")` 查看线程状态
   - 可补充调用 `pa_analyze_dimension("binder")` 查看 Binder 阻塞
3. 如果未检测到 ANR：
   - 告知用户 trace 中未发现 ANR 事件
   - 建议检查是否使用了正确的 trace

## 结果解读

- `anr_detected` 为 null 表示 MCP 工具不可用或 trace 不包含 ANR 数据
- `root_cause` 包含详细的 ANR 触发原因分析
- ANR 通常由主线程长时间阻塞引起，关注线程状态和 Binder 调用
