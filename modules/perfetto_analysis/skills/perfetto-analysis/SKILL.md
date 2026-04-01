---
name: perfetto-analysis
description: >-
  Perfetto trace 全场景性能分析。涵盖卡顿/ANR/内存/启动/CPU/线程等多场景，
  通过 MCP + 引擎混合架构提供原子工具集，按场景路由分析策略。
  当用户提到 Perfetto、trace 分析、卡顿、丢帧、jank、fps、帧耗时、
  游戏性能、ANR、内存泄漏、启动慢、CPU 占用、线程阻塞时使用此技能。
---

# Perfetto 性能分析

## 资源索引

| 资源 | 路径 |
|------|------|
| 完整工具文档 | [tool-catalog.md](tool-catalog.md) |
| SOP 文档 | [sop/](sop/) |
| 根因模式库 | [patterns/](patterns/) |
| 案例库 | [cases/](cases/) |
| SQL 查询模式 | [sql-patterns.md](sql-patterns.md) |
| Agent 工具源码 | `modules/perfetto_analysis/src/plugin.py` |
| 引擎源码 | `modules/perfetto_analysis/src/engine/` |
| CLI 入口 | `python -m toolkit.app analysis <command>` |
| MCP 服务 | `user-perfetto-mcp`（12 个工具） |

## 分析流程

```
Task Progress:
- [ ] Step 1: 确认分析目标（trace 路径、目标进程、分析意图）
- [ ] Step 2: Trace 概览 → 场景分类 → 加载对应 SOP
- [ ] Step 3: 按 SOP 执行分析
- [ ] Step 4: 归因排序 → 输出结论
```

### Step 1：确认分析目标

向用户确认或从上下文推断：trace 文件路径、目标应用包名、分析场景。

### Step 2：场景路由

```
pa_trace_overview(trace_path, process_name?)
```

返回 duration_s、frame_count、processes、refresh_rate_hz。
根据用户意图和关键词路由到对应 SOP：

| 场景 | 关键词 | SOP | 核心工具 |
|------|--------|-----|----------|
| **卡顿/掉帧** | 卡顿、丢帧、jank、fps、帧率 | [jank-analysis.md](sop/jank-analysis.md) | pa_detect_jank → pa_analyze_dimension |
| **响应时延** | 响应慢、返回慢、点击延迟、Back/Home 键、上划返回桌面 | [response-latency.md](sop/response-latency.md) | pa_execute_sql + 唤醒链追踪 |
| **输入时延** | 笔写时延、触控延迟、不跟手 | [input-latency.md](sop/input-latency.md) | pa_execute_sql + buffer 分析 |
| **启动性能** | 启动慢、冷启动、热启动、TTID、解锁慢 | [startup-analysis.md](sop/startup-analysis.md) | pa_execute_sql + pa_find_slices |
| **转屏/配置变更** | 旋转慢、转屏、横竖屏 | [rotation-analysis.md](sop/rotation-analysis.md) | pa_execute_sql + 唤醒链追踪 |
| **ANR/无响应** | ANR、无响应、卡死、freeze | [anr-analysis.md](sop/anr-analysis.md) | pa_analyze_anr |
| **内存问题** | 内存泄漏、OOM、heap | [memory-analysis.md](sop/memory-analysis.md) | pa_analyze_memory |
| **CPU/线程** | CPU 占用、线程阻塞、调度延迟 | 见下方维度分析 | pa_cpu_overview + pa_analyze_dimension |
| **IO 阻塞** | IO block、D-State、文件读取慢 | [io-block-analysis.md](sop/io-block-analysis.md) | pa_analyze_dimension(io) + pa_execute_sql |
| **通用/不明确** | "分析一下"、"看看性能" | [general-analysis.md](sop/general-analysis.md) | 场景分类 → 路由 |

**⚠️ 路由决定工具选择**：MUST 先完成场景路由，再调用对应 SOP 指定的工具。不同场景使用不同工具链：
- `pa_detect_jank` / `analysis parse` **仅适用于卡顿/掉帧场景**，不得用于响应时延、启动、转屏等场景
- 响应时延/启动/转屏场景使用 `pa_execute_sql` 查询特定 slice 和时间窗口
- 批量分析多个 trace 时，MUST 逐个路由，不得统一使用同一工具链

**⚠️ 批量分析编排策略**：当用户要求分析多个 trace 时，MUST 采用以下隔离策略防止上下文膨胀：

1. **独立分析**：每个 trace 使用独立 subagent（`Task` 工具）分析，各自的 MCP 返回数据不进入主 agent 上下文
2. **摘要回传**：subagent 分析完成后仅返回**结论摘要**（按 Step 6 输出模板），不回传原始 MCP 数据
3. **主 agent 职责**：执行场景路由（Step 2）并分配 subagent，汇总各 trace 结论，不参与具体分析
4. **compact 优先**：subagent 内部调用工具时优先使用 `compact=True` 减少返回量
5. **并行限制**：同时运行的 subagent 不超过 3 个，避免系统资源争抢

示例编排：
```
主 Agent:
  1. 收集所有 trace 路径
  2. 对每个 trace 执行 Step 2 场景路由
  3. 为每个 trace 启动 Task(subagent_type="generalPurpose"):
     - prompt: "分析 <trace_path>，目标进程 <process>，场景 <scenario>，
       按 perfetto-analysis Skill 的 Step 3-6 完成分析，
       返回 Step 6 输出模板格式的结论摘要"
  4. 汇总所有 subagent 结论
```

### Step 3：渲染管线识别

分析前需确认渲染管线类型，决定帧检测策略：

| 管线类型 | 识别特征 | 帧检测策略 |
|----------|----------|-----------|
| 标准 HWUI | `RenderThread` + `Choreographer#doFrame` | VSync/FrameTimeline（引擎默认） |
| 游戏 EGL | `eglSwapBuffers` + UnityMain/GameThread | `eglSwapBuffers` 间隔 |
| 游戏 Vulkan | `vkQueuePresentKHR` | `vkQueuePresentKHR` 间隔 |
| Flutter | `1.ui` + `1.raster` 线程 | 双管线帧检测 |
| WebView | `CrRendererMain` 线程 | Chromium 渲染流程 |

识别 SQL 见 [sql-patterns.md](sql-patterns.md#渲染管线识别)。

**App 侧一帧的完整流程**（标准 HWUI）：

VSync-App 到达 → 主线程 `Choreographer#doFrame`（input → animation → traversal）→ 主线程/RenderThread 同步 → RenderThread `dequeueBuffer` → 渲染 → `queueBuffer` → SF 在 VSync-SF 时合成

**SF 侧关键泳道与 slice**：详见 [jank-analysis.md — SF 维度分析要点](sop/jank-analysis.md#sf-维度分析要点)

### Step 4：维度分析（卡顿场景）

按优先级调用 `pa_analyze_dimension(trace_path, dimension, process_name, time_range?)`：

| 优先级 | 维度 | 数据源 | 关注点 |
|--------|------|--------|--------|
| P0 | cpu | MCP/引擎 | Running/Runnable 时间、调度延迟 |
| P0 | thread | MCP/引擎 | 线程状态分布（R/S/D）、阻塞原因 |
| P1 | binder | MCP 优先 | 慢 Binder（>2ms）、线程池饱和 |
| P1 | gpu | 引擎 | GPU 完成时间、fence 等待 |
| P1 | sf | 引擎 | SF 合成耗时 |
| P2 | io/gc/input/lock | 引擎 | D-State、GC STW、输入延迟、锁竞争 |
| P3 | hotspot | MCP 独有 | 主线程热点函数 |

### Step 5：线程状态分布后的分支决策

获取主线程状态分布后，根据**占比最高的异常状态**选择下一步分析：

| 线程状态 | 触发条件 | 下一步 |
|---------|---------|--------|
| **Running 高** (>40%) | 主线程 CPU 密集 | → 检查 CPU 频率是否受限（`pa_execute_sql` 查 `cpu_freq` counter）；检查运行在哪个核心（大/小核）；查看 hotspot 热点函数 |
| **Sleeping 高** (>40%) | 主线程大量等待 | → 唤醒链追踪（waker 分析），定位等待的 binder/锁/IO 对象 |
| **Runnable 高** (>10%) | CPU 排队严重 | → 检查 CPU 负载和核心利用率；检查是否有其他高优线程抢占 CPU |
| **D-State 高** (>5%) | IO 阻塞 | → 参见 [io-block-analysis.md](sop/io-block-analysis.md) |

CPU 频率检查 SQL 见 [sql-patterns.md](sql-patterns.md#cpu-频率查询)。

### Step 6：归因与输出

按优先级排查：线程状态异常 → 调度延迟 → CPU 频率 → Binder → IO/GC/Lock。

**输出模板**：

```markdown
## 性能分析结论

### 基本信息
- **Trace**: <文件名> | **设备**: <型号> | **刷新率**: <Hz>
- **渲染管线**: <类型> | **Trace 时长**: <s>

### 问题概况
- <场景描述>：<量化数据>

### 根因分析（按严重程度排序）
1. **[CRITICAL/HIGH/MEDIUM] <原因>**
   - 证据：<具体数据>
   - 影响：<范围>

### 关键数据摘要
| 维度 | 关键指标 | 值 | 状态 |
|------|---------|-----|------|

### 排查建议
- 基于数据的排查方向
```

## 工具选择原则

| 场景 | 推荐 | 原因 |
|------|------|------|
| 有 pa_* 覆盖的分析 | pa_* 工具 | 自动路由、降级、chain 记录 |
| MCP 特有参数 | 直接调用 MCP | severity_filter、group_by |
| 完整报告文件 | CLI `analysis export` | 生成 Markdown 报告 |
| 自定义数据探索 | pa_execute_sql | 灵活 SQL |
| 快速批量分析 | pa_analyze | 完整流水线 |

工具完整参数见 [tool-catalog.md](tool-catalog.md)。

## 关键注意事项

- Jank 阈值：App Deadline > 1.5× VSync，SF Composition 窗口 0.5× VSync
- trace 首个 VSync 周期跳过 jank 判定（P26 首周期守卫）
- 游戏 trace 的 `pa_detect_jank` 可能返回空，需用游戏帧降级方案（eglSwapBuffers 间隔）
- VSync 周期：60Hz=16.67ms, 90Hz=11.11ms, 120Hz=8.33ms, 144Hz=6.94ms
- 分析模式通过 `config.json` 的 `analysis_mode` 控制
- 已知误判模式见 [patterns/root-cause-patterns.md](patterns/root-cause-patterns.md)
- 所有脚本在项目虚拟环境下执行

## 详细参考

- SQL 查询模板 → [sql-patterns.md](sql-patterns.md)
- 完整工具文档 → [tool-catalog.md](tool-catalog.md)
- 历史分析案例 → [cases/](cases/)
