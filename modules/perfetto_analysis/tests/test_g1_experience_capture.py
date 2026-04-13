# -*- coding: utf-8 -*-
"""G1 分析经验自动沉淀测试。

覆盖功能点：
- RootCauseItem / AnalysisOutput Pydantic 模型验证
- pa_learnings 表创建和写入
- _fallback_output 降级输出
- _extract_single_learning 经验提取
- _calc_initial_confidence 置信度计算
- _resolve_device_model 设备型号解析
- _check_conclusion_quality 结构化自检
- generate_html_report 三区块报告
- _replace_chart_placeholders 占位符替换
"""

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.perfetto_analysis.src.agent import (
    AnalysisOutput,
    AnalysisReport,
    AnalysisRouting,
    OrchestrationConfig,
    RootCauseItem,
)
from modules.perfetto_analysis.src.agent.orchestrator import AnalysisOrchestrator
from modules.perfetto_analysis.src.agent.report import (
    _replace_chart_placeholders,
    generate_html_report,
)
from modules.perfetto_analysis.src.engine.storage import (
    init_db,
    insert_learning,
)


# ================================================================
# Pydantic 模型验证 (T001-T002)
# ================================================================


class TestRootCauseItem(unittest.TestCase):
    """RootCauseItem 模型验证。"""

    def test_required_fields(self):
        rc = RootCauseItem(
            tag="cpu_throttle",
            severity="HIGH",
            qualitative="CPU 频率被限制在 1.2GHz",
            evidence="cpu_freq 数据显示降频",
            reasoning="高负载 + 温控触发",
        )
        self.assertEqual(rc.tag, "cpu_throttle")
        self.assertEqual(rc.severity, "HIGH")

    def test_optional_fields_defaults(self):
        rc = RootCauseItem(
            tag="gc_pause",
            severity="WARNING",
            qualitative="GC 暂停过长",
            evidence="GC 日志",
            reasoning="频繁分配",
        )
        self.assertEqual(rc.quantitative, {})
        self.assertEqual(rc.suggestion, "")

    def test_with_quantitative(self):
        rc = RootCauseItem(
            tag="binder_ipc",
            severity="CRITICAL",
            qualitative="Binder 调用超时",
            quantitative={"avg_latency_ms": 45.2, "count": 12},
            evidence="binder_transaction 表",
            reasoning="同步 binder 阻塞主线程",
            suggestion="改用异步 binder",
        )
        self.assertIn("avg_latency_ms", rc.quantitative)
        self.assertEqual(rc.suggestion, "改用异步 binder")

    def test_model_dump(self):
        rc = RootCauseItem(
            tag="io_block",
            severity="INFO",
            qualitative="IO 等待",
            evidence="io 数据",
            reasoning="磁盘慢",
        )
        d = rc.model_dump()
        self.assertIn("tag", d)
        self.assertIn("quantitative", d)


class TestAnalysisOutput(unittest.TestCase):
    """AnalysisOutput 模型验证。"""

    def test_full_construction(self):
        ao = AnalysisOutput(
            user_intent_summary="分析卡顿原因",
            trace_info="时长 10s, 300 帧, 120Hz",
            scene="jank",
            overall_conclusion="主要由 CPU 降频导致卡顿",
            root_causes=[
                RootCauseItem(
                    tag="cpu_throttle",
                    severity="HIGH",
                    qualitative="CPU 降频",
                    evidence="cpu_freq",
                    reasoning="温控触发",
                ),
            ],
            detailed_report="## 详细分析\n降频发生在第 5s...",
        )
        self.assertEqual(len(ao.root_causes), 1)
        self.assertEqual(ao.scene, "jank")

    def test_empty_root_causes(self):
        ao = AnalysisOutput(
            user_intent_summary="测试",
            trace_info="",
            scene="general",
            overall_conclusion="未发现明显问题",
        )
        self.assertEqual(ao.root_causes, [])
        self.assertEqual(ao.detailed_report, "")

    def test_model_dump_roundtrip(self):
        ao = AnalysisOutput(
            user_intent_summary="测试",
            trace_info="info",
            scene="jank",
            overall_conclusion="结论",
            root_causes=[
                RootCauseItem(
                    tag="t1", severity="HIGH", qualitative="q",
                    evidence="e", reasoning="r",
                ),
            ],
        )
        d = ao.model_dump()
        ao2 = AnalysisOutput(**d)
        self.assertEqual(ao2.root_causes[0].tag, "t1")


# ================================================================
# pa_learnings DB (T003-T004)
# ================================================================


class TestPaLearningsDB(unittest.TestCase):
    """pa_learnings 表创建和 insert_learning。"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_table_exists(self):
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pa_learnings'"
        )
        self.assertIsNotNone(cursor.fetchone())

    def test_insert_learning(self):
        row_id = insert_learning(
            conn=self.conn,
            task_id="task-001",
            trace_id="trace-abc",
            scene="jank",
            root_cause_tags="cpu_throttle",
            insight="[HIGH] CPU 降频导致卡顿",
            device_model="TB522FU",
            process_name="com.test.app",
            key_metrics='{"freq_mhz": 1200}',
            confidence=0.8,
        )
        self.assertGreater(row_id, 0)

        cursor = self.conn.execute(
            "SELECT * FROM pa_learnings WHERE id = ?", (row_id,)
        )
        row = cursor.fetchone()
        self.assertEqual(row["scene"], "jank")
        self.assertEqual(row["device_model"], "TB522FU")
        self.assertEqual(row["confidence"], 0.8)
        self.assertEqual(row["archived"], 0)
        self.assertEqual(row["promoted"], 0)
        self.assertEqual(row["hit_count"], 0)

    def test_insert_without_optional_fields(self):
        row_id = insert_learning(
            conn=self.conn,
            task_id="task-002",
            trace_id="trace-def",
            scene="anr",
            root_cause_tags="binder_timeout",
            insight="Binder 调用超时",
        )
        cursor = self.conn.execute(
            "SELECT device_model, process_name, key_metrics FROM pa_learnings WHERE id = ?",
            (row_id,),
        )
        row = cursor.fetchone()
        self.assertIsNone(row["device_model"])
        self.assertIsNone(row["process_name"])

    def test_multiple_inserts(self):
        for i in range(5):
            insert_learning(
                conn=self.conn,
                task_id=f"task-{i}",
                trace_id=f"trace-{i}",
                scene="jank",
                root_cause_tags=f"tag_{i}",
                insight=f"insight_{i}",
            )
        cursor = self.conn.execute("SELECT COUNT(*) FROM pa_learnings")
        self.assertEqual(cursor.fetchone()[0], 5)


# ================================================================
# _fallback_output (T006)
# ================================================================


class TestFallbackOutput(unittest.TestCase):
    """_fallback_output 降级输出。"""

    def _make_orchestrator(self):
        llm = MagicMock()
        pa_svc = MagicMock()
        pa_svc._db_manager = None
        return AnalysisOrchestrator(llm, pa_svc)

    def test_basic_fallback(self):
        orch = self._make_orchestrator()
        ao = orch._fallback_output("原始文本输出", "jank")
        self.assertIsInstance(ao, AnalysisOutput)
        self.assertEqual(ao.root_causes, [])
        self.assertEqual(ao.scene, "jank")
        self.assertIn("结构化解析失败", ao.user_intent_summary)
        self.assertEqual(ao.detailed_report, "原始文本输出")

    def test_empty_text_fallback(self):
        orch = self._make_orchestrator()
        ao = orch._fallback_output("", "general")
        self.assertIn("未生成结论", ao.overall_conclusion)

    def test_long_text_truncation(self):
        orch = self._make_orchestrator()
        long_text = "A" * 5000
        ao = orch._fallback_output(long_text, "general")
        self.assertEqual(len(ao.overall_conclusion), 2000)
        self.assertEqual(len(ao.detailed_report), 5000)


# ================================================================
# _extract_single_learning (T009)
# ================================================================


class TestExtractLearning(unittest.TestCase):
    """经验提取逻辑。"""

    def test_extract_single(self):
        rc = RootCauseItem(
            tag="cpu_throttle",
            severity="HIGH",
            qualitative="CPU 频率被限制",
            quantitative={"freq_mhz": 1200},
            evidence="cpu_freq 数据",
            reasoning="温控触发降频",
            suggestion="优化功耗",
        )
        ao = AnalysisOutput(
            user_intent_summary="测试",
            trace_info="",
            scene="jank",
            overall_conclusion="结论",
        )
        result = AnalysisOrchestrator._extract_single_learning(rc, ao)
        self.assertEqual(result["root_cause_tags"], "cpu_throttle")
        self.assertIn("HIGH", result["insight"])
        self.assertIn("CPU 频率被限制", result["insight"])
        self.assertIn("freq_mhz", result["key_metrics"])

    def test_extract_without_quantitative(self):
        rc = RootCauseItem(
            tag="gc_pause",
            severity="WARNING",
            qualitative="GC 暂停",
            evidence="日志",
            reasoning="频繁分配",
        )
        ao = AnalysisOutput(
            user_intent_summary="", trace_info="",
            scene="general", overall_conclusion="",
        )
        result = AnalysisOrchestrator._extract_single_learning(rc, ao)
        self.assertEqual(result["key_metrics"], "")


# ================================================================
# _calc_initial_confidence (T010)
# ================================================================


class TestCalcConfidence(unittest.TestCase):
    """置信度计算。"""

    def test_critical_with_evidence(self):
        rcs = [
            RootCauseItem(
                tag="t1", severity="CRITICAL", qualitative="q",
                evidence="有证据", reasoning="r",
            ),
        ]
        conf = AnalysisOrchestrator._calc_initial_confidence(rcs)
        self.assertEqual(conf, 1.0)

    def test_info_without_evidence(self):
        rcs = [
            RootCauseItem(
                tag="t1", severity="INFO", qualitative="q",
                evidence="", reasoning="r",
            ),
        ]
        conf = AnalysisOrchestrator._calc_initial_confidence(rcs)
        self.assertEqual(conf, 0.3)

    def test_empty_root_causes(self):
        conf = AnalysisOrchestrator._calc_initial_confidence([])
        self.assertEqual(conf, 0.1)

    def test_high_with_evidence(self):
        rcs = [
            RootCauseItem(
                tag="t1", severity="HIGH", qualitative="q",
                evidence="有", reasoning="r",
            ),
        ]
        conf = AnalysisOrchestrator._calc_initial_confidence(rcs)
        self.assertAlmostEqual(conf, 0.8)


# ================================================================
# _resolve_device_model (T011)
# ================================================================


class TestResolveDeviceModel(unittest.TestCase):
    """设备型号解析。"""

    def test_from_filename(self):
        model = AnalysisOrchestrator._resolve_device_model(
            r"C:\traces\TB522FU_SM8750P_20260402_202006.perfetto-trace"
        )
        self.assertEqual(model, "TB522FU")

    def test_short_prefix_skipped(self):
        model = AnalysisOrchestrator._resolve_device_model(
            r"C:\traces\AB_test.perfetto-trace"
        )
        self.assertIsNone(model)

    def test_numeric_prefix_skipped(self):
        model = AnalysisOrchestrator._resolve_device_model(
            r"C:\traces\12345_test.perfetto-trace"
        )
        self.assertIsNone(model)

    def test_no_underscore(self):
        model = AnalysisOrchestrator._resolve_device_model(
            r"C:\traces\mytrace.perfetto-trace"
        )
        self.assertIsNone(model)

    def test_fallback_to_db(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE pa_analysis_tasks "
            "(trace_path TEXT, device_model TEXT, created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO pa_analysis_tasks VALUES (?, ?, ?)",
            ("custom.trace", "Pixel9", "2026-01-01"),
        )
        conn.commit()
        model = AnalysisOrchestrator._resolve_device_model("custom.trace", conn)
        self.assertEqual(model, "Pixel9")
        conn.close()


# ================================================================
# _check_conclusion_quality 结构化 (T008)
# ================================================================


class TestConclusionQualityStructured(unittest.TestCase):
    """结构化结论质量自检。"""

    def test_good_structured_output(self):
        ao = AnalysisOutput(
            user_intent_summary="分析卡顿",
            trace_info="info",
            scene="jank",
            overall_conclusion="CPU 降频是主要卡顿原因，建议优化功耗管理。",
            root_causes=[
                RootCauseItem(
                    tag="cpu", severity="HIGH", qualitative="q",
                    evidence="有证据", reasoning="r",
                ),
            ],
        )
        warnings = AnalysisOrchestrator._check_conclusion_quality(
            ao.overall_conclusion, ao,
        )
        self.assertEqual(warnings, [])

    def test_missing_evidence_warning(self):
        ao = AnalysisOutput(
            user_intent_summary="测试",
            trace_info="",
            scene="jank",
            overall_conclusion="有结论的",
            root_causes=[
                RootCauseItem(
                    tag="cpu", severity="HIGH", qualitative="q",
                    evidence="", reasoning="r",
                ),
            ],
        )
        warnings = AnalysisOrchestrator._check_conclusion_quality(
            ao.overall_conclusion, ao,
        )
        self.assertTrue(any("evidence" in w for w in warnings))

    def test_short_conclusion_warning(self):
        ao = AnalysisOutput(
            user_intent_summary="测试",
            trace_info="",
            scene="jank",
            overall_conclusion="短",
            root_causes=[
                RootCauseItem(
                    tag="cpu", severity="HIGH", qualitative="q",
                    evidence="e", reasoning="r",
                ),
            ],
        )
        warnings = AnalysisOrchestrator._check_conclusion_quality(
            ao.overall_conclusion, ao,
        )
        self.assertTrue(any("过短" in w for w in warnings))

    def test_fallback_to_text_check(self):
        warnings = AnalysisOrchestrator._check_conclusion_quality("短", None)
        self.assertTrue(any("过短" in w for w in warnings))


# ================================================================
# HTML 报告三区块 (T013-T016)
# ================================================================


class TestStructuredHTMLReport(unittest.TestCase):
    """三区块 HTML 报告生成。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _make_analysis_output(self):
        return AnalysisOutput(
            user_intent_summary="为什么游戏卡顿",
            trace_info="时长 10s, 300 帧, 120Hz, TB522FU",
            scene="jank",
            overall_conclusion="CPU 降频是主因",
            root_causes=[
                RootCauseItem(
                    tag="cpu_throttle",
                    severity="HIGH",
                    qualitative="CPU 频率被限制",
                    quantitative={"max_freq_mhz": 1200},
                    evidence="cpu_freq 数据",
                    reasoning="温控触发",
                    suggestion="优化散热",
                ),
                RootCauseItem(
                    tag="gc_pause",
                    severity="WARNING",
                    qualitative="GC 暂停 50ms",
                    evidence="gc 日志",
                    reasoning="频繁分配",
                ),
            ],
            detailed_report="## CPU 分析\n降频在第 5s 发生\n{{chart:cpu_freq}}\n## GC 分析\n多次 GC pause",
        )

    def test_structured_report_generated(self):
        ao = self._make_analysis_output()
        report = generate_html_report(
            task_id="test-001",
            result_dir=self.tmpdir,
            trace_path=r"C:\traces\test.perfetto-trace",
            scene="jank",
            process_name="com.test.app",
            conclusion=ao.overall_conclusion,
            raw_data={"completion": "llm_complete"},
            analysis_output=ao,
        )
        self.assertTrue(os.path.exists(report.html_path))
        with open(report.html_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn("cpu_throttle", html)
        self.assertIn("gc_pause", html)
        self.assertIn("为什么游戏卡顿", html)
        self.assertIn("CPU 降频是主因", html)
        self.assertIn("根因分析", html)
        self.assertIn("chart-placeholder", html)

    def test_fallback_to_text_report(self):
        report = generate_html_report(
            task_id="test-002",
            result_dir=os.path.join(self.tmpdir, "fallback"),
            trace_path=r"C:\traces\test.perfetto-trace",
            scene="general",
            process_name="",
            conclusion="纯文本结论",
            raw_data={"completion": "engine_fallback"},
            analysis_output=None,
        )
        self.assertTrue(os.path.exists(report.html_path))
        with open(report.html_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn("纯文本结论", html)
        self.assertNotIn("根因分析", html)

    def test_root_causes_in_report_metadata(self):
        ao = self._make_analysis_output()
        report = generate_html_report(
            task_id="test-003",
            result_dir=os.path.join(self.tmpdir, "meta"),
            trace_path="test.trace",
            scene="jank",
            process_name="",
            conclusion="c",
            raw_data={"completion": "llm_complete"},
            analysis_output=ao,
        )
        self.assertEqual(len(report.root_causes), 2)
        self.assertEqual(report.root_causes[0]["tag"], "cpu_throttle")


# ================================================================
# 占位符替换 (T015)
# ================================================================


class TestChartPlaceholders(unittest.TestCase):
    """{{chart:key}} 占位符替换。"""

    def test_single_placeholder(self):
        html = "<p>图表: {{chart:cpu_freq}}</p>"
        result = _replace_chart_placeholders(html)
        self.assertIn("chart-placeholder", result)
        self.assertIn("cpu_freq", result)
        self.assertNotIn("{{chart:", result)

    def test_multiple_placeholders(self):
        html = "{{chart:cpu_freq}} and {{chart:thread_timeline}}"
        result = _replace_chart_placeholders(html)
        self.assertIn("cpu_freq", result)
        self.assertIn("thread_timeline", result)
        self.assertEqual(result.count("chart-placeholder"), 2)

    def test_no_placeholders(self):
        html = "<p>Normal text</p>"
        result = _replace_chart_placeholders(html)
        self.assertEqual(result, html)


# ================================================================
# 经验自动提取集成 (T011-T012)
# ================================================================


class TestExtractAndSaveLearnings(unittest.TestCase):
    """经验自动提取集成测试。"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)

        self.llm = MagicMock()
        self.pa_svc = MagicMock()
        db_mgr = MagicMock()
        db_mgr.conn = self.conn
        self.pa_svc._db_manager = db_mgr
        self.orch = AnalysisOrchestrator(self.llm, self.pa_svc)

    def tearDown(self):
        self.conn.close()

    def test_extracts_on_root_causes(self):
        ao = AnalysisOutput(
            user_intent_summary="测试",
            trace_info="",
            scene="jank",
            overall_conclusion="结论",
            root_causes=[
                RootCauseItem(
                    tag="cpu_throttle", severity="HIGH",
                    qualitative="降频", evidence="数据", reasoning="温控",
                ),
                RootCauseItem(
                    tag="gc_pause", severity="WARNING",
                    qualitative="GC 暂停", evidence="日志", reasoning="分配",
                ),
            ],
        )
        routing = AnalysisRouting(
            scene="jank", process_name="com.test",
        )
        self.orch._extract_and_save_learnings("task-1", "TB522FU_SM8750P.trace", routing, ao)

        cursor = self.conn.execute("SELECT COUNT(*) FROM pa_learnings")
        self.assertEqual(cursor.fetchone()[0], 2)

        cursor = self.conn.execute(
            "SELECT root_cause_tags, confidence FROM pa_learnings ORDER BY id"
        )
        rows = cursor.fetchall()
        self.assertEqual(rows[0]["root_cause_tags"], "cpu_throttle")
        self.assertEqual(rows[1]["root_cause_tags"], "gc_pause")

    def test_skips_on_empty_root_causes(self):
        ao = AnalysisOutput(
            user_intent_summary="", trace_info="",
            scene="general", overall_conclusion="无问题",
        )
        routing = AnalysisRouting(scene="general")
        self.orch._extract_and_save_learnings("task-2", "test.trace", routing, ao)

        cursor = self.conn.execute("SELECT COUNT(*) FROM pa_learnings")
        self.assertEqual(cursor.fetchone()[0], 0)

    def test_skips_on_none_output(self):
        routing = AnalysisRouting(scene="jank")
        self.orch._extract_and_save_learnings("task-3", "test.trace", routing, None)

        cursor = self.conn.execute("SELECT COUNT(*) FROM pa_learnings")
        self.assertEqual(cursor.fetchone()[0], 0)

    def test_silent_degradation_on_db_error(self):
        self.pa_svc._db_manager = None
        ao = AnalysisOutput(
            user_intent_summary="", trace_info="",
            scene="jank", overall_conclusion="c",
            root_causes=[
                RootCauseItem(
                    tag="t", severity="HIGH", qualitative="q",
                    evidence="e", reasoning="r",
                ),
            ],
        )
        routing = AnalysisRouting(scene="jank")
        self.orch._extract_and_save_learnings("task-4", "test.trace", routing, ao)

    def test_device_model_extracted(self):
        ao = AnalysisOutput(
            user_intent_summary="", trace_info="",
            scene="jank", overall_conclusion="c",
            root_causes=[
                RootCauseItem(
                    tag="t", severity="HIGH", qualitative="q",
                    evidence="e", reasoning="r",
                ),
            ],
        )
        routing = AnalysisRouting(scene="jank", process_name="com.app")
        self.orch._extract_and_save_learnings(
            "task-5", r"C:\traces\TB522FU_SM8750P_20260402.trace", routing, ao,
        )
        cursor = self.conn.execute("SELECT device_model FROM pa_learnings")
        row = cursor.fetchone()
        self.assertEqual(row["device_model"], "TB522FU")


if __name__ == "__main__":
    unittest.main()
