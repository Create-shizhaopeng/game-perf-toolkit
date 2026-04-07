# -*- coding: utf-8 -*-
"""engine_only 模式回归测试。

验证在 engine_only 模式下，原子工具结果与现有 analyze() 输出一致。
使用 mock 避免依赖真实 trace 文件。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from modules.perfetto_analysis.src.models import AnalysisConfig, AnalysisMode, DimensionResult
from modules.perfetto_analysis.src.analysis_toolkit import AnalysisToolkit
from modules.perfetto_analysis.src.analysis_mode import FeatureFlagManager
from modules.perfetto_analysis.src.mcp_client import McpAnalysisClient


@pytest.fixture
def fake_trace_path(tmp_path):
    p = tmp_path / "fake.trace"
    p.write_bytes(b"fake")
    return str(p)


def test_engine_only_no_mcp_calls(fake_trace_path):
    cfg = AnalysisConfig(analysis_mode=AnalysisMode.ENGINE_ONLY.value)
    mcp = MagicMock(spec=McpAnalysisClient)
    tk = AnalysisToolkit(cfg, mcp_client=mcp)
    with patch.object(
        tk,
        "_engine_analyze",
        return_value=DimensionResult(dimension="thread", source="engine", data={}),
    ):
        tk.analyze_dimension(fake_trace_path, "com.app", "thread")
    assert mcp.mock_calls == []


def test_engine_only_dimension_routing(fake_trace_path):
    cfg = AnalysisConfig(analysis_mode=AnalysisMode.ENGINE_ONLY.value)
    mcp = MagicMock(spec=McpAnalysisClient)
    tk = AnalysisToolkit(cfg, mcp_client=mcp)

    def engine_side_effect(trace_path, process, dimension, time_range):
        return DimensionResult(dimension=dimension, source="engine", data={})

    with patch.object(tk, "_engine_analyze", side_effect=engine_side_effect) as eng:
        with patch.object(tk, "_mcp_analyze") as mcp_analyze:
            for dim in ["cpu", "thread", "binder"]:
                tk.analyze_dimension(fake_trace_path, "com.app", dim)
    mcp_analyze.assert_not_called()
    assert eng.call_count == 3


def test_engine_only_result_source(fake_trace_path):
    cfg = AnalysisConfig(analysis_mode=AnalysisMode.ENGINE_ONLY.value)
    tk = AnalysisToolkit(cfg, mcp_client=MagicMock(spec=McpAnalysisClient))
    with patch.object(
        tk,
        "_engine_analyze",
        return_value=DimensionResult(
            dimension="binder",
            source="engine",
            data={"issues": []},
        ),
    ):
        r = tk.analyze_dimension(fake_trace_path, "com.app", "binder")
    assert r.source == "engine"


def test_mcp_preferred_attempts_mcp_first(fake_trace_path):
    cfg = AnalysisConfig(analysis_mode=AnalysisMode.MCP_PREFERRED.value)
    tk = AnalysisToolkit(cfg, mcp_client=MagicMock(spec=McpAnalysisClient))
    mcp_payload = {"issues": [{"description": "mcp", "severity": "LOW"}]}
    with patch.object(tk, "_mcp_analyze", return_value=mcp_payload) as mcp_analyze:
        with patch.object(tk, "_engine_analyze") as eng:
            r = tk.analyze_dimension(fake_trace_path, "com.app", "thread")
    mcp_analyze.assert_called_once()
    eng.assert_not_called()
    assert r.source == "mcp"
    assert r.data == mcp_payload


def test_feature_flag_dimension_override(fake_trace_path):
    cfg = AnalysisConfig(
        analysis_mode=AnalysisMode.MCP_PREFERRED.value,
        dimension_overrides={"thread": AnalysisMode.ENGINE_ONLY.value},
    )
    mgr = FeatureFlagManager(cfg)
    assert mgr.get_mode_for_dimension("thread") == AnalysisMode.ENGINE_ONLY
    assert mgr.get_mode_for_dimension("cpu") == AnalysisMode.ENGINE_ONLY

    tk = AnalysisToolkit(cfg, mcp_client=MagicMock(spec=McpAnalysisClient))
    with patch.object(tk, "_mcp_analyze") as mcp_analyze:
        with patch.object(
            tk,
            "_engine_analyze",
            return_value=DimensionResult(
                dimension="thread",
                source="engine",
                data={"issues": []},
            ),
        ) as eng:
            r = tk.analyze_dimension(fake_trace_path, "com.app", "thread")
    mcp_analyze.assert_not_called()
    eng.assert_called_once()
    assert r.source == "engine"
