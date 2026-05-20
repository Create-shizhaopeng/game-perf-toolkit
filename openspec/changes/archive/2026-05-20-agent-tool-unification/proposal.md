## Why

当前项目对 Agent 的调用入口混杂：各模块通过 `register_agent_tools()` 注册工具，但只给内置 `agent_chat` 模块使用；CLI 命令（Typer）是给人类终端用的，输出 Rich 格式化文本（emoji/颜色/表格），LLM 调用时既浪费 token（解析格式化输出）又不稳定（格式变化导致解析失败）。外部 Agent（如 Claude Code）无法通过标准协议调用项目功能。同时，团队要求模块 Skill 可独立剥离到别的项目中运行（类似 Claude Code agent 形式），当前没有 Skill 发现和分发机制。

## What Changes

- **框架层新增 MCP Server**：将 `ToolRegistry` 中的工具通过标准 MCP 协议（stdio/sse 模式）暴露，供外部 Agent 调用
- **框架层新增 Skill 分发机制**：发现各模块 `skills/` 目录下的 `SKILL.md`，注册到 Agent 可发现和触发的列表中
- **各模块选择性注册**：模块按特性选择暴露为 MCP 工具、Skill 文档、或两者兼有，不强制
- **CLI 命令完全移除**: 人类使用 GUI，CLI (Typer) 体系整体删除
- **`register_agent_tools()` 规范化**：补全 parameters schema、返回值结构化，确保 MCP 和内部调用共享同一套定义

## Capabilities

### New Capabilities

- `mcp-server`: Framework-level MCP server (stdio/sse) that bridges `ToolRegistry` to standard MCP protocol for external Agent consumption
- `skill-registry`: Framework-level skill discovery mechanism that scans module `skills/` directories, loads `SKILL.md` files, and makes them available for Agent triggering
- `module-agent-tools`: Enhanced `register_agent_tools()` hook contract requiring complete JSON Schema parameters and structured return values, shared by both internal `agent_chat` and external MCP server

### Removed Capabilities

- `cli-commands`: Typer CLI 体系整体移除。人类用户通过 GUI 操作；Agent 通过 MCP 或 Skill 调用

## Impact

- **新增文件**: `toolkit/core/mcp_server.py`, `toolkit/core/skill_registry.py`
- **修改文件**: `toolkit/core/hookspecs.py`（新增 `register_skills` hook）, `toolkit/app.py`（启动 MCP Server 入口）, `toolkit/sdk/base_plugin.py`
- **各模块修改**: `plugin.py` 中 `register_agent_tools()` 补全 schema；试点模块 `device_disguise` 新增 `skills/` 目录
- **新增 hook**: `register_skills()` — 模块可选实现，返回 Skill 路径列表
- **不修改**: Service 层纯业务逻辑、GUI 层
- **移除**: 所有 `modules/*/src/cli_commands.py`、`modules/*/src/strings_cli.py`、CLI 选项操作
