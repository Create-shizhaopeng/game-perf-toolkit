# Tasks: gameperfconfig 多文件对比与合并（007-gameperf-config-diff）

**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [data-model.md](./data-model.md) · [contracts/gameperf_config_diff.md](./contracts/gameperf_config_diff.md) · [research.md](./research.md)  
**模块落点**: `modules/workspace_tools/`（**禁止** import `modules.game_perf.src.*`）  
**Speckit**: `$env:SPECIFY_FEATURE = '007-gameperf-config-diff'`  
**Prerequisites**: spec.md ✅ plan.md ✅

## 目录

- [Phase 1: 模型与校验基础](#phase-1-模型与校验基础)
- [Phase 2: US1 — 基准与多对比文件列表](#phase-2-us1--基准与多对比文件列表)
- [Phase 3: US2 — 语义 Diff 与采纳/撤销](#phase-3-us2--语义-diff-与采纳撤销)
- [Phase 4: US3 — 保存确认与原子写盘](#phase-4-us3--保存确认与原子写盘)
- [Phase 5: US4 — 设备拉取参与对比](#phase-5-us4--设备拉取参与对比)
- [Phase 6: 测试、样例与收尾](#phase-6-测试样例与收尾)
- [US ↔ Task 追溯](#us--task-追溯)

**格式**: `[x]` 未完成；完成后改 `[x]` 为 `[X]`。`[P]` 表示可与同 Phase 内其他 `[P]` 并行（不同文件）。

---

## Phase 1: 模型与校验基础

**Purpose**: dataclass/类型、文件名与 XML 良构校验、设备路径常量（与 game_perf **约定对齐**，代码在本模块）。

- [X] T001 [P] 在 `modules/workspace_tools/src/` 新增 `gameperf_constants.py`（或等价）：`REMOTE_GAMEPERF_CONFIG_PATH`、`PULL_CACHE_SUBDIR` 等 **文档化常量**，与 `game_perf` 中 `/system/etc/gameperfconfig.xml` 及 pull 缓存语义一致
- [X] T002 [P] 实现 `is_valid_gameperf_config_filename(name: str) -> bool`（逻辑对齐 game_perf：`gameperfconfig` in name + `.xml`）
- [X] T003 实现 `parse_gameperf_xml(path: str) -> lxml` 封装：读文件、**UTF-8 + errors=replace**、**ElementTree 良构校验**；失败抛本模块 `XmlParseError` / `InvalidGamePerfFileError`
- [X] T004 [P] 按 [data-model.md](./data-model.md) 在 `modules/workspace_tools/src/gameperf_diff_models.py`（或并入 service 文件）定义 `FileProvenance`、`DiffSeverity`、`DiffItem`、`ComparisonSession`、`MergeOperation` 等（字段可微调，语义对齐契约）

**Checkpoint**: T001–T004 完成后可开始 US1 界面与 Service 骨架

---

## Phase 2: US1 — 基准与多对比文件列表

**Goal**: 选基准、加多个本地对比文件、移除、换基准；未满条件时「开始对比」不可用或提示。

- [X] T005 新建 `modules/workspace_tools/src/gameperf_diff_service.py`：`GamePerfConfigDiffService` 骨架 — `load_session`、`add_comparator_local`（集成 T002/T003，坏文件记入 `parse_errors`）、`comparators` 列表与 `active_comparator_index`
- [X] T006 [US1] 扩展 `modules/workspace_tools/src/gui_tab.py`：增加 **「配置对比」** 子 UI（`QStackedWidget` / `QTabBar`+页 二选一，与主 Tab 风格一致）；**基准** `QLineEdit`+浏览、**对比文件列表** `QListWidget`+添加/删除、**设为基准**（可选）
- [X] T007 [US1] 本地添加：文件对话框 + 拖拽（仅 `gameperfconfig*.xml`），复用与主窗口一致的接受规则
- [X] T008 [US1] 「开始对比」：校验「1 基准 + ≥1 对比」→ 调用后续 `run_diff`（Phase 3）；失败时在日志区输出 `parse_errors`

**Independent test**: 仅完成 Phase 2 时，可选文件、列表管理、单文件时提示，不崩溃

---

## Phase 3: US2 — 语义 Diff 与采纳/撤销

**Goal**: 基准 vs **当前选中对比文件** 的差异树；按条采纳（基准侧/对比侧）；撤销一次 + 重置；多对比时摘要条数。

- [X] T009 实现 `run_diff()`：对 `GameOptPolicy` 下 **PreEnv / BaseInfo / GamePolicy** 分块遍历（粒度见 spec **FR-012**），生成 `list[DiffItem]`；结果可按 `comparator_index` 缓存
- [X] T010 [P] [US2] `apply_merge` / `undo_merge` / `reset_merge` / `get_merge_dirty`：工作副本 = 基准 DOM **深拷贝** + 补丁栈（见 [research.md](./research.md) R3）
- [X] T011 [US2] GUI：`QTreeWidget` 或 `QTreeView` 展示 `semantic_path`、各侧 snippet、采纳按钮；切换 **当前对比文件** 下拉框刷新树（**FR-013**）
- [X] T012 [US2] 摘要区：`QLabel`/`QListWidget` 显示每个对比文件 **差异条数**（调用已缓存的 per-comparator diff 统计）

**Independent test**: `modules/workspace_tools/tests/test_gameperf_diff_service.py` — 两份 fixture XML，断言 `DiffItem` 数量与采纳后 DOM/序列化一致

---

## Phase 4: US3 — 保存确认与原子写盘

**Goal**: 另存为/保存路径选择；确认对话框（**FR-015**）；`tmp` + `os.replace`（**NFR-004**）。

- [X] T013 [US3] `save_merged_as`：序列化工作副本（`lxml` + `pretty_print=True` + XML 声明 UTF-8）；**先写 `.tmp` 再 replace**
- [X] T014 [US3] GUI：`QFileDialog.getSaveFileName`；保存前 `QMessageBox` 展示路径、覆盖警告、脏状态；取消则不调用 Service 写盘
- [X] T015 [P] [US3] 可选：保存前比较目标文件 **mtime/size** 变化，弹窗「文件已在外部修改」—— 重新加载 / 仍覆盖

**Independent test**: mock 文件系统或 tmp_path，断言取消不写盘、成功后可再次 parse 一致

---

## Phase 5: US4 — 设备拉取参与对比

**Goal**: 「从当前设备添加」→ pull 到 pull_cache → 作为对比项；失败可理解；可取消（步骤间隙，`threading.Event`）。

- [X] T016 [US4] `add_comparator_from_device(serial, cancel_event)`：使用 `context["adb"]` **pull** 至 `data_dir/pull_cache/<serial>/gameperfconfig.xml`（路径与 T001 常量一致）；`FileProvenance.kind=device_pull`
- [X] T017 [US4] GUI：`QThread` 执行拉取；信号更新日志；按钮「取消」置 `Event`；列表项显示 **「设备 (serial)」** 标签

**Independent test**: mock `AdbManager.pull` 成功/失败/不存在远程文件

---

## Phase 6: 测试、样例与收尾

- [X] T018 [P] 在 `modules/workspace_tools/fixtures/` 添加 `gameperfconfig_diff_base.xml`、`gameperfconfig_diff_variant_a.xml`（≥5 处语义可辨差异，满足 **SC-001**；文件名须含 `gameperfconfig`）
- [X] T019 补全 `test_gameperf_diff_service.py`：覆盖坏文件跳过、无差异、多对比切换、设备失败路径
- [X] T020 `modules/workspace_tools/src/plugin.py`：`on_startup` 注册 `context["wo_gameperf_diff_service"]`（或契约约定键名）
- [X] T021 [P] `scripts/run_all_tests.py` 已含 `workspace_tools` 组则确保新测试被收集；更新 `modules/workspace_tools/AGENTS.md` 中本特性测试说明（若需）
- [X] T022 更新根 [plan.md](./plan.md) **Post-Design / 实现记录** 小节（若有）与 [quickstart.md](./quickstart.md) 手测步骤与实际入口一致

---

## US ↔ Task 追溯

| US | Tasks |
|----|--------|
| US1 | T005–T008 |
| US2 | T009–T012 |
| US3 | T013–T015 |
| US4 | T016–T017 |
| 基础 | T001–T004, T018–T022 |

---

## MVP 建议范围

**第一期必交付**: Phase 1–4（US1–US3）+ T018–T020。  
**第二期**: Phase 5（US4）+ T021–T022 + 性能抽检（**SC-004** / plan 中 ≤8s）。
