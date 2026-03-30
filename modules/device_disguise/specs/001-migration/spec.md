# Feature Specification: 设备伪装模块移植

**Feature Branch**: `device-disguise-migration`
**Created**: 2026-03-21
**Status**: Implemented
**Input**: 旧项目 `_archived_source/core/device_service.py` + `_archived_source/core/profile_manager.py` + `_archived_source/ui/` 的迁移

## 目录

- [User Scenarios & Testing](#user-scenarios--testing-mandatory)
  - [US1 - 设备信息伪装](#user-story-1---设备信息伪装-priority-p1)
  - [US2 - 设备信息还原](#user-story-2---设备信息还原-priority-p1)
  - [US3 - 设备档案管理](#user-story-3---设备档案管理-priority-p2)
  - [US4 - 档案导入](#user-story-4---档案导入-priority-p3)
  - [Edge Cases](#edge-cases)
- [Clarifications](#clarifications)
- [Requirements](#requirements-mandatory)
- [Key Entities](#key-entities)
- [Success Criteria](#success-criteria-mandatory)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 设备信息伪装 (Priority: P1)

作为测试人员，我在 GUI 中输入目标品牌、厂商、型号，点击「开始伪装」按钮后，工具自动修改已 root 设备的 `/odm/etc/build.prop` 并重启设备，完成后显示伪装结果验证。

**Why this priority**: 伪装功能是本模块的核心价值，所有其他功能都围绕它展开。

**Independent Test**: 在 GUI 中输入目标信息 → 点击伪装 → 设备重启后验证 `getprop` 属性已修改。

**Acceptance Scenarios**:

1. **Given** 设备已连接且已 root, **When** 输入 brand/manufacturer/model 并点击伪装, **Then** 工具依次执行 root→remount→setenforce→pull→modify→push→reboot→verify，显示进度和结果
2. **Given** 伪装过程中, **When** 每个步骤完成, **Then** 日志区域实时显示进度信息
3. **Given** 伪装完成后, **When** 设备重启并验证通过, **Then** 显示成功提示，设备状态更新为「已伪装」
4. **Given** 伪装前目标组合不在档案库中, **When** 点击伪装, **Then** 弹出保存对话框，用户可选择保存或跳过

---

### User Story 2 - 设备信息还原 (Priority: P1)

作为测试人员，我点击「还原」按钮后，工具自动将设备的 ODM 属性恢复为 vendor 原始值，流程与伪装相同但写入的是原始值。

**Acceptance Scenarios**:

1. **Given** 设备处于伪装状态, **When** 点击还原, **Then** 工具读取 vendor 属性写入 build.prop 并重启验证
2. **Given** 设备未处于伪装状态, **When** 点击还原, **Then** 提示当前未伪装，无需还原

---

### User Story 3 - 设备档案管理 (Priority: P2)

作为测试人员，我可以管理设备档案库：查看所有已保存的设备配置、通过输入联想快速选取档案、新增/编辑/删除档案记录。

**交互设计说明**：
- 输入框默认不填充数据库中的值，以置灰 placeholder 显示属性获取方式（如"通过 'ro.product.odm.brand' 属性获取"）
- 不提供联动填充功能（选中联想建议不自动填充其他字段）
- "选择档案"弹窗中每条记录提供"选择"、"编辑"、"删除"三个操作按钮

**Acceptance Scenarios**:

1. **Given** 档案库中有记录, **When** 在输入框输入部分文字, **Then** 显示匹配的联想建议
2. **Given** 选中一个联想建议, **When** 确认选择, **Then** 仅填充当前字段，不联动其他字段
3. **Given** 档案库中无该组合, **When** 点击保存, **Then** 弹出对话框输入备注后保存
4. **Given** 点击"选择档案", **When** 弹窗显示所有档案, **Then** 每条记录旁有"选择"、"编辑"、"删除"按钮
5. **Given** 在档案弹窗中点击"编辑", **When** 修改档案信息并确认, **Then** 档案更新成功，弹窗列表刷新
6. **Given** 在档案弹窗中点击"删除", **When** 确认删除, **Then** 档案从库中移除，弹窗列表刷新

---

### User Story 4 - 档案导入 (Priority: P3)

作为测试人员，我可以从 JSON 文件批量导入设备档案，已存在的记录自动跳过。

**Acceptance Scenarios**:

1. **Given** 选择一个有效的 JSON 文件, **When** 执行导入, **Then** 显示导入结果（N 条导入，M 条跳过）

---

### Edge Cases

- 当设备未 root 时，`root` 操作应抛出明确错误提示
- 当 `remount` 失败时（非 userdebug），应提示用户检查设备版本
- 当设备在伪装/还原过程中断开，应保留当前操作的进度日志
- 当 build.prop 中缺少目标属性键时，应在文件末尾追加
- 当设备重启后验证失败时（属性值与预期不一致），应显示期望值和实际值的对比
- 当档案 JSON 文件格式错误时，导入应报错而非静默失败
- 当输入框内容为空时，伪装/还原按钮应禁用

## Clarifications

### Session 2026-03-21

- Q: 伪装操作是否需要在子线程中执行？ → A: 服务层（service.py）保持同步调用，不依赖 QThread。GUI 层在调用服务时自行将耗时操作放入 QThread。理由：Constitution V 要求 service.py 不含 GUI 相关代码。
- Q: 设备档案存储方式？ → A: 继续使用 JSON 文件存储（`modules/device_disguise/data/device_profiles.json`），与旧版保持一致。后续如有需要可迁移到 SQLite。
- Q: 伪装历史记录是否持久化？ → A: 本期不实现。预留数据模型，后续迭代时添加。
- Q: GUI 布局设计方向？ → A: 全新设计匹配主框架 VS Code 风格，作为 Tab 嵌入主窗口。
- Q: CLI 命令格式？ → A: `device status`（查看设备状态和伪装信息）、`device disguise --brand --manufacturer --model`（执行伪装）、`device reset`（还原）、`device profile list/add/import`（档案管理）。

### Session 2026-03-30

- Q: 输入栏是否预填数据库中的值？ → A: 不预填。以置灰 placeholder 文字显示属性获取方式（如"通过 'ro.product.odm.brand' 属性获取"），用户需手动输入或从档案选择。
- Q: 联动填充功能是否保留？ → A: 取消。选中联想建议时仅填充当前字段，不自动联动填充其他字段（brand/manufacturer/model）。
- Q: 选择档案弹窗是否支持编辑和删除？ → A: 支持。弹窗中每条档案记录显示"选择"、"编辑"、"删除"三个操作按钮。编辑通过独立的 `_ProfileEditDialog` 弹窗实现，支持修改 brand、manufacturer、model、notes 字段。

### Session 2026-03-30（device_info 迭代，取代旧路径说明）

- Q: 设备档案 JSON 的文件名与存放路径？ → A: 以 [002-device-info-json/spec.md](../002-device-info-json/spec.md) 为准：正式文件名为 `device_info.json`；开发环境为 `modules/device_disguise/data/device_info.json`；PyInstaller 打包后为 `<exe 同级目录>/data/device_info.json`。原 Clarification 中 `device_profiles.json` 仅作为迁移来源；GUI 增加「导入配置」与档案变更一并写回该文件。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 服务层 MUST 实现 `get_device_state(serial)` 方法，返回 `DeviceState` 模型
- **FR-002**: 服务层 MUST 实现 `disguise(serial, brand, manufacturer, model)` 方法，执行完整的伪装流程（root→remount→setenforce→pull→modify→push→reboot→verify）
- **FR-003**: 服务层 MUST 实现 `reset(serial)` 方法，将 ODM 属性还原为 vendor 值
- **FR-004**: 伪装/还原操作 MUST 通过进度回调通知 GUI/CLI 每个步骤的完成状态
- **FR-005**: 服务层 MUST 实现设备档案的 CRUD 操作（增删改查）
- **FR-006**: 服务层 MUST 实现档案导入功能，支持从 JSON 文件批量导入
- **FR-007**: 服务层 MUST 在修改 build.prop 时，对已有的键进行替换，对缺失的键在文件末尾追加
- **FR-008**: GUI MUST 提供伪装/还原操作界面，包含输入区、操作按钮、进度日志
- **FR-009**: GUI MUST 提供输入联想功能，根据档案库内容提供建议
- **FR-010**: GUI MUST 在伪装前检查目标组合是否已存档，未存档时弹出保存对话框
- **FR-011**: CLI MUST 提供 `device disguise`、`device reset`、`device status`、`device profile list/add/import` 命令
- **FR-012**: 所有 ADB 操作 MUST 通过 `toolkit/core/adb_manager.py` 的 API 调用，MUST NOT 直接调用 subprocess

### Key Entities

- **DeviceDisguiseService**: 模块核心服务，位于 `modules/device_disguise/src/service.py`
- **DeviceState**: 共享设备状态模型，位于 `toolkit/sdk/models.py`（Phase 0 已实现）
- **DeviceProfile**: 设备档案数据模型
- **DeviceDisguiseTab**: GUI 页面，位于 `modules/device_disguise/src/gui_tab.py`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 伪装/还原服务层方法均有单元测试覆盖（mock ADB），全部通过
- **SC-002**: 档案 CRUD 和导入功能有完整测试覆盖
- **SC-003**: GUI 可正常启动，伪装界面所有组件可交互（手动验证）
- **SC-004**: CLI 命令可正常执行并返回预期输出
- **SC-005**: 模块不直接依赖 `toolkit/core/` 内部实现，仅通过 `toolkit/sdk/` 和钩子机制交互
