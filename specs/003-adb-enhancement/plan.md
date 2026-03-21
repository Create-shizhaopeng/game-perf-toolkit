# Implementation Plan: AdbManager 智能操作增强

## 目录

- [概述](#概述)
- [技术上下文](#技术上下文)
- [Constitution 检查](#constitution-检查)
- [影响范围](#影响范围)

## 概述

增强 `toolkit/core/adb_manager.py`，提供智能 remount（自动处理重启流程）、安全 root（等待 adbd 恢复）、完整输出捕获（`_run_cmd_raw`）。

## 技术上下文

| 依赖 | 说明 |
|------|------|
| `subprocess` | ADB 命令执行 |
| `toolkit.sdk.exceptions.AdbError` | 异常体系 |
| `typing.NamedTuple` | `AdbCmdResult` 返回类型 |

## Constitution 检查

| 原则 | 合规性 |
|------|--------|
| I. Plugin-First | ✅ 增强框架共享能力，非模块特定 |
| IV. 测试可逆 | ✅ 所有方法可 mock，有完整测试 |
| VIII. 向后兼容 | ✅ `run_cmd` 行为不变，`remount` 新增可选参数 |

## 影响范围

### 修改文件

| 文件 | 变更 |
|------|------|
| `toolkit/core/adb_manager.py` | 新增 `_run_cmd_raw`、`AdbCmdResult`；增强 `root`、重写 `remount` |
| `tests/test_adb_manager.py` | 新增 smart_remount 测试、root 增强测试 |

### 不修改的文件

- `toolkit/sdk/` — SDK 模型无变化
- `toolkit/gui/` — 不涉及 GUI
- `modules/` — 后续 device_disguise 适配作为单独任务
