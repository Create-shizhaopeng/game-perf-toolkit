# Tasks: 核心框架增强（迁移支撑）

**Input**: Design documents from `specs/002-core-enhancement/`
**Prerequisites**: plan.md (required), spec.md (required), research.md

## 目录

- [Phase 1: ADB 高级操作](#phase-1-adb-高级操作)
- [Phase 2: 设备状态模型](#phase-2-设备状态模型)
- [Phase 3: 测试与验证](#phase-3-测试与验证)
- [FR ↔ Task Traceability](#fr--task-traceability)
- [Dependencies & Execution Order](#dependencies--execution-order)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: ADB 高级操作

**Purpose**: 为 AdbManager 新增高级设备操作方法

- [x] T001 [US1] 新增 `root(serial)` 方法 — `toolkit/core/adb_manager.py`
- [x] T002 [US1] 新增 `remount(serial)` 方法 — `toolkit/core/adb_manager.py`
- [x] T003 [US3] 新增 `push(serial, local_path, remote_path)` 方法（含本地文件检查）— `toolkit/core/adb_manager.py`
- [x] T004 [US3] 新增 `pull(serial, remote_path, local_path)` 方法 — `toolkit/core/adb_manager.py`
- [x] T005 [US1] 新增 `reboot(serial)` 方法 — `toolkit/core/adb_manager.py`
- [x] T006 [US1] 新增 `wait_for_device(serial, timeout)` 方法（轮询 get-state + 超时）— `toolkit/core/adb_manager.py`
- [x] T007 [US1] 新增 `shell(serial, command)` 方法 — `toolkit/core/adb_manager.py`

**Checkpoint**: AdbManager 所有新增方法实现完成

---

## Phase 2: 设备状态模型

**Purpose**: 新增共享 DeviceState 模型

- [x] T008 [US2] 新增 `DeviceState` Pydantic 模型到 `toolkit/sdk/models.py`，含 current/original 属性和 `is_disguised` 计算属性

**Checkpoint**: DeviceState 模型就位

---

## Phase 3: 测试与验证

**Purpose**: 为所有新增代码编写测试，确保不破坏现有功能

- [x] T009 [P] [US1/US3] 扩展 `tests/test_adb_manager.py`，为 root/remount/push/pull/reboot/wait_for_device/shell 编写 mock 测试；验证每个方法的 subprocess 调用均包含 `-s <serial>` 参数（SC-003）— 9 项新增测试
- [x] T010 [P] [US2] 新建 `tests/test_models.py`，测试 DeviceState 的 is_disguised 逻辑：覆盖 connected/disconnected 状态、brand/manufacturer/model 三字段各自不匹配的场景（SC-002）— 8 项测试
- [x] T011 [SC-004] 运行全部测试套件 — 100 项全部通过（原 83 + 新增 17）

**Checkpoint**: 全部测试通过，核心框架增强完成

---

## FR ↔ Task Traceability

| FR | 关联 Task | 说明 |
|----|-----------|------|
| FR-001 | T001 | root(serial) |
| FR-002 | T002 | remount(serial) |
| FR-003 | T003 | push(serial, local, remote) + 文件存在检查 |
| FR-004 | T004 | pull(serial, remote, local) |
| FR-005 | T005 | reboot(serial) |
| FR-006 | T006 | wait_for_device(serial, timeout) |
| FR-007 | T007 | shell(serial, command) |
| FR-008 | T001-T007 | 统一 -s serial 参数 |
| FR-009 | T003 | push 前检查本地文件 |
| FR-010 | T006 | wait_for_device 超时机制 |
| FR-011 | T008 | DeviceState Pydantic 模型 |
| FR-012 | T008, T010 | is_disguised 在未连接时返回 False |
| SC-004 | T011 | 全量测试回归，确保不破坏现有功能 |

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (ADB)**: No dependencies — 可立即开始
- **Phase 2 (Model)**: No dependencies — 可与 Phase 1 并行
- **Phase 3 (Tests)**: Depends on Phase 1 + Phase 2

### Parallel Opportunities

- Phase 1 和 Phase 2 可并行（修改不同文件）
- Phase 3 中 T009 和 T010 可并行（测试不同模块）
