# Perfetto 解析分析 — AI 开发规则

## 目录

- [模块概述](#模块概述)
- [继承的全局规则](#继承的全局规则)
- [模块边界约束](#模块边界约束)
- [模块特有规则](#模块特有规则)
- [GUI 开发注意事项](#gui-开发注意事项)
- [数据库相关规则](#数据库相关规则)
- [测试要求](#测试要求)

## 模块概述

Perfetto trace 丢帧解析与多维度卡顿归因分析模块。基于 Android 丢帧 SOP 执行 Phase 1（丢帧定位）和 Phase 2（结构化数据拆解），支持 9 个分析维度（CPU/Thread/Binder/IO/GC/GPU/SF/Input/Lock）+ 全 Trace 整体分析（Summary），生成 Markdown 报告和 JSON 数据。

## 继承的全局规则

> 本模块遵循项目全局编码规范（详见项目根 `.cursor/rules/`）
> - Python 3.12+，类型注解覆盖所有公共方法
> - 数据模型：公共 API 用 Pydantic，模块内部用 dataclass
> - 中文注释和文档字符串
> - CLI 输出 SHOULD 支持 JSON 格式（渐进落地）
> - 插件 context 键名使用 `pa_` 前缀（如 `pa_service`、`pa_adb`、`pa_data_dir`）。`pa_` 取自 **p**erfetto **a**nalysis 缩写，不可使用 `pe_`（已被 perfetto_capture 占用，详见 P01 踩坑记录）
> - 开发前 MUST 阅读 `scripts/doc/development-pitfalls.md`

## 模块边界约束

- 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`
- 禁止修改：`toolkit/`、其他模块目录、项目根配置文件
- 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`
- 禁止导入：`toolkit.core` 内部实现、其他模块的 `src/`

## 模块特有规则

- 分析引擎核心逻辑放在 `src/engine/` 子包中，从源项目 `perfettoAnalysisByPython` 迁移而来
- `src/engine/` 内部使用相对导入（`from . import parser`），外层通过 `from .engine import ...` 访问
- `service.py` 封装 `engine/` 的能力，提供 `on_progress` 回调，MUST NOT 直接依赖 GUI 框架
- 模块使用独立 SQLite 数据库（`data/perfetto_analysis.db`），通过 `src/engine/storage.py` 管理
- 共享 DB 中创建 `pa_analysis_tasks` 索引表用于跨模块发现（含 process_name、mode、dimensions 字段）
- 依赖 `perfetto` Python 包（TraceProcessor），需在项目虚拟环境中安装
- 事件联动：监听 `perfetto_capture.trace_ready`，通过配置 `auto_analyze_on_capture` 控制是否自动分析
- 报告文件存放目录：
  - 开发环境：`data/output/trace_report/<trace_stem>/`（相对项目根）
  - 打包后（PyInstaller）：`<exe_dir>/output/trace_report/<trace_stem>/`
- Top N / Binder 阈值 / 调度延迟等参数在 `config.json` 中配置，不在 GUI 中暴露
- "重新生成报告"功能从 DB 已有数据生成 Markdown，不重新分析 trace
- 进程名未指定时自动从 trace 中检测并展示（纯包名，去掉 PID/SurfaceView 前缀）

## GUI 开发注意事项

- 左侧面板使用 `setFixedWidth(580px)`，不随窗口缩放
- 维度多选控件使用 QPushButton + _PersistentMenu（QMenu 子类），**不可使用 QComboBox 自定义 popup**（Windows 下会导致 COM 线程崩溃 `0x8001010d`）
- 删除/刷新历史表后 MUST 使用 `QTimer.singleShot(100ms)` 延迟刷新，避免 use-after-free 竞态
- 工作线程（_AnalysisWorker）中 MUST NOT 直接操作 UI 控件，通过 pyqtSignal 通信
- 按钮图标使用 `QStyle.StandardPixmap` 系统图标（跨平台兼容）

## 数据库相关规则

- 共享 DB 写入 MUST 使用独立 `sqlite3.connect()` 连接（工作线程安全）
- 主线程读取共享 DB 可使用 `db_manager.connection` 属性
- `_ensure_extra_columns()` 提供向后兼容的字段检测与动态添加
- 迁移脚本位于 `src/migrations/`，按序号命名（001, 002, 003...）
- 去重策略：`trace_path + mode` 组合唯一，重新分析时 DELETE+INSERT 覆盖
- 删除记录时检查同一 trace_path 是否还有其他模式记录，据此决定是否清理磁盘文件

## 测试要求

- `service.py` 中每个公共方法至少一个测试用例
- `engine/parser.py` 的核心解析逻辑需有单独测试
- 测试数据放在 `fixtures/` 目录
- 使用 `unittest.mock` 模拟 TraceProcessor 查询结果
- 测试不得依赖真实 trace 文件（除 fixtures 中的测试数据外）
