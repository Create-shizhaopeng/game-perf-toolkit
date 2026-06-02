# Tasks: Agent Wiring Fix

> **进度: 49/50** (最后更新: 2026-06-02)
> 
> | 阶段 | 完成 | 待办 |
> |------|------|------|
> | 1. Skill 工具模块 | 5/5 | — |
> | 2. AgentOrchestrator | 5/5 | — |
> | 3. app.py 启动连线 | 6/6 | — |
> | 4. AgentPanel 重构 | 8/8 | — |
> | 5. AgentService 清理 | 3/3 | — |
> | 6. System Prompt | 3/3 | — |
> | 7. SkillRegistry 修正 | 3/3 | — |
> | 8. ToolRegistry 完善 | 2/2 | — |
> | 9. MCP Registry 修复 | 5/5 | — |
> | 10. Compat shim | 2/2 | — |
> | 11. 全量验证 | 7/8 | 11.8 (需 LLM API Key 手动 GUI 验证) |

## 1. 新建 Skill 工具模块

- [x] 1.1 Port `SkillRouter` from `modules/agent_chat/src/skills/router.py` to `toolkit/agent/skill_router.py`, change SkillMetadata import to `toolkit.core.skill_registry.SkillMetadata`
- [x] 1.2 Extract curator utility functions from `modules/agent_chat/src/skills/curator_tools.py` into `toolkit/agent/skill_tools.py` (classify_document, match_skill, format_resource, check_duplicate, write_resource)
- [x] 1.3 Implement `build_skill_tools(skill_registry, router=None) -> list[ToolDefinition]` in `toolkit/agent/skill_tools.py` — 4 base tools + 5 curator tools
- [x] 1.4 [P] Create `tests/test_agent_skill_tools.py` — test build_skill_tools returns 9 tools, test skill_list returns known skills, test skill_load returns content
- [x] 1.5 Verify: `python -m pytest tests/test_agent_skill_tools.py -v`

## 2. 增强 AgentOrchestrator

- [x] 2.1 Add `_register_skill_tools()` — generate skill_* tools from SkillRegistry + SkillRouter, register into ToolRegistry
- [x] 2.2 [P] Add `_register_builtin_tools()` — register `create_workspace` and `list_workspace_files`
- [x] 2.3 Add `init()` — calls `_register_skill_tools()` + `_register_builtin_tools()`
- [x] 2.4 Add `init_async()` — calls `mcp_registry.connect_all()` then refreshes `init_tools()`
- [x] 2.5 Modify `create_service(conversation_store=None)` — call `init_tools()` before creating AgentService, accept optional store parameter

## 3. 修复 app.py 启动连线

- [x] 3.1 In `run_gui()`: add `orchestrator.init()` before creating AgentPanel
- [x] 3.2 In `run_gui()`: schedule `orchestrator.init_async()` via QTimer after event loop starts
- [x] 3.3 In `run_mcp_server()`: replace `from modules.agent_chat.src.tools` imports with `from toolkit.core.tool_registry import tool_registry` singleton
- [x] 3.4 In `run_mcp_server()`: add orchestrator.init_tools() to register skill tools before MCP serve
- [x] 3.5 Add ToolRegistry and MCPRegistry to `_build_context()` dict
- [x] 3.6 Verify: `grep -rn "modules.agent_chat" toolkit/app.py` returns zero results

## 4. 简化 AgentPanel._ensure_service()

- [x] 4.1 Replace `_ensure_service()` body: create ConversationStore → `self._orch.create_service(conversation_store=self._store)` → `_flush_pending()`
- [x] 4.2 Remove all `modules.agent_chat` imports
- [x] 4.3 Remove local ToolRegistry/SkillsManager creation and manual skill tool registration
- [x] 4.4 [P] Declare signals: `panel_expanded = pyqtSignal()`, `panel_collapsed = pyqtSignal()`, `message_sent = pyqtSignal(str)`
- [x] 4.5 [P] Emit `panel_expanded` in `_expand()`, `panel_collapsed` in `_collapse()`
- [x] 4.6 Implement drag-to-resize: connect to RightPanel's existing `_ResizeHandle.width_changed`, clamp to 240-480px
- [x] 4.7 Add session selector: QComboBox for history sessions + "新建" button above message area
- [x] 4.8 Rename `self._ctx` to `self._tool_registry` or remove unused attribute

## 5. 清理 AgentService

- [x] 5.1 Change `skills_manager: SkillsManager | None = None` to `skills_manager: Any | None = None`
- [x] 5.2 [P] Change `sop_manager: SOPManager | None = None` to `sop_manager: Any | None = None`
- [x] 5.3 [P] Add `from toolkit.core.tool_executor import ToolExecutor` import (already done in prior fix, verify)

## 6. System Prompt 完善

- [x] 6.1 Add `report_index: ReportIndex | None = None` parameter to `build_system_prompt()` and `_build_stable_prompt()`
- [x] 6.2 [P] Inject `conv_id` into `_build_volatile_prompt()` output: `[Session: {conv_id}] [Time: {ts}]`
- [x] 6.3 Wire `report_index` into Stable layer when not None: append recent report context (max 500 chars)

## 7. SkillRegistry 修正

- [x] 7.1 Change `SkillMetadata.triggers` type from `dict[str, Any]` to `list[str]`, update `_parse_skill()` to extract list
- [x] 7.2 [P] Update `search()` to match against triggers keywords in addition to name/description/tags
- [x] 7.3 [P] Add `get_content(name)` as alias for `get_skill_content(name)`

## 8. ToolRegistry 完善

- [x] 8.1 Make `_enhance_schema` a method on `ToolRegistry` class (not module-level), add `dispatch(name, args)` convenience method
- [x] 8.2 Verify `dispatch` returns JSON string result

## 9. MCP Registry 修复

- [x] 9.1 Implement `register_local()` — introspect handler_class, register `mcp__{module}__{method}` tools into ToolRegistry
- [x] 9.2 [P] Implement `register_remote()` — create MCPServerConfig, store for later connection via connect_all()
- [x] 9.3 Remove auto-persist from `register_external()` and `register_remote()` (keep in add_server/remove_server)
- [x] 9.4 [P] Create `tests/test_core_mcp_registry.py` — test register_local creates tools, test register_remote stores config
- [x] 9.5 Verify: `python -m pytest tests/test_core_mcp_registry.py -v`

## 10. Compat shim

- [x] 10.1 Update `modules/agent_chat/src/skills/manager.py` to delegate `create_agent_tools()` to `toolkit.agent.skill_tools.build_skill_tools()`
- [x] 10.2 Run `python -m pytest modules/agent_chat/tests/ -q --tb=no` — 37 passed (test_no_executor_returns_error 修复适配新 AgentConfig)

## 11. 全量验证

- [x] 11.1 Syntax check: all modified files parse without error
- [x] 11.2 Import check: `from toolkit.app import run_gui, run_mcp_server` succeeds
- [x] 11.3 Zero reverse deps: `grep -rn "modules.agent_chat" toolkit/ --include="*.py" | grep -v migration.py` → empty
- [x] 11.4 Skill tools: `build_skill_tools()` returns 9 tools from perfetto-analysis + device-disguise skills
- [x] 11.5 MCP registry: `register_local()` creates tools with correct `mcp__` prefix
- [x] 11.6 Unit tests: all test files pass (`test_agent_skill_tools.py`, `test_core_mcp_registry.py`, existing agent_chat tests)
- [x] 11.7 GUI startup: 无头启动链路验证通过 — context/build/plugins/orchestrator/service 全链路 OK（24 tools, 7 plugins）
- [ ] 11.8 Agent panel: expand → send message → receive streaming reply with tool call feedback (需 LLM API Key 手动验证)
