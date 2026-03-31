# 设备伪装模块 — 知识入口

## 目录

- [模块简介](#模块简介)
- [关键约束速查](#关键约束速查)
- [相关踩坑](#相关踩坑)
- [规格文档](#规格文档)

## 模块简介

修改 Android 设备的 ODM 属性（品牌/厂商/型号），支持配置文件管理和批量操作。

- **前缀**：`dd_`
- **类别**：device
- **Agent 工具**：已注册
- **详细开发规则**：见 `../AGENTS.md`

## 关键约束速查

- 设备属性修改前必须先记录原始值
- 档案管理通过 `context["dd_profile_mgr"]`（JSON 持久化）
- 通过 EventBus 发布 `device_disguise.state_changed` 事件

## 相关踩坑

| 编号 | 说明 | 关联 |
|------|------|------|
| P01 | context 键名冲突 — 必须使用 `dd_` 前缀 | 直接相关 |
| P02 | ADB 命令输出可能为 None | ADB 操作相关 |
| P05 | QThread 信号安全 | GUI 线程通信 |

## 规格文档

- `specs/001-migration/` — 迁移规格
- `specs/002-device-info-json/` — 设备信息 JSON 化
