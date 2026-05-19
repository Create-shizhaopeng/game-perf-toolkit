# -*- coding: utf-8 -*-
"""Perfetto 解析分析模块 — 数据模型定义。

公共 API 使用 Pydantic 模型，模块内部使用 dataclass。
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 分析模式枚举
# ---------------------------------------------------------------------------

class AnalysisMode(str, Enum):
    """分析模式：MCP 优先 / 纯引擎 / 纯 MCP。"""

    MCP_PREFERRED = "mcp_preferred"
    ENGINE_ONLY = "engine_only"
    MCP_ONLY = "mcp_only"


# ---------------------------------------------------------------------------
# Pydantic 配置模型（公共 API / 三端共享）
# ---------------------------------------------------------------------------

class AnalysisConfig(BaseModel):
    """Perfetto 解析分析配置。"""

    output_dir: str = Field(
        default="output/trace_report",
        description="报告输出基础目录（运行时由 service 自动解析实际路径）",
    )
    db_path: str = Field(
        default="perfetto_analysis.db",
        description="模块独立 SQLite 数据库文件名（相对于 data/）",
    )
    refresh_rate_preset: int = Field(
        default=60,
        description="刷新率预设（Hz），用于 stand_vsync_ms = 1000/Hz",
    )
    app_type: str = Field(
        default="auto",
        description="App 类型: auto / app / game / camera",
    )
    analyze_top: int = Field(
        default=20,
        description="逐帧分析的 Top N 条 jank_record",
    )
    slow_binder_threshold_ms: float = Field(
        default=2.0,
        description="慢 Binder 阈值（ms）",
    )
    sched_latency_threshold_ms: float = Field(
        default=1.0,
        description="异常调度延迟阈值（ms）",
    )
    auto_analyze_on_capture: bool = Field(
        default=False,
        description="perfetto_capture 抓取完成后是否自动触发分析",
    )
    default_process: str = Field(
        default="",
        description="默认目标进程名（如包名 com.tencent.letsgo）",
    )
    dimensions: list[str] = Field(
        default_factory=list,
        description="默认分析维度（空列表=全部维度）",
    )
    analysis_mode: str = Field(
        default=AnalysisMode.MCP_PREFERRED.value,
        description="分析模式: mcp_preferred / engine_only / mcp_only",
    )
    dimension_overrides: dict[str, str] = Field(
        default_factory=dict,
        description="维度级模式覆盖，如 {\"cpu\": \"engine_only\"}",
    )
    mcp_timeout_ms: int = Field(
        default=10000,
        description="MCP 工具调用超时（毫秒）",
    )


# ---------------------------------------------------------------------------
# 配置加载/保存
# ---------------------------------------------------------------------------

def load_config(config_path: Path | None = None) -> AnalysisConfig:
    """加载配置文件，缺失时使用默认值。

    优先级：config_path 参数 > user config > assets 模板 > 默认值
    """
    from toolkit.core.app_paths import get_config_path, ensure_config_dir, is_frozen

    if config_path and config_path.is_file():
        target = config_path
    else:
        target = get_config_path("perfetto_analysis", "config.json")
        if not target.is_file():
            assets = Path(__file__).resolve().parent.parent / "assets" / "config.json"
            if assets.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(assets, target)
            else:
                return AnalysisConfig()

    if not target.is_file():
        return AnalysisConfig()

    with open(target, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return AnalysisConfig(**raw)


def save_config(cfg: AnalysisConfig, config_path: Path | None = None) -> Path:
    """保存配置到文件，返回保存路径。"""
    from toolkit.core.app_paths import get_config_path

    target = config_path or get_config_path("perfetto_analysis", "config.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(cfg.model_dump(), f, ensure_ascii=False, indent=2)
    return target


# ---------------------------------------------------------------------------
# 内部数据模型（dataclass）
# ---------------------------------------------------------------------------

@dataclass
class AnalysisTask:
    """分析任务描述。"""

    task_id: str
    trace_path: str
    process_name: str = ""
    mode: str = "full"  # full / parse / dimensions
    dimensions: list[str] = field(default_factory=list)
    status: str = "pending"  # pending / running / completed / failed
    error_message: str = ""
    report_dir: str = ""
    analysis_db_path: str = ""


@dataclass
class AnalysisResult:
    """分析完成后的结果摘要。"""

    trace_path: str = ""
    detected_process: str = ""
    jank_times: int = 0
    frame_num: int = 0
    refresh_rate_hz: float = 60.0
    app_type: str = "app"
    elapsed_seconds: float = 0.0
    report_path: str = ""
    report_dir: str = ""
    dimensions_completed: list[str] = field(default_factory=list)
    dimensions_skipped: list[str] = field(default_factory=list)
    parse_result: dict[str, Any] = field(default_factory=dict)
    analysis_data: dict[str, Any] = field(default_factory=dict)

    def to_summary_dict(self) -> dict[str, Any]:
        """返回 Agent 可消费的结构化摘要。"""
        jank_ratio = (
            round(self.jank_times / self.frame_num * 100, 3)
            if self.frame_num > 0
            else 0.0
        )
        per_dim: dict[str, str] = {}
        for dim in self.dimensions_completed:
            dim_data = self.analysis_data.get(dim, {})
            if isinstance(dim_data, dict):
                issues = dim_data.get("issues", [])
                if issues:
                    per_dim[dim] = str(issues[0]) if len(issues) == 1 else f"{len(issues)} 个问题"
                else:
                    per_dim[dim] = "无异常"
            else:
                per_dim[dim] = "已分析"
        return {
            "trace_path": self.trace_path,
            "detected_process": self.detected_process,
            "frame_count": self.frame_num,
            "jank_count": self.jank_times,
            "jank_ratio_percent": jank_ratio,
            "refresh_rate_hz": self.refresh_rate_hz,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "dimensions_completed": self.dimensions_completed,
            "dimensions_skipped": self.dimensions_skipped,
            "per_dimension_issues": per_dim,
            "report_path": self.report_path,
            "report_dir": self.report_dir,
        }


# ---------------------------------------------------------------------------
# 混合分析工具集模型
# ---------------------------------------------------------------------------

@dataclass
class TraceOverview:
    """Trace 元数据概览。"""

    file: str = ""
    duration_s: float = 0.0
    processes: list[str] = field(default_factory=list)
    frame_count: int = 0
    refresh_rate_hz: float = 60.0
    scenario_phases: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DimensionResult:
    """单个维度的分析结果，含数据来源标注。"""

    dimension: str = ""
    source: str = ""  # mcp / engine / degraded / unavailable
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_ms: float = 0.0


@dataclass
class AnalysisScenario:
    """分析场景定义。"""

    name: str = ""
    description: str = ""
    mcp_tools: list[str] = field(default_factory=list)
    engine_dimensions: list[str] = field(default_factory=list)
    required_trace_data: list[str] = field(default_factory=list)


class RootCause(BaseModel):
    """压缩摘要中的单条根因。"""

    rank: int
    cause: str
    evidence: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    dimension: str


class DimensionHealth(BaseModel):
    """单维度健康度评级。"""

    status: Literal["OK", "WARNING", "CRITICAL", "UNAVAILABLE"]
    note: str = ""


class DataCompleteness(BaseModel):
    """数据完整度统计。"""

    degraded_dimensions: list[str] = Field(default_factory=list)
    mcp_source: list[str] = Field(default_factory=list)
    engine_source: list[str] = Field(default_factory=list)


class TraceInfo(BaseModel):
    """压缩摘要中的 trace 基础信息。"""

    file: str = ""
    process: str = ""
    duration_s: float = 0.0
    refresh_rate_hz: float = 60.0
    frame_count: int = 0
    jank_count: int = 0
    avg_fps: float = 0.0


class CompressedSummary(BaseModel):
    """分析结果压缩摘要，供 agent_chat 使用。"""

    trace_info: TraceInfo = Field(default_factory=TraceInfo)
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = "LOW"
    root_causes: list[RootCause] = Field(default_factory=list)
    health_summary: dict[str, DimensionHealth] = Field(default_factory=dict)
    data_completeness: DataCompleteness = Field(default_factory=DataCompleteness)


# ---------------------------------------------------------------------------
# Agent 辅助数据准备工具模型
# ---------------------------------------------------------------------------


class ThreadStateEntry(BaseModel):
    """单个线程状态条目。"""

    state: str
    duration_ms: float = 0.0
    percentage: float = 0.0
    count: int = 0


class ThreadStateSummary(BaseModel):
    """主线程状态分布。"""

    process: str = ""
    total_duration_ms: float = 0.0
    states: list[ThreadStateEntry] = Field(default_factory=list)
    dominant_state: str = ""
    time_range: dict[str, float] | None = None

    def to_compact_dict(self) -> dict[str, Any]:
        """compact 模式：仅返回关键指标。"""
        return {
            "process": self.process,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "dominant_state": self.dominant_state,
            "states": {
                s.state: f"{s.percentage:.1f}%"
                for s in self.states
            },
            "row_count": len(self.states),
        }


class CpuCoreEntry(BaseModel):
    """单个 CPU 核心的频率统计。"""

    cpu_id: int
    running_ms: float = 0.0
    running_percentage: float = 0.0
    freq_min_khz: int = 0
    freq_max_khz: int = 0
    freq_avg_khz: int = 0
    segment_count: int = 0


class CpuFreqAnalysis(BaseModel):
    """CPU 核心分布与频率统计。"""

    process: str = ""
    total_running_ms: float = 0.0
    cores: list[CpuCoreEntry] = Field(default_factory=list)
    primary_core: int = -1
    time_range: dict[str, float] | None = None

    def to_compact_dict(self) -> dict[str, Any]:
        """compact 模式：仅返回关键指标。"""
        return {
            "process": self.process,
            "total_running_ms": round(self.total_running_ms, 2),
            "primary_core": self.primary_core,
            "core_count": len(self.cores),
            "cores": {
                c.cpu_id: f"{c.running_percentage:.1f}% @ {c.freq_avg_khz}kHz"
                for c in self.cores[:5]
            },
            "sample_count": min(5, len(self.cores)),
        }


# ---------------------------------------------------------------------------
# 分析链路追溯模型
# ---------------------------------------------------------------------------

@dataclass
class AnalysisChainStep:
    """分析链路中的单个步骤。"""

    tool_name: str = ""
    input_params: dict[str, Any] = field(default_factory=dict)
    output_summary: str = ""
    duration_ms: float = 0.0
    source: str = ""  # mcp / engine / degraded / unavailable


@dataclass
class AnalysisChainResult:
    """完整的分析链路结果。"""

    steps: list[AnalysisChainStep] = field(default_factory=list)
    conclusion: str = ""
    confidence: float = 1.0  # 0.0-1.0，数据完整度对结论可靠性的影响
