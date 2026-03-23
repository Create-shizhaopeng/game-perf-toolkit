# Feature Specification: 游戏性能配置模块迁移

**Feature Branch**: `game-perf-migration`
**Created**: 2026-03-21
**Status**: Implemented（迁移）；**连接后自动载入设备配置** 见下方补充规格（规划中）
**Input**: `_archived_source/` 旧代码迁移至新插件架构  
**补充（2026-03-22）**: 连接上设备之后，自动读取 `/system/etc/gameperfconfig.xml`（仅列于本模块 `specs/001-migration/`，不单独建根目录规格目录）

## 目录

- [User Scenarios & Testing](#user-scenarios--testing-mandatory)
  - [US1 - XML 解析与浏览](#user-story-1---xml-解析与浏览-priority-p1)
  - [US2 - 频率配置编辑](#user-story-2---频率配置编辑-priority-p1)
  - [US3 - 策略配置推送](#user-story-3---策略配置推送-priority-p1)
  - [US4 - 配置还原](#user-story-4---配置还原-priority-p2)
  - [US5 - CLI 访问](#user-story-5---cli-访问-priority-p2)
  - [US6 - 连接后自动载入设备配置](#user-story-6---连接后自动载入设备配置-priority-p1-规划)
  - [Edge Cases](#edge-cases)
- [Clarifications](#clarifications)
- [Requirements](#requirements-mandatory)
- [Key Entities](#key-entities)
- [Success Criteria](#success-criteria-mandatory)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - XML 解析与浏览 (Priority: P1)

作为游戏性能测试工程师，我需要加载 `gameperfconfig.xml`，查看其中所有游戏的性能模式、温控策略（TempLevel）和频率配置，以便了解当前策略设置。

**Why this priority**: 这是所有后续功能（编辑、推送）的基础。

**Acceptance Scenarios**:

1. **Given** 有效的 gameperfconfig.xml，**When** 通过 GUI 打开或拖拽到界面，**Then** 解析 PreEnv（CPU/GPU 频率列表）、BaseInfo（游戏场景）、GamePolicy（模式+温控）并以表格展示
2. **Given** 文件格式不合法的 XML，**When** 尝试加载，**Then** 弹出警告提示解析错误位置
3. **Given** 已加载配置，**When** 切换游戏/性能模式下拉框，**Then** 频率配置表和策略面板同步更新

---

### User Story 2 - 频率配置编辑 (Priority: P1)

作为游戏性能测试工程师，我需要编辑频率索引和触发温度，系统自动反算出对应的 Hz 值，并能另存为修改后的 XML。

**Acceptance Scenarios**:

1. **Given** 频率表中某行的 Gold 索引为 "2_8"，**When** 修改为 "3_10"，**Then** Gold 下限/上限根据 PreEnv 频率列表自动重算并更新表格和 XML
2. **Given** 已修改若干配置，**When** 点击「另存为」，**Then** 生成新 XML 文件，保留所有修改
3. **Given** 右侧策略面板中的 Key/Value 表单，**When** 修改某项的 Value，**Then** XML DOM 实时更新

---

### User Story 3 - 策略配置推送 (Priority: P1)

作为游戏性能测试工程师，我需要将编辑后的 gameperfconfig.xml 推送到设备，设备自动应用新策略。

**Acceptance Scenarios**:

1. **Given** 设备已连接且选择了有效的 XML 配置文件，**When** 点击 Start，**Then** 执行完整推送流程（XML 校验 → version 递增 → root → remount → setenforce → 备份 → push → reboot → version 校验）
2. **Given** 推送过程中，**When** 每完成一个步骤，**Then** 日志区域和进度条实时更新
3. **Given** XML 格式有错误的文件，**When** 点击 Start，**Then** 日志区域以醒目颜色显示错误行及上下文（±3行），终止推送

---

### User Story 4 - 配置还原 (Priority: P2)

作为游戏性能测试工程师，我需要将设备上的策略还原为推送前的备份版本。

**Acceptance Scenarios**:

1. **Given** 之前已执行过 push 操作（有备份），**When** 点击 Reset，**Then** 将备份文件 version 设为「设备 version + 1」后推回设备并重启
2. **Given** 首次使用未推送过，**When** 点击 Reset，**Then** 提示"无可用备份，无法重置"

---

### User Story 5 - CLI 访问 (Priority: P2)

作为 AI Agent 或高级用户，我需要通过 CLI 执行推送/还原/查询操作，以便自动化测试流程。

**Acceptance Scenarios**:

1. **Given** 设备已连接，**When** 执行 `perf push <file.xml>`，**Then** 完成与 GUI 相同的推送流程并输出进度日志
2. **Given** 有备份，**When** 执行 `perf reset`，**Then** 执行还原操作
3. **When** 执行 `perf info`，**Then** 显示当前设备的配置文件 version 等信息

---

### User Story 6 - 连接后自动载入设备配置 (Priority: P1, 规划)

作为游戏性能测试工程师，当设备已通过工具建立连接后，我希望工具**自动**从设备标准路径读取当前生效的 `gameperfconfig.xml` 并载入到本 Tab（与手动从本机打开文件等效的浏览/编辑起点），从而不必每次连上设备都先手动「从设备拉取或选择文件」。

**Why this priority**: 减少重复操作，与推送目标路径一致，闭环更顺。

**Independent Test**: 使用预置已知配置内容的测试机，连接完成后在不选择本地文件的前提下，界面展示与设备文件一致。

**Acceptance Scenarios**:

1. **Given** 目标设备已连接且设备上存在可读的标准路径配置文件，**When** 连接可用且用户进入本 Tab（或满足产品约定的触发时机），**Then** 工具自动拉取并载入该文件，界面呈现解析后的配置内容。
2. **Given** 自动载入成功，**When** 用户随后使用「另存为」或推送流程，**Then** 行为与「用户先手动打开同一份内容」一致（以当前内存中的文档为基准）。
3. **Given** 设备已连接但标准路径文件不存在或不可读，**When** 触发自动读取，**Then** 展示可理解的失败说明，并保留手动选择/打开文件的入口。
4. **Given** 读取过程中连接中断，**When** 操作结束，**Then** 提示连接问题，界面稳定，无未捕获错误。
5. **Given** 当前存在未保存的本地编辑，**When** 将触发自动读取，**Then** 不得静默覆盖；须提示用户选择「放弃本地并载入设备」「取消自动载入」或等效选项。

---

### Edge Cases

- XML 文件编码非 UTF-8 时，应尝试容错解析（errors="replace"）
- PreEnv 中缺少某个 CPU cluster（如设备没有 Prime 核）时，对应频率列表显示为空、索引编辑仍可用
- 推送目标路径固定为 `/system/etc/gameperfconfig.xml`，无论本地文件名如何
- push 前如果 GUI 有未保存的编辑，应先将修改写回原文件
- version 字段在 `<GameOptPolicy version="N">` 标签中，读取和修改均需正则匹配
- BindCore 节点支持动态增删子项（tid），需刷新频率表
- PerfHint 节点使用特殊布局（id/time 并排 + opcode 数据行）
- 设备备份目录按 serial 号隔离
- **自动载入（US6）**：多台设备时仅对**当前选中设备**拉取；短时间反复断连宜去重/冷却，避免骚扰；超大文件行为与手动打开一致；设备上 XML 不合法时错误体验与手动载入一致并标明来源为自动读取

## Clarifications

### Session 2026-03-21

- **Q1**: GamePerfParser 设计方案？ → **A: 方案 B — service 层纯 lxml，返回 dataclass/dict，不依赖 pandas。GUI 层将 dict 转为 QTableWidget 行展示。CLI/Agent 直接消费 dict。**
- **Q2**: PushPolicyService 是否改为纯同步？ → **A: 是。service 层纯同步方法 + 回调通知（与 device_disguise 一致），GUI 层用 QThread 包装。**
- **Q3**: 推送记录存储方式？ → **A: JSON + DB 双写。DB 中保存记录元数据（游戏包名、时间、version、备注）及 JSON 报告文件路径；JSON 文件保存完整策略数据供 Agent 分析。JSON 被误删可从 DB 重新生成。JSON 保存路径需合理规划（作为策略报告）。**
- **Q4**: 「当前数据备注」功能？ → **A: 保留。备注同时写入 JSON 和 DB。**
- **Q5**: get_game_policy.py 是否纳入？ → **A: 延后。本次做策略文件推送 + 策略解析可视化 + 用户直接操作修改 XML。解析中需包含 16 进制→二进制等转换（参考 get_game_policy.py）。**
- **Q6**: 复杂策略面板布局？ → **已在 Step 3 完成设计（上下分栏布局），实现于 gui_tab.py。**

### 验收阶段补充（2026-03-21）

- **B1**: 插件 context 键名冲突 → 所有模块 context 键必须使用模块前缀命名空间（如 `gp_service`、`gp_adb`），详见 `scripts/doc/development-pitfalls.md` P01
- **B2**: ADB stdout/stderr 可能为 None → AdbManager 中所有 stdout/stderr 访问加 `or ""` 保护，详见 P02
- **B3**: GUI Start 崩溃 → 根因为 B1（context 键名冲突导致跨模块服务调用），修复后正常
- **B4**: Clear 按钮行为 → 改为「重置修改」，重载文件并保持当前游戏/模式选择，详见 P07
- **B5**: 滚动条样式 → 优化为 VS Code 风格（半透明轨道、圆角滑块）
- **B6**: Tab 图标 → 设备伪装 Tab 添加 🎭 图标

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 模块 MUST 解析 `gameperfconfig.xml` 的 PreEnv（CPU/GPU 频率列表）、BaseInfo（游戏场景）、GamePolicy（模式+温控+频率索引）
- **FR-002**: 模块 MUST 提供频率表展示，按「游戏→性能模式」过滤，表格列包含温度等级、触发温度、Gold/Prime/GPU 的下限/上限/索引
- **FR-003**: 频率索引编辑后 MUST 自动反算对应的 Hz 上下限值
- **FR-004**: 模块 MUST 提供「另存为」功能，将修改后的 XML 写入新文件
- **FR-005**: 右侧策略面板 MUST 按 XML 节点分组，展示 Key/Value 可编辑表单，修改实时写回 XML DOM
- **FR-006**: BindCore 节点 MUST 支持动态增删子项
- **FR-007**: PerfHint 节点 MUST 使用特殊布局（id/time 并排 + opcode 数据行）
- **FR-008**: 推送流程 MUST 包含：XML 格式校验 → version 递增 → root → remount（使用框架级 AdbManager 智能 remount）→ setenforce → 备份 → push → reboot → version 校验
- **FR-009**: XML 格式错误 MUST 以醒目颜色在日志区域显示错误行及上下文（±3行）
- **FR-010**: 还原功能 MUST 从设备 serial 号对应的备份目录恢复配置
- **FR-011**: CLI MUST 提供 `perf push <file>`、`perf reset`、`perf info` 命令
- **FR-012**: 推送/还原过程 MUST 通过进度回调通知 GUI/CLI 每个步骤的状态
- **FR-013**: 当目标设备连接可用时，模块 MUST 尝试从设备 **`/system/etc/gameperfconfig.xml`** 读取并载入 GUI（在不存在未保存本地冲突的前提下）；路径与现有推送目标一致
- **FR-014**: 自动读取成功后，界面 MUST 将当前文档来源标识为「来自设备」或等效表述，与「来自本地文件」区分
- **FR-015**: 文件不存在、不可读或传输失败时，MUST 展示可读错误说明，且 MUST 不剥夺用户手动打开本地文件等既有能力
- **FR-016**: 存在未保存本地编辑时，MUST NOT 静默用设备内容覆盖编辑缓冲区；MUST 经提示或确认处理（见 US6）
- **FR-017**: 自动读取 SHOULD 在后台或可取消的进度反馈中执行；用户取消时停止拉取并恢复一致 UI 状态
- **FR-018**: 自动载入得到的 XML MUST 复用手动载入相同的校验与解析规则

### Key Entities

- **GamePerfParser**: XML 解析引擎（纯 lxml，返回 dataclass/dict）
- **GamePerfService**: 推送/还原/版本管理的纯同步业务逻辑
- **GamePerfTab**: GUI Tab 页（上下分栏：频率表 → 频率参考+策略面板 → 日志+按钮）
- **XmlErrorContext**: XML 格式错误上下文（行号、列号、上下文行）
- **设备连接上下文（US6）**: 当前选中设备、连接/断开状态
- **配置文档缓冲区（US6）**: 内存中文档及来源（本地/设备）、是否脏（未保存）
- **自动读取结果（US6）**: 成功或失败（原因分类：不存在、权限、传输、解析等）

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: GamePerfParser 对标准 gameperfconfig.xml 解析成功率 100%（不含用户损坏的文件）
- **SC-002**: 频率索引编辑后 Hz 值反算正确，单元测试覆盖 Gold/Prime/GPU 三组
- **SC-003**: 推送端到端完成（含设备重启）< 3 分钟
- **SC-004**: 还原功能 version 校验通过率 100%（有备份时）
- **SC-005**: CLI 命令 `perf push/reset/info` 有单元测试覆盖
- **SC-006（US6）**: 标准测试设备上，从「连接可用」到「界面呈现与设备文件一致的解析结果」，典型场景 **60 秒内**完成且无需先手动选文件
- **SC-007（US6）**: 文件缺失、不可读、断连三类场景下 **100%** 有明确失败反馈，工具保持可用，**0** 次未处理崩溃
- **SC-008（US6）**: 存在未保存本地编辑时 **100%** 不发生静默覆盖

## Assumptions（US6）

- 「设备已连接」沿用工具现有发现/选中/连接流程；本特性仅在就绪后追加拉取动作。
- 自动读取触发时机至少包含：**首次进入本 Tab 且设备已就绪**、**从断连恢复为已连接**；细则在实现计划中定稿。
