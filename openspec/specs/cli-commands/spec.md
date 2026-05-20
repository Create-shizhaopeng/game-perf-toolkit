## MODIFIED Requirements

### Requirement: CLI commands as human-only interface
CLI commands SHALL remain available for human debugging and interactive use, but SHALL NOT be promoted as an Agent invocation path. Agent documentation and skill flows MUST direct Agent tool usage through MCP or Skill paths, not CLI commands.

#### Scenario: CLI remains functional for humans
- **WHEN** a human user runs `python -m toolkit.app device disguise --brand 华为 ...`
- **THEN** the CLI executes normally with Rich formatted output

#### Scenario: Agent invocation redirects to MCP/Skill
- **WHEN** an Agent needs to disguise a device
- **THEN** the Agent uses `device_disguise` MCP tool or follows the SKILL.md workflow, NOT the CLI command
