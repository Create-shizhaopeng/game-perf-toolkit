# -*- coding: utf-8 -*-
"""G4 Review 增强 — 单元测试。"""

import sqlite3
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from modules.perfetto_analysis.src.agent import (
    AnalysisOutput,
    AnalysisReport,
    ConfidenceAdjustment,
    ReviewResult,
    RootCauseItem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rc(tag: str = "cpu_throttle", severity: str = "HIGH") -> RootCauseItem:
    return RootCauseItem(
        tag=tag,
        severity=severity,
        qualitative="测试定性",
        evidence="测试证据",
        reasoning="测试推理",
    )


def _make_ao(
    scene: str = "jank",
    root_causes: list | None = None,
) -> AnalysisOutput:
    return AnalysisOutput(
        user_intent_summary="测试",
        trace_info="test trace",
        scene=scene,
        overall_conclusion="测试结论",
        root_causes=root_causes or [],
    )


def _make_report(
    task_id: str = "task-1",
    scene: str = "jank",
    root_causes: list | None = None,
) -> AnalysisReport:
    ao = _make_ao(scene=scene, root_causes=root_causes)
    return AnalysisReport(task_id=task_id, analysis_output=ao)


def _create_learnings_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pa_learnings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id         TEXT,
            trace_id        TEXT NOT NULL,
            scene           TEXT NOT NULL,
            device_model    TEXT,
            process_name    TEXT,
            root_cause_tags TEXT NOT NULL,
            insight         TEXT NOT NULL,
            key_metrics     TEXT,
            confidence      REAL DEFAULT 0.5,
            hit_count       INTEGER DEFAULT 0,
            last_used       TEXT,
            created_at      TEXT NOT NULL,
            promoted        INTEGER DEFAULT 0,
            archived        INTEGER DEFAULT 0
        )
    """)
    conn.commit()


def _insert_learning(
    conn: sqlite3.Connection,
    task_id: str = "task-1",
    tags: str = "cpu_throttle",
    confidence: float = 0.5,
    archived: int = 0,
) -> int:
    cursor = conn.execute(
        """INSERT INTO pa_learnings
           (task_id, trace_id, scene, root_cause_tags, insight,
            confidence, created_at, archived)
           VALUES (?, 'trace-1', 'jank', ?, '测试', ?, ?, ?)""",
        (task_id, tags, confidence, datetime.now().isoformat(), archived),
    )
    conn.commit()
    return cursor.lastrowid


# ===========================================================================
# Model Tests
# ===========================================================================


class TestConfidenceAdjustmentModel(unittest.TestCase):
    def test_basic_creation(self):
        adj = ConfidenceAdjustment(
            trace_index=0, tag="cpu_throttle", adjustment=0.1,
        )
        self.assertEqual(adj.trace_index, 0)
        self.assertEqual(adj.tag, "cpu_throttle")
        self.assertAlmostEqual(adj.adjustment, 0.1)
        self.assertEqual(adj.reason, "")

    def test_with_reason(self):
        adj = ConfidenceAdjustment(
            trace_index=1, tag="binder_ipc", adjustment=-0.2,
            reason="证据不足",
        )
        self.assertEqual(adj.reason, "证据不足")


class TestReviewResultModel(unittest.TestCase):
    def test_defaults(self):
        rr = ReviewResult(overall_assessment="良好")
        self.assertEqual(rr.cross_consistency, "")
        self.assertEqual(rr.common_patterns, [])
        self.assertEqual(rr.contradictions, [])
        self.assertEqual(rr.confidence_adjustments, [])
        self.assertEqual(rr.overall_assessment, "良好")

    def test_full_creation(self):
        rr = ReviewResult(
            cross_consistency="一致",
            common_patterns=["CPU 降频", "Binder 超时"],
            contradictions=["Trace 1 和 Trace 2 的 GC 结论矛盾"],
            confidence_adjustments=[
                ConfidenceAdjustment(
                    trace_index=0, tag="cpu_throttle", adjustment=0.1,
                ),
            ],
            overall_assessment="整体分析质量高",
        )
        self.assertEqual(len(rr.common_patterns), 2)
        self.assertEqual(len(rr.confidence_adjustments), 1)


class TestAnalysisReportWithOutput(unittest.TestCase):
    def test_analysis_output_field(self):
        ao = _make_ao()
        report = AnalysisReport(task_id="t1", analysis_output=ao)
        self.assertIsNotNone(report.analysis_output)
        self.assertEqual(report.analysis_output.scene, "jank")

    def test_analysis_output_default_none(self):
        report = AnalysisReport(task_id="t1")
        self.assertIsNone(report.analysis_output)


# ===========================================================================
# _should_review Tests
# ===========================================================================


class TestShouldReview(unittest.TestCase):
    def _call(self, reports):
        from modules.perfetto_analysis.src.agent.orchestrator import (
            AnalysisOrchestrator,
        )
        return AnalysisOrchestrator._should_review(reports)

    def test_empty_reports(self):
        should, rtype = self._call([])
        self.assertFalse(should)
        self.assertEqual(rtype, "")

    def test_single_no_analysis_output(self):
        report = AnalysisReport(task_id="t1")
        should, rtype = self._call([report])
        self.assertFalse(should)

    def test_single_few_root_causes_high_conf(self):
        report = _make_report(
            root_causes=[_make_rc(severity="CRITICAL")],
        )
        should, rtype = self._call([report])
        self.assertFalse(should)

    def test_single_many_root_causes_triggers_self_check(self):
        report = _make_report(
            root_causes=[
                _make_rc("tag1"), _make_rc("tag2"), _make_rc("tag3"),
            ],
        )
        should, rtype = self._call([report])
        self.assertTrue(should)
        self.assertEqual(rtype, "self_check")

    def test_single_low_confidence_triggers_self_check(self):
        report = _make_report(
            root_causes=[_make_rc(severity="INFO")],
        )
        should, rtype = self._call([report])
        self.assertTrue(should)
        self.assertEqual(rtype, "self_check")

    def test_batch_same_scene_triggers_cross_compare(self):
        reports = [
            _make_report(task_id="t1", scene="jank", root_causes=[_make_rc()]),
            _make_report(task_id="t2", scene="jank", root_causes=[_make_rc()]),
        ]
        should, rtype = self._call(reports)
        self.assertTrue(should)
        self.assertEqual(rtype, "cross_compare")

    def test_batch_diff_scene_high_conf_no_review(self):
        reports = [
            _make_report(task_id="t1", scene="jank", root_causes=[_make_rc(severity="CRITICAL")]),
            _make_report(task_id="t2", scene="cpu", root_causes=[_make_rc(severity="CRITICAL")]),
        ]
        should, rtype = self._call(reports)
        self.assertFalse(should)

    def test_batch_diff_scene_low_conf_triggers_individual(self):
        reports = [
            _make_report(task_id="t1", scene="jank", root_causes=[_make_rc(severity="INFO")]),
            _make_report(task_id="t2", scene="cpu", root_causes=[_make_rc(severity="CRITICAL")]),
        ]
        should, rtype = self._call(reports)
        self.assertTrue(should)
        self.assertEqual(rtype, "individual_review")

    def test_single_no_root_causes(self):
        report = _make_report(root_causes=[])
        should, rtype = self._call([report])
        self.assertFalse(should)


# ===========================================================================
# _apply_confidence_calibration Tests
# ===========================================================================


class TestApplyConfidenceCalibration(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.Connection(":memory:")
        _create_learnings_table(self.conn)

        self.mock_service = MagicMock()
        self.mock_service._db_manager.conn = self.conn

    def _make_orchestrator(self):
        from modules.perfetto_analysis.src.agent.orchestrator import (
            AnalysisOrchestrator,
        )
        orch = AnalysisOrchestrator.__new__(AnalysisOrchestrator)
        orch._pa_service = self.mock_service
        return orch

    def test_positive_adjustment(self):
        row_id = _insert_learning(self.conn, task_id="t1", tags="cpu_throttle", confidence=0.5)

        orch = self._make_orchestrator()
        reports = [_make_report(task_id="t1")]
        review_result = ReviewResult(
            overall_assessment="good",
            confidence_adjustments=[
                ConfidenceAdjustment(trace_index=0, tag="cpu_throttle", adjustment=0.2),
            ],
        )
        orch._apply_confidence_calibration(reports, review_result)

        row = self.conn.execute(
            "SELECT confidence FROM pa_learnings WHERE id = ?", (row_id,)
        ).fetchone()
        self.assertAlmostEqual(row[0], 0.7, places=5)

    def test_negative_adjustment(self):
        row_id = _insert_learning(self.conn, task_id="t1", tags="cpu_throttle", confidence=0.5)

        orch = self._make_orchestrator()
        reports = [_make_report(task_id="t1")]
        review_result = ReviewResult(
            overall_assessment="needs work",
            confidence_adjustments=[
                ConfidenceAdjustment(trace_index=0, tag="cpu_throttle", adjustment=-0.2),
            ],
        )
        orch._apply_confidence_calibration(reports, review_result)

        row = self.conn.execute(
            "SELECT confidence FROM pa_learnings WHERE id = ?", (row_id,)
        ).fetchone()
        self.assertAlmostEqual(row[0], 0.3, places=5)

    def test_clamp_upper(self):
        row_id = _insert_learning(self.conn, task_id="t1", tags="cpu_throttle", confidence=0.9)

        orch = self._make_orchestrator()
        reports = [_make_report(task_id="t1")]
        review_result = ReviewResult(
            overall_assessment="good",
            confidence_adjustments=[
                ConfidenceAdjustment(trace_index=0, tag="cpu_throttle", adjustment=0.3),
            ],
        )
        orch._apply_confidence_calibration(reports, review_result)

        row = self.conn.execute(
            "SELECT confidence FROM pa_learnings WHERE id = ?", (row_id,)
        ).fetchone()
        self.assertAlmostEqual(row[0], 1.0, places=5)

    def test_clamp_lower(self):
        row_id = _insert_learning(self.conn, task_id="t1", tags="cpu_throttle", confidence=0.1)

        orch = self._make_orchestrator()
        reports = [_make_report(task_id="t1")]
        review_result = ReviewResult(
            overall_assessment="bad",
            confidence_adjustments=[
                ConfidenceAdjustment(trace_index=0, tag="cpu_throttle", adjustment=-0.3),
            ],
        )
        orch._apply_confidence_calibration(reports, review_result)

        row = self.conn.execute(
            "SELECT confidence FROM pa_learnings WHERE id = ?", (row_id,)
        ).fetchone()
        self.assertGreaterEqual(row[0], 0.0)

    def test_trace_index_out_of_bounds(self):
        _insert_learning(self.conn, task_id="t1", tags="cpu_throttle", confidence=0.5)

        orch = self._make_orchestrator()
        reports = [_make_report(task_id="t1")]
        review_result = ReviewResult(
            overall_assessment="good",
            confidence_adjustments=[
                ConfidenceAdjustment(trace_index=5, tag="cpu_throttle", adjustment=0.1),
            ],
        )
        orch._apply_confidence_calibration(reports, review_result)

        row = self.conn.execute(
            "SELECT confidence FROM pa_learnings WHERE id = 1",
        ).fetchone()
        self.assertAlmostEqual(row[0], 0.5, places=5)

    def test_tag_no_match(self):
        _insert_learning(self.conn, task_id="t1", tags="cpu_throttle", confidence=0.5)

        orch = self._make_orchestrator()
        reports = [_make_report(task_id="t1")]
        review_result = ReviewResult(
            overall_assessment="good",
            confidence_adjustments=[
                ConfidenceAdjustment(trace_index=0, tag="nonexistent_tag", adjustment=0.2),
            ],
        )
        orch._apply_confidence_calibration(reports, review_result)

        row = self.conn.execute(
            "SELECT confidence FROM pa_learnings WHERE id = 1",
        ).fetchone()
        self.assertAlmostEqual(row[0], 0.5, places=5)

    def test_tag_partial_match(self):
        row_id = _insert_learning(
            self.conn, task_id="t1", tags="cpu_throttle,binder_ipc", confidence=0.5,
        )

        orch = self._make_orchestrator()
        reports = [_make_report(task_id="t1")]
        review_result = ReviewResult(
            overall_assessment="good",
            confidence_adjustments=[
                ConfidenceAdjustment(trace_index=0, tag="binder_ipc", adjustment=0.1),
            ],
        )
        orch._apply_confidence_calibration(reports, review_result)

        row = self.conn.execute(
            "SELECT confidence FROM pa_learnings WHERE id = ?", (row_id,)
        ).fetchone()
        self.assertAlmostEqual(row[0], 0.6, places=5)

    def test_adjustment_clamped_to_range(self):
        """adjustment > 0.3 should be clamped to 0.3."""
        row_id = _insert_learning(self.conn, task_id="t1", tags="cpu_throttle", confidence=0.5)

        orch = self._make_orchestrator()
        reports = [_make_report(task_id="t1")]
        review_result = ReviewResult(
            overall_assessment="good",
            confidence_adjustments=[
                ConfidenceAdjustment(trace_index=0, tag="cpu_throttle", adjustment=0.9),
            ],
        )
        orch._apply_confidence_calibration(reports, review_result)

        row = self.conn.execute(
            "SELECT confidence FROM pa_learnings WHERE id = ?", (row_id,)
        ).fetchone()
        self.assertAlmostEqual(row[0], 0.8, places=5)

    def test_archived_learning_not_updated(self):
        _insert_learning(
            self.conn, task_id="t1", tags="cpu_throttle",
            confidence=0.5, archived=1,
        )

        orch = self._make_orchestrator()
        reports = [_make_report(task_id="t1")]
        review_result = ReviewResult(
            overall_assessment="good",
            confidence_adjustments=[
                ConfidenceAdjustment(trace_index=0, tag="cpu_throttle", adjustment=0.2),
            ],
        )
        orch._apply_confidence_calibration(reports, review_result)

        row = self.conn.execute(
            "SELECT confidence FROM pa_learnings WHERE id = 1",
        ).fetchone()
        self.assertAlmostEqual(row[0], 0.5, places=5)

    def test_empty_adjustments(self):
        _insert_learning(self.conn, task_id="t1", tags="cpu_throttle", confidence=0.5)

        orch = self._make_orchestrator()
        reports = [_make_report(task_id="t1")]
        review_result = ReviewResult(
            overall_assessment="good",
            confidence_adjustments=[],
        )
        orch._apply_confidence_calibration(reports, review_result)

        row = self.conn.execute(
            "SELECT confidence FROM pa_learnings WHERE id = 1",
        ).fetchone()
        self.assertAlmostEqual(row[0], 0.5, places=5)


# ===========================================================================
# create_review_agent Tests
# ===========================================================================


class TestCreateReviewAgent(unittest.TestCase):
    @patch("pydantic_ai.Agent")
    def test_default_cross_compare(self, mock_agent_cls):
        from modules.perfetto_analysis.src.agent.agents import create_review_agent
        create_review_agent("test-model")
        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args
        self.assertEqual(call_kwargs[1]["output_type"], ReviewResult)
        self.assertIn("交叉评审", call_kwargs[1]["instructions"])

    @patch("pydantic_ai.Agent")
    def test_self_check_mode(self, mock_agent_cls):
        from modules.perfetto_analysis.src.agent.agents import create_review_agent
        create_review_agent("test-model", review_type="self_check")
        call_kwargs = mock_agent_cls.call_args
        self.assertIn("质量自检", call_kwargs[1]["instructions"])

    @patch("pydantic_ai.Agent")
    def test_individual_review_mode(self, mock_agent_cls):
        from modules.perfetto_analysis.src.agent.agents import create_review_agent
        create_review_agent("test-model", review_type="individual_review")
        call_kwargs = mock_agent_cls.call_args
        self.assertIn("独立评审", call_kwargs[1]["instructions"])


# ===========================================================================
# _run_review Integration Tests
# ===========================================================================


class TestRunReviewIntegration(unittest.TestCase):
    def _make_orchestrator(self):
        from modules.perfetto_analysis.src.agent.orchestrator import (
            AnalysisOrchestrator,
        )
        conn = sqlite3.Connection(":memory:")
        _create_learnings_table(conn)

        mock_service = MagicMock()
        mock_service._db_manager.conn = conn

        orch = AnalysisOrchestrator.__new__(AnalysisOrchestrator)
        orch._pa_service = mock_service
        orch._llm_manager = MagicMock()
        orch._conn = conn
        return orch, conn

    def test_run_review_no_analysis_output(self):
        import asyncio
        orch, _ = self._make_orchestrator()
        reports = [AnalysisReport(task_id="t1")]

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                orch._run_review(reports, None, "cross_compare")
            )
            self.assertIsNone(result)
        finally:
            loop.close()

    def test_run_review_import_error_degrades(self):
        import asyncio
        orch, _ = self._make_orchestrator()
        reports = [_make_report(root_causes=[_make_rc()])]

        with patch(
            "modules.perfetto_analysis.src.agent.orchestrator.AnalysisOrchestrator._get_model",
            side_effect=ImportError("no pydantic_ai"),
        ):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    orch._run_review(reports, None, "cross_compare")
                )
                self.assertIsNone(result)
            finally:
                loop.close()


if __name__ == "__main__":
    unittest.main()
