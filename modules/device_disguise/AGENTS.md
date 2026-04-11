# 设备伪装工具 — AI 开发规则

> 继承项目根 Constitution（`.specify/memory/constitution.md`），以下为模块级补充约束。

## 目录

- [模块概述](#模块概述)
- [继承的全局规则](#继承的全局规则)
- [模块边界约束](#模块边界约束)
- [模块特有规则](#模块特有规则)
- [Spec 索引](#spec-索引)
- [测试要求](#测试要求)

## 模块概述

修改 Android 设备的 ODM 属性（品牌/厂商/型号），支持配置文件管理和批量操作。

## 继承的全局规则

> 本模块遵循项目全局编码规范（详见项目根 `.cursor/rules/`）
> - Python 3.12+，类型注解覆盖所有公共方法
> - 数据模型：公共 API 用 Pydantic，模块内部用 dataclass
> - 中文注释和文档字符串
> - CLI 输出 SHOULD 支持 JSON 格式（渐进落地）
> - 插件 context 键名使用 `dd_` 前缀（如 `dd_service`、`dd_adb`、`dd_profile_mgr`）
> - 开发前 MUST 阅读 `doc/experience/development-pitfalls.md`

## 模块边界约束

- ✅ 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`
- ❌ 禁止修改：`toolkit/`、其他模块目录、项目根配置文件
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`
- ❌ 禁止导入：`toolkit.core` 内部实现（plugin_manager、db_manager 等）、其他模块的 `src/`

## 模块特有规则

- ADB 操作通过 `context["dd_adb"]` 调用（使用框架级 AdbManager），MUST NOT 自行实现 remount 逻辑
- 设备属性修改前必须先记录原始值
- 档案管理通过 `context["dd_profile_mgr"]`（JSON 持久化）
- 设备状态变更通过 EventBus 发布 `device_disguise.state_changed` 事件
- 后台 ADB 操作 MUST 使用 `QThread` + `pyqtSignal` 与 GUI 线程通信
- service 层纯同步，MUST NOT 包含 PyQt6 代码

## Spec 索引

当前无活跃 Spec。完整索引见 [specs/INDEX.md](specs/INDEX.md)。

## 测试要求

- `service.py` 中每个公共方法至少一个测试用例
- 测试数据放在 `fixtures/` 目录
