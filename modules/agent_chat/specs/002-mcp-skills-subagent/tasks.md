# Tasks: MCP 管理、Skills 扩展管理、Sub-agent 支持

**Input**: Design documents from `modules/agent_chat/specs/002-mcp-skills-subagent/`
**Prerequisites**: plan.md (required), spec.md (required), ui-design.md (required)

**Organization**: Tasks grouped by User Story，支持独立实现和测试。

## 目录

- [Phase 1: Setup](#phase-1-setup)
- [Phase 2: Foundational — 异步架构改造](#phase-2-foundational--异步架构改造)
- [Phase 3: US1 — MCP 服务器管理 (P1)](#phase-3-us1--mcp-服务器管理-p1--mvp)
- [Phase 4: US2+US4 — Skills 管理 + SOP 移除 (P1/P2)](#phase-4-us2us4--skills-管理--sop-移除-p1p2)
- [Phase 5: US2 (续) — knowledge-curator Skill](#phase-5-us2-续--knowledge-curator-skill)
- [Phase 6: US3 — Sub-agent 编排 (P2)](#phase-6-us3--sub-agent-编排-p2)
- [Phase 7: US5 — 001 缺口修复 + 打包支持 (P3)](#phase-7-us5--001-缺口修复--打包支持-p3)
- [Phase 8: Polish & Testing](#phase-8-polish--testing)
- [Dependencies & Execution Order](#dependencies--execution-order)
- [Implementation Strategy](#implementation-strategy)
- [Notes](#notes)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Feature branch and dependency preparation

- [x] T001 Create feature branch `002-mcp-skills-subagent` from dev
- [x] T002 Install async dependencies: `pytest-asyncio`, `mcp>=1.26.0` in `pyproject.toml`

**Checkpoint**: Dependencies installed, branch ready

---

## Phase 2: Foundational — 异步架构改造

**Purpose**: agent_chat 内部全面异步化，BLOCKS all user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Refactor `LLMProvider.stream_chat()` to return `AsyncIterator[StreamChunk]` in `modules/agent_chat/src/llm/base.py`
- [x] T004 [P] Adapt `GlmProvider` to async in `modules/agent_chat/src/llm/glm_provider.py`
- [x] T005 [P] Adapt `ClaudeProvider` to async in `modules/agent_chat/src/llm/claude_provider.py`
- [x] T006 Refactor `ToolExecutor.execute()` to `async def` with `asyncio.to_thread()` bridge in `modules/agent_chat/src/tools/executor.py`
- [x] T007 Refactor `AgentService.chat()` to `async def` in `modules/agent_chat/src/service.py`
- [x] T008 [P] Adapt CLI entry to `asyncio.run()` in `modules/agent_chat/src/cli_commands.py`
- [x] T009 [P] Adapt GUI `_AgentWorker` to run async event loop in QThread in `modules/agent_chat/src/gui_tab.py`
- [x] T010 Migrate all existing tests to `pytest-asyncio` in `modules/agent_chat/tests/`

**Checkpoint**: All existing functionality works asynchronously, tests pass

---

## Phase 3: US1 — MCP 服务器管理 (P1) 🎯 MVP

**Goal**: Agent 能通过配置文件声明 MCP 服务器，自动连接并透明调用 MCP 工具

**Independent Test**: 配置 perfetto-mcp 后，Agent 能发现并调用其工具

- [x] T011 [P] [US1] Create `MCPServerConfig`, `MCPConnectionStatus`, `MCPConnection` models in `modules/agent_chat/src/models.py`
- [x] T012 [P] [US1] Create `data/mcp_servers.json` config schema and parser in `modules/agent_chat/src/mcp/__init__.py`
- [x] T013 [US1] Implement `MCPManager` (ServerRegistry + ConnectionPool) in `modules/agent_chat/src/mcp/manager.py`
- [x] T014 [US1] Implement `MCPManager.connect()` with stdio/SSE transport in `modules/agent_chat/src/mcp/connection.py`
- [x] T015 [US1] Implement `ToolBridge` (MCP JSON Schema → ToolDefinition) in `modules/agent_chat/src/mcp/tool_bridge.py`
- [x] T016 [US1] Integrate MCP tools into ToolRegistry + `local_` prefix degradation in `modules/agent_chat/src/tools/registry.py`
- [x] T017 [US1] Implement SDK version check mechanism in `modules/agent_chat/src/mcp/__init__.py`
- [x] T018 [US1] Implement MCP management GUI panel (Tab 4) in `modules/agent_chat/src/gui_tab.py`

**Checkpoint**: MCP 服务器可配置、连接、工具可被 Agent 调用，断开时自动降级

---

## Phase 4: US2+US4 — Skills 管理 + SOP 移除 (P1/P2)

**Goal**: SkillsManager 替代 SOPManager，Agent 通过 Skill 获取领域知识并自主编排

**Independent Test**: 移除所有 SOP 后，Agent 通过 `perfetto-analysis` Skill 完成 trace 分析

- [x] T019 [P] [US2] Create `SkillMetadata`, `SkillContext` models in `modules/agent_chat/src/models.py`
- [x] T020 [US2] Implement `SkillDiscovery` (search path scanning + YAML frontmatter parsing) in `modules/agent_chat/src/skills/discovery.py`
- [x] T021 [US2] Implement `SkillRouter` (TF-IDF/keyword intent matching) in `modules/agent_chat/src/skills/router.py`
- [x] T022 [US2] Implement `SkillLoader` (3-level progressive loading) in `modules/agent_chat/src/skills/loader.py`
- [x] T023 [P] [US2] Register `skill_load_resource` and `skill_list` Agent tools via `SkillsManager.create_agent_tools()`
- [ ] T024 [US4] Remove SOPManager code: delete `modules/agent_chat/src/sop/` directory (deferred to Phase 8)
- [ ] T025 [US4] Remove `SOPDocument` and `SOPSource` from `modules/agent_chat/src/models.py` (deferred to Phase 8)
- [ ] T026 [US4] Remove all SOP files from `modules/agent_chat/assets/sops/` and `modules/agent_chat/data/sops/` (deferred to Phase 8)
- [x] T027 [US4] Update `service.py` — integrate SkillsManager alongside SOPManager in `modules/agent_chat/src/service.py`
- [x] T028 [US4] Update `gui_tab.py` — replace SOP panel with Knowledge Management in `modules/agent_chat/src/gui_tab.py`
- [ ] T029 [US4] Update `cli_commands.py` — remove SOP references in `modules/agent_chat/src/cli_commands.py` (deferred to Phase 8)
- [x] T030 [US2] Implement Skill management GUI panel (MCP Tab in settings) in `modules/agent_chat/src/gui_tab.py`
- [x] T031 [US2] Implement left panel Knowledge Management (Skill list + sub-resources) in `modules/agent_chat/src/gui_tab.py`

**Checkpoint**: SOPManager 完全移除，SkillsManager 管理所有知识资产，GUI 左侧面板显示 Skill 列表

---

## Phase 5: US2 (续) — knowledge-curator Skill

**Goal**: 用户可导入原始文档，Skill 自动分类、匹配、格式化并写入目标 Skill 子资源

**Independent Test**: 导入一份原始分析文档后，正确分类并写入 perfetto-analysis Skill 目录

- [x] T032 [US2] Finalize `knowledge-curator` SKILL.md content in `modules/agent_chat/skills/knowledge-curator/SKILL.md`
- [x] T033 [P] [US2] Implement `kc_classify_document` tool in `modules/agent_chat/src/skills/curator_tools.py`
- [x] T034 [P] [US2] Implement `kc_match_skill` tool in `modules/agent_chat/src/skills/curator_tools.py`
- [x] T035 [US2] Implement `kc_format_resource` tool in `modules/agent_chat/src/skills/curator_tools.py`
- [x] T036 [US2] Implement `kc_check_duplicate` tool in `modules/agent_chat/src/skills/curator_tools.py`
- [x] T037 [US2] Implement `kc_write_resource` tool in `modules/agent_chat/src/skills/curator_tools.py`
- [ ] T038 [US2] Add curator preview card to message area UI in `modules/agent_chat/src/gui_tab.py` (deferred to Phase 8)
- [ ] T039 [US2] Add "Import Document" quick action to welcome page in `modules/agent_chat/src/gui_tab.py` (deferred to Phase 8)

**Checkpoint**: knowledge-curator Skill 端到端可用，从文档导入到子资源写入全流程验证

---

## Phase 6: US3 — Sub-agent 编排 (P2)

**Goal**: 主 Agent 可创建独立子 Agent，上下文隔离，返回结构化摘要

**Independent Test**: 主 Agent 创建子 Agent 分析一个 trace，子 Agent 返回结论摘要而非原始数据

- [x] T040 [P] [US3] Create `SubAgentConfig`, `SubAgentResult`, `SubAgentStatus` models in `modules/agent_chat/src/models.py`
- [x] T041 [P] [US3] Create `ProviderCapabilities` model in `modules/agent_chat/src/models.py`
- [x] T042 [US3] Implement `SubAgentManager` (creation + execution + 3-retry + result collection) in `modules/agent_chat/src/subagent/manager.py`
- [x] T043 [US3] Implement `AgentFactory` logic inside `SubAgentManager._execute()` (independent LLM sessions + tool filtering)
- [x] T044 [US3] Implement `ResultCollector` logic inside `SubAgentManager._extract_summary()` (structured summary extraction)
- [x] T045 [US3] Implement 3-retry strategy in `SubAgentManager.create_and_run()`
- [x] T046 [US3] Implement `create_subagent_tool()` factory in `modules/agent_chat/src/subagent/manager.py`
- [ ] T047 [US3] Sub-agent task card UI (deferred to Phase 8)
- [ ] T048 [US3] Tab 3 advanced settings — sub-agent configuration (deferred to Phase 8)

**Checkpoint**: 批量 3 个 trace 分析使用子 Agent，主 Agent 上下文增量 < 50%

---

## Phase 7: US5 — 001 缺口修复 + 打包支持 (P3)

**Goal**: 修复 001 遗留缺口，确保 Skill 文件在打包产物中可用

**Independent Test**: CLI `agent ask` 调用所有插件工具；打包产物中 Skill 目录完整

- [x] T049 [P] [US5] CLI `agent ask` — integrate PluginManager + SkillsManager in `modules/agent_chat/src/cli_commands.py`
- [x] T050 [P] [US5] Context truncation — Skill context priority preservation in `modules/agent_chat/src/service.py`
- [ ] T051 [P] [US5] ReportIndex — PerfDog report scanning improvement (deferred — minor enhancement)
- [ ] T052 [US5] WorkflowTracker — Skill binding (deferred to Phase 8)
- [x] T053 [US5] Fix `_collect_modules()` in `scripts/build.py` — allow `.md` files under `skills/` directories
- [ ] T054 [US5] Verify packaging: SkillDiscovery scans Skill directories in PyInstaller output (requires manual test)

**Checkpoint**: CLI 完整工具注册，打包产物中 Skill 文件正常加载

---

## Phase 8: Polish & Testing

**Purpose**: 全面测试和文档更新

- [x] T055 [P] Unit tests for MCP module in `modules/agent_chat/tests/test_mcp.py` (19 tests)
- [x] T056 [P] Unit tests for Skills module in `modules/agent_chat/tests/test_skills.py` (24 tests)
- [x] T057 [P] Unit tests for SubAgent module in `modules/agent_chat/tests/test_subagent.py` (14 tests)
- [x] T058 Unit tests for curator tools in `modules/agent_chat/tests/test_curator_tools.py` (19 tests)
- [ ] T059 Integration test: MCP + Skill + Sub-agent + curator (deferred — requires live MCP server)
- [ ] T060 MCP tool call UI indicators (deferred — cosmetic enhancement)
- [ ] T061 Skill loading hint card in message area (deferred — cosmetic enhancement)
- [ ] T062 Documentation update in `modules/agent_chat/docs/` (deferred)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 MCP (Phase 3)**: Depends on Phase 2
- **US2+US4 Skills (Phase 4)**: Depends on Phase 2, can parallel with Phase 3
- **US2 curator (Phase 5)**: Depends on Phase 4 (SkillManager must exist)
- **US3 Sub-agent (Phase 6)**: Depends on Phase 2, can parallel with Phase 3/4
- **US5 Gaps (Phase 7)**: Depends on Phase 4 (SOP removal done)
- **Polish (Phase 8)**: Depends on Phase 3-7

### User Story Dependencies

- **US1 (MCP)**: Phase 2 完成后可独立开始
- **US2 (Skills)**: Phase 2 完成后可独立开始，与 US4 紧耦合
- **US3 (Sub-agent)**: Phase 2 完成后可独立开始，可与 US1/US2 并行
- **US4 (SOP→Skill)**: 与 US2 在同一 Phase 实现，先完成 SkillManager 再移除 SOPManager
- **US5 (001 Gaps)**: Phase 4 完成后开始（SOP 移除依赖）

### Parallel Opportunities

- Phase 3 (US1) 和 Phase 4 (US2+US4) 可并行
- Phase 6 (US3) 与 Phase 3/4/5 可并行（仅依赖 Phase 2）
- 各 Phase 内标记 [P] 的任务可并行执行

---

## Implementation Strategy

### MVP First (Phase 1 + 2 + 3)

1. Complete Setup + Foundational → 异步架构就绪
2. Complete US1 (MCP) → Agent 可调用 MCP 工具
3. **STOP and VALIDATE**: 验证 MCP 连接和工具调用

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (MCP) → Validate → First milestone
3. Add US2+US4 (Skills + SOP removal) → Validate → Second milestone
4. Add knowledge-curator → Validate → Knowledge management ready
5. Add US3 (Sub-agent) → Validate → Full orchestration
6. Add US5 (Gaps + Packaging) → Validate → Production ready
7. Polish + Tests → Release

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- T032 (knowledge-curator SKILL.md) already has initial content created — task is to finalize
- Phase 4 combines US2 and US4 because SOP removal is tightly coupled with Skill introduction
- 异步改造是最关键的基础设施，必须先完成
- 所有 SOP 相关代码和文件在 Phase 4 一次性清除
