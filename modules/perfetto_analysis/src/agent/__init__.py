"""Pydantic AI 多 Agent 分析引擎。

Main/Sub/Review 三角色编排：
- MainAgent: 用户意图分析、场景路由
- SubAgent: 独立 trace 分析（每 trace 一个实例）
- ReviewAgent: 交叉评审、一致性检查
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from typing import Literal

from pydantic import BaseModel, Field


class AnalysisStatus(str, Enum):
    """分析任务状态。"""

    PENDING = "PENDING"
    ROUTING = "ROUTING"
    ANALYZING = "ANALYZING"
    REVIEWING = "REVIEWING"
    REPORTING = "REPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


class AgentRole(str, Enum):
    """Agent 角色。"""

    MAIN = "MAIN"
    SUB = "SUB"
    REVIEW = "REVIEW"


class AnalysisTask(BaseModel):
    """分析任务。"""

    id: str = Field(description="任务唯一标识 (UUID)")
    trace_path: str = Field(description="待分析 trace 文件路径")
    process_name: str = Field(default="", description="目标进程名")
    user_intent: str = Field(default="", description="用户输入的分析意图")
    scene: str = Field(default="", description="AI 路由的分析场景")
    status: AnalysisStatus = Field(default=AnalysisStatus.PENDING)
    agent_role: AgentRole = Field(default=AgentRole.MAIN)
    result_dir: str = Field(default="", description="分析结果文件夹路径")
    error_message: str = Field(default="")
    token_used: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class AnalysisReport(BaseModel):
    """分析报告元数据。"""

    task_id: str
    html_path: str = Field(default="", description="HTML 报告文件路径")
    raw_data_dir: str = Field(default="", description="原始数据子文件夹路径")
    summary: str = Field(default="", description="结论摘要")
    trace_overview: dict = Field(default_factory=dict)
    root_causes: list[dict] = Field(default_factory=list)
    analysis_output: "AnalysisOutput | None" = Field(
        default=None, description="G1 结构化输出（G4 Review 增强使用）"
    )


class OrchestrationConfig(BaseModel):
    """Agent 编排配置（区别于 models.py 中服务层的 AnalysisConfig）。"""

    parallel_count: int = Field(default=1, ge=1, le=10, description="批量分析并行数")
    analysis_timeout_sec: int = Field(default=300, ge=60, description="单次分析超时（秒）")
    auto_open_report: bool = Field(default=True, description="分析完成后自动打开浏览器")
    user_trace_dir: str = Field(default="user_traces", description="用户拖入 trace 的托管目录名")


class AnalysisRouting(BaseModel):
    """MainAgent 的场景路由结果。"""

    scene: str = Field(description="分析场景: jank/anr/memory/startup/cpu/io/input-latency/response-latency/rotation/general")
    sop_name: str = Field(default="", description="SOP 文件名")
    process_name: str = Field(default="", description="检测到的目标进程")
    reasoning: str = Field(default="", description="路由理由")


# --- G0: 推理链重构新增模型 ---


class PrefetchSpec(BaseModel):
    """预取规格：定义编排器 Phase 1 预取的工具和注入方式。"""

    tool: str = Field(description="预取调用的工具名，如 detect_jank")
    inject_as: str = Field(description="注入到 prompt 的变量名，如 jank_frames")
    args: dict = Field(default_factory=dict, description="工具调用额外参数")


class SceneMeta(BaseModel):
    """场景元数据：从 SOP frontmatter 解析，驱动预取和 prompt 组装。"""

    scene: str = Field(description="场景标识")
    display_name: str = Field(default="", description="场景显示名")
    priority_dims: list[str] = Field(default_factory=list, description="必查维度")
    secondary_dims: list[str] = Field(default_factory=list, description="推荐维度")
    optional_dims: list[str] = Field(default_factory=list, description="辅助维度")
    prefetch: list[PrefetchSpec] = Field(default_factory=list, description="预取配置")


class CompressionProfile(BaseModel):
    """工具级压缩策略配置。"""

    strategy: str = Field(description="压缩策略: degraded_aware / jank_records / keep_all / truncate")
    max_tokens: int = Field(default=500, description="截断策略的 token 上限")


# --- G1: 分析经验自动沉淀新增模型 ---


class RootCauseItem(BaseModel):
    """单条根因条目，SubAgent 结构化输出的核心单元。"""

    tag: str = Field(description="根因标签: cpu_throttle, binder_ipc, gc_pause 等")
    severity: str = Field(description="严重级别: CRITICAL / HIGH / WARNING / INFO")
    qualitative: str = Field(description="定性描述")
    quantitative: dict = Field(default_factory=dict, description="定量数据（可选）")
    evidence: str = Field(description="证据来源")
    reasoning: str = Field(description="推理链")
    suggestion: str = Field(default="", description="优化建议（可选）")


class AnalysisOutput(BaseModel):
    """SubAgent 结构化输出模型，驱动经验提取和报告生成。"""

    user_intent_summary: str = Field(description="用户问题归纳")
    trace_info: str = Field(description="trace 基本信息（时长/帧数/设备等）")
    scene: str = Field(description="分析场景")
    overall_conclusion: str = Field(description="整体分析结论")
    root_causes: list[RootCauseItem] = Field(
        default_factory=list, description="根因列表"
    )
    detailed_report: str = Field(
        default="", description="详细分析报告（Markdown + {{chart:key}} 占位符）"
    )


# --- G4: Review 增强新增模型 ---


class ConfidenceAdjustment(BaseModel):
    """置信度校准条目，按 root_cause_tag 精确匹配 pa_learnings 记录。"""

    trace_index: int = Field(description="对应 trace 在批量中的索引（0-based）")
    tag: str = Field(description="根因标签，精确匹配 pa_learnings.root_cause_tags")
    adjustment: float = Field(description="校准值，范围 [-0.3, +0.3]")
    reason: str = Field(default="", description="调整理由")


class ReviewResult(BaseModel):
    """ReviewAgent 结构化评审输出。"""

    cross_consistency: str = Field(
        default="", description="交叉一致性评价（仅 cross_compare 模式）"
    )
    common_patterns: list[str] = Field(
        default_factory=list, description="共性问题列表"
    )
    contradictions: list[str] = Field(
        default_factory=list, description="矛盾点列表"
    )
    confidence_adjustments: list[ConfidenceAdjustment] = Field(
        default_factory=list, description="置信度调整列表"
    )
    overall_assessment: str = Field(description="整体评审意见")
