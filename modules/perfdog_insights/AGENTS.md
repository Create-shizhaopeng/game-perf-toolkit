# PerfDog 分析 — AI 开发规则

## 目录

- [模块概述](#模块概述)
- [继承的全局规则](#继承的全局规则)
- [模块边界约束](#模块边界约束)
- [模块特有规则](#模块特有规则)
- [测试要求](#测试要求)

## 模块概述

离线导入 PerfDog **`.xlsx/.xlsm`**，生成会话摘要、**异常洞察**（含**异常时间段**与 **Data_v4 异常关联采样切片**），并对其余时段作概括说明（**本期规格**不要求「可执行建议」章节）；见根目录 `specs/004-perfdog-import-insights/spec.md`。

## 继承的全局规则

> 本模块遵循项目全局编码规范（项目根 `.cursor/rules/`、[架构文档 §5.0](../../../doc/architecture/architecture-overview.md#50-代码规则总纲)）
>
> - Python 3.12+，公共 API 带类型注解
> - 业务在 **`service.py`**，**禁止**在 Service 中引入 PyQt6 / Typer
> - 插件 context 键名使用 **`pdi_` 前缀**（如 **`pdi_service`**）

## 模块边界约束

- ✅ 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`、`assets/`、本模块 `.specify/` / `.cursor/`（模块级 Speckit）
- ❌ 禁止修改：`toolkit/` 中与需求无关的文件、其他模块的 `src/`
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`、`toolkit.core.perfdog`
- ❌ 禁止导入：`toolkit.core` 内部实现（如 `plugin_manager`）、其他模块 `src/`

## 模块特有规则

- 解析与导出经 **`PerfdogInsightsService`** 调用 **`toolkit.core.perfdog`**，不在本模块复制 Data_v4 解析
- 耗时任务在 **`analysis_worker`**（`QThread`）中执行，**禁止**在工作线程直接操作控件
- 模块内 **`specs/004-perfdog-import-insights/`** 为指向仓库根 **`specs/004-perfdog-import-insights/`** 的索引；**正文以根目录为准**

## 测试要求

- Service 烟测见根目录 **`tests/test_perfdog_insights_service.py`**（`modules/.../tests` 易与 pytest 包名冲突，故放在顶层 `tests/`）
- 脱敏样例可放在 **`fixtures/`**；与核心库共用的烟测仍见根目录 **`tests/test_perfdog_workbook.py`**
