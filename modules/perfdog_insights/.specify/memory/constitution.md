# PerfDog 分析模块 Constitution

## 目录

- [继承关系](#继承关系)
- [模块边界约束](#模块边界约束)
- [技术约束](#技术约束)
- [开发规范](#开发规范)

## 继承关系

本模块 Constitution 继承自项目根 Constitution（`../../../../.specify/memory/constitution.md`），所有根 Constitution 中定义的原则、技术栈约束和开发流程均 MUST 适用于本模块。

以下仅补充模块级约束，不重复根级内容。

## 模块边界约束

- ✅ 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`、`assets/`
- ❌ 禁止修改：`toolkit/`、其他模块目录、项目根配置文件（除非跨模块契约评审）
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`、`toolkit.core.perfdog`、`toolkit.core.joint_assessment`（解析与联合分析公共 API）
- ❌ 禁止导入：`toolkit.core` 内部实现（如 `plugin_manager`）、其他模块的 `src/`
- 插件 context 键名 MUST 使用 **`pdi_` 前缀**（如 `pdi_service`）；读取游戏性能策略快照时使用 **`gp_joint_policy_snapshot`**（由 `game_perf` 写入，不得改名）

## 技术约束

- 业务编排集中在 **`PerfdogInsightsService`**（`service.py`）；**不得**在 `service.py` 中引入 PyQt6 / Typer
- 耗时解析与联合分析在 **`QThread`** 中执行，经 Service 调用 `toolkit.core.perfdog` / `joint_assessment`
- 跨 GUI/CLI 的结构化类型优先在 **`models.py`** 声明或再导出；报告主体类型来自 `toolkit.core.perfdog.report_types` 时须在 `models.py` 文档说明

## 开发规范

- 遵循项目根 `doc/experience/development-pitfalls.md`（context 前缀、QThread、ADB 输出等）
- 功能规格、计划与任务清单的**权威源**为仓库根 `specs/004-perfdog-import-insights/`；本模块下 `specs/004-perfdog-import-insights/` 为**入口索引**（链接到根目录），避免双份正文漂移
- 合并前：`pytest modules/perfdog_insights/tests/`，并执行 `ruff check`（若环境已安装）

**Version**: 1.0.0 | **Last Updated**: 2026-03-22
