# Perfetto 解析分析模块 Constitution

## 目录

- [继承关系](#继承关系)
- [模块边界约束](#模块边界约束)
- [技术约束](#技术约束)
- [开发规范](#开发规范)

## 继承关系

本模块 Constitution 继承自项目根 Constitution（`../../.specify/memory/constitution.md`），所有根 Constitution 中定义的原则、技术栈约束和开发流程均 MUST 适用于本模块。

以下仅补充模块级约束，不重复根级内容。

## 模块边界约束

- ✅ 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`
- ❌ 禁止修改：`toolkit/`、其他模块目录、项目根配置文件
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`
- ❌ 禁止导入：`toolkit.core` 内部实现（plugin_manager、db_manager 等）、其他模块的 `src/`
- 插件 context 键名 MUST 使用 `pa_` 前缀（如 `pa_service`、`pa_adb`、`pa_data_dir`）
  - `pa_` 取自 **p**erfetto **a**nalysis 的缩写
  - 不可使用 `pe_`（已被 `perfetto_capture` 模块占用），否则会导致 context 键覆盖冲突（详见 `doc/experience/development-pitfalls.md` P01）
  - 每个模块 MUST 使用全局唯一的 2~3 字母前缀作为命名空间

## 技术约束

- 分析引擎核心逻辑位于 `src/engine/` 子包，从源项目 `perfettoAnalysisByPython` 迁移而来
- 依赖 `perfetto` Python 包（TraceProcessor），MUST 在虚拟环境中安装
- 模块独立 SQLite 数据库（`data/perfetto_analysis.db`）存储详细分析数据
- 共享 DB 索引表 `pa_analysis_tasks` 含 process_name、mode、dimensions 扩展字段
- 报告输出目录：开发环境 `data/output/trace_report/`，打包后 `<exe_dir>/output/trace_report/`
- 工作线程写入共享 DB MUST 使用独立 `sqlite3.connect()` 连接（线程安全）
- 维度多选控件 MUST NOT 使用 QComboBox 自定义 popup（Windows COM 线程兼容问题）

## 开发规范

- 遵循项目根 `doc/experience/development-pitfalls.md` 中列出的踩坑指南
- 后台耗时操作 MUST 使用 `QThread` + `pyqtSignal` 与 GUI 线程通信
- service 层纯同步，MUST NOT 包含 PyQt6 代码
- GUI 刷新历史表 MUST 使用 `QTimer.singleShot()` 延迟执行，避免 use-after-free 竞态
- GUI 左侧面板 MUST 使用 `setFixedWidth()` 保持固定宽度

**Version**: 1.1.0 | **Last Updated**: 2026-03-23
