"""联合分析单测（T043）。"""

from __future__ import annotations

from toolkit.core.joint_assessment import assess_joint, build_observations_snapshot
from toolkit.core.perfdog.report_types import (
    AnalysisReport,
    Finding,
    FindingCategory,
    FindingSeverity,
    Recommendation,
    SessionSummary,
)
from toolkit.sdk.joint_models import FreqPolicyRow, ObservationsSnapshot, PolicySnapshot


def test_assess_joint_consistency_non_empty() -> None:
    policy = PolicySnapshot(
        package_name="com.example.game",
        mode_name="performance",
        freq_rows=[
            FreqPolicyRow(
                temp_level="L1",
                trigger_temp="42",
                gpu_min_hz=400,
                gpu_max_hz=900,
                gpu_index="1_5",
            ),
        ],
        bindcore_summary="tid0=cpu0",
    )
    report = AnalysisReport(
        session=SessionSummary(
            package_name="com.example.game",
            duration_ms=60_000,
            target_fps_hint=60,
        ),
        summary_metrics={
            "GPU 频率均值(MHz)": 650.0,
            "FPS 均值": 58.0,
        },
        findings=[
            Finding(
                id="f_thread",
                category=FindingCategory.thread,
                severity=FindingSeverity.info,
                title="线程负载",
                detail="占位",
            ),
        ],
        recommendations=[
            Recommendation(
                id="rec1",
                finding_ids=["f_thread"],
                text="建议关注渲染线程。后续可复测。",
                category="复现条件",
            ),
        ],
    )
    obs = build_observations_snapshot(report)
    joint = assess_joint(policy, obs)
    assert joint.consistency_section, "consistency_section 应有至少一条启发式结论"


def test_freq_gap_yields_insufficient_no_suggestions() -> None:
    """JA-SC-004：缺频点摘要时不得生成频点启发式建议（T043/T049）。"""
    policy = PolicySnapshot(
        package_name="com.example.game",
        mode_name="performance",
        freq_rows=[
            FreqPolicyRow(
                temp_level="L1",
                trigger_temp="40",
                gpu_min_hz=200,
                gpu_max_hz=800,
                gpu_index="0_4",
            ),
        ],
    )
    report = AnalysisReport(
        session=SessionSummary(package_name="com.example.game"),
        summary_metrics={"FPS 均值": 55.0},
        findings=[],
        recommendations=[],
    )
    obs = build_observations_snapshot(report)
    assert any("JA-SC-004" in g for g in obs.data_gaps)
    joint = assess_joint(policy, obs)
    assert joint.freq_suggestions == []
    assert joint.freq_insufficient_reason
    assert "频点" in joint.freq_insufficient_reason or "JA-SC-004" in joint.freq_insufficient_reason


def test_manual_observations_snapshot_assess() -> None:
    """构造最小 ObservationsSnapshot（不经 build_observations_snapshot）。"""
    policy = PolicySnapshot(package_name="a.b.c", mode_name="m", bindcore_summary="x=y")
    obs = ObservationsSnapshot(
        package_name="a.b.c",
        metric_lines=["GPU 频率均值(MHz): 500"],
        finding_summaries=[],
        data_gaps=[],
    )
    joint = assess_joint(policy, obs)
    assert joint.policy_section and joint.observation_section
