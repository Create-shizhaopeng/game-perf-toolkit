"""异常时间窗内 Data_v4 / 线程摘要（CPU、GPU、各核、线程 Top）。"""

from __future__ import annotations

import pandas as pd

from toolkit.core.perfdog.report_types import AnomalyDataChunk
from toolkit.core.perfdog.threads_top import top_threads_in_window
from toolkit.core.perfdog.wall_clock import wall_clock_range_zh


def summarize_datav4_window(df: pd.DataFrame, t_lo_ms: float, t_hi_ms: float) -> list[str]:
    """窗内应用/整机/GPU/各核频与占用的一小段可读摘要。"""
    lines: list[str] = []
    if df.empty or "time_ms" not in df.columns:
        return ["（无 Data_v4）"]
    t = pd.to_numeric(df["time_ms"], errors="coerce")
    mask = (t >= t_lo_ms) & (t <= t_hi_ms) & t.notna()
    if not mask.any():
        return ["（该时间窗内无 Data_v4 采样行）"]
    sub = df.loc[mask]

    def _line(col: str, label: str, nd: int = 2) -> None:
        if col not in sub.columns:
            return
        s = pd.to_numeric(sub[col], errors="coerce").dropna()
        if s.empty:
            return
        lines.append(
            f"- **{label}**：窗内均值≈{round(float(s.mean()), nd)}，最小≈{round(float(s.min()), nd)}，"
            f"最大≈{round(float(s.max()), nd)}",
        )

    _line("app_cpu_pct", "应用 CPU %")
    _line("total_cpu_pct", "整机 CPU %")
    _line("gpu_usage_pct", "GPU 占用 %")
    _line("gpu_clock_mhz", "GPU 频率 MHz", 0)

    core_bits: list[str] = []
    for i in range(8):
        clk = f"cpu_clock_{i}_mhz"
        usage = f"cpu_usage_{i}_pct"
        if clk in sub.columns:
            s = pd.to_numeric(sub[clk], errors="coerce").dropna()
            if not s.empty:
                core_bits.append(
                    f"CPU{i}频 均≈{round(float(s.mean()), 0):.0f}MHz",
                )
        if usage in sub.columns:
            s = pd.to_numeric(sub[usage], errors="coerce").dropna()
            if not s.empty:
                core_bits.append(
                    f"CPU{i}占 均≈{round(float(s.mean()), 1)}%",
                )
    if core_bits:
        lines.append("- **各核（窗内均值）**：" + "；".join(core_bits[:16]))
        if len(core_bits) > 16:
            lines.append(f"  （另有 {len(core_bits) - 16} 项，详见下方 TSV 列）")

    return lines


def thread_summary_lines(
    thread_df: pd.DataFrame | None,
    t_lo_ms: float,
    t_hi_ms: float,
    *,
    top_n: int = 8,
) -> list[str]:
    if thread_df is None or thread_df.empty:
        return ["（无 @ThreadCpuUsageData 或未读入线程表）"]
    tops = top_threads_in_window(thread_df, t_lo_ms, t_hi_ms, top_n=top_n)
    if not tops:
        return ["（该时间窗内无线程表采样或无数值列）"]
    return [
        f"- **{e.thread_label}**：窗内均值 {e.mean_pct_in_window:.1f}%，峰值 {e.peak_pct_in_window:.1f}%"
        for e in tops
    ]


def enrich_anomaly_chunk(
    ch: AnomalyDataChunk,
    df: pd.DataFrame,
    thread_df: pd.DataFrame | None,
    *,
    metrics_lo: float | None = None,
    metrics_hi: float | None = None,
    top_threads: int = 8,
) -> None:
    """就地填充墙钟、CPU/GPU/各核/线程摘要；指标窗默认与截取窗一致。"""
    mlo = float(metrics_lo if metrics_lo is not None else ch.time_lo_ms)
    mhi = float(metrics_hi if metrics_hi is not None else ch.time_hi_ms)
    ch.metrics_time_lo_ms = mlo
    ch.metrics_time_hi_ms = mhi
    ch.wall_clock_zh = wall_clock_range_zh(df, mlo, mhi)
    ch.resource_summary_zh = summarize_datav4_window(df, mlo, mhi)
    ch.thread_summary_zh = thread_summary_lines(thread_df, mlo, mhi, top_n=top_threads)
