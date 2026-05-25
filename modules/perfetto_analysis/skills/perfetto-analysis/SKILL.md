---
name: perfetto-analysis
description: >-
  Perfetto trace 全场景性能分析。通过 pa_execute_sql 执行 YAML 技能库中的
  PerfettoSQL 查询，覆盖卡顿/ANR/内存/启动/CPU/线程/输入时延/IO/渲染管线等场景。
  当用户提到 Perfetto、.perfetto-trace、trace 分析、卡顿、丢帧、jank、fps、
  帧率、ANR、内存泄漏、启动慢、CPU 占用、线程阻塞、不跟手时触发此技能。
---

# Perfetto 性能分析

## 可用工具

### pa_execute_sql(trace_path, sql)

执行 PerfettoSQL 查询的唯一工具。所有分析能力通过此工具 + YAML 技能库实现。

> **重要**: 了解 execute_sql 的用法和返回结构时，执行 `python scripts/sql_executor.py --help`，禁止阅读源码。

**参数**:
- `trace_path` (string, required): Perfetto trace 文件路径（.perfetto-trace）
- `sql` (string, required): PerfettoSQL 查询语句

**返回结构**:
```json
{
  "success": true,
  "rows": [{"col1": "val1", "col2": "val2"}, ...],
  "row_count": 10,
  "error": null
}
```

**使用规则**:
1. SQL 来自 YAML 技能文件的 `steps[].sql` 字段
2. 先将 SQL 中的 `${variable}` 替换为实际参数值再调用
3. `${var|default}` 语法：`|` 后为默认值（如 `${top_k|15}` 表示未提供时默认 15）
4. `fragments/*.sql` 中的 CTE 需手动拼接到 SQL 的 `WITH` 子句中
5. 可选参数未提供时替换为 `NULL`

## 技能体系

```
atomic/     → 126 个原子技能（单一 SQL 查询或少量关联查询）
composite/  → 33 个组合技能（多步分析流程，引用 atomic 技能）
deep/       → 2 个深度分析（需 simpleperf/perf 数据）
modules/    → 18 个跨域专家模块
pipelines/  → 32 种渲染管线检测
vendors/    → 8 个供应商覆盖
fragments/  → 3 个共享 SQL CTE 片段
```

## 分析场景索引

### 卡顿/掉帧

| 问题 | YAML 技能 | 关键参数 | 返回概要 |
|------|----------|---------|---------|
| 游戏 FPS 分析 | `atomic/game_fps_analysis.skill.yaml` | package, target_fps?, start_ts?, end_ts? | 目标帧率、实际帧率、掉帧统计 |
| 游戏主循环卡顿 | `atomic/game_main_loop_jank.skill.yaml` | package?, process_name?, start_ts?, end_ts? | 超 budget 帧切片列表 |
| 帧生产 Gap 分析 | `atomic/frame_production_gap.skill.yaml` | process_name, start_ts?, end_ts? | 缺帧区间 + UI/RT 活动状态 |
| Consumer Jank | `atomic/consumer_jank_detection.skill.yaml` | package?, layer_name?, start_ts?, end_ts? | SF 侧卡顿帧列表 |
| 帧阻塞调用 | `atomic/frame_blocking_calls.skill.yaml` | process_name, start_ts?, end_ts? | 掉帧期间的 GC/Binder/锁/IO 阻塞 |
| 帧管线方差 | `atomic/frame_pipeline_variance.skill.yaml` | package?, start_ts?, end_ts? | 帧时长抖动、高方差区间 |
| 每帧 CPU 时间 | `atomic/cpu_time_per_frame.skill.yaml` | (无必填) | 逐帧 CPU 累计活跃时长 |
| 每帧 UI 时间 | `atomic/frame_ui_time_breakdown.skill.yaml` | (无必填) | 逐帧 UI thread 耗时 |
| 帧超预算汇总 | `atomic/frame_overrun_summary.skill.yaml` | (无必填) | 超 budget 帧列表 |
| GL/Vulkan Swap 卡顿 | `atomic/gl_standalone_swap_jank.skill.yaml` | package?, process_name? | eglSwapBuffers/vkQueuePresent 间隔异常 |
| TextureView 帧时序 | `atomic/textureview_producer_frame_timing.skill.yaml` | package? | queueBuffer/swapBuffers 间隔 |
| 渲染管线时延 | `atomic/render_pipeline_latency.skill.yaml` | start_ts, end_ts | 帧渲染全链路各阶段耗时 |
| RenderThread Slice | `atomic/render_thread_slices.skill.yaml` | start_ts, end_ts | 渲染线程时间片分布 |
| 应用帧生产 | `atomic/app_frame_production.skill.yaml` | package?, start_ts? | 主线程帧生产情况 |
| Compose 重组热点 | `atomic/compose_recomposition_hotspot.skill.yaml` | package?, start_ts? | 过多/过慢的 Recomposition |
| WebView V8 性能 | `atomic/webview_v8_analysis.skill.yaml` | package?, start_ts? | GC/脚本编译/执行时间 |
| Present Fence 时序 | `atomic/present_fence_timing.skill.yaml` | package?, start_ts? | 实际显示延迟 |
| SF 帧消费 | `atomic/sf_frame_consumption.skill.yaml` | package?, start_ts? | SF 消费帧情况 |
| VSync 对齐 | `atomic/vsync_alignment_in_range.skill.yaml` | start_ts, end_ts | 帧与 VSync 对齐情况 |
| VSync 配置 | `atomic/vsync_config.skill.yaml` | start_ts?, end_ts? | VSync 周期/刷新率 |
| VRR/LTPO 检测 | `atomic/vrr_detection.skill.yaml` | start_ts?, end_ts? | 可变刷新率模式 |

### 渲染管线识别

| 问题 | YAML 技能 | 关键参数 | 返回概要 |
|------|----------|---------|---------|
| 渲染管线检测 (24 类型) | `atomic/rendering_pipeline_detection.skill.yaml` | package? | 主管线类型 + 置信度 + 特性列表 |
| Pipeline 4 特征评分 | `atomic/pipeline_4feature_scoring.skill.yaml` | package? | 综合评分分型结论 |
| 管线关键 Slice 时间线 | `atomic/pipeline_key_slices_overlay.skill.yaml` | slice_names, package? | Slice 的 ts/dur 数据 |

### 启动性能

| 问题 | YAML 技能 | 关键参数 | 返回概要 |
|------|----------|---------|---------|
| 启动慢原因 (20+种) | `atomic/startup_slow_reasons.skill.yaml` | (无必填) | 已知启动慢原因分类 |
| 启动关键任务发现 | `atomic/startup_critical_tasks.skill.yaml` | package, start_ts, end_ts | 活跃线程按 CPU 排序 + 四象限 |
| 启动事件列表 | `atomic/startup_events_in_range.skill.yaml` | package?, start_ts?, end_ts? | TTID/TTFD 指标 |
| 启动归因分解 | `atomic/startup_breakdown_in_range.skill.yaml` | package?, start_ts? | 各归因耗时占比 |
| 启动主线程状态 | `atomic/startup_main_thread_states_in_range.skill.yaml` | package?, start_ts? | Running/Runnable/Blocked 占比 |
| 启动主线程切片 | `atomic/startup_main_thread_slices_in_range.skill.yaml` | package?, start_ts? | 主线程切片热点 |
| 启动主线程文件 IO | `atomic/startup_main_thread_file_io_in_range.skill.yaml` | package?, start_ts? | 文件 IO 切片耗时 |
| 启动主线程 Binder 阻塞 | `atomic/startup_main_thread_binder_blocking_in_range.skill.yaml` | package?, start_ts? | 同步 Binder 阻塞明细 |
| 启动主线程同步 Binder | `atomic/startup_main_thread_sync_binder_in_range.skill.yaml` | package?, start_ts? | Binder 调用耗时分布 |
| 启动 Binder 线程池 | `atomic/startup_binder_pool_analysis.skill.yaml` | package, start_ts, end_ts | 线程池利用率/饱和度 |
| 启动调度延迟 | `atomic/startup_sched_latency_in_range.skill.yaml` | package?, start_ts? | 主线程 Runnable 等待时延 |
| 启动摆核时序 | `atomic/startup_cpu_placement_timeline.skill.yaml` | package, start_ts, end_ts | 核类型变化 + 困小核检测 |
| 启动 CPU 频率爬升 | `atomic/startup_freq_rampup.skill.yaml` | start_ts, end_ts | 升频延迟 |
| 启动 GC 分析 | `atomic/startup_gc_in_range.skill.yaml` | package?, start_ts? | GC 切片 + 主线程占比 |
| 启动 JIT 影响 | `atomic/startup_jit_analysis.skill.yaml` | package, start_ts, end_ts | JIT CPU 竞争/Code Cache/Baseline |
| 启动热点 Slice 状态 | `atomic/startup_hot_slice_states.skill.yaml` | package, start_ts, end_ts | Top N Slice 各自线程状态 |
| 启动线程阻塞关系 | `atomic/startup_thread_blocking_graph.skill.yaml` | package, start_ts, end_ts | 线程间 block/wakeup 关系 |
| 启动类加载 | `atomic/startup_class_loading_in_range.skill.yaml` | package?, start_ts? | 类加载切片耗时 |

### ANR / 无响应

| 问题 | YAML 技能 | 关键参数 | 返回概要 |
|------|----------|---------|---------|
| ANR 主线程阻塞链 | `atomic/anr_main_thread_blocking.skill.yaml` | process_name, start_ts? | 阻塞函数、唤醒链、Binder、锁 |
| ANR 上下文提取 | `atomic/anr_context_in_range.skill.yaml` | process_name? | 首个 ANR 时间窗口参数 |

### 输入时延 / 响应

| 问题 | YAML 技能 | 关键参数 | 返回概要 |
|------|----------|---------|---------|
| Input-to-Frame 延迟 | `atomic/input_to_frame_latency.skill.yaml` | package?, start_ts? | 逐帧输入到显示延迟 |
| VSync 相位对齐 | `atomic/vsync_phase_alignment.skill.yaml` | package?, start_ts? | 输入事件与 VSync 相位关系 |
| 触摸到显示延迟 | `atomic/touch_to_display_latency.skill.yaml` | package?, start_ts? | 5 维延迟分解 |
| 滚动响应延迟 | `atomic/scroll_response_latency.skill.yaml` | package?, start_ts? | 滚动手势首帧响应延迟 |
| 输入事件列表 | `atomic/input_events_in_range.skill.yaml` | package?, start_ts? | 触摸/按键 + 5 维延迟 |

### CPU / 调度

| 问题 | YAML 技能 | 关键参数 | 返回概要 |
|------|----------|---------|---------|
| CPU 拓扑检测 | `atomic/cpu_topology_detection.skill.yaml` | start_ts?, end_ts? | CPU 大小核拓扑 |
| CPU 拓扑视图 | `atomic/cpu_topology_view.skill.yaml` | start_ts?, end_ts? | 拓扑分类视图 (供后续 JOIN) |
| CPU 簇负载 | `atomic/cpu_cluster_load_in_range.skill.yaml` | start_ts, end_ts | 大核/小核 CPU 负载 |
| CPU 频率时间线 | `atomic/cpu_freq_timeline.skill.yaml` | start_ts, end_ts | 各核频率变化 |
| CPU 负载区间 | `atomic/cpu_load_in_range.skill.yaml` | start_ts, end_ts | 各核负载 |
| CPU Slice 分析 | `atomic/cpu_slice_analysis.skill.yaml` | start_ts?, end_ts? | CPU 时间片分布 |
| 调度延迟 | `atomic/sched_latency_in_range.skill.yaml` | start_ts?, end_ts? | 线程调度等待时间 |
| 任务迁移 | `atomic/task_migration_in_range.skill.yaml` | start_ts, end_ts | 大小核间迁移频率 |
| CPU 限频 | `atomic/cpu_throttling_in_range.skill.yaml` | start_ts, end_ts | 热控限频检测 |
| 线程亲和性异常 | `atomic/thread_affinity_violation.skill.yaml` | package?, start_ts? | 高频迁核行为 |
| 主线程调度延迟 | `atomic/main_thread_sched_latency_in_range.skill.yaml` | start_ts?, end_ts? | 主线程 Runnable 等待 |
| CPU Idle C-State | `atomic/cpu_idle_analysis.skill.yaml` | start_ts?, end_ts? | idle 状态分布 + 唤醒延迟 |
| 缓存未命中 | `atomic/cache_miss_impact.skill.yaml` | start_ts?, end_ts? | MPKI 评估 |
| 系统负载 | `atomic/system_load_in_range.skill.yaml` | start_ts, end_ts | CPU 利用率 + 进程活跃度 |
| Linux 调度延迟分布 | `atomic/linux_sched_latency_distribution.skill.yaml` | package?, start_ts? | Runnable→Running 等待分布 |
| Linux Runqueue 深度 | `atomic/linux_runqueue_depth_timeline.skill.yaml` | start_ts?, end_ts? | runnable 线程数时间线 |

### Binder / IPC

| 问题 | YAML 技能 | 关键参数 | 返回概要 |
|------|----------|---------|---------|
| Binder 风暴检测 | `atomic/binder_storm_detection.skill.yaml` | package?, start_ts? | 短时间过多 IPC |
| Binder 事务分析 | `atomic/binder_in_range.skill.yaml` | start_ts?, end_ts? | Binder 事务列表 |
| Binder 阻塞分析 | `atomic/binder_blocking_in_range.skill.yaml` | start_ts?, end_ts? | 对端响应延迟 |
| Binder 根因归因 | `atomic/binder_root_cause.skill.yaml` | process_name, start_ts, end_ts | 服务端/客户端阻塞原因 |
| 阻塞链分析 | `atomic/blocking_chain_analysis.skill.yaml` | process_name, start_ts, end_ts | 谁阻塞了主线程 → 唤醒者 |

### 内存

| 问题 | YAML 技能 | 关键参数 | 返回概要 |
|------|----------|---------|---------|
| GC 事件 | `atomic/gc_events_in_range.skill.yaml` | package, start_ts? | GC 分类列表 |
| 内存增长检测 | `atomic/memory_growth_detector.skill.yaml` | package?, start_ts? | RSS/Swap 持续增长趋势 |
| 内存压力 | `atomic/memory_pressure_in_range.skill.yaml` | start_ts, end_ts | 内存压力评估 |
| LMK 杀进程 | `atomic/lmk_kill_attribution.skill.yaml` | process_name?, start_ts? | 被杀进程列表 |
| Page Fault | `atomic/page_fault_in_range.skill.yaml` | start_ts?, end_ts? | 缺页异常影响 |
| RSS 峰值 | `atomic/memory_rss_high_watermark.skill.yaml` | process_name? | 每进程内存最高水位 |
| Native Heap | `atomic/native_heap_breakdown.skill.yaml` | min_size_mb? | heapprofd 未释放热点 |
| Bitmap 内存 | `atomic/android_bitmap_memory_per_process.skill.yaml` | (无必填) | 每进程 Bitmap 峰值 |
| OOM Score | `atomic/oom_adjuster_score_timeline.skill.yaml` | process_name? | oom_score_adj 变化 |
| Linux RSS/Swap | `atomic/linux_process_rss_swap_timeline.skill.yaml` | package? | 进程 RSS/Swap 时间线 |

### GPU

| 问题 | YAML 技能 | 关键参数 | 返回概要 |
|------|----------|---------|---------|
| GPU 指标 | `atomic/gpu_metrics.skill.yaml` | start_ts?, end_ts? | GPU 频率/利用率/渲染 |
| GPU 渲染分析 | `atomic/gpu_render_in_range.skill.yaml` | start_ts?, end_ts? | GPU 渲染耗时 + Fence 等待 |
| GPU 频率 | `atomic/gpu_freq_in_range.skill.yaml` | start_ts?, end_ts? | GPU 频率变化 |
| GPU 功耗状态 | `atomic/gpu_power_state_analysis.skill.yaml` | start_ts?, end_ts? | 降频压力 + DVFS |

### 锁竞争

| 问题 | YAML 技能 | 关键参数 | 返回概要 |
|------|----------|---------|---------|
| 锁竞争分析 | `atomic/lock_contention_in_range.skill.yaml` | start_ts, end_ts | 锁等待统计 |
| Futex 等待分布 | `atomic/futex_wait_distribution.skill.yaml` | package?, start_ts? | futex/mutex 锁等待 |

### 诊断工具

| 问题 | YAML 技能 | 关键参数 | 返回概要 |
|------|----------|---------|---------|
| Fence 等待分解 | `atomic/fence_wait_decomposition.skill.yaml` | start_ts, end_ts | acquire/present/release 分类计时 |
| Buffer Transaction | `atomic/buffer_transaction_lifecycle.skill.yaml` | start_ts, end_ts | BLAST Transaction 生命周期 |
| SF 图层数 | `atomic/sf_layer_count_in_range.skill.yaml` | start_ts, end_ts | 活跃图层数量 |
| 设备状态时间线 | `atomic/device_state_timeline.skill.yaml` | start_ts?, end_ts? | CPU/GPU 频率/温度/内存 |
| 设备环境快照 | `atomic/device_state_snapshot.skill.yaml` | start_ts?, end_ts? | 屏幕/电量/温度/CPU/内存 |

### 功耗

| 问题 | YAML 技能 | 关键参数 | 返回概要 |
|------|----------|---------|---------|
| DVFS Counter | `atomic/android_dvfs_counter_stats.skill.yaml` | (无必填) | CPU/GPU/DDR 频率统计 |
| Kernel Wakelock | `atomic/android_kernel_wakelock_summary.skill.yaml` | (无必填) | wakelock 持有时长 |
| 电池电量时间线 | `atomic/battery_charge_timeline.skill.yaml` | start_ts?, end_ts? | 电量/电压/电流 |
| Doze 状态 | `atomic/battery_doze_state_timeline.skill.yaml` | start_ts?, end_ts? | Deep/Light idle 区间 |
| Wake Lock 追踪 | `atomic/wakelock_tracking.skill.yaml` | start_ts?, end_ts? | Wake Lock 持有情况 |
| 启动期能耗 | `atomic/wattson_app_startup_power.skill.yaml` | package? | 启动期间 mWs |
| Power Rails | `atomic/wattson_rails_power_breakdown.skill.yaml` | top_n? | 按 rail 能耗分解 |
| 线程功耗归因 | `atomic/wattson_thread_power_attribution.skill.yaml` | process_name? | 按线程 CPU 能耗 |
| 热控风险预测 | `atomic/thermal_predictor.skill.yaml` | start_ts, end_ts | 限频风险预测 |
| FPSGO 策略 (MTK) | `atomic/fpsgo_analysis.skill.yaml` | start_ts?, end_ts? | FPSGO 帧感知调度 |

### 其他

| 问题 | YAML 技能 | 关键参数 | 返回概要 |
|------|----------|---------|---------|
| 应用生命周期 | `atomic/app_lifecycle_in_range.skill.yaml` | package?, start_ts? | Activity/Fragment 事件 |
| 进程启动汇总 | `atomic/app_process_starts_summary.skill.yaml` | package?, start_ts? | 系统 fork 事件 |
| Logcat 异常 | `atomic/logcat_analysis.skill.yaml` | start_ts?, end_ts? | ANR/GC/Binder/StrictMode |
| 媒体 Codec | `atomic/media_codec_activity.skill.yaml` | package?, start_ts? | 解码卡顿/buffer 异常 |
| JobScheduler | `atomic/android_job_scheduler_events.skill.yaml` | (无必填) | 后台任务序列 |
| React Native Bridge | `atomic/rn_bridge_to_frame_jank.skill.yaml` | package?, start_ts? | RN Bridge/JS/UIManager 关联 |
| RN Fabric | `atomic/rn_fabric_render_jank.skill.yaml` | package?, start_ts? | Fabric/JSI/Mounting 关联 |

## SQL 片段 (fragments/)

部分技能的 SQL 引用共享 CTE 片段，需在执行前拼接到 SQL 的 WITH 子句中：

| 片段 | 路径 | 用途 |
|------|------|------|
| target_threads | `fragments/target_threads.sql` | 解析 MainThread/RenderThread（含 Flutter/Compose） |
| thread_states_quadrant | `fragments/thread_states_quadrant.sql` | 线程状态四象限分类（依赖 target_threads + _cpu_topology） |
| vsync_config | `fragments/vsync_config.sql` | VSync 周期估算（自动对齐标准刷新率） |

**拼接规则**: 如果技能 SQL 以 `WITH` 开头，将片段 CTE 插入 `WITH` 关键字后；否则用 `WITH {片段} {原始SQL}` 包装。

## 组合技能索引 (composite/)

组合技能包含多步分析流程，步骤类型包括：
- `type: atomic` — 直接包含 SQL，通过 pa_execute_sql 执行
- `type: skill` — 引用其他技能（`skill: name` → 对应 `atomic/name.skill.yaml`），读取对应 YAML 获取 SQL
- `type: diagnostic` — 诊断规则，Agent 根据规则条件评估结果

| 问题 | YAML 技能 | 关键参数 | 步骤数 | 包含的子技能引用 |
|------|----------|---------|-------|----------------|
| Jank 帧详细分析 | `composite/jank_frame_detail.skill.yaml` | package, start_ts, frame_id | 21 | cpu_topology_view, sched_latency_in_range, task_migration_in_range, gpu_render_in_range 等 |
| CPU 全维度分析 | `composite/cpu_analysis.skill.yaml` | package, start_ts, end_ts | 15+ | cpu_topology_view, sched_latency_in_range, task_migration_in_range, cpu_throttling_in_range 等 |
| 启动分析 | `composite/startup_analysis.skill.yaml` | package | 10+ | startup_events_in_range, startup_breakdown_in_range, startup_critical_tasks 等 |
| 启动详细分析 | `composite/startup_detail.skill.yaml` | package, start_ts, end_ts | 10+ | startup_main_thread_states, startup_main_thread_slices, startup_binder 等 |
| ANR 分析 | `composite/anr_analysis.skill.yaml` | process_name | 5+ | anr_context_in_range, main_thread_states_in_range 等 |
| ANR 详细分析 | `composite/anr_detail.skill.yaml` | process_name, start_ts, end_ts | 10+ | cpu_topology_view, sched_latency_in_range, binder_blocking_in_range 等 |
| Binder 分析 | `composite/binder_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | binder_blocking_in_range 等 |
| Binder 详细分析 | `composite/binder_detail.skill.yaml` | process_name, start_ts, end_ts | 5+ | cpu_topology_view 等 |
| 内存分析 | `composite/memory_analysis.skill.yaml` | package, start_ts, end_ts | 8+ | gc_events_in_range, memory_pressure_in_range, page_fault_in_range 等 |
| GPU 分析 | `composite/gpu_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | gpu_render_in_range, gpu_freq_in_range 等 |
| 锁竞争分析 | `composite/lock_contention_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | lock_contention_in_range, futex_wait_distribution 等 |
| GC 分析 | `composite/gc_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | gc_events_in_range 等 |
| 热控分析 | `composite/thermal_throttling.skill.yaml` | package, start_ts, end_ts | 5+ | cpu_throttling_in_range, thermal_predictor 等 |
| 热控链路分析 | `composite/thermal_throttling_chain.skill.yaml` | package, start_ts, end_ts | 8+ | cpu_throttling_in_range, cpu_freq_timeline 等 |
| 点击响应分析 | `composite/click_response_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | input_events_in_range, input_to_frame_latency 等 |
| 点击响应详细 | `composite/click_response_detail.skill.yaml` | package, start_ts, end_ts | 10+ | input_to_frame_latency, vsync_phase_alignment, sched_latency_in_range 等 |
| 滚动分析 | `composite/scrolling_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | scroll_response_latency 等 |
| 滚动会话分析 | `composite/scroll_session_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | scroll_response_latency, frame_pipeline_variance 等 |
| Flutter 滚动分析 | `composite/flutter_scrolling_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | scroll_response_latency, vsync_alignment_in_range 等 |
| SF 分析 | `composite/surfaceflinger_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | sf_composition_in_range, sf_layer_count_in_range 等 |
| 导航分析 | `composite/navigation_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | input_events_in_range, app_lifecycle_in_range 等 |
| IO 阻塞分析 | `composite/block_io_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | main_thread_states_in_range, main_thread_file_io_in_range 等 |
| IO 压力分析 | `composite/io_pressure.skill.yaml` | package, start_ts, end_ts | 5+ | page_fault_in_range 等 |
| 网络分析 | `composite/network_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | — |
| LMK 分析 | `composite/lmk_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | lmk_kill_attribution, memory_pressure_in_range 等 |
| 电量消耗归因 | `composite/battery_drain_attribution.skill.yaml` | start_ts, end_ts | 8+ | battery_charge_timeline, battery_doze_state_timeline, wakelock_tracking 等 |
| 功耗概览 | `composite/power_consumption_overview.skill.yaml` | start_ts, end_ts | 8+ | wattson_rails_power_breakdown, wattson_thread_power_attribution 等 |
| 挂起唤醒分析 | `composite/suspend_wakeup_analysis.skill.yaml` | start_ts, end_ts | 5+ | android_kernel_wakelock_summary 等 |
| DMA-BUF 分析 | `composite/dmabuf_analysis.skill.yaml` | package, start_ts, end_ts | 5+ | — |
| 场景重建 | `composite/scene_reconstruction.skill.yaml` | package, start_ts, end_ts | 5+ | rendering_pipeline_detection 等 |
| WebView DrawFunctor | `composite/webview_drawfunctor_jank_chain.skill.yaml` | package, start_ts, end_ts | 5+ | webview_v8_analysis 等 |
| IRQ 分析 | `composite/irq_analysis.skill.yaml` | start_ts, end_ts | 5+ | linux_irq_summary 等 |
| 状态时间线 | `composite/state_timeline.skill.yaml` | start_ts, end_ts | 5+ | device_state_timeline 等 |

**执行方式**: Agent 读取 composite YAML → 按 steps 顺序逐步执行 → 遇到 `type: skill` 步骤时读取对应 atomic YAML 获取 SQL → 遇到 `type: diagnostic` 步骤时根据 rules 评估结果。

## 渲染管线检测 (pipelines/)

32 种渲染管线类型的自动检测。先用 `atomic/rendering_pipeline_detection.skill.yaml` 识别管线类型，再读取对应管线 YAML 获取 teaching + analysis 指引。

7 大管线族：

| 族 | 数量 | 包含 |
|----|------|------|
| hwui | 6 | Blast, Legacy, Software, Mixed, Multi-Window, Compose |
| surface | 4 | SurfaceView, TextureView, SurfaceControl, PiP/Freeform |
| graphics | 3 | OpenGL ES, Vulkan, ANGLE GLES-on-Vulkan |
| flutter | 3 | Impeller, Skia, TextureView |
| webview | 2 | Chrome Browser Viz, GL Functor |
| react_native | 2 | Old Arch, New Arch Fabric |
| specialized | 7 | Game Engine, Camera, Video HWC, HW Buffer, ImageReader, VRR, Software |

每个管线 YAML 包含：`detection`（信号检测 SQL）+ `teaching`（线程角色说明）+ `analysis`（推荐技能列表）。

## 供应商覆盖 (vendors/)

8 个 OEM 供应商的启动分析覆盖，按设备特征自动应用：

| 供应商 | 目录 | 特征信号 |
|--------|------|---------|
| Qualcomm | `vendors/qualcomm/` | `*QTI*`, `*Adreno*` |
| MediaTek | `vendors/mtk/` | `*MTK*`, `*FPSGO*` |
| Samsung | `vendors/samsung/` | `*Exynos*`, `*SEC*` |
| Xiaomi | `vendors/xiaomi/` | `*Xiaomi*`, `*MiUI*` |
| vivo | `vendors/vivo/` | `*vivo*`, `*BBK*` |
| OPPO | `vendors/oppo/` | `*OPPO*`, `*ColorOS*` |
| Honor | `vendors/honor/` | `*HONOR*`, `*Magic*` |
| Pixel | `vendors/pixel/` | `*Pixel*`, `*Google*` |

**使用方式**: Agent 先用 SQL 检测设备信号（如 `SELECT name FROM track WHERE name LIKE '%QTI%'`），匹配到供应商后读取对应 override YAML，将 `additional_steps` 中的 SQL 追加执行。

## 跨域专家模块 (modules/)

18 个模块专家，按系统层级组织。每个模块可回答特定领域问题，并推荐下一步查询的其他模块。

| 层级 | 模块 | YAML 路径 | 核心能力 |
|------|------|----------|---------|
| **app** | Launcher | `modules/app/launcher_module.skill.yaml` | 启动器调度、热启动 |
| **app** | SystemUI | `modules/app/systemui_module.skill.yaml` | 系统界面、通知栏 |
| **app** | 第三方应用 | `modules/app/third_party_module.skill.yaml` | 应用自身逻辑 |
| **framework** | AMS | `modules/framework/ams_module.skill.yaml` | Activity 管理、进程调度 |
| **framework** | ART | `modules/framework/art_module.skill.yaml` | JIT 编译、GC、类加载 |
| **framework** | Choreographer | `modules/framework/choreographer_module.skill.yaml` | VSync 调度、doFrame |
| **framework** | Input | `modules/framework/input_module.skill.yaml` | 输入事件分发 |
| **framework** | SurfaceFlinger | `modules/framework/surfaceflinger_module.skill.yaml` | 合成、BufferQueue |
| **framework** | WMS | `modules/framework/wms_module.skill.yaml` | 窗口管理、配置变更 |
| **hardware** | CPU | `modules/hardware/cpu_module.skill.yaml` | 频率、拓扑、调度 |
| **hardware** | GPU | `modules/hardware/gpu_module.skill.yaml` | 渲染、频率、功耗 |
| **hardware** | Memory | `modules/hardware/memory_module.skill.yaml` | RSS、Swap、LMK |
| **hardware** | Power | `modules/hardware/power_module.skill.yaml` | WakeLock、Doze、能耗 |
| **hardware** | Thermal | `modules/hardware/thermal_module.skill.yaml` | 限频、温度趋势 |
| **kernel** | Binder | `modules/kernel/binder_module.skill.yaml` | IPC 事务、阻塞链 |
| **kernel** | Filesystem | `modules/kernel/filesystem_module.skill.yaml` | 文件 IO、fuse |
| **kernel** | Lock Contention | `modules/kernel/lock_contention_module.skill.yaml` | futex、mutex |
| **kernel** | Scheduler | `modules/kernel/scheduler_module.skill.yaml` | 调度延迟、迁核 |

每个模块 YAML 包含 `dialogue` 段：
- `capabilities[]`: 模块能回答的问题（questionTemplate + requiredParams）
- `findingsSchema[]`: 结构化发现（severity + titleTemplate + evidenceFields）
- `suggestionsSchema[]`: 跨域推荐（condition → targetModule → questionTemplate）

**使用方式**: Agent 分析到某个领域的问题后，读取对应模块 YAML → 按 capabilities 回答问题 → 按 suggestions 推荐查询其他模块。

## 深度分析 (deep/)

| 问题 | YAML 技能 | 关键参数 | 说明 |
|------|----------|---------|------|
| 调用栈分析 | `deep/callstack_analysis.skill.yaml` | package, start_ts, end_ts | 需 simpleperf/perf 采样的调用栈热点 |
| CPU Profiling | `deep/cpu_profiling.skill.yaml` | package, start_ts, end_ts | 需 simpleperf 数据的 CPU profiling |

## Trace 探索与路由

每次分析新 trace 时，MUST 先执行以下探索流程，再选择分析技能：

```
1. 验证工具可用性
   - pa_execute_sql 会自动发现 trace_processor_shell：
     ① ~/.local/share/perfetto/prebuilts/trace_processor_shell(.exe)
     ② skill scripts/ 同级目录
     ③ perfetto 包自动下载（兜底）
   - 国内网络无法访问 Google Cloud Storage 时，需手动下载二进制放到上述位置之一
   - Windows: https://commondatastorage.googleapis.com/perfetto-luci-artifacts/v55.3/windows-amd64/trace_processor_shell.exe
   - macOS: https://commondatastorage.googleapis.com/perfetto-luci-artifacts/v55.3/mac-amd64/trace_processor_shell
   - Linux: https://commondatastorage.googleapis.com/perfetto-luci-artifacts/v55.3/linux-amd64/trace_processor_shell
   - 下载后需设置可执行权限 (chmod +x)，Windows 不需要

2. 查询 metadata → 设备信息
   SELECT name, str_value FROM metadata WHERE str_value IS NOT NULL
   关注: android_build_fingerprint, android_device_manufacturer,
         android_soc_model, android_system_version

3. 查询 process 表 → 定位目标应用
   - 按 slice count 排序找最活跃进程
   - 过滤 system_server, surfaceflinger, audioserver 等系统进程
   - 从 /data/app/ 或 com.* 包名识别应用

4. 查询 thread 表 → 识别游戏引擎
   - Unity: UnityMain, UnityGfxDeviceW
   - Unreal: GameThread, RHIThread, RenderThread
   - Cocos: *cocos*
   - 通用: GLThread, VulkanThread

5. 查询渲染管线 → 检测帧边界方式
   - SELECT DISTINCT name FROM slice WHERE name IN
     ('eglSwapBuffers', 'vkQueuePresentKHR', 'queueBuffer', 'dequeueBuffer')
   - FrameTimeline 是否可用？(INCLUDE PERFETTO MODULE android.frames.timeline)
   - 若 actual_frame_timeline_slice 帧数远小于 swap 次数 → 使用 swap 间隔分析

6. 选择分析章节
   根据引擎类型、渲染管线、trace 场景选择对应的分析技能和报告章节
```

## 分析流程

```
1. 确认分析目标 → trace_path, package, 分析场景
2. 按场景索引找到对应 YAML 技能
3. 读取 YAML → 获取 steps[].sql
4. 替换 ${variable} 为实际参数
5. 如需 fragments → 读取并拼接到 SQL
6. 调用 pa_execute_sql(trace_path, sql)
7. 按 YAML 中的 output/thresholds/diagnostics 评估结果
8. 生成 HTML 报告（参见下方"报告生成"章节）
   ① 确定输出目录: data/output/trace_report/<trace_stem>/
   ② 运行 build_report.py init 初始化报告目录
   ③ 根据分析场景，为每个触发章节准备 data JSON
   ④ 依次运行 build_report.py chapter 渲染各章节
   ⑤ 准备 conclusion JSON，运行 build_report.py conclusion
   ⑥ 运行 build_report.py assemble 生成最终 HTML 报告
   ⑦ 对话区仅输出报告路径和根因摘要，详细数据在 HTML 报告中
```

## 报告生成

分析完成后 MUST 使用 `scripts/build_report.py` 生成 HTML 报告。

> **重要**: 了解 build_report.py 的用法和子命令时，执行 `python scripts/build_report.py --help`，禁止阅读源码。

### 输出路径规范

```
data/output/trace_report/<trace_stem>/
├── header.json
├── chapters/
│   ├── fps.html
│   ├── cpu.html
│   └── ...
├── chapter_data/
│   ├── fps.json
│   └── ...
├── conclusion.html
└── perfetto-report-{app_short}-{date}-{type}.html
```

- `trace_stem`: trace 文件名去 `.perfetto-trace` 后缀
- `app_short`: 从包名提取简短标识，如 `com.tencent.tmgp.sgame` → `sgame`
- `date`: trace 文件名中的日期或分析日期 (YYYYMMDD)
- `type`: 分析类型 — `jank` / `startup` / `memory` / `comprehensive`

### 报告生成流水线

```bash
# Phase 0: 初始化报告目录
python scripts/build_report.py init \
  --output-dir data/output/trace_report/<trace_stem>/ \
  --header '{"trace_name":"...","analysis_time":"..."}'

# Phase 1: 逐章渲染（以 fps 为例）
# ① 将章节数据写入 chapter_data/fps.json（格式参见各章节 data_schema）
# ② 运行 chapter 命令
python scripts/build_report.py chapter \
  --chapter-id fps \
  --data data/output/trace_report/<trace_stem>/chapter_data/fps.json \
  --chapters-dir templates/chapters/ \
  --fragments-dir templates/fragments/ \
  -o data/output/trace_report/<trace_stem>/chapters/fps.html

# Phase 2: 结论
python scripts/build_report.py conclusion \
  --data data/output/trace_report/<trace_stem>/chapter_data/conclusion.json \
  --fragments-dir templates/fragments/ \
  -o data/output/trace_report/<trace_stem>/conclusion.html

# Phase 3: 组装最终报告
python scripts/build_report.py assemble \
  -d data/output/trace_report/<trace_stem>/ \
  -t templates/base.html \
  -o data/output/trace_report/<trace_stem>/perfetto-report-{app_short}-{date}-{type}.html
```

### 章节选择规则

Agent 根据实际运行的分析技能自动选择章节（章节 YAML `trigger.when_skills_used` 定义）：

| 分析场景 | 已使用的 Skill | 触发章节 |
|---------|---------------|---------|
| 帧率/卡顿 | game_fps_analysis / game_main_loop_jank | fps |
| CPU/调度 | sched_latency_in_range / cpu_topology_view | cpu |
| GPU 渲染 | gpu_metrics / gpu_render_in_range | gpu |
| 内存 | gc_events_in_range / memory_growth_detector | memory |
| Binder/IPC | binder_blocking_in_range | binder |
| 启动 | startup_events_in_range | startup |
| SurfaceFlinger | sf_frame_consumption | sf |
| IO | main_thread_file_io_in_range | io |
| 功耗 | battery_charge_timeline | power |
| 锁竞争 | lock_contention_in_range | lock |
| 热控 | cpu_throttling_in_range | thermal |

header 和 root_causes 始终包含，conclusion 始终生成。未触发条件的章节跳过。

### data JSON 格式

每个章节的 data JSON 结构：

```json
{
  "title": "章节显示标题",
  "data": {
    "<section_id>": { ... },
    "<section_id>": [ ... ],
    "<section_id>": null
  }
}
```

- `object` 类型 section → 渲染为 metric_grid
- `array` 类型 section → 渲染为 data_table
- `null` + schema 中 `required: false` → 跳过

具体字段定义见 `templates/chapters/{chapter_id}_data.yaml`，Agent 应读取对应 YAML 了解需要填充的字段。

### 结论 JSON 格式

```json
{
  "overall_rating": "优秀 / 良好 / 一般 / 较差",
  "rating_color": "green / yellow / red",
  "summary": "3-5 句话的综合总结",
  "highlights": ["亮点1", "亮点2", ...],
  "risks": ["关注点1", "关注点2", ...],
  "recommendations": ["建议1", "建议2", ...],
  "chapters_included": ["fps", "cpu", ...]
}
```

### 对话区输出规范

生成 HTML 报告后，对话区仅输出：
1. 报告文件路径（可点击的 markdown 链接）
2. 根因摘要（3-5 条，每条包含严重度标签）

详细数据、表格、分布图均在 HTML 报告中，对话区不重复输出。

## 关键注意事项

- Jank 阈值：App Deadline > 1.5× VSync，SF Composition 窗口 0.5× VSync
- 游戏 trace 使用 `game_fps_analysis` / `game_main_loop_jank`，不使用 VSync 帧检测
- VSync 周期：60Hz=16.67ms, 90Hz=11.11ms, 120Hz=8.33ms, 144Hz=6.94ms
- `${var|default}` 语法：`|` 分隔变量名和默认值，未提供参数时使用默认值
- SQL 中的 `COALESCE(${start_ts}, MIN(ts))` — 可选参数替换为 NULL 后由 SQL 处理

## 详细参考

- SQL CTE 片段 → `fragments/`
- 完整工具参数 → [tool-catalog.md](tool-catalog.md)
