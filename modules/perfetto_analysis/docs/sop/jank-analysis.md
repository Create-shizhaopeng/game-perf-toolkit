# 卡顿分析 SOP

## 目录

- [分析目标](#分析目标)
- [前置检查](#前置检查)
- [分析流程](#分析流程)
- [结果解读指引](#结果解读指引)
- [常见卡顿模式](#常见卡顿模式)

## 分析目标

识别 Perfetto trace 中的卡顿帧，定位根因维度，输出可操作的优化建议。

## 前置检查

1. 调用 `pa_trace_overview` 获取 trace 元数据
2. 确认 trace 包含目标进程
3. 确认 trace 时长和帧数合理
4. 如果 trace 包含多个场景（如冷启动 + 正常使用），确定用户关注的时间范围

## 分析流程

1. **卡顿帧检测**: 调用 `pa_detect_jank`（如有 time_range 则传入）
2. **确定分析窗口**: 每个卡顿帧有 window_start_ms 和 window_end_ms
3. **逐维度分析**: 对每个卡顿帧的时间窗口，逐个调用 `pa_analyze_dimension`：
  - 必查维度: cpu, thread, binder（与卡顿根因最相关）
  - 推荐维度: gpu, sf, io（影响渲染管线）
  - 辅助维度: gc, input, lock（特定场景才有影响）
  - MCP 增强: hotspot（主线程热点函数，仅 MCP 可用）
4. **全局 CPU 概览**: 调用 `pa_cpu_overview` 获取整体 CPU 使用情况
5. **结果压缩**: 调用 `pa_compress_results` 生成摘要

## 结果解读指引

- severity 为 CRITICAL/HIGH 时，重点关注 root_causes 中排名前 3 的根因
- health_summary 中 CRITICAL/WARNING 的维度需要优先分析
- data_completeness 中的 degraded_dimensions 表示该维度数据来自降级（MCP 不可用），结论可靠性可能降低

## 常见卡顿模式


| 模式                | 特征                     | 维度关联                 |
| ----------------- | ---------------------- | -------------------- |
| 主线程耗时             | cpu 维度显示 Running 时间长   | cpu, thread, hotspot |
| Binder 阻塞         | binder 维度显示慢 Binder 调用 | binder               |
| GPU 瓶颈            | gpu 维度显示 GPU 完成时间超标    | gpu, sf              |
| GC 停顿             | gc 维度检测到长时间 GC         | gc                   |
| IO 阻塞             | io 维度显示 IO 等待          | io                   |
| 锁竞争               | lock 维度检测到长时间等待        | lock, thread         |
| SurfaceFlinger 延迟 | sf 维度显示合成超时            | sf                   |
| 输入延迟              | input 维度显示输入处理慢        | input                |


