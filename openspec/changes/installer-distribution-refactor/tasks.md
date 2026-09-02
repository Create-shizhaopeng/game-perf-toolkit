# Tasks — installer-distribution-refactor

> 依赖关系: 阶段 1(路径层地基) → 阶段 2(output 配置 + 迁移助手) → 阶段 3(Velopack 集成)。
> 阶段 1 完成即可独立交付(路径层正确，仍走 zip 分发)。遵循 [code-quality-gate.md](.claude/rules/code-quality-gate.md): 移动/重构用 cp+Edit，禁止 Write 重写; 每阶段完成后执行启动验证。

## 1. 依赖声明与路径层骨架

- [x] 1.1 在 `pyproject.toml` 显式声明 `platformdirs` 依赖(当前仅作为传递依赖存在)
- [x] 1.2 在 `pyproject.toml` 声明 `velopack` 运行时依赖
- [x] 1.3 `uv pip install` 同步依赖，确认 `platformdirs` 4.9.4 与 `velopack` 可导入
- [x] 1.4 在 `toolkit/core/app_paths.py` 新增三层根函数 `get_user_config_dir()`(roaming=True)、`get_user_data_dir()`、`get_user_output_dir()`(默认 Documents，读 config 覆盖)，底层走 platformdirs
- [x] 1.5 `get_exe_dir()` 语义收窄注释更新: 仅"只读程序资源根"，标注不再用于写数据

## 2. app_paths 封装函数内部改走分层根

- [x] 2.1 `get_config_path()` 内部从 `get_exe_dir()/"data"/"config"` 改走 `get_user_config_dir()`
- [x] 2.2 `get_db_path()` 内部改走 `get_user_data_dir()/"db"`
- [x] 2.3 `get_backup_path()` 内部改走 `get_user_data_dir()/"backup"`
- [x] 2.4 `get_output_dir()` 内部改走 `get_user_output_dir()`(config 覆盖优先)
- [x] 2.5 确认各封装函数对外签名与扁平命名语义不变(走封装的调用点零改动验证)

## 3. 清理 get_exe_dir()/data 直拼旁路点

- [x] 3.1 `toolkit/app.py:63` 删除硬编码 `DATA_DIR`，`_build_context()` 改用 `get_user_config_dir()`/`get_user_data_dir()` 解析 config 与 db 路径
- [x] 3.2 `toolkit/app.py:307` `_resolve_log_level()` 中 `DATA_DIR/"config"/"toolkit_config.json"` 改走 `get_config_path` 或 `get_user_config_dir()`
- [x] 3.3 `toolkit/core/config_manager.py:31` 默认 config_path 改走 `get_user_config_dir()/"toolkit_config.json"`
- [x] 3.4 `toolkit/core/db_manager.py:24` 默认 db_path 改走 `get_db_path` 或 `get_user_data_dir()/"db"/"toolkit.db"`
- [x] 3.5 `modules/llm_manager/src/service.py` 三处 `get_exe_dir()/"data"/"config"` 与两处 `/"data"/"db"` 改走 `get_config_path`/`get_db_path`
- [x] 3.6 `modules/perfetto_capture/src/service.py:63,98` `get_exe_dir()/"data"` 与 `get_exe_dir()/"output"/"trace"` 改走分层函数
- [x] 3.7 `modules/agent_chat/src/tools/builtin.py:21-22` 与 `toolkit/agent/builtin.py:21-22` agent_workspace 路径改走分层
- [x] 3.8 `toolkit/agent/__init_plugin.py:74-78` `get_exe_dir()/"data"` 改走分层
- [x] 3.9 `toolkit/core/skill_registry.py:88-91` `get_exe_dir()/"data"/"sops"` 改走分层
- [x] 3.10 `toolkit/agent/knowledge/report_index.py:114-115` 与 `modules/agent_chat/src/knowledge/report_index.py:114-115` output 路径改走 `get_output_dir("trace_report")`
- [x] 3.11 `modules/perfetto_capture/src/session_tree.py:97-100` output 路径改走 `get_output_dir`
- [x] 3.12 `modules/game_perf/src/plugin.py:104` `get_exe_dir()/"data"` 改走分层
- [x] 3.13 全量 grep `get_exe_dir\(\)\s*/\s*"data"` 与 `get_exe_dir\(\)\s*/\s*"output"` 确认无残留直拼点

## 4. dev 模式路径覆盖

- [x] 4.1 在 app_paths 三层根函数中支持 `LV_TOOLKIT_DATA_DIR` 环境变量: dev 模式下覆盖 data 层根到项目 `data/`，frozen 模式忽略
- [x] 4.2 文档化该环境变量到 `CLAUDE.md` 开发环境章节

## 5. 路径层测试与启动验证

- [x] 5.1 重写 `tests/test_app_paths.py`: 覆盖三层路径(config roaming / data local / output Documents)、frozen 与 dev 模式、`LV_TOOLKIT_DATA_DIR` 覆盖、`get_exe_dir` 语义
- [x] 5.2 新增 headless 路径一致性测试: 无 QCoreApplication 下 `get_config_path`/`get_db_path` 返回带 appname 隔离路径
- [x] 5.3 启动验证: `.venv/Scripts/python -c "from toolkit.app import _build_context; c=_build_context(); print('paths ok')"` 无头路径通过
- [x] 5.4 启动验证: `python -m toolkit.app` GUI 启动通过(可无头则无头，否则人工确认)
- [x] 5.5 运行 `python -m pytest tests/test_app_paths.py tests/test_config_manager.py -v` 全绿

## 6. output 目录可配置

- [x] 6.1 `toolkit_config.json` 默认配置增 `output_dir` 字段(空表示用默认 Documents)
- [x] 6.2 `get_output_dir()` 优先读 config `output_dir`，空则回退 `get_user_output_dir()` 默认
- [x] 6.3 设置面板(`toolkit/gui/`)增 output 目录选择控件(QLineEdit + Browse 按钮)，保存写 config
- [x] 6.4 确保 output_dir 变更经 `config_changed` 信号同步(ConfigManager 须接入 FileConfigService 或等价信号机制，参照 [config-sync-rules.md](.claude/rules/config-sync-rules.md))
- [x] 6.5 测试: 改 output_dir 后 `get_output_dir()` 返回新路径，无需重启

## 7. 便携数据迁移助手

- [x] 7.1 新建 `toolkit/core/portable_migration.py`: `PortableMigrator` 类，含 `is_migration_needed()`(检测无标记)、`validate_source(dir)`(校验含 `data/`)、`migrate(src, on_progress)`(按映射复制)
- [x] 7.2 实现映射规则: config→roaming、db→local/db、backup→local/backup、logs→跳过、output/trace→output/trace、output/trace_report→output/trace_report; 目标已存在且更新则不覆盖
- [x] 7.3 实现 `config/.migrated_from_portable` 标记写入(时间戳 + 源路径)与读取
- [x] 7.4 实现迁移失败非致命: 部分复制保留 + 错误日志 + 可重试
- [x] 7.5 新建 `toolkit/gui/portable_migration_dialog.py`: 继承 `ToolkitDialog`，含目录选择、文件清单预览、Migrate/Skip 按钮，遵循 [ui-style-guide.md](.claude/rules/ui-style-guide.md) 与 [string-extraction-gate.md](.claude/rules/string-extraction-gate.md)
- [x] 7.6 GUI 启动流程(`run_gui()`)在主窗口显示前调用 `is_migration_needed()`，需要则弹迁移对话框
- [x] 7.7 新增 `tests/test_portable_migration.py`: 覆盖各映射规则、标记读写、跳过、部分失败重试、源校验

## 8. Velopack 运行时集成

- [x] 8.1 在 `toolkit/app.py` 的 `main()` 最前(stdio 修复之后、`setup_logging` 之前)植入 `velopack.App().run()` 钩子
- [x] 8.2 MCP server 模式(`mcp-serve`)绕过更新应用钩子，避免中断 stdio 会话
- [x] 8.3 GUI 模式主窗口显示后后台调 `velopack.UpdateManager` 检查更新(GitHub Releases feed)，有更新非阻塞通知
- [x] 8.4 更新检查失败仅 debug 日志，不中断启动
- [x] 8.5 抽离更新源 URL/feed 到配置，默认指向 GitHub Releases

## 9. 构建流程对接 vpk pack

- [x] 9.1 `scripts/build.py`: PyInstaller 产出目录从 `dist/Toolkit_<ts>` 规整到 `dist/publish/`(onedir 标准布局)
- [x] 9.2 `build.py` 新增 `pack_velopack(version)` 函数: 调 `vpk pack --packId LVGameToolkit --packVersion <ver> --packDir dist/publish --mainExe Toolkit.exe`
- [x] 9.3 `build.py` 主流程: PyInstaller → vpk pack → 产 Setup.exe + delta 包; 保留 `--no-package` 兼容(只构建不打包)
- [x] 9.4 移除/降级原 zip 打包路径为可选(过渡期保留 `--zip` 标志)
- [x] 9.5 vpk CLI 可用性检测: 构建前检查 `vpk` 是否安装，未安装则提示 `dotnet tool install -g vpk`
- [x] 9.6 代码签名可选: 环境变量有签名凭证则传 vpk 签名参数，无则警告并继续

## 10. 文档与收尾

- [x] 10.1 更新 `CLAUDE.md` 分发章节: 便携→安装版、vpk pack 流程、`LV_TOOLKIT_DATA_DIR` 说明
- [x] 10.2 新增 `docs/architecture/` 路径与分发架构文档(三层路径 + Velopack 更新流)
- [x] 10.3 更新 `docs/PROGRESS.md` 近期工作记录本次改造
- [x] 10.4 更新 `README.md` 安装/更新说明(Setup.exe + 应用内自动更新)
- [x] 10.5 全量 `python -m pytest` 通过(主项目 + 模块测试)
- [x] 10.6 `ruff check .` 无新增违规
- [ ] 10.7 首个版本 GitHub Releases feed 配置 + 端到端更新验证(本地 feed 或私有 repo)
