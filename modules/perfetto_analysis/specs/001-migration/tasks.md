# Task List: Perfetto 解析分析模块迁移

## 目录

- [Phase 1: 数据模型与配置](#phase-1-数据模型与配置)
- [Phase 2: 分析引擎迁移](#phase-2-分析引擎迁移)
- [Phase 3: Service 封装层](#phase-3-service-封装层)
- [Phase 4: Plugin 注册](#phase-4-plugin-注册)
- [Phase 5: CLI 迁移](#phase-5-cli-迁移)
- [Phase 6: GUI 实现](#phase-6-gui-实现)
- [Phase 7: 混合 DB 与事件联动](#phase-7-混合-db-与事件联动)
- [Phase 8: 测试与文档](#phase-8-测试与文档)
- [FR 可追溯矩阵](#fr-可追溯矩阵)

---

## Phase 1: 数据模型与配置

- [x] **T001**: 创建 `src/models.py` — 定义 `AnalysisConfig(BaseModel)` Pydantic 配置模型（FR-201）
  - 字段：output_dir, db_path, refresh_rate_preset, app_type, analyze_top, slow_binder_threshold_ms, sched_latency_threshold_ms, auto_analyze_on_capture, default_process, dimensions
  - 定义 `load_config(path)` / `save_config(cfg, path)` 函数
  - 首次加载时从 assets/config.json 复制到 data/config.json

- [x] **T002**: 创建 `assets/config.json` — 默认配置模板（FR-201）

- [x] **T003**: 创建 `data/config.json` — 运行时用户配置（FR-201）
  - 内容与 assets/config.json 一致，首次运行时自动生成

---

## Phase 2: 分析引擎迁移

- [x] **T004**: 复制 `engine/config.py` — 重写为 Pydantic 适配层（FR-005）
  - 接收 AnalysisConfig 对象，提供与源项目 config.py 兼容的接口
  - 移除 YAML 支持，仅保留 JSON

- [x] **T005**: 复制 `engine/parser.py` — Phase 1 丢帧解析（FR-001 ~ FR-003, FR-008, FR-009）
  - 从 `_archived_source/perfettoAnalysisByPython/src/perfetto_analysis/parser.py` 复制
  - 调整导入：`from . import config` 等保持不变

- [x] **T006**: 复制 `engine/storage.py` — SQLite 持久化（FR-003）
  - 从源项目复制
  - DB 路径逻辑由 Service 层控制

- [x] **T007**: 复制 `engine/analyzer.py` — Phase 2 分析编排（FR-100 ~ FR-113）
  - 从源项目复制
  - 验证所有维度模块的导入正确

- [x] **T008**: 复制 `engine/export.py` — Markdown 报告导出（FR-004, FR-007, FR-008）
  - 从源项目复制

- [x] **T009**: 复制 `engine/report_writer.py` — 报告文件写入（FR-004）
  - 从源项目复制
  - 调整输出路径：从 `report/` 改为 `output/analysis/`（C-002）

- [x] **T010**: 复制 `engine/app_type.py` — App 类型检测（FR-100）

- [x] **T011**: 复制 `engine/cpu_topology.py` — CPU 拓扑初始化（FR-101）

- [x] **T012**: 复制 `engine/frame_boundary.py` — 帧边界确定（FR-103）

- [x] **T013**: 复制 `engine/dimension_registry.py` — 维度注册表（FR-120）

- [x] **T014**: 复制 `engine/summary_analysis.py` — 全 Trace 整体分析（FR-119）

- [x] **T015**: 复制 9 个维度分析模块（FR-104 ~ FR-118）
  - `engine/thread_analysis.py` — FR-104, FR-105
  - `engine/cpu_analysis.py` — FR-106, FR-107, FR-108
  - `engine/binder_analysis.py` — FR-109, FR-110
  - `engine/io_analysis.py` — FR-111
  - `engine/gc_analysis.py` — FR-114
  - `engine/gpu_analysis.py` — FR-115
  - `engine/sf_analysis.py` — FR-116
  - `engine/input_analysis.py` — FR-117
  - `engine/lock_analysis.py` — FR-118

- [x] **T016**: 验证 engine/ 包导入完整性
  - 执行 `python -c "from modules.perfetto_analysis.src.engine import parser, analyzer, storage, export"`
  - 确认无 ImportError

---

## Phase 3: Service 封装层

- [x] **T017**: 重写 `src/service.py` — PerfettoAnalysisService（FR-202）
  - `__init__(self, data_dir, db_manager=None)`
  - `analyze(trace_path, process_name, on_progress)` — 完整分析
  - `parse_only(trace_path, process_name, on_progress)` — 仅 Phase 1
  - `analyze_dimensions(trace_path, process_name, dimensions, on_progress)` — 按维度
  - `export_report(trace_path, output_dir)` — 导出报告
  - `list_dimensions()` — 返回维度列表
  - `get_analysis_history()` — 查询历史（从共享 DB）
  - `reload_config(config_path)` — 重新加载配置
  - `get_config()` — 获取当前配置

- [x] **T018**: Service 进度回调集成
  - 在 analyze() 流程中插入 on_progress 回调点
  - 回调消息格式："Phase 1: 解析中..."、"Phase 2: 分析 {dim} 维度..."、"导出报告中..."

- [x] **T019**: Service 报告路径管理
  - 默认输出到 `output/analysis/<trace_stem>/`（C-002）
  - 支持通过配置或参数自定义输出目录

---

## Phase 4: Plugin 注册

- [x] **T020**: 完善 `src/plugin.py` — PerfettoAnalysisPlugin（FR-200）
  - `on_startup`: 注册 pa_service, pa_adb, pa_data_dir
  - `register_gui_tab`: 返回 PerfettoAnalysisTab
  - `register_cli_commands`: 注册 analysis Typer 子命令
  - `register_agent_tools`: 注册 5 个 Agent 工具（FR-207）
  - `on_shutdown`: 清理资源

- [x] **T021**: perfetto 依赖检查
  - on_startup 时检查 perfetto 包是否安装
  - 未安装时在日志中给出安装提示

---

## Phase 5: CLI 迁移

- [x] **T022**: 重写 `src/cli_commands.py` — Typer CLI（FR-203）
  - `analysis parse <traces...>` — 仅解析
  - `analysis export <traces...>` — 完整分析导出
  - `analysis analyze <traces...> --dims <dims>` — 独立维度
  - `analysis dims` — 列出维度
  - `analysis history` — 查看历史

- [x] **T023**: CLI 参数映射
  - --process, --config, --output-dir, --app-type, --analyze-top
  - --timing, --window, --jank-index, --format
  - --slow-binder-threshold, --sched-latency-threshold

- [x] **T024**: CLI JSON 输出支持
  - 所有命令支持 --json 标志输出 JSON 格式

---

## Phase 6: GUI 实现

- [x] **T025**: 重写 `src/gui_tab.py` — PerfettoAnalysisTab（FR-204）
  - 继承 BaseTab，左右分栏布局（QSplitter）
  - tab_title = "Perfetto 分析", tab_icon = "📊"

- [x] **T026**: 左侧面板 — Trace 文件选择
  - QLineEdit + QPushButton("浏览")
  - 拖拽支持（dragEnterEvent/dropEvent）
  - 支持 .perfetto-trace, .perfetto 等格式

- [x] **T027**: 左侧面板 — 分析配置区
  - 目标进程 QLineEdit（固定 240px）
  - App 类型 QComboBox（100px, auto/app/game/camera）
  - 分析模式 QComboBox（100px, 完整分析/仅解析/独立维度）+ 维度多选 _DimensionSelector（120px）
  - ~~Top N QSpinBox, Binder 阈值 QDoubleSpinBox, 调度延迟 QDoubleSpinBox~~ **已移除**（C-005: 使用 config.json 默认值）

- [x] **T028**: 左侧面板 — 分析历史列表
  - QTableWidget 6 列固定宽度（Trace 140px, 目标进程 120px, 模式 60px, 时间 80px, 状态 36px, 操作 120px）
  - 数据合并来源：共享 DB `pa_analysis_tasks` + 磁盘 `output/trace_report/` 扫描
  - 去重策略：trace_path + mode 组合唯一
  - 双击重新生成报告（从 DB 数据）

- [x] **T029**: 左侧底部 — 控制区
  - 状态指示（QLabel）
  - 开始/停止按钮（QPushButton）
  - 进度条（QProgressBar）+ 阶段文字

- [x] **T030**: ~~右侧面板 — 报告文件区~~ **已移除**
  - 打开报告/打开目录功能已集成到左侧分析历史的操作列中

- [x] **T031**: 右侧面板 — 分析结果预览
  - 丢帧概览（jank_times, frame_num, refresh_rate, app_type, 耗时）
  - 维度分析状态概要（各维度完成/跳过状态）

- [x] **T032**: 右侧底部 — 操作日志
  - QTextEdit（readonly）
  - 固定高度，与左侧控制区等高对齐
  - 底部吸附

- [x] **T033**: 后台分析线程
  - _BackgroundWorker(QThread) + finished/error/progress pyqtSignal
  - progress 信号连接到进度条和操作日志更新

- [x] **T034**: 维度多选下拉组件
  - _DimensionSelector：QPushButton + _PersistentMenu（QMenu 子类，点击不自动关闭）
  - 显示已选维度数量（"全部维度 ▾" / "N 个维度 ▾" / "未选维度 ▾"）
  - 注：最初使用 QComboBox 实现，因 Windows COM 线程崩溃改为 QPushButton 方案

---

## Phase 6.5: GUI 功能迭代与 Bug 修复

- [x] **T043**: GUI 布局调整 — 控制区移至配置与历史之间
  - 开始/停止按钮从底部吸附改为配置区下方
  - 按钮宽度固定 100px，使用 SP_MediaPlay / SP_MediaStop 系统图标

- [x] **T044**: 分析历史功能增强
  - 增加"目标进程"列（分析后自动填充检测到的进程名）
  - 增加"模式"列（完整/仅解析/独立维度，tooltip 显示维度详情）
  - 操作列：重新生成（从 DB 数据）、打开报告、打开目录、删除（智能清理）

- [x] **T045**: 进程名自动检测
  - Service 层从 trace 的 buffer_track_name 自动提取进程名（regex 匹配纯包名）
  - 分析完成后写入共享 DB 的 process_name 字段
  - GUI 分析结果和历史表中显示检测到的进程名

- [x] **T046**: 报告输出目录调整
  - 开发环境：`data/output/trace_report/<trace_stem>/`
  - 打包后：`<exe_dir>/output/trace_report/<trace_stem>/`
  - 通过 `sys.frozen` 判断运行环境

- [x] **T047**: "重新生成报告"实现（C-006）
  - `service.regenerate_report()` 从模块 DB 读取已有数据（trace_run, trace_summary, jank_record）
  - 使用 export 模块重新生成 Markdown 报告
  - 不重新分析 trace 文件

- [x] **T048**: 删除记录智能清理（C-007）
  - `service.delete_analysis_record()` 仅删除指定 task_id 记录
  - 检查同一 trace_path 是否还有其他模式记录
  - 无其他记录时同时清理模块 DB（trace_run, jank_record 等）和磁盘文件
  - GUI 使用 QTimer.singleShot(100ms) 延迟刷新避免 UI 竞态

- [x] **T049**: 移除 Top N / Binder 阈值 / 调度延迟 GUI 配置项（C-005）
  - 从 GUI 移除 QSpinBox / QDoubleSpinBox
  - 保留 config.json 中的默认值供后端使用

- [x] **T050**: 左侧面板固定宽度
  - 设置 `panel.setFixedWidth(580px)`，不随窗口缩放
  - QSplitter stretchFactor(0)=0, stretchFactor(1)=1

- [x] **T051**: CPU 频率分析多级降级查询
  - `cpu_analysis.py` 和 `summary_analysis.py` 使用 3 级 fallback 查询策略
  - 解决部分 trace 缺少标准 CPU 频率数据的问题

- [x] **T052**: 丢帧时间戳修复
  - 修复 jank_3 类型事件中 app 侧时间戳异常（出现在 trace 开始前）
  - `ajt1` 为 0 时使用 `pre_vt` 替代

- [x] **T053**: 线程安全 DB 写入
  - `_write_task_to_shared_db` 使用独立 `sqlite3.connect()` 连接
  - 解决工作线程访问主线程 DB 连接导致的 ProgrammingError

- [x] **T054**: Windows COM 线程崩溃修复
  - 维度选择器从 QComboBox 改为 QPushButton + _PersistentMenu
  - 避免自定义 QComboBox.hidePopup 破坏 Qt 内部事件处理

---

## Phase 7: 混合 DB 与事件联动

- [x] **T035**: 创建 `src/migrations/001_create_tables.sql`（FR-205）
  - pa_analysis_tasks 表（task_id, trace_path, device_serial, analysis_db_path, report_dir_path, status, created_at, completed_at, error_message）

- [x] **T035a**: 创建 `src/migrations/002_add_process_name.sql`
  - ALTER TABLE pa_analysis_tasks ADD COLUMN process_name TEXT DEFAULT ''

- [x] **T035b**: 创建 `src/migrations/003_add_mode_dimensions.sql`
  - ALTER TABLE pa_analysis_tasks ADD COLUMN mode TEXT DEFAULT 'full'
  - ALTER TABLE pa_analysis_tasks ADD COLUMN dimensions TEXT DEFAULT ''

- [x] **T036**: Service 写入共享 DB 索引
  - 分析开始时 INSERT status='running'
  - 分析完成时 UPDATE status='completed', completed_at
  - 分析失败时 UPDATE status='failed', error_message

- [x] **T037**: Plugin 事件联动逻辑（FR-206）
  - 监听 perfetto_capture.trace_ready 事件
  - 检查 auto_analyze_on_capture 配置
  - 启用时自动调用 service.analyze()

---

## Phase 8: 测试与文档

- [x] **T038**: 创建 `tests/conftest.py` — 测试固件
  - mock TraceProcessor
  - mock DB 连接
  - 临时目录 fixture

- [x] **T039**: 创建 `tests/test_service.py` — Service 层测试（合并到 test_perfetto_analysis.py）
  - test_analyze, test_parse_only, test_analyze_dimensions
  - test_list_dimensions, test_get_config, test_reload_config

- [ ] **T040**: 创建 `tests/test_parser.py` — 解析引擎测试（待有 fixture trace 数据后实现）
  - test_parse_trace（mock TraceProcessor）
  - test_jank_detection_logic

- [x] **T041**: 更新 `scripts/run_all_tests.py` — 注册新模块测试

- [ ] **T042**: 安装 perfetto 依赖（待集成测试阶段安装）
  - `.venv\Scripts\pip.exe install perfetto>=0.16.0 -i https://pypi.tuna.tsinghua.edu.cn/simple`

---

## FR 可追溯矩阵

| FR | Task(s) | 说明 |
|----|---------|------|
| FR-001 ~ FR-003 | T005, T006 | Phase 1 解析 + 持久化 |
| FR-004 | T008, T009, T047 | 报告导出 + 重新生成报告 |
| FR-005 | T001, T002, T003, T004, T049 | 配置模型（GUI 中移除部分配置项） |
| FR-006 | T004 ~ T015, T051 | 模块化引擎 + CPU 频率降级查询 |
| FR-007 | T005, T008 | UTF-8 编码 |
| FR-008 | T005, T008, T052 | 北京时间转换 + 丢帧时间戳修复 |
| FR-009 | T005, T045 | 进程匹配 + 自动检测进程名 |
| FR-100 ~ FR-120 | T007, T010 ~ T015 | Phase 2 分析 |
| FR-200 | T020, T021 | Plugin 注册 |
| FR-201 | T001, T002, T003 | Pydantic 配置 |
| FR-202 | T017, T018, T019, T047, T048 | Service 层 + 重新生成 + 删除记录 |
| FR-203 | T022, T023, T024 | CLI |
| FR-204 | T025 ~ T034, T043 ~ T050, T054 | GUI（含迭代与 Bug 修复） |
| FR-205 | T035, T035a, T035b, T036, T053 | 混合 DB + 迁移脚本 + 线程安全 |
| FR-206 | T037 | 事件联动 |
| FR-207 | T020 | Agent 工具 |
