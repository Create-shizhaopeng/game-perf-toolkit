# Tasks: 历史面板批量操作与 Perfetto AI 分析接入

**Input**: Design documents from `specs/009-history-batch-analysis/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

## 目录

- [Phase 1: Setup](#phase-1-setup-shared-infrastructure)
- [Phase 2: Foundational](#phase-2-foundational-blocking-prerequisites)
- [Phase 3: US1 — 多选与批量删除](#phase-3-user-story-1--多选与批量删除-priority-p1--mvp)
- [Phase 4: US2 — 对话式 AI 分析](#phase-4-user-story-2--对话式-ai-分析单条-priority-p1)
- [Phase 5: US3 — 批量 AI 分析](#phase-5-user-story-3--批量-ai-分析-priority-p1)
- [Phase 6: US4 — 外部 trace 拖入](#phase-6-user-story-4--外部-trace-拖入管理-priority-p1)
- [Phase 7: US5 — 分析历史与报告查看](#phase-7-user-story-5--分析历史与报告查看-priority-p1)
- [Phase 8: US6 — 包名数据库](#phase-8-user-story-6--包名数据库-priority-p2)
- [Phase 9: Polish & Cross-Cutting](#phase-9-polish--cross-cutting-concerns)
- [Dependencies & Execution Order](#dependencies--execution-order)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 安装依赖、创建目录结构

- [x] T001 安装 pydantic-ai 和 pydantic-ai-litellm 依赖，更新 `pyproject.toml`
- [x] T002 安装 Jinja2 依赖（HTML 报告模板），更新 `pyproject.toml`
- [x] T003 创建 `modules/perfetto_analysis/src/agent/` 目录结构（`__init__.py`, `orchestrator.py`, `agents.py`, `tools.py`, `prompts.py`, `report.py`）
- [x] T004 [P] 创建 `modules/perfetto_analysis/templates/` 目录，放置 HTML 报告模板骨架 `report.html`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 数据模型扩展、Agent 工具注册、核心基础设施

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 扩展 `modules/perfetto_capture/src/models.py` — 在 `HistoryTrace` 中增加 `analysis_status`, `target_package`, `last_analysis_id` 字段
- [x] T006 [P] 创建分析数据模型 — 在 `modules/perfetto_analysis/src/agent/__init__.py` 中定义 `AnalysisTask`, `AnalysisStatus`, `AnalysisReport`, `AgentRole`, `AnalysisConfig` Pydantic 模型（参照 data-model.md）
- [x] T007 [P] 实现 pa_* 工具注册 — 在 `modules/perfetto_analysis/src/agent/tools.py` 中将 `PerfettoAnalysisService` 的 14 个方法封装为 Pydantic AI 工具函数（带 docstring 和类型注解）
- [x] T008 [P] 实现 Agent prompts 管理 — 在 `modules/perfetto_analysis/src/agent/prompts.py` 中实现 SOP 文件加载、场景路由 prompt 模板、Review Agent prompt 模板
- [x] T009 扩展 `modules/perfetto_capture/src/history_storage.py` — 增加 `analysis_tasks` 表 schema、CRUD 方法（`create_task`, `update_task_status`, `get_tasks_for_trace`, `get_all_tasks`）
- [x] T010 实现 `AnalysisOrchestrator` 基础骨架 — 在 `modules/perfetto_analysis/src/agent/orchestrator.py` 中创建类，初始化 LiteLLMModel（从 LLMManager 获取配置），定义 `analyze_single()` 和 `analyze_batch()` 的 async 接口签名

**Checkpoint**: 基础设施就绪，可以开始 User Story 实现

---

## Phase 3: User Story 1 — 多选与批量删除 (Priority: P1) 🎯 MVP

**Goal**: 历史面板支持 Ctrl/Shift 多选，批量删除带确认对话框

**Independent Test**: 打开历史面板，Ctrl 选中多个 trace，点击删除，确认后全部删除

### Implementation for User Story 1

- [x] T011 [US1] 修改 `modules/perfetto_capture/src/history_panel.py` — `SessionTreeWidget` 设置 `ExtendedSelection` 选择模式
- [x] T012 [US1] 修改 `modules/perfetto_capture/src/history_panel.py` — 重写 `_get_selected_items_data()` 返回 `list[dict]` 支持多选
- [x] T013 [US1] 修改 `modules/perfetto_capture/src/history_panel.py` — `_update_action_buttons_state()` 根据多选数量动态更新按钮文字（"删除 3 项"）
- [x] T014 [US1] 修改 `modules/perfetto_capture/src/history_panel.py` — `_on_delete()` 实现批量删除逻辑：收集所有选中项，弹出 QMessageBox 显示数量和总大小，确认后依次删除

**Checkpoint**: 多选和批量删除功能可独立测试

---

## Phase 4: User Story 2 — 对话式 AI 分析（单条） (Priority: P1)

**Goal**: 左右双栏布局 + 对话输入框 + 单条 trace AI 分析 + 流式输出

**Independent Test**: 选中 trace，输入分析意图，AI 在右栏流式输出分析过程，完成后浏览器打开 HTML 报告

### Implementation for User Story 2

- [x] T015 [US2] 重构 `modules/perfetto_capture/src/history_panel.py` — 将面板改为左右双栏布局（QSplitter horizontal），左栏放现有 trace 列表，右栏预留空间。设置面板整体最小宽度 600px（左栏 280px + 右栏 320px），支持手动拖动左边缘加宽
- [x] T016 [US2] 创建 `modules/perfetto_capture/src/analysis_chat.py` — 实现 `AnalysisChatWidget(QWidget)`，包含对话历史显示区域（QTextBrowser）和底部输入框（QLineEdit + 发送按钮）
- [x] T017 [US2] 修改 `modules/perfetto_capture/src/history_panel.py` — 将 `AnalysisChatWidget` 嵌入右栏，连接 trace 选中信号自动填入对话框
- [x] T018 [US2] 实现 trace 选中时自动带入逻辑 — 有 `target_package` 元数据的 trace 标注进程名，无元数据的显示置灰提示
- [x] T019 [US2] 实现 `MainAgent` — 在 `modules/perfetto_analysis/src/agent/agents.py` 中创建 MainAgent（Pydantic AI Agent），system prompt 为场景路由指令，工具为 `pa_trace_overview`，输出 `AnalysisRouting` 结构
- [x] T020 [US2] 实现 `SubAgent` — 在 `modules/perfetto_analysis/src/agent/agents.py` 中创建 SubAgent 工厂函数 `create_sub_agent(scene, sop_content)`，注册全部 pa_* 工具集
- [x] T021 [US2] 实现 `AnalysisOrchestrator.analyze_single()` — 完整流程：MainAgent 路由 → 创建 SubAgent → 执行分析 → 返回结论。通过 callback 函数传递流式输出和状态变化。分析结果存放在 `output/analysis/<trace_stem>_<YYYYMMDD_HHmmss>/` 目录下
- [x] T022 [US2] 创建 `AnalysisWorker(QThread)` — 在 `modules/perfetto_capture/src/analysis_chat.py` 中，工作线程运行 `asyncio.run(orchestrator.analyze_single(...))`，通过 `pyqtSignal(str, str)` 传递 (role, content)
- [x] T023 [US2] 实现 HTML 报告生成 — 在 `modules/perfetto_analysis/src/agent/report.py` 中使用 Jinja2 渲染分析结论为 HTML，保存到分析结果文件夹，生成 `raw_data/` 子目录存放 JSON 数据
- [x] T024 [US2] 实现分析完成后自动打开浏览器 — `AnalysisWorker` 完成信号触发 `QDesktopServices.openUrl()` 打开 HTML 报告
- [x] T025 [US2] 在 `modules/perfetto_analysis/src/plugin.py` 的 `on_startup()` 中创建 `AnalysisOrchestrator` 实例（从 `context["llm_manager"]` 获取 LLMManager 引用），注入 `context["pa_orchestrator"]`
- [x] T025b [US2] 实现单条分析取消机制 — `AnalysisChatWidget` 发送按钮在分析中变为"取消"按钮，点击设置 `AnalysisWorker` 的 abort flag，Agent 在工具调用间检查
- [x] T025c [US2] 实现分析超时机制 — `AnalysisOrchestrator.analyze_single()` 使用 `asyncio.wait_for()` 设置 5 分钟超时，超时标记任务为 TIMEOUT
- [x] T025d [US2] 实现 token 预算集成 — `AnalysisOrchestrator` 使用 Pydantic AI 的 `ctx.usage` 记录 token 消耗，每次 Agent 调用完成后调用 `LLMManager.record_tokens()`

**Checkpoint**: 单条 trace 的 AI 分析端到端可用

---

## Phase 5: User Story 3 — 批量 AI 分析 (Priority: P1)

**Goal**: 多选 trace 后批量分析，独立 SubAgent，Review Agent 评审

**Independent Test**: 选中 3 个 trace 发送分析，看到每个 trace 的状态变化，完成后生成 3 份报告

### Implementation for User Story 3

- [x] T026 [US3] 实现 `AnalysisOrchestrator.analyze_batch()` — 接收 `list[AnalysisTask]`，默认串行遍历 `analyze_single()`，支持 `parallel_count` 配置使用 `asyncio.gather()` 并行
- [x] T027 [US3] 实现 `ReviewAgent` — 在 `modules/perfetto_analysis/src/agent/agents.py` 中创建 ReviewAgent（Pydantic AI Agent），输入各 SubAgent 结论摘要，输出交叉评审意见
- [x] T028 [US3] 扩展 `AnalysisOrchestrator.analyze_batch()` — 所有 SubAgent 完成后调用 ReviewAgent，将评审结果附加到各 trace 的报告中
- [x] T029 [US3] 修改 `AnalysisChatWidget` — 支持批量分析进度展示，在对话区域显示每个 trace 的状态（排队中/分析中/评审中/完成/失败）
- [x] T030 [US3] 扩展批量取消机制 — 复用 T025b 的单条取消，扩展为批量取消：取消当前分析 + 跳过后续排队任务

**Checkpoint**: 批量分析端到端可用，含 Review 评审

---

## Phase 6: User Story 4 — 外部 trace 拖入管理 (Priority: P1)

**Goal**: 拖入外部 trace 文件到左栏顶部，自动纳入管理

**Independent Test**: 从文件管理器拖入 .perfetto-trace 文件，出现在列表中

### Implementation for User Story 4

- [x] T031 [US4] 创建 `modules/perfetto_capture/src/drag_drop_area.py` — 实现 `DragDropArea(QWidget)`，支持 `dragEnterEvent`/`dropEvent`，接受 `.perfetto-trace` 和 `.pb` 文件
- [x] T032 [US4] 修改 `modules/perfetto_capture/src/history_panel.py` — 在左栏顶部嵌入 `DragDropArea`
- [x] T033 [US4] 实现文件移动逻辑 — 拖入后将文件移动到 `user_traces/` 托管目录，创建 HistorySession 记录，自动刷新列表
- [x] T034 [US4] 添加格式校验 — 拖入非 trace 文件时提示"格式不支持"

**Checkpoint**: 外部 trace 拖入功能可独立测试

---

## Phase 7: User Story 5 — 分析历史与报告查看 (Priority: P1)

**Goal**: 左栏下半部展示分析历史，双击打开 HTML 报告

**Independent Test**: 完成一次分析后，下半部出现记录，双击在浏览器中打开报告

### Implementation for User Story 5

- [x] T035 [US5] 修改 `modules/perfetto_capture/src/history_panel.py` — 左栏改为上下 QSplitter（垂直），下半部放置 `AnalysisHistoryTree(QTreeWidget)`
- [x] T036 [US5] 实现 `AnalysisHistoryTree` — 与 `SessionTreeWidget` 风格一致，从 `analysis_tasks` 表加载数据，展示分析文件夹结构（📊 分析记录 → 📄 report.html / 📁 raw_data）
- [x] T037 [US5] 实现双击打开报告 — 双击分析记录时调用 `QDesktopServices.openUrl()` 打开 HTML 文件
- [x] T038 [US5] 实现分析历史删除 — 选中分析记录后点击删除，删除分析结果文件夹并移除数据库记录
- [x] T039 [US5] 实现分析状态标记 — `SessionTreeWidget` 中 trace 节点旁显示 ✅（已完成）/❌（失败）/⏳（进行中），刷新时从 `analysis_tasks` 查询

**Checkpoint**: 分析历史查看和管理功能可独立测试

---

## Phase 8: User Story 6 — 包名数据库 (Priority: P2)

**Goal**: 维护包名↔进程名映射，支持自动学习和 JSON 导入/导出

**Independent Test**: 分析 trace 后包名自动学习；导出 JSON 给另一个人导入

### Implementation for User Story 6

- [x] T040 [US6] 创建 `modules/perfetto_analysis/src/agent/package_db.py` — 实现 `PackageMappingDB` 类，支持 CRUD、`learn(package, process)` 自动学习、`export_json(path)` 和 `import_json(path)` 方法
- [x] T041 [US6] 修改 `AnalysisOrchestrator` — 分析完成后调用 `PackageMappingDB.learn()` 自动记录包名映射
- [x] T042 [US6] 在对话输入框中集成包名提示 — 选中无元数据 trace 时，从 `PackageMappingDB` 查询匹配的包名建议
- [x] T042b [US6] 在历史面板添加包名 DB 管理入口 — 左栏底部或设置菜单中提供"导入包名配置"和"导出包名配置"按钮

**Checkpoint**: 包名数据库学习和分享功能可用

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: 架构变更、性能优化、文档

- [x] T043 修改 `modules/perfetto_analysis/src/plugin.py` — `register_gui_tab()` 返回 `None`（移除 PerfettoAnalysisTab），保留其余钩子
- [x] T044 [P] 添加 `AnalysisConfig` 配置面板 — 在历史面板中提供分析配置入口（并行数、超时时间、自动打开报告）
- [x] T045 更新 `modules/perfetto_analysis/AGENTS.md` — 补充 Agent 引擎相关约束和目录说明
- [x] T046 更新 `modules/perfetto_capture/AGENTS.md` — 补充历史面板双栏布局和对话组件说明

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 无依赖，立即开始
- **Phase 2 (Foundational)**: 依赖 Phase 1 完成，阻塞所有 User Story
- **Phase 3 (US1 多选删除)**: 依赖 Phase 2（T005）
- **Phase 4 (US2 对话式分析)**: 依赖 Phase 2 全部完成（T005-T010）
- **Phase 5 (US3 批量分析)**: 依赖 Phase 4 完成（复用 `analyze_single()`）
- **Phase 6 (US4 拖入)**: 依赖 Phase 2（T005）
- **Phase 7 (US5 分析历史)**: 依赖 Phase 4（需要分析结果数据）
- **Phase 8 (US6 包名DB)**: 依赖 Phase 4（需要分析流程）
- **Phase 9 (Polish)**: 依赖所有 User Story 完成

### User Story Dependencies

- **US1 (多选删除)**: 可在 Phase 2 后独立实现
- **US2 (对话式分析)**: Phase 2 后开始，核心路径
- **US3 (批量分析)**: 依赖 US2 的 `analyze_single()` 实现
- **US4 (拖入)**: 可与 US1 并行
- **US5 (分析历史)**: 依赖 US2 产生分析记录
- **US6 (包名DB)**: 依赖 US2 的分析流程

### Parallel Opportunities

Phase 2 内: T006, T007, T008 可并行  
US1 (T011-T014) 与 US4 (T031-T034) 可并行  
Phase 9 的 T045, T046, T047 可并行

---

## Implementation Strategy

### MVP First (User Story 1 + 2)

1. Phase 1: 安装依赖 → Phase 2: 基础设施
2. Phase 3: 多选删除（快速交付，用户可立即验证）
3. Phase 4: 对话式分析（核心功能）
4. **STOP and VALIDATE**: 验证单条分析端到端流程

### Incremental Delivery

1. Setup + Foundational → US1 (多选删除) → 验证
2. US2 (对话式分析) → 验证核心 AI 分析链路
3. US3 (批量分析) → 验证批量 + Review
4. US4 (拖入) + US5 (分析历史) → 完善管理功能
5. US6 (包名DB) + Polish → 全功能交付

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- `modules/perfetto_analysis/src/agent/` 是新目录，所有 Agent 引擎代码集中在此
- `AnalysisOrchestrator` 是编排器（非 Agent），管理 Agent 生命周期
- pa_* 工具通过 `PerfettoAnalysisService` 调用，保持服务层不变
