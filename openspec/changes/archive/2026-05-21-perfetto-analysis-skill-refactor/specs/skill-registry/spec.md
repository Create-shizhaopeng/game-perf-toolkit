## MODIFIED Requirements

### Requirement: Skill Discovery Hook
The framework SHALL provide a new pluggy hook `register_skills()` that modules can optionally implement to return paths to their `SKILL.md` files, enabling framework-level skill discovery.

模块在实现 `register_skills()` 时，SHALL 支持返回包含子资源目录（如 YAML 技能文件、fragments、references）的 SKILL.md 路径。框架 SHALL 不对 SKILL.md 所在目录的子目录结构做限制。

#### Scenario: Module registers skill with YAML sub-resources
- **WHEN** a module implements `register_skills()` returning a path to a SKILL.md file
- **AND** the SKILL.md directory contains subdirectories like `atomic/`, `composite/`, `fragments/`
- **THEN** the framework registers the skill without error, and the sub-resources are accessible to Agents that read the SKILL.md and follow its references

#### Scenario: SKILL.md references YAML skill files
- **WHEN** a SKILL.md file references YAML skill files in its directory (e.g., `composite/jank_frame_detail.skill.yaml`)
- **THEN** Agents can read these YAML files by resolving paths relative to the SKILL.md location

### Requirement: Skill File Portability
SKILL.md files and their sub-directories (including YAML skill files, fragments, references) SHALL be self-contained and portable — they can be copied to any other Claude Code or Agent project and function independently without toolkit framework code.

YAML 技能文件中的 SQL 查询 SHALL 只依赖 `perfetto` Python 包和标准 PerfettoSQL 语法，不依赖 lv-game-toolkit 框架的任何模块。

#### Scenario: Skill directory standalone usage
- **WHEN** a perfetto-analysis SKILL.md file and its entire directory (atomic/, composite/, fragments/, etc.) are copied to a different project
- **THEN** an Agent in that project can read the SKILL.md, follow its index to YAML skill files, and execute SQL via any PerfettoSQL execution method without any toolkit dependencies
