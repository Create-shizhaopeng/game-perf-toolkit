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


class TestThreadStateSummary:
    """thread_state_summary 方法测试。"""

    def test_returns_summary_with_data(self, trace_path: str) -> None:
        """MCP 返回行数据时正确解析各状态占比。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.execute_sql.return_value = {
            "rows": [
                {"state": "Running", "total_dur": 4_000_000_000, "cnt": 100},
                {"state": "S", "total_dur": 5_000_000_000, "cnt": 50},
                {"state": "R", "total_dur": 1_000_000_000, "cnt": 30},
            ],
        }
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp)

        result = toolkit.thread_state_summary(trace_path, "com.app")

        from modules.perfetto_analysis.src.models import ThreadStateSummary
        assert isinstance(result, ThreadStateSummary)
        assert result.dominant_state == "Running"
        assert len(result.states) == 3
        assert result.total_duration_ms > 0

    def test_compact_mode(self, trace_path: str) -> None:
        """compact=True 返回 dict 而非 Pydantic 模型。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.execute_sql.return_value = {
            "rows": [
                {"state": "Running", "total_dur": 6_000_000_000, "cnt": 80},
                {"state": "S", "total_dur": 4_000_000_000, "cnt": 40},
            ],
        }
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp)

        result = toolkit.thread_state_summary(trace_path, "com.app", compact=True)

        assert isinstance(result, dict)
        assert "dominant_state" in result
        assert "states" in result
        assert result["row_count"] == 2

    def test_empty_mcp_response(self, trace_path: str) -> None:
        """MCP 返回 None 时返回空 summary。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.execute_sql.return_value = None
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp)

        result = toolkit.thread_state_summary(trace_path, "com.app")

        from modules.perfetto_analysis.src.models import ThreadStateSummary
        assert isinstance(result, ThreadStateSummary)
        assert result.states == []
        assert result.dominant_state == ""

    def test_with_time_range(self, trace_path: str) -> None:
        """传入 time_range 时 SQL 包含时间过滤。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.execute_sql.return_value = {"rows": []}
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp)

        time_range = {"start_ms": 1000.0, "end_ms": 2000.0}
        toolkit.thread_state_summary(trace_path, "com.app", time_range=time_range)

        call_args = mcp.execute_sql.call_args[0]
        sql = call_args[1]
        assert "ts.ts >=" in sql
        assert "ts.ts + ts.dur <=" in sql

    def test_chain_step_recorded(self, trace_path: str) -> None:
        """调用后分析链路中记录步骤。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.execute_sql.return_value = {"rows": []}
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp)
        toolkit.reset_chain()

        toolkit.thread_state_summary(trace_path, "com.app")

        assert len(toolkit._chain_steps) == 1
        assert toolkit._chain_steps[0].tool_name == "thread_state_summary"


class TestCpuFreqAnalysis:
    """cpu_freq_analysis 方法测试。"""

    def test_returns_analysis_with_data(self, trace_path: str) -> None:
        """MCP 返回核心数据时正确解析。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.execute_sql.side_effect = [
            {
                "rows": [
                    {"cpu": 7, "running_segments": 50, "total_running_ns": 3_000_000_000},
                    {"cpu": 4, "running_segments": 30, "total_running_ns": 2_000_000_000},
                ],
            },
            {"rows": [{"freq_min": 800000, "freq_max": 2800000, "freq_avg": 1800000}]},
            {"rows": [{"freq_min": 600000, "freq_max": 2000000, "freq_avg": 1200000}]},
        ]
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp)

        result = toolkit.cpu_freq_analysis(trace_path, "com.app")

        from modules.perfetto_analysis.src.models import CpuFreqAnalysis
        assert isinstance(result, CpuFreqAnalysis)
        assert result.primary_core == 7
        assert len(result.cores) == 2
        assert result.cores[0].freq_max_khz == 2800000

    def test_compact_mode(self, trace_path: str) -> None:
        """compact=True 返回 dict。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.execute_sql.side_effect = [
            {
                "rows": [
                    {"cpu": 6, "running_segments": 20, "total_running_ns": 1_000_000_000},
                ],
            },
            {"rows": [{"freq_min": 500000, "freq_max": 2500000, "freq_avg": 1500000}]},
        ]
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp)

        result = toolkit.cpu_freq_analysis(trace_path, "com.app", compact=True)

        assert isinstance(result, dict)
        assert "primary_core" in result
        assert result["core_count"] == 1

    def test_no_running_data(self, trace_path: str) -> None:
        """MCP 返回空核心数据时处理。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.execute_sql.return_value = {"rows": []}
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp)

        result = toolkit.cpu_freq_analysis(trace_path, "com.app")

        from modules.perfetto_analysis.src.models import CpuFreqAnalysis
        assert isinstance(result, CpuFreqAnalysis)
        assert result.cores == []
        assert result.primary_core == -1

    def test_chain_step_recorded(self, trace_path: str) -> None:
        """调用后分析链路中记录步骤。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.execute_sql.return_value = {"rows": []}
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp)
        toolkit.reset_chain()

        toolkit.cpu_freq_analysis(trace_path, "com.app")

        assert len(toolkit._chain_steps) == 1
        assert toolkit._chain_steps[0].tool_name == "cpu_freq_analysis"


class TestCompactPassthrough:
    """find_slices 和 execute_sql 的 compact 模式测试。"""

    def test_find_slices_compact(self, trace_path: str) -> None:
        """compact 模式截断结果。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        rows = [{"name": f"slice_{i}"} for i in range(20)]
        mcp.find_slices.return_value = {"rows": rows, "columns": ["name"]}
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp)

        result = toolkit.find_slices(trace_path, "egl*", compact=True)

        assert result is not None
        assert result["total_rows"] == 20
        assert result["sample_count"] == 5
        assert len(result["sample"]) == 5

    def test_find_slices_no_compact(self, trace_path: str) -> None:
        """非 compact 模式返回全量。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        rows = [{"name": f"slice_{i}"} for i in range(20)]
        payload = {"rows": rows, "columns": ["name"]}
        mcp.find_slices.return_value = payload
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp)

        result = toolkit.find_slices(trace_path, "egl*", compact=False)

        assert result is payload

    def test_execute_sql_compact(self, trace_path: str) -> None:
        """compact 模式截断 SQL 结果。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        rows = [{"ts": i, "val": i * 10} for i in range(100)]
        mcp.execute_sql.return_value = {"rows": rows, "columns": ["ts", "val"]}
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp)

        result = toolkit.execute_sql(trace_path, "SELECT * FROM counter", compact=True)

        assert result is not None
        assert result["total_rows"] == 100
        assert result["sample_count"] == 5
        assert len(result["sample"]) == 5

    def test_execute_sql_none_result(self, trace_path: str) -> None:
        """MCP 返回 None 时即使 compact 也返回 None。"""
        cfg = AnalysisConfig()
        mcp = MagicMock()
        mcp.execute_sql.return_value = None
        toolkit = AnalysisToolkit(cfg, mcp_client=mcp)

        result = toolkit.execute_sql(trace_path, "SELECT 1", compact=True)

        assert result is None
