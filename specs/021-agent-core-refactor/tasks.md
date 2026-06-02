# Tasks: Agent 核心重构

**Input**: Design documents from `/specs/021-agent-core-refactor/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/service-api.md

**Tests**: No new tests requested. Existing tests must remain passing (SC-006).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- `toolkit/core/` — Framework core services (registries, MCP)
- `toolkit/agent/` — Agent engine (orchestrator, service, GUI)
- `toolkit/gui/` — Framework GUI (main window)
- `modules/<name>/` — Business modules

---

## Phase 1: Setup (准备与兼容层)

**Purpose**: 定义新的目录路径，创建 re-export 兼容层，确保现有 agent_chat 模块在迁移期间可继续运行。

- [x] T001 Create `toolkit/core/mcp/` directory with `__init__.py` at toolkit/core/mcp/__init__.py
- [x] T002 [P] Create `toolkit/agent/` directory skeleton with `__init__.py` at toolkit/agent/__init__.py
- [x] T003 [P] Create `toolkit/agent/gui/` directory with `__init__.py` at toolkit/agent/gui/__init__.py
- [x] T004 [P] Create `toolkit/agent/memory/` directory with `__init__.py` at toolkit/agent/memory/__init__.py
- [x] T005 [P] Create `toolkit/agent/knowledge/` directory with `__init__.py` at toolkit/agent/knowledge/__init__.py
- [x] T006 [P] Create `toolkit/agent/workflow/` directory with `__init__.py` at toolkit/agent/workflow/__init__.py

**Checkpoint**: Directory structure ready for code migration.

---

## Phase 2: Foundational — Core 基础设施下沉 (Phase 1 of spec)

**Purpose**: 将 ToolRegistry、ToolExecutor、核心模型、MCP 组件提升到 `toolkit/core/`，消除循环依赖。**此阶段完成后 US1/US2/US3 才能开始。**

**⚠️ CRITICAL**: 所有任务必须在现有 agent_chat 测试保持通过的前提下完成。

### 2.1: 核心模型提取

- [x] T007 Extract `ToolCall`, `ToolResult`, `ToolCallStatus` dataclass models from modules/agent_chat/src/models.py into toolkit/core/models.py. Re-export from old location via `from toolkit.core.models import *`
- [x] T008 [P] Move `ToolDefinition` from toolkit/core/llm/base.py into toolkit/core/models.py (consolidate with T007). Update `toolkit/core/llm/base.py` to re-export
- [x] T009 Update `toolkit/core/mcp_server.py` to import `ToolCall` from `toolkit.core.models` instead of `modules.agent_chat.src.models`

### 2.2: ToolRegistry + ToolExecutor 提升

- [x] T010 Move `modules/agent_chat/src/tools/registry.py` → `toolkit/core/tool_registry.py`. Add `toolset` field to ToolEntry. Keep re-export in old path
- [x] T011 Move `modules/agent_chat/src/tools/executor.py` → `toolkit/core/tool_executor.py`. Update import to `from toolkit.core.tool_registry import ToolRegistry`. Keep re-export in old path
- [x] T012 Update `toolkit/core/mcp_server.py` to import `ToolRegistry`/`ToolExecutor` from `toolkit.core` instead of `modules.agent_chat.src.tools`
- [x] T013 [P] Update all agent_chat internal imports: `modules/agent_chat/src/service.py` to use `toolkit.core.tool_registry` and `toolkit.core.tool_executor`
- [x] T014 [P] Update all agent_chat internal imports: `modules/agent_chat/src/skills/manager.py` to use `toolkit.core.models.ToolDefinition`
- [x] T015 Verify `tk.core.mcp_server` has zero imports from `modules.agent_chat`. Run `python -m pytest tests/ -k "mcp" -v`

### 2.3: MCP Framework 统一

- [x] T016 Move `modules/agent_chat/src/mcp/connection.py` → `toolkit/core/mcp/client.py`. Keep `ConnectionPool` class name unchanged. Update internal imports to `toolkit.core.models`
- [x] T017 [P] Move `modules/agent_chat/src/mcp/tool_bridge.py` → `toolkit/core/mcp/tool_bridge.py`. Update import path to `toolkit.core.mcp.client`
- [x] T018 [P] Move `modules/agent_chat/src/mcp/manager.py` → `toolkit/core/mcp/registry.py`. Rename `MCPManager` → `MCPRegistry`. Add `register_local()` method. Update internal imports
- [x] T019 Move `toolkit/core/mcp_server.py` into `toolkit/core/mcp/server.py`. Delete `toolkit/core/mcp_server.py`. Update `toolkit/app.py` import for `run_mcp_server`
- [x] T020 [P] Add re-export compatibility layer: `modules/agent_chat/src/mcp/connection.py` → `from toolkit.core.mcp.client import *`
- [x] T021 [P] Add re-export compatibility layer: `modules/agent_chat/src/mcp/manager.py` → `from toolkit.core.mcp.registry import *`
- [x] T022 [P] Add re-export compatibility layer: `modules/agent_chat/src/mcp/tool_bridge.py` → `from toolkit.core.mcp.tool_bridge import *`

### 2.4: SkillRegistry 增强

- [x] T023 Enhance `toolkit/core/skill_registry.py`: add `add_search_path(path: Path)` method that recursively scans subdirectories for SKILL.md files
- [x] T024 [P] Enhance `toolkit/core/skill_registry.py`: add `scan()` method that refreshes the skill index from all registered search paths
- [x] T025 [P] Enhance `toolkit/core/skill_registry.py`: add `get_resource(name, rel_path)` and `list_resources(name)` methods for sub-resource access
- [x] T026 Merge `modules/agent_chat/src/skills/discovery.py` YAML parsing logic into `toolkit/core/skill_registry.py`. Update agent_chat skills code to use `toolkit.core.skill_registry.SkillRegistry`. Delete discovery.py after merge
- [x] T027 Add `data/sops/` as default search path in SkillRegistry so existing SOP documents are discovered as Skills

### 2.5: 验证

- [x] T028 Run full test suite: `python scripts/run_all_tests.py`. All 289 agent_chat tests + other module tests must pass
- [x] T029 Verify FR-005: Launch GUI (`python -m toolkit.app`), confirm Agent tab still loads and responds to messages (functionality preserved during Phase 1 migration)

**Checkpoint**: Core infrastructure in place, zero reverse dependencies from core → modules/agent_chat, all tests pass.

---

## Phase 3: User Story 1 — Agent 作为右侧面板辅助分析 (Priority: P1) 🎯 MVP

**Goal**: Agent 从 `modules/agent_chat/` 提升为 `toolkit/agent/`；GUI 从中央 Tab 改为右侧面板；System Prompt 三段式重构；SOP 合并到 Skill。

**Independent Test**: 启动 GUI → 展开右侧 Agent 面板 → 输入分析请求 → Agent 自主加载 Skill 并调用工具 → 流式返回结果。

### 3.1: Agent 目录迁移

- [x] T030 [US1] Move `modules/agent_chat/src/service.py` → `toolkit/agent/service.py`. Update all imports to use `toolkit.core.*`. Rename class AgentService stays
- [x] T031 [P] [US1] Move `modules/agent_chat/src/memory/conversation.py` → `toolkit/agent/memory/conversation.py`. Update imports
- [x] T032 [P] [US1] Move `modules/agent_chat/src/knowledge/report_index.py` → `toolkit/agent/knowledge/report_index.py`. Update imports
- [x] T033 [P] [US1] Move `modules/agent_chat/src/workflow/tracker.py` → `toolkit/agent/workflow/tracker.py`. Update imports
- [x] T034 [P] [US1] Move `modules/agent_chat/src/workflow/generator.py` → `toolkit/agent/workflow/generator.py`. Update output format to SKILL.md
- [x] T035 [P] [US1] Move `modules/agent_chat/src/models.py` → `toolkit/agent/models.py`. Remove already-extracted core models (ToolCall/ToolResult/ToolDefinition). Keep AgentConfig, Message, Conversation, SkillMetadata, SubAgentConfig, SubAgentResult
- [x] T036 [P] [US1] Move `modules/agent_chat/src/strings_gui.py` → `toolkit/agent/strings_gui.py`. Update imports
- [x] T037 [US1] Move `modules/agent_chat/src/plugin.py` → `toolkit/agent/__init__.py` as AgentPlugin class. Rename `AgentChatPlugin` → `AgentPlugin`

### 3.2: AgentOrchestrator

- [x] T038 [US1] Create `toolkit/agent/orchestrator.py` with AgentOrchestrator class. Implement `init_tools()` that builds unified tool view from ToolRegistry + Skill tools. Implement `create_service()` and `on_provider_changed()`
- [x] T039 [US1] Implement AgentOrchestrator.build_system_prompt() → delegate to system_prompt.py (T040)

### 3.3: System Prompt 三段式

- [x] T040 [US1] Create `toolkit/agent/system_prompt.py`. Implement `build_system_prompt(tools, skills, language, extra, report_index)` returning Stable + Context + Volatile joined string
- [x] T041 [US1] Implement `_build_stable_prompt()`: identity + tool summary + skill index + usage guidance. Max 3000 chars
- [x] T042 [P] [US1] Implement `_build_context_prompt()`: user-supplied context files + extra system_message
- [x] T043 [P] [US1] Implement `_build_volatile_prompt()`: memory snapshot + timestamp + session ID

### 3.4: AgentService 重构

- [x] T044 [US1] Refactor `toolkit/agent/service.py` AgentService.__init__: remove internal `_init_provider()` fallback logic. Use `LLMManager.get_provider()` exclusively (FR-009)
- [x] T045 [US1] Refactor AgentService._build_system_prompt(): replace monolithic prompt with call to `system_prompt.build_system_prompt()`
- [x] T046 [US1] Remove `_resolve_api_key()`, `_smart_truncate()`, `_trim_system_prompt()` from AgentService (moved to system_prompt.py or deleted)

### 3.5: SOP → Skill 合并

- [x] T047 [US1] Refactor `toolkit/agent/workflow/generator.py` `generate_sop_from_trace()` to output SKILL.md format (YAML frontmatter + Markdown body) instead of old SOP format
- [x] T048 [US1] Refactor `toolkit/agent/workflow/tracker.py` WorkflowTracker to emit "save as new Skill" event instead of "save as new SOP". Update `check_deposit_condition()` result message
- [x] T049 [US1] Move `modules/agent_chat/src/sop/manager.py` logic into `toolkit/core/skill_registry.py` (just the SOP import path). Delete `modules/agent_chat/src/sop/`

### 3.6: SubAgent 清理

- [x] T050 [US1] Delete `modules/agent_chat/src/subagent/manager.py`. Keep `SubAgentConfig` and `SubAgentResult` models in `toolkit/agent/models.py`
- [x] T051 [US1] Add `spawn_subagent(config: SubAgentConfig) -> SubAgentResult` stub method to AgentOrchestrator that raises `NotImplementedError`

### 3.7: AgentPanel GUI (右侧面板)

- [x] T052 [US1] Create `toolkit/agent/gui/agent_panel.py` with AgentPanel(QWidget) class. Implement collapsed (24px narrow bar + icon) and expanded (~360px) states
- [x] T053 [US1] Port message rendering widgets from `modules/agent_chat/src/gui_tab.py` into `toolkit/agent/gui/agent_panel.py`: `_UserMessageWidget`, `_AgentTextWidget`, `_ToolCallCard`, `_TokenUsageLabel`
- [x] T054 [US1] Implement AgentPanel input bar: `_ChatInput` (adaptive height text edit, Enter to send, Shift+Enter newline) + Send button. Wire to AgentWorker thread for async execution
- [x] T055 [US1] Implement AgentPanel session selector: compact dropdown/tabs for conversation history (simplified from current `_ScrollableTabBar` system)
- [x] T056 [US1] Implement AgentPanel theme support via `set_theme(theme: str)` method using `theme_colors.get_colors()`. Add objectName `agentPanel` for global QSS in styles.py. Ensure panel expand/collapse transition animation ≤ 300ms (SC-007)
- [x] T057 [US1] Add AgentPanel QSS styles to `toolkit/gui/styles.py`: `#agentPanel`, `#agentPanelMsgScroll`, `#agentPanelInputBar`, `#agentPanelConvBar`

### 3.8: MainWindow 集成

- [x] T058 [US1] Modify `toolkit/gui/main_window.py`: remove `set_agent_panel()` method. Replace with `self._right_panel.set_widget(agent_panel)`
- [x] T059 [US1] Modify `toolkit/app.py` `run_gui()`: instantiate AgentOrchestrator with context → create AgentPanel(orchestrator) → add to right_panel. Remove special agent_tab handling in tab registration loop

### 3.9: 插件入口更新

- [x] T060 [US1] Update `toolkit/agent/__init__.py` (AgentPlugin): `get_plugin_info()` display_name stays "Agent 智能助手", name changes to "agent". `register_gui_tab()` returns None. Add `register_right_panel()` returning AgentPanel
- [x] T061 [US1] Update `toolkit/app.py` `_build_context()`: add `tool_registry` (ToolRegistry singleton) and `mcp_registry` (MCPRegistry instance) to context dict

### 3.10: 清理旧代码

- [x] T062 [US1] Delete `modules/agent_chat/` directory and its `manifest.json`
- [x] T063 [US1] Remove all re-export compatibility layers created in Phase 1 (`modules/agent_chat/src/tools/registry.py`, `executor.py`, `mcp/` re-exports)

### 3.11: 验证

- [x] T064 [US1] Run full test suite. Update any test import paths that referenced `modules.agent_chat`. All tests must pass (SC-006)
- [x] T065 [US1] Manual GUI test: launch app, verify no "Agent" in left nav, expand right panel, send message, verify streaming reply starts within 5 seconds (SC-001), verify tool call cards render

**Checkpoint**: US1 complete — Agent works as right panel with unified tool view and three-tier system prompt.

---

## Phase 4: User Story 2 — 模块通过 Skill 文档暴露能力 (Priority: P2)

**Goal**: `perfetto_analysis` 模块通过 SKILL.md 暴露能力，不再直接注册裸方法。验证 Skill 发现→加载→使用的完整链路。

**Independent Test**: App 启动后 `SkillRegistry` 包含 `perfetto-analysis` Skill → Agent System Prompt 包含该 Skill 摘要 → Agent 能按需加载 SKILL.md 全文。

- [x] T066 [US2] Create `modules/perfetto_analysis/skills/perfetto-analysis/` directory
- [x] T067 [US2] Write `modules/perfetto_analysis/skills/perfetto-analysis/SKILL.md` with YAML frontmatter (name, description, tags: [perfetto, trace, jank, fps], triggers, platforms) and Markdown body documenting analysis methods and tool usage
- [x] T068 [US2] Update `modules/perfetto_analysis/src/plugin.py`: `register_skills()` returns path to SKILL.md. `register_agent_tools()` returns empty list (FR-015)
- [x] T069 [US2] Verify `device_disguise` module's existing Skill at `modules/device_disguise/skills/device-disguise/SKILL.md` is correctly discovered by enhanced SkillRegistry on startup

**Checkpoint**: US2 complete — Module capabilities exposed via Skill documents, not bare methods.

---

## Phase 5: User Story 3 — 外部 MCP 服务扩展 Agent 能力 (Priority: P3)

**Goal**: MCPRegistry 自动连接已配置的外部 MCP Server，工具注入 ToolRegistry。

**Independent Test**: 配置 MCP Server → 启动 → Agent 工具列表包含 `mcp__{server}__{tool}` → Agent 能调用并返回结果。

- [x] T070 [US3] Enhance `toolkit/core/mcp/registry.py` MCPRegistry: implement `connect_all()` that iterates enabled servers and connects in parallel, injecting tools into ToolRegistry via `register_mcp_tools()`
- [x] T071 [US3] Enhance `toolkit/core/mcp/registry.py` MCPRegistry: implement error handling — connection failure logs warning, does not block startup (FR-003 acceptance scenario 2)
- [x] T072 [US3] Add MCP tool prefix convention: external tools register as `mcp__{server_name}__{tool_name}` in ToolRegistry. Implement in `toolkit/core/mcp/tool_bridge.py`
- [x] T073 [US3] Wire `MCPRegistry.connect_all()` into `AgentOrchestrator.init_tools()` so MCP tools appear in unified tool view
- [x] T074 [US3] Verify end-to-end: configure a simple test MCP server (e.g., `mcp-everything` or an echo server) in `data/config/mcp_servers.json` → launch app → Agent can call `mcp__{test_server}__{tool}` and receive result

**Checkpoint**: US3 complete — External MCP tools available alongside built-in tools.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup, Edge case handling, Documentation.

- [x] T075 Run full test suite and verify SC-006 (100% test pass rate). Fix any regressions
- [x] T076 Verify SC-004: Run `grep -r "modules.agent_chat" toolkit/core/` — should return zero results
- [x] T077 Verify SC-002: Run SkillRegistry.scan() and confirm all registered Skills are discovered (100% coverage)
- [x] T078 Update `docs/PROGRESS.md` to reflect Agent core refactor completion
- [x] T079 Run `quickstart.md` validation script and verify all steps succeed
- [x] T080 Update `toolkit/agent/models.py` AgentConfig: remove deprecated LLM fields (provider, api_key, model_name, max_tokens, temperature, smart_switch, claude_api_key, glm_api_key). Depend fully on LLMManager (FR-016)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (directories created) — **BLOCKS all user stories**
- **Phase 3 (US1)**: Depends on Phase 2 completion. No dependency on US2/US3
- **Phase 4 (US2)**: Depends on Phase 2 completion. Independent of US1/US3
- **Phase 5 (US3)**: Depends on Phase 2 completion. Independent of US1/US2
- **Phase 6 (Polish)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: After Phase 2. No dependencies on other stories
- **US2 (P2)**: After Phase 2. May reference US1's SkillRegistry enhancement but independently testable
- **US3 (P3)**: After Phase 2. May reference US1's ToolRegistry but independently testable

### Within Phase 2 (Foundational)

```
T007 (models) ──→ T009 (mcp_server fix)
            ──→ T010,T011 (tool_registry, tool_executor) ──→ T012,T013,T014
T007 ──→ T016,T017,T018 (MCP components) ──→ T019,T020,T021,T022
T023,T024,T025 ──→ T026,T027 (SkillRegistry merge)
                                    ──→ T028,T029 (verify)
```

### Within Phase 3 (US1)

```
T030,T031,T032,T033,T034,T035,T036,T037 (move files, all [P])
    ──→ T038,T039 (AgentOrchestrator)
    ──→ T040,T041,T042,T043 (System Prompt, [P] within group)
    ──→ T044,T045,T046 (AgentService refactor)
    ──→ T047,T048,T049 (SOP merge)
    ──→ T050,T051 (SubAgent cleanup)
    ──→ T052,T053,T054,T055,T056,T057 (AgentPanel GUI)
    ──→ T058,T059 (MainWindow integration)
    ──→ T060,T061 (plugin entry update)
    ──→ T062,T063 (cleanup old code)
    ──→ T064,T065 (verify)
```

### Parallel Opportunities

- All Phase 1 tasks (T001-T006): **6 parallel tasks**
- All Phase 2 core model tasks (T007-T009): serial due to dependency
- Phase 2 MCP tasks (T016-T022): T016→T017,T018 (can parallelize T017,T018)
- Phase 3 file moves (T030-T037): **8 parallel tasks** (different source files)
- Phase 3 System Prompt sub-tasks (T041,T042,T043): **3 parallel tasks**
- Phase 3 AgentPanel GUI (T053-T057): **5 parallel tasks** (different widgets)
- US1, US2, US3 can run in parallel after Phase 2 (if multiple developers)

---

## Parallel Example: Phase 3 Agent 文件迁移

```bash
# All independent file moves can run together:
Task: "Move service.py → toolkit/agent/service.py" (T030)
Task: "Move memory/conversation.py → toolkit/agent/memory/" (T031)
Task: "Move knowledge/report_index.py → toolkit/agent/knowledge/" (T032)
Task: "Move workflow/tracker.py → toolkit/agent/workflow/" (T033)
Task: "Move workflow/generator.py → toolkit/agent/workflow/" (T034)
Task: "Move models.py → toolkit/agent/models.py" (T035)
Task: "Move strings_gui.py → toolkit/agent/strings_gui.py" (T036)
Task: "Move plugin.py → toolkit/agent/__init__.py" (T037)
```

---

## Implementation Strategy

### MVP First (Phase 2 + Phase 3 = US1 Only)

1. Complete Phase 1: Setup (T001-T006)
2. Complete Phase 2: Foundational (T007-T029) — **CRITICAL GATE**
3. Complete Phase 3: US1 (T030-T065)
4. **STOP and VALIDATE**: Test US1 independently per acceptance scenarios
5. Agent works as right panel — **MVP ready**

### Incremental Delivery

1. Phases 1+2 → Core infrastructure ready, agent_chat still functional via re-exports
2. Phase 3 (+ US1) → Agent as right panel, three-tier prompt, SOP merged **← MVP**
3. Phase 4 (+ US2) → Module capabilities via Skill documents
4. Phase 5 (+ US3) → External MCP integration
5. Phase 6 → Polish, cleanup, docs update

### Risk Mitigation

- **T028 (full test run)**: Run after EVERY Phase 2 sub-group, not just at the end
- **T029 (GUI smoke test)**: Manual verification after Phase 2 to catch imports/rendering issues early
- **re-export layers**: T020-T022 ensure old code paths work during transition. Remove in T063 only after US1 is complete and verified

---

## Notes

- [P] tasks = different files, no dependencies — can run in parallel
- [US*] label maps task to spec user story for traceability
- Each checkpoint is a valid stopping point for validation
- All tasks reference exact file paths for immediate execution
- SC-004 (zero reverse deps) is verified at T076; SC-006 (test pass) at T075
- Phase 2 is the highest risk section — keep re-export layers until Phase 3 verified
