# Perfetto 引擎 vs MCP 对比 Demo 方案

## 目录

- [背景与目标](#背景与目标)
- [对比范围](#对比范围)
- [前置准备](#前置准备)
- [Demo 1: 卡顿检测](#demo-1-卡顿检测)
- [Demo 2: CPU 分析](#demo-2-cpu-分析)
- [Demo 3: 线程分析](#demo-3-线程分析)
- [Demo 4: Binder 分析](#demo-4-binder-分析)
- [Demo 5: MCP 独有能力验证](#demo-5-mcp-独有能力验证)
- [Demo 6: 引擎独有能力验证](#demo-6-引擎独有能力验证)
- [评估标准](#评估标准)
- [决策矩阵](#决策矩阵)
- [执行步骤](#执行步骤)

## 背景与目标

`perfetto_analysis` 模块当前使用自建引擎（Python + TraceProcessor SQL）进行卡顿分析。
项目同时接入了 `user-perfetto-mcp` MCP Server，提供 12 个结构化分析工具。
两者在卡顿检测、CPU、线程、Binder 分析上存在显著重叠。

**目标**：通过同一 trace 文件的对比分析，确定架构演进方向：
- 混合模式（MCP 为主 + 引擎补充）
- 全面转 MCP
- 引擎为主（MCP 仅补充）

## 对比范围

| 对比项 | 引擎模块 | MCP 工具 | 重叠度 |
|--------|---------|----------|--------|
| 卡顿检测 | `parser.py` | `detect_jank_frames` | 高 |
| CPU 分析 | `cpu_analysis.py` | `cpu_utilization_profiler` | 高 |
| 线程分析 | `thread_analysis.py` | `thread_contention_analyzer` | 中 |
| Binder | `binder_analysis.py` | `binder_transaction_profiler` | 高 |
| ANR | 无 | `detect_anrs` + `anr_root_cause_analyzer` | MCP 独有 |
| 内存 | 无 | `memory_leak_detector` + `heap_dominator_tree_analyzer` | MCP 独有 |
| IO/GC/GPU/SF/Input/Lock | 有 | 无 | 引擎独有 |

## 前置准备

### 所需 trace 文件

需要一个包含以下特征的 `.perfetto-trace` 文件：
- 有明显卡顿帧（jank_num > 0）
- 包含 CPU 频率数据
- 包含 Binder 事务
- 有目标进程可指定

**推荐**：使用之前调试过的真实游戏 trace，确保引擎已经成功分析过。

### 环境确认

```bash
# 确认引擎可用
python -m toolkit.app  # 启动后确认 perfetto_analysis 模块正常加载

# 确认 MCP 可用（Cursor 中）
# Perfetto MCP Server 应在 MCP 列表中显示为已连接
```

## Demo 1: 卡顿检测

### 引擎方式

```python
# 通过 CLI 执行
python -m toolkit.app analysis parse <trace_path> --process <process_name>
```

**输出**：`parse_result` 包含：
- `jank_records`: 每条卡顿的 vsync 时间戳、jank_num、jank_type
- `vsync_cycles`: 全部 vsync 周期数据
- `stand_vsync_ms`: 标准帧间隔

### MCP 方式

```
# Cursor 中调用 MCP 工具
detect_jank_frames(
    trace_path="<trace_path>",
    process_name="<process_name>",
    jank_threshold_ms=16.67
)
```

**输出**：`result` 字符串，包含帧信息和严重程度分类。

### 对比关注点

| 维度 | 引擎 | MCP | 评判标准 |
|------|------|-----|---------|
| 卡顿帧数量 | 统计 jank_records 数量 | 统计返回帧数量 | 数量是否一致 |
| 卡顿分类 | jank_type (app/sf/mixed) | severity_filter 分类 | 分类体系差异 |
| 时间精度 | ns 级时间戳 | ms 级阈值 | 是否影响分析 |
| 帧间关联 | vsync 周期关联 | 独立帧判定 | 是否能追踪连续掉帧 |
| 数据结构 | dict（程序可处理） | string（需 LLM 解读） | Agent 调用的便利性 |

## Demo 2: CPU 分析

### 引擎方式

```python
# 通过 CLI 按维度分析
python -m toolkit.app analysis analyze <trace_path> --process <process_name> --analyze cpu
```

**输出**：
- `freq_analysis`: 每个 CPU 的频率变化 + 频率爬升检测
- `cluster_analysis`: 大小核调度时间分配
- `sched_latency`: 调度延迟统计

### MCP 方式

```
cpu_utilization_profiler(
    trace_path="<trace_path>",
    process_name="<process_name>",
    include_frequency_analysis=true
)
```

**输出**：per-thread CPU 使用率排名 + 可选频率分析。

### 对比关注点

| 维度 | 引擎 | MCP | 评判标准 |
|------|------|-----|---------|
| 分析粒度 | 逐帧窗口内 CPU 分析 | 全进程 CPU 使用率 | 逐帧 vs 全局的取舍 |
| 频率爬升检测 | 有（FREQ_RAMP_MIN_STEPS） | 不确定 | 引擎独有能力是否关键 |
| 大小核调度 | 有（cluster_analysis） | 不确定 | 依赖 cpu_topology |
| 调度延迟 | 有（sched_latency） | 无 | 引擎独有 |
| 输出格式 | 结构化 dict | string | 可编程性 |

## Demo 3: 线程分析

### 引擎方式

```python
python -m toolkit.app analysis analyze <trace_path> --process <process_name> --analyze thread
```

**输出**：
- 线程状态时间线（Running/Sleeping/Uninterruptible/Runnable）
- Block/Waker 链追踪

### MCP 方式

```
thread_contention_analyzer(
    trace_path="<trace_path>",
    process_name="<process_name>",
    min_block_ms=50,
    include_per_thread_breakdown=true,
    include_examples=true
)
```

**输出**：锁/调度竞争分析（monitor_contention 或 scheduler_inferred）。

### 对比关注点

| 维度 | 引擎 | MCP | 评判标准 |
|------|------|-----|---------|
| 分析范围 | 线程状态时间线（全状态） | 锁竞争聚焦 | 广度 vs 深度 |
| Block 追踪 | Block/Waker 链 | monitor_contention | 根因定位能力 |
| 时间窗口 | 逐帧窗口内 | 全 trace 或指定范围 | 灵活性 |
| 互补性 | 广视角 | 深视角 | 是否互补而非替代 |

## Demo 4: Binder 分析

### 引擎方式

```python
python -m toolkit.app analysis analyze <trace_path> --process <process_name> --analyze binder
```

**输出**：
- Binder 调用列表（耗时 > slow_binder_ms）
- 线程池饱和度检测

### MCP 方式

```
binder_transaction_profiler(
    trace_path="<trace_path>",
    process_filter="<process_name>",
    min_latency_ms=10,
    include_thread_states=true,
    correlate_with_main_thread=true
)
```

**输出**：跨进程 Binder IPC 延迟、开销比、主线程影响。

### 对比关注点

| 维度 | 引擎 | MCP | 评判标准 |
|------|------|-----|---------|
| 阈值控制 | slow_binder_ms（默认 2ms） | min_latency_ms（默认 10ms） | 敏感度差异 |
| 线程池分析 | 饱和度检测 | 不确定 | 引擎独有？ |
| 主线程关联 | 在逐帧窗口内 | correlate_with_main_thread | MCP 有专门参数 |
| 分组聚合 | 无 | group_by (AIDL/server) | MCP 更灵活 |

## Demo 5: MCP 独有能力验证

验证引擎没有但 MCP 提供的能力，评估扩展价值：

### ANR 检测 + 根因分析

```
# 步骤 1: 检测 ANR
detect_anrs(trace_path="<trace_path>")

# 步骤 2: 根因分析
anr_root_cause_analyzer(
    trace_path="<trace_path>",
    process_name="<process_name>",
    deep_analysis=true
)
```

### 内存分析

```
memory_leak_detector(
    trace_path="<trace_path>",
    process_name="<process_name>"
)

heap_dominator_tree_analyzer(
    trace_path="<trace_path>",
    process_name="<process_name>"
)
```

### 主线程热点 + Slice 搜索

```
main_thread_hotspot_slices(
    trace_path="<trace_path>",
    process_name="<process_name>",
    limit=20
)

find_slices(
    trace_path="<trace_path>",
    pattern="<关键字>",
    process_name="<process_name>"
)
```

### 关注点

- 这些能力对 "多场景分析" 的覆盖度
- 输出质量是否足以作为 Agent 的数据源
- 是否需要引擎补充

## Demo 6: 引擎独有能力验证

验证引擎有但 MCP 没有的能力，评估保留价值：

```python
# IO 分析
python -m toolkit.app analysis analyze <trace_path> --process <process_name> --analyze io

# GC 分析
python -m toolkit.app analysis analyze <trace_path> --process <process_name> --analyze gc

# GPU 分析
python -m toolkit.app analysis analyze <trace_path> --process <process_name> --analyze gpu

# SurfaceFlinger 分析
python -m toolkit.app analysis analyze <trace_path> --process <process_name> --analyze sf

# 输入延迟分析
python -m toolkit.app analysis analyze <trace_path> --process <process_name> --analyze input

# 锁竞争分析
python -m toolkit.app analysis analyze <trace_path> --process <process_name> --analyze lock
```

### 关注点

- 这些能力对卡顿根因定位的贡献度
- MCP 的 `execute_sql_query` 能否按需替代
- 是否值得保留为独立 skill

## 评估标准

每个对比项按 1-5 分评估（5 为最优）：

| 评估维度 | 权重 | 说明 |
|---------|------|------|
| **准确性** | 30% | 分析结果的正确性和完整性 |
| **LLM 可调用性** | 25% | Agent 调用的便利性、输出的可解析性 |
| **分析深度** | 20% | 根因定位的层次和细节 |
| **灵活性** | 15% | 参数可调、时间窗口可控、场景可扩展 |
| **可维护性** | 10% | 代码/配置维护成本 |

## 决策矩阵

Demo 完成后，填写此矩阵做最终决策：

| 能力 | 引擎评分 | MCP 评分 | 推荐方案 | 理由 |
|------|---------|---------|---------|------|
| 卡顿检测 | | | | |
| CPU 分析 | | | | |
| 线程分析 | | | | |
| Binder 分析 | | | | |
| ANR | N/A | | | |
| 内存 | N/A | | | |
| IO/GC/GPU/SF/Input/Lock | | N/A | | |

**最终架构决策**：
- [ ] 混合模式（MCP 为主 + 引擎补充独有能力）
- [ ] 全面转 MCP
- [ ] 引擎为主（MCP 仅补充）

## 实测结果（2026-03-31）

### 测试环境

- **Trace 文件**: `launcher慢划TB522FU_SM8750P_20260331_143427.perfetto-trace`（22MB）
- **设备**: 联想 TB522FU (SM8750P, 8核: 6×little + 2×big)
- **目标进程**: `com.zui.launcher` (PID 631)
- **场景**: Launcher 慢划（滑动卡顿）

### Demo 1: 卡顿检测

| 指标 | 引擎 | MCP detect_jank | MCP frame_summary |
|------|------|----------------|-------------------|
| **总帧数** | 342 | **0** ❌ | **0** ❌ |
| **卡顿帧** | 3 (jank_num: 2279/93/1) | **0** ❌ | **0** ❌ |
| **刷新率** | 120Hz | - | - |
| **帧率** | 22.79 FPS | - | - |
| **评级** | 严重卡顿 | - | **EXCELLENT** ❌ |
| **分析方式** | VSync/Buffer 计数器 | actual_frame_timeline_slice | 同左 |

**结论**：MCP 依赖 `actual_frame_timeline_slice` 表，此 trace 中不存在该表，导致 **帧分析完全失败**。引擎使用 VSync/Buffer 计数器方式更通用可靠。

**评分**：引擎 5/5, MCP 0/5

### Demo 2: CPU 分析

| 指标 | 引擎 | MCP cpu_utilization |
|------|------|---------------------|
| **线程级 CPU 使用率** | 有（按线程聚合到窗口内） | ✅ 11 线程详细数据 |
| **频率分析** | ❌ 缺少数据（该 trace） | ✅ 8 核均有频率 |
| **频率爬升检测** | ✅ 6 核 3 步爬升，98.8ms | ❌ 无此能力 |
| **大小核调度** | ✅ little 100%，跨集群迁移 0 | ❌ 无此能力 |
| **调度延迟** | ✅ P50/P90/P99/MAX 分布 | ❌ 无此能力 |
| **输出格式** | Markdown 报告 + JSON | 结构化 JSON |

**结论**：两者互补。MCP 提供全局 CPU 视图（per-thread 使用率+频率），引擎提供逐帧窗口内的深度分析（爬升检测、大小核调度、调度延迟）。

**评分**：引擎 4/5, MCP 3/5

### Demo 3: 线程分析

| 指标 | 引擎 | MCP thread_contention |
|------|------|-----------------------|
| **分析范围** | 逐帧窗口内线程状态 | ✅ 全 trace 线程竞争 |
| **数据深度** | Running/S/D/R+时间 + CPU核分布 | 竞争次数/总阻塞/最大阻塞 |
| **主线程标识** | 有 | ✅ 有（CRITICAL 级别） |
| **Block 追踪** | Block/Waker 链（此 trace 无数据） | ❌ 无 waker（scheduler_inferred 模式） |
| **严重度评级** | 无 | ✅ CRITICAL/HIGH |
| **状态分布** | 全状态（R, R+, S, D, I） | 仅 Sleeping/D 状态 |

**结论**：互补关系明确。引擎提供精确到帧级的线程状态时间线，MCP 提供全局竞争概览和严重度评级。

**评分**：引擎 4/5, MCP 3/5

### Demo 4: Binder 分析

| 指标 | 引擎 | MCP binder_profiler |
|------|------|---------------------|
| **事务数** | 1382（全 trace） | **0** ❌ |
| **慢调用检测** | 有（阈值 2ms，无慢调用） | 无数据 |
| **目标-服务端关联** | ✅ launcher → system_server/surfaceflinger | 无数据 |
| **线程池饱和度** | 有 | 无数据 |

**结论**：MCP 的 `binder_transaction_profiler` 依赖 `android_binder_txns` 表，此 trace 中不存在。引擎使用 slice 级 binder 查询更通用。

**评分**：引擎 4/5, MCP 0/5

### Demo 5: MCP 独有能力

| 工具 | 结果 | 价值评估 |
|------|------|---------|
| **detect_anrs** | 0 ANR（预期，非 ANR 场景） | 场景适用时有价值 |
| **anr_root_cause_analyzer** | 未测（无 ANR） | 需 ANR trace 验证 |
| **memory_leak_detector** | 无数据（heap graph 不在 trace 中） | 需 heap dump trace |
| **main_thread_hotspot_slices** | ✅ **20 个热点 slice**，含调用层级 | **高价值 — 引擎没有的能力** |
| **find_slices "DrawFrame"** | ✅ 大量 DrawFrame 数据（3770 行） | **高价值 — 灵活的 slice 搜索** |
| **execute_sql_query** | ✅ 任意 SQL 查询 | **最高价值 — 万能兜底** |

**关键发现**：`main_thread_hotspot_slices` 和 `find_slices` 提供了引擎缺失的关键能力 — **函数级调用栈分析**。引擎只告诉你线程在睡觉/运行，MCP 能告诉你它在做什么。

### Demo 6: 引擎独有能力

| 维度 | 结果 | 保留价值 |
|------|------|---------|
| **IO 分析** | D-State 0.2ms, 4 次阻塞 | 中（MCP 无等效工具） |
| **GC 分析** | 0 GC 事件 | 中（MCP 无等效工具） |
| **GPU 渲染** | DrawFrame avg 1.93ms, P99 2.56ms | 高（逐帧 GPU 时间） |
| **SurfaceFlinger** | 在报告中体现 | 中 |
| **Input 延迟** | 在报告中体现 | 低（MCP hotspot 可替代） |
| **Lock 竞争** | 7 次，0.3ms | 中（MCP thread_contention 部分覆盖） |

## 决策矩阵

| 能力 | 引擎 | MCP | 推荐 | 理由 |
|------|------|-----|------|------|
| **卡顿检测** | **5** | 0 | **引擎** | MCP 依赖特定表，通用性不足 |
| **CPU 分析** | 4 | 3 | **混合** | MCP 全局视图 + 引擎逐帧深度 |
| **线程分析** | 4 | 3 | **混合** | 引擎帧级状态 + MCP 全局竞争 |
| **Binder 分析** | 4 | 0 | **引擎** | MCP 依赖特定表 |
| **ANR** | N/A | 3* | **MCP** | 引擎无此能力（需 ANR trace 验证） |
| **内存** | N/A | 2* | **MCP** | 引擎无此能力（需 heap trace 验证） |
| **主线程热点** | N/A | **5** | **MCP** | 函数级调用栈，引擎无此能力 |
| **Slice 搜索** | N/A | **5** | **MCP** | 灵活的模式搜索 |
| **任意 SQL** | N/A | **5** | **MCP** | 万能兜底查询 |
| **IO/GC/GPU/SF** | 3 | N/A | **引擎** | MCP 无等效工具 |

*标注：因 trace 数据限制未能充分验证

## 最终结论

### 推荐架构：混合模式（引擎核心 + MCP 补充扩展）

**理由**：

1. **引擎不可替代**：卡顿检测（VSync/Buffer 方式）和逐帧归因分析是核心竞争力，MCP 在此类 trace 上完全失败
2. **MCP 有独占优势**：主线程热点、Slice 搜索、任意 SQL 是引擎没有的高价值能力
3. **MCP 可靠性不足**：高度依赖 trace 中特定表的存在，通用性差（3/12 工具返回有效数据）
4. **两者互补明确**：CPU、线程维度各有侧重，结合使用效果最佳

### 架构演进建议

```text
perfetto_analysis Agent (编排层)
├── 引擎核心（保留并强化）
│   ├── 卡顿检测 + 逐帧归因（不可替代）
│   ├── CPU/Thread/Binder 逐帧窗口分析
│   └── IO/GC/GPU/SF/Lock 维度分析
├── MCP 工具（补充扩展）
│   ├── main_thread_hotspot_slices（函数级热点）
│   ├── find_slices（模式搜索）
│   ├── execute_sql_query（灵活查询）
│   ├── cpu_utilization_profiler（全局 CPU）
│   ├── thread_contention_analyzer（竞争概览）
│   └── ANR/Memory（场景扩展）
└── 结果整合层
    └── 引擎深度分析 + MCP 广度补充 → 压缩输出
```

### 待验证事项

- [ ] 使用包含 frame_timeline 数据的 trace 再次验证 MCP 帧检测能力
- [ ] 使用 ANR trace 验证 MCP ANR 分析能力
- [ ] 使用包含 heap graph 的 trace 验证内存分析能力
