"""JointAssessmentReport → Markdown（UTF-8），列表风格对齐 perfdog export_md。"""

from __future__ import annotations

from toolkit.core.perfdog.report_types import AnalysisReport
from toolkit.sdk.joint_models import JointAssessmentReport


def build_joint_markdown(
    joint: JointAssessmentReport,
    *,
    base_report: AnalysisReport | None = None,
) -> str:
    """生成「游戏性能策略联合分析」Markdown 章节。

    与 PerfDog 主报告拼接时推荐：``build_markdown(report) + "\\n\\n" + build_joint_markdown(joint)``，
    且 **base_report=None**，避免与会话摘要重复（JA-FR-007 / T051）。
    若未来要在单文件内嵌完整 PerfDog 正文，可传入 base_report 由调用方扩展（当前未展开）。
    """
    _ = base_report  # 预留：完整二合一导出时可复用
    lines: list[str] = []
    lines.append("## 游戏性能策略联合分析")
    lines.append("")

    lines.append("### 策略侧要点")
    lines.append("")
    for bullet in joint.policy_section:
        lines.append(f"- {bullet}")
    lines.append("")

    lines.append("### 观测侧要点")
    lines.append("")
    for bullet in joint.observation_section:
        lines.append(f"- {bullet}")
    lines.append("")

    lines.append("### 一致性 / 矛盾与启发式解读")
    lines.append("")
    for bullet in joint.consistency_section:
        lines.append(f"- {bullet}")
    lines.append("")

    if joint.warnings:
        lines.append("### 警告与校验")
        lines.append("")
        for w in joint.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("### 策略调整建议（绑核）")
    lines.append("")
    if joint.bindcore_suggestions:
        for s in joint.bindcore_suggestions:
            rel = f"；关联 finding：{', '.join(s.related_finding_ids or [])}" if s.related_finding_ids else ""
            lines.append(f"- **{s.id}** {s.text}（依据：{s.basis}{rel}）")
    elif joint.bindcore_insufficient_reason:
        lines.append(f"- （数据不足）{joint.bindcore_insufficient_reason}")
    else:
        lines.append("- （无）")
    lines.append("")

    lines.append("### 策略调整建议（频点）")
    lines.append("")
    if joint.freq_suggestions:
        for s in joint.freq_suggestions:
            rel = f"；关联 finding：{', '.join(s.related_finding_ids or [])}" if s.related_finding_ids else ""
            lines.append(f"- **{s.id}** {s.text}（依据：{s.basis}{rel}）")
    elif joint.freq_insufficient_reason:
        lines.append(f"- （数据不足）{joint.freq_insufficient_reason}")
    else:
        lines.append("- （无）")
    lines.append("")

    lines.append("### 免责声明")
    lines.append("")
    lines.append(joint.disclaimer)
    lines.append("")

    return "\n".join(lines)
