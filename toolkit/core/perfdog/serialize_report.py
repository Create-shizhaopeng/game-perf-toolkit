"""AnalysisReport → 纯 dict / JSON（供自定义 UI、脚本、自动化，与 PyQt 无关）。"""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from enum import Enum
from typing import Any

from toolkit.core.perfdog.report_types import (
    AnalysisReport,
    AnomalyDataChunk,
    Finding,
    FrameStats,
    Recommendation,
    SessionSummary,
    ThreadTopEntry,
)


def _sanitize(v: Any) -> Any:
    """仅保留 JSON 友好结构；未知类型转 str。"""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, dict):
        return {str(k): _sanitize(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_sanitize(x) for x in v]
    return str(v)


def _session_dict(s: SessionSummary) -> dict[str, Any]:
    return _sanitize(asdict(s))


def _frame_stats_dict(fs: FrameStats | None) -> dict[str, Any] | None:
    if fs is None:
        return None
    return _sanitize(asdict(fs))


def _finding_dict(f: Finding) -> dict[str, Any]:
    return {
        "id": f.id,
        "category": f.category.value,
        "severity": f.severity.value,
        "title": f.title,
        "detail": f.detail,
        "time_start_ms": f.time_start_ms,
        "time_end_ms": f.time_end_ms,
        "evidence": _sanitize(f.evidence or {}),
    }


def _recommendation_dict(r: Recommendation) -> dict[str, Any]:
    return _sanitize(asdict(r))


def _thread_top_dict(e: ThreadTopEntry) -> dict[str, Any]:
    return _sanitize(asdict(e))


def _chunk_dict(ch: AnomalyDataChunk, *, include_rows: bool) -> dict[str, Any]:
    d: dict[str, Any] = {
        "finding_id": ch.finding_id,
        "finding_title": ch.finding_title,
        "time_lo_ms": ch.time_lo_ms,
        "time_hi_ms": ch.time_hi_ms,
        "wall_clock_zh": ch.wall_clock_zh,
        "resource_summary_zh": list(ch.resource_summary_zh),
        "thread_summary_zh": list(ch.thread_summary_zh),
        "metrics_time_lo_ms": ch.metrics_time_lo_ms,
        "metrics_time_hi_ms": ch.metrics_time_hi_ms,
        "columns": list(ch.columns),
    }
    if include_rows:
        d["rows"] = [list(r) for r in ch.rows]
    else:
        d["row_count"] = len(ch.rows)
    return d


def report_to_plain_dict(
    report: AnalysisReport,
    *,
    include_chunk_rows: bool = True,
) -> dict[str, Any]:
    """将报告转为嵌套 dict（默认含异常切片 TSV 行，体量大时可 `include_chunk_rows=False`）。"""
    chunks = [
        _chunk_dict(ch, include_rows=include_chunk_rows)
        for ch in report.anomaly_data_chunks
    ]
    fi = report.frameinfo_window_chunk
    fi_dict = None
    if fi is not None:
        fi_dict = _chunk_dict(fi, include_rows=include_chunk_rows)

    return {
        "schema_version": 1,
        "session": _session_dict(report.session),
        "summary_metrics": _sanitize(report.summary_metrics),
        "findings": [_finding_dict(f) for f in report.findings],
        "recommendations": [_recommendation_dict(r) for r in report.recommendations],
        "frame_stats": _frame_stats_dict(report.frame_stats),
        "thread_top": [_thread_top_dict(e) for e in (report.thread_top or [])],
        "compare_note": report.compare_note,
        "stat_row_disclaimer": report.stat_row_disclaimer,
        "source_path": report.source_path,
        "unrecognized_columns": list(report.unrecognized_columns),
        "has_thread_cpu_sheet": report.has_thread_cpu_sheet,
        "anomaly_sample_pad_ms": report.anomaly_sample_pad_ms,
        "non_anomaly_summary_zh": report.non_anomaly_summary_zh,
        "anomaly_data_chunks": chunks,
        "frameinfo_window_chunk": fi_dict,
    }


def report_to_json(
    report: AnalysisReport,
    *,
    include_chunk_rows: bool = True,
    ensure_ascii: bool = False,
    indent: int | None = 2,
) -> str:
    """UTF-8 JSON 文本。"""
    payload = report_to_plain_dict(report, include_chunk_rows=include_chunk_rows)
    return json.dumps(
        payload,
        ensure_ascii=ensure_ascii,
        indent=indent,
        allow_nan=False,
    )
