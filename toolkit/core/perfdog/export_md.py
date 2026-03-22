"""AnalysisReport → Markdown 文本（UTF-8，附录 B 结构简化版）。"""

from __future__ import annotations

from toolkit.core.perfdog.report_types import AnalysisReport


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
            lines.append(f.detail)
            lines.append("")

    lines.append("## 建议")
    lines.append("")
    for r in report.recommendations:
        ids = ", ".join(r.finding_ids) if r.finding_ids else "—"
        lines.append(f"- **{r.category}** [{ids}]: {r.text}")
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

    return "\n".join(lines)
