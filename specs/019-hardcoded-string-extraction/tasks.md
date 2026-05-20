# Tasks: Hardcoded String Extraction

**Input**: Design documents from `/specs/019-hardcoded-string-extraction/`

**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md) (required for user stories)

**Tests**: Tests are included per module migration to verify functionality and string display correctness.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create automation tooling needed across all migrations

- [X] T001 Create automated hardcoded string verification script `scripts/check_hardcoded_strings.py` that scans all module `src/` and `toolkit/gui/` `.py` files, detects remaining Chinese hardcoded strings (excluding comments, imports, docstrings), and outputs file/line references with exit code 0/1

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Validate existing migrated modules as pattern baselines before proceeding

**⚠️ CRITICAL**: No new module migration can begin until existing migrations are verified as compliant with the Final[str] pattern

- [X] T002 [P] Review `modules/device_disguise/src/strings_gui.py`, `strings_cli.py`, `strings_service.py` for compliance with `Final[str]` constant pattern, functional prefix grouping, `_FMT` suffix on format strings, and absence of unused constants
- [X] T003 [P] Review `modules/game_perf/src/strings_gui.py`, `strings_cli.py`, `strings_service.py` for the same compliance checks as T002
- [X] T004 [P] Verify `modules/device_disguise/src/gui_tab.py`, `cli_commands.py`, `service.py` contain no residual Chinese hardcoded strings after migration
- [X] T005 [P] Verify `modules/game_perf/src/gui_tab.py`, `cli_commands.py`, `service.py` contain no residual Chinese hardcoded strings after migration

**Checkpoint**: Existing migrations (device_disguise, game_perf) confirmed as pattern-compliant baselines

---

## Phase 3: User Story 1 - perfetto_capture Migration (Priority: P1) 🎯 MVP

**Goal**: Complete full string extraction for the largest module (~305 lines of Chinese text), establishing the migration pattern for all subsequent modules

**Independent Test**: After T011, run `python -m pytest modules/perfetto_capture/tests/ -v` and verify all tests pass. Run `python -m toolkit.app` and confirm the perfetto_capture GUI tab displays Chinese text identically to pre-migration.

- [X] T006 [P] [US1] Scan and catalog all Chinese hardcoded strings in `modules/perfetto_capture/src/gui_tab.py`, `cli_commands.py`, `service.py` — produce an inventory grouped by function (BTN_, LABEL_, MSG_, DLG_TITLE_, LOG_, CLI_HELP_, PROGRESS_, ERROR_)
- [X] T007 [P] [US1] Create `modules/perfetto_capture/src/strings_gui.py` with `Final[str]` constants for all GUI strings from `gui_tab.py`, organized by functional prefix groups with section separators
- [X] T008 [P] [US1] Create `modules/perfetto_capture/src/strings_cli.py` with `Final[str]` constants for all CLI help text and Rich console messages from `cli_commands.py`
- [X] T009 [P] [US1] Create `modules/perfetto_capture/src/strings_service.py` with `Final[str]` constants for all progress messages and log strings from `service.py`; format templates use `_FMT` suffix and `.format()` compatible placeholders
- [X] T010 [US1] Update `modules/perfetto_capture/src/gui_tab.py` to import and reference `strings_gui.py` constants, replacing all hardcoded Chinese strings while preserving `.format()` for dynamic values
- [X] T011 [US1] Update `modules/perfetto_capture/src/cli_commands.py` to import and reference `strings_cli.py` constants, replacing all hardcoded Chinese CLI help strings and console messages
- [X] T012 [US1] Update `modules/perfetto_capture/src/service.py` to import and reference `strings_service.py` constants, replacing all hardcoded Chinese progress/log messages
- [X] T013 [US1] Run `python -m pytest modules/perfetto_capture/tests/ -v` and verify all tests pass; run `ruff check modules/perfetto_capture/src/` and `ruff format modules/perfetto_capture/src/`

**Checkpoint**: perfetto_capture fully migrated — GUI, CLI, and service strings centralized, tests passing, lint clean

---

## Phase 4: User Story 2 - agent_chat Migration (Priority: P2)

**Goal**: Migrate the second-largest module (~271 lines of Chinese text) using the established pattern

**Independent Test**: After T020, run `python -m pytest modules/agent_chat/tests/ -v` (if tests exist) or verify GUI/CLI display. Confirm Chinese text displays identically to pre-migration.

- [X] T014 [P] [US2] Scan and catalog all Chinese hardcoded strings in `modules/agent_chat/src/gui_tab.py`, `cli_commands.py`, `service.py` — produce inventory grouped by functional prefix
- [X] T015 [P] [US2] Create `modules/agent_chat/src/strings_gui.py` with `Final[str]` constants for all GUI strings from `gui_tab.py`
- [X] T016 [P] [US2] Create `modules/agent_chat/src/strings_cli.py` with `Final[str]` constants for all CLI strings from `cli_commands.py`
- [X] T017 [P] [US2] Create `modules/agent_chat/src/strings_service.py` with `Final[str]` constants for all service strings from `service.py`
- [X] T018 [US2] Update `modules/agent_chat/src/gui_tab.py` to reference `strings_gui.py` constants
- [X] T019 [US2] Update `modules/agent_chat/src/cli_commands.py` to reference `strings_cli.py` constants
- [X] T020 [US2] Update `modules/agent_chat/src/service.py` to reference `strings_service.py` constants
- [X] T021 [US2] Run `python -m pytest modules/agent_chat/tests/ -v` and `ruff check modules/agent_chat/src/` + `ruff format modules/agent_chat/src/`

**Checkpoint**: agent_chat fully migrated — independently testable and lint clean

---

## Phase 5: User Story 2 - perfetto_analysis Migration (Priority: P2)

**Goal**: Migrate perfetto_analysis module (~265 lines of Chinese text)

**Independent Test**: After T028, run `python -m pytest modules/perfetto_analysis/tests/ -v` and verify pass. Confirm GUI/CLI Chinese text unchanged.

- [X] T022 [P] [US2] Scan and catalog all Chinese hardcoded strings in `modules/perfetto_analysis/src/gui_tab.py`, `cli_commands.py`, `service.py`
- [X] T023 [P] [US2] Create `modules/perfetto_analysis/src/strings_gui.py` with `Final[str]` constants
- [X] T024 [P] [US2] Create `modules/perfetto_analysis/src/strings_cli.py` with `Final[str]` constants
- [X] T025 [P] [US2] Create `modules/perfetto_analysis/src/strings_service.py` with `Final[str]` constants
- [X] T026 [US2] Update `modules/perfetto_analysis/src/gui_tab.py` to reference `strings_gui.py`
- [X] T027 [US2] Update `modules/perfetto_analysis/src/cli_commands.py` to reference `strings_cli.py`
- [X] T028 [US2] Update `modules/perfetto_analysis/src/service.py` to reference `strings_service.py`
- [X] T029 [US2] Run tests and lint (`pytest modules/perfetto_analysis/tests/`, `ruff check`, `ruff format`)

**Checkpoint**: perfetto_analysis fully migrated

---

## Phase 6: User Story 2 - perfdog_insights Migration (Priority: P2)

**Goal**: Migrate perfdog_insights module (~108 lines of Chinese text)

**Independent Test**: After T036, run `python -m pytest modules/perfdog_insights/tests/ -v` and verify pass.

- [X] T030 [P] [US2] Scan and catalog all Chinese hardcoded strings in `modules/perfdog_insights/src/gui_tab.py`, `cli_commands.py`, `service.py`
- [X] T031 [P] [US2] Create `modules/perfdog_insights/src/strings_gui.py` with `Final[str]` constants
- [X] T032 [P] [US2] Create `modules/perfdog_insights/src/strings_cli.py` with `Final[str]` constants
- [X] T033 [P] [US2] Create `modules/perfdog_insights/src/strings_service.py` with `Final[str]` constants
- [X] T034 [US2] Update `modules/perfdog_insights/src/gui_tab.py` to reference `strings_gui.py`
- [X] T035 [US2] Update `modules/perfdog_insights/src/cli_commands.py` to reference `strings_cli.py`
- [X] T036 [US2] Update `modules/perfdog_insights/src/service.py` to reference `strings_service.py`
- [X] T037 [US2] Run tests and lint (`pytest modules/perfdog_insights/tests/`, `ruff check`, `ruff format`)

**Checkpoint**: perfdog_insights fully migrated

---

## Phase 7: User Story 2 - workspace_tools Migration (Priority: P2)

**Goal**: Migrate workspace_tools module (~91 lines of Chinese text)

**Independent Test**: After T044, run `python -m pytest modules/workspace_tools/tests/ -v` and verify pass.

- [X] T038 [P] [US2] Scan and catalog all Chinese hardcoded strings in `modules/workspace_tools/src/gui_tab.py`, `cli_commands.py`, `service.py`
- [X] T039 [P] [US2] Create `modules/workspace_tools/src/strings_gui.py` with `Final[str]` constants
- [X] T040 [P] [US2] Create `modules/workspace_tools/src/strings_cli.py` with `Final[str]` constants
- [X] T041 [P] [US2] Create `modules/workspace_tools/src/strings_service.py` with `Final[str]` constants
- [X] T042 [US2] Update `modules/workspace_tools/src/gui_tab.py` to reference `strings_gui.py`
- [X] T043 [US2] Update `modules/workspace_tools/src/cli_commands.py` to reference `strings_cli.py`
- [X] T044 [US2] Update `modules/workspace_tools/src/service.py` to reference `strings_service.py`
- [X] T045 [US2] Run tests and lint (`pytest modules/workspace_tools/tests/`, `ruff check`, `ruff format`)

**Checkpoint**: All 5 target modules fully migrated — workspace_tools is the final module-level migration

---

## Phase 8: User Story 3 - Framework Layer String Extraction (Priority: P3)

**Goal**: Extract Chinese hardcoded strings from `toolkit/gui/` framework layer files

**Independent Test**: After T050, run `python -m toolkit.app` and verify MainWindow sidebar labels, dialog titles, LLM settings dialog text display identically to pre-migration.

- [X] T046 [US3] Scan and catalog all Chinese hardcoded strings in `toolkit/gui/main_window.py`, `toolkit_dialog.py`, `llm_settings_dialog.py`, and other `toolkit/gui/*.py` files
- [X] T047 [P] [US3] Create `toolkit/gui/strings.py` with `Final[str]` constants for all framework GUI strings, organized by file/source section (MAIN_WINDOW_, DLG_, LLM_SETTINGS_, etc.)
- [X] T048 [P] [US3] Update `toolkit/gui/main_window.py` to reference `toolkit/gui/strings.py` constants
- [X] T049 [P] [US3] Update `toolkit/gui/toolkit_dialog.py` to reference `toolkit/gui/strings.py` constants
- [X] T050 [P] [US3] Update `toolkit/gui/llm_settings_dialog.py` to reference `toolkit/gui/strings.py` constants
- [X] T051 [US3] Update any remaining `toolkit/gui/*.py` files with Chinese hardcoded strings to reference `toolkit/gui/strings.py`
- [X] T052 [US3] Run `ruff check toolkit/gui/` and `ruff format toolkit/gui/`

**Checkpoint**: Framework layer strings extracted — GUI smoke test confirms MainWindow, dialogs, and settings display correctly

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final verification across all migrations

- [X] T053 [P] Run `scripts/check_hardcoded_strings.py` against all 5 migrated modules and `toolkit/gui/` — confirm zero remaining Chinese hardcoded strings in source files (excluding strings_*.py themselves and comments/docstrings)
- [X] T054 [P] Run `scripts/check_hardcoded_strings.py` against `modules/device_disguise/src/` and `modules/game_perf/src/` — confirm zero regressions in already-migrated modules
- [X] T055 Run `python scripts/run_all_tests.py` — confirm full test suite passes with no regressions
- [X] T056 Run `ruff check .` and `ruff format .` — confirm project-wide lint/format clean
- [X] T057 Update `docs/PROGRESS.md` to reflect string extraction completion status per longmemory rules
- [X] T058 Archive completed change records: update `specs/019-hardcoded-string-extraction/` status and cross-reference `docs/PROGRESS.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — verifies existing migrations before new work begins
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1 (perfetto_capture) → establishes the pattern, must complete first
  - US2 modules (agent_chat, perfetto_analysis, perfdog_insights, workspace_tools) — can proceed sequentially or in parallel after US1 pattern is validated
  - US3 (toolkit/gui/) — depends on all module migrations to avoid merge conflicts
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational — No dependencies on other stories
- **User Story 2 (P2)**: Can start after US1 pattern is established — 4 modules are independent of each other
- **User Story 3 (P3)**: Can start after all module migrations complete — to avoid touching framework files while modules are in flux

### Within Each Module Migration

- Scan/catalog strings (create inventory)
- Create strings_*.py files (parallelizable per type: gui/cli/service)
- Update source files to reference strings (sequential: gui_tab → cli_commands → service)
- Run tests and lint

### Parallel Opportunities

- All Foundational review tasks (T002–T005) can run in parallel
- Strings file creation (gui/cli/service) within a single module can run in parallel
- Different modules' string file creation can run in parallel once the pattern is established (after T009)
- T053 and T054 (verification script runs) can run in parallel
- T055 and T056 (tests and lint) can run in parallel

---

## Parallel Example: perfetto_capture (US1)

```bash
# Launch all strings file creation together (after inventory is complete):
Task: "Create modules/perfetto_capture/src/strings_gui.py"
Task: "Create modules/perfetto_capture/src/strings_cli.py"
Task: "Create modules/perfetto_capture/src/strings_service.py"

# Then update source files sequentially:
Task: "Update modules/perfetto_capture/src/gui_tab.py"
Task: "Update modules/perfetto_capture/src/cli_commands.py"
Task: "Update modules/perfetto_capture/src/service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verification script)
2. Complete Phase 2: Foundational (review existing migrations)
3. Complete Phase 3: US1 — perfetto_capture migration
4. **STOP and VALIDATE**: Run full perfetto_capture test suite + GUI smoke test
5. Verify the `Final[str]` pattern works end-to-end before scaling to other modules

### Incremental Delivery

1. Complete Setup + Foundational → Baseline verified
2. Add US1 (perfetto_capture) → Test independently → Pattern confirmed
3. Add US2 module 1 (agent_chat) → Test independently
4. Add US2 module 2 (perfetto_analysis) → Test independently
5. Add US2 module 3 (perfdog_insights) → Test independently
6. Add US2 module 4 (workspace_tools) → Test independently
7. Add US3 (toolkit/gui/) → Test independently
8. Final Polish → Full verification

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Developer A: US1 (perfetto_capture) — establishes pattern
3. Once US1 is validated:
   - Developer A: agent_chat
   - Developer B: perfetto_analysis
   - Developer C: perfdog_insights + workspace_tools
4. When all module migrations complete:
   - Any developer: US3 (toolkit/gui/)
5. Final Polish all together

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each module migration or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- Format templates (strings with placeholders) MUST use `_FMT` suffix and store the template string literal; runtime code uses `.format()` or f-string on the constant
