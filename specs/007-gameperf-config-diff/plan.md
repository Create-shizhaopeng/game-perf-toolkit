# Implementation Plan: gameperfconfig 多文件对比与合并

**Branch**: `007-gameperf-config-diff` | **Date**: 2026-04-03 | **Spec**: [spec.md](./spec.md)  
**Input**: 根目录规格 `/specs/007-gameperf-config-diff/spec.md`

## Summary

在 **`modules/workspace_tools`（侧边栏名：**性能配置对比**）** 内交付「多文件对比与合并」：用户选定 **一个基准 XML** 与 **多个对比源**（本地路径或从设备拉取的标准路径副本），在 **Service 层** 完成解析与语义级差异计算，在 **`WorkspaceToolsTab`** 内以子界面展示差异，支持 **按条采纳**、**保存前确认**、**原子写盘**。不自动 push 设备（规格 Out of Scope）。

**技术要点**：本模块内使用 **lxml** 实现解析/diff/合并；**禁止** `import modules.game_perf.src.*`。设备标准路径、gameperfconfig 文件名规则与 **game_perf 产品约定** 一致（常量在本模块文档化复制或后续上沉 `toolkit`）。ADB 通过 **`context["adb"]`**（与框架注入一致）拉取设备文件。新增 **`GamePerfConfigDiffService`**（或等价命名）与 **`wo_` context 键**；GUI 长任务 **`QThread` + `pyqtSignal`**。

## Technical Context

| 项 | 内容 |
|----|------|
| **Language/Version** | Python 3.12+ |
| **Primary Dependencies** | PyQt6、lxml、Typer/Rich（CLI 可选）；框架 `AdbManager`（经 context） |
| **Storage** | 本地 XML；设备 pull 缓存目录语义与 game_perf **路径约定对齐**（如 `data/pull_cache/<serial>/`，实现 tasks 定稿） |
| **Testing** | `modules/workspace_tools/tests/` pytest + mock |
| **Target Platform** | Windows 10+ 桌面（与 LVGT 一致） |
| **Project Type** | 插件模块 **`workspace_tools`** 扩展 |
| **Performance Goals** | **SC-004**：单文件 ≤10MB，diff + 可交互呈现 **≤ 8s（P95）**（样机可 ±2s） |
| **Constraints** | 禁止修改 `toolkit/`；Service 无 PyQt；**`wo_` context 前缀**；禁止跨模块 import `src/` |
| **Scale/Scope** | 1 基准 + 建议 ≤10 对比文件 |

## Constitution Check

| 原则 | 结论 |
|------|------|
| I Plugin-First | 功能落在独立模块 **`workspace_tools`**，符合优先独立模块。 |
| II 三端统一 | Service API；GUI 调 Service；CLI 可选挂 `workspace` 命名空间。 |
| III Agent | 可选后续 `register_agent_tools`。 |
| IV 依赖反转 | 仅 `toolkit.sdk.*` / `hookspecs`；不 import `game_perf` 实现。 |
| V 表现分离 | `service.py` 无 PyQt。 |
| VI 开闭 | 不改 `toolkit/`。 |
| VII Spec-Driven | 与 spec FR/SC 对齐。 |

**GATE**：通过。

## Project Structure

### Documentation（本特性）

```text
specs/007-gameperf-config-diff/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── gameperf_config_diff.md
├── checklists/
└── tasks.md               # 任务拆解（与 spec 细化同步）
```

### 模块内索引（与 004 同型）

```text
modules/workspace_tools/specs/007-gameperf-config-diff/
├── spec.md
├── plan.md
├── tasks.md
├── quickstart.md
└── ui-design.md
```

### Source Code（实现落点）

```text
modules/workspace_tools/
├── src/
│   ├── gameperf_diff_service.py   # 建议：对比/合并/保存（纯同步）
│   ├── gui_tab.py                 # Tab 内增加「配置对比」子区或 QStackedWidget
│   ├── cli_commands.py            # 可选 workspace 子命令
│   └── plugin.py                  # context["wo_gameperf_diff_service"] 等
├── tests/
│   └── test_gameperf_diff_service.py
└── fixtures/                      # 成对差异样例 XML
```

**Structure Decision**：**全部实现与测试在 `workspace_tools`**；与 **game_perf** 仅 **约定对齐**（路径/校验策略），**代码不耦合**。

## Complexity Tracking

> 本计划不再引用「放入 game_perf 以复用 Parser」；复用需求通过 **本模块内 lxml 实现** 或 **后续 toolkit 公共层** 解决，避免违反模块 `src` 隔离。

| 主题 | 说明 |
|------|------|
| 与 game_perf 行为一致 | 文件名、`/system/etc/gameperfconfig.xml`、UTF-8 容错等 **对照 game_perf 文档与行为** 在本模块实现或抽共享常量；**不 import game_perf.src**。 |

## Phase 0 — Research（见 research.md）

（保持既有结论：语义 DOM diff、单活跃对比文件 UI、tmp+replace 写盘。）

## Phase 1 — Design（见 data-model.md、contracts/gameperf_config_diff.md、quickstart.md）

## Phase 2 — 实现（[tasks.md](./tasks.md)）

已拆解为 **T001–T022**（按 US 分 Phase）；MVP 边界见 tasks 文末。

---

## Post-Design Constitution Re-check

- Service / GUI 分离：**满足**  
- **`wo_` 前缀**：**满足**  
- 不改 toolkit：**满足**  
- 不 import 其他模块 `src/`：**满足**

## 实现记录（2026-04-03）

- **源码**：`gameperf_constants.py`、`gameperf_xml.py`、`gameperf_diff_errors.py`、`gameperf_diff_models.py`、`gameperf_diff_engine.py`、`gameperf_diff_service.py`；GUI 在 `gui_tab.py` 的 **配置对比** 子 Tab；`plugin.py` 注入 `context["wo_gameperf_diff_service"]`，并在缺省时设置 `context["adb"]`（`AdbManager`）。
- **测试**：`tests/test_gameperf_diff_service.py` + fixtures `gameperfconfig_diff_*.xml`。
- **契约**：与 `contracts/gameperf_config_diff.md` 方法名对齐。

