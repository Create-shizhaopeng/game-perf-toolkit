## Context

LV Game Toolkit 当前以"便携绿色包"分发：PyInstaller `--onedir` 构建 `dist/Toolkit/`，打 zip 下发，用户解压即用。所有用户数据(config/db/backup/logs/output)通过 `toolkit/core/app_paths.py` 的 `get_exe_dir()` 解析，落在 exe 同级 `data/` 与 `output/` 目录。这套架构的三个根本缺陷：

1. **数据与程序混居**：exe 同级目录在安装版下(`Program Files`)对普通用户只读，SQLite 写入、配置保存全部 `PermissionError`。
2. **无更新机制**：全库 grep `check_update/auto_update` 零命中，用户只能手动覆盖解压，易丢数据。
3. **路径旁路**：`app.py:63` 硬编码 `DATA_DIR = Path(sys.executable).parent / "data"`，绕过 `app_paths.py` 封装，已有两套路径并存的技术债。

约束与现状（代码事实，explore 阶段实测）：

- `run_mcp_server()`([toolkit/app.py:255-289](toolkit/app.py#L255-L289)) **不创建 QCoreApplication**，headless 模式下 `QStandardPaths.writableLocation()` 只返回 `AppData/Local` 根目录、**不带 appname 隔离**（实测确认）。
- `platformdirs` 4.9.4 已作为传递依赖存在于环境，纯 Python，GUI 与 headless 通用，`roaming` 参数显式控制 roaming/local。
- `build.py` 已是 `--onedir` 模式(`COLLECT` 段)，满足 Velopack 硬性要求（`--onefile` 不兼容）。
- 直调 `get_exe_dir()/data` 拼路径的"旁路点"约 15 处：`app.py`、`db_manager.py`、`config_manager.py`、`llm_manager/service.py`、`perfetto_capture/service.py`、`agent_chat/`、`toolkit/agent/` 等。其余调用点已走 `app_paths` 封装函数(`get_config_path`/`get_db_path`/`get_output_dir`/`get_backup_path`)。

## Goals / Non-Goals

**Goals:**

- 用户数据与程序本体彻底分离：程序只读(Program Files / frozen _MEIPASS 周边)，用户数据 per-user 可写(APPDATA)。
- 安装版分发：Setup.exe 一键安装，应用内自动检查更新，delta 差分下载，下次启动生效。
- 老便携用户数据平滑迁移到新分层路径，零数据丢失。
- 路径解析统一收口到 `app_paths.py` 三层接口，消除 `DATA_DIR` 硬编码与 `get_exe_dir()/data` 旁路。
- GUI 与 headless(MCP server) 模式路径解析一致。

**Non-Goals:**

- 不做跨平台(Linux/macOS)安装包——当前仅 Windows，但路径层选 platformdirs 保留可扩充性。
- 不做 MSIX 容器化——VFS 重定向与 APPDATA 路径架构冲突，且签名/sideload 摩擦大。
- 不做企业 MSI/SCCM 部署——内部测试团队规模无需。
- 不做云端账号同步/Settings Sync——本阶段只本地数据保留。
- 不引入 Squirrel/WinSparkle——已归档或非 Python 友好，Velopack 一体化替代。
- 不改 PyInstaller 构建产物的内部结构(仍 `--onedir`)，只改打包后处理(打 zip → vpk pack)。

## Decisions

### D1: 数据路径层用 platformdirs，不用 QStandardPaths

**选择**: `platformdirs` 4.9.4（[pypi.org](https://pypi.org/project/platformdirs/)）。

**理由**: `run_mcp_server()` 无 QCoreApplication，`QStandardPaths` 在此状态下实测只返回 `AppData/Local` 根、无 appname 隔离（致命）。QStandardPaths 要在 headless 模式可用须硬塞 `QCoreApplication`，是为路径引入额外 Qt 耦合，违反"拒绝妥协改造"。`platformdirs` 纯 Python、GUI/headless 通用、已作为传递依赖在环境、`roaming` 参数显式控 roaming/local、appdirs 继任者(Python 生态标准)。

**备选**: QStandardPaths(排除：headless 无隔离 + Qt 耦合);纯 stdlib `os.environ["APPDATA"]`(排除：跨平台与边界处理需自造轮子，违反"选成熟方案")。

**实测路径**(`app="LV Game Toolkit"`, `author="lv-toolkit"`)：
- config roaming: `C:\Users\<u>\AppData\Roaming\lv-toolkit\LV Game Toolkit` ← `user_config_dir(app, author, roaming=True)`
- data local: `C:\Users\<u>\AppData\Local\lv-toolkit\LV Game Toolkit` ← `user_data_dir(app, author)`
- logs: `...\Local\...\Logs` ← `user_log_dir`
- cache: `...\Local\...\Cache` ← `user_cache_dir`
- output: `C:\Users\<u>\Documents\LV Game Toolkit` ← `user_documents_dir()` + 子目录

### D2: 三层分类(config roaming / data local / output Documents)

**选择**: 按 Microsoft 桌面应用数据惯例([learn.microsoft.com](https://learn.microsoft.com/en-us/windows/apps/design/app-settings/store-and-retrieve-app-data))三分：

| 层 | 位置 | 内容 | 语义 |
|----|------|------|------|
| config | `%APPDATA%\Roaming\lv-toolkit\LV Game Toolkit` | `*.json` 配置 | roaming，跟随用户，小 |
| data | `%LOCALAPPDATA%\lv-toolkit\LV Game Toolkit` | `db\`、`logs\`、`backup\`、`cache\` | local，机器绑定，大 |
| output | `Documents\LV Game Toolkit`（可配置） | `trace\`、`trace_report\` | 用户产物，可见，被备份 |

**理由**: Microsoft 官方判定标准——"用户是否需直接交互/拥有"。trace/报告是用户主动采集分析的产物，归属 Documents；db/logs/backup/cache 是内部态，归属 LOCALAPPDATA。output 塞 APPDATA 会撑爆 roaming 同步配额。VSCode/PyCharm/DBeaver 同款惯例。

**output 可配置**: output 根存 `toolkit_config.json["output_dir"]`，默认 `Documents\LV Game Toolkit`，设置面板可改，经 `config_changed` 信号实时同步(复用 [config-sync-rules.md](.claude/rules/config-sync-rules.md) 的 FileConfigService 体系)。

**备选**: output 全放 LOCALAPPDATA(排除：用户看不到自己的 trace，违反 MS 惯例);output 全放固定 Documents(排除：用户可能想放 D 盘大容量位，需可配)。

### D3: 安装包 + 更新一体化用 Velopack

**选择**: [Velopack](https://velopack.io/)（velopack.io · 2.3k★ · 4175 commits · Squirrel 继任者）。

**理由**: 一次性解决"安装包格式 + 更新机制 + 整包 vs 增量"三件事——Setup.exe 一键安装 + `UpdateManager` 后台检查/下载/应用 + 自带 delta 差分("只下载版本间 diff")。不用拼接 Inno Setup + 独立更新框架(违反"拒绝妥协")。PyInstaller `--onedir` 官方文档支持([docs.velopack.io](https://docs.velopack.io/getting-started/python))，本项目 build.py 已是 `--onedir`，零改造满足。跨平台(Win/Mac/Linux)保留可扩充性。代码签名/公证内置。

**集成点**:
- 构建侧：`build.py` 在 PyInstaller 产出 `dist/publish/` 后，调 `vpk pack --packId LVGameToolkit --packVersion <ver> --packDir dist/publish --mainExe Toolkit.exe`，产出 Setup.exe + delta 包发 GitHub Releases。
- 运行时侧：`toolkit/app.py` 的 `main()` 最前面植入 `velopack.App().run()`(可能在更新应用时重启进程，须在所有启动代码之前)，`UpdateManager` 在 GUI 启动后后台检查更新。

**备选**: Inno Setup(25 年极成熟，但只安装不更新，需另配更新框架且无 delta，妥协拼接);MSIX(微软推，但 VFS 容器化重定向 APPDATA 与 D1/D2 路径架构冲突，签名/sideload 摩擦);Inno + Squirrel(Squirrel 已 archived 归档)。

**诚实权衡**: Velopack 2.3k★ 比 Inno Setup 年轻，但对内部测试团队规模(非百万用户)成熟度足够，可扩充性维度(delta + 跨平台 + 一体化)碾压。

### D4: 更新源用 GitHub Releases

**选择**: GitHub Releases 作为 Velopack `UpdateManager` 的 feed 源。

**理由**: 零运维、版本管理好、Velopack 原生 Squirrel-style feed 支持。私有分发用私有 repo + token。

**备选**: 自建静态 HTTP(运维成本);内网文件共享(更新体验差)。

### D5: 老便携用户数据迁移助手(半自动)

**选择**: 新安装版首启检测 + 弹窗让用户确认旧便携版目录 + 按分层映射复制 + 写迁移标记。

**理由**: Firefox/VSCode 便携→安装迁移的成熟做法也是"手动复制文件夹"(因旧便携位置不固定)。旧便携解压位置用户各异(Desktop/Downloads/自定义)，无法自动定位，半自动(用户确认 + 程序映射复制)是可控且零误判的方案。迁移标记文件 `config/.migrated_from_portable` 防重复；全新用户点"跳过"。

**映射规则**:
- 旧 `data/config/*.json` → config roaming
- 旧 `data/db/*.db` → data local/db
- 旧 `data/backup/` → data local/backup
- 旧 `data/logs/` → 跳过(日志无需迁移)
- 旧 `output/trace/` → output/trace
- 旧 `output/trace_report/` → output/trace_report

### D6: app_paths.py 重构策略——接口不变，内部换分层根

**选择**: `get_config_path`/`get_db_path`/`get_output_dir`/`get_backup_path` 对外签名与语义不变，内部从 `get_exe_dir()` 改走 D1/D2 三层根。`get_exe_dir()` 语义收窄为"只读程序资源根"(frozen=exe 所在或 _MEIPASS 周边，dev=项目根)，不再用于写数据。新增 `get_user_config_dir()`/`get_user_data_dir()`/`get_user_output_dir()` 三层根函数。

**理由**: 走封装的调用点(占多数)零改动，重构面锁死在 ~15 处 `get_exe_dir()/data` 直拼点。遵循 [code-quality-gate.md](.claude/rules/code-quality-gate.md)：移动/重构用 cp+Edit，禁止 Write 重写。

**`app.py:63` 处理**: 删除 `DATA_DIR` 硬编码，`_build_context()` 改用 `get_user_config_dir()`/`get_user_data_dir()` 解析。`_resolve_log_level()` 中 `DATA_DIR / "config" / "toolkit_config.json"` 同步改。

### D7: 运行时更新钩子位置

**选择**: `velopack.App().run()` 放在 `toolkit/app.py` 的 `main()` 函数最前面，在 `setup_logging`/`_resolve_log_level` 之前。

**理由**: [Velopack 文档](https://docs.velopack.io/getting-started/python) 明确要求"as early as possible, before any other app startup code"，因为它可能 quit/restart 进程以应用更新。放最前确保更新应用不被 logging/插件加载等副作用干扰。`_fix_frozen_stdio()`(行 12-27)属 stdio 修复，须在钩子前(否则 frozen 下 velopack 可能触发 IO 异常)，保持其模块级执行。

## Risks / Trade-offs

- **[R1] Velopack 相对新(2.3k★) vs Inno Setup(25 年)** → 内部测试团队规模成熟度足够;锁定在 D1/D2 路径层与 D3 分发层解耦，若 Velopack 未来不可用，回退 Inno Setup + 手动更新只需重写 `build.py` 打包段与 `app.py` 钩子，路径层与迁移层不受影响。
- **[R2] 老用户迁移误判旧目录** → 迁移助手不自动扫描，由用户明确指定目录;复制前预览将迁移的文件清单;复制而非移动(旧数据保留，迁移失败可重试)。
- **[R3] roaming 配置同步配额** → config 层只放小 JSON，db/output 全在 local/Documents，不进 roaming。
- **[R4] dev 与 frozen 路径差异** → dev 下 `platformdirs` 仍解析到 `%APPDATA%`(用户级)，与当前 dev 用 `<root>/data` 不同。开发体验影响：dev 测试数据不再在项目根 `data/`。缓解：dev 模式可通过环境变量 `LV_TOOLKIT_DATA_DIR` 覆盖指向项目 `data/`(测试 fixture 用)，frozen 走标准路径。
- **[R5] MCP server 模式更新钩子** → `velopack.App().run()` 在 `main()` 最早处，MCP 模式也会经过。更新应用会重启进程，MCP stdio 连接会断开重连。缓解：MCP 模式可配置跳过更新检查(更新仅 GUI 模式触发)，或接受 stdio 重连。
- **[R6] 构建依赖 .NET SDK(vpk CLI)** → CI/构建机需装 .NET SDK。缓解：`vpk` 是全局工具一次性安装，写进构建文档。
- **[R7] code signing 证书成本** → EV 证书贵。缓解：本阶段内部团队可先不签名(Windows SmartScreen 警告可接受)，后续上量再签。

## Migration Plan

**阶段 1: 路径层重构(地基)**
1. 重写 `app_paths.py`：新增三层根 + 封装函数内部改走 platformdirs + `get_exe_dir()` 语义收窄。
2. 逐个清理 ~15 处 `get_exe_dir()/data` 直拼点(cp+Edit)，改走分层函数。
3. 拆 `app.py:63` `DATA_DIR`，`_build_context`/`_resolve_log_level` 改分层。
4. 重写 `tests/test_app_paths.py`(三层路径 + dev 覆盖环境变量)。
5. 启动验证(`python -m toolkit.app` 无头路径 + GUI)。

**阶段 2: output 可配置 + 迁移助手**
6. `toolkit_config.json` 增 `output_dir` 字段，`get_output_dir` 优先读配置。
7. 设置面板增 output 目录选择控件，`config_changed` 同步。
8. 新建 `toolkit/gui/portable_migration_dialog.py` 迁移助手 UI + `toolkit/core/portable_migration.py` 迁移逻辑。
9. `tests/test_portable_migration.py` 覆盖映射规则与迁移标记。

**阶段 3: Velopack 集成**
10. `pyproject.toml` 声明 `platformdirs`、`velopack` 依赖。
11. `app.py` 植入 `velopack.App().run()` 钩子(D7 位置) + GUI 后台 `UpdateManager` 检查。
12. `build.py` 对接 `vpk pack`：PyInstaller 产出后调 vpk 产 Setup.exe + delta。
13. GitHub Releases feed 配置 + 首个版本发布验证。

**回退策略**: 阶段 1 完成即可独立交付(路径层正确，仍走 zip 分发);阶段 3 失败不影响阶段 1/2。git 分支隔离，每阶段独立验证。

## Open Questions

- Q1: 迁移助手是否需扫描常见解压位置(Desktop/Downloads)给出候选目录，还是纯手动指定?倾向手动(零误判)，待 UI 设计时定。
- Q2: GUI 模式的 `UpdateManager` 检查更新 UI——是静默后台 + 有更新弹通知，还是"检查更新"按钮手动触发?倾向静默后台 + 弹通知(现代应用惯例)，待设置面板设计定。
- Q3: dev 模式环境变量覆盖名 `LV_TOOLKIT_DATA_DIR` 是否合适，是否需单独 `LV_TOOLKIT_CONFIG_DIR`/`LV_TOOLKIT_OUTPUT_DIR`?倾向先单一变量覆盖 data 根，按需扩展。
