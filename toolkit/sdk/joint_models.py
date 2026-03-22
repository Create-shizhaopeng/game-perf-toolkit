"""游戏性能策略 × PerfDog 联合分析 — Pydantic 模型（spec US9～11 / data-model.md）"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FreqPolicyRow(BaseModel):
    """gameperfconfig 当前模式下某一温档行的频点策略（数值与索引并存便于对照 XML）。"""

    temp_level: str = ""
    trigger_temp: str = ""
    gold_min_hz: int | None = None
    gold_max_hz: int | None = None
    prime_min_hz: int | None = None
    prime_max_hz: int | None = None
    gpu_min_hz: int | None = None
    gpu_max_hz: int | None = None
    gold_index: str = ""
    prime_index: str = ""
    gpu_index: str = ""


class PolicySnapshot(BaseModel):
    """从 GamePerfParser 当前选中游戏/模式抽取的策略快照。"""

    package_name: str
    mode_name: str
    game_alias: str | None = None
    freq_rows: list[FreqPolicyRow] = Field(default_factory=list)
    bindcore_summary: str | None = None
    strategy_highlights: list[str] = Field(default_factory=list)
    source_xml_path: str | None = None


class FindingRef(BaseModel):
    """观测侧 finding 摘要（用于联合分析追溯）。"""

    id: str
    title_or_text: str
    category: str


class RecRef(BaseModel):
    """观测侧 recommendation 摘要。"""

    id: str
    title_or_text: str
    category: str


class ObservationsSnapshot(BaseModel):
    """由 AnalysisReport 派生的联合分析观测视图。"""

    package_name: str | None = None
    duration_ms: int | None = None
    target_fps_hint: int | None = None
    metric_lines: list[str] = Field(default_factory=list)
    finding_summaries: list[FindingRef] = Field(default_factory=list)
    recommendation_summaries: list[RecRef] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class JointAssessOptions(BaseModel):
    """assess_joint 可选行为（UI 在用户确认后传入）。"""

    skip_package_warning: bool = False


class JointSuggestion(BaseModel):
    """绑核 / 频点类单条建议（启发式，须含 basis）。"""

    id: str
    text: str
    basis: str
    related_finding_ids: list[str] | None = None
    severity_hint: str | None = None


class JointAssessmentReport(BaseModel):
    """联合分析输出：结论段落 + 分类建议 + 数据不足说明 + 警告。"""

    policy_section: list[str] = Field(default_factory=list)
    observation_section: list[str] = Field(default_factory=list)
    consistency_section: list[str] = Field(default_factory=list)
    bindcore_suggestions: list[JointSuggestion] = Field(default_factory=list)
    freq_suggestions: list[JointSuggestion] = Field(default_factory=list)
    bindcore_insufficient_reason: str | None = None
    freq_insufficient_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = ""
