# Feature Specification: Hardcoded String Extraction

**Feature Branch**: `019-hardcoded-string-extraction`

**Created**: 2026-05-19

**Status**: Draft

**Input**: 当前项目中存在很多硬编码的字符串，现在需要重构代码优化这个问题，确保每个模块都有单独的字符串映射表，替代掉代码中的硬编码。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 模块字符串映射表创建 (Priority: P1)

作为开发者，我希望每个模块拥有独立的 `strings.py` 文件，将 GUI 对话框标题/正文、按钮文字、分组框标题、进度提示、CLI 帮助文本等中文硬编码字符串提取为集中管理的常量或字典，这样后续修改文案时无需在多个文件中逐个搜索替换。

**Why this priority**: 这是整个重构的基础设施，所有后续迁移依赖于此。没有统一的字符串管理结构，无法开展分模块迁移。

**Independent Test**: 创建任一模块的 `strings.py` 后，可通过运行模块的单元测试验证字符串是否正确显示，且代码引用正常。

**Acceptance Scenarios**:

1. **Given** 模块存在 `src/strings.py`，**When** 查看文件内容，**Then** 包含该模块所有 GUI 对话框标题、按钮文字、CLI 帮助文本等字符串常量，按类别组织
2. **Given** 模块的 GUI Tab 文件，**When** 引用 `strings.py` 中的常量替换原有硬编码字符串，**Then** 界面显示的中文文本与重构前完全一致
3. **Given** 模块的 CLI 命令文件，**When** 引用 `strings.py` 中的常量替换原有硬编码 help 字符串，**Then** CLI 帮助输出与重构前完全一致

---

### User Story 2 - 模块逐个迁移字符串 (Priority: P2)

作为维护者，我希望按模块逐步迁移硬编码字符串到 `strings.py`，每次迁移一个模块，这样可以在出问题时只回退单个模块，降低风险。

**Why this priority**: 保证重构过程的可控性。每个模块迁移后都应通过该模块的测试验证功能未受影响。

**Independent Test**: 完成任一模块的迁移后，运行该模块的测试和 GUI 功能验证，界面文案和 CLI 帮助文本保持不变。

**Acceptance Scenarios**:

1. **Given** 模块已完成 `strings.py` 创建，**When** 将该模块所有硬编码中文字符串替换为 `strings.py` 引用，**Then** 模块的 GUI 界面、CLI 命令、日志提示文案与重构前一致
2. **Given** 模块迁移完成，**When** 需要修改某条文案，**Then** 只需修改 `strings.py` 一处即可生效

---

### User Story 3 - 框架层 GUI 字符串提取 (Priority: P3)

作为维护者，我希望 `toolkit/gui/` 框架层也有独立的字符串常量管理，因为框架层的对话框、侧边栏、导航栏同样包含硬编码中文。

**Why this priority**: 框架层字符串数量相对较少但影响范围广（所有模块共用），建议在模块迁移完成后处理。

**Independent Test**: 框架层迁移完成后，MainWindow 侧边栏、系统对话框、LLM 设置对话框等中文显示正常。

**Acceptance Scenarios**:

1. **Given** `toolkit/gui/strings.py` 已创建，**When** 框架 GUI 文件引用其中常量，**Then** 主窗口侧边栏、对话框、设置页面中文文案与重构前一致

---

### Edge Cases

- 字符串中包含格式化占位符（如 `f"设备 {serial} 未连接"`）：需要保留插值能力，使用 `.format()` 或 f-string 模板存储在 `strings.py` 中
- 部分字符串使用了 Rich 标记（如 `[red]✗ 未检测到已连接设备[/red]`）：Rich 标记作为字符串一部分保留在映射表中
- CLI 的 `typer.Typer(help=...)` 字符串需要在模块初始化时动态读取，不能延迟加载

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 每个模块 `modules/<name>/` 根据入口文件按需创建字符串文件：有 gui_tab.py 则创建 strings_gui.py，有 cli_commands.py 则创建 strings_cli.py，有 service.py 则创建 strings_service.py
- **FR-002**: `strings.py` 中的字符串必须按类别分组（如 `GUI_DIALOGS`、`CLI_HELP`、`PROGRESS_MSG`、`ERROR_MSG`）
- **FR-003**: 字符串存储结构统一使用 `dict[str, str]` 或 `Final[str]` 常量形式，确保 IDE 自动补全支持
- **FR-004**: 迁移过程中，所有 GUI 对话框标题/正文、按钮文字、分组标题、CLI help 文本、Rich console 消息必须被提取
- **FR-005**: 迁移完成后，模块的功能行为（界面文案、CLI 帮助输出、错误提示）必须与迁移前完全一致
- **FR-006**: 包含变量的动态字符串（如 `f"设备 {serial} 未连接"`）应提取为模板字符串，使用 `.format()` 方法在运行时插值
- **FR-007**: `toolkit/gui/` 框架层需单独维护一份 `strings.py`，独立于模块

### Clarifications

### CL-001: 模块拆分策略 — 按类别拆分为多个子文件

**决策**: 所有模块统一按类别拆分为三个子文件：
- `strings_gui.py` — GUI 文案（对话框标题、按钮、分组框、消息提示）
- `strings_cli.py` — CLI 帮助文本、Rich console 消息
- `strings_service.py` — Service 层进度消息、日志文案

原阈值规则（50 个拆三文件、30 个以下单文件）已废弃。所有模块统一采用三文件结构。`device_disguise` 按三文件拆分。

### Session 2026-05-19

- Q: dev branch 上已有 device_disguise 和 game_perf 的 strings_*.py 文件修改，是否作为迁移基线？
  **A**: 丢弃已有全部修改，所有模块从头开始统一按 spec 顺序迁移。
- Q: 字符串文件拆分阈值是否保持 30？
  **A**: 保持阈值 30，所有模块统一拆分为三文件（strings_gui.py、strings_cli.py、strings_service.py）。CL-001 已更新废弃原阈值规则。
- Q: device_disguise 和 game_perf 已按三文件拆分完成，是否仍需在迁移顺序中重新迁移？
  **A**: 跳过这两个模块，保留其 strings 文件作为已完成状态，仅需验证正确性。迁移顺序调整为：perfetto_capture → agent_chat → perfetto_analysis → perfdog_insights → workspace_tools。
- Q: 对于缺少对应入口文件（如 cli_commands.py）的模块，是否仍要创建空的 strings_*.py 文件？
  **A**: 按需创建：模块有 gui_tab.py 才建 strings_gui.py，有 cli_commands.py 才建 strings_cli.py，有 service.py 才建 strings_service.py。FR-001 需更新。
- Q: 是否需要提供自动化验证脚本？
  **A**: 提供自动化验证脚本，检查源文件中是否有遗漏的中文硬编码并运行全量测试。

### CL-002: Service 层进度消息 — 提取到 `strings_service.py`

**决策**: `service.py` 中的 `on_progress(msg)` 文案和 `_append_log()` 中的进度提示字符串属于用户可见文案，必须提取到 `strings_service.py`。

### CL-003: 通用按钮文字 — 各模块独立维护

**决策**: "确认""取消""确定""保存"等通用按钮文字不放在框架统一字典中，由每个模块在自己的 `strings_gui.py` 中独立维护。框架层 `toolkit/gui/` 的通用文案由框架自己维护，不对外暴露。

## Key Entities  



- **模块字符串表 (Module String Table)**: 存放于 `modules/<name>/src/strings.py`，按功能类别组织的字符串常量集合
- **框架字符串表 (Framework String Table)**: 存放于 `toolkit/gui/strings.py`，框架级 UI 文案

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 项目中不再有模块级文件中的中文硬编码字符串（GUI 标题、按钮、对话框、CLI help），可通过 grep 验证
- **SC-002**: 每个模块至少包含一个 `src/strings.py` 文件，且覆盖该模块所有 GUI 和 CLI 中文字符串
- **SC-003**: 迁移后所有模块的 GUI Tab 能正常加载，中文文案显示正确
- **SC-004**: 迁移后所有 CLI 命令的 `--help` 输出与迁移前完全一致
- **SC-005**: 迁移后全量测试通过，无回归

## Assumptions

- 仅提取用户可见的字符串（GUI 文案、CLI 帮助、错误提示），不涉及日志格式字符串、内部状态标识、SQL 语句等
- 不引入国际化（i18n）框架，仅做字符串集中管理，降低复杂度
- 字符串使用 Python 原生 `dict` 或 `Final[str]` 常量存储，不依赖外部依赖
- 模块按受影响字符串数量从高到低顺序迁移：perfetto_capture → agent_chat → game_perf → perfetto_analysis → device_disguise → perfdog_insights → workspace_tools
- 框架层 `toolkit/gui/` 字符串在所有模块迁移完成后处理
