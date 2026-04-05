# -*- coding: utf-8 -*-
"""上下文超限降级测试。"""

import asyncio
import unittest
from unittest.mock import MagicMock

from modules.perfetto_analysis.src.agent.orchestrator import AnalysisOrchestrator
from modules.perfetto_analysis.src.agent import AnalysisRouting


class TestContextOverflowDetection(unittest.TestCase):
    """测试上下文超限判断逻辑。"""

    def test_max_length_detected(self):
        exc = Exception("Prompt exceeds max length")
        self.assertTrue(AnalysisOrchestrator._is_context_overflow(exc))

    def test_context_keyword_detected(self):
        exc = Exception("context window exceeded")
        self.assertTrue(AnalysisOrchestrator._is_context_overflow(exc))

    def test_token_limit_detected(self):
        exc = Exception("token limit reached")
        self.assertTrue(AnalysisOrchestrator._is_context_overflow(exc))

    def test_too_long_detected(self):
        exc = Exception("input is too long for this model")
        self.assertTrue(AnalysisOrchestrator._is_context_overflow(exc))

    def test_normal_error_not_detected(self):
        exc = Exception("connection refused")
        self.assertFalse(AnalysisOrchestrator._is_context_overflow(exc))

    def test_api_key_error_not_detected(self):
        exc = Exception("invalid API key")
        self.assertFalse(AnalysisOrchestrator._is_context_overflow(exc))


class TestDegradationFlow(unittest.TestCase):
    """测试降级流程 — SubAgent 失败后降级到 engine。"""

    def _create_orchestrator(self):
        llm_manager = MagicMock()
        llm_manager.get_config.return_value = MagicMock(
            provider="glm", model_name="glm-4-plus",
            get_api_key=lambda: "test-key"
        )
        pa_service = MagicMock()
        pa_service.analyze.return_value = {
            "summary": "引擎分析结果",
            "jank_info": {"jank_count": 5},
        }
        return AnalysisOrchestrator(llm_manager, pa_service)

    def test_fallback_engine_result_has_completion(self):
        """降级到 engine 时 result 包含 completion 标记。"""
        orch = self._create_orchestrator()
        routing = AnalysisRouting(
            scene="jank", sop_name="jank-analysis.md",
            process_name="com.test", reasoning="test"
        )
        result = asyncio.run(
            orch._fallback_engine_analysis("test.trace", routing)
        )
        self.assertIn("conclusion", result)
        self.assertEqual(result.get("token_used"), 0)


if __name__ == "__main__":
    unittest.main()
