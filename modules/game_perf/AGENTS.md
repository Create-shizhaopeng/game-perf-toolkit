# 游戏性能配置 — AI 开发规则

## 目录

- [模块概述](#模块概述)
- [继承的全局规则](#继承的全局规则)
- [模块边界约束](#模块边界约束)
- [模块特有规则](#模块特有规则)
- [测试要求](#测试要求)

## 模块概述

解析、编辑和推送游戏性能配置文件（gameperfconfig.xml）到 Android 设备。

## 继承的全局规则

> 本模块遵循项目全局编码规范（详见项目根 `.cursor/rules/`）
> - Python 3.12+，类型注解覆盖所有公共方法
> - 数据模型使用 dataclass（模块内部数据传递），公共 API 数据结构使用 Pydantic
> - 中文注释和文档字符串
> - CLI 输出 SHOULD 支持 JSON 格式（渐进落地）
> - 插件 context 键名使用 `gp_` 前缀（如 `gp_service`、`gp_adb`）

## 模块边界约束

- ✅ 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`
- ❌ 禁止修改：`toolkit/`、其他模块目录、项目根配置文件
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`
- ❌ 禁止导入：`toolkit.core` 内部实现、其他模块的 `src/`

## 模块特有规则

- XML 解析统一使用 `lxml.etree`
- 推送前必须先验证 XML 合法性
- 推送前必须先备份设备上的原始配置
- 备份和推送记录通过 `context["db_manager"]` 持久化

## 测试要求

- XML 解析和验证逻辑必须有测试覆盖
- 测试用样本 XML 文件放在 `fixtures/` 目录
