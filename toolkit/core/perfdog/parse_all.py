"""解析 all 表：DeviceInfo 文本区、Stat、Data_v4 → DataFrame。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from toolkit.core.perfdog.column_aliases import rename_dataframe_columns
from toolkit.core.perfdog.config_defaults import STAT_FPS_DIFF_RATIO
from toolkit.core.perfdog.errors import PerfDogParseError
from toolkit.core.perfdog.report_types import AnalyzeOptions
from toolkit.core.perfdog.workbook import probe_workbook, safe_load_workbook


@dataclass
class ParsedAll:
    """parse_all 输出。"""

    dataframe: pd.DataFrame
    preamble_lines: list[str] = field(default_factory=list)
    stat_fps: float | None = None
    unrecognized_columns: list[str] = field(default_factory=list)


def _check_interrupt(options: AnalyzeOptions) -> None:
    if options.interrupt_check and options.interrupt_check():
        raise PerfDogParseError("解析已取消")


def _read_preamble_rows(path: str, sheet_name: str, end_row_exclusive: int) -> list[str]:
    lines: list[str] = []
    wb = safe_load_workbook(path)
    try:
        sheet = wb[sheet_name]
        for i, row in enumerate(sheet.iter_rows(max_row=max(0, end_row_exclusive), values_only=True)):
            if i >= end_row_exclusive:
                break
            parts = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if parts:
                lines.append(" | ".join(parts[:12]))
    finally:
        wb.close()
    return lines


def _guess_stat_fps(preamble_lines: list[str]) -> float | None:
    """从汇总区文本中猜测 Stat / 平均 FPS。"""
    for line in preamble_lines:
        low = line.lower()
        if "fps" not in low and "帧率" not in line:
            continue
        m = re.search(r"(\d+\.?\d*)\s*(?:fps|帧率|帧/s)", low, re.I)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
        nums = re.findall(r"\b(\d{2,3}(?:\.\d+)?)\b", line)
        for n in nums:
            v = float(n)
            if 30 <= v <= 144:
                return v
    return None


def parse_all(path: str, options: AnalyzeOptions) -> ParsedAll:
    _check_interrupt(options)
    sheet_name, header_row_idx, raw_headers = probe_workbook(path)

    _check_interrupt(options)
    preamble_lines = _read_preamble_rows(path, sheet_name, header_row_idx)
    stat_fps = _guess_stat_fps(preamble_lines)

    _check_interrupt(options)
    try:
        df = pd.read_excel(
            path,
            sheet_name=sheet_name,
            header=0,
            skiprows=header_row_idx,
            engine="openpyxl",
            nrows=options.max_frame_rows,
        )
    except Exception as e:
        raise PerfDogParseError(f"读取数据表失败: {e}") from e

    if df.empty:
        raise PerfDogParseError("Data_v4 数据区为空")

    rename_map = rename_dataframe_columns([str(c) for c in df.columns])
    unrecognized = [str(c) for c in df.columns if str(c) not in rename_map]

    df = df.rename(columns=rename_map)
    # 同内部名列重复时保留第一个
    df = df.loc[:, ~df.columns.duplicated()]

    if "time_ms" not in df.columns or "fps" not in df.columns:
        raise PerfDogParseError("Data_v4 缺少必要列（至少需要时间与 FPS / 帧率）")

    return ParsedAll(
        dataframe=df,
        preamble_lines=preamble_lines,
        stat_fps=stat_fps,
        unrecognized_columns=unrecognized,
    )


def compute_stat_disclaimer(df: pd.DataFrame, stat_fps: float | None) -> str | None:
    """若 Stat 行 FPS 与 Data_v4 重算差异过大，返回脚注文案。"""
    if stat_fps is None or stat_fps <= 0:
        return None
    series = pd.to_numeric(df["fps"], errors="coerce").dropna()
    if series.empty:
        return None
    recalc = float(series.mean())
    if recalc <= 0:
        return None
    diff = abs(recalc - stat_fps) / stat_fps
    if diff > STAT_FPS_DIFF_RATIO:
        return (
            f"PerfDog 汇总区 FPS 约为 {stat_fps:.2f}，"
            f"由 Data_v4 重算均值为 {recalc:.2f}（相对差异 {diff*100:.1f}%）。"
            "本报告以序列重算为主结论。"
        )
    return None
