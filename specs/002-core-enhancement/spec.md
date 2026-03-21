# Feature Specification: 核心框架增强（迁移支撑）

**Feature Branch**: `002-core-enhancement`
**Created**: 2026-03-21
**Status**: Implemented
**Input**: 旧项目迁移需求 — 增强 `toolkit/core/` 和 `toolkit/sdk/` 的共享基础设施，为 device_disguise 和 game_perf 模块移植提供必要的底层 API

## 目录

- [User Scenarios & Testing](#user-scenarios--testing-mandatory)
  - [User Story 1 - ADB 高级操作支撑模块业务](#user-story-1---adb-高级操作支撑模块业务-priority-p1)
  - [User Story 2 - 设备状态模型支撑伪装检测](#user-story-2---设备状态模型支撑伪装检测-priority-p1)
  - [User Story 3 - 文件传输操作支撑配置推送](#user-story-3---文件传输操作支撑配置推送-priority-p1)
  - [Edge Cases](#edge-cases)
- [Clarifications](#clarifications)
- [Requirements](#requirements-mandatory)
- [Key Entities](#key-entities)
- [Success Criteria](#success-criteria-mandatory)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - ADB 高级操作支撑模块业务 (Priority: P1)

作为模块开发者，我需要通过 `AdbManager` 执行 root、remount、reboot 等高级 ADB 操作，以支撑设备伪装（修改 build.prop）和配置推送（push XML 文件）等业务场景。当前 `AdbManager` 仅支持基础的设备发现和属性读取，缺少写操作和设备控制能力。

**Why this priority**: 两个业务模块（device_disguise、game_perf）的核心业务流都依赖 ADB 高级操作，缺少这些 API 模块无法实现。

**Independent Test**: 运行 `pytest tests/test_adb_manager.py -v` 全部通过。

**Acceptance Scenarios**:

1. **Given** AdbManager 已初始化, **When** 调用 `root(serial)`, **Then** 执行 `adb -s <serial> root` 并返回输出
2. **Given** AdbManager 已初始化, **When** 调用 `remount(serial)`, **Then** 执行 `adb -s <serial> remount` 并返回输出
3. **Given** AdbManager 已初始化, **When** 调用 `reboot(serial)`, **Then** 执行 `adb -s <serial> reboot` 命令
4. **Given** 设备已重启, **When** 调用 `wait_for_device(serial)`, **Then** 阻塞直到设备恢复 `device` 状态
5. **Given** AdbManager 已初始化, **When** 调用 `shell(serial, command)`, **Then** 在设备上执行 shell 命令并返回输出

---

### User Story 2 - 设备状态模型支撑伪装检测 (Priority: P1)

作为模块开发者，我需要一个共享的 `DeviceState` 数据模型来描述设备的当前属性与原始属性，以便判断设备是否处于伪装状态。这个模型需要在 `toolkit/sdk/models.py` 中定义，供 device_disguise 模块和首页状态卡片使用。

**Why this priority**: 伪装状态检测是 device_disguise 的核心逻辑，也影响 GUI 首页的设备状态显示。

**Independent Test**: 构造 DeviceState 实例，验证 `is_disguised` 属性的判断逻辑正确。

**Acceptance Scenarios**:

1. **Given** DeviceState 的 current 属性与 original 属性相同, **When** 访问 `is_disguised`, **Then** 返回 False
2. **Given** DeviceState 的 current_brand 与 original_brand 不同, **When** 访问 `is_disguised`, **Then** 返回 True
3. **Given** DeviceState 的 is_connected 为 False, **When** 访问 `is_disguised`, **Then** 返回 False

---

### User Story 3 - 文件传输操作支撑配置推送 (Priority: P1)

作为模块开发者，我需要通过 `AdbManager` 进行设备文件的推送和拉取操作，以支撑 build.prop 修改（device_disguise）和 gameperfconfig.xml 推送（game_perf）。

**Why this priority**: 文件传输是两个模块的共同需求，属于核心共享能力。

**Independent Test**: 运行 `pytest tests/test_adb_manager.py -v` 中文件传输相关测试全部通过。

**Acceptance Scenarios**:

1. **Given** AdbManager 已初始化, **When** 调用 `push(serial, local_path, remote_path)`, **Then** 将本地文件推送到设备指定路径
2. **Given** AdbManager 已初始化, **When** 调用 `pull(serial, remote_path, local_path)`, **Then** 将设备文件拉取到本地指定路径
3. **Given** 本地文件不存在, **When** 调用 `push(serial, invalid_path, remote)`, **Then** 抛出 `AdbError` 异常

---

### Edge Cases

- 当设备未 root 时，`root()` 应抛出明确的 `AdbError` 并包含 "root 权限" 相关提示
- 当 `remount` 失败时（例如非 userdebug 版本），应抛出 `AdbError` 并包含 remount 失败信息
- 当 `wait_for_device` 超时时，应抛出 `AdbError` 而非无限等待
- 当指定 serial 的设备不存在时，所有操作应抛出 `AdbError`
- 当 `push` 的源文件不存在时，应在调用 adb 前先检查并抛出异常
- `DeviceState` 的 `is_disguised` 仅在三个字段（brand/manufacturer/model）中任一不同时返回 True

## Clarifications

暂无澄清问题。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `AdbManager` MUST 新增 `root(serial)` 方法，执行 `adb -s <serial> root`
- **FR-002**: `AdbManager` MUST 新增 `remount(serial)` 方法，执行 `adb -s <serial> remount`
- **FR-003**: `AdbManager` MUST 新增 `push(serial, local_path, remote_path)` 方法，执行文件推送
- **FR-004**: `AdbManager` MUST 新增 `pull(serial, remote_path, local_path)` 方法，执行文件拉取
- **FR-005**: `AdbManager` MUST 新增 `reboot(serial)` 方法，执行设备重启
- **FR-006**: `AdbManager` MUST 新增 `wait_for_device(serial, timeout)` 方法，阻塞等待设备恢复
- **FR-007**: `AdbManager` MUST 新增 `shell(serial, command)` 方法，执行设备 shell 命令
- **FR-008**: 所有 `AdbManager` 新增方法 MUST 通过 `-s serial` 参数指定目标设备
- **FR-009**: `push()` MUST 在调用 adb 前检查本地文件是否存在，不存在则抛出 `AdbError`
- **FR-010**: `wait_for_device()` MUST 支持超时参数，超时后抛出 `AdbError`
- **FR-011**: `toolkit/sdk/models.py` MUST 新增 `DeviceState` Pydantic 模型，包含 current/original 属性和 `is_disguised` 计算属性
- **FR-012**: `DeviceState.is_disguised` MUST 在设备未连接时返回 False

### Key Entities

- **AdbManager**: 核心 ADB 命令封装，位于 `toolkit/core/adb_manager.py`
- **DeviceState**: 设备伪装状态模型，位于 `toolkit/sdk/models.py`
- **AdbError / DeviceNotFoundError**: 异常体系，位于 `toolkit/sdk/exceptions.py`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: AdbManager 新增方法（root/remount/push/pull/reboot/wait_for_device/shell）全部有单元测试覆盖，使用 mock 模拟 subprocess，全部通过
- **SC-002**: DeviceState 模型的 `is_disguised` 逻辑有测试覆盖（connected/disconnected、匹配/不匹配），全部通过
- **SC-003**: 所有新增方法均通过 `-s serial` 指定目标设备，不存在硬编码单设备假设
- **SC-004**: 新增代码不破坏现有 83 项测试（全部通过）
