# -*- coding: utf-8 -*-
"""ToolReturn 集成测试：验证各工具返回 ToolReturn 格式。"""

import unittest
from unittest.mock import MagicMock

from modules.perfetto_analysis.src.result_compressor import ResultCompressor
from modules.perfetto_analysis.src.agent.tools import build_analysis_tools


class _MockPaService:
    """模拟 PerfettoAnalysisService。"""

    def get_trace_overview(self, trace_path, process_name=""):
        return {"duration_ns": 5_000_000_000, "processes": ["com.test.app"]}

    def parse_only(self, trace_path, process_name=""):
        return {
            "jank_frames": [
                {"frame_number": i, "duration_ms": 30 + i, "severity": "MEDIUM"}
                for i in range(10)
            ]
        }

    def analyze_dimensions(self, trace_path, process_name, dimensions, compact=True):
        return {
            dim: {"issues": [{"description": f"{dim} 问题"}], "metrics": {}}
            for dim in dimensions
        }

    def get_analysis_history(self, limit=20):
        return [{"id": 1, "trace": "test.perfetto-trace", "scene": "jank"}]

    def find_slices(self, trace_path, slice_name, process_name=""):
        return [{"name": slice_name, "dur": 1000, "ts": 500}]

    def execute_sql(self, trace_path, sql):
        return [{"col1": "val1"}]

    def analyze_anr(self, trace_path, process_name=""):
        return {"anr_detected": True, "main_thread_state": "blocked"}

    def analyze_memory(self, trace_path, process_name=""):
        return {"heap_size_mb": 256, "leak_suspected": False}


class TestToolReturnFormat(unittest.TestCase):
    """所有工具 MUST 返回 ToolReturn 格式。"""

    def setUp(self):
        self.pa_service = _MockPaService()
        self.compressor = ResultCompressor()
        self.tools = build_analysis_tools(self.pa_service, self.compressor)
        self.tool_map = {t.__name__: t for t in self.tools}

    def _assert_tool_return(self, result):
        self.assertTrue(hasattr(result, "return_value"), "缺少 return_value")
        self.assertTrue(hasattr(result, "metadata"), "缺少 metadata")
        self.assertIsInstance(result.return_value, str)
        self.assertIsInstance(result.metadata, dict)

    def test_tool_count(self):
        """验证工具数量为 9（移除了 pa_analyze_full 和 pa_cpu_overview）。"""
        self.assertEqual(len(self.tools), 9)

    def test_pa_trace_overview(self):
        result = self.tool_map["pa_trace_overview"]("test.trace")
        self._assert_tool_return(result)
        self.assertIn("raw", result.metadata)

    def test_pa_detect_jank(self):
        result = self.tool_map["pa_detect_jank"]("test.trace")
        self._assert_tool_return(result)
        self.assertIn("Jank", result.return_value)

    def test_pa_analyze_dimension(self):
        result = self.tool_map["pa_analyze_dimension"]("test.trace", "cpu")
        self._assert_tool_return(result)

    def test_pa_list_dimensions(self):
        result = self.tool_map["pa_list_dimensions"]()
        self._assert_tool_return(result)
        self.assertIn("cpu", result.return_value)

    def test_pa_get_history(self):
        result = self.tool_map["pa_get_history"]()
        self._assert_tool_return(result)

    def test_pa_find_slices(self):
        result = self.tool_map["pa_find_slices"]("test.trace", "doFrame")
        self._assert_tool_return(result)

    def test_pa_execute_sql(self):
        result = self.tool_map["pa_execute_sql"]("test.trace", "SELECT 1")
        self._assert_tool_return(result)

    def test_pa_analyze_anr(self):
        result = self.tool_map["pa_analyze_anr"]("test.trace")
        self._assert_tool_return(result)

    def test_pa_analyze_memory(self):
        result = self.tool_map["pa_analyze_memory"]("test.trace")
        self._assert_tool_return(result)

    def test_return_value_within_budget(self):
        """每个工具返回值不超过 300 token (~750 字符)。"""
        max_chars = int(300 * 2.5) + 20
        for name, tool in self.tool_map.items():
            if name == "pa_list_dimensions":
                result = tool()
            elif name in ("pa_get_history",):
                result = tool()
            elif name == "pa_analyze_dimension":
                result = tool("test.trace", "cpu")
            elif name == "pa_find_slices":
                result = tool("test.trace", "doFrame")
            elif name == "pa_execute_sql":
                result = tool("test.trace", "SELECT 1")
            else:
                result = tool("test.trace")
            self.assertLessEqual(
                len(result.return_value), max_chars,
                f"{name} 的 return_value 超出 token 预算: {len(result.return_value)} 字符"
            )

    def test_error_handling(self):
        """工具异常时返回 ToolReturn 格式的错误信息。"""
        service = MagicMock()
        service.get_trace_overview.side_effect = RuntimeError("连接失败")
        tools = build_analysis_tools(service, self.compressor)
        tool_map = {t.__name__: t for t in tools}

        result = tool_map["pa_trace_overview"]("bad.trace")
        self._assert_tool_return(result)
        self.assertIn("错误", result.return_value)
        self.assertIn("error", result.metadata)


if __name__ == "__main__":
    unittest.main()
