# PerfDog 分析 — AI 开发规则

## 目录

- [模块概述](#模块概述)
- [继承的全局规则](#继承的全局规则)
- [模块边界约束](#模块边界约束)
- [模块特有规则](#模块特有规则)
- [测试要求](#测试要求)

## 模块概述

离线导入 PerfDog **`.xlsx/.xlsm`**，生成会话摘要与**异常洞察**（**本期规格**不要求「可执行建议」章节）；可选与 **游戏性能配置**（`game_perf` 写入的 `gp_joint_policy_snapshot`）做联合分析（联合侧**本期**亦以矛盾/异常结论为主，见根目录 `specs/004-perfdog-import-insights/spec.md`）。

## 继承的全局规则

> 本模块遵循项目全局编码规范（项目根 `.cursor/rules/`、[架构文档 §5.0](../../../doc/architecture/architecture-overview.md#50-代码规则总纲)）
>
> - Python 3.12+，公共 API 带类型注解
> - 业务在 **`service.py`**，**禁止**在 Service 中引入 PyQt6 / Typer
> - 插件 context 键名使用 **`pdi_` 前缀**（如 **`pdi_service`**）
> - 读取策略快照时使用 **`gp_joint_policy_snapshot`**（`game_perf` 写入，键名勿改）

## 模块边界约束

- ✅ 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`、`assets/`、本模块 `.specify/` / `.cursor/`（模块级 Speckit）
- ❌ 禁止修改：`toolkit/` 中与需求无关的文件、其他模块的 `src/`
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`、`toolkit.core.perfdog`、`toolkit.core.joint_assessment`
- ❌ 禁止导入：`toolkit.core` 内部实现（如 `plugin_manager`）、其他模块 `src/`

## 模块特有规则

- 解析与对比逻辑经 **`PerfdogInsightsService`** 调用 **`toolkit.core.perfdog`**，不在本模块复制 Data_v4 解析
- 耗时任务在 **`analysis_worker` / `joint_worker`**（`QThread`）中执行，**禁止**在工作线程直接操作控件
- 模块内 **`specs/004-perfdog-import-insights/`** 为指向仓库根 **`specs/004-perfdog-import-insights/`** 的索引；**正文以根目录为准**

## 测试要求

- Service 与可单测逻辑须有 **`modules/perfdog_insights/tests/`** 覆盖
- 脱敏样例可放在 **`fixtures/`**；与核心库共用的烟测仍见根目录 **`tests/test_perfdog_workbook.py`**
