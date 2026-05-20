## ADDED Requirements

### Requirement: Complete Parameters Schema
Every tool registered via `register_agent_tools()` SHALL include a complete JSON Schema `parameters` field, enabling both internal `agent_chat` and external MCP clients to construct correct tool calls without guessing parameter types or names.

#### Scenario: Tool with parameters
- **WHEN** a module registers a tool like `device_disguise`
- **THEN** the tool definition includes `parameters` with `type: object`, `properties` for each parameter (serial, brand, manufacturer, model), and `required` listing mandatory fields

#### Scenario: Tool without parameters
- **WHEN** a module registers a tool that takes no arguments (e.g., `profile_list`)
- **THEN** the tool definition includes `parameters: { "type": "object", "properties": {} }`

### Requirement: Structured Return Values
Tools registered via `register_agent_tools()` SHALL return data that can be reliably serialized to strings for LLM consumption. Pydantic models, dataclasses, dicts, and lists are automatically handled by `ToolExecutor._serialize_result()`.

#### Scenario: Tool returns Pydantic model
- **WHEN** a tool method returns a Pydantic BaseModel instance
- **THEN** `ToolExecutor` serializes it via `model_dump_json(indent=2)`, producing valid JSON the LLM can parse

#### Scenario: Tool returns None
- **WHEN** a tool method returns None
- **THEN** `ToolExecutor` returns the string "执行完成（无返回值）"

### Requirement: Tool Registry Unification
The `ToolDefinition` type SHALL be defined in a single location (`toolkit/core/llm/base.py`) and imported by all consumers. Duplicate definitions in `modules/agent_chat/src/models.py` SHALL be replaced with imports from the unified location.

#### Scenario: Import from unified location
- **WHEN** `modules/agent_chat/src/tools/registry.py` imports `ToolDefinition`
- **THEN** it imports from `toolkit.core.llm.base` instead of the local models.py
