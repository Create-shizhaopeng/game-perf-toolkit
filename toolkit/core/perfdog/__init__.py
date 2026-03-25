"""PerfDog 导出解析与性能洞察（核心库，供 GUI / CLI / 测试调用）。"""

from __future__ import annotations

from toolkit.core.perfdog.compare import build_compare_markdown, compare_reports
from toolkit.core.perfdog.anomaly_rows import build_anomaly_data_chunks, build_non_anomaly_summary_zh
from toolkit.core.perfdog.correlate import correlate_findings_with_freq
from toolkit.core.perfdog.detect import detect_findings, finding_from_frame_stats
from toolkit.core.perfdog.errors import PerfDogParseError, PerfDogUnsupportedError
from toolkit.core.perfdog.export_md import build_markdown
from toolkit.core.perfdog.parse_all import compute_stat_disclaimer, parse_all
from toolkit.core.perfdog.parse_frameinfo import parse_frameinfo
from toolkit.core.perfdog.parse_threads import parse_thread_cpu
from toolkit.core.perfdog.report_types import (
    AnalysisReport,
    AnalyzeOptions,
    Recommendation,
    SessionComparePair,
)
from toolkit.core.perfdog.session import build_session
from toolkit.core.perfdog.threads_top import (
    attach_thread_top_to_findings,
    pick_anomaly_window_ms,
    top_threads_in_window,
)

__all__ = [
    "load_and_analyze",
    "build_markdown",
    "build_compare_markdown",
    "compare_reports",
    "AnalysisReport",
    "AnalyzeOptions",
    "SessionComparePair",
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

    frame_stats, frame_warn = parse_frameinfo(path, opts, target)
    if frame_warn:
        summary_metrics = {**summary_metrics, "FrameInfo 扫描": frame_warn}
    if frame_stats and frame_stats.count:
        ff = finding_from_frame_stats(frame_stats, target)
        if ff:
            findings.append(ff)

    thread_df = parse_thread_cpu(path, opts)
    has_thread_sheet = thread_df is not None
    correlate_findings_with_freq(findings, df, opts.anomaly_window_ms)

    thread_top = None
    if has_thread_sheet and thread_df is not None and not thread_df.empty:
        attach_thread_top_to_findings(findings, thread_df, opts.anomaly_window_ms)
        win = pick_anomaly_window_ms(findings)
        if win is not None:
            ts, te = win
            t0 = ts - opts.anomaly_window_ms
            t1 = te + opts.anomaly_window_ms
            thread_top = top_threads_in_window(thread_df, t0, t1)

    # 本期 spec：不交付单文件「建议清单」；保留 recommendations 字段为空列表（后续里程碑可再接 recommendations 管线）。
    recommendations: list[Recommendation] = []

    warn_crit = sum(
        1 for f in findings if f.severity.value in ("warn", "critical")
    )
    summary_metrics = {
        **summary_metrics,
        "明显异常项数( warn/critical )": warn_crit,
    }

    pad_used = min(5000, max(500, int(opts.anomaly_window_ms)))
    anomaly_chunks = build_anomaly_data_chunks(df, findings, pad_ms=pad_used)
    non_anomaly_zh = build_non_anomaly_summary_zh(session, summary_metrics)

    return AnalysisReport(
        session=session,
        summary_metrics=summary_metrics,
        findings=findings,
        recommendations=recommendations,
        frame_stats=frame_stats if frame_stats and frame_stats.count else None,
        thread_top=thread_top,
        stat_row_disclaimer=disclaimer,
        source_path=path,
        unrecognized_columns=parsed.unrecognized_columns,
        has_thread_cpu_sheet=has_thread_sheet,
        anomaly_data_chunks=anomaly_chunks,
        anomaly_sample_pad_ms=pad_used,
        non_anomaly_summary_zh=non_anomaly_zh,
    )
