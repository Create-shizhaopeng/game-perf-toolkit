# Tasks: LLM Manager 模块重构

**Input**: Design documents from `specs/020-llm-manager-refactor/`

**Prerequisites**: [plan.md](plan.md) (tech stack), [spec.md](spec.md) (7 user stories), [research.md](research.md), [data-model.md](data-model.md), [contracts/service-api.md](contracts/service-api.md)

**Tests**: Not requested — implementation tasks only. Tests can be added as a separate PR.

**Organization**: Tasks grouped by user story for independent implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Phase 1: Setup — 模块脚手架

**Purpose**: 新建 `modules/llm_manager/` 模块骨架 + 字符串常量准备

- [x] T001 Create module directory structure per plan.md: `modules/llm_manager/` with `src/`, `config/`, `tests/`
- [x] T002 [P] Create `modules/llm_manager/manifest.json` per research.md R4
- [ ] T003 [P] Create `modules/llm_manager/config/llm_providers.json` — default template with GLM + Claude providers
- [ ] T004 [P] Add LLM Manager strings to `modules/llm_manager/src/strings_gui.py` (provider dialog, settings labels) per ui-mockups.md
- [ ] T005 [P] Add service strings to `modules/llm_manager/src/strings_service.py` (error messages, log messages)
- [ ] T006 [P] Add new LLM settings strings to `toolkit/gui/strings.py`: `LLM_SETTINGS_PROVIDER_LABEL`, `LLM_SETTINGS_THINKING`, `LLM_SETTINGS_MANAGE_PROVIDER`, `LLM_CONTEXT_TOOLTIP_FMT`
- [ ] T007 Create `modules/llm_manager/src/__init__.py` and `modules/llm_manager/tests/__init__.py`

---

## Phase 2: Foundational — 数据模型 + 核心服务

**Purpose**: Pydantic models + LLMManagerService 配置读写 — 所有 User Story 的基石

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T008 [P] Create `modules/llm_manager/src/models.py` — `ProviderConfig`, `ModelConfig`, `LLMProvidersConfig` Pydantic models per data-model.md
- [ ] T009 [P] Create `modules/llm_manager/src/service.py` — skeleton `LLMManagerService` class with `_config_path`, `_providers`, `_active_provider`
- [ ] T010 Develop `LLMManagerService.load()` in `modules/llm_manager/src/service.py` — load from JSON, validate with Pydantic, fallback to built-in template on error
- [ ] T011 Develop `LLMManagerService.save()` in `modules/llm_manager/src/service.py` — validate + atomic write (write to tmp then replace)
- [ ] T012 [P] Develop `LLMManagerService.get_active_provider_config()` in `modules/llm_manager/src/service.py` — return `(ProviderConfig, ModelConfig)` tuple
- [ ] T013 [P] Develop Provider CRUD: `get_provider()`, `add_provider()`, `remove_provider()`, `update_provider()`, `list_providers()`, `set_active_provider()` in `modules/llm_manager/src/service.py`
- [ ] T014 Create `modules/llm_manager/src/plugin.py` — `BasePlugin` subclass, register `LLMManagerService` to `ServiceRegistry` on `on_startup()`
- [ ] T015 Add migration logic in `LLMManagerService._migrate_from_old_config()`: extract `glm_api_key` / `claude_api_key` from `toolkit_config.json["llm"]`, generate default providers with migrated keys, mark `_migrated_to_llm_providers: true`

**Checkpoint**: Service can load/save provider config, CRUD works, migration from old config works

---

## Phase 3: User Story 1 — 配置自定义 LLM Provider (Priority: P1) 🎯 MVP

**Goal**: 通过 JSON 配置或 GUI 添加管理多个 LLM Provider

**Independent Test**: 编辑 `llm_providers.json` 添加 Provider → 启动应用 → 设置面板显示新 Provider → 可正常发起对话

### Implementation for User Story 1

- [ ] T016 [P] [US1] Create `modules/llm_manager/src/provider_dialog.py` — `ProviderManageDialog` skeleton (inherits `ToolkitDialog`, title bar + close button + save/cancel)
- [ ] T017 [P] [US1] Build Provider list widget (`QListWidget#providerListWidget`) in `modules/llm_manager/src/provider_dialog.py` — display enabled/disabled status with codicons (`check` / `circle-slash`), edit button per row
- [ ] T018 [US1] Build Provider edit panel (`QWidget#providerEditPanel`) in `modules/llm_manager/src/provider_dialog.py` — ID, Name, Base URL, Prefix, API Key (password mode + show/hide toggle), Thinking checkbox + budget spinbox
- [ ] T019 [US1] Build Models sub-section in edit panel — model list with name + context_window, add/remove buttons (`add` / `trash` codicons)
- [ ] T020 [US1] Wire save/delete logic in `provider_dialog.py` — call `LLMManagerService` CRUD methods, confirm dialog on delete, refresh list after save
- [ ] T021 [P] [US1] Add QSS for `#providerManageDialog`, `#providerListWidget`, `#providerEditPanel`, `#providerIdEdit`, `#providerNameEdit`, `#providerUrlEdit`, `#prefixEdit`, `#apiKeyEdit`, `#modelNameEdit`, `#contextEdit`, `#thinkingBudgetEdit` in `toolkit/gui/styles.py` (both dark + light themes)
- [ ] T022 [US1] Add "管理 Provider..." button handler in `toolkit/gui/llm_settings_dialog.py` — open `ProviderManageDialog`, pass `LLMManagerService` from ServiceRegistry, refresh provider combo on dialog accept
- [ ] T023 [US1] Add "settings-gear 管理 Provider..." item at bottom of provider QComboBox dropdown in `llm_settings_dialog.py` — via custom QAbstractItemView or context menu

**Checkpoint**: Can add/edit/delete providers via GUI, changes persist to JSON and reflect in settings panel

---

## Phase 4: User Story 2 — 自定义 Provider API 地址 (Priority: P1)

**Goal**: 自定义 base_url 覆盖默认 API 地址，请求路由到用户指定 URL

**Independent Test**: 配置 Claude base_url 为代理地址 → 发送请求 → 请求到达代理

### Implementation for User Story 2

- [ ] T024 [US2] Modify `toolkit/core/llm/litellm_provider.py` — `stream_chat()` accepts optional `api_base: str | None` parameter, passes to `litellm.acompletion(api_base=api_base)` when not None
- [ ] T025 [US2] Modify `toolkit/core/llm/manager.py` — `_init_provider()` reads `base_url` from active ProviderConfig (via ServiceRegistry → LLMManagerService), passes to `LiteLLMProvider` constructor
- [ ] T026 [US2] Modify `toolkit/core/llm/manager.py` — `stream_chat()` passes `api_base` through to `LiteLLMProvider.stream_chat()`
- [ ] T027 [US2] Remove hardcoded `_PROVIDER_MODEL_MAP` and `_LITELLM_PREFIX` from `toolkit/core/llm/litellm_provider.py` — read both from ProviderConfig instead

**Checkpoint**: Custom base_url works, LLM requests route to user-specified URL

---

## Phase 5: User Story 3 — 模型上下文尺寸区分 (Priority: P2)

**Goal**: 模型下拉列表显示上下文窗口标识（[1M], [200K], [128K]）

**Independent Test**: 配置 claude-opus-4-7 context_window=1000000 → 下拉列表显示 "[1M] claude-opus-4-7"

### Implementation for User Story 3

- [ ] T028 [US3] Modify `toolkit/gui/llm_settings_dialog.py` — provider combo change → load model list from `LLMManagerService` (no longer hardcoded `_GLM_MODELS` / `_CLAUDE_MODELS`)
- [ ] T029 [US3] Add context window label formatting in `llm_settings_dialog.py` — `_format_model_label(name, context_window)` → `"[1M] claude-opus-4-7"`, `"[200K] claude-sonnet"`, `"glm-4-plus"` (no label for <128K)
- [ ] T030 [US3] Update model combo in `toolkit/gui/widgets/llm_status_widget.py` — `_on_model_clicked` reads model list from provider config instead of local hardcoded list

**Checkpoint**: Model dropdown shows context labels, model list dynamically sourced from provider config

---

## Phase 6: User Story 4 — Thinking 特性支持 (Priority: P2)

**Goal**: 选择 Claude 时显示 Thinking 开关，开启后请求带上 thinking 参数

**Independent Test**: 选择 Claude → 勾选 Thinking → 发送请求 → 请求包含 thinking param

### Implementation for User Story 4

- [ ] T031 [US4] Modify `toolkit/core/llm/litellm_provider.py` — `stream_chat()` accepts optional `thinking: dict | None` parameter, passes to `litellm.acompletion(thinking=thinking)` when not None
- [ ] T032 [US4] Modify `toolkit/core/llm/manager.py` — `_init_provider()` reads `thinking` + `thinking_budget` from active ProviderConfig, constructs `thinking={"type":"enabled","budget_tokens":N}` dict
- [ ] T033 [US4] Add `QCheckBox#thinkingCheck` to `toolkit/gui/llm_settings_dialog.py` — visible only when selected provider has `thinking: true`, load/save state
- [ ] T034 [US4] Handle thinking content blocks in `litellm_provider.py` — LiteLLM returns thinking blocks in streaming response; ensure they are separated from regular text chunks and not displayed to user by default

**Checkpoint**: Thinking toggle works, supported models get thinking param, unsupported models hide toggle

---

## Phase 7: User Story 5 — 精简的 LLM 设置面板 (Priority: P2)

**Goal**: 设置面板只保留 Provider + Model + Thinking 3 个控件

**Independent Test**: 打开设置面板 → 只显示 Provider/M/Thinking + 管理按钮 + 保存按钮

### Implementation for User Story 5

- [ ] T035 [US5] Remove from `toolkit/gui/llm_settings_dialog.py`: API Key inputs (GLM + Claude tabs, `_ApiKeyRow`, `QStackedWidget` for keys), temperature slider, max_tokens spinbox, smart_switch checkbox, token_budget spinbox, budget_alert_threshold spinbox
- [ ] T036 [US5] Remove from `toolkit/sdk/models.py` `LLMConfig`: `glm_api_key`, `claude_api_key`, `temperature`, `max_tokens`, `smart_switch`, `token_budget`, `budget_alert_threshold` fields; widen `provider` field from `pattern=r"^(glm|claude)$"` to `str`
- [ ] T037 [US5] Remove from `toolkit/core/llm/manager.py`: `smart_switch` logic, `_switch_provider` fallback logic, `_budget_alerted`, `budget_alert` signal, `_session_tokens` for budget tracking
- [ ] T038 [US5] Update `toolkit/core/llm/manager.py` `save_config()` — only persist `active_provider` and `model_name` to `toolkit_config.json["llm"]`, all other settings from `llm_providers.json`
- [ ] T039 [US5] Clean up `toolkit/gui/strings.py` — remove unused LLM settings strings (temperature, smart_switch, budget-related labels)
- [ ] T040 [US5] Verify removed fields have zero references — grep for `temperature`, `max_tokens`, `smart_switch`, `token_budget`, `budget_alert` across `toolkit/` and confirm zero results in non-deprecation code

**Checkpoint**: Settings dialog has exactly 3 controls + manage button + save button; old fields removed from entire codebase

---

## Phase 8: User Story 7 — 状态栏上下文用量显示 (Priority: P2)

**Goal**: 状态栏圆环显示上下文用量百分比，hover 显示精确数字

**Independent Test**: 选择 glm-4-plus → 对话消耗 5K tokens → 圆环约 4% 填充 → hover 显示 "5,120 / 128,000 tokens (4.0%)"

### Implementation for User Story 7

- [ ] T041 [US7] Modify `toolkit/gui/widgets/llm_status_widget.py` — `ContextRingWidget`: remove color logic (green/yellow/red), use single color `#89b4fa` for fill arc always; add `setToolTip()` with formatted tooltip text
- [ ] T042 [US7] Modify `LLMStatusWidget` in `toolkit/gui/widgets/llm_status_widget.py` — remove `_token_label` (the "1.2k / 100k" text label), keep only `_ring` + `_model_label`
- [ ] T043 [US7] Update tooltip generation in `LLMStatusWidget` — `_ring.setToolTip(f"{used:,} / {total:,} tokens ({pct:.1f}%)")` using `LLM_CONTEXT_TOOLTIP_FMT`
- [ ] T044 [US7] Update `LLMStatusWidget.set_ratio()` — receives `(used, total)` and computes ratio internally; called from `LLMManager.token_updated` signal
- [ ] T045 [US7] Remove from `toolkit/gui/styles.py`: `#llmTokenLabel` QSS (no longer exists)
- [ ] T046 [US7] Update `toolkit/gui/main_window.py` — `_status_bar` layout: remove `_llm_status` token-related code paths

**Checkpoint**: Status bar shows clean ring + model name, hover shows precise numbers, no redundant text labels

---

## Phase 9: User Story 6 — Token 用量后台记录 (Priority: P3)

**Goal**: 后台 SQLite 记录每次 LLM 请求的 Token 用量

**Independent Test**: 发送 LLM 请求 → 查询 `llm_token_usage` 表 → 新记录存在

### Implementation for User Story 6

- [ ] T047 [P] [US6] Create SQL migration `modules/llm_manager/src/migrations/001_create_token_usage.sql` — `CREATE TABLE llm_token_usage` per data-model.md schema with indexes
- [ ] T048 [US6] Create `modules/llm_manager/src/token_tracker.py` — `TokenTracker` class: `record(request_id, provider, model, prompt_tokens, completion_tokens, conversation_id=None, trace_id=None)`, `get_usage_by_conversation()`, `get_usage_by_trace()`, `get_total_usage()`
- [ ] T049 [US6] Integrate `TokenTracker` with `LLMManagerService` — service owns tracker instance, exposes via `get_token_tracker()`
- [ ] T050 [US6] Expose `record_token_usage(prompt, completion, conv_id, trace_id)` method in `toolkit/core/llm/manager.py` — Agent Chat calls this when it receives a USAGE chunk; method internally calls `TokenTracker.record()`
- [ ] T051 [US6] Add `conversation_id` and `trace_id` passthrough in `toolkit/core/llm/manager.py` `stream_chat()` signature — callers (Agent Chat) pass these IDs, manager passes to tracker without interpreting them
- [ ] T051a [US6] Pass `conversation_id` and `trace_id` from Agent Chat to LLMManager in `modules/agent_chat/src/service.py` — modify `_run_loop()` to pass `conversation_id` and `trace_id` via `stream_chat()` kwargs when available

**Checkpoint**: Token usage recorded to SQLite on every LLM request; queryable by conversation/trace dimensions

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Cleanup, validation, documentation

- [ ] T052 [P] Remove unused imports and dead code across all modified files
- [ ] T053 [P] Verify all GUI strings extracted to `strings_gui.py` / `strings.py` — no Chinese hardcoded in modified GUI files
- [ ] T054 [P] Verify all new QSS selectors exist in both dark and light themes in `toolkit/gui/styles.py`
- [ ] T055 [P] Verify `modules/llm_manager/tests/` contains basic test files (`test_service.py`, `test_models.py`) — structural tests (not full coverage)
- [ ] T056 Run full test suite `python -m pytest tests/ modules/llm_manager/tests/ -v` — verify 0 regressions
- [ ] T057 Run GUI smoke test `python -m toolkit.app` — verify settings dialog opens, provider dialog opens, status bar renders
- [ ] T058 Update `docs/PROGRESS.md` with LLM Manager module completion entry
- [ ] T059 Run `/longmemory sync` to refresh doc indices

---

## Dependencies & Execution Order

### Phase Dependencies

```
Setup (P1) ──► Foundational (P2) ──► US1 (P3) ──► US2 (P4)
                                         │            │
                                         ▼            ▼
                                      US3 (P5)    US4 (P6)
                                         │            │
                                         ▼            ▼
                                      US5 (P7)    US7 (P8)
                                         │            │
                                         └─────┬──────┘
                                               ▼
                                            US6 (P9)
                                               │
                                               ▼
                                          Polish (P10)
```

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Foundational)**: Depends on Setup — **BLOCKS all user stories**
- **Phase 3 (US1)**: Depends on Foundational
- **Phase 4 (US2)**: Depends on Foundational + US1 (needs `LLMManagerService`)
- **Phase 5 (US3)**: Depends on Foundational + US1 (reads provider config)
- **Phase 6 (US4)**: Depends on Foundational + US1 + US2 (needs api_base + thinking params)
- **Phase 7 (US5)**: Depends on US1 completed (settings panel rework after provider dialog exists)
- **Phase 8 (US7)**: Depends on Foundational (reads model context_window)
- **Phase 9 (US6)**: Depends on US2 (needs LiteLLM usage data from stream_chat)
- **Phase 10 (Polish)**: Depends on all desired stories complete

### User Story Dependencies

| Story | Can Start After | Parallel With |
|-------|----------------|---------------|
| US1 (P1) | Foundational | — |
| US2 (P1) | Foundational + US1 | US3, US4 |
| US3 (P2) | Foundational + US1 | US2, US4, US7 |
| US4 (P2) | Foundational + US1 + US2 | US3, US7 |
| US5 (P2) | Foundational + US1 | US2, US3, US4, US7 |
| US7 (P2) | Foundational | US3, US4, US5 |
| US6 (P3) | US2 | US3, US4, US5, US7 |

### Parallel Opportunities

- T002, T003, T004, T005, T006 can all run in parallel (Setup phase)
- T008, T009 can run in parallel (Foundational phase)
- T016, T017 can run in parallel (US1 dialog skeleton + list widget)
- T024, T028 can run in parallel (US2 LiteLLM adapter + US3 model combo)
- T031, T041 can run in parallel (US4 thinking param + US7 context ring)
- T035, T036, T037 can run in parallel (US5 cleanup across 3 files)
- T047, T048 can run in parallel (US6 migration + tracker class)
- T052, T053, T054, T055 can all run in parallel (Polish phase)

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (Provider config CRUD + GUI)
4. Complete Phase 4: US2 (Custom API URL)
5. **STOP and VALIDATE**: Test: add a custom Provider via JSON → launch → settings panel shows it → send LLM request to custom URL
6. MVP delivers: multi-Provider with custom URLs. This alone is a huge win over the current 2 hardcoded providers.

### Incremental Delivery

1. Setup + Foundational → Foundation
2. US1 + US2 → MVP (multi-Provider + custom URL) ✓
3. US3 → Model context labels in dropdown
4. US4 → Thinking feature
5. US5 → Slimmed settings (clean removal of old fields)
6. US7 → Status bar context ring
7. US6 → Token tracking (backend only, no UI)
8. Polish → Docs, tests, cleanup

### Fastest Path (sequential, no parallel)

If working alone: Setup → Foundational → US1 → US2 → US3 → US4 → US5 → US7 → US6 → Polish
Estimated: ~50 tasks, ~1-2 sessions per phase

---

## Notes

- [P] tasks = different files, no dependencies → can be done simultaneously
- [Story] label maps task to specific user story for traceability
- Remove operations (US5) should leave no dangling references — verify with grep
- `LLMConfig` model changes are **breaking** — ensure no code references removed fields before deleting them
- Migration (T015) runs once on first launch; test by deleting `llm_providers.json` and restarting
- All GUI changes must be tested in both dark + light themes
- Token tracking (US6) has no UI — verify via SQLite query only
