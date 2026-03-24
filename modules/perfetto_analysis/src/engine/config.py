# -*- coding: utf-8 -*-
"""配置适配层：兼容引擎内部 dict 配置接口与 Pydantic AnalysisConfig 模型。

engine/ 内部模块通过 dict[str, Any] 访问配置，此模块负责在
Pydantic AnalysisConfig ↔ dict 之间进行转换。
"""
from __future__ import annotations

from typing import Any

DEFAULTS: dict[str, Any] = {
    "output_dir": "output/analysis",
    "db_path": "perfetto_analysis.db",
    "refresh_rate_preset": 60,
    "app_type": "auto",
    "analyze_top": 20,
    "slow_binder_threshold_ms": 2.0,
    "sched_latency_threshold_ms": 1.0,
}


def from_pydantic(cfg: Any) -> dict[str, Any]:
    """将 Pydantic AnalysisConfig 转换为引擎内部使用的 dict 配置。"""
    if hasattr(cfg, "model_dump"):
        return {**DEFAULTS, **cfg.model_dump()}
    if isinstance(cfg, dict):
        out = dict(DEFAULTS)
        out.update(cfg)
        return out
    return dict(DEFAULTS)


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """从文件加载配置（向后兼容接口，优先使用 from_pydantic）。"""
    import json
    from pathlib import Path

    out = dict(DEFAULTS)
    if not config_path:
        return out
    p = Path(config_path)
    if not p.is_file():
        return out
    with open(p, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k in DEFAULTS:
                out[k] = v
    return out


def get_output_dir(config: dict[str, Any]) -> str:
    return str(config.get("output_dir", DEFAULTS["output_dir"]))


def get_db_path(config: dict[str, Any]) -> str:
    return str(config.get("db_path", DEFAULTS["db_path"]))


def get_refresh_rate_preset(config: dict[str, Any]) -> int | float:
    return config.get("refresh_rate_preset", DEFAULTS["refresh_rate_preset"])
