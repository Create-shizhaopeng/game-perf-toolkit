# 设备伪装工具 — AI 开发规则

## 目录

- [模块概述](#模块概述)
- [继承的全局规则](#继承的全局规则)
- [模块边界约束](#模块边界约束)
- [模块特有规则](#模块特有规则)
- [测试要求](#测试要求)

## 模块概述

修改 Android 设备的 ODM 属性（品牌/厂商/型号），支持配置文件管理和批量操作。

## 继承的全局规则

> 本模块遵循项目全局编码规范（详见项目根 `.cursor/rules/`）
> - Python 3.12+，类型注解覆盖所有公共方法
> - 数据模型：公共 API 用 Pydantic，模块内部用 dataclass
> - 中文注释和文档字符串
> - CLI 输出 SHOULD 支持 JSON 格式（渐进落地）
> - 插件 context 键名使用 `dd_` 前缀（如 `dd_service`、`dd_adb`）
> - 开发前 MUST 阅读 `scripts/doc/development-pitfalls.md`

## 模块边界约束

- ✅ 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`
- ❌ 禁止修改：`toolkit/`、其他模块目录、项目根配置文件
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`
- ❌ 禁止导入：`toolkit.core` 内部实现、其他模块的 `src/`

## 模块特有规则

- ADB 操作通过 `context["dd_adb"]` 调用（使用框架级 AdbManager）
- 设备属性修改前必须先记录原始值
- 档案管理通过 `context["dd_profile_mgr"]`（JSON 持久化）
- 设备状态变更通过 EventBus 发布 `device_disguise.state_changed` 事件

## 测试要求

- `service.py` 中每个公共方法至少一个测试用例
- 测试数据放在 `fixtures/` 目录
