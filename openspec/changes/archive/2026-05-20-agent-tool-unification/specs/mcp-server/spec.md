## ADDED Requirements

### Requirement: Framework MCP Server
The system SHALL provide a unified MCP server that exposes all registered agent tools from `ToolRegistry` via the standard Model Context Protocol (MCP), enabling external agents (Claude Code, other LLMs) to call module functions through a standardized protocol.

#### Scenario: MCP server starts in stdio mode
- **WHEN** the application is launched with `mcp-serve` command or stdio mode
- **THEN** the MCP server reads from stdin and writes JSON-RPC responses to stdout, following the MCP specification

#### Scenario: MCP server exposes all registered tools
- **WHEN** an external MCP client connects to the server
- **THEN** the client receives a `tools/list` response containing all tools registered in `ToolRegistry`, each with name, description, and JSON Schema input schema

#### Scenario: External agent calls a tool
- **WHEN** an external MCP client sends a `tools/call` request with tool name and arguments
- **THEN** the server delegates to `ToolExecutor.execute()`, returns the serialized result to the client

#### Scenario: Tool call fails gracefully
- **WHEN** a tool execution raises an exception
- **THEN** the MCP server returns an error response containing the exception message, not a crash

#### Scenario: MCP server initializes after module startup
- **WHEN** the application starts
- **THEN** the MCP server registers tools only after all module `on_startup()` hooks have completed, ensuring `ToolRegistry` is fully populated

### Requirement: SSE mode (deferred)
The MCP server SHALL support an optional SSE (Server-Sent Events) transport mode, activatable via a command-line flag, for scenarios where HTTP-based MCP connectivity is needed.

#### Scenario: SSE mode activation
- **WHEN** the application is launched with `mcp-serve --transport sse --port 8765`
- **THEN** the MCP server listens on the specified port and accepts SSE connections from external clients
