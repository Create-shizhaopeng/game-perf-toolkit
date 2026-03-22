"""异常时间窗内线程 CPU Top-N（@ThreadCpuUsageData）。"""

from __future__ import annotations

import pandas as pd

from toolkit.core.perfdog.report_types import (
    Finding,
    FindingSeverity,
    ThreadTopEntry,
)


def pick_anomaly_window_ms(findings: list[Finding]) -> tuple[float, float] | None:
    """优先 critical > warn，取首个带时间的 finding 窗口。"""
    scored: list[tuple[int, float, float]] = []
    for f in findings:
        if f.time_start_ms is None:
            continue
        rank = 0
        if f.severity == FindingSeverity.critical:
            rank = 3
        elif f.severity == FindingSeverity.warn:
            rank = 2
        else:
            rank = 1
        te = float(f.time_end_ms if f.time_end_ms is not None else f.time_start_ms)
        scored.append((rank, float(f.time_start_ms), te))
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], x[1]))
    _, ts, te = scored[0]
    return ts, te


def thread_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if str(c).startswith("thread::")]


def top_threads_in_window(
    thread_df: pd.DataFrame,
    t0: float,
    t1: float,
    *,
    top_n: int = 5,
) -> list[ThreadTopEntry]:
    if "time_ms" not in thread_df.columns or thread_df.empty:
        return []
    tt = pd.to_numeric(thread_df["time_ms"], errors="coerce")
    mask = (tt >= t0) & (tt <= t1)
    sub = thread_df.loc[mask]
    if sub.empty:
        return []
    cols = thread_columns(thread_df)
    if not cols:
        return []
    entries: list[ThreadTopEntry] = []
    for c in cols:
        s = pd.to_numeric(sub[c], errors="coerce")
        if s.dropna().empty:
            continue
        entries.append(
            ThreadTopEntry(
                thread_label=str(c).removeprefix("thread::"),
                mean_pct_in_window=round(float(s.mean()), 4),
                peak_pct_in_window=round(float(s.max()), 4),
            ),
        )
    entries.sort(key=lambda e: e.mean_pct_in_window, reverse=True)
    return entries[:top_n]


def attach_thread_top_to_findings(
    findings: list[Finding],
    thread_df: pd.DataFrame,
    window_ms: int,
    top_n: int = 5,
) -> None:
    """为带时间的 finding 写入 ``evidence['thread_top_in_window']``（序列化列表）。"""
    if "time_ms" not in thread_df.columns:
        return
    tt = pd.to_numeric(thread_df["time_ms"], errors="coerce")

    for f in findings:
        if f.time_start_ms is None:
            continue
        t0 = float(f.time_start_ms) - window_ms
        t1 = float(f.time_end_ms if f.time_end_ms is not None else f.time_start_ms) + window_ms
        mask = (tt >= t0) & (tt <= t1)
        if not mask.any():
            continue
        top = top_threads_in_window(thread_df, t0, t1, top_n=top_n)
        if not top:
            continue
        ev = dict(f.evidence or {})
        ev["thread_top_in_window"] = [
            {
                "thread": e.thread_label,
                "mean_pct": e.mean_pct_in_window,
                "peak_pct": e.peak_pct_in_window,
            }
            for e in top
        ]
        f.evidence = ev
