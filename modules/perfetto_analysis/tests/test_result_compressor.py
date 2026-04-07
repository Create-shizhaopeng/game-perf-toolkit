# -*- coding: utf-8 -*-
"""ResultCompressor.compress_tool_output() 单元测试。"""

import unittest

from modules.perfetto_analysis.src.result_compressor import ResultCompressor


class TestCompressToolOutput(unittest.TestCase):
    """测试 compress_tool_output 各压缩策略。"""

    def setUp(self):
        self.compressor = ResultCompressor()

    def test_none_input(self):
        result = self.compressor.compress_tool_output("pa_detect_jank", None)
        self.assertEqual(result, "工具未返回数据")

    def test_empty_dict_input(self):
        result = self.compressor.compress_tool_output("pa_detect_jank", {})
        self.assertEqual(result, "工具未返回数据")

    def test_error_input(self):
        data = {"error": "连接超时"}
        result = self.compressor.compress_tool_output("pa_detect_jank", data)
        self.assertIn("连接超时", result)

    def test_jank_top5_with_200_frames(self):
        """200 条 jank → Top-5 + 统计摘要。"""
        frames = [
            {"frame_number": i, "duration_ms": 20 + i * 0.5, "severity": "MEDIUM"}
            for i in range(200)
        ]
        data = {"jank_frames": frames}
        result = self.compressor.compress_tool_output("pa_detect_jank", data, 300)

        self.assertIn("200", result)
        self.assertIn("Top-5", result)
        lines_with_frame = [
            l for l in result.split("\n")
            if l.strip().startswith(("1.", "2.", "3.", "4.", "5."))
        ]
        self.assertEqual(len(lines_with_frame), 5)

    def test_jank_empty_frames(self):
        data = {"jank_frames": []}
        result = self.compressor.compress_tool_output("pa_detect_jank", data)
        self.assertIn("未检测到", result)

    def test_dimension_with_issues(self):
        """维度分析 → issues + top 指标。"""
        data = {
            "cpu": {
                "issues": [
                    {"description": "CPU 占用率过高 (95%)"},
                    {"description": "大核未调度"},
                ]
            },
            "thread": {
                "issues": []
            },
        }
        result = self.compressor.compress_tool_output("pa_analyze_dimension", data)
        self.assertIn("cpu", result)
        self.assertIn("2 个问题", result)
        self.assertIn("thread", result)
        self.assertIn("无异常", result)

    def test_generic_truncation_string(self):
        long_text = "A" * 2000
        result = self.compressor.compress_tool_output("pa_find_slices", long_text, 300)
        max_chars = int(300 * 2.5)
        self.assertLessEqual(len(result), max_chars + 20)

    def test_generic_truncation_large_dict(self):
        data = {f"key_{i}": f"value_{i}" * 50 for i in range(100)}
        result = self.compressor.compress_tool_output("pa_execute_sql", data, 300)
        max_chars = int(300 * 2.5)
        self.assertLessEqual(len(result), max_chars + 20)

    def test_generic_list(self):
        data = [{"id": i, "name": f"item_{i}"} for i in range(50)]
        result = self.compressor.compress_tool_output("pa_find_slices", data)
        self.assertIn("50", result)

    def test_token_budget_respected(self):
        """确保输出不超过 token 预算对应的字符数。"""
        frames = [
            {"frame_number": i, "duration_ms": 100 + i, "severity": "CRITICAL"}
            for i in range(500)
        ]
        data = {"jank_frames": frames}
        result = self.compressor.compress_tool_output("pa_detect_jank", data, 300)
        max_chars = int(300 * 2.5)
        self.assertLessEqual(len(result), max_chars + 20)


if __name__ == "__main__":
    unittest.main()
