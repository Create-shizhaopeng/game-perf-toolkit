# Tasks: PerfDog 导入与性能洞察（004-perfdog-import-insights）

**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [data-model.md](./data-model.md) · [contracts/analysis_api.md](./contracts/analysis_api.md)  
**子特性（联合分析迭代）**: 需求与模型已并入 **本目录**：[spec.md](./spec.md)（**US9～US11**、**JA-FR/JA-SC**）、[plan.md](./plan.md) 联合分析小节、[data-model.md](./data-model.md) 联合实体、[research.md](./research.md) JA-R*、[contracts/joint_assessment_api.md](./contracts/joint_assessment_api.md)。实现任务见 **Phase 12～16**（**US9～US11** = 子特性 P1～P3）。

**仅做联合分析时**：主链 Phase 1～7 已勾选完成则 **从 Phase 12 / T038 开始**；顺序 **T039→T040→T041→T042→T043**，再 **T044～T048**（MVP），随后 **T049～T056**。  
**Speckit**：`$env:SPECIFY_FEATURE = '004-perfdog-import-insights'`  
**实现记录（已做修改汇总）**: [implementation.md](./implementation.md) — 新增/变更代码时请同步更新该文档 **§8 修订记录** 与相关小节。  
**Prerequisites**: plan.md ✅ spec.md ✅  

**框架约定**：与 `modules/game_perf`、`toolkit/gui/main_window.py` 插件钩子一致 —— 新能力放在 **`modules/perfdog_insights/`**（GUI + worker），可复用逻辑放在 **`toolkit/core/perfdog/`**（与 plan 中 `source/core/perfdog` 对应，实际仓库根为 `toolkit/`）。

**Tests**：spec 未强制 TDD；Phase 11 提供**最小 pytest 夹具**，其余可后续补。

---

## 目录

- [Phase 1: 依赖与包骨架](#phase-1-依赖与包骨架)
- [Phase 2: 核心解析与洞察（阻塞所有 UI）](#phase-2-核心解析与洞察阻塞所有-ui)
- [Phase 3: US1 + US8 — 导入、摘要、加载、清除](#phase-3-us1--us8--导入摘要加载清除)
- [Phase 4: US2 — 问题与洞察展示](#phase-4-us2--问题与洞察展示)
- [Phase 5: US4 — 建议清单](#phase-5-us4--建议清单)
- [Phase 6: US6 — 导出与复制](#phase-6-us6--导出与复制)
- [Phase 7: US7 — 设备无关与 Tab 行为](#phase-7-us7--设备无关与-tab-行为)
- [Phase 8: v1.1 — @FrameInfo（US3 部分）](#phase-8-v11--frameinfous3-部分)
- [Phase 9: v1.2 — 频点/线程关联（US3）](#phase-9-v12--频点线程关联us3)
- [Phase 10: v1.3 — A/B 对比（US5）](#phase-10-v13--ab-对比us5)
- [Phase 11: Polish](#phase-11-polish)
- [Phase 12: 联合分析 — 基础（阻塞 US9～US11）](#phase-12-联合分析--基础阻塞-us9us11)
- [Phase 13: US9 — 联合结论与包名警告（子特性 P1）](#phase-13-us9--联合结论与包名警告子特性-p1)
- [Phase 14: US10 — 绑核/频点建议与合并导出（子特性 P2）](#phase-14-us10--绑核频点建议与合并导出子特性-p2)
- [Phase 15: US11 — 离线衔接与复测工作流（子特性 P3）](#phase-15-us11--离线衔接与复测工作流子特性-p3)
- [Phase 16: 联合分析 — Polish](#phase-16-联合分析--polish)
- [依赖与并行](#依赖与并行)
- [MVP 范围](#mvp-范围)
- [US ↔ Task 追溯](#us--task-追溯)

---

## Phase 1: 依赖与包骨架

**Purpose**: 依赖声明 + 异常类型，无业务逻辑。

- [X] T001 在 `pyproject.toml` 的 `[project] dependencies` 中增加 `openpyxl>=3.1.0`（与 plan / 解析栈一致）
- [X] T002 [P] 新建 `toolkit/core/perfdog/__init__.py` 并导出公开 API 占位（`load_and_analyze` 可延后 Phase 2 末再 re-export）
- [X] T003 [P] 新建 `toolkit/core/perfdog/errors.py`，定义 `PerfDogParseError`、`PerfDogUnsupportedError`（契约见 `contracts/analysis_api.md`）

---

## Phase 2: 核心解析与洞察（阻塞所有 UI）

**Purpose**: `load_and_analyze(path)` 可返回完整 `AnalysisReport`（MVP 可先无 FrameInfo/对比）。

⚠️ 完成本 Phase 前不要写 `gui_tab` 业务逻辑（仅可搭空壳）。

- [X] T004 [P] 新建 `toolkit/core/perfdog/config_defaults.py`（异常窗口 ±5s、`ANALYSIS_SLOW_SEC`、最大帧行数等常量）
- [X] T005 [P] 新建 `toolkit/core/perfdog/column_aliases.py`（PerfDog 列名别名 → 内部统一列名，便于多版本导出）
- [X] T006 实现 `toolkit/core/perfdog/workbook.py`：安全打开 `.xlsx/.xlsm`（只读数据、不执行宏）、枚举 sheet、探测 `all` 表中 `Data_v4` 表头行索引
- [X] T007 实现 `toolkit/core/perfdog/parse_all.py`：解析 DeviceInfo 区块、Stat 行、`Data_v4` → `pandas.DataFrame`；落实 plan **Stat vs Data_v4** 脚注逻辑（与 Stat 差异 >1% 时写入 `AnalysisReport.stat_row_disclaimer`）
- [X] T008 实现 `toolkit/core/perfdog/session.py`：从解析结果构建 `SessionSummary` 与摘要区 `summary_metrics`（包名、机型、时长、目标帧率 hint）
- [X] T009 [P] 新建 `toolkit/core/perfdog/report_types.py`（或 `models.py`）：`dataclass` — `Finding`、`Recommendation`、`AnalysisReport`（字段对齐 `data-model.md`）
- [X] T010 实现 `toolkit/core/perfdog/detect.py`：从 DataFrame 生成 `Finding`（低帧段、尖刺、方差/稳定性、温度/功耗列若存在）；缺失列时生成「本文件未包含该项」类 finding
- [X] T011 实现 `toolkit/core/perfdog/recommendations.py`：由 `Finding` 生成 `Recommendation`，`finding_ids` 可追溯，文案符合 **FR-008**
- [X] T012 实现 `toolkit/core/perfdog/export_md.py`：`build_markdown(report: AnalysisReport) -> str`，UTF-8 文本，章节结构对齐 spec **附录 B**
- [X] T013 在 `toolkit/core/perfdog/__init__.py` 实现并导出 `load_and_analyze(path: str, *, options=None) -> AnalysisReport`（组合 T006–T011，可选 T012 不在此调用）

---

## Phase 3: US1 + US8 — 导入、摘要、加载、清除

**Goal**: 拖入/选取 xlsx → 后台解析 → 展示摘要；大文件有加载指示；可清除。

**Independent Test**: 无设备连接，拖入标准 PerfDog xlsx，30s 内看到摘要；清除后空态可再次导入。

- [X] T014 [US1] 使用 `scripts/create_module.py perfdog_insights --display-name "PerfDog分析"` 生成模块骨架，或**手工**创建 `modules/perfdog_insights/manifest.json`（`provides.gui=true`，`python_packages` 含 `openpyxl` 若模块独立安装时需要；通常继承根 `pyproject` 即可）、`modules/perfdog_insights/src/plugin.py`、`modules/perfdog_insights/src/__init__.py`
- [X] T015 [US1] 在 `modules/perfdog_insights/src/plugin.py` 实现 `GamePerfPlugin` 同款钩子：`register_gui_tab` 返回 `PerfDogTab` 实例（类定义于 `gui_tab.py`）
- [X] T016 [US8] [US1] 新建 `modules/perfdog_insights/src/analysis_worker.py`：`QThread`（或 `QRunnable`+线程池）内调用 `toolkit.core.perfdog.load_and_analyze`，发射 `progress(str)`、`finished(object)`、`failed(str)`；支持 `requestInterruption()` 检查（**FR-015**）
- [X] T017 [US1] 新建 `modules/perfdog_insights/src/gui_tab.py`：`BaseTab` 子类，`tab_title="PerfDog分析"`；拖拽 + `QFileDialog` 选文件；`QTextBrowser` 或分段 `QLabel` 展示 `AnalysisReport.summary_metrics` 与会话信息
- [X] T018 [US8] [US1] 在 `modules/perfdog_insights/src/gui_tab.py` 增加加载指示（`QProgressBar` 不确定模式或状态文案）、解析中禁用「导入」按钮；**清除当前分析**按钮清空 `AnalysisReport` 与视图（**FR-016**）
- [X] T019 [US1] 在 `modules/perfdog_insights/src/gui_tab.py` 处理非 xlsx、损坏文件、加密簿：捕获 `PerfDogParseError` 等，**不覆盖**上一份成功结果（**FR-009** / US1 场景 2）

---

## Phase 4: US2 — 问题与洞察展示

**Goal**: UI 展示 `findings` 列表，含时间定位；与 `detect.py` 输出一致。

**Independent Test**: 样例含开局低帧+中段尖刺，界面分段可见。

- [X] T020 [US2] 扩展 `modules/perfdog_insights/src/gui_tab.py`：新增「问题与洞察」区域，遍历 `AnalysisReport.findings` 展示标题、详情、时间范围
- [X] T021 [US2] 复核 `toolkit/core/perfdog/detect.py` 覆盖掉帧/帧不稳/温度三类及缺失列提示（与 spec US2 验收对齐）

---

## Phase 5: US4 — 建议清单

**Goal**: 展示 `recommendations`，与 finding id 对应（界面可用小字或折叠显示 id）。

- [X] T022 [US4] 在 `modules/perfdog_insights/src/gui_tab.py` 增加「建议」区域，展示 `AnalysisReport.recommendations`，文案保持启发式（**FR-008**）

---

## Phase 6: US6 — 导出与复制

**Goal**: 导出 Markdown 文件 + 复制全文（**FR-010** / **FR-019**）。

- [X] T023 [US6] 在 `modules/perfdog_insights/src/gui_tab.py` 增加「导出报告」：`QFileDialog.getSaveFileName`，写入 `build_markdown(report)`，UTF-8
- [X] T024 [US6] 在 `modules/perfdog_insights/src/gui_tab.py` 增加「复制报告」：`QGuiApplication.clipboard().setText(build_markdown(report))`

---

## Phase 7: US7 — 设备无关与 Tab 行为

**Goal**: 未连接设备仍可用；切换 Tab 不丢当前分析（除非用户清除）。

- [X] T025 [US7] 重写 `modules/perfdog_insights/src/gui_tab.py` 中 `on_devices_changed`：**不**因无设备禁用文件分析相关控件（本 Tab 纯离线）；若需设备按钮则无（**FR-013**）
- [X] T026 [US7] 在 `modules/perfdog_insights/src/gui_tab.py` 的 `on_deactivated`/`on_activated`：不自动清空报告；可选 Tooltip/说明文案（spec US7）

---

## Phase 8: v1.1 — @FrameInfo（US3 部分）

**Goal**: **SC-009** — 帧时长量化结论并入报告。

- [ ] T027 [US3] 实现 `toolkit/core/perfdog/parse_frameinfo.py`：`read_only` 扫描 `@FrameInfo`，聚合 `FrameStats`（p99、max、超阈帧数），超大行数提前截断并警告
- [ ] T028 [US3] 在 `toolkit/core/perfdog/__init__.py` 的 `load_and_analyze` 中合并 `FrameStats`；更新 `detect.py`/`export_md.py`/`gui_tab.py` 展示帧级结论；时间对齐规则见 `research.md`

---

## Phase 9: v1.2 — 频点/线程关联（US3）

**Goal**: 异常窗口前后 CPU/GPU 摘要 + 线程 Top-N。

- [ ] T029 [P] [US3] 实现 `toolkit/core/perfdog/parse_threads.py` 解析 `@ThreadCpuUsageData`
- [ ] T030 [US3] 实现 `toolkit/core/perfdog/correlate.py`：对每个 `Finding` 时间窗提取频点/GPU 均值对比
- [ ] T031 [US3] 实现 `toolkit/core/perfdog/threads_top.py`：异常窗内线程 Top-N
- [ ] T032 [US3] 扩展 `gui_tab.py`「关联分析」区；无表时展示 spec 要求提示（**不可用**）

---

## Phase 10: v1.3 — A/B 对比（US5）

**Goal**: **FR-011/012**、**SC-007**。

- [ ] T033 [US5] 实现 `toolkit/core/perfdog/compare.py`：`compare_reports(a,b) -> SessionComparePair`（或等价结构），包名不一致时生成警告标志
- [ ] T034 [US5] 扩展 `modules/perfdog_insights/src/gui_tab.py`：「添加对比文件」、应用不一致时 `QMessageBox` 确认（**FR-012**）；并列展示差异表

---

## Phase 11: Polish

- [X] T035 [P] 新增 `tests/test_perfdog_workbook.py` 或 `modules/perfdog_insights/tests/test_parse_smoke.py`：使用 `modules/perfdog_insights/fixtures/` 下**脱敏**最小 xlsx（或生成临时 xlsx）验证 `load_and_analyze` 不崩溃
- [X] T036 [P] 更新 `specs/004-perfdog-import-insights/quickstart.md` 中模块路径为 `modules/perfdog_insights` + `toolkit/core/perfdog`（若与初稿不一致）
- [ ] T037 [P] 在 `doc/` 或模块 `README` 增加用户可见的一节「PerfDog 分析」入口说明（可选，产品文档）

---

## Phase 12: 联合分析 — 基础（阻塞 US9～US11）

**Purpose**: Pydantic 模型 + `toolkit/core/joint_assessment` 纯函数管线；**不**依赖 PyQt、**不** `import modules.*`（对齐 [plan.md](./plan.md) **子特性：游戏性能策略 × PerfDog 联合分析**）。

**Checkpoint**: `assess_joint` + `build_observations_snapshot` 可被 pytest 直接调用（完成 T042 后）。

**执行细则（Phase 12）**：

- **import 边界**：`joint_assessment` 仅允许 `toolkit.sdk.joint_models`、`toolkit.core.perfdog.report_types`（及标准库）；**禁止** `from modules.` 或 `game_perf` / `perfdog_insights` 的 `src`。
- **频点列判定**：在 `observations.py` 用 `summary_metrics` 键名白名单或 `column_aliases` 已有语义判断「是否存在 CPU/GPU 频点类指标」；无则 `data_gaps` 记录，**JA-SC-004**。
- **T040 首期规则**：`assess_joint` 至少生成 3 段列表（策略摘要 bullet、观测摘要 bullet、一致性/矛盾 bullet）；可基于 **频点上下限 vs 观测均值/峰值**、**bindcore_summary 非空时的占位互证** 等简单启发式；**T049** 再充实绑核/频点 **JointSuggestion**。
- **包**：若根 `pyproject.toml` 未显式列出 **pydantic**，则 T038 同时补上依赖（与 Constitution **Pydantic 2** 一致）。

- [X] T038 [P] 新建 `toolkit/sdk/joint_models.py`：`PolicySnapshot`、`FreqPolicyRow`、`ObservationsSnapshot`、`JointAssessmentReport`、`JointSuggestion`、`JointAssessOptions`（字段语义对齐 [data-model.md](./data-model.md) **子特性：联合分析实体**；`JointAssessOptions` 含 `skip_package_warning: bool = False` 等与 [contracts/joint_assessment_api.md](./contracts/joint_assessment_api.md) 一致）
- [X] T039 实现 `toolkit/core/joint_assessment/observations.py`：`build_observations_snapshot(report: AnalysisReport) -> ObservationsSnapshot`，填充 `metric_lines`（从 `report.summary_metrics` 筛选展示用字符串）、`finding_summaries` / `recommendation_summaries`（截断过长文本）、`data_gaps`（缺包名、缺频点类列等）；缺频点列时 **不得** 在下游推断伪造频点数值（**JA-SC-004**）
- [X] T040 实现 `toolkit/core/joint_assessment/engine.py`：`assess_joint(policy, observations, *, options=None) -> JointAssessmentReport`；填充 **policy_section** / **observation_section** / **consistency_section**；**disclaimer** 固定模板句（启发式、需复测）；若 `options.skip_package_warning` 为 False 且两侧包名可比对且不等，可将说明写入 **warnings**（最终弹窗在 T047）；**T040 可先返回空的** `bindcore_suggestions` / `freq_suggestions`，由 **T049** 填满
- [X] T041 实现 `toolkit/core/joint_assessment/export_md.py`：`build_joint_markdown(joint, *, base_report=None) -> str`（UTF-8；二级标题建议 `## 游戏性能策略联合分析`，子节与 `toolkit/core/perfdog/export_md.py` 列表风格一致）
- [X] T042 新建 `toolkit/core/joint_assessment/__init__.py` 并导出 `build_observations_snapshot`、`assess_joint`、`build_joint_markdown`（在 T039–T041 完成后聚合 re-export；可在 `pyproject.toml` / 包发现中确保 `toolkit.core` 子包可被导入）
- [X] T043 [P] 新增 `toolkit/core/joint_assessment/tests/test_joint_assess.py`：至少 2 例 — (1) 合成 `PolicySnapshot` + 构造最小 `ObservationsSnapshot`（或经 `build_observations_snapshot` 的 mock report）断言 **consistency_section** 非空；(2) 观测侧 `data_gaps` 含缺频点说明时，调用 **T049 完成后**的 `assess_joint` 断言 **freq_suggestions** 为空且 **freq_insufficient_reason** 非空（若 T043 提交早于 T049，可先测 T040 行为并在 T049 后补第二条断言）

---

## Phase 13: US9 — 联合结论与包名警告（子特性 P1）

**Goal**: 游戏性能 Tab 写入策略快照；PerfDog Tab 在已有 `AnalysisReport` 上触发联合分析并展示结论；包名不一致时 **QMessageBox** 确认（**JA-FR-006**）。

**Independent Test**: 加载 fixture XML + 脱敏 xlsx → 点击「联合分析」→ 可见三段结论；故意错包名时先弹窗。

**执行细则（Phase 13）**：

- **T044**：`PolicySnapshot` 须 **Pydantic v2**；从 `parser.freq_rows` 过滤 `package_name`+`mode_name` 匹配行填入 `FreqPolicyRow`；**bindcore_summary** 从 `get_mode_level_data` / `StrategyItem` 中含 `BindCore` 的块生成短文本（实现可迭代）。
- **T045**：`context` 与 `MainWindow` 共享同一 dict；无解析器或未选游戏/模式时 **删除键或写 None**，避免 PerfDog 侧误用过期快照。
- **T046**：worker 入参为 **已序列化** `policy: dict` + `skip_package_warning: bool`（或主线程持有 `AnalysisReport` 仅传 path 再加载——避免跨线程传大对象需约定一种）；`joint_finished_ok` 传 `JointAssessmentReport` 或 `model_dump` 字典（与 GUI 约定一致）。
- **T047/T048**：主线程更新控件；包名比对使用 `PolicySnapshot.model_validate(context[...])` 后与 `report.session.package_name` 规范化比较（strip、小写可选）。

- [X] T044 [P] [US9] 新建 `modules/game_perf/src/joint_adapter.py`：实现 `policy_snapshot_from_parser(parser: GamePerfParser, package: str, mode: str) -> PolicySnapshot`（仅依赖本模块 `parser.py` / `models.py`；从 `FreqRow.to_dict` 或字段映射填充 `FreqPolicyRow`；**bindcore_summary** / **strategy_highlights** 尽力而为，空则留空字符串或空列表）
- [X] T045 [US9] 修改 `modules/game_perf/src/gui_tab.py`：在加载 XML、切换游戏、切换性能模式后调用 T044 并将 **`PolicySnapshot.model_dump(mode="json")`** 写入 **`self.context["gp_joint_policy_snapshot"]`**（固定此键名；失败时清除键并可选 `QMessageBox`）
- [X] T046 [US9] 新建 `modules/perfdog_insights/src/joint_worker.py`：`QThread` 子类，在 `run()` 内 `from toolkit.core.joint_assessment import build_observations_snapshot, assess_joint` 并调用；发射 `progress(str)`、`joint_finished_ok(object)`、`joint_finished_err(str)`；循环中检查 `isInterruptionRequested()`（与 `analysis_worker.py` 模式一致）
- [X] T047 [US9] 修改 `modules/perfdog_insights/src/gui_tab.py`：新增「联合分析」按钮；无 `gp_joint_policy_snapshot` 或无当前 `AnalysisReport` → **QMessageBox**；否则解析 policy 包名与 `report.session.package_name`：双侧非空且不等 → 确认「仍继续」后 `skip_package_warning=True` 启动 worker；单侧或双侧为空 → 不阻断但依赖 **assess_joint** 写入 **warnings**
- [X] T048 [US9] 修改 `modules/perfdog_insights/src/gui_tab.py`：增加 `QGroupBox`/`QTextBrowser`（或折叠区）展示 **policy_section**、**observation_section**、**consistency_section**、**warnings**；清空时机与「清除当前分析」一致

---

## Phase 14: US10 — 绑核/频点建议与合并导出（子特性 P2）

**Goal**: **bindcore_suggestions** / **freq_suggestions** 分区展示；数据不足时展示 **insufficient_reason**；导出/复制报告含联合章节（**JA-FR-007**）。

**Independent Test**: 夹具下可见绑核或频点类建议至少一条，或明确「当前数据不足以…」；导出 md 含联合块。

**执行细则（Phase 14）**：

- **T049**：每条 **JointSuggestion** 须含 **basis**（中文短句）+ **related_finding_ids**（若有）；无 BindCore 摘要且无线程类 finding 时 **bindcore_insufficient_reason**；无频点观测或 `data_gaps` 已声明缺频点 → **freq_insufficient_reason**（**JA-FR-004**）。
- **T051**：推荐顺序：`build_markdown(report)` 全文 + 空行 + `build_joint_markdown(joint, base_report=None)` **避免**联合节重复会话摘要；若实现选择单文件分段，须在 `export_md` 注释写明。

- [X] T049 [US10] 扩展 `toolkit/core/joint_assessment/engine.py`：在 `assess_joint` 内填充 **bindcore_suggestions** / **freq_suggestions**（`list[JointSuggestion]`）；规则绑定 **observations.finding_summaries** 与 **policy.freq_rows** / **bindcore_summary**；无依据时填 **bindcore_insufficient_reason** / **freq_insufficient_reason**（**JA-FR-004**）；措辞 **不得** 断言唯一根因（**JA-FR-005**）
- [X] T050 [US10] 修改 `modules/perfdog_insights/src/gui_tab.py`：在联合分析区下增加「策略调整建议」：**绑核** / **频点** 两个子列表；列表项展示 **text** + **basis**（`setToolTip` 或小字）；无建议时展示对应 **insufficient_reason**
- [X] T051 [US10] 修改 `modules/perfdog_insights/src/gui_tab.py`：**导出报告**与**复制报告**：若存在最新 `JointAssessmentReport`，输出为 `build_markdown(report) + "\n\n" + build_joint_markdown(joint, base_report=None)`（UTF-8）；代码注释固定该拼接契约（**JA-FR-007**）

---

## Phase 15: US11 — 离线衔接与复测工作流（子特性 P3）

**Goal**: 无 ADB/无设备仍可联合分析；用户改本地 XML 后切换回 PerfDog 可重新跑联合分析得到更新策略摘要（[spec.md](./spec.md) **US11**）。

**Independent Test**: 断连设备仅本地 XML+xlsx 完成联合分析；改 XML 后 game_perf 触发 context 更新，PerfDog 再次「联合分析」结论变化。

**执行细则（Phase 15）**：联合分析按钮 **不得** `if not serial: disable`；仅依赖 context 快照 + 内存中 `AnalysisReport`。

- [X] T052 [US11] 复核并修正 `modules/perfdog_insights/src/gui_tab.py` 与 `modules/game_perf/src/gui_tab.py`：「联合分析」与 `gp_joint_policy_snapshot` 更新路径 **不** 依赖设备连接；`game_perf` 在仅本地打开 XML 时亦须写入快照；空态提示「请先在 **游戏性能配置** 加载 XML 并选择游戏/模式」
- [X] T053 [P] [US11] 复核 `specs/004-perfdog-import-insights/quickstart.md` 中「联合分析烟测」小节与最终实现一致（步骤、按钮文案、无需设备）

---

## Phase 16: 联合分析 — Polish

**执行细则（Phase 16）**：契约与实现签名不一致时 **以代码为准回写 contract** 或 **改代码** 二选一，须在 **implementation.md** 记一笔。

- [X] T054 [P] 核对 `specs/004-perfdog-import-insights/contracts/joint_assessment_api.md` 与 [spec.md](./spec.md) **JA-FR** 及仓库内实际 `joint_assessment` / `joint_models` 签名一致；差异更新契约 **§1** 代码块或补 **§5 修订**
- [X] T055 [P] 更新 `specs/004-perfdog-import-insights/implementation.md`：**§8 修订记录** 列出新增路径：`toolkit/sdk/joint_models.py`、`toolkit/core/joint_assessment/*`、`modules/game_perf/src/joint_adapter.py`、`modules/perfdog_insights/src/joint_worker.py` 及 GUI 改动摘要
- [X] T056 [P] 更新 `modules/perfdog_insights/README.md`：一句话说明「联合游戏性能策略分析」入口、依赖 **游戏性能配置** 已加载 XML、以及 **SPECIFY_FEATURE=004-perfdog-import-insights** 文档位置（链到 `specs/004-perfdog-import-insights/quickstart.md`）

---

## 依赖与并行

```text
Phase 1 → Phase 2 (T006→T013 顺序为主；T004,T005,T009 可与 T006 前并行)
Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7
Phase 8 依赖 Phase 2 完成
Phase 9 依赖 Phase 4（需 findings 时间窗）
Phase 10 依赖 Phase 2 + Phase 6（双报告）
Phase 12 → Phase 13 → Phase 14 → Phase 15 → Phase 16（联合分析；与 Phase 8～10 可并行由不同开发者开发，但 US9 依赖 Phase 2 已有 AnalysisReport）
Phase 13 依赖 Phase 12 完成
Phase 14 依赖 Phase 13（UI 已能跑通一次 assess_joint）
Phase 15 依赖 Phase 13
Phase 16 依赖 Phase 14（文档与 README 对齐最终导出行为）；**T043 第二条**可在 **T049** 合并后再跑通 pytest 全绿
```

**可并行示例**：

- T004、T005、T009 与 T006 准备阶段并行  
- T029 与 T030 在不同文件，Phase 9 内可并行开发后集成  
- T038、T043、T044、T053、T054、T055、T056 在各自文件并行；**T039→T040→T041→T042** 顺序  
- Phase 12 与 Phase 8（FrameInfo）可由不同人并行，但联合分析 **MVP** 仅依赖 Phase 2～7 已有报告能力  

---

## MVP 范围

**建议 MVP = Phase 1～7 + T035**（约 T001–T026 + T035）：  
离线导入、摘要、洞察、建议、导出/复制、加载/清除、设备无关 Tab、**最小单测**。

**不包含 MVP**：FrameInfo（Phase 8）、线程/频点深化（Phase 9）、A/B（Phase 10），与 plan **v1.1～v1.3** 一致。

**联合分析子特性建议 MVP**：**Phase 12 + Phase 13（T038～T048）** — 与 [spec.md](./spec.md) 子特性 **P1（US9）** 对齐；**P2** 为 Phase 14，**P3** 为 Phase 15。

---

## US ↔ Task 追溯

| US | 主要任务 |
|----|----------|
| US1 | T014–T017, T019 |
| US2 | T020, T021 |
| US3 | T027–T032（分 v1.1 / v1.2） |
| US4 | T022 |
| US5 | T033, T034 |
| US6 | T023, T024 |
| US7 | T025, T026 |
| US8 | T016, T018 |
| US9 | T044–T048（子特性 P1：结论 + 包名警告） |
| US10 | T049–T051（子特性 P2：绑核/频点建议 + 合并导出） |
| US11 | T052–T053（子特性 P3：离线衔接 + quickstart） |

---

## 任务格式校验

- 共 **56** 条任务（T001–T056）；其中 **T038～T056** 为 **联合分析** 子特性（文档在 **本目录**）  
- 用户故事阶段任务均含 **`[US#]`** 标签（Phase 1–2、Phase 12 无 story 标签）  
- **并行**标记 `[P]` 含 T002,T003,T004,T005,T009,T029,T035,T036,T037,T038,T043,T044,T053,T054,T055,T056  

---

## 与 plan.md 路径差异说明

| plan.md 写的是 | 实际框架路径 |
|----------------|--------------|
| `source/core/perfdog/` | **`toolkit/core/perfdog/`** |
| `source/ui/perfdog_tab.py` | **`modules/perfdog_insights/src/gui_tab.py`** + **`analysis_worker.py`** |
| `main.py` 注册 Tab | **`modules/perfdog_insights/src/plugin.py`** 的 `register_gui_tab` 钩子（与 `game_perf` 一致） |

后续可小幅修订 `plan.md` 以统一路径描述。
