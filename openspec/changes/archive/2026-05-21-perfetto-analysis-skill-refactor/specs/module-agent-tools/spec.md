## MODIFIED Requirements

### Requirement: Complete Parameters Schema
Every tool registered via `register_agent_tools()` SHALL include a complete JSON Schema `parameters` field, enabling both internal `agent_chat` and external MCP clients to construct correct tool calls without guessing parameter types or names.

perfetto_analysis 模块 SHALL 从 14 个 pa_* 工具收拢为 1 个 `pa_execute_sql` 工具。pa_execute_sql 的 parameters SHALL 包含 `trace_path` (string, required) 和 `sql` (string, required) 两个字段，以及完整的使用指引 description。

#### Scenario: perfetto_analysis registers single tool
- **WHEN** perfetto_analysis module implements `register_agent_tools()`
- **THEN** it returns a list containing only `pa_execute_sql` tool with parameters `{trace_path: string, sql: string}`

#### Scenario: pa_execute_sql has complete parameter schema
- **WHEN** pa_execute_sql tool is registered
- **THEN** its `parameters` includes `type: object`, `properties` with `trace_path` and `sql` (both type string), and `required: ["trace_path", "sql"]`

#### Scenario: pa_execute_sql description includes usage guidance
- **WHEN** Agent reads pa_execute_sql tool description
- **THEN** description includes guidance on: SQL source (YAML skill files), variable substitution (${var} → actual values), result format

## REMOVED Requirements

### Requirement: Multi-tool registration for perfetto_analysis
**Reason**: 14 个细粒度 pa_* 工具被单一 pa_execute_sql 工具替代。Agent 通过 YAML 技能库 + pa_execute_sql 获得完整分析能力，不需要预定义的高层工具。
**Migration**: 所有 pa_* 工具的 SQL 逻辑已迁移到 atomic/composite YAML 技能文件中，Agent 通过 SKILL.md 索引定位后用 pa_execute_sql 执行。
