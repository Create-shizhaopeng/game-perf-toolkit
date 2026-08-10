"""PerfDog 分析模块 — 服务冒烟测试。"""

from __future__ import annotations

from modules.perfdog_insights.src.service import PerfdogInsightsService


def test_service_info():
    svc = PerfdogInsightsService()
    info = svc.get_service_info()
    assert info["name"] == "perfdog_insights"
    assert "display_name" in info


def test_service_imports_core_perfdog():
    """服务层委托 toolkit.core.perfdog，确保可正常导入。"""
    import toolkit.core.perfdog as core_perfdog

    assert hasattr(core_perfdog, "load_and_analyze")
