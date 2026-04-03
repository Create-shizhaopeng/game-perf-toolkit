# Contract: GamePerfConfigDiffService（`workspace_tools` 模块内）

**Feature**: 007-gameperf-config-diff | **Consumer**: `workspace_tools` GUI（如 `WorkspaceToolsTab` 内子页）/ 可选 CLI（`workspace` 命名空间下子命令）

本契约描述 **Service 层对外能力**（纯 Python，无 Qt）。方法名为逻辑名，实现时可微调但 **语义必须等价**。

## 模块边界

- 实现位于 **`modules/workspace_tools`**，`context` 键使用 **`wo_` 前缀**（如 `wo_gameperf_diff_service`）。
- **禁止** `import modules.game_perf.src.*`；设备路径、文件名规则与 **性能配置** 模块 **产品约定对齐**（常量可在本模块内复制文档化字符串，或后续上沉至 `toolkit`）。

## 类型约定

- 路径均为 **绝对路径** 字符串（UTF-8）。
- 进度/日志：`(message: str) -> None` 可选回调。
- 失败：使用本模块内语义异常（如 `DiffValidationError`、`XmlValidationError` 等价物）；**不得** 仅以裸 `Exception` 对外。

## 方法

（与前一版 `GamePerfDiffService` 契约一致，类名实现阶段可定为 `GamePerfConfigDiffService`。）

### `load_session(baseline_path: str) -> ComparisonSession`

### `add_comparator_local(path: str) -> None`

### `add_comparator_from_device(serial: str, cancel_event: threading.Event | None = None) -> None`

### `set_active_comparator(index: int) -> None`

### `run_diff() -> list[DiffItem]`

### `apply_merge(diff_item_id: str, side: str, comparator_index: int) -> None`

### `undo_merge() -> tuple[bool, str]`

成功为 `(True, 描述)`，`描述` 含语义路径与采纳侧（供日志）；无可撤销为 `(False, "")`。

### `reset_merge() -> None`

### `save_merged_as(target_path: str, *, atomic: bool = True) -> None`

### `get_merge_dirty() -> bool`

## GUI 侧约定

- 保存前 **QMessageBox**（或等价）确认后再调用 `save_merged_as`。
- `run_diff`、`add_comparator_from_device` 在 **QThread** 中执行，经 **pyqtSignal** 回传结果或错误。

## CLI 可选（P3）

- `toolkit workspace <subcommand> ...`（具体子命令名在 tasks 中定稿），`--json-out` 输出与 `DiffItem` 对齐的结构化报告。
