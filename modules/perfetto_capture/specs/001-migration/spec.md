# Perfetto 卡顿抓取模块迁移 — 规格说明

## 目录

- [背景与目标](#背景与目标)
  - [背景](#背景)
  - [源项目分析](#源项目分析)
  - [目标](#目标)
- [关联规格](#关联规格)
- [用户故事](#用户故事)
  - [P1 — 核心抓取](#p1-核心抓取)
  - [P2 — 配置管理](#p2-配置管理)
  - [P3 — 断线恢复](#p3-断线恢复)
  - [P4 — CLI 自动化](#p4-cli-自动化)
- [功能需求](#功能需求)
  - [FR-001 配置管理](#fr-001-配置管理)
  - [FR-002 Perfetto 抓取引擎](#fr-002-perfetto-抓取引擎)
  - [FR-003 会话管理](#fr-003-会话管理)
  - [FR-004 设备断线重连](#fr-004-设备断线重连)
  - [FR-005 CLI 命令](#fr-005-cli-命令)
  - [FR-006 GUI 页面](#fr-006-gui-页面)
  - [FR-007 事件通知](#fr-007-事件通知)
- [数据模型](#数据模型)
  - [CaptureConfig (Pydantic)](#captureconfig-pydantic)
  - [CaptureMode (enum)](#capturemode-enum)
  - [RunningTrace (dataclass)](#runningtrace-dataclass)
  - [TraceItem (dataclass)](#traceitem-dataclass)
  - [CaptureSession (dataclass)](#capturesession-dataclass)
- [验收标准](#验收标准)
- [非目标](#非目标)
- [依赖](#依赖)

## 背景与目标

### 背景

perfetto-tool 是一个独立的 Perfetto trace 抓取工具，支持交互模式和命令行模式。
当前需要将其迁移到 lv-game-toolkit 模块架构中，复用 toolkit 核心的 AdbManager、
ConfigManager、EventBus 等基础设施，同时保留原有的全部业务逻辑。

### 源项目分析

- **源码位置**: `_archived_source/perfetto-tool/perfetto_capturer/`
- **核心文件**: adb.py, cli.py, cli_cmd.py, config.py, device.py, perfetto.py, session.py, utils.py
- **配置契约**: config.json（JSON Schema 见 specs/001/contracts/config.schema.json）
- **测试覆盖**: 5 个单元测试文件
- **两个 spec 迭代**: 001-基础抓取, 002-CLI 命令模式

### 目标

将 perfetto-tool 的所有功能迁移到 `modules/perfetto_capture`，包括：
1. 复用 toolkit 核心 AdbManager（需先扩展 input_text + shell_raw）
2. 适配 plugin 架构（hookimpl 注册）
3. 提供 Typer CLI 子命令
4. 提供 PyQt6 GUI 页面
5. 通过 EventBus 发布 trace 就绪事件

## 关联规格

| 文档 | 内容 |
|------|------|
| [specs/002-auto-buffer/spec.md](../002-auto-buffer/spec.md) | 按抓取时长自动计算 ring buffer、安全系数与手动覆盖；与双模引擎共用 TraceConfig |
| [specs/003-ui-enhancement/spec.md](../003-ui-enhancement/spec.md) | 单栏布局、FlowWidget、底栏固定、断线 UI、导入打开 `data/`、停止后打开导出目录、陈旧会话清理的配合说明 |

## 用户故事

### P1 — 核心抓取

作为性能测试人员，我希望通过 GUI 或 CLI 启动 Perfetto trace 持续抓取，按需保存多段 trace，
最终导出到本机，以便后续分析卡顿问题。

### P2 — 配置管理

作为用户，我希望自定义抓取配置（atrace categories、buffer 大小、时长、目标包名等），
并能保存/加载不同的配置预设。

### P3 — 断线恢复

作为用户，当 USB 断开时，工具不应直接退出，而是等待重连后继续。

### P4 — CLI 自动化

作为 AI Agent 或自动化脚本，我希望通过 CLI 命令进行非交互式的 trace 抓取（start → save → quit）。

## 功能需求

### FR-001 配置管理

- 配置文件存放在模块 `assets/config.json`（默认模板）
- 用户自定义配置存放在模块 `data/config.json`
- 配置项包含: atrace_categories, duration_sec, buffer_size_kb, buffer_manual_override, buffer_safety_factor（默认 **1.2**，与 [002-auto-buffer](../002-auto-buffer/spec.md) 一致）, device_trace_dir, output_dir,
  target (mode/packages), advanced (ftrace_events, sampling, raw_perfetto_config), export, logging
- 使用 Pydantic 模型进行验证（替代原手写 validate_config）
- 配置加载优先级: 用户自定义 > 默认模板
- **Trace 本机输出根目录（环境感知）**：开发模式下为 `modules/perfetto_capture/data/output/trace/`（其中 `output` 来自配置项 `output_dir`，默认值为 `"output"`）；PyInstaller 打包且 `sys.frozen` 为真时，为 **`<exe 所在目录>/output/trace/`**。会话级导出子目录命名规则不变（见 FR-003）。

### FR-002 Perfetto 抓取引擎

- 生成 pbtxt TraceConfig（RING_BUFFER + linux.ftrace + process_stats + packages_list）
- 通过 AdbManager 与设备上 `perfetto` 交互；具体启动方式由 **双模引擎** 决定（见下）
- 支持启动/停止抓取（`start_tracing` / `stop_tracing`）
- 支持 Perfetto 能力探测（`probe_perfetto_capabilities()`：解析 `perfetto --help` 是否包含 `--detach` 与 `--clone`）
- 设备端 trace 目录自动创建与回退

**双模抓取引擎（Snapshot / Autobuffer）**：

| 模式 | 枚举 `CaptureMode` | 适用条件 | 启动要点 | 停止 `stop_tracing` | 中途保存 `session_save_trace` |
|------|---------------------|----------|----------|----------------------|------------------------------|
| **Snapshot** | `SNAPSHOT` | 设备同时支持 detach 与 clone | `perfetto --detach` + `perfetto --clone-by-name`；`RunningTrace` 记录 `detach_key` / `session_name` 等 | `perfetto --attach --stop` | `clone-by-name`（尽量不中断持续抓取） |
| **Autobuffer** | `AUTOBUFFER` | 不支持上述能力时回退 | `perfetto --background`（`start_tracing_legacy()`）；`RunningTrace` 记录 `pid` | `kill` 设备端 perfetto PID | stop → 落盘/导出段 → 再启动（连续抓取） |

- `PerfettoCapabilities` 提供 `supports_detach`、`supports_clone`、`supports_snapshot_mode`（两者兼具才为 true）
- 每次**开始新 trace 前**调用 `cleanup_stale_sessions()`（如 `pkill -f perfetto`），减轻「Too many concurrent tracing sessions」错误

### FR-003 会话管理

- 一轮会话 = 启动 → 多次保存 → 导出退出
- 保存行为依 `CaptureMode` 分流（clone 路径 vs stop→record→restart）
- trace 文件名: `{MODEL}_{SOC}_{YYYYMMDD}_{HHMMSS}.perfetto-trace`
- 会话导出目录：位于 **Trace 本机输出根目录**（见 FR-001 环境感知说明）下的 `{yyyy_MM_dd-HH_mm_ss}/` 子目录
- 断线时产生的故障段文件添加 `FAULT_` 前缀

### FR-004 设备断线重连

- **检测**：抓取进行中若 `on_devices_changed([])` 收到空列表，或 ADB 路径抛出 `DeviceUnavailableError`，进入等待重连态
- **状态**：展示「🟡 等待重连」；**禁用**保存与停止；提供「❌ 放弃会话」（`session_abandon()`，无导出清理会话）
- **重连**：依赖全局 `DeviceMonitor` 自动检测（约 2s 轮询）；恢复后 worker 以 **reconnect** 动作在设备上重新启动 perfetto
- **放弃后无设备**：界面显示「🔴 设备断开」，**不得**显示「🟢 就绪」
- 尝试导出断线前的故障段 trace（与既有策略一致）

### FR-005 CLI 命令

基于 Typer 注册到 `perfetto` 命名空间：

| 命令 | 说明 |
|------|------|
| `perfetto info` | 显示模块信息与当前配置 |
| `perfetto start` | 命令行模式启动抓取（-t/-b/-o 覆盖配置） |
| `perfetto config show` | 显示当前配置 |
| `perfetto config reset` | 重置为默认配置 |

### FR-006 GUI 页面

- Tab 标签: "Perfetto 抓取"，带图标
- 配置区（可滚动）：核心参数、Categories、Ftrace（详见 [003-ui-enhancement](../003-ui-enhancement/spec.md)）
- **Buffer**：SpinBox 取值范围 **91136～512000 KB**（约 89 MB～500 MB）；未勾选「手动设置 Buffer」时为 **只读**（`setReadOnly(True)`），与自动计算值联动；勾选手动后可编辑
- **Ftrace Events**：勾选变化会触发 **buffer 自动重算**（与 atrace categories、duration 一致）；与 [002-auto-buffer](../002-auto-buffer/spec.md) 中 tag 计数规则一致
- 底部固定区：状态、开始/保存/停止/放弃、日志 — 不在滚动区域内
- 后台抓取线程使用 QThread + pyqtSignal；进入/退出抓取态（`_set_capturing`）时需正确处理手动 Buffer 开关与 SpinBox 只读态

### FR-007 事件通知

- 抓取完成并导出后，通过 EventBus 发布 `perfetto_capture.trace_ready` 事件
- 事件数据包含: trace 文件路径列表、设备信息、会话 ID

## 数据模型

### CaptureConfig (Pydantic)

```python
class CaptureConfig(BaseModel):
    atrace_categories: list[str]
    duration_sec: int = Field(ge=1)
    buffer_size_kb: int = Field(ge=1)
    device_trace_dir: str = "/data/misc/perfetto-traces"
    output_dir: str = "output"
    target: TargetConfig
    advanced: AdvancedConfig
    export: ExportConfig
```

### CaptureMode (enum)

- `SNAPSHOT`：detach + clone 路径
- `AUTOBUFFER`：`--background` 路径

### RunningTrace (dataclass)

- `mode: CaptureMode`
- 可选 `detach_key`、`session_name`（Snapshot）
- 可选 `pid`（Autobuffer）

### TraceItem (dataclass)

```python
@dataclass
class TraceItem:
    kind: TraceKind  # NORMAL | FAULT
    device_path: str
    export_filename: str
    export_path: Path | None = None
    exported: bool = False
```

### CaptureSession (dataclass)

```python
@dataclass
class CaptureSession:
    session_id: str
    device_serial: str
    export_session_dir: Path
    saved_traces: list[TraceItem]
    conn_state: DeviceConnectionState
```

## 验收标准

| ID | 标准 | 类型 |
|----|------|------|
| SC-001 | 配置文件加载/验证/保存功能正常 | 功能 |
| SC-002 | pbtxt 生成内容与原实现一致（RING_BUFFER、不含 duration_ms） | 功能 |
| SC-003 | 连接设备后可通过 GUI 或 CLI 启动抓取 | 功能 |
| SC-004 | 回车保存一段 trace 后继续抓取 | 功能 |
| SC-005 | exit 结束会话并导出所有已保存 trace | 功能 |
| SC-006 | USB 断开后等待重连而非退出 | 功能 |
| SC-007 | CLI `-start -save -q` 命令模式正常工作 | 功能 |
| SC-008 | 导出后 EventBus 收到 trace_ready 事件 | 功能 |
| SC-009 | 所有迁移测试通过 | 回归 |
| SC-010 | GUI 状态面板实时更新 | 功能 |
| SC-011 | 双模引擎按能力选择 Snapshot 或 Autobuffer | 功能 |
| SC-012 | 开始抓取前清理陈旧 perfetto 会话，避免并发会话数报错 | 功能 |

> **说明（SC-002）**：仍要求 pbtxt **不含 `duration_ms`**（当前实现未新增该字段）。与自动 buffer 相关的默认值与 Trace 本机输出路径约定以 **002-auto-buffer** 及上文 **FR-001** 为准。

## 非目标

- 不做 trace 在线分析/可视化（由 perfetto_analysis 模块负责）
- 不做跨设备同步抓取
- 不修改原有的丢帧判定逻辑

## 依赖

- **前置**: specs/004-adb-perfetto-support（AdbManager input_text + shell_raw 扩展）
- **子规格**: [002-auto-buffer](../002-auto-buffer/spec.md)（自动 buffer），[003-ui-enhancement](../003-ui-enhancement/spec.md)（界面与断线交互）
- **运行时**: toolkit.core.adb_manager, toolkit.core.event_bus
- **SDK**: toolkit.sdk.base_plugin, toolkit.sdk.exceptions
