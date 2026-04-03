"""gameperfconfig 对比数据模型（对齐 specs/007 data-model 与契约）"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

FileProvenanceKind = Literal["local", "device_pull"]
SessionStatus = Literal["idle", "computing", "ready", "error"]
DiffSeverityType = Literal["missing_left", "missing_right", "value_changed", "order_changed"]
MergeSide = Literal["baseline", "comparator"]


@dataclass
class FileProvenance:
    """文件来源。"""

    kind: FileProvenanceKind
    display_label: str
    path: str | None
    serial: str | None = None


@dataclass
class DiffItem:
    """单条语义差异。"""

    id: str
    semantic_path: str
    comparator_index: int
    severity: DiffSeverityType
    left_snippet: str | None
    right_snippet: str | None
    mergeable: bool
    # 实现层：供 apply_merge 使用，不对 GUI 暴露
    merge_spec: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class ComparisonSession:
    """一次对比会话摘要。"""

    session_id: str
    baseline_path: str
    baseline_provenance: FileProvenance
    comparators: list[tuple[FileProvenance, str]]
    active_comparator_index: int
    status: SessionStatus
    parse_errors: list[str]


@dataclass
class MergeOperation:
    """补丁栈元素（记录用）。"""

    diff_item_id: str
    side: MergeSide
    comparator_index: int
    payload: Any
