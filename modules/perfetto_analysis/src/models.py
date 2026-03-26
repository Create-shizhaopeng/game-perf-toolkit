# -*- coding: utf-8 -*-
"""Perfetto 解析分析模块 — 数据模型定义。

公共 API 使用 Pydantic 模型，模块内部使用 dataclass。
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


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


# ---------------------------------------------------------------------------
# 配置加载/保存
# ---------------------------------------------------------------------------

def _module_dir() -> Path:
    """返回模块根目录 (modules/perfetto_analysis/)。"""
    return Path(__file__).resolve().parent.parent


def _assets_config_path() -> Path:
    return _module_dir() / "assets" / "config.json"


def _data_config_path() -> Path:
    return _module_dir() / "data" / "config.json"


def load_config(config_path: Path | None = None) -> AnalysisConfig:
    """加载配置文件，缺失时使用默认值。

    优先级：config_path 参数 > data/config.json > assets/config.json > 默认值
    """
    if config_path and config_path.is_file():
        target = config_path
    else:
        target = _data_config_path()
        if not target.is_file():
            assets = _assets_config_path()
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
    target = config_path or _data_config_path()
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
