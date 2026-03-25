"""PerfDog 分析报告数据结构（对齐 data-model.md）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class FindingCategory(str, Enum):
    drop = "drop"
    stability = "stability"
    thermal = "thermal"
    power = "power"
    freq = "freq"
    thread = "thread"


class FindingSeverity(str, Enum):
    info = "info"
    warn = "warn"
    critical = "critical"


@dataclass
class SessionSummary:
    package_name: str | None = None
    device_name: str | None = None
    perfdog_version: str | None = None
    record_started_at: str | None = None
    duration_ms: int | None = None
    target_fps_hint: int | None = None


@dataclass
class FrameStats:
    """@FrameInfo 聚合（MVP 可为空；Phase 8 填充）。"""

    count: int = 0
    mean_ms: float = 0.0
    p99_ms: float = 0.0
    max_ms: float = 0.0
    over_budget_count: int = 0
    max_frame_time_ms: float = 0.0
    max_frame_at_ms: float | None = None


@dataclass
class ThreadTopEntry:
    thread_label: str
    mean_pct_in_window: float
    peak_pct_in_window: float


@dataclass
class Finding:
    id: str
    category: FindingCategory
    severity: FindingSeverity
    title: str
    detail: str
    time_start_ms: float | None = None
    time_end_ms: float | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class Recommendation:
    id: str
    finding_ids: list[str]
    text: str
    category: str  # 复现条件 / 采集建议 / 环境 等


@dataclass
class AnomalyDataChunk:
    """某条 Finding 在 Data_v4 上截取的异常关联采样（非全量）。"""

    finding_id: str
    finding_title: str
    time_lo_ms: float
    time_hi_ms: float
    columns: list[str]
    rows: list[list[str]]


@dataclass
class AnalysisReport:
    session: SessionSummary
    summary_metrics: dict[str, Any]
    findings: list[Finding]
    recommendations: list[Recommendation]
    frame_stats: FrameStats | None = None
    thread_top: list[ThreadTopEntry] | None = None
    compare_note: str | None = None
    stat_row_disclaimer: str | None = None
    source_path: str | None = None
    unrecognized_columns: list[str] = field(default_factory=list)
    has_thread_cpu_sheet: bool = False
    # 各洞察时间段对应的 Data_v4 采样切片（± anomaly_sample_pad_ms）
    anomaly_data_chunks: list[AnomalyDataChunk] = field(default_factory=list)
    anomaly_sample_pad_ms: int = 0
    non_anomaly_summary_zh: str = ""


@dataclass
class SessionComparePair:
    """双会话对比（data-model.md / FR-011）。"""

    session_a: SessionSummary
    session_b: SessionSummary
    delta_metrics: dict[str, tuple[Any, Any]]
    aligned_columns: list[str]
    warnings: list[str]


@dataclass
class AnalyzeOptions:
    """分析可选参数（contracts/analysis_api.md）。"""

    anomaly_window_ms: int = 5000
    max_frame_rows: int = 800_000
    locale: str = "zh_CN"
    interrupt_check: Callable[[], bool] | None = None
