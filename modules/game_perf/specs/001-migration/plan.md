# Implementation Plan: 游戏性能配置模块迁移

## 目录

- [概述](#概述)
- [技术上下文](#技术上下文)
- [Constitution 检查](#constitution-检查)
- [影响范围](#影响范围)
- [实施阶段](#实施阶段)

## 概述

将 `_archived_source/` 中的游戏性能配置功能迁移至 `modules/game_perf/` 插件架构，实现 GUI/CLI/Agent 三端统一访问。核心重构点：service 层纯同步、解耦 GUI 依赖、推送逻辑使用框架级 AdbManager。

## 技术上下文

| 依赖 | 说明 |
|------|------|
| `lxml` | XML 解析和编辑（gameperfconfig.xml） |
| `toolkit.core.adb_manager` | 框架级 ADB 操作（smart remount, root, push） |
| `toolkit.core.db_manager` | 推送记录数据库存储 |
| `toolkit.sdk.exceptions` | 统一异常体系 |
| `dataclasses` | 数据模型（FreqRow、PushRecord 等） |

## Constitution 检查

| 原则 | 合规性 |
|------|--------|
| I. Plugin-First | ✅ 模块通过 pluggy 注册，不修改主框架 |
| III. 三端统一 | ✅ service 层纯同步，GUI/CLI/Agent 均可调用 |
| IV. 测试可逆 | ✅ service 层可 mock AdbManager 测试 |
| V. 子模块隔离 | ✅ 不修改 toolkit/ 目录下任何文件 |

## 影响范围

### 新增/修改文件（modules/game_perf/ 目录下）

| 文件 | 变更 |
|------|------|
| `src/parser.py` | 新增：XML 解析引擎（纯 lxml，返回 dict/dataclass） |
| `src/models.py` | 新增：FreqRow、PushRecord 等 dataclass 数据模型 |
| `src/service.py` | 重写：推送/还原/版本管理（纯同步，使用 AdbManager） |
| `src/cli_commands.py` | 重写：perf push/reset/info CLI 命令 |
| `src/gui_tab.py` | 重写：上下分栏布局，频率表+策略面板+日志 |
| `src/plugin.py` | 更新：注册 service、CLI、GUI |
| `src/migrations/` | 新增：perf_push_history 表迁移脚本 |
| `tests/test_parser.py` | 新增：解析引擎单元测试 |
| `tests/test_service.py` | 新增：推送/还原服务单元测试 |
| `tests/test_cli.py` | 新增：CLI 命令测试 |

### 不修改的文件

- `toolkit/` — 主框架代码不变
- `modules/device_disguise/` — 其他模块不受影响

## 实施阶段

1. **Phase 1**: 数据模型 + XML 解析引擎（parser.py + models.py）
2. **Phase 2**: 推送/还原服务层（service.py + migrations/）
3. **Phase 3**: CLI 命令（cli_commands.py）
4. **Phase 4**: GUI Tab 页（gui_tab.py）
5. **Phase 5**: 插件集成（plugin.py）
6. **Phase 6**: 测试 + 回归验证

## 规格补充：连接后自动载入设备配置（US6 / FR-013～018）

**目标**：设备连接可用后，自动从 `/system/etc/gameperfconfig.xml` 拉取并载入 GUI，失败可诊断、成功标明「来自设备」、有未保存本地编辑时不静默覆盖。详见同目录 [spec.md](./spec.md) 中 User Story 6 与 Assumptions（US6）。

**实现要点（规划，不修改 `toolkit/`）**：

- `GamePerfService`（或等价层）增加「从设备读取配置到临时文件/内存」的同步能力，复用现有 `AdbManager` 拉取语义；GUI 用 `QThread` 包装。
- `GamePerfTab` 监听设备连接/选中变化与 Tab 可见性，按 spec 触发自动拉取；与 `models.py` 中来源枚举配合更新状态栏或配置文件行旁标识。
- 与现有「配置文件路径」、`Push` 前写回逻辑对齐，避免双路径语义冲突。

任务拆解见 [tasks.md](./tasks.md) **Phase 7**。
