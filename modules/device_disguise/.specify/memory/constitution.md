# 设备伪装模块 Constitution

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
- 插件 context 键名 MUST 使用 `dd_` 前缀（如 `dd_service`、`dd_adb`、`dd_profile_mgr`）

## 技术约束

- ADB 操作统一使用框架级 `AdbManager`（smart root/remount），模块内 MUST NOT 自行实现 remount 逻辑
- 设备状态变更（伪装/还原）MUST 通过 `EventBus` 发布 `device_disguise.state_changed` 事件
- 档案管理使用 `ProfileManager`（JSON 持久化），不涉及数据库

## 开发规范

- 遵循项目根 `scripts/doc/development-pitfalls.md` 中列出的踩坑指南
- 后台 ADB 操作 MUST 使用 `QThread` + `pyqtSignal` 与 GUI 线程通信
- service 层纯同步，MUST NOT 包含 PyQt6 代码

**Version**: 1.0.0 | **Last Updated**: 2026-03-21
