# Feature Specification: Toolkit — Push Policy 选项卡

**Feature Name**: 策略配置推送功能（Push Policy Tab）
**Short Name**: push-policy-tab
**Created**: 2026-03-12
**Status**: Draft

---

## 目录

- [Overview](#overview)
- [Clarifications](#clarifications)
- [User Scenarios & Testing](#user-scenarios--testing)
- [Functional Requirements](#functional-requirements)
- [Success Criteria](#success-criteria)
- [Key Entities](#key-entities)
- [UI Layout](#ui-layout)
- [Assumptions](#assumptions)
- [Scope Boundaries](#scope-boundaries)

---

## Overview

在现有 **ModifyModelNameTool**（设备型号伪装工具）基础上，将工具升级为 **Toolkit**（多功能工具箱），通过选项卡（Tab）组织不同功能。新增 **push policy** 选项卡，用于将本地策略配置文件（如 `gameperfconfig.xml`）推送到 Android 设备，替换设备上的原始策略。

### Problem Statement

测试人员在调试游戏性能策略时，需要频繁将修改后的 `gameperfconfig.xml` 推送到设备。当前依赖命令行脚本（`push_gameperf.py`）操作，缺乏可视化反馈，且格式错误不易排查。需要一个 GUI 化的推送工具，支持文件选择/搜索/拖拽导入，并在推送前做格式校验，将错误信息以醒目方式呈现。

### Target Users

- 游戏性能优化测试工程师
- OEM 厂商游戏策略调试人员

---

## Clarifications

### Session 2026-03-12

- Q: Reset 时 version 如何处理？ → A: Reset 时也需要将恢复的配置文件 version 修改为「当前设备 version + 1」后再推送到设备，与 Push 行为一致。
- Q: 用户选择的文件名可能前后有其他字符，如何认定并推送到设备？ → A: 只要文件名中包含完整的 "gameperfconfig" 且扩展名为 .xml，即视为有效配置文件（如 `gameperfconfig（11）.xml`、`aaagameperfconfig.xml`）。推送到设备时一律使用目标路径 `/system/etc/gameperfconfig.xml`，即本地文件无论原名如何，在设备上均以 `gameperfconfig.xml` 存在。

---

## User Scenarios & Testing

### Scenario 1: 工具更名与选项卡切换

**前置条件**: 工具已启动

1. 用户看到窗口标题为 **Toolkit**（而非原来的 ModifyModelNameTool）
2. 标题栏下方出现两个选项卡：**ModifyModelNameTool**、**push policy**
3. 默认停留在 ModifyModelNameTool 选项卡（原有功能不变）
4. 用户点击 **push policy** 选项卡，切换到策略推送界面

**验收标准**:

- 窗口标题显示"Toolkit"
- 两个选项卡可自由切换，切换后各自内容独立
- 原有 ModifyModelNameTool 功能完全不受影响

### Scenario 2: 选择配置文件（搜索 + 拖拽）

**前置条件**: 已切换到 push policy 选项卡

1. 第二行区域显示为"配置文件"，提供文件路径输入框
2. 用户可以通过以下方式选择配置文件：
   - **手动输入/粘贴**：在路径输入框中直接输入或粘贴文件路径
   - **浏览按钮**：点击浏览按钮，弹出文件选择对话框（过滤 `*.xml` 文件）
   - **拖拽导入**：将 XML 文件从文件管理器拖拽到该区域，自动填充路径
3. 文件选择后，输入框显示完整文件路径
4. **有效配置文件**：文件名只要包含完整子串 `gameperfconfig` 且扩展名为 `.xml` 即视为有效（例如 `gameperfconfig（11）.xml`、`aaagameperfconfig.xml`）。推送时无论本地文件名为何，在设备上均以 `gameperfconfig.xml` 存在（目标路径 `/system/etc/gameperfconfig.xml`）。

**验收标准**:

- 三种文件选择方式均可正常使用
- 拖拽仅接受 `.xml` 文件，且文件名包含 `gameperfconfig` 方视为有效策略配置；其他格式或名称提示不支持
- 选择后路径正确显示在输入框中
- 推送后设备上文件名为 `gameperfconfig.xml`

### Scenario 3: Push 策略配置文件

**前置条件**: 设备已连接，配置文件已选择

1. 用户点击 **Start**
2. 工具校验是否已选择配置文件，未选择则提示
3. 工具执行 XML 格式校验：
   - 校验通过：日志区域显示"✓ XML 格式检查通过"
   - 校验失败：日志区域以**醒目颜色**显示错误位置及其前后几行内容，帮助用户定位问题
4. 格式校验通过后，执行推送流程：
   - 读取设备当前配置文件的 version
   - 将本地文件 version 修改为 设备 version + 1
   - adb root → adb remount → setenforce 0
   - push 配置文件到设备
   - 重启设备
   - 等待设备启动完成，校验 version
5. 日志区域实时显示每个步骤的执行状态
6. 进度条反映当前执行进度

**异常流程**:

- XML 格式错误：在日志中高亮显示出错行及前后上下文（±3行），终止流程
- adb root 失败：日志打印错误提示
- 设备未连接：按钮置灰不可点击

**验收标准**:

- XML 格式错误信息以红色/高亮方式显示，与普通日志明显区分
- 格式错误附带出错位置的前后 3 行配置内容作为上下文
- 推送成功后 version 校验通过
- 整个流程在日志中有完整记录

### Scenario 4: 清除已选配置文件

1. 用户点击 **Clear**
2. 文件路径输入框被清空

**验收标准**:

- 仅清除文件路径，不影响设备状态
- 不清除日志区域内容

### Scenario 5: 重置为 Push 前的策略

**前置条件**: 之前已执行过 push 操作

1. 用户点击 **Reset**
2. 工具读取设备当前 version，将备份文件 version 修改为「设备 version + 1」
3. 将修改后的备份推送到设备，恢复策略内容
4. 日志区域显示重置过程
5. 完成后校验 version 与预期一致

**异常流程**:

- 没有备份文件（首次使用未执行过 push）：提示"无可用备份，无法重置"

**验收标准**:

- 重置后设备上的配置文件内容为 push 前的备份内容，version 为「重置前设备 version + 1」
- version 校验恢复正确

### Scenario 6: 格式错误日志高亮

**前置条件**: 用户选择了一个有格式错误的 XML 文件并点击 Start

1. 日志区域正常日志使用默认颜色
2. 格式错误信息使用**醒目的红色/橙色**显示
3. 错误行附带其前后各 3 行的配置内容，以便定位
4. 有问题的配置内容行使用特殊背景色或不同颜色，区别于正常的上下文行

**验收标准**:

- 错误信息颜色与正常日志明显不同
- 前后上下文帮助用户快速定位错误位置
- 出错的具体行有额外视觉标识（如红色背景或加粗）

---

## Functional Requirements

### FR-1: 工具更名为 Toolkit

- 窗口标题由 "ModifyModelNameTool" 改为 "Toolkit"
- `QApplication.setApplicationName` 改为 "Toolkit"

### FR-2: 选项卡架构

- 在标题栏下方添加 `QTabWidget`，包含两个选项卡：
  - Tab 0: "ModifyModelNameTool"（原有全部功能，迁移到 Tab 页内）
  - Tab 1: "push policy"（新增功能）
- 两个 Tab 共享同一个设备连接监听（DeviceMonitor）
- Tab 0 的功能行为与现有完全一致

### FR-3: 配置文件选择

- push policy Tab 的第二区域改为「配置文件」选择
- 提供文件路径输入框（QLineEdit）+ 浏览按钮（QPushButton）
- 支持拖拽 XML 文件到该区域自动填充路径
- **有效文件判定**：文件名须包含完整子串 `gameperfconfig` 且扩展名为 `.xml`（如 `gameperfconfig（11）.xml`、`aaagameperfconfig.xml`）。不满足则提示不支持
- 拖拽与浏览仅接受符合上述条件的 .xml 文件
- 推送时无论本地文件名为何，设备上目标路径固定为 `/system/etc/gameperfconfig.xml`，即设备上始终为 `gameperfconfig.xml`

### FR-4: 策略推送执行

- 集成 `push_gameperf.py` 的核心逻辑到 `PushPolicyService`
- 推送流程：
  1. 校验文件路径是否有效，且文件名包含 `gameperfconfig` 且为 .xml
  2. XML 格式校验（使用 `xml.etree.ElementTree.parse`）
  3. 读取设备当前 version
  4. 将本地文件 version 修改为 设备 version + 1（在临时副本上修改，不改变用户原文件）
  5. adb root / remount / setenforce 0
  6. 备份设备当前配置文件到本地
  7. 将修改后的本地文件 push 到设备 `/system/etc/gameperfconfig.xml`（设备上文件名固定为 `gameperfconfig.xml`）
  8. adb reboot
  9. 等待设备启动完成
  10. 校验 version
- 每个步骤通过信号通知 UI 更新日志和进度

### FR-5: 策略重置

- 重置时读取设备当前 version，将备份文件的 version 修改为「设备 version + 1」后推回设备（与 Push 时的 version 规则一致）
- 备份文件存储在工具数据目录中
- 无备份时给出明确提示

### FR-6: 格式错误高亮显示

- XML 格式校验失败时：
  - 解析错误位置（行号、列号）
  - 读取源文件中出错行及其前后各 3 行
  - 在日志区域中：
    - 上下文行使用正常颜色
    - 出错行使用**红色加粗**显示
    - 错误描述信息使用**红色**显示
  - 与普通进度日志的颜色明显不同

### FR-7: 设备状态共享

- push policy Tab 复用 Section 1（当前设备信息），布局与原有一致
- 设备连接/断开事件同步到两个 Tab
- 设备未连接时两个 Tab 的操作按钮均置灰

---

## Success Criteria

| 编号 | 标准                       | 度量                                       |
| ---- | -------------------------- | ------------------------------------------ |
| SC-1 | 选项卡切换流畅             | 切换无明显延迟（< 200ms）                  |
| SC-2 | 文件拖拽导入               | 拖入 XML 文件后 500ms 内路径显示           |
| SC-3 | 推送端到端完成             | 整个流程 < 3 分钟（含设备重启）            |
| SC-4 | 格式错误定位准确           | 错误行号与实际不符的偏差 = 0               |
| SC-5 | 错误信息视觉区分度         | 错误行与普通日志颜色/样式明显不同          |
| SC-6 | 重置成功率                 | 100%（有备份时）                           |
| SC-7 | 原有功能无回归             | ModifyModelNameTool Tab 全部场景通过       |

---

## Key Entities

### PushConfig（推送配置状态）

| 字段            | 说明                                         |
| --------------- | -------------------------------------------- |
| config_file     | 本地配置文件的完整路径                       |
| remote_path     | 设备上配置文件路径（/system/etc/gameperfconfig.xml） |
| device_version  | 设备当前 version                             |
| target_version  | 目标 version（设备 version + 1）             |
| backup_path     | push 前设备配置文件的本地备份路径            |
| push_time       | 上次 push 时间戳                             |

---

## UI Layout

### 整体结构

```
┌───────────────────────────────────────────────┐
│ Toolkit                                   ⚙  │  ← 标题栏（更名）
├──────────────────┬────────────────────────────┤
│ModifyModelNameTool│  push policy              │  ← 选项卡
├──────────────────┴────────────────────────────┤
│ [当前设备信息]                                │  ← Section 1（两个 Tab 共享布局）
│  brand: Lenovo  manufacturer: LENOVO  model:  │
│  ● 设备已连接 · HA2DKTYN                     │
├───────────────────────────────────────────────┤
│ [配置文件] (push policy Tab)  支持拖拽「文件名包含 gameperfconfig」的 .xml 到此区域  │  ← 标题与提醒同一行
│  文件路径: [________________________] [浏览]  │
│ （与「伪装设备信息」块区域高度一致）          │
├───────────────────────────────────────────────┤
│ [执行日志]                                    │  ← Section 3
│  ✓ setenforce 0 成功                          │
│  拉取 build.prop...                           │
│  ✗ XML 格式错误（第 15 行）                   │  ← 红色高亮
│    13| <GamePolicy name="xxx">                │  ← 上下文行
│  → 14| <BindCore>                             │  ← 错误行（红色加粗）
│    15| </GamePolicy>                          │  ← 上下文行
│  ─────────────── 100%                         │
├───────────────────────────────────────────────┤
│  [▶ Start]      [✕ Clear]      [↺ Reset]      │  ← Section 4
└───────────────────────────────────────────────┘
```

### 布局约定

- **配置文件** 标题与提醒文字「支持拖拽「文件名包含 gameperfconfig」的 .xml 到此区域」同一行显示，提醒文字在标题右侧。
- **伪装设备信息**（ModifyModelNameTool 选项卡）与 **配置文件**（push policy 选项卡）两块区域高度一致（统一最小高度），保证两个 Tab 视觉一致。

### 按钮语义（push policy Tab）

- **Start**: 开始 push 策略（先校验格式，再推送）
- **Clear**: 清除已选取的配置文件路径
- **Reset**: 重置为 push 前的策略（从备份恢复）

---

## Assumptions

1. 配置文件推送目标路径固定为 `/system/etc/gameperfconfig.xml`
2. 设备需支持 root 和 remount
3. 备份文件存储在工具数据目录（`data/` 下），设备 Serial 作为子目录
4. XML 校验使用 Python 标准库 `xml.etree.ElementTree`
5. push policy Tab 中的 "当前设备信息" 区域布局与 ModifyModelNameTool Tab 完全一致
6. 两个 Tab 共享 `AdbManager` 和 `DeviceMonitor`

---

## Scope Boundaries

### In Scope

- 工具更名为 Toolkit
- 选项卡架构（2 个 Tab）
- 配置文件选择（手动输入 / 浏览 / 拖拽）
- XML 格式校验与错误高亮
- 策略推送全流程（version 自增 + push + 重启 + 校验）
- 推送前备份与重置恢复
- 两个 Tab 共享设备连接状态

### Out of Scope

- 多设备同时推送
- 推送 `gameperfconfig.xml` 以外的配置文件类型
- 配置文件内容编辑（仅推送）
- 推送历史记录管理
