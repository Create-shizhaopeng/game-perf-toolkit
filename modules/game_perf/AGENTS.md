# 游戏性能配置 — AI 开发规则

> 继承项目根 Constitution（`.specify/memory/constitution.md`），以下为模块级补充约束。

## 目录

- [模块概述](#模块概述)
- [继承的全局规则](#继承的全局规则)
- [模块边界约束](#模块边界约束)
- [模块特有规则](#模块特有规则)
- [Spec 索引](#spec-索引)
- [测试要求](#测试要求)

## 模块概述

解析、编辑和推送游戏性能配置文件（gameperfconfig.xml）到 Android 设备。

## 继承的全局规则

> 本模块遵循项目全局编码规范（详见项目根 `.cursor/rules/`）
> - Python 3.12+，类型注解覆盖所有公共方法
> - 数据模型：XML 内部用 dataclass，公共 API 用 Pydantic
> - 中文注释和文档字符串
> - CLI 输出 SHOULD 支持 JSON 格式（渐进落地）
> - 插件 context 键名使用 `gp_` 前缀（如 `gp_service`、`gp_adb`、`gp_data_dir`）
> - 开发前 MUST 阅读 `docs/experience/development-pitfalls.md`

## 模块边界约束

- ✅ 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`
- ❌ 禁止修改：`toolkit/`、其他模块目录、项目根配置文件
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`
- ❌ 禁止导入：`toolkit.core` 内部实现（plugin_manager、db_manager 等）、其他模块的 `src/`

## 模块特有规则

- XML 解析统一使用 `lxml.etree`
- 推送前必须先验证 XML 合法性
- 推送前必须先备份设备上的原始配置
- 推送记录采用 JSON + DB 双写（JSON 供 Agent 分析，`context["db_manager"]` 供查询索引）
- ADB 操作统一使用框架级 `AdbManager`（smart root/remount）
- 后台 ADB/推送操作 MUST 使用 `QThread` + `pyqtSignal` 与 GUI 线程通信
- service 层纯同步，MUST NOT 包含 PyQt6 代码
- GUI Tab 使用上下分栏布局，风格与主模块一致

## Spec 索引

当前无活跃 Spec。完整索引见 [specs/INDEX.md](specs/INDEX.md)。

## 测试要求

- XML 解析和验证逻辑必须有测试覆盖
- 测试用样本 XML 文件放在 `fixtures/` 目录
