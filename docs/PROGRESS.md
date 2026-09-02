# LV Game Toolkit — 项目进度

## 目录

- [当前阶段](#当前阶段)
- [活跃工作](#活跃工作)
- [近期完成](#近期完成)
- [业务汇报](#业务汇报)

## 当前阶段

Android 性能分析工具集，插件化架构 7 模块就绪，核心功能可用。当前聚焦 Perfetto 分析的 LLM 集成优化和 FPS 采集鲁棒性。

**活跃模块**：agent、perfetto_analysis、perfetto_capture

## 活跃工作

### R6: Agent 核心重构（toolkit/agent）✅

- 目标：`modules/agent_chat/` → `toolkit/agent/`，Tool/Skill/MCP 基础设施下沉到 `toolkit/core/`
- 设计方案已落盘：[DES-001](design/DES-001-agent-core-refactor.md)，参考 Hermes Agent 开源架构
- 4 项设计决策已确认：SOP 合并到 Skill、SubAgent 暂不实现、Toolset 预留不分、Agent 不做独立窗口
- Speckit 流程全部完成，Phase 1-6 实现完毕（80/80 tasks）
- 217/217 测试通过，SC-004 (零反向依赖) + SC-006 (测试通过率) 达成 ✅

### R7: Hermes Agent 深度引入 — Agent 框架升级（toolkit/agent）

- 目标：在 DES-001 基础上，深度引入 Hermes 的对话循环鲁棒性 + 质量保障 + 知识库 + 记忆管理能力
- 设计方案已落盘：[DES-002](design/DES-002-hermes-agent-upgrade.md)（2026-06-02，draft）
- 核心差距分析完成：lv-game-toolkit 已有 6 项 Hermes 模式，缺失/薄弱 12 项
- 四阶段路线：Phase 1 韧性基础（ErrorClassifier/CircuitBreaker/Watchdog）→ Phase 2 质量保障（Verification/ContextCompressor）→ Phase 3 知识库（KnowledgeBase/Memory）→ Phase 4 SubAgent
- 2026-06-02: agent-wiring-fix 49/50 完成后，对照 DES-002 全量差距分析 — **确认 20 项新交付物全部待开始**，详见 DES-002 文档
- 待进入 Speckit 流程（建议先创建 `hermes-phase1-resilience` change）

### R8: UI 设计规范与 VSCode 差距补齐（DES-003）

- 目标：解决 GUI 美观度/商用感与 VSCode 的系统性差距
- 设计方案已落盘：[DES-003](design/DES-003-ui-design-standards.md)（2026-08-12，draft）
- 产出：Design Token 体系（颜色/间距/字号/圆角/阴影）+ 组件六态规范 + 模块 GUI 审计差距清单（P0-P3）+ 三期实施路线
- 审计要点：5 个 GUI 模块存在 objectName 命名不一致（`primaryButton`）、4 组件内联样式/硬编码颜色、`sectionCard` class 死代码
- 待用户审阅后进入 Phase 1（token 落地 + 规范违规清零）

### R1: LLM 上下文优化（perfetto_analysis）

- ToolReturn 压缩机制已实现（≤300 token 摘要 + metadata 保留原始数据）
- 冗余工具已移除（11→9），SOP 场景映射补全（10 个场景）
- 待完成：graceful degradation（上下文溢出时部分完成报告）

### R5: FPS 采集鲁棒性（perfetto_capture）

- 待实现：SF latency 数据校验、Android 16 layer name regex、诊断日志

## 近期完成

### 2026-09-02（修复 TitleBar 启动崩溃）

- **现象**：`python -m toolkit.app` 启动崩溃 `AttributeError: 'TitleBar' object has no attribute 'output_dir_requested'`（main_window.py:113）
- **根因**：`toolkit/gui/widgets/title_bar.py` 重构 log-panel-header 时，`TitleBar` 作为桥接层遗漏了 `output_dir_requested` 信号的声明与转发——`SettingsButton` 已定义并 emit 该信号，但 `TitleBar` 只转发了 `theme/llm/agent/log_*` 6 个信号，唯独漏了 `output_dir_requested`，导致 `MainWindow.__init__` 访问 `self._title_bar.output_dir_requested` 时崩溃
- **修复**：`TitleBar` 补齐 `output_dir_requested = pyqtSignal()` 信号声明 + `self._settings_btn.output_dir_requested.connect(self.output_dir_requested.emit)` 桥接，顺序对齐 `SettingsButton`
- **验证**：无头完整启动链（`_build_context → _load_plugins → MainWindow`）通过，`output_dir_requested` 已连接 1 个 receiver；`tests/ -k title_bar/main_window` 1 passed 无回归

### 2026-09-01（项目重命名 + game_perf 模块排除公开发布）

- **背景**：项目将公开发布到 GitHub，需重命名仓库/项目为 `game-perf-toolkit`，且内部模块 `game_perf`（游戏性能配置，含两个子 tab）源码、发布产物、本地 db 数据均不上传公开仓库
- **重命名**：pyproject.toml name、build.py APP_NAME、Velopack packId(`GamePerfToolkit`)、app_paths APP_NAME(`Game Perf Toolkit`)、app.py ApplicationName、README/CLAUDE 标题
- **排除 game_perf**：.gitignore 加 `modules/game_perf/` + `git rm -r --cached -f`（33 文件移出索引，本地保留）；build.py `_collect_modules`/`_hidden_imports`/config 复制三处跳过 game_perf；data 目录本就由 skip_dirs 排除打包
- **验证**：git 追踪 0、.gitignore 生效、build.py 语法 OK、无头启动 OK、tests/ 234 passed、game_perf 本地 86 passed（本地仍可用）

### 2026-09-01（installer-distribution-refactor: 安装包分发 + 增量更新 + 数据隔离架构）

- **背景**：原便携绿色包(zip)分发，用户数据堆 exe 同级 `data/`，覆盖升级易丢数据、无更新机制
- **方案**（基于 explore 调研六条决策）：① 数据路径三层分层(platformdirs: config roaming / data local / output Documents)；② 安装包+更新一体化(Velopack, Squirrel 继任者, delta 差分)；③ 老便携数据迁移助手(半自动)；④ app_paths.py 三层重写 + 清理 ~15 处 `get_exe_dir()/"data"` 直拼旁路点
- **关键约束**：MCP server 模式无 QCoreApplication，QStandardPaths 无 appname 隔离，故选 platformdirs（实测确认）
- **实现**：`toolkit/core/app_paths.py` 三层根 + 封装函数内部改走分层；`toolkit/app.py` 植入 `velopack.App().run()` 钩子 + 后台 UpdateManager 检查；`toolkit/core/portable_migration.py` 迁移逻辑 + `toolkit/gui/portable_migration_dialog.py` UI；`scripts/build.py` 对接 vpk pack 产 Setup.exe
- **测试**：test_app_paths 29 passed（三层路径 + dev 覆盖 + headless 一致性）、test_portable_migration 20 passed；tests/ 全量 234 passed；新文件 ruff 清零
- **验证**：无头 `_build_context` 启动通过；build.py `--help` 验证新参数
- **文档**：[ARCH-003](architecture/distribution-paths-architecture.md) 分发与路径架构；CLAUDE.md 构建章节更新
- **决策遗留**：ConfigManager 接入 FileConfigService 的 config_changed 信号为 config-sync 专项，本 change 以"get_output_dir 每次读 config 即时生效"满足功能需求

### 2026-09-01（perfetto_capture: 修复属主冲突导致启动失败）

- **背景**：Perfetto 抓取报 `Failed to open /data/misc/perfetto-traces/current_1.perfetto-trace ... errno: 13, Permission denied`，提示 "file might have been created by another user, try deleting it first"
- **根因**：`/data/misc/perfetto-traces/` 下残留同名 trace 文件属主非当前 shell 用户（常见于 userdebug/rooted 设备混用 `adb root` 与普通 shell），perfetto 以写模式 open 已有文件被拒；代码每次会话 `trace_idx` 从 1 递增生成 `current_{idx}`，跨会话重名易命中残留；`cleanup_stale_sessions` 只清进程不清文件
- **实现**：新增 `PerfettoCaptureService._purge_device_path`，在 `session_start_capture`/`session_save_trace` 启动 perfetto 前 `rm -f` 目标文件，让 perfetto 以当前用户全新创建；删除失败仅告警不中断
- **测试**：新增 3 用例（rm 命令构造、删除失败不抛异常、启动前清理集成），test_perfetto_capture 31 passed
- **验证**：语法/导入通过；插件加载链路 + 核心框架 `_build_context` 8 服务无头构建通过
- **文件**：`modules/perfetto_capture/src/service.py`、`tests/test_perfetto_capture.py`

### 2026-08-12（UI 设计规范 DES-003 落盘）

- **背景**：用户提出 GUI 美观度/商用感与 VSCode 差距大，单进程架构能否借鉴 VSCode 多进程设计
- **分析结论**：VSCode 是 Electron+TS，代码无法移植；当前 PyQt6 已实现"类 VSCode 布局"；差距在细节层（token 缺失/规范违规/交互缺失）
- **产出**：[DES-003](design/DES-003-ui-design-standards.md) UI 设计规范文档（draft）
  - Design Token 体系：颜色（补充 focus_border/badge/shadow 等 9 类）/ 间距（8px 基准）/ 字号 / 圆角 / 阴影
  - 组件六态规范：normal/hover/pressed/focus/disabled/active + 窗口失活两级
  - 差距清单：P0（`primaryButton` 命名错）、P1（4 组件内联样式/硬编码颜色）、P2（focus 环/徽标/布局记忆/命令面板）、P3（虚拟滚动）
  - 实施路线：Phase 1 token 落地+违规清零（低风险）→ Phase 2 交互补强 → Phase 3 动效/性能（可选）
- **架构借鉴结论**：单进程下借鉴 VSCode 多进程的核心是"UI 不阻塞"，落地为渐进式启动 + QThread 纪律；进程化改造收益有限
- **验证**：模块 GUI 审计（Explore agent）完成，md-doc 目录校验通过（37/37 一致）

### 2026-08-08（导出失败后设备重连自动接续导出）

- **背景**：修复"轮询误删抓取会话目录导致导出失败"后，进一步解决导出失败（设备断开 / 进程退出）后的 trace 接续导出
- **方案**（与用户讨论确认）：待导出清单持久化 + 设备重连半自动确认接续；关键决策：serial 强隔离防跨设备串扰、JSON 载体、确认框提示时效性
- **实现**：
  - 新增 `pending_export_store.py`：`PendingExportItem` + `PendingExportStore`（JSON 原子写 tmp+rename、线程锁、按 serial 过滤/出队/清理）
  - `service.py`：`session_save_trace` 入队 / `session_stop_and_export` 出队 / `session_abandon` 清理当前会话清单项 / 新增 `resume_pending_exports(serial)` 接续导出（本地已存在→视为已导出、设备端文件缺失→跳过出队、pull 失败→保留重试、设备不可用→抛错）
  - `gui_tab.py`：设备连接时检测 pending → 半自动确认框（serial/型号/数量 + "可能被新抓取覆盖"提示）→ `_CaptureWorker("resume_export")` QThread 接续 → 结果日志 + 打开导出目录
- **测试**：`test_pending_export_store.py` 12 用例 + `test_pending_export_resume.py` 9 用例（含跨设备隔离、失败保留、设备不可用抛错、入队/出队）
- **验证**：perfetto_capture 184 passed（此前 161）；全量测试 8 组通过 0 组失败；启动链 7 插件加载通过

### 2026-08-07（分析历史文件夹热更新 + game_perf 新增游戏 + BindCore 二进制显示）

- **BindCore 二进制显示**（game_perf）：BindCore 策略块的绑核 value 为十六进制 CPU mask（如 `3c`），新增「二进制」列同步显示 mask 的二进制形式（`3c → 00111100`），便于判断绑了哪些核；位宽按 4 的倍数向上取整、至少 8 位，编辑后随策略区刷新自动更新。转换逻辑放 `GamePerfParser.format_bindmask_binary()`（纯函数，新增 7 个测试）
- **分析历史实时热更新**（perfetto_capture）：
  - 问题：抓取/分析历史不随 `trace_report/`、`trace/` 目录的实际增删而刷新，只有下次保存（分析完成）或切 Tab 时才更新列表
  - 方案：Tab 前台时启动 2s `QTimer` 轮询，复用 `_history_dir_signature()`（目录 mtime）签名比较，仅签名变化时才做完整扫描刷新；`on_deactivated()` 停止轮询避免无谓 stat 开销
  - 代价：约 20 行，无新依赖；stat 目录 mtime 微秒级，不阻塞主线程
- **game_perf 支持新增游戏**：
  - 问题：性能配置模块只能修改现有游戏参数，无法新增游戏
  - 方案：筛选区「游戏」下拉框旁新增「新增」按钮 → 弹窗输入包名+可选别名 → `GamePerfParser.add_game()` 在 XML 创建默认 `Game / Normal Mode / Policy / TempLevel` 结构 → 刷新下拉框并选中新游戏
  - 别名持久化：写入 `<Game alias="…">` 属性（gameperfconfig.xml 无 DTD，标准解析器忽略未知属性；推送验证仅做格式检查），避免实例属性在重新加载后丢失
  - 测试：新增 6 个 `TestAddGame` 用例（节点创建 / 默认别名 / 重复拒绝 / 非法包名 / 持久化 / 不破坏既有游戏）
- **热更新回归修复：轮询误删抓取会话目录导致导出失败**（perfetto_capture）：
  - 现象：导出 trace 时 `adb: error: cannot create file/directory ... No such file or directory`，目标会话目录不存在
  - 根因：当日新加的 2s 轮询热更新使 `scan_sessions()` 频繁扫描，`_cleanup_empty_dir()` 把「首次 save 创建、trace 尚未 pull 进来」的空会话目录当垃圾删除，export 阶段 pull 目标目录已不存在
  - 修复：① `_cleanup_empty_dir` 扫描路径加 600s 宽限期（新空目录不删；`delete_trace` 主动清理路径不受影响）；② `session_stop_and_export` 在 pull 前防御性 `ensure_dir` 重建
  - 测试：新增 `test_scan_keeps_recent_empty_directory`（新空目录保留）、`TestExportDirRecreation`（目录被删后导出自动重建落盘）；`test_cleanup_empty_directory` 改为模拟旧 mtime
- **验证**：全量测试 8 组通过 0 组失败；启动链加载 7 插件通过；GUI 无头实例化 + 集成流程验证通过

### 2026-08-06（Jank 监测前台应用热切换修复 + pytest GUI 测试 QApplication GC 崩溃根因修复）

- **问题**：停止监测后不重连设备，切换前台游戏（和平精英 → 王者荣耀）再重新启动监测，应用列表标星仍为旧游戏，且帧率曲线不再向后统计
- **根因**（两个现象同一根因）：`_start_jank_monitor()` 启动时直接使用 `AppSelector` combo 的**上次选中项**，从不重新刷新应用列表
  - ① 列表标星不变：应用列表只在「勾选 Jank 检测」时刷新一次，重新启动时王者不会标 ★ 也不会被选中
  - ② 曲线不统计：target 仍是已退到后台的和平精英，`JankMonitorWorker._check_foreground_state()` 首轮检测到非前台 → `_on_app_background()` → `_paused=True`，帧率采集暂停，曲线不再更新
- **修复**：
  - `jank_panel.py`：`AppSelector.set_apps()` 新增 `select_foreground` 参数，为 True 时刷新后自动选中当前前台应用
  - `gui_tab.py`：`_refresh_jank_apps()` 新增 `auto_select_foreground` / `refresh_threshold` 参数透传；`_on_jank_toggled()` 勾选时与 `_start_jank_monitor()` 启动前均调用刷新并自动选中前台应用（`refresh_threshold=False` 避免覆盖用户手动设置的阈值）
- **pytest GUI 测试 QApplication GC 崩溃根因**（顺带定位并修复，导致多个 GUI 测试套件卡住）：
  - **根因**：测试把 `QApplication` 作为局部变量创建后丢弃返回值（`_ensure_app()`），引用计数归零被 Python GC，后续创建 QWidget 时 Qt 报 `QWidget: Must construct a QApplication before a QWidget` → `qFatal` → `abort()` → 进程 exit 127、未刷新缓冲丢失看起来像 hang
  - **修复**：4 个测试文件统一改为 `@pytest.fixture(scope="session")` 的 `qapp` fixture 保持 QApplication 存活；`test_agent_context_injection.py` / `test_history_agent_context.py` 中引用已随 Agent 重构移除的旧接口（`compose_message_with_context`、旧 AgentTab 私有属性）的死测试迁移到 `toolkit/agent/gui/agent_panel.py` 新接口或标记 skip 注明
- **验证**：perfetto_capture 全量 161 passed, 3 skipped（此前卡 23% 无法出汇总）；agent_chat 全量 196 passed, 1 skipped；toolkit/gui/widgets 11 passed；启动链 7 模块加载通过
- **主项目 tests/ 既有问题已修复（同日）**：
  - `test_mcp_server.py`：import `toolkit.core.mcp_server` 不存在（MCP Server 重构后迁移到 `toolkit/core/mcp/server.py`）→ 更新 import 路径，13 passed
  - `test_skill_registry.py`：`SkillMetadata.triggers` 断言与解析逻辑不匹配（triggers 为 `list[str]`，dict 结构取键名）→ 更新断言匹配实现，8 passed
  - `test_scaffold.py`：`create_module()` 内 `uvx --from git+...spec-kit specify init` 联网下载导致每个测试超时 120s → `modules_tmp` fixture monkeypatch `_init_speckit`，19 passed in 0.7s
- **run_all_tests 暴露的模块级测试遗留已修复（同日）**：
  - `perfetto_analysis`：11 个测试文件 import 已随 Agent 重构移除的模块（`src.agent`、`src.result_compressor`、`src.mcp_client` 等），10 个收集失败 + g3 运行时失败 → 新增 `tests/conftest.py` 用 `collect_ignore` 保留备查不收集；补 `test_service.py` 冒烟测试（4 passed）
  - `perfdog_insights`：tests/ 空目录（0 tests → pytest returncode 5 误判失败）→ 补 `test_service.py` 冒烟测试（2 passed）
  - `scripts/run_all_tests.py`：空测试目录跳过不判失败（修复 0 tests 误判）；`llm_manager` 纳入 TEST_GROUPS
- **最终验证**：`python scripts/run_all_tests.py` → **8 组通过, 0 组失败，全部通过**（主项目 196 passed + perfetto_capture 161 + agent_chat 196 + 各模块）

### 2026-08-05（首启/切 Tab 卡死性能修复 + debug 诊断日志系统完善）

- **根因定位**：GUI 主线程同步执行阻塞操作导致"首次启动/切换 Tab 卡死退出"
  - ① 主线程同步 ADB：`DeviceMonitor._poll`（主线程 QTimer）→ 设备变化 → 各 Tab `on_devices_changed`/`on_activated` 同步调 `adb get_connected_devices` / 多次 `adb getprop`。慢 adb 场景实测 `_on_devices_changed` 卡 2.6s、切 Tab 卡 0.87-0.99s，真实设备假死时放大为数十秒 → Windows 未响应 → 强退
  - ② 主线程文件系统扫描：`perfetto_capture` 每次 `on_activated` 重复 `scan_sessions()` + 递归扫 `trace_report/`（trace 目录 225MB）
  - ③ 首次冷启动 import `pyqtgraph`（3s+）/`pandas`（2s+）拉长窗口显示前黑屏期
- **修复**：
  - `game_perf` / `device_disguise`：`_get_serial()` 从同步调 adb 改为读缓存（`on_devices_changed` 已传入 devices，不再重复查询）
  - `perfetto_capture`：`_try_fetch_device_info` 异步化（`_DeviceInfoWorker` QThread）；`on_activated` 历史刷新加目录签名缓存（`_maybe_refresh_history`）
  - `DeviceMonitor._poll`：防重入 + 耗时统计
  - 验证：慢 adb 场景切 Tab 遍历从 2.7s → **0.002s**，`_on_devices_changed` 2.6s → **0.001s**
- **新增 debug 诊断日志系统**（`toolkit/core/perf_debug.py`）：
  - `TimeIt` 耗时打点上下文管理器/`timed` 装饰器（慢操作超阈值 warning，debug 输出明细）
  - `MainThreadWatchdog` 主线程卡死检测：心跳超时自动 dump 主线程堆栈到日志（解决"卡死但无日志"）
  - 集成：`AdbManager` 每次命令耗时、`DeviceMonitor._poll` 耗时、`MainWindow.add_tab`/`_on_tab_selected` 耗时、`app.py` 启动阶段打点
  - `--debug` 参数自动启用；`tests/test_perf_debug.py` 19 个测试
- 新增诊断脚本 `scripts/diag_startup_perf.py`（无头实测各阶段耗时 + 模拟慢 adb 复现卡死）

### 2026-06-02（agent-wiring-fix 收尾 + DES-002 差距分析）

- agent-wiring-fix: 49/50 任务完成。本会话完成剩余 13 项任务：
  - 10.1: SkillsManager.create_agent_tools() 委托到 build_skill_tools()
  - 4.6: AgentPanel drag-to-resize（240-480px clamp），RightPanel/AgentPanel 宽度解锁
  - 4.7: AgentPanel session selector（QComboBox + 新建按钮 + 会话切换/消息加载）
  - 11.3: 消除最后一条反向依赖 — builtin.py 迁移到 `toolkit/agent/builtin.py`
  - 10.2: 修复 test_no_executor_returns_error（GLMProvider mock → provider 注入）
  - 1.5/9.5/11.6: 全部测试套件通过（agent_skill_tools 10p + mcp_registry 8p + agent_chat 37p）
  - 11.1-11.7: 全量语法/导入/反向依赖/启动链路验证通过
  - 仅剩 11.8（需 LLM API Key 手动 GUI 验证）
- DES-002 vs agent-wiring-fix 差距分析：确认 **20 项新交付物未覆盖**（ErrorClassifier/CircuitBreaker/Watchdog/ConversationLoop/ContextCompressor/Verification/KnowledgeBase/MemoryManager/SubAgent 等）
- 启动链路验证: 7 plugins, 24 tools (13 plugin + 9 skill + 2 builtin), service created OK

### 2026-05-26（Hermes Agent 深度引入 — 框架升级设计）

- 深度分析 AI-Performance-Platform 项目中 Hermes Agent 的完整能力矩阵（107 agent + 97 tools + 571 skills）
- 对比 lv-game-toolkit 当前架构（DES-001 完成态）与 Hermes 全景能力，识别 6 项已有 / 6 项薄弱 / 12 项缺失
- 撰写 [DES-002](design/DES-002-hermes-agent-upgrade.md) 框架升级设计文档，涵盖：
  - 对话循环升级：朴素递归 → 状态机驱动的鲁棒编排（ErrorClassifier + CircuitBreaker + Watchdog + RetryPolicy）
  - 工具执行安全层：ToolGuardrail 三层检查（静态规则 / 动态规则 / 自定义规则）
  - 上下文管理升级：ContextCompressor（关键数字保留 + 摘要）+ MemoryManager（跨会话记忆）
  - 分析质量保障：Verification + Reflection + ConfidenceModel（五级置信度）+ PlanGate（分析计划门禁）
  - 知识库体系：从空壳 ReportIndex → 可检索 KnowledgeBase（TF-IDF 搜索 Skill + 案例 + SOP + Vendor）
  - SubAgent 启步 + 错误韧性全链路
- 四阶段实施路线：Phase 1 韧性基础（3-5 天）→ Phase 2 质量保障（3-5 天）→ Phase 3 知识库与记忆（5-7 天）→ Phase 4 SubAgent（5-7 天）

### 2026-05-26（Agent 核心重构实现 — 80 tasks）

- `modules/agent_chat/` → `toolkit/agent/`：Agent 从"聊天模块"提升为框架级核心引擎
- `ToolRegistry`/`ToolExecutor`/`MCP Framework` 提升到 `toolkit/core/`，消除循环依赖
- `SkillRegistry` 增强：合并 discovery 扫描 + 三级渐进加载 + 平台过滤
- Agent GUI 从中央 Tab 改为右侧可展开面板（AgentPanel），独占 RightPanel 内容区
- System Prompt 三段式重构（Stable/Context/Volatile），借鉴 Hermes Agent 设计
- SOP 系统合并到 Skill 体系；SubAgent 空实现移除；AgentConfig 废弃 LLM 字段清理
- `llm_manager` 统一管理 LLM Provider，Agent 不再自行创建
- MCP 统一前缀 `mcp__{server}__{tool}`，支持 local/external/remote 三种来源
- 217/217 测试通过（6 deprecated、2 SubAgent/LLM 文件删除）

### 2026-05-26（Agent 核心重构设计方案）

- 完成 Agent 核心架构重构设计文档 [DES-001](design/DES-001-agent-core-refactor.md)
- 确定重构方向：`modules/agent_chat/` → `toolkit/agent/` + Core 基础设施下沉
- 参考 Hermes Agent 架构：Registry Pattern、Progressive Disclosure、三段式 System Prompt
- 关键决策：模块 Tool 不再直接暴露，统一封装为 Skill 或 MCP Tool
- 确定三层架构：Core (注册中心) → Agent (编排引擎) → Modules (能力提供者)

### 2026-05-26（LLM Manager 模块重构：多 Provider 配置化 + 精简设置 + Thinking + Token 统计）

- 新建 `modules/llm_manager/` 独立模块：Provider 配置管理、Token 用量记录、插件化注册
- Provider 配置从硬编码（2 个）迁移到 `data/config/llm_providers.json`，支持多 Provider 自定义 API 地址/Key/模型列表
- 框架层 `LLMConfig` 从 9 字段精简到 2 字段（provider + model_name），移除 temperature/max_tokens/smart_switch/token_budget/budget_alert_threshold
- `LiteLLMProvider` 支持 `api_base`（自定义 URL）和 `thinking`（Anthropic extended thinking）参数
- `LLMManager` 精简：移除 smart_switch 降级逻辑、token_budget 预算告警、degradation_occurred 信号
- 设置面板精简为 Provider 下拉 + Model 下拉 + Thinking 开关 + Base URL/API Key 编辑 + 管理按钮
- 「管理 Provider」按钮改为直接打开 `llm_providers.json` 系统编辑器
- 状态栏上下文圆环改为单色填充 + hover tooltip，移除文字标签和颜色区分
- Token 用量后台 SQLite 记录（四维度：request/conversation/trace/total）
- Bug 修复：hookimpl 来源错误 → 插件钩子不触发（BUG-002）；ghostBtn 无颜色 → 按钮不可见；模型下拉不填充；QComboBox/QLineEdit 高度不一致

### 2026-05-25（日志面板 UI 重构：导出迁移 + 控制台 Tab 化 + 设置菜单扩展）

- 底部面板 header 移除「导出」按钮，迁移到右上角设置 → 日志 → 导出日志
- 设置菜单新增「日志」二级菜单（导出日志 / 历史日志 / 清空历史），SettingsButton 新增 3 个 pyqtSignal
- 「控制台」从独立 QPushButton checkable 改为 QTabBar tab，紧挨「全部」右侧，11px 统一字体
- 删除 `_show_console` / `_console_btn` / `_on_console_toggled`，源过滤逻辑简化
- header 清除按钮从 text+font 改为 `_cached_icon()` + `setIcon()` 方式，修复 QSS 覆盖导致图标不显示
- 底部面板新增 `export_logs` / `open_log_directory` / `clear_log_history` 公开方法
- MainWindow 新增 SettingsButton → BottomPanel 信号桥接

### 2026-05-25（历史面板架构重构：提取基类 + 统一数据源 + codicon 图标迁移）

- 提取 `BaseHistoryTreeWidget` 到 `toolkit/gui/widgets/` — 通用历史树基类，统一右键菜单、主题、搜索过滤、格式化工具、send_to_agent 信号
- 拆分 `history_panel.py`（~850行）为 `session_tree.py` 和 `analysis_tree.py`，各继承基类
- 删除未使用的覆盖式 `HistoryPanel`（~500行含动画、遮罩、双栏布局）
- 统一分析任务数据源：废弃 `pe_analysis_tasks`，以 `pa_analysis_tasks` 为权威表
- `PerfettoAnalysisService` 新增 `create_analysis_record` / `update_analysis_record` 写入方法，`get_analysis_history()` 归一化返回格式
- `gui_tab.py` 消除"创建 HistoryPanel → 拆出 widget → 重新挂载"反模式
- 历史面板所有 Unicode Emoji 迁移到 `assets/codicon.ttf` 字体图标，补充 22 个新 codicon 映射
- `app_paths.py` 新增 `get_output_dir()` 统一 dev/frozen 输出目录
- 测试：17+4 个已有测试通过，新增 11 个 BaseHistoryTreeWidget 测试

### 2026-05-20（Agent Tool Unification 重构：CLI → MCP Server + Skill）

- 全面移除 CLI 体系（移除 Typer/Rich 子命令、`cli_commands.py`、`test_cli.py`、`strings_cli.py`），以 MCP Server + Skill 替代
- 建立 MCP Server（FastMCP）与 Skill Registry（YAML frontmatter 标准化），框架层通过标准协议自动收集各模块工具
- `ToolkitDef` 统一，各模块通过 `register_agent_tools()` 返回 JSON Schema 工具定义、`register_skills()` 返回 SKILL.md 路径
- 以 `device_disguise` 为试点模块完成迁移验证
- 测试覆盖：150 个测试全部通过，含主项目、device_disguise 及各业务模块

### 2026-05-20（统一日志规范约束体系化）

- 统一日志体系规则写入 CLAUDE.md 与 .claude/rules/log-panel-rules.md：
  - 3 个场景的正确日志接口标准：Service/Engine 层用 `logging.getLogger()`、GUI Tab 层用 `self._log()`、结构化日志用 `UnifiedLogger.bind_module()`
  - 禁用 `print()` 输出诊断/错误/警告（保留 CLI 交互输出例外）
  - 日志级别语义与 GUI 面板行为对照表（debug/info/success/warning/error）
- `.cursor/rules/log-panel-rules.mdc` 与 `.claude/rules/log-panel-rules.md` 内容同步对齐
- `docs/knowledge/module-development-guide.md` 新增「日志输出规范」章节 + 「常见错误」条目 #6
- 7 个模块的 `print()` 已清理完毕，全部桥接到 `unified_logger` 统一路由

### 2026-05-20（字符串提取规范体系化与归档）

- 完成字符串提取规范的长期规则化：
  - CLAUDE.md「不可违反的硬规则」新增第 9 条：用户可见中文文本必须提取到 `strings_*.py`
  - 新建 `.claude/rules/string-extraction-gate.md`：明确提取范围、豁免范围、常量命名约定、导入方式、微调流程
  - 明确日志输出（`_log()`、`logger.debug()` 等）不需要提取，避免过度工程
- specs/019-hardcoded-string-extraction 归档：
  - 创建 `ARCHIVE.md` 记录完成交付物、已知遗留项、后续微调策略
  - `spec.md` 状态标记为 Archived
- 当前字符串提取模式已覆盖 7 个模块 + 框架层，后续按模块逐个微调即可

### 2026-05-20（硬编码中文字符串提取完成）

- 完成 5 个目标模块的硬编码字符串提取，统一提取到 `strings_gui.py` / `strings_service.py`（`strings_cli.py` 已随 CLI 移除）
  - perfetto_capture、agent_chat、perfetto_analysis、perfdog_insights、workspace_tools
- 完成 `toolkit/gui/` 框架层字符串提取，集中到 `toolkit/gui/strings.py`
  - 覆盖 main_window.py、home_tab.py、toolkit_dialog.py、llm_settings_dialog.py、base_tab.py、title_bar.py、llm_status_widget.py
- `Final[str]` 常量模式统一，功能前缀分组（BTN_、LABEL_、MSG_、DLG_TITLE_、CLI_HELP_ 等），格式模板使用 `_FMT` 后缀
- `scripts/check_hardcoded_strings.py` 确认：已迁移模块源码零中文硬编码残留（注释/文档字符串除外）
- 全量 pytest：
  - 主项目 tests/、device_disguise、perfetto_analysis（302 passed）、workspace_tools（15 passed）、game_perf（5 passed）通过
  - agent_chat（289 passed）、perfetto_capture（163 passed）通过
  - perfdog_insights 的 1 个失败为既有测试缺陷（CLI 子命令调用未传参），非迁移引入

### 2026-05-19（路径规范化重构）

- 新增 `toolkit/core/app_paths.py` 集中式路径工具，消除各模块重复的 `sys.frozen` 分支
- 所有 7 个模块迁移至新路径规范：
  - 配置文件：dev=`modules/<name>/config/<file>` → frozen=`data/config/<name>_<file>`（扁平命名）
  - 数据库：统一 `data/db/<module>_<db>.db`
  - 备份：统一 `data/backup/<module>/`
- 构建脚本更新为 `data/config/` 扁平目录结构，构建后自动生成带模块名前缀的配置文件

### 2026-04-09（长期记忆系统优化）

- 合并 7 个模块 constitution → AGENTS.md，AGENTS.md 成为统一权威约束源
- 删除 63 个模块级 Speckit 命令文件 + 84 个模板/脚本
- 为 7 个模块创建 specs/INDEX.md 状态索引
- 删除 doc/legacy/ 旧版文档归档
- 合并 doc/ + context/ → docs/ 统一文档目录
- context-engineering.mdc 添加大文档检索策略

### 2026-04-09（编译优化）

- 构建时间缩减 ~63%（双入口合并为单次构建 + PE header patching）
- 产物体积减少 ~55MB（排除 31 个无用依赖）
- 自动版本号管理（git tag → VERSION 文件 → 运行时读取）

### 2026-04-09（perfetto_analysis 架构审查）

- 修复 14 个问题（H1-H3, M1-M8, L1-L6）
- 分支清理（7 本地 + 4 远程废弃分支）
- analysis-architecture.md 文档全面对齐

## 业务汇报

向管理层汇报项目进度时，参见 [汇报流程](team/progress-reporting.md)。用户在会话中说"准备汇报"即可触发 Agent 协助生成飞书汇报文档。
