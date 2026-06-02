# Test Plan: agent/skill_tools

**关联 Spec**: `openspec/changes/agent-wiring-fix/specs/agent-skill-tools/spec.md`
**测试文件**: `tests/test_agent_skill_tools.py`
**被测模块**: `toolkit/agent/skill_tools.py`, `toolkit/agent/skill_router.py`

## 测试目标

验证 `build_skill_tools()` 生成的 9 个 Skill 工具符合 DES-001 设计的 Progressive Disclosure 规范，以及 `SkillRouter` 的意图匹配功能正确。

## 前置条件

- `SkillRegistry` 已含 2 个测试 Skill（perfetto-analysis、device-disguise），每个有完整的 YAML frontmatter（name、description、tags、triggers）和 Markdown body
- `SkillRegistry` 空状态场景用空的 Registry 构建

## 测试用例

### 1. build_skill_tools — 基础工具生成

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_returns_at_least_4_tools` |
| **输入** | `build_skill_tools(registry)` — registry 含 2 个 Skill |
| **预期** | 返回 ≥4 个 ToolDefinition（skill_list/load/load_resource/list_resources） |
| **验证点** | 返回值类型为 `list[ToolDefinition]`；每个元素 `isinstance(ToolDefinition)` |

### 2. skill_list — 列出所有 Skill

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_skill_list_tool_returns_skill_names` |
| **输入** | 调用 `skill_list()` 闭包 |
| **预期** | 返回字符串包含 `"perfetto-analysis"` 和 `"device-disguise"` |
| **验证点** | Skill 的 name 和 description 出现在输出中 |

### 3. skill_load — 加载指定 Skill 内容

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_skill_load_tool_returns_content` |
| **输入** | 调用 `skill_load("perfetto-analysis")` |
| **预期** | 返回字符串包含 SKILL.md body 内容 `"Perfetto Analysis"` |
| **验证点** | Level 1 渐进式加载：获取 SKILL.md 全文 |

### 4. skill_load — 加载不存在的 Skill

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_skill_load_missing_returns_error` |
| **输入** | 调用 `skill_load("nonexistent")` |
| **预期** | 返回错误提示字符串（含 "不存在" 或 "加载失败"） |
| **验证点** | 错误路径处理，不抛异常 |

### 5. skill_list_resources — 列出子资源

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_skill_list_resources_tool` |
| **输入** | 调用 `skill_list_resources("perfetto-analysis")` |
| **预期** | 返回字符串（可能为空或含资源目录列表） |
| **验证点** | 返回值类型为 str，不抛异常 |

### 6. skill_load_resource — 加载不存在的子资源

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_skill_load_resource_nonexistent` |
| **输入** | 调用 `skill_load_resource("perfetto-analysis", "nonexistent/file.md")` |
| **预期** | 返回错误信息字符串 |
| **验证点** | Level 2 错误路径处理 |

### 7. 空 Registry 处理

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_empty_registry_returns_tools` |
| **输入** | `build_skill_tools(empty_registry)` |
| **预期** | 仍返回 ≥4 个工具；`skill_list` 输出提示无可用 Skill |
| **验证点** | 空状态不崩溃，优雅降级 |

### 8. SkillRouter — 导入验证

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_router_imports` |
| **输入** | 从 `toolkit.agent.skill_router` 导入 `SkillRouter` |
| **预期** | 成功导入，实例化返回非 None 对象 |
| **验证点** | 模块存在且类可实例化 |

### 9. SkillRouter — 意图匹配

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_router_match_returns_results` |
| **输入** | 用 2 个 Skill 更新索引 → `match("trace 卡顿分析", top_k=2)` |
| **预期** | 返回非空结果列表，每个元素为 `(SkillMetadata, float)` |
| **验证点** | 相关度排序，perfetto-analysis（含 trace/jank tags）排在前面 |

### 10. SkillRouter — 空查询

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_router_empty_query` |
| **输入** | `match("", top_k=2)` |
| **预期** | 返回空列表（无关键词无法匹配） |
| **验证点** | 边界条件不抛异常 |

## 覆盖的 Spec Requirements

| Spec 要求 | 测试用例 |
|-----------|---------|
| build_skill_tools 返回 ≥4 个 ToolDefinition | 1, 7 |
| skill_list 列出所有已注册 Skill | 2 |
| skill_load 返回 SKILL.md 全文 | 3 |
| skill_load 不存在的 Skill 返回错误 | 4 |
| skill_list_resources 返回子资源列表 | 5 |
| skill_load_resource 不存在的资源返回错误 | 6 |
| SkillRouter 导入和实例化 | 8 |
| SkillRouter 按关键词匹配 | 9 |
| SkillRouter 空查询不崩溃 | 10 |

## 不覆盖的内容

- curator 工具（kc_*）的 smoke test — 依赖于复杂的文档分类逻辑，由现有 `test_curator_tools.py` 和 `test_skills.py` 覆盖
- 性能测试 — 非本次范围
