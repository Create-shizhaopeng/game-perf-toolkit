# PerfDog 导入与性能洞察 — 实现记录

**特性目录**：`specs/004-perfdog-import-insights/`  
**关联**： [spec.md](./spec.md) · [plan.md](./plan.md) · [tasks.md](./tasks.md) · [data-model.md](./data-model.md)

本文档记录 **已落地代码与文档变更**，便于评审、排障与后续迭代对齐。新增修改请在本文件追加 **修订记录** 小节条目。

---

## 1. 实际代码布局（与 plan 初稿差异）

plan 初稿中的 `lv-game-toolkit/source/core`、`source/ui` 在仓库中 **未采用**；与现有 **pluggy 插件 + `toolkit` 核心包** 一致，实际为：

| plan 初稿路径 | 实际路径 |
|---------------|----------|
| `source/core/perfdog/` | **`toolkit/core/perfdog/`** |
| `source/ui/perfdog_tab.py`、`perfdog_worker.py` | **`modules/perfdog_insights/src/gui_tab.py`**、**`analysis_worker.py`** |
| `main.py` 注册 Tab | **`modules/perfdog_insights/src/plugin.py`** 的 **`register_gui_tab`** 钩子（与 `game_perf` 同模式） |

主程序无需改 `main.py`：由 `toolkit/app.py` 统一 `pm.hook.register_gui_tab()` 挂载。

---

## 2. 依赖（根 `pyproject.toml`）

| 变更 | 说明 |
|------|------|
| 增加 **`openpyxl>=3.1.0`** | 与 `research.md`、解析栈一致，用于读写 `.xlsx/.xlsm` |

其余：`pandas`、`PyQt6`、`pluggy` 等沿用工程既有声明。

---

## 3. 核心库 `toolkit/core/perfdog/`（MVP）

| 文件 | 职责 |
|------|------|
| `__init__.py` | 导出 **`load_and_analyze`**、**`build_markdown`** 及公开类型/异常 |
| `errors.py` | **`PerfDogParseError`**、**`PerfDogUnsupportedError`** |
| `config_defaults.py` | 阈值与常量：`ANOMALY_WINDOW_MS`、`STAT_FPS_DIFF_RATIO`、低帧/尖刺/不稳/温度、`MAX_DATA_V4_ROWS` 扫描深度、`ANALYSIS_SLOW_SEC` 等 |
| `column_aliases.py` | 列名别名 → 内部列名；**compact 匹配**（去括号/空格）及 PerfDog 常见变体（如 `SmallJank`、`Data v4` 场景配套列名） |
| `workbook.py` | 只读打开工作簿；**Data_v4 / Data v4 等标记识别**；**表头在标记后最多 24 行内搜索**；**工作表名 `all` 大小写不敏感**；**多表扫描**（先 `all` 再其余表）；前 **3000 行**扫描窗口 |
| `parse_all.py` | 前导区文本、`Stat` 猜测、`Data_v4` → **`pandas.DataFrame`**；**Stat vs Data_v4** 脚注 `compute_stat_disclaimer` |
| `session.py` | **`SessionSummary`** + **`summary_metrics`**；时间列单位启发式归一为 **ms** |
| `report_types.py` | **`AnalysisReport`**、`Finding`、`Recommendation`、`AnalyzeOptions`（含 **`interrupt_check`**）等 |
| `detect.py` | 低帧段、尖刺、帧不稳、温度列存在/缺失类 **`Finding`** |
| `recommendations.py` | 由 **`Finding`** 生成可追溯 **`Recommendation`**（FR-008 措辞） |
| `export_md.py` | **`build_markdown(report)`** → UTF-8 文本章节结构 |

**联合分析（US9～US11，T039+）** — 目录 **`toolkit/core/joint_assessment/`**：

| 文件 | 职责 |
|------|------|
| `observations.py` | **`build_observations_snapshot(report)`**；`data_gaps` 含 JA-SC-004（缺频点摘要）；**不** import `column_aliases`（包边界：仅 `report_types` + `joint_models`） |
| `engine.py` | **`assess_joint(policy, observations, options)`** → `JointAssessmentReport`（三段结论、warnings、绑核/频点建议与 insufficient 理由） |
| `export_md.py` | **`build_joint_markdown(joint, base_report=None)`** |
| `tests/test_joint_assess.py` | 联合分析回归（`pytest` 已纳入 `pyproject.toml` `testpaths`） |

**未实现（按 tasks Phase 8～10，后续迭代）**：

- `parse_frameinfo.py`、`parse_threads.py`、`correlate.py`、`threads_top.py`、`compare.py` 等（见 [tasks.md](./tasks.md) T027～T034）。

---

## 4. 插件模块 `modules/game_perf/`（联合分析衔接）

| 文件 | 职责 |
|------|------|
| `src/joint_adapter.py` | **`policy_snapshot_from_parser(parser, package, mode)`** → `PolicySnapshot`（`FreqRow` → `FreqPolicyRow`，BindCore / PerfHint 摘要） |
| `src/gui_tab.py` | **`_publish_joint_policy_snapshot`**：刷新表/策略后写入 **`context["gp_joint_policy_snapshot"]`**（`model_dump(mode="json")`）；无解析器或未选游戏/模式/解析失败时 **pop** 键；**不依赖设备**即可更新快照 |

---

## 5. 插件模块 `modules/perfdog_insights/`

| 文件 | 职责 |
|------|------|
| `manifest.json` | `provides.gui=true`；**`dependencies.toolkit_modules`**：`device_disguise`、`game_perf`、`perfetto_capture`，保证 **插件加载顺序** 在既有三模块之后，**侧栏 Tab 位于「设备伪装」下方** |
| `src/plugin.py` | `register_gui_tab` → **`PerfdogInsightsTab`**；CLI `perfdog`；`on_startup` 注册 **`pdi_service`** |
| `src/gui_tab.py` | **`BaseTab`**：`tab_title="PerfDog分析"`；**联合分析**按钮、`gp_joint_policy_snapshot` 校验与包名确认；**联合结论区**（`QGroupBox` + `QTextBrowser` + 绑核/频点建议列表）；**导出/复制** = `build_markdown` + `build_joint_markdown`（见 `_compose_export_markdown`）；**不因无设备禁用**导入与联合分析 |
| `src/analysis_worker.py` | **`QThread`**：`progress`、`finished_ok`、`finished_err`；`AnalyzeOptions(interrupt_check=QThread.isInterruptionRequested)` |
| `src/joint_worker.py` | **`JointAssessmentWorker`**：`report_path` + 序列化 `policy` dict + `skip_package_warning`；子线程 `load_and_analyze` + `assess_joint`；`joint_finished_ok` / `joint_finished_err` |
| `src/service.py` | 占位服务，便于后续持久化扩展 |
| `src/cli_commands.py` | `typer` 子命令 **`perfdog info`** |
| `src/migrations/.gitkeep` | 占位（当前无 DB 迁移） |

**契约说明**：`contracts/analysis_api.md` 中的 Worker 信号名为示例；实现侧为 **`finished_ok` / `finished_err`**（语义等价于成功/失败回调）。

---

## 6. 测试

| 文件 | 内容 |
|------|------|
| **`tests/test_perfdog_workbook.py`** | 临时生成最小 xlsx；**非法扩展名**拒绝；**`All` 表名 + `Data v4` 空格 + 表头前空行**；**无 Data_v4 字样仅靠列名回退** 等场景 |
| **`toolkit/core/joint_assessment/tests/test_joint_assess.py`** | 联合分析：`consistency_section`、JA-SC-004 与 `freq_insufficient_reason` 等 |

运行：`pytest tests/test_perfdog_workbook.py -q`；联合分析：`pytest toolkit/core/joint_assessment/tests/test_joint_assess.py -q`

---

## 7. 文档与任务清单同步

| 文档 | 变更 |
|------|------|
| [quickstart.md](./quickstart.md) | 已改为 **`toolkit/core/perfdog` + `modules/perfdog_insights`** 与启动方式 |
| [tasks.md](./tasks.md) | **MVP** T001～T026、T035、T036 已勾选；**联合分析** T038～T056 已勾选；T027～T034、T037 仍待 FrameInfo 等 |
| [plan.md](./plan.md) | 已补充 **实际路径** 与指向本 **`implementation.md`**（避免继续误读 `source/`） |

---

## 8. Data_v4 探测增强（真实导出兼容）

针对用户反馈「文件中可见 Data_v4 仍提示找不到」等问题，在 **`workbook.py` / `column_aliases.py`** 已做增强，要点如下：

1. 工作表 **`all` 大小写不敏感**（如 **`All`**）。  
2. 识别 **`Data_v4`、`Data v4`、`DATA V4`** 等变体（去分隔符后 `datav4` 或正则 `data…v4`）。  
3. **标记行与表头之间允许空行/说明行**：向下 **最多 24 行** 内择优表头。  
4. **多工作表**：在 **`all` 优先**后依次尝试其它表。  
5. 扫描行数上限 **3000**（避免前区过长漏检）。  
6. 列名：**`SmallJank` / `BigJank`**、**compact 键**、**去括号后缀** 等提升表头命中。  
7. **openpyxl `read_only=True` 与宽表**：部分 PerfDog 导出在 `all` 表中将 **Data_v4 放在整行仅 A 列**，表头在 **下一行整行横向展开**（数十列）。在此类文件上使用 **`read_only=True`** 时，openpyxl 流式迭代 **`iter_rows` 每行往往只返回 1 个单元格**，表头无法同时出现 `time`+`FPS`，探测必然失败。  
   **对策**：`safe_load_workbook` 默认 **`read_only=False`**（`workbook.py` / `parse_all` 前导区读取）；数据主体仍由 **pandas.read_excel** 读取，行为正常。

若仍失败：请核对表头是否含可映射的 **时间列 + FPS 列**（见 `column_aliases.py`），或向别名表补充该 PerfDog 版本列名。

---

## 9. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-03-22 | 初版：记录 MVP 落地路径、`perfdog_insights` 模块、依赖、测试与 plan/quickstart/tasks 同步策略。 |
| 2026-03-22 | 补充：Data_v4 多表/大小写/空行/列别名等探测增强说明（见下文 **§8 Data_v4**）。 |
| 2026-03-22 | 修复：PerfDog `all` 宽表 + openpyxl **read_only** 单列迭代问题；默认改为 **read_only=False**；列别名补充 `Stutter[%]`、`1%Low(FPS)` 等。 |
| 2026-03-22 | 扩展：`column_aliases.py` 覆盖 **Num / absTime / monoTime / label / Notes / InterFrame**、**AppCPU/TotalCPU 及 Normalized**、**CPUClock0～7 / CPUUsage0～7 及 Normalized**、**GUsage/GClock/BTemp/ThermalStatus**、**亮度/电量**、**电流电压功耗/ScreenShot** 等；`session.py` 对 GPU/CPU 频点、温度、CPU 占用等写入 **核心指标**；GUI/导出增加 **「未映射」语义说明**（非读不到数据）。 |
| 2026-03-22 | **最低帧根因（启发式）**：`detect.py` 定位全段最低 FPS 邻域，对比 GPU/CPU/温度/GPU 频率/各 CPU 核频率与全段；`recommendations.py` 生成 **「最低帧解决建议」**（画质、线程、后台、温控、绑核等）；阈值见 `config_defaults.py`（`LOW_FPS_*`）；GUI 洞察详情支持换行。 |
| 2026-03-22 | **最低帧误判修正**：CPU/GPU 频率以 **窗口中位数 vs 全段中位数** 判定持续偏低；**窗口 min 单点**仅配合「低采样占比」或「中位数正常」时提示 **瞬时下探**，避免把 PerfDog 秒级偶发谷底误报为持续限频；增加 **综合研判**（落差幅度、应用 CPU、温度、GPU 高占用）及 **卡顿列**（stutter/jank）对齐提示；`recommendations` 区分持续限频 vs 瞬时频点、增加 **综合排查** 类建议。 |
| 2026-03-22 | **文档**：原 `specs/005-gameperf-perfdog-analysis/` 中 spec/plan/research/data-model/quickstart/contract/checklist **并入本目录**（见 [spec.md](./spec.md) **US9～US11**、[plan.md](./plan.md) 联合分析小节、[contracts/joint_assessment_api.md](./contracts/joint_assessment_api.md)）。**代码** `joint_assessment` 等实现落地后请再追加本条。 |
| 2026-03-22 | **路径**：全量规格由 `specs/001-perfdog-import-insights/` **迁回** `specs/004-perfdog-import-insights/`；`001-perfdog-import-insights` 目录已删除；**SPECIFY_FEATURE** 使用 **`004-perfdog-import-insights`**。 |
| 2026-03-19 | **联合分析 T038**：新增 `toolkit/sdk/joint_models.py`（`PolicySnapshot`、`FreqPolicyRow`、`ObservationsSnapshot`、`FindingRef`/`RecRef`、`JointAssessmentReport`、`JointSuggestion`、`JointAssessOptions`），并由 `toolkit.sdk` 导出；对齐 [data-model.md](./data-model.md) 联合分析实体。 |
| 2026-03-22 | **联合分析 T039～T056 落地**：`toolkit/core/joint_assessment/{observations,engine,export_md}.py`；`modules/game_perf/src/joint_adapter.py` + `gui_tab._publish_joint_policy_snapshot`；`modules/perfdog_insights/src/joint_worker.py` + `gui_tab` 联合分析 UI/导出拼接（JA-FR-007）；契约见 [contracts/joint_assessment_api.md](./contracts/joint_assessment_api.md) §5。 |
| 2026-03-22 | **T027～T037**：`parse_frameinfo.py` / `parse_threads.py` / `correlate.py` / `threads_top.py` / `compare.py`；`load_and_analyze` 合并帧统计与线程/频点关联；`gui_tab` 关联分析区 +「添加对比文件」与 FR-012 确认；导出含对比节；`doc/README.md` 增加 PerfDog 入口说明。 |

---

## 10. 后续建议（非本文档范围实现）

- 维护 **脱敏多版本 xlsx 夹具**（`research.md` Open Items）。  
- PyInstaller **hiddenimports** 确认 `openpyxl`（若打包缺失再补）。  
