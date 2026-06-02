# Agent Skill Tools

Skill 工具的统一生成，替换旧的 `SkillsManager.create_agent_tools()`，基于 Core SkillRegistry + SkillRouter。

## ADDED Requirements

### Requirement: build_skill_tools 函数生成全部 Skill 工具

`toolkit/agent/skill_tools.py` SHALL 提供 `build_skill_tools(skill_registry, router=None) -> list[ToolDefinition]`，生成以下 9 个工具：

- `skill_list` — 列出所有已注册 Skill 的元数据
- `skill_load` — 按名称加载指定 Skill 的 SKILL.md 全文
- `skill_load_resource` — 按路径加载 Skill 的子资源
- `skill_list_resources` — 列出 Skill 的子资源目录
- `kc_classify_document` — 分类文档内容
- `kc_match_skill` — 匹配内容到目标 Skill
- `kc_format_resource` — 格式化资源内容
- `kc_check_duplicate` — 检查重复内容
- `kc_write_resource` — 写入资源到 Skill 目录

#### Scenario: 生成基本 Skill 工具

- **WHEN** 调用 `build_skill_tools(registry)` 且 registry 中有已扫描的 Skill
- **THEN** 返回至少 4 个 ToolDefinition（skill_list/load/load_resource/list_resources）
- **AND** 每个 ToolDefinition 的 `method` 为可调用函数

#### Scenario: skill_list 返回已注册 Skill

- **WHEN** 调用 `skill_list()` 闭包且 registry 中有 perfetto-analysis 和 device-disguise
- **THEN** 返回字符串包含两个 Skill 的 name 和 description

#### Scenario: skill_load 加载指定 Skill

- **WHEN** 调用 `skill_load("perfetto-analysis")` 闭包
- **THEN** 返回 perfetto-analysis 的 SKILL.md 全文内容

### Requirement: SkillRouter 从旧模块移植

`toolkit/agent/skill_router.py` SHALL 从 `modules/agent_chat/src/skills/router.py` 移植 `SkillRouter` 类，改为引用 `toolkit.core.skill_registry.SkillMetadata`。

#### Scenario: SkillRouter 匹配已有 Skill

- **WHEN** 调用 `router.update_index(skills)` 后 `router.match("trace 卡顿分析", top_k=2)`
- **THEN** 返回包含 perfetto-analysis 的匹配结果，按相关度降序

### Requirement: 旧 SkillsManager 改为 compat shim

`modules/agent_chat/src/skills/manager.py` SHALL 改为委托到 `toolkit.core.skill_registry` + `toolkit.agent.skill_tools` 的兼容层。

#### Scenario: 旧测试通过 compat shim 创建 Skill 工具

- **WHEN** 旧测试代码调用 `SkillsManager(skill_search_paths).create_agent_tools()`
- **THEN** 返回与 `build_skill_tools(registry)` 等效的 ToolDefinition 列表
