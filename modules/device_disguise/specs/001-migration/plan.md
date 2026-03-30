# Implementation Plan: 设备伪装模块移植

## 目录

- [概述](#概述)
- [技术上下文](#技术上下文)
- [Constitution 检查](#constitution-检查)
- [影响范围](#影响范围)
- [实现阶段](#实现阶段)

## 概述

将旧项目 `_archived_source/core/device_service.py` + `profile_manager.py` 的设备伪装功能迁移到新架构的 `modules/device_disguise/` 模块中。核心变化：
- 服务层与 GUI 完全解耦（旧代码 `DeviceService` 继承 `QThread`，新架构 service.py 纯 Python）
- GUI 层使用 `QThread` 包装服务调用，保持 UI 响应
- 通过 `AdbManager` API 而非直接调用 subprocess
- 档案管理保留 JSON 存储，使用 Pydantic 模型替代 dataclass

## 技术上下文

| 依赖 | 用途 |
|------|------|
| `toolkit.core.adb_manager.AdbManager` | 所有 ADB 操作的入口 |
| `toolkit.sdk.models.DeviceState` | 设备伪装状态模型（Phase 0 已实现） |
| `toolkit.gui.base_tab.BaseTab` | GUI Tab 基类 |
| `toolkit.sdk.base_plugin.BasePlugin` | 插件注册基类 |
| `PyQt6` | GUI 组件（仅限 gui_tab.py） |
| `typer` + `rich` | CLI 命令 |
| `pydantic` | 数据模型验证 |

## Constitution 检查

| 原则 | 合规性 |
|------|--------|
| I. 核心稳定 | ✅ 不修改 toolkit/core/ |
| II. 模块对称 | ✅ 提供 GUI + CLI + Agent Tools |
| III. JSON/Pydantic Schema | ✅ DeviceProfile 使用 Pydantic |
| IV. 测试可逆 | ✅ 服务层方法纯同步，易于 mock |
| V. 表现分离 | ✅ service.py 不含 QThread/GUI 代码 |
| VI. 渐进实现 | ✅ 历史记录预留，本期不实现 |
| VII. 约定优于配置 | ✅ 遵循模块目录约定 |

## 影响范围

### 新增文件

| 文件 | 说明 |
|------|------|
| `modules/device_disguise/src/service.py` | 服务层（重写） |
| `modules/device_disguise/src/models.py` | 模块内 DeviceProfile 模型 |
| `modules/device_disguise/src/gui_tab.py` | GUI 页面（重写） |
| `modules/device_disguise/src/cli_commands.py` | CLI 命令（重写） |
| `modules/device_disguise/src/plugin.py` | 插件入口（更新） |
| `modules/device_disguise/tests/test_service.py` | 服务层测试 |
| `modules/device_disguise/tests/test_models.py` | 模型测试 |
| `modules/device_disguise/tests/test_cli.py` | CLI 测试 |
| `modules/device_disguise/data/device_info.json` | 设备档案库（演进见 [002-device-info-json](../002-device-info-json/spec.md)） |

### 修改文件

| 文件 | 变更 |
|------|------|
| `modules/device_disguise/manifest.json` | 按需微调 |

### 不修改的文件

- `toolkit/core/*` — 所有核心服务
- `toolkit/sdk/models.py` — DeviceState 已就绪

## 实现阶段

### Phase 1: 数据模型 (T001-T002)
定义 `DeviceProfile` Pydantic 模型和 `ProfileManager` 服务。

### Phase 2: 服务层核心 (T003-T007)
实现 `DeviceDisguiseService`：`get_device_state`、`disguise`、`reset`、`_modify_build_prop`、`_wait_boot_completed`。服务层方法全部同步，接收 `serial` 参数和进度回调函数。

### Phase 3: CLI 命令 (T008-T010)
实现 `device status`、`device disguise`、`device reset`、`device profile` 子命令。

### Phase 4: GUI 页面 (T011-T016)
实现 `DeviceDisguiseTab`（方案 A 左右分栏）：设备状态区、输入区（带联想）、操作按钮、日志区、档案弹窗。

### Phase 5: 插件集成 (T017-T018)
更新 `plugin.py`，注册服务、传递 context、注册 agent tools。

### Phase 6: 测试 (T019-T023)
服务层单元测试、模型测试、CLI 测试，全部使用 mock ADB。
