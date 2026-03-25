"""AnalysisReport → Markdown 文本（UTF-8，附录 B 结构简化版）。"""

from __future__ import annotations

from toolkit.core.perfdog.config_defaults import REPORT_METHODS_AND_LIMITATIONS_ZH
from toolkit.core.perfdog.report_types import AnalysisReport, AnomalyDataChunk, Finding


def format_finding_anomaly_period(f: Finding) -> str | None:
    """异常对应的时间段说明（与 Data_v4 time_ms 同一坐标系：相对记录起点）。"""
    if f.time_start_ms is None:
        return None
    t0 = f.time_start_ms / 1000.0
    te = f.time_end_ms
    if te is None or abs(te - f.time_start_ms) < 1e-3:
        return (
            f"约 {t0:.2f} s（瞬时；相对记录起点，与导出表 Time(ms) 一致）"
        )
    t1 = te / 1000.0
    lo, hi = (t0, t1) if t0 <= t1 else (t1, t0)
    dur = hi - lo
    return (
        f"{lo:.2f} s ~ {hi:.2f} s（持续 {dur:.2f} s；相对记录起点，与导出表 Time(ms) 一致）"
    )


def format_finding_time_sentence(f: Finding) -> str | None:
    """兼容旧名；同 `format_finding_anomaly_period`。"""
    return format_finding_anomaly_period(f)


def anomaly_chunk_to_tsv(chunk: AnomalyDataChunk) -> str:
    """单条洞察对应的 Data_v4 切片 TSV。"""
    if not chunk.columns:
        return ""
    lines = ["\t".join(chunk.columns)]
    for row in chunk.rows:
        lines.append("\t".join(row))
    return "\n".join(lines)


def build_markdown(report: AnalysisReport) -> str:
    lines: list[str] = []
    s = report.session
    lines.append("# PerfDog 性能洞察报告")
    lines.append("")
    lines.append("## 会话摘要")
    lines.append("")
    lines.append(f"- 包名: {s.package_name or '（未识别）'}")
    lines.append(f"- 设备/机型信息: {s.device_name or '（未识别）'}")
    lines.append(f"- 推断目标帧率: {s.target_fps_hint or '—'}")
    lines.append(f"- 记录时长(ms): {s.duration_ms or '—'}")
    lines.append("")

    lines.append("## 核心指标")
    lines.append("")
    for k, v in report.summary_metrics.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    if report.stat_row_disclaimer:
        lines.append("## 数据脚注")
        lines.append("")
        lines.append(report.stat_row_disclaimer)
        lines.append("")

    lines.append("## 问题与洞察")
    lines.append("")
    if not report.findings:
        lines.append("（无）")
    else:
        for f in report.findings:
            tr = ""
            if f.time_start_ms is not None:
                tr = f"（约 {f.time_start_ms/1000:.2f}s"
                if f.time_end_ms is not None and f.time_end_ms != f.time_start_ms:
                    tr += f" ~ {f.time_end_ms/1000:.2f}s"
                tr += "）"
            lines.append(f"### {f.title} `{f.id}`{tr}")
            lines.append("")
            lines.append(f.severity.value.upper() + " · " + f.category.value)
            lines.append("")
            period = format_finding_anomaly_period(f)
            if period:
                lines.append(f"- **异常时间段**：{period}")
                lines.append("")
            lines.append(f.detail)
            lines.append("")

    fs = report.frame_stats
    if fs is not None and fs.count:
        lines.append("## 帧级（@FrameInfo）")
        lines.append("")
        lines.append(
            f"- 帧数: {fs.count}；均值 {fs.mean_ms:.2f} ms；p99 {fs.p99_ms:.2f} ms；"
            f"最大 {fs.max_ms:.2f} ms；超 2×预算帧数 {fs.over_budget_count}"
        )
        if fs.max_frame_at_ms is not None:
            lines.append(f"- 最大帧相对时间约: {fs.max_frame_at_ms/1000:.2f} s")
        lines.append("")

    if any((f.evidence or {}).get("freq_gpu_window_vs_global") for f in report.findings):
        lines.append("## 频点与 GPU（异常窗 vs 全段）")
        lines.append("")
        for f in report.findings:
            comp = (f.evidence or {}).get("freq_gpu_window_vs_global")
            if not comp:
                continue
            tr = f"`{f.id}`"
            lines.append(f"### {f.title} {tr}")
            for col, gw in comp.items():
                g, wv = gw
                lines.append(f"- {col}: 全段均值≈{g}，异常窗均值≈{wv}")
            lines.append("")

    if report.thread_top:
        lines.append("## 异常窗内线程 Top（@ThreadCpuUsageData）")
        lines.append("")
        for e in report.thread_top:
            lines.append(
                f"- {e.thread_label}: 窗内均值 {e.mean_pct_in_window:.2f}%，"
                f"峰值 {e.peak_pct_in_window:.2f}%",
            )
        lines.append("")

    lines.append("## 异常关联采样（Data_v4）")
    lines.append("")
    if report.anomaly_data_chunks:
        lines.append(
            f"下列为各条洞察在 **time_ms** 落入「异常时间段」两侧各扩展至多 "
            f"**{report.anomaly_sample_pad_ms} ms** 内的秒级采样（列名已别名映射）；"
            "非异常时段不逐行展开。",
        )
        lines.append("")
        for ch in report.anomaly_data_chunks:
            lines.append(f"### `{ch.finding_id}` {ch.finding_title}")
            lines.append("")
            lines.append(
                f"- **截取时间窗（ms，与导出表一致）**: {ch.time_lo_ms:.1f} ~ {ch.time_hi_ms:.1f}",
            )
            lines.append("")
            tsv = anomaly_chunk_to_tsv(ch)
            if not tsv:
                lines.append("（该时间窗内无秒级采样点。）")
            else:
                lines.append("```text")
                lines.append(tsv)
                lines.append("```")
            lines.append("")
    else:
        lines.append(
            "（当前无带「异常时间段」的洞察，或 Data_v4 中无匹配采样行。）",
        )
        lines.append("")

    lines.append("## 其余时段说明")
    lines.append("")
    lines.append(report.non_anomaly_summary_zh.strip() or "（无）")
    lines.append("")

    lines.append("## 导出列说明")
    lines.append("")
    lines.append(
        "已在工具中登记别名的列会参与「核心指标」与洞察规则；"
        "「尚未登记别名的列」仅表示未映射为内部字段名，**数据仍已从 Excel 读入**，"
        "常见未映射项为功耗细分、截图标记等，可后续扩展。",
    )
    lines.append("")

    if report.unrecognized_columns:
        lines.append("## 尚未登记别名的列名")
        lines.append("")
        lines.append(", ".join(report.unrecognized_columns[:80]))
        lines.append("")

    lines.append("## 方法与局限性")
    lines.append("")
    lines.append(REPORT_METHODS_AND_LIMITATIONS_ZH.strip())
    lines.append("")

    return "\n".join(lines)
