"""按洞察时间段从 Data_v4 截取异常关联采样行（非全量）。"""

from __future__ import annotations

import pandas as pd

from toolkit.core.perfdog.data_table import dataframe_to_report_cells
from toolkit.core.perfdog.report_types import AnomalyDataChunk, Finding, SessionSummary


def _window_for_finding(f: Finding, pad_ms: float) -> tuple[float, float] | None:
    if f.time_start_ms is None:
        return None
    te = f.time_end_ms if f.time_end_ms is not None else f.time_start_ms
    lo = min(f.time_start_ms, te) - pad_ms
    hi = max(f.time_start_ms, te) + pad_ms
    return lo, hi


def build_anomaly_data_chunks(
    df: pd.DataFrame,
    findings: list[Finding],
    *,
    pad_ms: int,
) -> list[AnomalyDataChunk]:
    """每条带时间的 Finding 取 time_ms 落入 [起点,终点]±padding 的采样副本。"""
    if df.empty or "time_ms" not in df.columns:
        return []
    cap = max(0.0, min(float(pad_ms), 5000.0))
    tcol = pd.to_numeric(df["time_ms"], errors="coerce")
    chunks: list[AnomalyDataChunk] = []
    for f in findings:
        win = _window_for_finding(f, cap)
        if win is None:
            continue
        lo, hi = win
        mask = (tcol >= lo) & (tcol <= hi) & tcol.notna()
        sub = df.loc[mask]
        cols, rows = dataframe_to_report_cells(sub)
        chunks.append(
            AnomalyDataChunk(
                finding_id=f.id,
                finding_title=f.title,
                time_lo_ms=lo,
                time_hi_ms=hi,
                columns=cols,
                rows=rows,
            ),
        )
    return chunks


def build_non_anomaly_summary_zh(
    session: SessionSummary,
    summary_metrics: dict,
) -> str:
    """对其余时段的概括说明（不逐行罗列正常采样）。"""
    dur_s = (session.duration_ms / 1000.0) if session.duration_ms else None
    n = summary_metrics.get("采样点数")
    parts: list[str] = []
    if dur_s is not None:
        parts.append(f"记录时长约 {dur_s:.1f} s")
    if n is not None:
        parts.append(f"秒级采样约 {n} 点")
    head = "、".join(parts) if parts else "会话规模见上方「核心指标」"
    return (
        f"{head}。"
        "除下文「异常关联采样」各时段外，其余时间未命中本工具当前规则的 warn/critical 结论；"
        "正常区间不单独逐行展开，请以「核心指标」及 PerfDog 原始曲线为准。"
    )
