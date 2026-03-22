"""双会话 A/B 对比（FR-011 / FR-012）。"""

from __future__ import annotations

from typing import Any

from toolkit.core.perfdog.report_types import AnalysisReport, SessionComparePair


def _norm_pkg(name: str | None) -> str:
    return (name or "").strip().lower()


def _frame_metrics(report: AnalysisReport) -> dict[str, Any]:
    fs = report.frame_stats
    if fs is None or not fs.count:
        return {}
    return {
        "count": fs.count,
        "mean_ms": fs.mean_ms,
        "p99_ms": fs.p99_ms,
        "max_ms": fs.max_ms,
        "over_budget_count": fs.over_budget_count,
    }


def compare_reports(a: AnalysisReport, b: AnalysisReport) -> SessionComparePair:
    warnings: list[str] = []
    pa, pb = a.session.package_name, b.session.package_name
    if pa and pb and _norm_pkg(pa) != _norm_pkg(pb):
        warnings.append(
            f"应用/包名不一致：会话 A={pa} vs 会话 B={pb}（FR-012：展示前须用户确认）。",
        )
    elif (pa and not pb) or (pb and not pa):
        warnings.append("一侧缺少包名，并列对比仅作参考。")

    delta: dict[str, tuple[Any, Any]] = {}
    for k in sorted(set(a.summary_metrics.keys()) & set(b.summary_metrics.keys())):
        delta[k] = (a.summary_metrics[k], b.summary_metrics[k])

    fa, fb = _frame_metrics(a), _frame_metrics(b)
    for ek in sorted(set(fa) | set(fb)):
        key = f"帧级.{ek}"
        delta[key] = (fa.get(ek), fb.get(ek))

    aligned_cols = sorted(delta.keys())
    return SessionComparePair(
        session_a=a.session,
        session_b=b.session,
        delta_metrics=delta,
        aligned_columns=aligned_cols,
        warnings=warnings,
    )


def build_compare_markdown(pair: SessionComparePair, *, label_a: str = "会话 A", label_b: str = "会话 B") -> str:
    lines: list[str] = []
    lines.append("## 双会话对比（A/B）")
    lines.append("")
    sa, sb = pair.session_a, pair.session_b
    lines.append(f"- {label_a} 包名: {sa.package_name or '—'} | 设备: {sa.device_name or '—'}")
    lines.append(f"- {label_b} 包名: {sb.package_name or '—'} | 设备: {sb.device_name or '—'}")
    lines.append("")
    if pair.warnings:
        lines.append("### 警告")
        for w in pair.warnings:
            lines.append(f"- {w}")
        lines.append("")
    lines.append("### 指标对照")
    lines.append("")
    for k in pair.aligned_columns:
        va, vb = pair.delta_metrics[k]
        lines.append(f"- **{k}**: A={va} | B={vb}")
    lines.append("")
    return "\n".join(lines)
