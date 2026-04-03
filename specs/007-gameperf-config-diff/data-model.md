# Data Model: gameperfconfig 对比与合并

**Feature**: 007-gameperf-config-diff | **Date**: 2026-04-03

## 枚举与值对象

### `FileProvenance`

| 字段 | 类型 | 说明 |
|------|------|------|
| `kind` | `Literal["local","device_pull"]` | 来源类型 |
| `display_label` | `str` | UI 展示（含文件名或「设备 (serial)」） |
| `path` | `str \| None` | 本地路径；设备拉取为缓存路径 |
| `serial` | `str \| None` | 设备来源时 ADB serial |

### `DiffSeverity`

| 值 | 含义 |
|----|------|
| `missing_left` | 基准缺失 |
| `missing_right` | 对比侧缺失 |
| `value_changed` | 文本/属性值不同 |
| `order_changed` | 同级子节点顺序变化（若检测） |

## 核心实体

### `ComparisonSession`

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | `str` | UUID 或单调 id |
| `baseline_path` | `str` | 基准文件绝对路径 |
| `baseline_provenance` | `FileProvenance` | 通常为 local |
| `comparators` | `list[tuple[FileProvenance, str]]` | (来源, 解析用路径) |
| `active_comparator_index` | `int` | 当前 UI 选中的对比文件下标 |
| `status` | `Literal["idle","computing","ready","error"]` | 会话状态 |
| `parse_errors` | `list[str]` | 跳过文件时的可读错误 |

### `DiffItem`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 稳定键（如 path + 哈希） |
| `semantic_path` | `str` | 人类可读路径，如 `Game[pkg]/Mode[Normal]/TempLevel[0]/Gold` |
| `comparator_index` | `int` | 相对哪个对比文件 |
| `severity` | `DiffSeverity` | 见上 |
| `left_snippet` | `str \| None` | 基准侧摘要 |
| `right_snippet` | `str \| None` | 对比侧摘要 |
| `mergeable` | `bool` | 是否允许一键采纳 |

### `MergeOperation`（补丁栈元素）

| 字段 | 类型 | 说明 |
|------|------|------|
| `diff_item_id` | `str` | 对应 `DiffItem.id` |
| `side` | `Literal["baseline","comparator"]` | 采纳侧 |
| `comparator_index` | `int` | 当 side 为 comparator 时有效 |
| `payload` | `opaque` | 实现层：XPath 片段或节点序列化（由实现定，不对 GUI 暴露） |

### `MergeSnapshot`

| 字段 | 类型 | 说明 |
|------|------|------|
| `working_tree_ref` | opaque | 工作副本 DOM 或 parser 包装 |
| `operation_stack` | `list[MergeOperation]` | 支持撤销 |
| `is_dirty` | `bool` | 相对基准是否已修改 |

## 状态转换（简图）

```text
idle →（选择文件）→ idle
idle →（开始对比）→ computing → ready | error
ready →（采纳/撤销）→ ready（is_dirty 变化）
ready →（保存确认 OK）→ idle（或保持 ready 且 is_dirty=false，由产品定；建议保存后标记已落盘）
```

## 校验规则

- 进入 `computing` 前：基准与所有对比路径 **通过** `is_valid_config_filename`（若适用）+ **XML 良构**校验（与 push 前校验一致）。
- `MergeSnapshot.is_dirty == False` 时，保存按钮可禁用或仅允许「另存为」—— **实现阶段与 UE 一致即可**（spec 未强制）。
