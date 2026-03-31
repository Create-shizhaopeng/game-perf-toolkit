# -*- coding: utf-8 -*-
"""AnalysisToolkit 单元测试。"""
from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from modules.perfetto_analysis.src.analysis_toolkit import AnalysisToolkit
from modules.perfetto_analysis.src.analysis_mode import FeatureFlagManager
from modules.perfetto_analysis.src.mcp_client import McpAnalysisClient
from modules.perfetto_analysis.src.models import AnalysisConfig


def _temp_trace_path() -> str:
    f = tempfile.NamedTemporaryFile(suffix=".pftrace", delete=False)
    f.close()
    return f.name


@pytest.fixture
def trace_path() -> str:
    path = _temp_trace_path()
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


class TestAnalysisToolkit:
    """AnalysisToolkit 路由与链路测试。"""

    def test_analyze_dimension_engine_only(
        self, trace_path: str,
    ) -> None:
        """仅引擎：cpu 维度默认 engine_only，不调用 MCP。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp, flag_manager=FeatureFlagManager(cfg))

        parse_result = {
            "trace_start_ns": 0,
            "trace_end_ns": 10_000_000_000,
            "jank_records": [],
        }
        mock_tp = MagicMock()
        with patch(
            "modules.perfetto_analysis.src.engine.parser.parse_trace_with_tp",
            return_value=(parse_result, mock_tp),
        ), patch(
            "modules.perfetto_analysis.src.engine.analyzer.analyze_jank",
            return_value={"per_jank_analyses": [{"cpu": {"ok": True}}]},
        ):
            result = toolkit.analyze_dimension(trace_path, "com.app", "cpu", None)

        assert result.source == "engine"
        assert result.data.get("per_jank_count") == 1
        mcp.analyze_thread_contention.assert_not_called()

    def test_analyze_dimension_mcp_preferred_success(
        self, trace_path: str,
    ) -> None:
        """MCP 优先：MCP 返回数据时 source=mcp。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.analyze_thread_contention.return_value = {"from_mcp": True}
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp, flag_manager=FeatureFlagManager(cfg))

        result = toolkit.analyze_dimension(trace_path, "com.app", "thread", None)

        assert result.source == "mcp"
        assert result.data == {"from_mcp": True}
        mcp.analyze_thread_contention.assert_called_once()

    def test_analyze_dimension_mcp_preferred_fallback(
        self, trace_path: str,
    ) -> None:
        """MCP 优先：MCP 返回 None 时降级引擎，source=degraded。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.analyze_thread_contention.return_value = None
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp, flag_manager=FeatureFlagManager(cfg))

        parse_result = {
            "trace_start_ns": 0,
            "trace_end_ns": 10_000_000_000,
            "jank_records": [],
        }
        mock_tp = MagicMock()
        with patch(
            "modules.perfetto_analysis.src.engine.parser.parse_trace_with_tp",
            return_value=(parse_result, mock_tp),
        ), patch(
            "modules.perfetto_analysis.src.engine.analyzer.analyze_jank",
            return_value={"per_jank_analyses": [{"thread": {"t": 1}}]},
        ):
            result = toolkit.analyze_dimension(trace_path, "com.app", "thread", None)

        assert result.source == "degraded"
        assert result.data.get("per_jank_count") == 1

    def test_analyze_dimension_mcp_only_unavailable(
        self, trace_path: str,
    ) -> None:
        """纯 MCP：MCP 无数据时 source=unavailable。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.get_main_thread_hotspots.return_value = None
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp, flag_manager=FeatureFlagManager(cfg))

        result = toolkit.analyze_dimension(trace_path, "com.app", "hotspot", None)

        assert result.source == "unavailable"
        assert result.error == "MCP 工具未返回数据"

    def test_time_range_validation(self, trace_path: str) -> None:
        """time_range 超出 trace 范围时返回错误。"""
        cfg = AnalysisConfig()
        toolkit = AnalysisToolkit(
            cfg,
            mcp_client=McpAnalysisClient(),
            flag_manager=FeatureFlagManager(cfg),
        )

        parse_result = {
            "trace_start_ns": 1_000_000_000,
            "trace_end_ns": 2_000_000_000,
            "jank_records": [],
        }
        mock_tp = MagicMock()
        with patch(
            "modules.perfetto_analysis.src.engine.parser.parse_trace_with_tp",
            return_value=(parse_result, mock_tp),
        ):
            result = toolkit.analyze_dimension(
                trace_path,
                "com.app",
                "cpu",
                {"start_ms": 0.0, "end_ms": 100.0},
            )

        assert result.source == "unavailable"
        assert "超出 trace 范围" in (result.error or "")

    def test_merge_overlapping_frames(self) -> None:
        """重叠帧窗口合并为一条。"""
        frames = [
            {
                "index": 0,
                "jank_num": 1,
                "window_start_ns": 0,
                "window_end_ns": 100,
                "window_start_ms": 0.0,
                "window_end_ms": 0.1,
            },
            {
                "index": 1,
                "jank_num": 2,
                "window_start_ns": 50,
                "window_end_ns": 150,
                "window_start_ms": 0.05,
                "window_end_ms": 0.15,
            },
        ]
        merged = AnalysisToolkit._merge_overlapping_frames(frames)
        assert len(merged) == 1
        assert merged[0]["window_end_ns"] == 150
        assert merged[0]["jank_num"] == 3

    def test_chain_step_recording(self, trace_path: str) -> None:
        """analyze_dimension 后链路步骤记录。"""

        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.analyze_thread_contention.return_value = {"x": 1}
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp, flag_manager=FeatureFlagManager(cfg))
        toolkit.reset_chain()

        toolkit.analyze_dimension(trace_path, "com.app", "thread", None)

        assert len(toolkit._chain_steps) == 1
        step = toolkit._chain_steps[0]
        assert step.tool_name == "analyze_dimension"
        assert step.source == "mcp"
        assert "source=mcp" in step.output_summary

    def test_reset_chain(self, trace_path: str) -> None:
        """reset_chain 清空步骤。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.analyze_thread_contention.return_value = {"x": 1}
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp, flag_manager=FeatureFlagManager(cfg))
        toolkit.analyze_dimension(trace_path, "com.app", "thread", None)
        assert len(toolkit._chain_steps) >= 1

        toolkit.reset_chain()
        assert toolkit._chain_steps == []

    def test_get_chain_result(self, trace_path: str) -> None:
        """get_chain_result 返回完整链路。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.analyze_thread_contention.return_value = {"x": 1}
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp, flag_manager=FeatureFlagManager(cfg))
        toolkit.reset_chain()

        toolkit.analyze_dimension(trace_path, "com.app", "thread", None)
        chain = toolkit.get_chain_result(conclusion="完成", confidence=0.85)

        assert len(chain.steps) == 1
        assert chain.steps[0].tool_name == "analyze_dimension"
        assert chain.conclusion == "完成"
        assert chain.confidence == 0.85
