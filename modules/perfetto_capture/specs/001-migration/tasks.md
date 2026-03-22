# Perfetto 抓取模块迁移 — 任务清单

## 目录

- [Phase 0 ADB 核心扩展](#phase-0-adb-核心扩展)
- [Phase 1 数据模型与配置](#phase-1-数据模型与配置)
- [Phase 2 抓取引擎](#phase-2-抓取引擎)
- [Phase 3 CLI 命令](#phase-3-cli-命令)
- [Phase 4 GUI 页面](#phase-4-gui-页面)
- [Phase 5 插件集成](#phase-5-插件集成)
- [Phase 6 测试与验证](#phase-6-测试与验证)

## Phase 0: ADB 核心扩展

| ID | 任务 | 依赖 | 状态 |
|----|------|------|------|
| T001 | `_run_cmd_raw()` 新增 `input_text: str \| None = None` 参数 | — | ☐ |
| T002 | 新增 `shell_raw(serial, command, *, input_text, timeout) -> AdbCmdResult` | T001 | ☐ |
| T003 | 补充 ADB 扩展单元测试 | T002 | ☐ |

## Phase 1: 数据模型与配置

| ID | 任务 | 依赖 | 状态 |
|----|------|------|------|
| T004 | 创建 `models.py` — CaptureConfig, TargetConfig, AdvancedConfig, ExportConfig (Pydantic) | — | ☐ |
| T005 | 创建 `models.py` — TraceItem, TraceKind, CaptureSession, RunningTrace (dataclass) | — | ☐ |
| T006 | 创建 `models.py` — DeviceConnectionState, PerfettoCapabilities (dataclass) | — | ☐ |
| T007 | 创建 `config_manager.py` — 配置加载/保存/验证/默认值 | T004 | ☐ |
| T008 | 创建 `assets/config.json` 默认配置模板 | T004 | ☐ |
| T009 | 创建 `utils.py` — 文件命名、路径处理工具函数 | — | ☐ |

## Phase 2: 抓取引擎

| ID | 任务 | 依赖 | 状态 |
|----|------|------|------|
| T010 | `service.py` — `build_pbtxt_config()` pbtxt 生成 | T004 | ☐ |
| T011 | `service.py` — `start_tracing()` 适配 AdbManager.shell_raw | T002, T005 | ☐ |
| T012 | `service.py` — `stop_tracing()` 适配 AdbManager.shell_raw | T002, T005 | ☐ |
| T013 | `service.py` — `ensure_device_trace_dir()` | T002 | ☐ |
| T014 | `service.py` — `probe_perfetto_capabilities()` | T002, T006 | ☐ |
| T015 | `service.py` — `save_trace()` 会话保存逻辑 | T005, T009, T011, T012 | ☐ |
| T016 | `service.py` — `export_session()` 导出逻辑 | T005, T009 | ☐ |
| T017 | `service.py` — 断线检测辅助 `is_device_unavailable()` | T002 | ☐ |
| T018 | `service.py` — `get_device_timestamp()` 设备时间获取 | T002 | ☐ |

## Phase 3: CLI 命令

| ID | 任务 | 依赖 | 状态 |
|----|------|------|------|
| T019 | `cli_commands.py` — `perfetto info` | T010 | ☐ |
| T020 | `cli_commands.py` — `perfetto start` (含 -t/-b/-o 参数) | T011, T015, T016 | ☐ |
| T021 | `cli_commands.py` — `perfetto config show/reset` | T007 | ☐ |

## Phase 4: GUI 页面

| ID | 任务 | 依赖 | 状态 |
|----|------|------|------|
| T022 | `gui_tab.py` — 布局框架（左右分栏 QSplitter） | — | ☐ |
| T023 | `gui_tab.py` — 配置面板（Duration/Buffer/Mode/Categories） | T007 | ☐ |
| T024 | `gui_tab.py` — 会话状态面板 | T005 | ☐ |
| T025 | `gui_tab.py` — 控制按钮（开始/保存/停止） | — | ☐ |
| T026 | `gui_tab.py` — 日志面板（QTextEdit 只读 + 自动滚动） | — | ☐ |
| T027 | `gui_tab.py` — CaptureWorker(QThread) 后台抓取 | T011, T012, T015, T016 | ☐ |
| T028 | `gui_tab.py` — 按钮状态联动（idle/capturing/exporting） | T025, T027 | ☐ |
| T029 | `gui_tab.py` — 断线状态显示与自动恢复 | T017, T027 | ☐ |

## Phase 5: 插件集成

| ID | 任务 | 依赖 | 状态 |
|----|------|------|------|
| T030 | `plugin.py` — on_startup: 注册 pe_service, pe_adb | T010 | ☐ |
| T031 | `plugin.py` — register_gui_tab: 传递 context | T022 | ☐ |
| T032 | `plugin.py` — register_cli_commands: 传递 context | T019 | ☐ |
| T033 | `plugin.py` — EventBus trace_ready 事件发布 | T016 | ☐ |
| T034 | `manifest.json` — 更新 dependencies, events, external_tools | — | ☐ |

## Phase 6: 测试与验证

| ID | 任务 | 依赖 | 状态 |
|----|------|------|------|
| T035 | 迁移 test_cli_args → 适配 Typer | T019, T020 | ☐ |
| T036 | 迁移 test_perfetto_config → 测试 build_pbtxt_config | T010 | ☐ |
| T037 | 迁移 test_export_session_dir → 测试导出目录命名 | T009 | ☐ |
| T038 | 迁移 test_fault_segment → 测试 FAULT_ 前缀 | T009 | ☐ |
| T039 | 迁移 test_reconnect → 测试断线状态转换 | T005, T017 | ☐ |
| T040 | 新增 CaptureConfig Pydantic 模型测试 | T004 | ☐ |
| T041 | 新增 service 层核心功能测试 | T010-T018 | ☐ |
| T042 | spec analysis 一致性检查 | T001-T041 | ☐ |
