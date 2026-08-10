"""Perfetto 分析模块 — 服务冒烟测试。

注：模块分析能力已迁移到 Skill YAML + pa_execute_sql 工具，
本测试仅覆盖 service.py 当前职责（配置管理与历史记录查询）。
"""

from __future__ import annotations

from pathlib import Path

from modules.perfetto_analysis.src.models import AnalysisConfig
from modules.perfetto_analysis.src.service import PerfettoAnalysisService


def _make_service(tmp_path: Path) -> PerfettoAnalysisService:
    return PerfettoAnalysisService(data_dir=tmp_path / "data")


def test_service_info(tmp_path):
    svc = _make_service(tmp_path)
    info = svc.get_service_info()
    assert info["name"] == "perfetto_analysis"
    assert "display_name" in info


def test_get_config_returns_analysis_config(tmp_path):
    svc = _make_service(tmp_path)
    assert isinstance(svc.get_config(), AnalysisConfig)


def test_reload_config_returns_analysis_config(tmp_path):
    svc = _make_service(tmp_path)
    assert isinstance(svc.reload_config(), AnalysisConfig)


def test_get_analysis_history_returns_list(tmp_path):
    svc = _make_service(tmp_path)
    history = svc.get_analysis_history()
    assert isinstance(history, list)
    # 每条记录包含归一化字段（_get_output_dir 指向项目真实 trace_report 目录，
    # 内容取决于磁盘状态，仅验证结构）
    if history:
        entry = history[0]
        for key in ("id", "created_at", "result_dir", "status"):
            assert key in entry
