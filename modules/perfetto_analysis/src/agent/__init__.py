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


