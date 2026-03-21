# Tasks: 框架完善与验证

**Input**: Design documents from `specs/001-framework-completion/`
**Prerequisites**: plan.md (required), spec.md (required), research.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 确保测试基础设施就绪

- [x] T001 创建 conftest.py 配置 pytest fixtures — `tests/conftest.py`
- [x] T002 [P] 验证虚拟环境和依赖安装正常

**Checkpoint**: 测试基础设施就绪

---

## Phase 2: User Story 1 - GUI 主窗口正常显示与交互 (Priority: P1)

**Goal**: GUI 窗口可以正常启动、显示所有组件、支持基本交互

**Independent Test**: 手动运行 `python -m toolkit.app` 启动 GUI 并验证

### Implementation for User Story 1

- [x] T003 [US1] 启动 GUI 验证窗口正常渲染 — `toolkit/gui/main_window.py`
- [x] T004 [US1] 修复 GUI 启动中发现的问题（如有）— 多轮迭代修复 Logo/按钮/主题/缩放/布局
- [x] T005 [US1] 验证导航面板切换功能正常
- [x] T006 [US1] 验证主题切换功能（暗色 ↔ 亮色）— 含亮色主题文字对比度修复
- [x] T007 [US1] 验证标题栏设备状态显示和窗口控制按钮 — 含底部状态栏新增

**Checkpoint**: GUI 主窗口完全可用

---

## Phase 3: User Story 2 - 核心服务可靠运行 (Priority: P1)

**Goal**: 核心服务均有测试覆盖，全部通过

**Independent Test**: `pytest tests/ -v` 全部通过

### Tests for User Story 2

- [x] T008 [P] [US2] ConfigManager 单元测试 (12 项) — `tests/test_config_manager.py`
- [x] T009 [P] [US2] EventBus 单元测试 (9 项) — `tests/test_event_bus.py`
- [x] T010 [P] [US2] ServiceRegistry 单元测试（含 JSON Schema 生成验证, 8 项） — `tests/test_service_registry.py`
- [x] T011 [P] [US2] DatabaseManager 单元测试 (10 项) — `tests/test_db_manager.py`
- [x] T012 [P] [US2] PluginManager 单元测试 (5 项) — `tests/test_plugin_manager.py`
- [x] T013 [P] [US2] AdbManager 基本场景测试 (5 项) — `tests/test_adb_manager.py`

### Implementation for User Story 2

- [x] T014 [US2] 修复测试中发现的核心服务 bug — ServiceRegistry typing.get_type_hints 修复
- [x] T015 [US2] 运行全部测试确保通过 — 49 项核心服务测试全部通过

**Checkpoint**: 核心服务全部经过测试验证

---

## Phase 4: User Story 3 - CLI 内置命令完整可用 (Priority: P2)

**Goal**: CLI 命令均有自动化测试，模块子命令正常注册

**Independent Test**: `pytest tests/test_cli.py -v` 全部通过

### Tests for User Story 3

- [x] T016 [P] [US3] CLI version 命令测试 (2 项) — `tests/test_cli.py`
- [x] T017 [P] [US3] CLI config 命令组测试 (7 项) — `tests/test_cli.py`
- [x] T018 [P] [US3] CLI plugin 命令组测试 (3 项) — `tests/test_cli.py`

### Implementation for User Story 3

- [x] T019 [US3] 修复 CLI 测试中发现的问题 — Typer help exit_code=2 断言修复，15 项全部通过

**Checkpoint**: CLI 内置命令全部验证通过

---

## Phase 5: User Story 4 - 脚手架生成完整可用的模块骨架 (Priority: P2)

**Goal**: 脚手架脚本生成的模块结构完整且可被框架自动加载

**Independent Test**: `pytest tests/test_scaffold.py -v` 全部通过

### Tests for User Story 4

- [x] T020 [P] [US4] 脚手架正常创建测试 (12 项) — `tests/test_scaffold.py`
- [x] T021 [P] [US4] 脚手架模块加载测试 (2 项) — `tests/test_scaffold.py`
- [x] T022 [P] [US4] 脚手架错误处理测试 (5 项) — `tests/test_scaffold.py`

### Implementation for User Story 4

- [x] T023 [US4] 无需修复，19 项全部一次通过

**Checkpoint**: 脚手架工具验证通过

---

## Phase 6: 澄清需求实现

**Purpose**: 实现需求澄清中确认的功能

- [x] T024 [US1] 实现设备断开时功能按钮禁用和提示逻辑 — `toolkit/gui/base_tab.py` (on_devices_changed/require_device), `toolkit/gui/main_window.py` (状态传播)
- [x] T025 实现 config.json 日志级别配置 + CLI --verbose/--debug 参数支持 — `toolkit/core/logger.py` (resolve_log_level), `toolkit/app.py` (_resolve_log_level)

**Checkpoint**: 澄清需求全部实现

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 整体质量提升

- [x] T026 [P] 确保所有中文输出 UTF-8 无乱码 — logger.py + create_module.py 均已处理
- [x] T027 [P] 运行完整测试套件 — 83 项全部通过 (5 adb + 15 cli + 12 config + 10 db + 9 event + 5 plugin + 19 scaffold + 8 registry)
- [ ] T028 Git 提交当前所有进度

---

## FR ↔ Task Traceability

| FR | 关联 Task | 说明 |
|----|-----------|------|
| FR-001 | T003 | GUI/CLI 双入口启动验证 |
| FR-002 | T003, T004 | 无边框窗口布局验证与修复 |
| FR-003 | T007 | 设备状态指示灯（红/绿/蓝）+ DeviceComboBox |
| FR-004 | T005 | 导航面板动态按钮生成 |
| FR-005 | T006 | 暗色/亮色主题切换 |
| FR-006 | T016-T019 | CLI version/config/plugin 自动化测试；device 通过 T013 AdbManager 间接覆盖 |
| FR-007 | T012 | PluginManager 模块发现与排序测试 |
| FR-008 | T012 | CLI 命名空间冲突检测测试 |
| FR-009 | T008 | ConfigManager 嵌套键读写测试 |
| FR-010 | T009 | EventBus 注册/注销/触发测试 |
| FR-011 | T010 | ServiceRegistry + JSON Schema 生成测试 |
| FR-012 | T011 | DatabaseManager 连接/SQL/迁移测试 |
| FR-013 | T020-T023 | 脚手架生成与加载测试 |
| FR-014 | T026 | UTF-8 编码验证 |
| FR-015 | T024 | 设备断开功能禁用 + 提示 |
| FR-016 | T025 | config.json 日志级别 + CLI --verbose/--debug |
| FR-017 | T007 | 底部状态栏 StatusBar |
| FR-018 | T004 | 窗口边缘拖拽缩放 |
| FR-019 | T004 | 导航面板 QSplitter 拖拽调整 |

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — 可立即开始
- **Phase 2 (GUI)**: Depends on Setup — 需手动执行
- **Phase 3 (Core Tests)**: Depends on Setup — 可与 Phase 2 并行
- **Phase 4 (CLI Tests)**: Depends on Phase 3 (共享 conftest fixtures)
- **Phase 5 (Scaffold Tests)**: Depends on Phase 3
- **Phase 6 (Clarify)**: Depends on Phase 2 (GUI 基础可用后实现设备断开逻辑)
- **Phase 7 (Polish)**: Depends on all prior phases

### Parallel Opportunities

- Phase 2 (GUI) 和 Phase 3 (Core Tests) 可并行推进
- Phase 3 中的 T008-T013 全部可并行（测试不同服务）
- Phase 4 和 Phase 5 可在 Phase 3 完成后并行
- Phase 6 中的 T024 和 T025 可并行
