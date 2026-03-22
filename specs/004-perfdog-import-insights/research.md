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

**已实现说明**：MVP 代码路径、列别名与 Data_v4 探测策略见 **[implementation.md](./implementation.md)**；新增版本验证结论请同步更新该文档 **§8 / §9**。

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
