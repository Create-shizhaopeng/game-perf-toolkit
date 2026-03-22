"""Finding 时间窗内频点 / GPU 均值 vs 全段（US3 / FR-005）。"""

from __future__ import annotations

import pandas as pd

from toolkit.core.perfdog.report_types import Finding


def _freq_related_columns(df: pd.DataFrame) -> list[str]:
    out: list[str] = []
    for c in df.columns:
        cs = str(c)
        if cs.startswith("cpu_clock_") or cs in ("gpu_clock_mhz", "gpu_usage_pct"):
            out.append(cs)
    return out


def correlate_findings_with_freq(
    findings: list[Finding],
    df: pd.DataFrame,
    window_ms: int,
) -> None:
    """就地写入 ``evidence['freq_gpu_window_vs_global']``：``{列: (全段均值, 窗内均值)}``。"""
    if "time_ms" not in df.columns:
        return
    cols = _freq_related_columns(df)
    if not cols:
        return
    tseries = pd.to_numeric(df["time_ms"], errors="coerce")

    for f in findings:
        if f.time_start_ms is None:
            continue
        t0 = float(f.time_start_ms) - window_ms
        t1 = float(f.time_end_ms if f.time_end_ms is not None else f.time_start_ms) + window_ms
        mask = (tseries >= t0) & (tseries <= t1)
        sub = df.loc[mask]
        if sub.empty or len(sub) < 2:
            continue
        comp: dict[str, tuple[float, float]] = {}
        for col in cols:
            if col not in df.columns:
                continue
            g = pd.to_numeric(df[col], errors="coerce").mean()
            w = pd.to_numeric(sub[col], errors="coerce").mean()
            if pd.notna(g) and pd.notna(w):
                comp[col] = (round(float(g), 4), round(float(w), 4))
        if not comp:
            continue
        ev = dict(f.evidence or {})
        ev["freq_gpu_window_vs_global"] = comp
        f.evidence = ev
