"""从 AnalysisReport 构建 ObservationsSnapshot（JA-SC-004：无频点列不伪造数值）。"""

from __future__ import annotations

import re

from toolkit.core.perfdog.report_types import AnalysisReport
from toolkit.sdk.joint_models import FindingRef, ObservationsSnapshot, RecRef

# 与 session.summary_metrics 中文键一致；仅依赖键名子串，不 import column_aliases（包边界）
_FREQ_METRIC_KEY_MARKERS = ("频率", "MHz", "mhz")

_TEXT_MAX = 220
_REC_FIRST_MAX = 160


def _summary_key_has_freq_semantics(key: str) -> bool:
    k = str(key)
    return any(m in k for m in _FREQ_METRIC_KEY_MARKERS)


def _report_has_freq_metrics(summary_metrics: dict) -> bool:
    return any(_summary_key_has_freq_semantics(k) for k in summary_metrics)


def _truncate(s: str, max_len: int) -> str:
    t = s.strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _first_sentence(text: str) -> str:
    t = text.strip()
    if not t:
        return ""
    for sep in ("。", "！", "!", "？", "?", "\n"):
        if sep in t:
            return _truncate(t.split(sep, 1)[0] + sep.replace("\n", ""), _REC_FIRST_MAX)
    return _truncate(t, _REC_FIRST_MAX)


def build_observations_snapshot(report: AnalysisReport) -> ObservationsSnapshot:
    """填充 metric_lines、finding/recommendation 摘要与 data_gaps。"""
    s = report.session
    gaps: list[str] = []

    pkg = (s.package_name or "").strip()
    if not pkg:
        gaps.append("PerfDog 会话摘要中未识别到包名。")

    if not _report_has_freq_metrics(report.summary_metrics):
        gaps.append(
            "JA-SC-004：摘要指标中未检测到 CPU/GPU 频点类数据，"
            "无法与策略表的 Gold/Prime/GPU 频点上下限做数值对照。"
        )

    metric_lines: list[str] = []
    for key, val in report.summary_metrics.items():
        if val is None:
            continue
        metric_lines.append(f"{key}: {val}")

    finding_summaries: list[FindingRef] = []
    for f in report.findings:
        finding_summaries.append(
            FindingRef(
                id=f.id,
                title_or_text=_truncate(f.title, _TEXT_MAX),
                category=f.category.value,
            ),
        )

    recommendation_summaries: list[RecRef] = []
    for r in report.recommendations:
        recommendation_summaries.append(
            RecRef(
                id=r.id,
                title_or_text=_first_sentence(r.text),
                category=r.category,
            ),
        )

    return ObservationsSnapshot(
        package_name=s.package_name,
        duration_ms=s.duration_ms,
        target_fps_hint=s.target_fps_hint,
        metric_lines=metric_lines,
        finding_summaries=finding_summaries,
        recommendation_summaries=recommendation_summaries,
        data_gaps=gaps,
    )


def parse_numeric_metrics_from_lines(metric_lines: list[str]) -> dict[str, float]:
    """从 metric_lines 解析「键: 值」中的数值，供 engine 启发式使用（非伪造原始采样）。"""
    out: dict[str, float] = {}
    for line in metric_lines:
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        m = re.match(r"^-?[\d.]+", rest)
        if not m:
            continue
        try:
            out[key] = float(m.group(0))
        except ValueError:
            continue
    return out
