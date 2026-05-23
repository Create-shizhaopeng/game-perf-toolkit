# -*- coding: utf-8 -*-
"""Perfetto 解析分析模块 — 数据模型定义。"""
from __future__ import annotations

import json
import shutil
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class AnalysisMode(str, Enum):
    """分析模式：MCP 优先 / 纯引擎 / 纯 MCP。"""

    MCP_PREFERRED = "mcp_preferred"
    ENGINE_ONLY = "engine_only"
    MCP_ONLY = "mcp_only"


class AnalysisConfig(BaseModel):
    """Perfetto 解析分析配置。"""

    output_dir: str = Field(
        default="output/trace_report",
        description="报告输出基础目录",
    )
    db_path: str = Field(
        default="perfetto_analysis.db",
        description="模块独立 SQLite 数据库文件名",
    )
    refresh_rate_preset: int = Field(
        default=60,
        description="刷新率预设（Hz）",
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
        description="默认目标进程名",
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
        description="维度级模式覆盖",
    )
    mcp_timeout_ms: int = Field(
        default=10000,
        description="MCP 工具调用超时（毫秒）",
    )


def load_config(config_path: Path | None = None) -> AnalysisConfig:
    """加载配置文件，缺失时使用默认值。"""
    from toolkit.core.app_paths import get_config_path

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
