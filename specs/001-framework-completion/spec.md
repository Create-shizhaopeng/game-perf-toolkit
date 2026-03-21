# Feature Specification: 框架完善与验证

**Feature Branch**: `001-framework-completion`
**Created**: 2026-03-20
**Status**: Draft
**Input**: User description: "Complete the LV Game Toolkit core framework: GUI verification, core service testing, and framework documentation"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - GUI 主窗口正常显示与交互 (Priority: P1)

作为工具使用者，我启动 LV Game Toolkit 后看到一个完整的 GUI 界面，包含自定义标题栏（设备状态指示、设备选择、主题切换）、左侧导航面板和模块内容区域。我可以通过导航面板切换不同模块页面，通过标题栏切换暗色/亮色主题，窗口支持拖拽移动、最小化、最大化和关闭。

**Why this priority**: GUI 是人类用户的主要交互入口，是工具可用性的基础保障。如果界面无法正常显示和交互，后续所有模块的 GUI 功能都无法正常工作。

**Independent Test**: 运行 `python -m toolkit.app` 启动 GUI，验证窗口正常显示、导航切换、主题切换和窗口控制均可操作。

**Acceptance Scenarios**:

1. **Given** 无命令行参数启动应用, **When** 程序启动完成, **Then** 显示无边框主窗口，包含标题栏、导航面板和首页内容
2. **Given** GUI 已启动, **When** 点击左侧导航按钮, **Then** 内容区域切换到对应模块页面
3. **Given** GUI 已启动, **When** 点击标题栏主题切换按钮, **Then** 整个界面在暗色/亮色主题间切换
4. **Given** GUI 已启动, **When** 拖拽标题栏, **Then** 窗口跟随移动
5. **Given** GUI 已启动, **When** 点击最小化/最大化/关闭按钮, **Then** 窗口执行相应操作

---

### User Story 2 - 核心服务可靠运行 (Priority: P1)

作为模块开发者，我依赖核心框架提供的服务（配置管理、数据库、事件总线、服务注册表、插件管理器、ADB 管理器）进行模块开发。每个核心服务都应有测试覆盖，确保接口行为符合预期，不会因核心服务的 bug 导致模块开发受阻。ADB 管理器仅覆盖基本场景测试（路径解析、命令拼接）。

**Why this priority**: 核心服务是所有模块的基础依赖，任何核心服务的 bug 都会影响全部模块的开发和运行。与 US1 同等优先级。

**Independent Test**: 运行 `pytest tests/` 执行核心服务单元测试，全部通过。

**Acceptance Scenarios**:

1. **Given** ConfigManager 已初始化, **When** 设置和获取嵌套键值, **Then** 值正确存储和读取
2. **Given** EventBus 已初始化, **When** 注册监听并触发事件, **Then** 回调函数正确执行
3. **Given** ServiceRegistry 已初始化, **When** 注册和获取服务, **Then** 服务实例正确返回
4. **Given** DatabaseManager 已连接, **When** 执行 SQL 和迁移操作, **Then** 数据正确持久化
5. **Given** PluginManager 已初始化, **When** 扫描 modules/ 目录, **Then** 所有合法模块被正确发现、排序和加载

---

### User Story 3 - CLI 内置命令完整可用 (Priority: P2)

作为 AI Agent 或高级用户，我通过 CLI 方式与工具交互。内置命令（version、config、plugin、device）应该正常工作，模块的子命令应该自动注册并可用。

**Why this priority**: CLI 是 Agent 的主要交互通道，也是开发者调试的重要工具。核心框架的 CLI 部分已通过手动验证，但需要自动化测试保证持续可靠。

**Independent Test**: 运行 `python -m toolkit.app version`、`python -m toolkit.app plugin list` 等命令验证输出正确。

**Acceptance Scenarios**:

1. **Given** 带参数启动应用, **When** 执行 `version` 命令, **Then** 输出版本号
2. **Given** 模块已加载, **When** 执行 `plugin list` 命令, **Then** 显示所有已加载模块信息表格
3. **Given** 配置文件存在, **When** 执行 `config get <key>` 命令, **Then** 返回对应配置值
4. **Given** 模块已注册 CLI, **When** 执行模块子命令如 `device info`, **Then** 模块子命令正确响应

---

### User Story 4 - 脚手架生成完整可用的模块骨架 (Priority: P2)

作为新模块开发者，我使用脚手架脚本创建新模块。生成的模块骨架应该结构完整、代码可运行，能被框架自动发现和加载。

**Why this priority**: 脚手架是团队协作开发的入口工具，影响每个新模块的开发体验。已通过手动验证，需要自动化测试。

**Independent Test**: 运行脚手架脚本创建测试模块，验证模块结构完整且能被框架加载。

**Acceptance Scenarios**:

1. **Given** 提供合法模块名, **When** 运行 `python scripts/create_module.py test_mod`, **Then** 在 modules/ 下生成完整目录结构
2. **Given** 脚手架已生成模块, **When** 启动应用, **Then** 新模块被自动发现和加载
3. **Given** 提供已存在的模块名, **When** 运行脚手架, **Then** 报错退出，不覆盖已有目录

---

### Edge Cases

- 当 `modules/` 目录不存在时，PluginManager 应优雅处理并给出警告
- 当 `manifest.json` 格式错误时，PluginManager 应跳过该模块并记录错误
- 当两个模块声明相同的 CLI 命名空间时，应抛出冲突异常
- 当 `data/` 目录不存在时，ConfigManager 和 DatabaseManager 应自动创建
- 当 GUI 启动但无设备连接时，标题栏应显示红色指示灯和"未连接设备"（此为默认/初始状态文案；设备断开后点击操作按钮的提示为"设备已断开"，两者语义不同，前者描述连接状态，后者描述操作被拒原因）
- 当主题切换时，所有已渲染的组件样式应立即更新（含状态卡片、模块列表等内联样式）
- 当设备在操作过程中断开连接时，已填写的数据应保留，设备相关操作按钮应变为禁用状态
- 当窗口高度已达最小值时拖拽右侧边缘，宽度仍应可正常缩放（维度独立处理）
- 当鼠标从窗口边缘移开后，光标样式应自动恢复为箭头
- 当双击标题栏最大化/恢复时，窗口应以鼠标位置为中心定位

## Clarifications

### Session 2026-03-20

- Q: 设备在使用过程中断开连接，各模块页面应如何响应？ → A: 标题栏显示断开状态，涉及设备操作的功能按钮禁用，点击时提示"设备已断开"。当前工作区已填写的内容保持不变不丢失。（注：标题栏/选择器的默认状态文案为"未连接设备"，操作被拒的提示文案为"设备已断开"，二者语义不同、各有用途）
- Q: AdbManager 是否需要 mock 测试？ → A: ADB 只测基本场景（路径解析、命令拼接），其他核心服务全面测试。
- Q: 日志级别如何控制？ → A: 同时支持 config.json 配置日志级别和 CLI --verbose/--debug 参数，CLI 参数优先级高于配置文件。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 在无命令行参数时启动 GUI 模式，有参数时启动 CLI 模式
- **FR-002**: GUI MUST 显示自定义无边框窗口，包含标题栏、左侧导航和内容堆栈
- **FR-003**: 标题栏 MUST 显示设备连接状态指示灯（红/绿/蓝）和设备选择下拉框
- **FR-004**: 导航面板 MUST 根据已加载模块动态生成导航按钮
- **FR-005**: 系统 MUST 支持暗色和亮色两种主题，可通过标题栏按钮切换
- **FR-006**: CLI MUST 提供 version、config、plugin、device 四组内置命令
- **FR-007**: PluginManager MUST 自动发现 modules/ 下的模块并按依赖排序加载
- **FR-008**: PluginManager MUST 检测 CLI 命名空间冲突并阻止加载
- **FR-009**: ConfigManager MUST 支持嵌套键的读写和持久化
- **FR-010**: EventBus MUST 支持事件注册、注销和同步触发
- **FR-011**: ServiceRegistry MUST 支持服务注册、查询和 JSON Schema 生成
- **FR-012**: DatabaseManager MUST 支持连接管理、SQL 执行和模块迁移
- **FR-013**: 脚手架脚本 MUST 生成完整的模块骨架（manifest.json、plugin.py、service.py、cli_commands.py、gui_tab.py、AGENTS.md、测试文件）
- **FR-014**: 所有中文输出 MUST 使用 UTF-8 编码，不出现乱码
- **FR-015**: 设备断开连接时，标题栏 MUST 显示断开状态，涉及设备操作的功能按钮 MUST 禁用并在点击时提示"设备已断开"，用户当前工作区的数据 MUST 保持不丢失
- **FR-016**: 系统 MUST 支持通过 config.json 配置日志级别，同时 CLI MUST 支持 --verbose 和 --debug 参数覆盖配置文件的日志级别设置
- **FR-017**: GUI MUST 在窗口底部显示状态栏（StatusBar），左侧显示当前状态信息，右侧显示版本号
- **FR-018**: GUI MUST 支持通过拖拽窗口边缘进行自由缩放，缩放时各维度独立限制到最小尺寸，不会出现卡顿
- **FR-019**: 导航面板 MUST 支持通过拖拽分隔条调整宽度（120-300px 范围）

### Key Entities

- **模块 (Module)**: 独立功能单元，通过 manifest.json 声明元数据，包含 src/、tests/、specs/ 子目录
- **核心服务 (Core Service)**: ConfigManager、DatabaseManager、EventBus、ServiceRegistry、PluginManager、AdbManager、ProcessBridge、Logger
- **模块页面 (Tab)**: 继承 BaseTab 的 GUI 页面组件，由模块通过钩子注册

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: GUI 启动后 3 秒内完成窗口渲染和模块加载
- **SC-002**: US2 列出的 6 项核心服务（ConfigManager、EventBus、ServiceRegistry、DatabaseManager、PluginManager、AdbManager）单元测试全部通过（共 ≥49 项）。ProcessBridge 和 Logger 为薄封装层，本期不做单元测试
- **SC-003**: CLI 内置命令（version、config get/set/list、plugin list）均可正常执行并返回预期格式输出；device 命令组依赖 ADB 环境，通过 AdbManager 基本场景测试间接覆盖（见 T013）
- **SC-004**: 脚手架创建的模块能在 2 秒内被框架自动发现和加载
- **SC-005**: 主题切换操作后界面即时更新，无视觉异常
- **SC-006**: 中文字符在 CLI 输出、GUI 界面和日志文件中均正确显示
