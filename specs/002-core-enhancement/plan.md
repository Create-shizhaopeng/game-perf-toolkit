# Implementation Plan: 核心框架增强（迁移支撑）

**Branch**: `002-core-enhancement` | **Date**: 2026-03-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-core-enhancement/spec.md`

## 目录

- [Summary](#summary)
- [Technical Context](#technical-context)
- [Constitution Check](#constitution-check)
- [Project Structure](#project-structure)
- [Complexity Tracking](#complexity-tracking)

## Summary

为旧项目迁移提供底层 API 支撑，增强 `toolkit/core/adb_manager.py` 和 `toolkit/sdk/models.py`：
1. AdbManager 新增 7 个高级操作方法（root/remount/push/pull/reboot/wait_for_device/shell），统一 `-s serial` 多设备支持
2. SDK models 新增 DeviceState Pydantic 模型，提供伪装状态检测（`is_disguised`）

变更范围严格限定在 `toolkit/core/` 和 `toolkit/sdk/`，不涉及任何业务模块代码。

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: subprocess（标准库），Pydantic 2.0+
**Testing**: pytest + unittest.mock
**Affected Files**:
- `toolkit/core/adb_manager.py`（新增方法）
- `toolkit/sdk/models.py`（新增 DeviceState）
- `tests/test_adb_manager.py`（扩展测试）
- `tests/test_models.py`（新建）

**Reference**: `_archived_source/core/adb_manager.py`（旧实现参考）、`_archived_source/core/device_service.py`（DeviceState 参考）

## Constitution Check

| 原则 | 状态 | 说明 |
|------|------|------|
| Plugin-First | ✅ | 不涉及业务模块，仅增强核心框架 |
| Three-Surface Unity | ✅ | AdbManager 无 GUI/CLI 依赖，纯逻辑层 |
| Agent-Driven Design | ✅ | ADB 操作通过 ServiceRegistry 可被 Agent 调用 |
| Dependency Inversion | ✅ | 模块将通过 SDK 使用 ADB 能力，核心不依赖模块 |
| Presentation Separation | ✅ | AdbManager 不含 GUI/CLI 代码 |
| Open-Closed | ✅ | 本特性是框架维护（非模块开发），新增方法不修改已有接口；Constitution VI 约束的是「模块不得改 core/sdk」，框架自身增强不在此约束范围 |
| Spec-Driven Development | ✅ | 当前正在按 speckit 工作流执行 |

## Project Structure

### Source Code (affected files)

```text
toolkit/
├── core/
│   └── adb_manager.py      # 新增 root/remount/push/pull/reboot/wait_for_device/shell
└── sdk/
    └── models.py            # 新增 DeviceState

tests/
├── test_adb_manager.py      # 扩展：新增方法的 mock 测试
└── test_models.py           # 新建：DeviceState 逻辑测试
```

## Complexity Tracking

无违规项 — 变更范围小（2 个源文件 + 2 个测试文件），不引入新依赖，不修改已有接口。
