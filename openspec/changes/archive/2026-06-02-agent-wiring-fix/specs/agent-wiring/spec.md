# Agent Wiring

AgentOrchestrator 作为启动时唯一初始化入口，串联模块工具收集 → Skill 工具注入 → MCP 异步连接 → AgentService 创建。

## ADDED Requirements

### Requirement: Orchestrator.init() 串联同步初始化

`AgentOrchestrator.init()` SHALL 依次执行：
1. `_register_skill_tools()` — 从 SkillRegistry 生成 skill_* 工具并注入 ToolRegistry
2. `_register_builtin_tools()` — 注入 create_workspace/list_workspace_files

#### Scenario: 启动后 Skill 工具已注入

- **WHEN** Orchestrator.init() 执行完成
- **THEN** ToolRegistry 中包含 `skill_list`、`skill_load`、`skill_load_resource`、`skill_list_resources` 工具

#### Scenario: 启动后内置工具已注入

- **WHEN** Orchestrator.init() 执行完成
- **THEN** ToolRegistry 中包含 `create_workspace`、`list_workspace_files` 工具

### Requirement: Orchestrator.init_async() 连接 MCP

`AgentOrchestrator.init_async()` SHALL 异步调用 `MCPRegistry.connect_all()` 连接所有已启用的 MCP Server，并将发现的工具注入 ToolRegistry。

#### Scenario: MCP 工具在 event loop 启动后可用

- **WHEN** app.py 通过 QTimer 调度 `init_async()` 且存在已配置的 MCP Server
- **THEN** ToolRegistry 中包含 `mcp__{server}__{tool}` 格式的外部工具

#### Scenario: MCP 连接失败不阻塞启动

- **WHEN** MCP Server 连接失败
- **THEN** 启动不中断，错误记录到日志

### Requirement: AgentPanel 通过 Orchestrator 创建服务

`AgentPanel._ensure_service()` SHALL 调用 `self._orch.create_service(conversation_store=self._store)`，不再自行创建 ToolRegistry 或 SkillsManager。

#### Scenario: 面板展开时服务就绪

- **WHEN** 用户展开 Agent 面板
- **THEN** AgentService 已通过 Orchestrator 创建，`is_ready` 返回 True（当 LLM Provider 已配置时）
- **AND** 服务使用 Orchestrator 统一的 ToolRegistry（含模块+Skill+MCP 工具）

### Requirement: run_mcp_server 使用 toolkit.core 路径

`app.py` 的 `run_mcp_server()` SHALL 使用 `toolkit.core.tool_registry` 的模块级单例和 `toolkit.core.tool_executor.ToolExecutor`，不再从 `modules.agent_chat.src.tools` 创建独立实例。

#### Scenario: MCP Server 模式暴露全部工具

- **WHEN** 执行 `python -m toolkit.app mcp-serve`
- **THEN** MCP Server 中暴露的工具包括模块工具和 Skill 工具
