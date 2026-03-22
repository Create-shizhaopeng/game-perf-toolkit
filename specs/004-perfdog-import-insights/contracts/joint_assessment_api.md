# Contract: 游戏性能策略 × PerfDog 联合分析（Python）

**Feature**: `004-perfdog-import-insights` 子特性（**US9～US11**，见 [spec.md](../spec.md)）  
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

- **`JointAssessmentWorker`**（`joint_worker.py`）：构造参数为 **`report_path: str`**、**`policy_dict: dict`**（`PolicySnapshot.model_dump(mode="json")`）、**`skip_package_warning: bool`**；子线程内 **`load_and_analyze(report_path)`** 后 **`build_observations_snapshot`** + **`assess_joint`**。
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
| v1.1 | GUI 侧 Worker 定名为 **`JointAssessmentWorker`**；导出/复制 Markdown 的拼接约定为 **`build_markdown(report) + "\n\n" + build_joint_markdown(joint, base_report=None)`**（见 `modules/perfdog_insights/src/gui_tab.py` 中 `_compose_export_markdown` 注释，**JA-FR-007**）。 |
| v1.0 | 初版 §1 Core 签名与 `joint_models` 类型。 |
