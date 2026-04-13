---
scene: jank
display_name: 卡顿分析
priority_dims: [cpu, thread, binder]
secondary_dims: [gpu, sf, io]
optional_dims: [gc, input, lock]
prefetch:
  - tool: detect_jank
    inject_as: jank_frames
  - tool: trace_overview
    inject_as: trace_info
---

# 卡顿分析 SOP

## 目录

- [分析目标](#分析目标)
- [前置检查](#前置检查)
- [分析流程](#分析流程)
- [结果解读指引](#结果解读指引)
- [CPU 维度深度分析](#cpu-维度深度分析)
- [SF 维度分析要点](#sf-维度分析要点)
- [IO 维度深度分析](#io-维度深度分析)
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
4. **全局 CPU 概览**: 调用 `pa_analyze_dimension(cpu)` 获取整体 CPU 使用情况
5. **结果压缩**: 工具返回值已自动压缩为摘要

## 结果解读指引

- severity 为 CRITICAL/HIGH 时，重点关注 root_causes 中排名前 3 的根因
- health_summary 中 CRITICAL/WARNING 的维度需要优先分析
- data_completeness 中的 degraded_dimensions 表示该维度数据来自降级（MCP 不可用），结论可靠性可能降低

## CPU 维度深度分析

当 `pa_analyze_dimension(cpu)` 或线程状态分布显示 Running 占比高时，需检查 CPU 频率和核心分配：

1. **查看主线程运行核心**：确认是否调度到大核（性能核心）
2. **查看核心频率**：确认频率是否在卡顿窗口内被限制
3. **判断依据**：
   - Running 高 + 小核/低频 → 调度策略或 Perflock 未生效
   - Running 高 + 大核/满频 → 应用代码本身耗时（查 hotspot）
   - Runnable 高 → CPU 争抢严重，需查看全局 CPU 使用率
4. **工具**：`pa_analyze_dimension(cpu)` 获取全局概况，`pa_execute_sql` 查 CPU 频率

SQL 查询见 [sql-patterns.md — CPU 频率查询](../sql-patterns.md#cpu-频率查询)。
设备调优见 [ref/device-tuning.md](../ref/device-tuning.md)。

## SF 维度分析要点

当 `pa_analyze_dimension(sf)` 报告异常时，重点关注以下 SurfaceFlinger 关键 slice 和泳道：

**SF 进程关键泳道**（直接在 Perfetto UI 可见）：
- `FrameMissed` — 丢帧标记
- `GpuFrameMissed` — GPU 导致的丢帧
- `HwcFrameMissed` — HWC 导致的丢帧
- `hasClientComposition` — 是否有 GPU 合成（1 = 有）
- `VSYNC-app` / `VSYNC-sf` — VSync 信号
- `Total Buffer Size` — buffer 总量

**SF 主线程关键 slice**：
- `onMessageReceived` — 消息入口
- `handleMessageRefresh` — 帧合成（耗时异常时重点分析）
- `HIDL::IComposerClient::executeCommands::client` — HWC binder 调用
- `doComposition` / `postComposition` — 合成过程

**HWC 侧关键 slice**（在 `vendor.qti.hardware.display.composer-service` 进程中）：
- `HWCSession::CommitOrPrepare` / `HWCSession::PresentDisplay`
- `HWC::DisplayBufferCommit` / `DRMAtomicReq::Commit`

当 `handleMessageRefresh` 耗时异常 → 检查内嵌的 HWC binder 调用是否超时。
已知根因模式：[HWC Binder 超时](../patterns/root-cause-patterns.md#hwc-binder-超时)

## IO 维度深度分析

当 `pa_analyze_dimension(io)` 报告 D-State 异常时，按以下步骤深入：

1. 确认 D-State 持续时长和受影响线程
2. 如需定位具体阻塞文件、判断 IO 竞争或高负载影响 → 参见 [io-block-analysis.md](io-block-analysis.md)

> IO Block 分析可能需要 trace 包含 f2fs/block ftrace 事件和设备 root 权限，详见 [环境准备](../ref/environment-setup.md#ftrace-io-配置)。

## 常见卡顿模式

| 模式 | 特征 | 维度关联 | 深入参考 |
| --- | --- | --- | --- |
| 主线程耗时 | cpu 维度显示 Running 时间长 | cpu, thread, hotspot | |
| Binder 阻塞 | binder 维度显示慢 Binder 调用 | binder | |
| GPU 瓶颈 | gpu 维度显示 GPU 完成时间超标 | gpu, sf | |
| GC 停顿 | gc 维度检测到长时间 GC | gc | |
| IO 阻塞 | io 维度显示 IO 等待（D-State） | io | [IO Block SOP](io-block-analysis.md) |
| 锁竞争 | lock 维度检测到长时间等待 | lock, thread | |
| SF 合成超时 | sf 维度显示合成超时 | sf | 见上方 SF 维度分析 |
| HWC 超时 | sf 维度异常 + HWC binder 耗时高 | sf | [HWC 模式](../patterns/root-cause-patterns.md#hwc-binder-超时) |
| 输入延迟 | input 维度显示输入处理慢 | input | |
| CPU 抢占 | 目标线程被高优线程抢占 | cpu, thread | [CPU 抢占模式](../patterns/root-cause-patterns.md#cpu-调度抢占) |

## 深入分析资源

分析过程中需要深入了解时，调用 `pa_read_knowledge` 获取知识资产:
- 根因模式库: `pa_read_knowledge("patterns/root-cause-patterns.md")`（卡顿相关章节含 VSync 检测全误报、IO Block（文件未 pin / IO 竞争）、HWC Binder 超时、CPU 调度抢占）
- SQL 查询模板: `pa_read_knowledge("sql-patterns.md")`
