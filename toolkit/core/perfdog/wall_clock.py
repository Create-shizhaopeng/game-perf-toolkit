"""相对 time_ms → 可读墙钟时间（依赖 Data_v4 绝对时间列）。"""

from __future__ import annotations

import math
from datetime import datetime

import pandas as pd


def _epoch_ms_from_raw(v: float) -> float | None:
    """将导出中的时间戳统一为毫秒级 Unix 时间（尽力推断）。"""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    av = abs(v)
    if av >= 1e16:  # 纳秒级
        return v / 1_000_000.0
    if av >= 1e13:  # 微秒
        return v / 1000.0
    if av >= 1e11:  # 已是毫秒 epoch
        return float(v)
    if av >= 1e9:  # 秒级 epoch
        return float(v) * 1000.0
    return None


def pick_absolute_time_column(df: pd.DataFrame) -> tuple[str, pd.Series] | None:
    """返回 (列名, 已转为 epoch_ms 的 Series) 或 None。"""
    for col in ("abs_time_ms", "cap_time_ms"):
        if col not in df.columns:
            continue
        raw = pd.to_numeric(df[col], errors="coerce")
        if raw.notna().sum() == 0:
            continue
        med = float(raw.dropna().median())
        em = _epoch_ms_from_raw(med)
        if em is None or em < 1e11:  # 不像墙钟
            continue
        converted = raw.apply(
            lambda x: _epoch_ms_from_raw(float(x)) if pd.notna(x) else float("nan"),
        )
        converted = pd.to_numeric(converted, errors="coerce")
        if converted.notna().sum() == 0:
            continue
        return col, converted
    return None


def format_epoch_ms_local(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000.0).strftime("%Y-%m-%d %H:%M:%S")


def wall_clock_range_zh(
    df: pd.DataFrame,
    t_lo_ms: float,
    t_hi_ms: float,
) -> str | None:
    """在给定相对 time_ms 窗内，用绝对时间列换算墙钟区间说明；无时返回 None。"""
    picked = pick_absolute_time_column(df)
    if picked is None:
        return None
    col_name, abs_series = picked
    t_rel = pd.to_numeric(df["time_ms"], errors="coerce")
    mask = (t_rel >= t_lo_ms) & (t_rel <= t_hi_ms) & t_rel.notna() & abs_series.notna()
    if not mask.any():
        return None
    amin = float(abs_series.loc[mask].min())
    amax = float(abs_series.loc[mask].max())
    lab = "AbsTime" if col_name == "abs_time_ms" else "CapTime"
    return (
        f"{format_epoch_ms_local(amin)} ~ {format_epoch_ms_local(amax)} "
        f"（由 Data_v4 **{lab}** 列推算，本地时区）"
    )


def datav4_window_near_frame_center(
    df: pd.DataFrame,
    frame_center_ms: float,
    pad_ms: float,
) -> tuple[float, float]:
    """在 Data_v4 轴上取与 FrameInfo 最大帧时刻最近的一点，并 ±pad，便于对齐 CPU/GPU/线程。"""
    lo = frame_center_ms - pad_ms
    hi = frame_center_ms + pad_ms
    if df.empty or "time_ms" not in df.columns:
        return lo, hi
    t = pd.to_numeric(df["time_ms"], errors="coerce").dropna()
    if t.empty:
        return lo, hi
    idx = (t - frame_center_ms).abs().idxmin()
    c = float(pd.to_numeric(df.loc[idx, "time_ms"], errors="coerce"))
    if c != c:
        return lo, hi
    return c - pad_ms, c + pad_ms
