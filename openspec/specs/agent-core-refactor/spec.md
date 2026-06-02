# Agent Core Refactor — Delta Spec

修复 DES-001 实现中的全部 18 项审计偏差，不改需求本身，只修正实现路径。

## ADDED Requirements

### Requirement: 新建模块包含单元测试

`toolkit/agent/skill_tools.py`、`toolkit/agent/skill_router.py` 和修改后的 `toolkit/core/mcp/registry.py` MUST 在 `tests/` 下有对应的测试文件，每个公开方法 ≥1 个正常路径测试。

#### Scenario: skill_tools 测试

- **WHEN** 运行 `python -m pytest tests/test_agent_skill_tools.py`
- **THEN** 至少包含 `test_build_skill_tools` 和每个 skill 工具的 smoke test

#### Scenario: mcp registry 测试

- **WHEN** 运行 `python -m pytest tests/test_core_mcp_registry.py`
- **THEN** 至少包含 `test_register_local` 和 `test_register_remote`

## MODIFIED Requirements

### Requirement: FR-003 — MCP Client 启动连接

MCP Client 组件已提升至 `toolkit/core/mcp/`。MUST 在启动时调用 `MCPRegistry.connect_all()`。MUST 实现 `register_local()` 和 `register_remote()`。MUST NOT 在注册操作时自动持久化配置文件（auto-save 仅在显式 `add_server()`/`remove_server()` 时触发）。

#### Scenario: 启动时 MCP 工具已注入

- **WHEN** 应用 GUI 启动完成且 event loop 就绪
- **THEN** 所有已启用的 MCP Server 的工具以 `mcp__{server}__{tool}` 格式出现在 ToolRegistry 中

#### Scenario: register_local 注册子模块工具

- **WHEN** 模块调用 `mcp_registry.register_local("module_name", HandlerClass)`
- **THEN** HandlerClass 的公开方法以 `mcp__module_name__{method}` 格式注册到 ToolRegistry

### Requirement: FR-007 — AgentOrchestrator 初始化入口

`AgentOrchestrator` MUST 作为启动时的唯一初始化入口。`init()` 和 `init_async()` MUST 在 GUI 启动时被调用。

#### Scenario: Orchestrator.init 在 GUI 启动时被调用

- **WHEN** `run_gui()` 执行
- **THEN** `orchestrator.init()` 在 AgentPanel 创建之前被调用

### Requirement: FR-008 — System Prompt 三段式

System Prompt MUST 支持 `report_index` 参数输入报告上下文。Volatile 层 MUST 包含 `conv_id` 信息。

#### Scenario: System Prompt 包含报告上下文

- **WHEN** 调用 `build_system_prompt(tools=[], skills=[], report_index=ReportIndex())`
- **THEN** Stable 层包含最近分析报告摘要

### Requirement: FR-010 — AgentPanel 右侧面板

AgentPanel MUST 声明 `panel_expanded`/`panel_collapsed`/`message_sent` 信号。MUST 支持拖拽调整宽度（240px-480px）。MUST 提供会话选择器。

#### Scenario: 面板拖拽调整

- **WHEN** 用户在面板左边缘拖拽
- **THEN** 面板宽度在 240px-480px 范围内变化

### Requirement: FR-013 — 消息渲染组件复用

AgentPanel 的消息渲染 MUST 复用现有组件设计，MUST NOT 使用内联样式覆盖全局 QSS。

### Requirement: FR-015 — Skill 工具注入

Skill 工具 MUST 通过 `Orchestrator._register_skill_tools()` 从 `SkillRegistry` 生成并注入 `ToolRegistry`。

#### Scenario: Skill 工具由 Orchestrator 统一管理

- **WHEN** Orchestrator.init() 执行
- **THEN** `skill_list`、`skill_load`、`skill_load_resource`、`skill_list_resources` 已注册到 ToolRegistry

### Requirement: SkillMetadata 类型修正

`SkillMetadata.triggers` 类型 MUST 为 `list[str]` 而非 `dict`。`search()` 方法 MUST 搜索 triggers 关键词。

#### Scenario: 按触发关键词搜索 Skill

- **WHEN** Skill 的 triggers 包含 `["trace", "jank"]`
- **AND** 调用 `registry.search("jank")`
- **THEN** 该 Skill 出现在搜索结果中

### Requirement: SkillRegistry API 别名

`SkillRegistry` MUST 提供 `get_content(name)` 作为 `get_skill_content(name)` 的别名。

### Requirement: ToolRegistry.dispatch 方法

`ToolRegistry` MUST 提供 `dispatch(name, args)` 便捷方法，委托到 `ToolExecutor.execute()`。

### Requirement: MCP 注册不自动持久化

`MCPRegistry.register_external()` 和 `register_remote()` MUST NOT 在注册时自动调用 `save_config()`。持久化仅在 `add_server()`/`remove_server()` 时触发。

### Requirement: _build_context 补全

`_build_context()` MUST 创建 `ToolRegistry()` 和 `MCPRegistry()` 实例。

### Requirement: AgentService 类型清理

`AgentService.__init__()` 的 `skills_manager` 和 `sop_manager` 参数类型 MUST 使用 `Any` 替代未定义的类名。

### Requirement: _enhance_schema 方法归属

`_enhance_schema()` MUST 作为 `ToolRegistry` 的实例方法，而非模块级函数。

### Requirement: AgentPanel._ctx 命名修正

AgentPanel 中的 `_ctx` 属性 MUST 被移除或重命名为明确名称（如 `_tool_registry`）。
