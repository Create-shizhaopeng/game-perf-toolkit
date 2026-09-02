## Why

当前 LV Game Toolkit 以"便携绿色包"(zip 解压即用)形式分发，所有用户数据(config/db/backup/logs/output)堆在 exe 同级 `data/` 目录。这导致两个根本问题:① 用户覆盖升级时极易丢失或污染数据，无法做版本化的干净更新;② 限制了下发自动更新、增量更新等现代分发能力。项目已具备 7 模块、SQLite 索引、LLM 配置等用户长期沉淀的状态，"保留用户数据"已从可选变为刚需。现在升级到"安装包分发 + 增量更新 + 数据隔离"架构，时机成熟且基础设施成本可控。

## What Changes

- **数据路径三层分层**: 基于 platformdirs 将用户数据从 exe 同级目录迁移到 OS 标准位置 —— 配置层 roaming(`%APPDATA%`)、数据层 local(`%LOCALAPPDATA%` 的 db/logs/backup/cache)、产物层 Documents(`Documents\LV Game Toolkit\`，可配置)。程序本体(只读)与用户数据(per-user 可写)彻底分离。**BREAKING** 旧便携版 exe 同级 `data/` 不再被直接使用，需迁移。
- **app_paths.py 重构**: 引入 `get_user_config_dir()` / `get_user_data_dir()` / `get_user_output_dir()` 三层根函数，`get_exe_dir()` 语义收窄为"只读程序资源根"，不再用于写数据。`get_config_path`/`get_db_path`/`get_output_dir`/`get_backup_path` 对外接口不变，内部改走分层根。**BREAKING** app.py:63 硬编码 `DATA_DIR` 旁路清理，直调 `get_exe_dir()/data` 的 ~15 处直拼点改为分层函数。
- **安装包 + 更新一体化 (Velopack)**: 引入 [Velopack](https://velopack.io/) 作为安装与自动更新框架(Squirrel 继任者，PyInstaller `--onedir` 官方支持)。构建产物从"打 zip"改为 `vpk pack` 产出 Setup.exe + delta 更新包;运行时入口植入 `velopack.App().run()` 钩子 + `UpdateManager` 后台检查更新，delta 差分下载。**BREAKING** 分发物从 zip 变为 Setup.exe。
- **更新源 (GitHub Releases)**: UpdateManager 指向 GitHub Releases feed 作为更新源，零运维;私有分发场景使用私有 repo + token。
- **老便携用户数据迁移助手**: 新安装版首次启动检测旧 `data/` 目录，弹窗让用户确认旧便携版位置，按分层映射半自动复制(config→roaming, db/backup→local, output→Documents)，写迁移标记防重复。全新用户可跳过。
- **output 大文件目录可配置**: output 根路径存入 `toolkit_config.json["output_dir"]`，设置面板可改，经 `config_changed` 信号实时同步(复用已有 FileConfigService 体系)。

## Capabilities

### New Capabilities

- `app-data-paths`: 用户数据路径三层分层解析(config roaming / data local / output Documents)，platformdirs 封装，GUI 与 headless 通用，对外稳定接口。
- `installer-update`: Velopack 安装包构建与运行时自动更新能力(delta 差分、后台检查、下次启动生效、代码签名)。
- `portable-data-migration`: 老便携版数据到新安装版的首次启动半自动迁移助手。

### Modified Capabilities

- `mcp-server`: 启动路径解析从 `DATA_DIR` 硬编码改为走 `app-data-paths` 分层根(headless 模式无 QCoreApplication 可用)。

## Impact

- **代码**: `toolkit/core/app_paths.py`(重写核心)、`toolkit/app.py`(入口钩子 + DATA_DIR 拆分)、`toolkit/core/config_manager.py`、`toolkit/core/db_manager.py`、`modules/llm_manager/src/service.py`、`modules/perfetto_capture/src/service.py`、`modules/agent_chat/` 及 `toolkit/agent/` 中直调 `get_exe_dir()/data` 的 ~15 处点、`scripts/build.py`(对接 vpk pack)、`toolkit/gui/`(设置面板 output_dir 配置项 + 迁移助手 UI)。
- **依赖**: 新增 `platformdirs`(已作为传递依赖在环境，需显式声明到 `pyproject.toml`)、`velopack`(pip 包，运行时更新钩子);构建时新增 `vpk` CLI(.NET SDK 全局工具)。
- **分发**: 产物从 `lv-game-toolkit-v*-windows.zip` 变为 `Setup.exe` + GitHub Releases delta feed;用户首次安装走 Setup.exe，后续走应用内自动更新。
- **测试**: `tests/test_app_paths.py` 重写(三层路径)、新增 `tests/test_portable_migration.py`、build.py 集成测试对接 vpk。
- **文档**: `CLAUDE.md` 分发章节、`docs/architecture/` 路径与分发架构、`docs/PROGRESS.md`。
