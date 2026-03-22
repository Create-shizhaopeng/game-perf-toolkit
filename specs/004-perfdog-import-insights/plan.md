# Implementation Plan: PerfDog 导入与性能洞察报告

**Branch**: `004-perfdog-import-insights` | **Date**: 2026-03-22 | **Spec**: [spec.md](./spec.md) | **Tasks**: [tasks.md](./tasks.md)

> **布局规范**：与 [specs/003-adb-enhancement](../003-adb-enhancement/) 一致，本目录 **仅保留** `spec.md`、`plan.md`、`tasks.md` 三份主文件；原 `data-model.md`、`research.md`、`contracts/*`、`quickstart.md`、`implementation.md`、`checklists/*` 已 **合并入本 plan** 对应章节。

## 目录

- [概述](#概述)
- [技术上下文](#技术上下文)
- [Constitution 检查](#constitution-检查)
- [影响范围](#影响范围)
- [架构与模块](#架构与模块)
- [关键产品决策](#关键产品决策)
- [源码与文档结构](#源码与文档结构)
- [分阶段交付](#分阶段交付)
- [风险与缓解](#风险与缓解)
- [子特性：游戏性能策略 × PerfDog 联合分析](#子特性游戏性能策略--perfdog-联合分析)
- [数据模型](#数据模型)
- [技术调研](#技术调研)
- [API 契约：core.perfdog 分析 API](#api-契约coreperfdog-分析-api)
- [API 契约：联合分析](#api-契约联合分析)
- [快速开始](#快速开始)
- [规格质量清单（摘录）](#规格质量清单摘录)
- [实现记录](#实现记录)

## 概述

在 **Toolkit**（`lv-game-toolkit`，PyQt6）中提供 **「PerfDog分析」** Tab：拖拽 PerfDog **.xlsx/.xlsm**，后台解析 `all` / `@FrameInfo` / `@ThreadCpuUsageData`，生成摘要、洞察、启发式建议；支持 Markdown 导出/复制、双会话对比、与 **游戏性能配置** 的联合分析。核心逻辑在 **`toolkit/core/perfdog`** 与 **`toolkit/core/joint_assessment`**；UI 在 **`modules/perfdog_insights`**（`PerfdogInsightsService` 门面 + QThread）。

## 技术上下文

| 项 | 选择 |
|----|------|
| **Language** | Python **3.12+** |
| **GUI** | PyQt6 |
| **解析** | **openpyxl** + **pandas**；大表 `@FrameInfo` 使用 openpyxl `read_only` 流式（见技术调研） |
| **数据模型** | 报告侧 **dataclass**（`toolkit.core.perfdog.report_types`）；联合分析 **Pydantic v2**（`toolkit.sdk.joint_models`） |
| **测试** | **pytest**；根 `tests/test_perfdog_workbook.py` + `modules/perfdog_insights/tests/` + `toolkit/core/joint_assessment/tests/` |

## Constitution 检查

| 原则 | 合规性 |
|------|--------|
| Plugin-First | ✅ 能力在 `modules/perfdog_insights`，核心解析在 `toolkit/core/perfdog`（本特性授权） |
| 表现分离 | ✅ `service.py` 无 PyQt；Worker 仅调 Service |
| 模块间 | ✅ `joint_assessment` 不 `import modules.*`；策略经 `context['gp_joint_policy_snapshot']` |

## 影响范围

### 修改/涉及的主要路径

- `toolkit/core/perfdog/` — 解析、洞察、导出、FrameInfo/线程/对比（T027～T037）
- `toolkit/core/joint_assessment/` — 联合分析
- `toolkit/sdk/joint_models.py` — 联合分析 Pydantic 模型
- `modules/perfdog_insights/` — 插件、GUI、Service、测试
- `modules/game_perf/` — `joint_adapter`、`gp_joint_policy_snapshot`
- `tests/test_perfdog_workbook.py` — 核心烟测

### 不修改

- 无需求时不扩展无关 `toolkit/core` 模块；不直接依赖其他模块 `src/`。

## 架构与模块

```text
modules/perfdog_insights/src/gui_tab.py
    → PerfdogInsightsService（pdi_service） / QThread workers
    → toolkit.core.perfdog.load_and_analyze
toolkit/core/perfdog/   workbook, parse_all, session, detect, recommendations, export_md, parse_frameinfo, ...
toolkit/core/joint_assessment/   observations, engine, export_md
modules/game_perf/     context['gp_joint_policy_snapshot']
```

主程序经 `register_gui_tab` 挂载；**FR-013**：无需连接设备即可导入分析。

## 关键产品决策

| 主题 | 决策 |
|------|------|
| Stat vs Data_v4 | 以 Data_v4 重算为主；差异超阈值则脚注（见 `compute_stat_disclaimer`） |
| 异常窗口 | 默认 ±5s（`ANOMALY_WINDOW_MS`） |
| MVP 范围 | US1,8 + US2,4,6,7；US3/5 分阶段；联合分析 US9～US11 |

## 源码与文档结构

### 本特性规格（与 003 同型）

```text
specs/004-perfdog-import-insights/
├── spec.md
├── plan.md      ← 本文件（含数据模型、调研、契约、实现记录）
└── tasks.md
```

### 源码（仓库根）

见下文 **[实现记录](#实现记录)** 中的路径表（`toolkit/core/perfdog`、`modules/perfdog_insights` 等）。

## 分阶段交付

| 阶段 | 内容 |
|------|------|
| MVP | Data_v4 解析、洞察、Tab、导出、联合分析 JA-MVP |
| v1.1+ | @FrameInfo、线程关联、A/B 对比（已实现见 tasks 勾选） |

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 超大 FrameInfo | read_only + max 行截断 |
| 列名版本差异 | `column_aliases.py` + 夹具 |
| UI 卡死 | QThread + interrupt_check |

---

## 子特性：游戏性能策略 × PerfDog 联合分析

**Spec**：[spec.md](./spec.md) **US9～US11**、**JA-FR/JA-SC** · **Tasks**：[tasks.md](./tasks.md) Phase 12～16

在 **`toolkit/core/joint_assessment`** 实现纯函数研判；**`game_perf`** 写 **`gp_joint_policy_snapshot`**；**`perfdog_insights`** 触发联合分析与合并导出（**JA-FR-007**）。**禁止**自动改机（**JA-FR-008**）。

---

## 数据模型

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## 运行时实体（Python dataclass / 等价）

### SessionSummary

| 字段 | 类型 | 说明 |
|------|------|------|
| package_name | str? | 包名，来自 `all` 首行/元数据区 |
| device_name | str? | 机型 |
| perfdog_version | str? | 如首行含 PerfDog(xxx) |
| record_started_at | str? | 原始字符串 |
| duration_ms | int? | 由 Data_v4 `time` max 或元数据推断 |
| target_fps_hint | int? | 由 FPS P95 或 Stat 推断 60/90/120/144 |

### MetricSample（逻辑行）

对应 `Data_v4` 一行（解析后列名规范化为内部 snake_case）。

| 字段 | 类型 | 说明 |
|------|------|------|
| index | int | 行号 |
| time_ms | float | 相对时间 |
| fps | float? | |
| smooth | float? | |
| jank_small / jank / jank_big | int? | 列存在则填 |
| stutter_pct | float? | |
| app_cpu_pct | float? | |
| total_cpu_pct | float? | |
| gpu_usage_pct | float? | GUsage |
| cpu_clocks_mhz | list[float]? | 多核 |
| gpu_clock_mhz | float? | |
| battery_temp | float? | BTemp |
| gpu_temp | float? | GTemp |
| power_mw | float? | |
| battery_level_pct | float? | |

*实际列随版本变化；解析层填充「已知映射」，其余进 `extras: dict`。*

### FrameStats（聚合）

由 `@FrameInfo` 计算，非逐帧存储在内存（大文件）。

| 字段 | 类型 | 说明 |
|------|------|------|
| count | int | |
| mean_ms / p99_ms / max_ms | float | |
| over_budget_count | int | 超 2×目标帧时间的帧数 |
| max_frame_time_ms | float | |
| max_frame_at_ms | float? | 对应 time 列 |

### ThreadTopEntry

| 字段 | 类型 | 说明 |
|------|------|------|
| thread_label | str | 列名或线程名 |
| mean_pct_in_window | float | |
| peak_pct_in_window | float | |

### Finding

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 稳定 id，如 `spike-34376` |
| category | enum | drop / stability / thermal / power / freq / thread |
| severity | enum | info / warn / critical |
| title | str | 展示标题 |
| detail | str | 说明文字 |
| time_start_ms | float? | |
| time_end_ms | float? | |
| evidence | dict | 关键数值快照 |

### Recommendation

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | |
| finding_ids | list[str] | **FR-007** 追溯 |
| text | str | 含「建议复测」类措辞 |
| category | str | 复现条件 / 采集建议 / 环境 |

### AnalysisReport（聚合根）

| 字段 | 类型 | 说明 |
|------|------|------|
| session | SessionSummary | |
| summary_metrics | dict | 摘要区键值 |
| findings | list[Finding] | |
| recommendations | list[Recommendation] | |
| frame_stats | FrameStats? | |
| thread_top | list[ThreadTopEntry]? | |
| compare_note | str? | A/B 警告文案 |
| stat_row_disclaimer | str? | Stat vs 重算 |

### SessionComparePair（二期）

| 字段 | 类型 |
|------|------|
| session_a / session_b | SessionSummary |
| delta_metrics | dict[str, tuple[Any, Any]] |
| aligned_columns | list[str] |
| warnings | list[str] |

## 校验规则（来自 spec）

- 无包名/无 Data_v4：解析失败，**FR-009** 友好错误。
- 应用不一致对比：**FR-012** 需确认标记。

## 状态（ImportJob）

| 状态 | 说明 |
|------|------|
| idle | |
| running | 显示加载 |
| success | 展示 AnalysisReport |
| failed | message + 可恢复 |

---

## 子特性：联合分析实体（Pydantic）

> 对应 [spec.md](./spec.md) **US9～US11**；实现建议放在 **`toolkit/sdk/joint_models.py`**。以下字段语义须保持一致。

### PolicySnapshot（策略快照）

从 **`gameperfconfig`** 解析结果中，针对选定 **`package_name` + `mode_name`** 抽取。

| 字段 | 类型 | 说明 |
|------|------|------|
| package_name | str | 包名 |
| mode_name | str | 性能模式名 |
| game_alias | str? | 展示用别名 |
| freq_rows | list[FreqPolicyRow] | 当前模式下各温档行的 Gold/Prime/GPU 上下限（Hz 或索引，实现须注释固定策略） |
| bindcore_summary | str? | BindCore 等 **人类可读摘要** |
| strategy_highlights | list[str] | 其他 CPU/GPU 调度相关要点 |
| source_xml_path | str? | 报告脚注，可选 |

#### FreqPolicyRow

| 字段 | 类型 |
|------|------|
| temp_level, trigger_temp | str |
| gold_min_hz, gold_max_hz, prime_min_hz, prime_max_hz, gpu_min_hz, gpu_max_hz | int? |
| gold_index, prime_index, gpu_index | str? |

### ObservationsSnapshot（观测快照）

从 **`AnalysisReport`** 派生。

| 字段 | 类型 | 说明 |
|------|------|------|
| package_name | str? | 来自 SessionSummary |
| duration_ms, target_fps_hint | int? | |
| metric_lines | list[str] | 可对比摘要行 |
| finding_summaries | list[FindingRef] | id + title + category |
| recommendation_summaries | list[RecRef] | id + 首句 |
| data_gaps | list[str] | 缺失说明（**JA-SC-004**） |

#### FindingRef / RecRef

| 字段 | 类型 |
|------|------|
| id | str |
| title_or_text | str |
| category | str |

### JointAssessmentReport

| 字段 | 类型 |
|------|------|
| policy_section, observation_section, consistency_section | list[str] |
| bindcore_suggestions, freq_suggestions | list[JointSuggestion] |
| bindcore_insufficient_reason, freq_insufficient_reason | str? |
| warnings | list[str] |
| disclaimer | str |

#### JointSuggestion

| 字段 | 类型 |
|------|------|
| id, text, basis | str |
| related_finding_ids | list[str]? |
| severity_hint | str |

### 联合分析 UI 状态

| 状态 | 说明 |
|------|------|
| idle / running / success / failed | 同 ImportJob 语义；success 时展示 `JointAssessmentReport` |


---

## 技术调研

# Technical Research: PerfDog 导入与性能洞察

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)  
**Date**: 2026-03-21

## Decision 1: Excel 解析栈

**Decision**: **openpyxl** + **pandas**（与团队已有 PerfDog 分析脚本一致）。

**Rationale**:

- `pandas.read_excel` 开发速度快，适合 `Data_v4` 中等规模行数。
- `@FrameInfo` 可达 **10万+ 行**：大文件路径使用 **openpyxl `read_only=True`** 逐行聚合指标（p99、max、超阈计数），避免一次性 `read_excel` 爆内存。

**Alternatives considered**:

- 仅 csv：PerfDog 默认可导出 xlsx，转换增加用户步骤。
- calamine / polars：新增原生依赖与打包体积，首期不必要。

---

## Decision 2: UI 集成方式

**Decision**: **PyQt6** 新增 `QWidget` 子类作为 **QTabWidget** 一页；耗时逻辑放 **QThread**。

**Rationale**:

- Toolkit 已统一 PyQt6；拖拽用 `QDragEnterEvent` / `dropEvent` 或 `QLineEdit` + 文件按钮（双入口满足 **NF-003**）。

**Alternatives considered**:

- WebView 内嵌：与现有 QSS/主题割裂，打包复杂。

---

## Decision 3: 洞察逻辑形态

**Decision**: **纯 Python 函数 + 显式规则表**（`detect.py` / `recommendations.py`），输出结构化 `Finding` / `Recommendation` dataclass 列表，再由 `export_md.py` 渲染。

**Rationale**:

- 满足 **FR-008**（措辞模板集中）；便于单测注入合成 DataFrame。

**Alternatives considered**:

- LLM 解读：违反离线与非确定性验收，**Out of Scope**。

---

## Decision 4: Stat 与 Data_v4 不一致

**Decision**: **以 Data_v4 重算为主展示**；Stat 行可选展示为「PerfDog 汇总」对照；差异超阈值时脚注说明（见 [plan.md](./plan.md)）。

**Rationale**:

- 与实现 readiness 清单 CHK022 一致；避免用户不知以谁为准。

---

## Decision 5: 时间对齐（FrameInfo vs Data_v4）

**Decision**: `Data_v4` 使用 `time`（通常为相对 ms）；`@FrameInfo` 使用 `time`（相对 ms）。将帧归入 **1s bucket** 与秒级采样对齐做交叉引用；无法对齐时报告声明「帧级与秒级分列展示」。

**Rationale**:

- 实采样本中两表时间列语义一致（见历史 PD_20260320 分析）。

---

## Open Items（实现时关闭）

- [ ] 收集 2 个 PerfDog 版本 xlsx **脱敏夹具**，写入 `tests/fixtures/perfdog/`  
- [ ] PyInstaller `build.spec` 确认 **openpyxl/pandas** 隐式依赖已列入 hiddenimports（若需要）

**已实现说明**：MVP 代码路径、列别名与 Data_v4 探测策略见 **[实现记录](#实现记录)**；新增版本验证结论请同步更新该文档 **§8 / §9**。

---

# 子特性研究：游戏性能策略 × PerfDog 联合分析

**Spec 锚点**：[spec.md](./spec.md)（**US9～US11**、**JA-FR / JA-SC**）  
**Date**: 2026-03-22（由原 `specs/005-*/research.md` 迁入）

## JA-R1 — 联合逻辑放置位置（core vs 模块）

| 决策 | **联合研判与建议生成** 放在 **`toolkit/core/joint_assessment`**，输入/输出使用 **Pydantic**（**`toolkit/sdk/joint_models.py`**）。 |
|------|----------------------------------------------------------------------------------------------------------------------------------|
| **Rationale** | Constitution **IV**：模块互不导入对方 `src/`；`game_perf` 与 `perfdog_insights` 仅 **组装快照** 与 **UI/线程**。 |
| **Alternatives** | 写在 `perfdog_insights` 并 `import game_perf` — **违宪**；新建独立插件 — UI 与两 Tab 强耦合过重。 |

## JA-R2 — 策略侧数据如何到达 PerfDog Tab

| 决策 | 使用 **`context` 键**（如 `gp_joint_policy_snapshot`）+ 可选 EventBus；**`GamePerfTab`** 在加载/切换游戏或模式时写入；**`PerfdogInsightsTab`** 读取；缺失则阻断联合分析。 |
|------|------|
| **Rationale** | `BaseTab.context` 与 `MainWindow` 共享；**`gp_` 前缀** 符合质量门禁。 |

## JA-R3 — 观测侧数据来源

| 决策 | 以 **`AnalysisReport`**（`toolkit.core.perfdog`）为主输入；缺列时 core **降级**（与 **JA-SC-004** 一致）。 |
|------|------|

## JA-R4 — 包名不一致警告

| 决策 | `PolicySnapshot.package_name` vs `SessionSummary.package_name`：均缺则不阻断、报告脚注；均存在且不等则 **QMessageBox** 确认。 |
|------|------|

## JA-R5 — 导出形态

| 决策 | **`build_joint_markdown`** + 与 **`build_markdown(report)`** 拼接，单一可读导出（**JA-FR-007**）。 |
|------|------|

## JA-R6 — 线程与 UI

| 决策 | 联合分析在 **QThread**，**pyqtSignal** 回传结果；主线程只更新控件。 |
|------|------|


---

## API 契约：core.perfdog 分析 API

**Consumers**: `ui/perfdog_worker.py`、未来 CLI/测试。

## 入口函数（建议签名）

```python
# core/perfdog/__init__.py 或 facade module

def load_and_analyze(path: str, *, options: AnalyzeOptions | None = None) -> AnalysisReport:
    """
    同步解析 + 洞察。由 QThread 调用；不在主线程执行。
    raises: PerfDogParseError, PerfDogUnsupportedError
    """

def build_markdown(report: AnalysisReport) -> str:
    """FR-010：UTF-8 文本，无 BOM 或统一 BOM 策略见实现。"""

def compare_reports(a: AnalysisReport, b: AnalysisReport) -> SessionComparePair:
    """二期；应用不一致时 warnings 非空。"""
```

## AnalyzeOptions（可选配置）

| 字段 | 默认 | 说明 |
|------|------|------|
| anomaly_window_ms | 5000 | 异常窗口半宽（总窗口约 2×+1s） |
| max_frame_rows | 800_000 | 超过则降级采样或拒解析 |
| locale | zh_CN | 报告语言 |

## 错误类型

| 异常 | 含义 |
|------|------|
| PerfDogParseError | 文件损坏、非 xlsx、无法定位 Data_v4 |
| PerfDogUnsupportedError | 加密簿、宏执行拒绝等 |

## UI 契约（信号）

`PerfDogWorker`（QObject in QThread）建议暴露：

- `progress(str)` — 阶段文案  
- `finished(report: AnalysisReport)`  
- `failed(message: str)`  

**不得**在信号中传递不可序列化超大对象：若未来优化，可改为传递报告 ID + 主线程取缓存（MVP 可直接传 `AnalysisReport` 若体积可控）。

### 实现对照（lv-game-toolkit）

当前模块 **`modules/perfdog_insights/src/analysis_worker.py`** 中类 **`PerfDogAnalysisWorker`** 构造需传入 **`PerfdogInsightsService`**，子线程内调用 **`service.load_report`**；PyQt 信号名：

| 契约（本文） | 实现 |
|--------------|------|
| `finished(report)` | **`finished_ok(object)`** |
| `failed(message)` | **`finished_err(str)`** |
| `progress(str)` | **`progress(str)`**（一致） |

语义与本文一致；详见 **[实现记录](#实现记录)（§5 插件模块 `perfdog_insights`）**。

## 版本

- **Contract v1**：与 MVP 同步；破坏性变更递增 minor 并更新本文件。


---

## API 契约：联合分析

**Feature**: `004-perfdog-import-insights` 子特性（**US9～US11**，见 [spec.md](./spec.md)）  
**Consumers**: `modules/perfdog_insights`（GUI worker）、未来 CLI / Agent。

---

## 1. Core 入口（建议签名）

```python
# toolkit.core.joint_assessment (package)

def build_observations_snapshot(report: AnalysisReport) -> ObservationsSnapshot:
    """从现有 PerfDog 报告派生观测快照；填充 data_gaps。"""

def assess_joint(
    policy: PolicySnapshot,
    observations: ObservationsSnapshot,
    *,
    options: JointAssessOptions | None = None,
) -> JointAssessmentReport:
    """
    纯函数；可单测。不得访问 GUI、ADB、磁盘。
    options：如是否强制忽略包名警告（通常由 UI 传入用户选择）。
    """

def build_joint_markdown(
    joint: JointAssessmentReport,
    *,
    base_report: AnalysisReport | None = None,
) -> str:
    """UTF-8 Markdown；若提供 base_report，建议原 PerfDog 章节 + 「联合分析」分节。"""
```

类型 `PolicySnapshot`、`ObservationsSnapshot`、`JointAssessmentReport`、`JointAssessOptions`：**Pydantic v2**，定义于 **`toolkit/sdk/joint_models.py`**。

---

## 2. 模块侧适配（非 core）

### `game_perf`

- **`policy_snapshot_from_parser(parser: GamePerfParser, package: str, mode: str) -> PolicySnapshot**`（`joint_adapter.py` 或 `service.py`），仅依赖本模块。
- **`GamePerfTab`**：将快照写入 **`context["gp_joint_policy_snapshot"]`**（须 **`gp_` 前缀**）。

### `perfdog_insights`

- **`JointAssessmentWorker`**（`joint_worker.py`）：构造参数为 **`report_path: str`**、**`policy_dict: dict`**（`PolicySnapshot.model_dump(mode="json")`）、**`PerfdogInsightsService`**、**`skip_package_warning: bool`**；子线程内经 Service **`load_report`** 再 **`assess_joint_from_loaded_report`**（等价于原 `load_and_analyze` + `build_observations_snapshot` + `assess_joint`）。
- **信号**：`progress(str)`、`joint_finished_ok(object)`（`JointAssessmentReport.model_dump(mode="json")` 字典）、`joint_finished_err(str)`。

---

## 3. 包名比对契约

| 条件 | 行为 |
|------|------|
| `policy.package_name` 与 `observations.package_name` 均非空且不等 | UI **必须**确认；`JointAssessOptions.skip_package_warning=True` 仅在用户确认后传入 |
| 任一侧为空 | `JointAssessmentReport.warnings` 含「无法校验包名」；**不**自动视为不一致 |

---

## 4. 版本

- **Contract v1**：与 **`004-perfdog-import-insights`** 联合分析 MVP 同步；破坏性变更递增 minor 并更新本文件。

---

## 5. 修订（与实现对齐）

| 版本 | 说明 |
|------|------|
| v1.1 | GUI 侧 Worker 定名为 **`JointAssessmentWorker`**；导出/复制 Markdown 的拼接约定不变，实现上由 **`PerfdogInsightsService.compose_export_markdown`** 完成（等价于 **`build_markdown` + `build_joint_markdown(..., base_report=None)`** + 可选对比节；GUI 经 **`gui_tab._compose_export_markdown`** 调用 Service，**JA-FR-007**）。 |
| v1.0 | 初版 §1 Core 签名与 `joint_models` 类型。 |


---

## 快速开始

## 前置

- 仓库：本仓库根目录（`lv-game-toolkit`）
- Python **3.12+**，在根目录执行 `pip install -e ".[dev]"`（含 `openpyxl`、`pandas`）
- 参考规范：同目录 [spec.md](./spec.md)

## 目录与入口

1. 核心库：`toolkit/core/perfdog/`（解析、洞察、`load_and_analyze` / `build_markdown`）。
2. GUI 模块：`modules/perfdog_insights/`（`plugin.py` 注册 `register_gui_tab`，`gui_tab.py` + `analysis_worker.py`）。
3. 启动主程序：`python -m toolkit.app`，侧栏选择 **「PerfDog分析」**；**无需连接设备**即可拖入 `.xlsx`。

## 单测

```bash
cd lv-game-toolkit
pytest tests/test_perfdog_workbook.py -q
```

测试会在临时目录生成最小 xlsx，验证 `load_and_analyze` 不崩溃。真实夹具可置于 `modules/perfdog_insights/fixtures/`（脱敏，勿提交用户数据）。

## 依赖

根目录 `pyproject.toml` 已包含：

- `pandas>=2.0`
- `openpyxl>=3.1`

## 文档链路

| 文档 | 用途 |
|------|------|
| [spec.md](./spec.md) | 产品需求 |
| [plan.md](./plan.md) | 技术方案、数据模型、调研、契约、实现记录（本文件） |
| [plan.md#实现记录](./plan.md#实现记录) | **实现记录**：已落地路径、Data_v4 兼容、修订历史 |
| [tasks.md](./tasks.md) | 任务拆解与完成勾选 |
| [plan.md#数据模型](./plan.md#数据模型) | 数据结构 |
| [plan.md#api-契约coreperfdog-分析-api](./plan.md#api-契约coreperfdog-分析-api) | `core.perfdog` 分析契约 |
| [plan.md#api-契约联合分析](./plan.md#api-契约联合分析) | **联合分析** Core API（US9～US11） |

## 联合分析烟测（US9～US11）

1. 启动 `python -m toolkit.app`，**无需连接设备**。
2. **游戏性能配置**：加载 `gameperfconfig*.xml`，选中与 PerfDog 会话一致（或故意不一致）的游戏与模式。
3. **PerfDog 分析**：拖入脱敏 `.xlsx`，等待标准报告生成。
4. 点击 **「联合分析」**（`PerfdogInsightsTab` 工具栏按钮）：应看到策略要点 / 观测要点 / 一致性或矛盾；包名不一致时应先确认。
5. **导出/复制**：报告应包含联合章节，且含启发式/复测免责声明（**JA-FR-007**）。

单测（实现落地后）：

```bash
pytest toolkit/core/joint_assessment/tests/test_joint_assess.py -q
```

## 常见问题（解析）

- **提示找不到 Data_v4**：多为表名大小写、标记与表头间空行、列名未映射等；处理策略见 **[实现记录 §8](#实现记录)** 与源码 `toolkit/core/perfdog/workbook.py`、`column_aliases.py`。


---

## 规格质量清单（摘录）

需求规格完整性（原 `checklists/requirements.md`）：内容质量、需求完整性、功能就绪等项均已勾选通过；成功标准可验证、线程/频点降级与 US5～8 一致。实现就绪清单（原 `checklists/implementation-readiness.md`）曾在实现前用于门禁，落地后以 **tasks.md 勾选 + 本 plan 实现记录** 为准。联合子特性质量（原 `checklists/joint-spec-quality.md`）：权威需求以 **spec.md** 为准。

---

## 实现记录

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
| 增加 **`openpyxl>=3.1.0`** | 与本 plan **技术调研**、解析栈一致，用于读写 `.xlsx/.xlsm` |

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

**Phase 8～10（T027～T037）已落地**：`parse_frameinfo.py`、`parse_threads.py`、`correlate.py`、`threads_top.py`、`compare.py`；`load_and_analyze` 合并帧统计与线程/频点关联；GUI 关联分析与双会话对比；详见 [tasks.md](./tasks.md) 勾选与源码。

---

## 4. 插件模块 `modules/game_perf/`（联合分析衔接）

| 文件 | 职责 |
|------|------|
| `src/joint_adapter.py` | **`policy_snapshot_from_parser(parser, package, mode)`** → `PolicySnapshot`（`FreqRow` → `FreqPolicyRow`，BindCore / PerfHint 摘要） |
| `src/gui_tab.py` | **`_publish_joint_policy_snapshot`**：刷新表/策略后写入 **`context["gp_joint_policy_snapshot"]`**（`model_dump(mode="json")`）；无解析器或未选游戏/模式/解析失败时 **pop** 键；**不依赖设备**即可更新快照 |

---

## 5. 插件模块 `modules/perfdog_insights/`

与 **`game_perf`** 同构：**`tests/`、`fixtures/`、`assets/`、`specs/004-perfdog-import-insights/`（索引）、`.specify/`、`.cursor/commands/`**；模块内 `specs/004-*/` 仅链到本目录正文，避免重复编辑。

| 文件 | 职责 |
|------|------|
| `manifest.json` | `provides.gui=true`；**`dependencies.toolkit_modules`**：`device_disguise`、`game_perf`、`perfetto_capture`，保证 **插件加载顺序** 在既有三模块之后，**侧栏 Tab 位于「设备伪装」下方** |
| `src/plugin.py` | `register_gui_tab` → **`PerfdogInsightsTab`**；CLI `perfdog`；`on_startup` 注册 **`pdi_service`** |
| `src/gui_tab.py` | **`BaseTab`**：`tab_title="PerfDog分析"`；从 **`context["pdi_service"]`** 取 **`PerfdogInsightsService`**（缺失则临时实例化）；**联合分析** / **对比** / **导出** 均经 Service；**联合结论区** 与 **不因无设备禁用** 行为不变 |
| `src/analysis_worker.py` | **`QThread`**：注入 **`PerfdogInsightsService`**，子线程调用 **`service.load_report`**（`interrupt_check` 同前） |
| `src/joint_worker.py` | **`JointAssessmentWorker`**：`report_path` + `policy` dict + **`PerfdogInsightsService`** + `skip_package_warning`；`load_report` 后 **`assess_joint_from_loaded_report`** |
| `src/service.py` | **业务门面**：`load_report`、`assess_joint_from_loaded_report`、`compare_reports_pair`、`compose_export_markdown`（无 PyQt/Typer） |
| `src/cli_commands.py` | **`perfdog info`** → **`PerfdogInsightsService.get_service_info`** |
| `src/models.py` | 跨 GUI/CLI 类型再导出（`AnalysisReport` 等） |
| `tests/test_service.py` | `PerfdogInsightsService` 单测 |
| `AGENTS.md` | 与 `game_perf` 同目录结构（概述 / 边界 / 测试） |
| `.specify/`、`.cursor/` | 模块级 Speckit（自 `game_perf` 复制并改写 constitution） |
| `src/migrations/.gitkeep` | 占位（当前无 DB 迁移） |

**契约说明**：[API 契约：core.perfdog 分析 API](#api-契约coreperfdog-分析-api) 中的 Worker 信号名为示例；实现侧为 **`finished_ok` / `finished_err`**（语义等价于成功/失败回调）。

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
| [plan.md#快速开始](#快速开始) | 开发入口与 pytest 命令（原 quickstart） |
| [tasks.md](./tasks.md) | MVP、联合分析、FrameInfo/对比等任务勾选与 [tasks.md](./tasks.md) 同步 |
| 本 plan 概述 / 架构 | **三文件规范** 与 **实际路径**（避免误读 `source/`） |

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
| 2026-03-22 | **文档**：原 `specs/005-gameperf-perfdog-analysis/` 中 spec/plan/research/data-model/quickstart/contract/checklist **并入本目录**（见 [spec.md](./spec.md) **US9～US11**、[plan.md](./plan.md) 联合分析小节与 [API 契约：联合分析](#api-契约联合分析)）。**代码** `joint_assessment` 等实现落地后请再追加本条。 |
| 2026-03-22 | **路径**：全量规格由 `specs/001-perfdog-import-insights/` **迁回** `specs/004-perfdog-import-insights/`；`001-perfdog-import-insights` 目录已删除；**SPECIFY_FEATURE** 使用 **`004-perfdog-import-insights`**。 |
| 2026-03-19 | **联合分析 T038**：新增 `toolkit/sdk/joint_models.py`（`PolicySnapshot`、`FreqPolicyRow`、`ObservationsSnapshot`、`FindingRef`/`RecRef`、`JointAssessmentReport`、`JointSuggestion`、`JointAssessOptions`），并由 `toolkit.sdk` 导出；对齐 [数据模型](#数据模型) 联合分析实体。 |
| 2026-03-22 | **联合分析 T039～T056 落地**：`toolkit/core/joint_assessment/{observations,engine,export_md}.py`；`modules/game_perf/src/joint_adapter.py` + `gui_tab._publish_joint_policy_snapshot`；`modules/perfdog_insights/src/joint_worker.py` + `gui_tab` 联合分析 UI/导出拼接（JA-FR-007）；契约见 [API 契约：联合分析](#api-契约联合分析) §5。 |
| 2026-03-22 | **T027～T037**：`parse_frameinfo.py` / `parse_threads.py` / `correlate.py` / `threads_top.py` / `compare.py`；`load_and_analyze` 合并帧统计与线程/频点关联；`gui_tab` 关联分析区 +「添加对比文件」与 FR-012 确认；导出含对比节；`doc/README.md` 增加 PerfDog 入口说明。 |
| 2026-03-22 | **`perfdog_insights` 分层重构**：`PerfdogInsightsService` 承载解析/联合/对比/导出拼接；`analysis_worker` / `joint_worker` 注入 Service；`gui_tab` 不再直接 `import load_and_analyze` / `compare_reports`；新增 **`AGENTS.md`**；与本 plan **API 契约** 两节及联合契约 **§5** 修订表已同步。 |
| 2026-03-22 | **模块目录与 `game_perf` 对齐**：新增 **`tests/`**、**`fixtures/`**、**`assets/`**、**`specs/004-perfdog-import-insights/`**（链到根规格）、**`.specify/`** / **`.cursor/commands/`**（自 game_perf 复制）；**`src/models.py`**；**`run_all_tests.py`** 登记本模块测试组；**`AGENTS.md`** 改为与 game_perf 同结构。 |
| 2026-03-22 | **规格三文件规范**：与 `specs/003-adb-enhancement` 对齐，本目录仅保留 `spec.md` / `plan.md` / `tasks.md`；原 `data-model.md`、`research.md`、`contracts/*`、`quickstart.md`、`implementation.md`、`checklists/*`、`image/*` 已并入 **本 plan** 对应章节；`tasks.md` / `spec.md` / 模块索引与 `doc/README` 链接已改为 **plan 锚点**。 |

---

## 10. 后续建议（非本文档范围实现）

- 维护 **脱敏多版本 xlsx 夹具**（本 plan **[技术调研](#技术调研)** Open Items）。  
- PyInstaller **hiddenimports** 确认 `openpyxl`（若打包缺失再补）。  

