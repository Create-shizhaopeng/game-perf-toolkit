<!--
  id: ARCH-003
  title: 分发与路径架构
  type: design
  status: implemented
  created: 2026-09-01
  updated: 2026-09-01
  tags: [distribution, paths, velopack, installer]
-->

# 分发与路径架构

## 背景

Game Perf Toolkit 原以"便携绿色包"(zip 解压即用)分发，用户数据堆在 exe 同级 `data/`，覆盖升级易丢数据且无更新机制。本次改造为"安装包分发 + 增量更新 + 数据隔离"架构。

## 三层用户数据路径

基于 [platformdirs](https://pypi.org/project/platformdirs/) 按操作系统惯例分层（程序本体只读，用户数据 per-user 可写）：

| 层 | 位置 (Windows) | 内容 | 语义 |
|----|----------------|------|------|
| config | `%APPDATA%\Roaming\game-perf-toolkit\Game Perf Toolkit` | `*.json` 配置 | roaming，跟随用户漫游 |
| data | `%LOCALAPPDATA%\game-perf-toolkit\Game Perf Toolkit` | `db\`、`logs\`、`backup\`、`cache\` | local，机器绑定 |
| output | `Documents\Game Perf Toolkit`（可配置） | `trace\`、`trace_report\` | 用户产物，可见可备份 |

**关键约束**：MCP server 模式（`mcp-serve`）不创建 QCoreApplication，`QStandardPaths` 在此状态下无 appname 隔离，故选 platformdirs（纯 Python，GUI/headless 通用）。

**对外接口**：`toolkit/core/app_paths.py` 的 `get_config_path`/`get_db_path`/`get_output_dir`/`get_backup_path` 签名不变，内部走三层根。`get_exe_dir()` 语义收窄为只读程序资源根，不再写数据。

**dev 覆盖**：`LV_TOOLKIT_DATA_DIR` 环境变量在 dev 模式覆盖 data 层根到项目 `data/`，frozen 忽略。

## 安装与更新（Velopack）

[Velopack](https://velopack.io/)（Squirrel 继任者，PyInstaller `--onedir` 官方支持）一体化安装+更新：

- **构建**：`scripts/build.py` PyInstaller 产出 `dist/publish/` → `vpk pack` 产 `Setup.exe` + delta 更新包。
- **运行时钩子**：`toolkit/app.py` 的 `main()` 最前调 `velopack.App().run()`，应用待处理更新（可能重启进程）。MCP 模式绕过避免中断 stdio。
- **后台检查**：GUI 主窗口显示后 `UpdateManager.check_for_updates()` 后台检查 GitHub Releases feed，delta 下载，下次启动生效。
- **非 Velopack 环境**：`App().run()` 安全 no-op；`UpdateManager` 抛 RuntimeError 被 try 捕获仅 debug 日志。

## 便携版数据迁移

老便携版（zip）用户数据迁移到新三层路径：`toolkit/core/portable_migration.py` 的 `PortableMigrator` 按映射规则复制（config→roaming、db→local、output→Documents、logs 跳过），写 `.migrated_from_portable` 标记防重复。`toolkit/gui/portable_migration_dialog.py` 提供首启半自动迁移 UI（用户确认旧目录）。仅 frozen 安装版触发，dev 跳过。

## 相关

- Spec：`openspec/changes/installer-distribution-refactor/`
- 规则：[config-sync-rules.md](../../.claude/rules/config-sync-rules.md)、[code-quality-gate.md](../../.claude/rules/code-quality-gate.md)
