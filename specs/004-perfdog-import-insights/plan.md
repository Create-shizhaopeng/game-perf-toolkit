# Implementation Plan: PerfDog 导入与性能洞察报告

**Branch**: `004-perfdog-import-insights` | **Date**: 2026-03-21 | **Spec**: [spec.md](./spec.md)  
**Location**: `lv-game-toolkit/specs/004-perfdog-import-insights/`（由 MojitoTools 根目录初稿迁入本仓库；曾短暂使用 `001-perfdog-import-insights` 目录名，已迁回 **004**）  
**Input**: 用户要求 — **Python** 实现，**未来集成到 lv-game-toolkit（Toolkit）**。

**实现状态与变更总账**：见 **[implementation.md](./implementation.md)**（所有已落地修改、路径差异、Data_v4 兼容策略均在此维护）。

## Summary

在 **Toolkit**（`lv-game-toolkit`，PyQt6）中新增 **「PerfDog 分析」** 选项卡：用户拖拽 PerfDog 导出的 **.xlsx**，在后台线程解析 `all` / `@FrameInfo` / `@ThreadCpuUsageData`，生成**摘要、问题洞察、启发式建议**；支持 **Markdown/文本导出与复制**；**二期**可做双会话 A/B 对比（FR-011 SHOULD）。

**技术路线（已落地）**：**纯 Python 核心库**（**`toolkit/core/perfdog/`**）负责解析与洞察；**GUI 插件**（**`modules/perfdog_insights/`**）负责拖拽、进度、展示与导出；与 UI 解耦，便于单测。初稿中的 `source/core`、`source/ui` **未采用**，以 **implementation.md** 为准。

## Technical Context

| 项 | 选择 |
|----|------|
| **Language/Version** | Python **3.10+**（与现有 `lv-game-toolkit/source` 对齐，推荐 3.11） |
| **Primary Dependencies** | **PyQt6**（已有）、**pandas**、**openpyxl**；可选 **read_only** 大表用 `openpyxl` streaming |
| **Storage** | 无服务端 DB；可选 `data/perfdog_last_path.json`（FR-014 SHOULD，仅存路径/文件名，可关） |
| **Testing** | **pytest**；核心解析/检测用**固定 xlsx 夹具**（脱敏小样例） |
| **Target Platform** | Windows 10/11 x64（与 Toolkit 一致） |
| **Project Type** | 桌面应用内嵌模块（**core 可独立单测**） |
| **Performance Goals** | 与 spec **SC-001** 一致：标准体量（如帧表 ≤~1M 行）**10 分钟内**首屏摘要；解析阶段 UI **≤2s** 须有反馈（**NF-001**） |
| **Constraints** | **完全离线**（FR-017）；内存上限在实现中约定（如帧表 **>80 万行**提示截取导出，见 **NF-002**） |
| **Scale/Scope** | 单用户本机；首期 **MVP** = US1,8 + US2,4,6,7 + FR-010；**P3** = US3,5（线程/频点深化 + A/B） |

## Constitution Check

仓库内 `.specify/memory/constitution.md` 仍为模板占位，**不作硬性门禁**。本计划采用通用门禁：

- [x] 与 [spec.md](./spec.md) 范围一致（Out of Scope 不实现）  
- [x] Phase 0 **research.md** 已关闭主要技术选型  
- [x] 推断结论符合 **FR-008**（措辞模板在 `recommendations` 模块）  

**Complexity Tracking**：不填（无 constitution 违规需特批）。

## 架构与模块

**（下图路径为仓库实际结构；二期文件见 tasks.md T027+）**

```text
┌──────────────────────────────────────────────────────────────┐
│  modules/perfdog_insights/src/gui_tab.py                     │
│    拖拽区、进度、报告视图、导出/复制                           │
│         │ signals/slots                                       │
│         ▼                                                     │
│  modules/perfdog_insights/src/analysis_worker.py (QThread)    │
│    调用 toolkit.core.perfdog.load_and_analyze                 │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│  toolkit/core/perfdog/                                         │
│    workbook.py      打开 xlsx、多表/ Data_v4 标记、表头行      │
│    parse_all.py     DeviceInfo + Stat + Data_v4 → DataFrame   │
│    session.py       SessionSummary 构建                        │
│    detect.py        尖刺、低帧段、温度等 Finding               │
│    recommendations.py  规则 → 建议列表（可追溯 finding id）     │
│    export_md.py     报告 → Markdown 文本                       │
│    （二期占位）parse_frameinfo / parse_threads / correlate /    │
│                 threads_top / compare — 见 tasks.md            │
└────────────────────────────────────────────────────────────────┘
```

**主窗口集成**：`toolkit/app.py` 通过 **`register_gui_tab`** 钩子挂载；**不依赖** `AdbManager` 连接状态即可启用（**FR-013**）。

## 关键产品决策（落实 spec 留白）

| 主题 | 决策 |
|------|------|
| **Stat 行 vs Data_v4 重算** | **主结论以 Data_v4 重算为准**；若与 `all` 表 Stat 行差异 > 约定阈值（如 FPS 均值差 >1%），在报告脚注提示「与 PerfDog 汇总行不一致，已以序列为准」。 |
| **「异常时段附近」窗口** | 默认 **±5 秒**（按 `time` 列单位校准为 ms 或 s）；可在 `core/perfdog/config_defaults.py` 常量中调整。 |
| **尖刺 / 低帧阈值** | **低帧秒**：FPS < 目标 × 0.85（目标从序列 P95 或 Stat 推断， cap 144/120/90/60）；**长帧**：`@FrameInfo` 中单帧 ms > 1000/目标帧率 × 1.8；**温度**：列存在时环比前后窗口 Δ 与绝对值组合规则见 `detect.py` 注释与附录。 |
| **FR-013「P1～P4」** | 规范笔误风险：实现范围以 **User Story** 为准；MVP = **US1, US8, US2, US4, US6, US7**；**US3, US5** 为第二阶段。 |
| **取消长解析** | `QThread` + `requestInterruption()`；openpyxl/pandas 循环中检查 `isInterruptionRequested()`；无法立即中断时 FR-015  fallback 文案。 |

## Project Structure

### Documentation（本特性）

```text
specs/004-perfdog-import-insights/
├── plan.md
├── implementation.md      # 实现记录（路径差异、文件清单、修订历史）
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
├── contracts/
│   └── analysis_api.md
├── checklists/
└── spec.md
```

### Source Code（实际仓库：`lv-game-toolkit`）

```text
lv-game-toolkit/
├── pyproject.toml              # dependencies 含 openpyxl>=3.1.0
├── toolkit/core/perfdog/       # 本特性核心（MVP 已实现）
│   ├── __init__.py
│   ├── errors.py
│   ├── config_defaults.py
│   ├── column_aliases.py
│   ├── workbook.py
│   ├── parse_all.py
│   ├── session.py
│   ├── report_types.py
│   ├── detect.py
│   ├── recommendations.py
│   └── export_md.py
├── modules/perfdog_insights/
│   ├── manifest.json           # 依赖三模块，保证侧栏顺序
│   └── src/
│       ├── plugin.py
│       ├── gui_tab.py
│       ├── analysis_worker.py
│       ├── service.py
│       └── cli_commands.py
└── tests/test_perfdog_workbook.py
```

**Structure Decision**：核心在 **`toolkit/core/perfdog`**（框架代码，本特性经 spec 明确授权新增）；UI 在 **`modules/perfdog_insights`**，与 **game_perf** 等插件并列。详细变更见 **[implementation.md](./implementation.md)**。

## 分阶段交付

| 阶段 | 内容 | 验收锚点 |
|------|------|----------|
| **MVP** | 解析 `all` + Data_v4、基础 detect、建议、导出/复制、Tab、加载/清除 | SC-001～006、US1,2,4,6,7,8 |
| **v1.1** | `@FrameInfo` 并入洞察、SC-009 | FR-002 完整 |
| **v1.2** | `@ThreadCpuUsageData` + 频点关联 | US3、FR-005/006 |
| **v1.3** | A/B 对比 | US5、FR-011/012、SC-007 |

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 超大 `@FrameInfo` 内存 | `read_only=True` 流式迭代；超行数提前中止并提示 |
| 列名随 PerfDog 版本变化 | `column_aliases.py` 映射表 + 单元测试夹具多版本 |
| UI 线程卡死 | 所有 pandas/openpyxl 重活在 **QThread** |
| 乱码设备名 | 按 spec：原始字符串展示；openpyxl 默认 UTF-8 |

## Phase 2+（本命令范围外）

- `/speckit.tasks` → `tasks.md` 拆解开发任务  
- 实现完成后更新 `lv-game-toolkit/doc/` 用户说明（可选）  
- **每次合并实现**：在 **[implementation.md](./implementation.md)** 追加修订记录，并视需要同步本 plan 的架构图/目录树

---

## Complexity Tracking

（无）

---

## 子特性：游戏性能策略 × PerfDog 联合分析

**Spec**：[spec.md](./spec.md)（**US9～US11**，**JA-FR / JA-SC**） · **Tasks**：[tasks.md](./tasks.md) Phase 12～16 · **Research**：[research.md](./research.md)（JA-R1～R6） · **Data model**：[data-model.md](./data-model.md) 联合实体 · **Contract**：[contracts/joint_assessment_api.md](./contracts/joint_assessment_api.md)

> 原独立目录 `specs/005-gameperf-perfdog-analysis/` 的 plan 已 **合并到本节**。**权威规格目录**：`specs/004-perfdog-import-insights/`（曾用编号 **004**，见 [spec.md](./spec.md) 修订记录）。

### Summary

在 **不新增独立顶层插件** 的前提下，于 **`toolkit/core/joint_assessment`** 实现联合研判（纯函数 + pytest）；**`toolkit/sdk/joint_models.py`** 定义 Pydantic 模型。**`modules/game_perf`** 从 `GamePerfParser` 生成 **PolicySnapshot** 写入 **`context`（`gp_` 前缀键）**。**`modules/perfdog_insights`** 在已有 **AnalysisReport** 上触发 **联合分析**、展示结论与绑核/频点建议，**合并导出 Markdown**。**禁止**自动改机（**JA-FR-008**）。

### 架构（联合分析）

```text
modules/game_perf/src/gui_tab.py
    加载/切换游戏模式 → policy_snapshot_from_parser(...) → context["gp_joint_policy_snapshot"]
modules/perfdog_insights/src/gui_tab.py + joint_worker.py
    「联合分析」→ build_observations_snapshot + assess_joint → JointAssessmentReport
toolkit/core/joint_assessment/
    observations.py, engine.py, export_md.py
toolkit/core/perfdog/report_types.py   ← AnalysisReport（已有）
```

### 分阶段（联合子特性）

| 阶段 | 内容 | 验收 |
|------|------|------|
| **JA-MVP** | Phase 12 + 13（[tasks.md](./tasks.md) T038～T048） | **US9**、**JA-SC-001** |
| **JA-P2** | Phase 14（T049～T051） | **US10**、合并导出 |
| **JA-P3** | Phase 15～16 | **US11**、文档与契约 |

### Constitution（联合）

- **IV**：`joint_assessment` **不得** `import modules.*`。
- **V**：研判逻辑无 PyQt。
- **质量门禁**：`gp_` context 键；QThread + **pyqtSignal**。
