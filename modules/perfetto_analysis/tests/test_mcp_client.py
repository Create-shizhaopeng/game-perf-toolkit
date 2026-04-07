# -*- coding: utf-8 -*-
"""McpAnalysisClient 单元测试。"""
from __future__ import annotations

from unittest.mock import patch

from modules.perfetto_analysis.src.mcp_client import McpAnalysisClient


class TestMcpAnalysisClient:
    """McpAnalysisClient 行为测试。"""

    def test_analyze_thread_contention_returns_none_by_default(self) -> None:
        client = McpAnalysisClient()
        assert client.analyze_thread_contention("/t", "p") is None

    def test_analyze_binder_returns_none_by_default(self) -> None:
        client = McpAnalysisClient()
        assert client.analyze_binder("/t", "p") is None

    def test_get_main_thread_hotspots_returns_none_by_default(self) -> None:
        client = McpAnalysisClient()
        assert client.get_main_thread_hotspots("/t", "p") is None

    def test_get_cpu_utilization_returns_none_by_default(self) -> None:
        client = McpAnalysisClient()
        assert client.get_cpu_utilization("/t", "p") is None

    def test_find_slices_returns_none_by_default(self) -> None:
        client = McpAnalysisClient()
        assert client.find_slices("/t", "pat") is None

    def test_execute_sql_returns_none_by_default(self) -> None:
        client = McpAnalysisClient()
        assert client.execute_sql("/t", "SELECT 1") is None

    def test_detect_anrs_returns_none_by_default(self) -> None:
        client = McpAnalysisClient()
        assert client.detect_anrs("/t", "p") is None

    def test_detect_memory_leaks_returns_none_by_default(self) -> None:
        client = McpAnalysisClient()
        assert client.detect_memory_leaks("/t", "p") is None

    def test_call_mcp_tool_with_mock_success(self) -> None:
        payload = {"rows": [{"a": 1}]}
        with patch.object(McpAnalysisClient, "_call_mcp_tool", return_value=payload):
            client = McpAnalysisClient()
            assert client.analyze_thread_contention("/trace", "proc") is payload

    def test_call_mcp_tool_timeout(self) -> None:
        with patch.object(McpAnalysisClient, "_call_mcp_tool", return_value=None):
            client = McpAnalysisClient()
            assert client.analyze_thread_contention("/trace", "proc") is None

    def test_time_range_passed_to_mcp(self) -> None:
        client = McpAnalysisClient()
        with patch.object(client, "_call_mcp_tool", return_value=None) as mock_call:
            tr = {"start_ms": 100.0, "end_ms": 200.0}
            client.analyze_thread_contention("/trace", "proc", time_range=tr)
        mock_call.assert_called_once()
        call_args = mock_call.call_args[0]
        assert call_args[0] == "thread_contention_analyzer"
        assert call_args[1]["time_range"] == tr
        assert call_args[1]["trace_path"] == "/trace"
        assert call_args[1]["process_name"] == "proc"

    def test_client_init_with_custom_timeout(self) -> None:
        client = McpAnalysisClient(timeout_ms=5000)
        assert client.timeout_ms == 5000
