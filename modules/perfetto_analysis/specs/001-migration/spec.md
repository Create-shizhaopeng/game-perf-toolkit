# Feature Specification: Perfetto 解析分析工具（模块迁移）

**Feature Branch**: `001-migration`
**Created**: 2026-03-23
**Status**: Draft
**Input**: 从 `_archived_source/perfettoAnalysisByPython` 迁移至 lv-game-toolkit 模块体系，包含 Phase 1（丢帧解析）spec 001 + Phase 2（卡顿归因分析）spec 002 的全部功能。

## 目录

- [Clarifications](#clarifications)
- [迁移概述](#迁移概述)
- [User Scenarios & Testing](#user-scenarios--testing)
- [功能需求 — 迁移自源项目](#功能需求--迁移自源项目)
  - [Phase 1: 丢帧解析（FR-001 ~ FR-009）](#phase-1-丢帧解析fr-001--fr-009)
  - [Phase 2: 卡顿归因分析（FR-100 ~ FR-120）](#phase-2-卡顿归因分析fr-100--fr-120)
- [功能需求 — Toolkit 集成（新增）](#功能需求--toolkit-集成新增)
  - [FR-200: Plugin 注册](#fr-200-plugin-注册)
  - [FR-201: Pydantic 配置模型](#fr-201-pydantic-配置模型)
  - [FR-202: Service 封装层](#fr-202-service-封装层)
  - [FR-203: Typer CLI](#fr-203-typer-cli)
  - [FR-204: PyQt6 GUI Tab](#fr-204-pyqt6-gui-tab)
  - [FR-205: 混合 DB 策略](#fr-205-混合-db-策略)
  - [FR-206: perfetto_capture 事件联动](#fr-206-perfetto_capture-事件联动)
  - [FR-207: Agent 工具注册](#fr-207-agent-工具注册)
- [Key Entities](#key-entities)
- [边界条件与异常处理](#边界条件与异常处理)
- [Success Criteria](#success-criteria)
- [实施变更记录](#实施变更记录)

---

## Clarifications

### Session 2026-03-23

- **C-001**: engine/ 子包的内部引用策略？ → **保持内部相对引用不变**。源项目模块间的 `from . import parser` 等相对导入不做修改，仅调整 engine/ 包的包名。外层通过 `from .engine import parser` 访问。最小化核心逻辑改动。
- **C-002**: 报告文件存放位置？ → **开发环境**：`data/output/trace_report/<trace_stem>/`（相对项目根目录）；**打包后**：`<exe_dir>/output/trace_report/<trace_stem>/`。配置中 `output_dir` 的默认值为 `output/trace_report`。*(2026-03-23 修订：从 `output/analysis` 改为 `output/trace_report`)*
- **C-003**: perfetto Python 包版本？ → **使用 perfetto>=0.16.0**（当前最新版）。实现阶段安装。
- **C-004**: 配置文件格式？ → **仅保留 JSON 格式**（去掉 YAML 支持），与 toolkit 其他模块一致。源项目的 YAML 配置仅包含 3 个基本类型配置项（output_dir/db_path/refresh_rate_preset），转 JSON 零风险。迁移后使用 Pydantic 模型管理配置。
- **C-005**: GUI 中 Top N / Binder 阈值 / 调度延迟是否保留？ → **从 GUI 中移除**，这些参数对用户意义不大，保留在 config.json 中使用默认值即可。
- **C-006**: "重新生成报告"功能行为？ → **从数据库已有数据重新生成 Markdown 报告**，不重新分析 trace 文件。读取模块 DB 中的 trace_run、trace_summary、jank_record 数据，调用 export 模块输出报告。
- **C-007**: 删除分析记录行为？ → **仅删除当前记录**（按 task_id），若同一 trace 无其他模式记录则同时清理模块 DB 数据和磁盘文件。
- **C-008**: 进程名显示？ → 未指定目标进程时，**自动从 trace 中检测并显示进程名**（纯包名如 `com.tencent.xxx`，去掉 PID 和 SurfaceView 前缀），在报告和 GUI 历史中均展示。

---

## 迁移概述

### 源项目概况

源项目 `perfettoAnalysisByPython` 是一个独立的 Python 工具，用于 Perfetto trace 的丢帧解析与卡顿归因分析。包含 20 个 Python 模块（~160KB 代码），分为两个阶段：

- **Phase 1**（spec 001）：丢帧解析——基于 Android 丢帧 SOP，通过 Perfetto `TraceProcessor` 查询 vsync/buffer 数据，执行三条丢帧判定，持久化到 SQLite，导出 Markdown 报告
- **Phase 2**（spec 002）：卡顿归因——对已定位的丢帧区间进行 9 维度多层分析（CPU/Thread/Binder/IO/GC/GPU/SF/Input/Lock + Summary），产出结构化数据拆解报告

### 迁移目标

将源项目完整迁移为 `modules/perfetto_analysis/` 插件模块，遵循 lv-game-toolkit 的 Constitution 和开发规范，实现：

1. **Plugin-First**：pluggy 注册，pa_ 前缀 context 键
2. **Three-Surface Unity**：GUI (PyQt6) + CLI (Typer) + Agent 共享 Service API
3. **Agent-Driven Design**：所有分析能力可被 Agent 调用
4. **Spec-Driven Development**：遵循 speckit 8 步流程

### 迁移策略

源项目 20 个分析模块放入 `src/engine/` 子包，保持内部逻辑和引用关系不变，外层通过 Service 层封装对接 GUI/CLI/Agent 三端。

### 架构决策

| 决策项 | 结论 |
|--------|------|
| 模块名称 | `perfetto_analysis`，context 前缀 `pa_`，CLI: `analysis` |
| 数据库 | 混合方案：模块独立 SQLite（详细分析数据）+ 共享 DB 索引表（跨模块发现） |
| GUI | 完整 GUI（文件选择、配置、分析进度、结果预览、报告管理） |
| perfetto_capture 集成 | 默认独立，可配置事件联动（监听 `perfetto_capture.trace_ready`） |
| 迁移范围 | 全量迁移（Phase 1 + Phase 2 所有分析维度） |

---

## User Scenarios & Testing

### US-1: 通过 GUI 选择 trace 文件进行一键分析 (Priority: P1)

用户通过 GUI 界面选择一个 Perfetto trace 文件，指定目标进程，点击"开始分析"执行完整流程（Phase 1 丢帧解析 + Phase 2 归因分析 + 报告导出）。分析过程中显示实时进度，完成后在界面预览丢帧概览和报告路径。

**Acceptance Scenarios**:

1. **Given** GUI 已启动且 trace 文件存在，**When** 用户选择 trace 文件并点击"开始分析"，**Then** 分析进度实时显示，完成后生成报告并在 GUI 中显示结果概览。
2. **Given** 分析正在进行中，**When** 用户点击"停止"，**Then** 分析安全中止，已完成部分的结果保留。
3. **Given** 分析完成，**When** 用户点击"打开报告"，**Then** 报告文件夹自动打开。

### US-2: 通过 CLI 命令解析 trace 并导出报告 (Priority: P1)

用户通过 CLI 命令行执行与源项目等效的所有操作：仅解析、完整分析导出（`--export`）、独立维度分析（`--analyze`）。CLI 输出支持 JSON 格式（`--json`），便于 Agent 调用。

**Acceptance Scenarios**:

1. **Given** trace 文件存在，**When** 用户执行 `analysis export <trace> --process <pkg>`，**Then** 完整流程执行并生成合并报告。
2. **Given** trace 文件存在，**When** 用户执行 `analysis analyze <trace> --dims cpu thread`，**Then** 仅执行 CPU 和线程维度分析。
3. **Given** 用户执行 `analysis dims`，**Then** 输出可用维度列表及描述。

### US-3: 配置分析参数 (Priority: P2)

用户通过配置文件调整分析参数（刷新率预设、Top N 丢帧数、Binder 阈值、调度延迟阈值、输出目录等），无需修改代码。GUI 中仅暴露核心参数（App 类型、目标进程、分析模式与维度），其余参数通过 `data/config.json` 配置。

**Acceptance Scenarios**:

1. **Given** 用户修改了配置中的刷新率预设为 120Hz，**When** 执行分析，**Then** 使用 120Hz 作为基准周期。
2. **Given** 用户修改了 config.json 中的阈值配置，**When** 重启后执行分析，**Then** 新配置生效。

### US-4: 查看和管理分析报告 (Priority: P2)

用户通过 GUI 查看已完成的分析历史（合并共享 DB 记录和磁盘上已有报告），可执行以下操作：重新生成报告（从 DB 数据）、打开报告文件、打开报告目录、删除分析记录。

**Acceptance Scenarios**:

1. **Given** 已有多次分析历史，**When** 用户在 GUI 中查看历史列表，**Then** 显示所有分析记录（trace 名、目标进程、模式、时间、状态、操作）。
2. **Given** 选中历史记录，**When** 用户点击"打开报告"，**Then** 对应 Markdown 报告文件打开。
3. **Given** 选中历史记录，**When** 用户点击"重新生成"，**Then** 从 DB 中已有数据重新生成 Markdown 报告，不重新分析 trace。
4. **Given** 同一 trace 有完整/仅解析/独立维度三种记录，**When** 用户删除其中一条，**Then** 仅该条记录被删除，其他记录保留且可操作。
5. **Given** 同一 trace 仅剩最后一条记录，**When** 用户删除该记录，**Then** 同时清理磁盘文件和模块 DB 数据。

### US-5: 与 perfetto_capture 联动自动分析 (Priority: P3)

当 perfetto_capture 模块抓取完成并发出 `trace_ready` 事件时，perfetto_analysis 可选自动触发分析。此功能默认关闭，用户可在配置中启用。

**Acceptance Scenarios**:

1. **Given** 用户启用了"抓取后自动分析"配置，**When** perfetto_capture 完成抓取并发出事件，**Then** perfetto_analysis 自动开始分析该 trace。
2. **Given** 用户未启用自动分析，**When** perfetto_capture 完成抓取，**Then** perfetto_analysis 不执行任何操作。

### US-6: Agent 通过 Service API 调用分析能力 (Priority: P3)

AI Agent 通过 ServiceRegistry 调用 perfetto_analysis 的分析能力，获取 JSON 格式的分析结果，用于自动化性能诊断流程编排。

**Acceptance Scenarios**:

1. **Given** Agent 获取到 trace 文件路径，**When** 调用 `pa_analyze` 工具，**Then** 返回 JSON 格式的分析结果。
2. **Given** Agent 需要按维度分析，**When** 调用 `pa_analyze_dims` 工具并指定维度，**Then** 仅执行指定维度并返回结果。

---

## 功能需求 — 迁移自源项目

### Phase 1: 丢帧解析（FR-001 ~ FR-009）

以下需求完整继承自源项目 spec 001，核心逻辑保持不变，仅适配 Toolkit 框架接口。

- **FR-001**: 支持通过 Service API / CLI / GUI 接收 trace 文件路径，单次可接受多个路径并依次解析、分别持久化；仅支持标准 Perfetto 格式。
- **FR-002**: 按照「Android 丢帧问题定位 SOP」执行拆解逻辑：vsync 周期基准、buffer 数量变化、三条丢帧判定规则（含双周期校验前置守卫）、丢帧统计。Buffer 数据源从 Perfetto `counter` 表查询 SurfaceFlinger 进程的 BufferTX counter_track。
- **FR-003**: 解析结果持久化到模块独立 SQLite 数据库；同一 trace 再次解析覆盖旧数据。
- **FR-004**: 提供将持久化内容导出为 Markdown 格式报告的能力，每个 trace 生成独立报告文件。
- **FR-005**: 支持通过 Pydantic 配置模型设置可配置项（替代源项目的 dict 配置），配置文件为 JSON 格式。
- **FR-006**: 源码模块化：分析引擎各功能由 `src/engine/` 下独立模块承担。
- **FR-007**: 所有输出（报告、日志）中文无乱码，UTF-8 编码。
- **FR-008**: 报告中时间显示为北京时间、24h 制、含年月日、精确到 1ms；通过 `clock_snapshot` 获取 BOOTTIME → REALTIME 偏移。
- **FR-009**: 支持指定目标进程名用于 BufferTX 轨道匹配；未指定时自动选择含 SurfaceView 的轨道。

### Phase 2: 卡顿归因分析（FR-100 ~ FR-120）

以下需求完整继承自源项目 spec 002，核心逻辑保持不变。

- **FR-100**: 流程集成——完整分析触发 Phase 1 + Phase 2，共享同一 TraceProcessor 实例。支持 App 类型自动检测（app/game/camera）和 `--app-type` 手动覆盖。
- **FR-101**: CPU 拓扑初始化——核心数、集群划分（big/mid/little）、各集群最大频率。
- **FR-102**: 基础环境信息输出——trace 路径、包名、App 类型、拓扑、刷新率、丢帧统计、时长。
- **FR-103**: 帧边界确定——按 App 类型（Choreographer/eglSwapBuffers/BufferTX）定位帧边界。
- **FR-104**: 帧内线程状态时间线——关键线程（UI Thread/RenderThread/GameThread 等）的状态查询。
- **FR-105**: 线程间 Block/Waker 链分析——阻塞 >1ms 时追溯唤醒链，上限 10 层。
- **FR-106**: CPU 频率与爬升状态分析——频率爬升/稳定/降频检测。
- **FR-107**: 大小核调度分析——各集群运行时间占比、核迁移统计。
- **FR-108**: 调度延迟分析——Runnable 等待时间 P50/P90/P99/MAX，异常调度延迟详情。
- **FR-109**: Binder 调用分析——慢 Binder（>2ms）列表和耗时拆解。
- **FR-110**: Binder 线程池饱和度——并发活跃数/池大小/饱和时间段。
- **FR-111**: 文件 IO 阻塞分析——D 状态列表、阻塞函数分类、总时长。
- **FR-112**: 卡顿归因综合报告（逐帧级）——每条 jank_record 的全维度结构化数据拆解。
- **FR-113**: 卡顿归因摘要与统计——调度延迟分布、慢 Binder Top-5、IO 阻塞 Top-5 等汇总。
- **FR-114**: GC 阻塞分析——GC 事件列表、STW 时长。
- **FR-115**: GPU 渲染耗时分析——DrawFrame/dequeueBuffer/GPU Render Stage 耗时。
- **FR-116**: SurfaceFlinger 合成耗时分析——commit/composite 阶段耗时。
- **FR-117**: 输入事件延迟分析——Input 到帧渲染的延迟、慢输入事件。
- **FR-118**: Java Monitor 锁竞争分析——锁竞争列表、严重竞争（>1ms）。
- **FR-119**: 全 Trace 整体分析（summary 维度）——CPU/GPU/帧率匹配/Binder/IO/GC/锁竞争的全局统计。
- **FR-120**: 独立分析模式——按维度（cpu/thread/binder/io/gc/gpu/sf/input/lock/summary）独立执行分析，支持 `--window` 和 `--jank-index` 指定分析范围。

---

## 功能需求 — Toolkit 集成（新增）

### FR-200: Plugin 注册

- `PerfettoAnalysisPlugin` 继承 `BasePlugin`，实现所有 `@hookimpl` 钩子
- `on_startup` 中注册 context 键：`pa_service`（PerfettoAnalysisService）、`pa_adb`（AdbManager）、`pa_data_dir`（模块数据目录）
- `register_gui_tab` 返回 `PerfettoAnalysisTab` 实例
- `register_cli_commands` 注册 `analysis` 命名空间的 Typer 子命令
- `register_agent_tools` 注册 Agent 可调用的分析工具
- manifest.json 声明 `cli_namespace: "analysis"`、`listens: ["perfetto_capture.trace_ready"]`

### FR-201: Pydantic 配置模型

替代源项目的 dict 配置，定义 `AnalysisConfig` Pydantic 模型：

| 配置项 | 类型 | 默认值 | GUI 可编辑 | 说明 |
|--------|------|--------|-----------|------|
| output_dir | str | "output/trace_report" | ❌ | 报告输出基础目录（C-002） |
| db_path | str | "perfetto_analysis.db" | ❌ | 模块独立 DB 路径（相对于 data/） |
| refresh_rate_preset | int | 60 | ❌ | 刷新率预设（Hz） |
| app_type | str | "auto" | ✅ | App 类型（auto/app/game/camera） |
| analyze_top | int | 20 | ❌ | 逐帧分析 Top N（C-005: 从 GUI 移除） |
| slow_binder_threshold_ms | float | 2.0 | ❌ | 慢 Binder 阈值（C-005: 从 GUI 移除） |
| sched_latency_threshold_ms | float | 1.0 | ❌ | 异常调度延迟阈值（C-005: 从 GUI 移除） |
| auto_analyze_on_capture | bool | False | ❌ | 抓取完成后是否自动触发分析 |
| default_process | str | "" | ✅ | 默认目标进程名 |
| dimensions | list[str] | [] | ✅ | 默认分析维度（空=全部） |

配置文件路径：`assets/config.json`（默认模板）→ `data/config.json`（用户配置）。

### FR-202: Service 封装层

`PerfettoAnalysisService` 作为 Three-Surface Unity 的 API 层，纯同步实现，不依赖 GUI 框架：

| 方法 | 说明 |
|------|------|
| `analyze(trace_path, process_name, on_progress)` | 完整分析（Phase 1 + Phase 2 + 导出） |
| `parse_only(trace_path, process_name, on_progress)` | 仅 Phase 1 丢帧解析 |
| `analyze_dimensions(trace_path, process_name, dimensions, on_progress)` | 按维度独立分析 |
| `export_report(trace_path, output_dir)` | 导出已有分析结果为报告 |
| `regenerate_report(trace_path, on_progress)` | 从 DB 已有数据重新生成报告（C-006） |
| `list_dimensions()` | 返回可用维度列表 |
| `get_analysis_history()` | 查询分析历史记录（合并共享 DB + 磁盘扫描） |
| `delete_analysis_record(task_id, trace_path, report_dir)` | 删除分析记录（C-007） |
| `reload_config(config_path)` | 重新加载配置 |
| `get_config()` | 获取当前配置 |

所有方法支持 `on_progress: Callable[[str], None] | None` 回调。

### FR-203: Typer CLI

将源项目的 argparse CLI 迁移为 Typer 子命令，挂载在 `analysis` 命名空间下：

| 命令 | 对应源项目功能 | 说明 |
|------|-------------|------|
| `analysis parse <traces...>` | 仅解析模式 | Phase 1 解析并持久化 |
| `analysis export <traces...>` | `--export` | 完整流程（Phase 1 + Phase 2 + 报告） |
| `analysis analyze <traces...> --dims <dims>` | `--analyze` | 独立维度分析 |
| `analysis dims` | `--analyze`（无参数） | 列出可用维度 |
| `analysis history` | 新增 | 查看分析历史 |

公共参数：`--process`、`--config`、`--output-dir`、`--app-type`、`--analyze-top`、`--timing`、`--window`、`--jank-index`、`--format`。

所有命令 SHOULD 支持 `--json` 输出格式。

### FR-204: PyQt6 GUI Tab

完整的分析界面，继承 `BaseTab`，采用左右分栏布局（QSplitter），左侧固定宽度 580px。

**左侧面板**（固定宽度，不随窗口缩放）：
1. **Trace 文件选择区**：QLineEdit（320px）+ 浏览按钮 + 拖拽支持
2. **分析配置区**：目标进程输入（240px）、App 类型 + 分析模式 + 维度多选（同一行）
3. **分析控制区**（配置与历史之间）：状态指示 + 开始/停止按钮（各 100px, 带图标）+ 进度条
4. **分析历史区**：6 列固定宽度表格（Trace/目标进程/模式/时间/状态/操作），操作含重新生成、打开报告、打开目录、删除

**右侧面板**（自适应宽度）：
5. **结果预览区**：分析完成后显示——目标进程、报告路径、丢帧概览、维度完成状态
6. **操作日志**（底部固定 150px）：实时日志输出

GUI 后台线程通过 `QThread` + `pyqtSignal` 执行分析任务。维度多选采用 QPushButton + _PersistentMenu（QMenu 子类，避免 Windows 下 QComboBox 自定义 popup 导致的 COM 线程崩溃）。

详细布局设计见 [ui-design.md](ui-design.md)。

### FR-205: 混合 DB 策略

- **模块独立 DB**：`modules/perfetto_analysis/data/perfetto_analysis.db`
  - 保持源项目 schema 不变（trace_run、vsync_cycle、buffer_event、jank_record、trace_summary、cpu_topology、analysis_report 等表）
  - 模块内部通过 `src/engine/storage.py` 直接管理
- **共享 DB 索引表**：通过 toolkit 的 `db_manager` 迁移机制创建 `pa_analysis_tasks` 表

```sql
CREATE TABLE IF NOT EXISTS pa_analysis_tasks (
    task_id TEXT PRIMARY KEY,
    trace_path TEXT NOT NULL,
    device_serial TEXT,
    analysis_db_path TEXT NOT NULL,
    report_dir_path TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at INTEGER NOT NULL,
    completed_at INTEGER,
    error_message TEXT,
    process_name TEXT DEFAULT '',      -- 迁移脚本 002 添加
    mode TEXT DEFAULT 'full',          -- 迁移脚本 003 添加 (full/parse/dimensions)
    dimensions TEXT DEFAULT ''         -- 迁移脚本 003 添加 (逗号分隔的维度列表)
);
```

去重策略：同一 `trace_path` + `mode` 组合视为同一记录，重新分析时覆盖旧记录。

### FR-206: perfetto_capture 事件联动

- manifest.json 声明 `listens: ["perfetto_capture.trace_ready"]`
- plugin.py 中实现事件监听钩子
- 当 `auto_analyze_on_capture` 配置为 True 时，收到事件后自动触发分析
- 事件 payload 中包含 trace_path 和 device_serial

### FR-207: Agent 工具注册

通过 `register_agent_tools` 钩子注册以下 Agent 可调用工具：

| 工具名 | 方法 | 说明 |
|--------|------|------|
| `pa_analyze` | `service.analyze()` | 完整分析 |
| `pa_parse` | `service.parse_only()` | 仅解析 |
| `pa_analyze_dims` | `service.analyze_dimensions()` | 按维度分析 |
| `pa_list_dims` | `service.list_dimensions()` | 列出维度 |
| `pa_history` | `service.get_analysis_history()` | 查询历史 |

---

## Key Entities

### 配置模型（Pydantic）

- **AnalysisConfig**: 分析配置（output_dir, db_path, refresh_rate_preset, app_type, analyze_top, 各阈值, auto_analyze_on_capture 等）

### 内部数据模型（dataclass）

- **AnalysisTask**: 分析任务（task_id, trace_path, process_name, mode, dimensions, status, result）
- **ParseResult**: Phase 1 解析结果（vsync_cycles, jank_records, jank_times, frame_num 等）
- **AnalysisResult**: Phase 2 分析结果（app_type, cpu_topology, per_jank_analyses, summary_analysis）
- **DimensionResult**: 维度分析结果（dimension_id, data, error）

### DB 实体（模块独立 DB）

- **trace_run**: Trace 运行记录
- **vsync_cycle**: Vsync 周期数据
- **buffer_event**: Buffer 事件数据
- **jank_record**: 丢帧记录
- **trace_summary**: Trace 概要统计
- **cpu_topology**: CPU 拓扑信息
- **analysis_report**: 分析报告路径索引

### DB 实体（共享 DB）

- **pa_analysis_tasks**: 分析任务索引（供跨模块发现）

---

## 边界条件与异常处理

| 场景 | 预期行为 |
|------|---------|
| trace 文件不存在或损坏 | 明确错误提示，不崩溃 |
| 未指定 `--process` | Phase 1 自动选择 SurfaceView 轨道；Phase 2 提示需要指定目标进程 |
| 无丢帧（jank_records 为空） | 跳过逐帧分析，输出 Phase 1 概览 + 全 Trace 整体分析 |
| trace 中缺少 sched/cpu_freq 等数据 | 对应维度分析降级跳过，报告中注明 |
| 分析窗口过大（jank_num > 20） | 逐帧分析仅采集 Top-20 最长阻塞事件，注明截断 |
| GC/Monitor/GPU/Input 数据不存在 | 对应分析静默跳过 |
| perfetto Python 包未安装 | 启动时检测并给出安装提示 |
| GUI 中分析进行时关闭窗口 | 安全中止分析线程 |
| 同一 trace 重复分析 | 覆盖旧结果（模块 DB + 报告文件） |

---

## Success Criteria

### 继承自源项目

- **SC-001**: 对典型 trace（≤500MB），完整解析与持久化在 2 分钟内完成。
- **SC-002**: 丢帧数量、次数及起止时间与 Android 丢帧 SOP 规则一致。
- **SC-003**: 报告时间戳为北京时间、24h 制、含年月日、精确到 1ms；中文无乱码。
- **SC-004**: 修改配置后工具行为随之变化。

### 新增 Toolkit 集成

- **SC-005**: GUI 一键分析功能正常，进度实时显示，结果可预览。
- **SC-006**: CLI `analysis` 命名空间下所有命令等效可用，`--json` 输出格式正确。
- **SC-007**: 共享 DB `pa_analysis_tasks` 索引正确记录每次分析任务。
- **SC-008**: `perfetto_capture.trace_ready` 事件联动可配置，启用后自动触发分析。
- **SC-009**: 模块内所有 Service 公共方法至少有一个测试用例通过。
- **SC-010**: Plugin context 键使用 `pa_` 前缀，不与其他模块冲突。
- **SC-011**: GUI 后台分析通过 QThread + pyqtSignal 通信，无跨线程 UI 操作。
- **SC-012**: 500MB trace 完整流程（Phase 1 + Phase 2 + 报告）耗时目标 ≤5 分钟。

---

## 实施变更记录

| 日期 | 变更项 | 说明 |
|------|--------|------|
| 2026-03-23 | C-002 修订 | 报告输出目录从 `output/analysis` 改为 `output/trace_report`，开发环境存入 `data/output/trace_report/` |
| 2026-03-23 | C-005 新增 | GUI 中移除 Top N / Binder 阈值 / 调度延迟三个配置项，使用 config.json 默认值 |
| 2026-03-23 | C-006 新增 | "重新生成报告"功能改为从 DB 已有数据生成，非重新分析 trace |
| 2026-03-23 | C-007 新增 | 删除分析记录支持智能清理：仅删除当前记录，最后一条记录时清理磁盘文件 |
| 2026-03-23 | C-008 新增 | 未指定进程时自动检测并展示进程名 |
| 2026-03-23 | FR-202 更新 | Service 新增 `regenerate_report` 和 `delete_analysis_record` 方法 |
| 2026-03-23 | FR-204 更新 | GUI 左右分栏布局重构，左侧固定 580px，控制区移至配置与历史之间 |
| 2026-03-23 | FR-205 更新 | pa_analysis_tasks 表新增 process_name、mode、dimensions 字段（迁移脚本 002/003） |
| 2026-03-23 | US-3 更新 | GUI 不再暴露 Top N 等参数，通过 config.json 配置 |
| 2026-03-23 | US-4 更新 | 历史管理增加重新生成、智能删除等操作 |
