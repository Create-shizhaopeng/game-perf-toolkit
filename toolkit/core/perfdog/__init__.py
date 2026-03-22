"""PerfDog 导出解析与性能洞察（核心库，供 GUI / CLI / 测试调用）。"""

from __future__ import annotations

from toolkit.core.perfdog.errors import PerfDogParseError, PerfDogUnsupportedError
from toolkit.core.perfdog.export_md import build_markdown
from toolkit.core.perfdog.parse_all import compute_stat_disclaimer, parse_all
from toolkit.core.perfdog.report_types import AnalysisReport, AnalyzeOptions
from toolkit.core.perfdog.session import build_session
from toolkit.core.perfdog.detect import detect_findings
from toolkit.core.perfdog.recommendations import build_recommendations

__all__ = [
    "load_and_analyze",
    "build_markdown",
    "AnalysisReport",
    "AnalyzeOptions",
    "PerfDogParseError",
    "PerfDogUnsupportedError",
]


def load_and_analyze(path: str, *, options: AnalyzeOptions | None = None) -> AnalysisReport:
    """同步解析 PerfDog Excel 并生成结构化报告（应在工作线程中调用）。"""
    opts = options or AnalyzeOptions()
    parsed = parse_all(path, opts)
    session, summary_metrics, df = build_session(parsed)
    disclaimer = compute_stat_disclaimer(df, parsed.stat_fps)
    target = session.target_fps_hint or 60
    findings = detect_findings(df, target)
    recommendations = build_recommendations(findings)

    warn_crit = sum(
        1 for f in findings if f.severity.value in ("warn", "critical")
    )
    summary_metrics = {
        **summary_metrics,
        "明显异常项数( warn/critical )": warn_crit,
    }

    return AnalysisReport(
        session=session,
        summary_metrics=summary_metrics,
        findings=findings,
        recommendations=recommendations,
        frame_stats=None,
        thread_top=None,
        stat_row_disclaimer=disclaimer,
        source_path=path,
        unrecognized_columns=parsed.unrecognized_columns,
    )
