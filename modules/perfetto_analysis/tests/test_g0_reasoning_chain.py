# -*- coding: utf-8 -*-
"""G0 SubAgent 推理链重构测试。

覆盖 T001-T029 的关键功能点：
- SOP frontmatter 解析与场景注册表
- 压缩策略（degraded_aware / jank_records）
- 缓存基础设施
- 推理链 prompt 模板
- 预取流程 + 已知信息注入
- pa_detect_jank 结构化数据修复
- 遥测数据采集
"""

import json
import sqlite3
import unittest
from unittest.mock import MagicMock, patch

from modules.perfetto_analysis.src.agent import (
    CompressionProfile,
    PrefetchSpec,
    SceneMeta,
)
from modules.perfetto_analysis.src.agent.prompts import (
    _parse_frontmatter,
    build_reasoning_chain_prompt,
    get_scene_meta,
    get_scene_registry,
)
from modules.perfetto_analysis.src.agent.tools import (
    COMPRESSION_PROFILES,
    build_analysis_tools,
)
from modules.perfetto_analysis.src.result_compressor import ResultCompressor


class _MockPaService:
    """用于测试的模拟 PerfettoAnalysisService。"""

    def __init__(self):
        self._analysis_cache: dict = {}
        self._db_manager = None

    def cache_key(self, trace_path, tool, **kwargs):
        parts = [trace_path, tool]
        for k in sorted(kwargs):
            parts.append(f"{k}={kwargs[k]}")
        return "|".join(parts)

    def get_cached(self, key):
        return self._analysis_cache.get(key)

    def set_cached(self, key, value):
        self._analysis_cache[key] = value

    def clear_cache(self):
        self._analysis_cache.clear()

    def get_trace_overview(self, trace_path, process_name=""):
        return {"duration_ns": 5_000_000_000, "processes": ["com.test.app"]}

    def parse_only(self, trace_path, process_name=""):
        return {
            "jank_frames": [
                {"frame_number": i, "duration_ms": 30 + i, "severity": "MEDIUM"}
                for i in range(10)
            ]
        }

    def analyze_dimensions(self, trace_path, process_name, dimensions, on_progress=None):
        return {
            dim: {"degraded": dim == "cpu", "freq_mhz": 1800, "issues": [], "count": 5}
            for dim in dimensions
        }

    def get_analysis_history(self, limit=20):
        return [{"id": 1, "trace": "test.trace", "scene": "jank"}]


# ==========================================================================
# Test 1: SOP frontmatter 解析 + 场景注册表
# ==========================================================================


class TestSOPFrontmatter(unittest.TestCase):

    def test_parse_frontmatter_valid(self):
        content = "---\nscene: jank\ndisplay_name: 卡顿分析\npriority_dims: [cpu]\n---\n# SOP"
        meta, body = _parse_frontmatter(content)
        self.assertEqual(meta["scene"], "jank")
        self.assertEqual(meta["display_name"], "卡顿分析")
        self.assertIn("# SOP", body)

    def test_parse_frontmatter_no_frontmatter(self):
        content = "# No frontmatter\nsome content"
        meta, body = _parse_frontmatter(content)
        self.assertEqual(meta, {})
        self.assertEqual(body, content)

    def test_parse_frontmatter_invalid_yaml(self):
        content = "---\n: invalid: yaml: [[\n---\n# Body"
        meta, body = _parse_frontmatter(content)
        self.assertEqual(meta, {})

    def test_scene_registry_loads_all_sops(self):
        registry = get_scene_registry()
        self.assertGreaterEqual(len(registry), 9)
        expected_scenes = {"jank", "anr", "memory", "startup", "io", "general",
                           "input-latency", "response-latency", "rotation"}
        self.assertEqual(expected_scenes, set(registry.keys()))

    def test_scene_meta_has_required_fields(self):
        meta = get_scene_meta("jank")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.scene, "jank")
        self.assertIsInstance(meta.priority_dims, list)
        self.assertTrue(len(meta.priority_dims) > 0)
        self.assertIsInstance(meta.prefetch, list)

    def test_scene_meta_prefetch_has_spec(self):
        meta = get_scene_meta("jank")
        self.assertTrue(len(meta.prefetch) > 0)
        for spec in meta.prefetch:
            self.assertIsInstance(spec, PrefetchSpec)
            self.assertTrue(spec.tool)
            self.assertTrue(spec.inject_as)

    def test_unknown_scene_returns_none(self):
        meta = get_scene_meta("nonexistent_scene")
        self.assertIsNone(meta)


# ==========================================================================
# Test 2: 压缩策略
# ==========================================================================


class TestCompressionStrategies(unittest.TestCase):

    def setUp(self):
        self.compressor = ResultCompressor()

    def test_degraded_aware_preserves_degraded(self):
        data = {
            "cpu": {"degraded": True, "freq_mhz": 1800, "load": 95},
            "thread": {"degraded": False, "count": 5},
        }
        result = self.compressor._compress_degraded_aware(data, 500)
        self.assertIn("DEGRADED", result)
        self.assertIn("1800", result)
        self.assertIn("正常", result)

    def test_degraded_aware_no_degraded_field(self):
        data = {"cpu": {"anomalies": [{"description": "限频"}]}}
        result = self.compressor._compress_degraded_aware(data, 500)
        self.assertIn("限频", result)

    def test_jank_records_preserves_jank_data(self):
        data = {
            "jank_frames": [{"frame": 1, "dur": 30}],
            "jank_times": 5,
            "frame_count": 100,
            "vsync_cycles": list(range(1000)),
        }
        result = self.compressor._compress_jank_records(data, 500)
        self.assertIn("jank_frames", result)
        self.assertIn("jank_times", result)
        self.assertIn("frame_count", result)
        self.assertIn("精简", result)

    def test_compression_profiles_cover_all_tools(self):
        expected = {
            "pa_trace_overview", "pa_detect_jank", "pa_analyze_dimension",
            "pa_list_dimensions", "pa_get_history", "pa_find_slices",
            "pa_execute_sql", "pa_analyze_anr", "pa_analyze_memory",
            "pa_read_knowledge",
        }
        self.assertEqual(expected, set(COMPRESSION_PROFILES.keys()))

    def test_compression_profile_strategies(self):
        self.assertEqual(COMPRESSION_PROFILES["pa_trace_overview"].strategy, "keep_all")
        self.assertEqual(COMPRESSION_PROFILES["pa_detect_jank"].strategy, "jank_records")
        self.assertEqual(COMPRESSION_PROFILES["pa_analyze_dimension"].strategy, "degraded_aware")
        self.assertEqual(COMPRESSION_PROFILES["pa_analyze_anr"].strategy, "degraded_aware")


# ==========================================================================
# Test 3: 缓存基础设施
# ==========================================================================


class TestCacheInfrastructure(unittest.TestCase):

    def setUp(self):
        self.service = _MockPaService()

    def test_cache_key_generation(self):
        key = self.service.cache_key("test.trace", "detect_jank", process_name="com.test")
        self.assertIn("test.trace", key)
        self.assertIn("detect_jank", key)
        self.assertIn("process_name=com.test", key)

    def test_cache_set_and_get(self):
        self.service.set_cached("key1", {"data": 42})
        result = self.service.get_cached("key1")
        self.assertEqual(result, {"data": 42})

    def test_cache_miss(self):
        result = self.service.get_cached("nonexistent")
        self.assertIsNone(result)

    def test_cache_clear(self):
        self.service.set_cached("key1", "val1")
        self.service.clear_cache()
        self.assertIsNone(self.service.get_cached("key1"))

    def test_tool_uses_cache(self):
        """验证工具在缓存命中时不重复调用服务。"""
        compressor = ResultCompressor()
        tools = build_analysis_tools(self.service, compressor)
        tool_map = {t.__name__: t for t in tools}

        result1 = tool_map["pa_trace_overview"]("test.trace")
        self.assertIn("duration_ns", result1.metadata["raw"])

        cache_key = self.service.cache_key("test.trace", "trace_overview", process_name="")
        cached = self.service.get_cached(cache_key)
        self.assertIsNotNone(cached)

        result2 = tool_map["pa_trace_overview"]("test.trace")
        self.assertEqual(result1.return_value, result2.return_value)


# ==========================================================================
# Test 4: 推理链 prompt 模板
# ==========================================================================


class TestReasoningChainPrompt(unittest.TestCase):

    def test_prompt_has_five_parts(self):
        meta = SceneMeta(
            scene="jank",
            display_name="卡顿分析",
            priority_dims=["cpu", "thread"],
            secondary_dims=["gpu"],
            optional_dims=["gc"],
        )
        prompt = build_reasoning_chain_prompt("SOP content", meta)
        self.assertIn("分析专家", prompt)
        self.assertIn("SOP content", prompt)
        self.assertIn("必查维度", prompt)
        self.assertIn("推荐维度", prompt)
        self.assertIn("Phase A", prompt)
        self.assertIn("Phase B", prompt)
        self.assertIn("Phase C", prompt)

    def test_prompt_without_sop(self):
        prompt = build_reasoning_chain_prompt("", None)
        self.assertIn("自主判断", prompt)
        self.assertIn("Phase A", prompt)

    def test_prompt_with_scene_meta_dims(self):
        meta = SceneMeta(
            scene="anr",
            priority_dims=["thread", "binder", "lock"],
        )
        prompt = build_reasoning_chain_prompt("", meta)
        self.assertIn("thread", prompt)
        self.assertIn("binder", prompt)
        self.assertIn("lock", prompt)


# ==========================================================================
# Test 5: 预取流程 + 已知信息注入
# ==========================================================================


class TestPrefetchAndKnownInfo(unittest.TestCase):

    def test_build_known_info_block_empty(self):
        from modules.perfetto_analysis.src.agent.orchestrator import AnalysisOrchestrator
        result = AnalysisOrchestrator._build_known_info_block({})
        self.assertEqual(result, "")

    def test_build_known_info_block_with_data(self):
        from modules.perfetto_analysis.src.agent.orchestrator import AnalysisOrchestrator
        ctx = {
            "jank_frames": {"jank_times": 5, "frame_count": 100},
            "trace_info": {"duration_ns": 5000},
            "db_process_name": "com.test.app",
        }
        result = AnalysisOrchestrator._build_known_info_block(ctx)
        self.assertIn("已知信息", result)
        self.assertIn("jank_frames", result)
        self.assertIn("com.test.app", result)
        self.assertIn("无需重复调用", result)


# ==========================================================================
# Test 6: pa_detect_jank 结构化数据修复
# ==========================================================================


class TestDetectJankFix(unittest.TestCase):

    def test_dict_input_preserved(self):
        service = _MockPaService()
        compressor = ResultCompressor()
        tools = build_analysis_tools(service, compressor)
        tool_map = {t.__name__: t for t in tools}

        result = tool_map["pa_detect_jank"]("test.trace")
        raw = result.metadata["raw"]
        self.assertIsInstance(raw, dict)
        self.assertIn("jank_frames", raw)

    def test_analysis_result_object_converted(self):
        """模拟 AnalysisResult 对象（非 dict）被正确转为结构化 dict。"""
        mock_result = MagicMock()
        mock_result.parse_result = {"frames": [1, 2, 3]}
        mock_result.jank_times = 3
        mock_result.frame_count = 100
        mock_result.detected_process = "com.test"

        service = _MockPaService()
        service.parse_only = lambda tp, pn="": mock_result
        compressor = ResultCompressor()
        tools = build_analysis_tools(service, compressor)
        tool_map = {t.__name__: t for t in tools}

        result = tool_map["pa_detect_jank"]("test.trace")
        raw = result.metadata["raw"]
        self.assertIsInstance(raw, dict)
        self.assertEqual(raw["jank_times"], 3)
        self.assertEqual(raw["detected_process"], "com.test")
        self.assertIn("parse_result", raw)


# ==========================================================================
# Test 7: 遥测数据写入
# ==========================================================================


class TestTelemetryWrite(unittest.TestCase):

    def test_insert_telemetry(self):
        from modules.perfetto_analysis.src.engine.storage import (
            _create_telemetry_table,
            insert_telemetry,
        )

        conn = sqlite3.connect(":memory:")
        _create_telemetry_table(conn)

        insert_telemetry(
            conn=conn,
            task_id="test-task-001",
            trace_id="test_trace",
            scene="jank",
            model_name="glm-4-flash",
            tool_call_count=15,
            tool_calls_detail='[{"tool":"pa_detect_jank"}]',
            total_prompt_tokens=1000,
            total_completion_tokens=500,
            conclusion_quality='[]',
            elapsed_sec=12.5,
        )

        cursor = conn.execute("SELECT * FROM pa_telemetry")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 1)

        cursor = conn.execute("SELECT task_id, scene, tool_call_count FROM pa_telemetry")
        row = cursor.fetchone()
        self.assertEqual(row[0], "test-task-001")
        self.assertEqual(row[1], "jank")
        self.assertEqual(row[2], 15)

        conn.close()


# ==========================================================================
# Pydantic 模型测试
# ==========================================================================


class TestPydanticModels(unittest.TestCase):

    def test_prefetch_spec(self):
        spec = PrefetchSpec(tool="detect_jank", inject_as="jank_frames")
        self.assertEqual(spec.tool, "detect_jank")
        self.assertEqual(spec.args, {})

    def test_scene_meta(self):
        meta = SceneMeta(
            scene="jank",
            display_name="卡顿分析",
            priority_dims=["cpu", "thread"],
            prefetch=[PrefetchSpec(tool="detect_jank", inject_as="jank_frames")],
        )
        self.assertEqual(meta.scene, "jank")
        self.assertEqual(len(meta.prefetch), 1)

    def test_compression_profile(self):
        p = CompressionProfile(strategy="degraded_aware")
        self.assertEqual(p.strategy, "degraded_aware")
        self.assertEqual(p.max_tokens, 500)


if __name__ == "__main__":
    unittest.main()
