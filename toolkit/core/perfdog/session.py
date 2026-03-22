"""从解析结果构建 SessionSummary 与 summary_metrics。"""

from __future__ import annotations

import re

import pandas as pd

from toolkit.core.perfdog.parse_all import ParsedAll
from toolkit.core.perfdog.report_types import SessionSummary


def _infer_target_fps(fps_series: pd.Series, stat_hint: float | None) -> int:
    caps = (144, 120, 90, 60)
    if stat_hint and 30 <= stat_hint <= 165:
        for c in caps:
            if abs(stat_hint - c) <= 8:
                return c
        return int(round(stat_hint))

    p95 = float(fps_series.quantile(0.95))
    for c in caps:
        if p95 >= c * 0.92:
            return c
    if p95 >= 50:
        return 60
    return 60


def _normalize_time_ms(df: pd.DataFrame) -> pd.DataFrame:
    """推断 time 列单位并统一为毫秒（副本）。"""
    out = df.copy()
    t = pd.to_numeric(out["time_ms"], errors="coerce")
    if t.dropna().empty:
        return out
    diffs = t.diff().abs().median()
    mx = float(t.max())
    # 若整体量级像「秒」且步长较小
    if mx <= 7200 and diffs is not None and diffs < 5 and mx < 600:
        out["time_ms"] = t * 1000.0
    else:
        out["time_ms"] = t
    return out


def _parse_package_from_preamble(lines: list[str]) -> str | None:
    for line in lines:
        if "package" in line.lower() or "包名" in line or "应用" in line:
            m = re.search(
                r"([\w.]{4,200}\.[a-zA-Z][\w.]*)",
                line,
            )
            if m:
                return m.group(1)
    return None


def _parse_device_from_preamble(lines: list[str]) -> str | None:
    for line in lines:
        low = line.lower()
        if "model" in low or "设备" in line or "机型" in line or "device" in low:
            return line[:200]
    if lines:
        return lines[0][:200]
    return None


def build_session(parsed: ParsedAll) -> tuple[SessionSummary, dict, pd.DataFrame]:
    """返回 (会话摘要, 摘要键值, 时间已规范为 ms 的 DataFrame)。"""
    df = _normalize_time_ms(parsed.dataframe)
    fps = pd.to_numeric(df["fps"], errors="coerce").dropna()

    target = _infer_target_fps(fps, parsed.stat_fps)
    tcol = pd.to_numeric(df["time_ms"], errors="coerce").dropna()
    duration_ms: int | None = None
    if not tcol.empty:
        duration_ms = int(max(0.0, float(tcol.max() - tcol.min())))

    session = SessionSummary(
        package_name=_parse_package_from_preamble(parsed.preamble_lines),
        device_name=_parse_device_from_preamble(parsed.preamble_lines),
        perfdog_version=None,
        record_started_at=parsed.preamble_lines[0] if parsed.preamble_lines else None,
        duration_ms=duration_ms,
        target_fps_hint=target,
    )

    smooth = pd.to_numeric(df["smooth"], errors="coerce") if "smooth" in df.columns else None
    jank = pd.to_numeric(df["jank"], errors="coerce") if "jank" in df.columns else None

    summary_metrics: dict = {
        "采样点数": int(len(df)),
        "FPS 均值": round(float(fps.mean()), 2) if not fps.empty else None,
        "FPS P95": round(float(fps.quantile(0.95)), 2) if not fps.empty else None,
        "FPS 最小": round(float(fps.min()), 2) if not fps.empty else None,
        "推断目标帧率": target,
        "时长(ms)": duration_ms,
    }
    if smooth is not None and not smooth.dropna().empty:
        summary_metrics["Smooth 均值"] = round(float(smooth.mean()), 3)
    if jank is not None and not jank.dropna().empty:
        summary_metrics["Jank 合计"] = int(jank.fillna(0).sum())

    def _mean(col: str, label: str, nd: int = 2) -> None:
        if col not in df.columns:
            return
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            return
        summary_metrics[label] = round(float(s.mean()), nd)

    def _min_mean(col: str, label: str, nd: int = 0) -> None:
        if col not in df.columns:
            return
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            return
        summary_metrics[label] = round(float(s.min()), nd)

    _mean("app_cpu_pct", "应用 CPU 均值(%)")
    _mean("total_cpu_pct", "整机 CPU 均值(%)")
    _mean("gpu_usage_pct", "GPU 占用均值(%)")
    _mean("gpu_clock_mhz", "GPU 频率均值(MHz)", 0)
    _min_mean("gpu_clock_mhz", "GPU 频率最小(MHz)")
    _mean("battery_temp", "电池温度均值(℃)", 1)
    if "battery_temp" in df.columns:
        bt = pd.to_numeric(df["battery_temp"], errors="coerce").dropna()
        if not bt.empty:
            summary_metrics["电池温度最大(℃)"] = round(float(bt.max()), 1)
    _mean("brightness", "屏幕亮度均值", 1)
    _mean("battery_level_pct", "电量均值(%)", 1)

    # 各 CPU 核频率均值（便于一眼看是否某核长期低频）
    clock_means: list[float] = []
    for i in range(8):
        c = f"cpu_clock_{i}_mhz"
        if c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce").dropna()
            if not s.empty:
                clock_means.append(float(s.mean()))
    if clock_means:
        summary_metrics["CPU 各核频率均值最小(MHz)"] = int(min(clock_means))
        summary_metrics["CPU 各核频率均值最大(MHz)"] = int(max(clock_means))

    return session, summary_metrics, df
