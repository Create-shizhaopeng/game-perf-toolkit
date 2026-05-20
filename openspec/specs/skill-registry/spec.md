## ADDED Requirements

### Requirement: Skill Discovery Hook
The framework SHALL provide a new pluggy hook `register_skills()` that modules can optionally implement to return paths to their `SKILL.md` files, enabling framework-level skill discovery.

#### Scenario: Module registers skills
- **WHEN** a module implements `register_skills()` returning a list of SKILL.md file paths
- **THEN** the framework collects these paths into the `SkillRegistry`

#### Scenario: Module does not register skills
- **WHEN** a module does not implement `register_skills()` or returns an empty list
- **THEN** the framework continues without error; no skills are registered for that module

### Requirement: Skill Registry
The system SHALL maintain a `SkillRegistry` that loads SKILL.md files, parses their YAML frontmatter, and makes skill metadata available for Agent discovery and triggering.

#### Scenario: Skill metadata extraction
- **WHEN** a SKILL.md file is loaded
- **THEN** the registry extracts name, description, trigger keywords, and category from the YAML frontmatter

#### Scenario: Skill content retrieval
- **WHEN** an Agent requests the full content of a registered skill
- **THEN** the registry returns the complete SKILL.md file content as a string

### Requirement: Skill File Portability
SKILL.md files and their `references/` subdirectories SHALL be self-contained and portable — they can be copied to any other Claude Code or Agent project and function independently without toolkit framework code.

#### Scenario: Skill file standalone usage
- **WHEN** a SKILL.md file and its references directory are copied to a different project
- **THEN** an Agent in that project can read and follow the skill's workflow without any toolkit dependencies
