# Feature Specification: AdbManager 智能操作增强

**Feature Branch**: `adb-enhancement`
**Created**: 2026-03-21
**Status**: Implemented
**Input**: device_disguise 模块验收中发现 ADB 操作需要框架级增强支持

## 目录

- [User Scenarios & Testing](#user-scenarios--testing-mandatory)
  - [US1 - 智能 remount](#user-story-1---智能-remount-priority-p1)
  - [US2 - 安全 root](#user-story-2---安全-root-priority-p1)
  - [US3 - 完整输出捕获](#user-story-3---完整输出捕获-priority-p1)
  - [Edge Cases](#edge-cases)
- [Clarifications](#clarifications)
- [Requirements](#requirements-mandatory)
- [Key Entities](#key-entities)
- [Success Criteria](#success-criteria-mandatory)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 智能 remount (Priority: P1)

作为模块开发者，我调用 `adb.remount(serial)` 时，如果设备需要重启后再次 remount（如首次启用 overlayfs），AdbManager 应自动处理整个流程（reboot → wait → re-root → re-remount），让我无需在每个模块中重复实现此逻辑。

**Why this priority**: remount 是修改设备系统分区的前提条件，多个模块（device_disguise、game_perf 等）都需要此能力。

**Acceptance Scenarios**:

1. **Given** 设备 remount 成功（无需重启），**When** 调用 `remount(serial)`，**Then** 直接返回成功
2. **Given** 设备 remount 输出包含 "reboot" 提示（stdout 或 stderr），**When** 调用 `remount(serial, on_progress=cb)`，**Then** 自动 reboot → wait_for_device → wait_boot_completed → root → remount，全程通过回调通知进度
3. **Given** 设备 remount 两次均失败（如 verity 未关闭），**When** 调用 `remount(serial)`，**Then** 抛出明确异常，提示用户执行 `adb disable-verity`

---

### User Story 2 - 安全 root (Priority: P1)

作为模块开发者，我调用 `adb.root(serial)` 时，AdbManager 应自动等待 adbd 重启完成（root 操作会断开 USB 连接），确保后续 ADB 命令可以正常执行。

**Acceptance Scenarios**:

1. **Given** 设备支持 root，**When** 调用 `root(serial)`，**Then** 执行 root 后等待设备恢复可用
2. **Given** 设备不支持 root（user build），**When** 调用 `root(serial)`，**Then** 抛出明确异常，提示使用 userdebug/eng 版本

---

### User Story 3 - 完整输出捕获 (Priority: P1)

作为模块开发者，我需要 `run_cmd` 同时返回 stdout 和 stderr，以便准确判断 ADB 命令的执行结果（如 remount 的重启提示可能在 stderr 中）。

**Acceptance Scenarios**:

1. **Given** ADB 命令 stdout 和 stderr 均有输出，**When** 调用 `run_cmd_full(args)`，**Then** 返回包含 stdout 和 stderr 的结构化结果
2. **Given** ADB 命令返回非零退出码，**When** 调用 `run_cmd_full(args)`，**Then** 返回结果而非直接抛异常（由调用方决定处理方式）

---

### Edge Cases

- 当设备在 root 后 adbd 重启期间调用 remount，应等待而非立即失败
- 当 remount 需要重启时，重启后第二次 remount 也需要重启（罕见场景），应给出明确提示而非无限循环
- 当 root 已经是 root 状态时（"adbd is already running as root"），不应再等待
- 当 `adb remount` 输出同时包含 stdout 和 stderr 内容时，两者都应被检查
- **stdout/stderr 可能为 None**：`subprocess.run` 在特定情况下可能返回 `None`，所有字符串拼接处 MUST 使用 `or ""` 保护

## Clarifications

### Session 2026-03-21

- Q: `smart_remount` 是替代现有 `remount` 还是新增？ → A: 直接替代。现有 `remount` 功能被 `smart_remount` 完全覆盖（无需重启时行为一致），移除旧 `remount`，新方法命名为 `remount`（增加 `on_progress` 可选参数）。
- Q: `run_cmd` 返回类型？ → A: 保持 `run_cmd` 不变（向后兼容），新增 `_run_cmd_raw()` 返回 `NamedTuple(stdout, stderr, returncode)`。`run_cmd` 内部调用 `_run_cmd_raw`。`smart_remount` 使用 `_run_cmd_raw` 检查 stdout+stderr。
- Q: 进度回调签名？ → A: `Callable[[str], None] | None`，与 device_disguise 模块一致。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `run_cmd` 方法 MUST 支持返回完整输出（stdout + stderr），向后兼容现有调用
- **FR-002**: `root(serial)` 方法 MUST 在执行 root 后等待设备恢复可用（wait_for_device），检测 "already running as root" 时跳过等待
- **FR-003**: AdbManager MUST 提供 `remount(serial, on_progress)` 方法（替代旧 remount），自动处理 remount → 检测重启提示 → reboot → wait → re-root → re-remount 的完整流程
- **FR-004**: `remount` MUST 同时检查 stdout 和 stderr 中的重启提示关键词
- **FR-005**: `remount` MUST 通过 `on_progress` 回调通知调用方每个步骤的进度
- **FR-006**: `remount` 在第二次 remount 仍然失败时 MUST 抛出 `AdbError`，提示用户执行 `adb disable-verity`
- **FR-007**: `root` 在设备不支持 root 时 MUST 抛出 `AdbError`，提示使用 userdebug/eng 版本
- **FR-008**: 所有增强 MUST 向后兼容，现有调用 `run_cmd`/`root`/`remount` 的代码无需修改

### Key Entities

- **AdbManager**: `toolkit/core/adb_manager.py` — 增强目标
- **AdbCmdResult**: 新增的命令执行结果数据类（stdout, stderr, returncode）
- **AdbError**: 现有异常类，保持不变

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `remount` 方法有完整单元测试覆盖：成功、需重启、两次失败 3 种场景（实际 6 个测试用例）
- **SC-002**: `root` 增强有测试覆盖：成功+等待、已 root、不支持 root 3 种场景
- **SC-003**: `run_cmd` 向后兼容，主项目 113 个测试全部通过
- **SC-004**: device_disguise 模块移除自行实现的 remount 逻辑，改用 `smart_remount`
