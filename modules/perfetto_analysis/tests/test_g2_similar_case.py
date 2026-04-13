# -*- coding: utf-8 -*-
"""G2 相似案例注入测试。

覆盖功能点：
- L1 精确匹配 / 标签交叉匹配
- L2 降级（无 embedder）
- issue_tags 提取
- hit_count 条件更新
- 格式化注入区块
- 编排器集成
"""

import sqlite3
import unittest
from datetime import datetime
from unittest.mock import MagicMock

from modules.perfetto_analysis.src.agent import (
    AnalysisOutput,
    AnalysisRouting,
    RootCauseItem,
)
from modules.perfetto_analysis.src.agent.learnings_search import LearningsSearcher
from modules.perfetto_analysis.src.agent.orchestrator import AnalysisOrchestrator
from modules.perfetto_analysis.src.engine.storage import (
    init_db,
    insert_learning,
)


def _seed_learnings(conn: sqlite3.Connection) -> list[int]:
    """插入测试数据，返回 id 列表。"""
    ids = []
    data = [
        ("jank", "com.test.app", "cpu_throttle", "[HIGH] CPU 降频", '{"freq": 1200}', 0.8),
        ("jank", "com.test.app", "gc_pause", "[WARNING] GC 暂停", '{"pause_ms": 50}', 0.6),
        ("jank", "com.other.app", "cpu_throttle,thermal", "[HIGH] CPU 降频+温控", '{}', 0.7),
        ("anr", "com.test.app", "binder_timeout", "[CRITICAL] Binder 超时", '{}', 0.9),
        ("memory", "com.test.app", "gc_alloc", "[WARNING] 频繁分配", '{}', 0.5),
    ]
    for scene, proc, tags, insight, metrics, conf in data:
        rid = insert_learning(
            conn=conn,
            task_id="seed",
            trace_id="seed_trace",
            scene=scene,
            root_cause_tags=tags,
            insight=insight,
            device_model="TB522FU",
            process_name=proc,
            key_metrics=metrics,
            confidence=conf,
        )
        ids.append(rid)
    return ids


class TestL1ExactMatch(unittest.TestCase):
    """L1 精确匹配。"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        self.ids = _seed_learnings(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_exact_match_same_scene_process(self):
        searcher = LearningsSearcher(self.conn)
        results = searcher._l1_exact_match("jank", "com.test.app", limit=2)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["scene"] == "jank" for r in results))
        self.assertTrue(all(r["process_name"] == "com.test.app" for r in results))

    def test_exact_match_no_results(self):
        searcher = LearningsSearcher(self.conn)
        results = searcher._l1_exact_match("startup", "com.nonexist", limit=2)
        self.assertEqual(len(results), 0)

    def test_exact_match_ordered_by_confidence(self):
        searcher = LearningsSearcher(self.conn)
        results = searcher._l1_exact_match("jank", "com.test.app", limit=2)
        if len(results) >= 2:
            self.assertGreaterEqual(results[0]["confidence"], results[1]["confidence"])


class TestL1TagCrossMatch(unittest.TestCase):
    """L1 标签交叉匹配。"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        self.ids = _seed_learnings(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_tag_cross_match(self):
        searcher = LearningsSearcher(self.conn)
        results = searcher._l1_tag_cross_match(
            "jank", ["cpu_throttle"], exclude_ids=[self.ids[0], self.ids[1]], limit=1,
        )
        self.assertEqual(len(results), 1)
        self.assertIn("cpu_throttle", results[0]["root_cause_tags"])

    def test_tag_cross_match_no_tags(self):
        searcher = LearningsSearcher(self.conn)
        results = searcher._l1_tag_cross_match(
            "jank", [], exclude_ids=[self.ids[0]], limit=2,
        )
        self.assertGreater(len(results), 0)
        self.assertTrue(all(r["scene"] == "jank" for r in results))

    def test_excludes_already_found(self):
        searcher = LearningsSearcher(self.conn)
        results = searcher._l1_tag_cross_match(
            "jank", ["cpu_throttle"], exclude_ids=self.ids[:3], limit=5,
        )
        found_ids = {r["id"] for r in results}
        for eid in self.ids[:3]:
            self.assertNotIn(eid, found_ids)


class TestSearchMainFlow(unittest.TestCase):
    """search 主流程。"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        self.ids = _seed_learnings(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_search_returns_limit(self):
        searcher = LearningsSearcher(self.conn)
        results = searcher.search("jank", "com.test.app", limit=3)
        self.assertLessEqual(len(results), 3)
        self.assertGreater(len(results), 0)

    def test_search_empty_table(self):
        empty_conn = sqlite3.connect(":memory:")
        empty_conn.row_factory = sqlite3.Row
        init_db(empty_conn)
        searcher = LearningsSearcher(empty_conn)
        results = searcher.search("jank", "com.test.app")
        self.assertEqual(len(results), 0)
        empty_conn.close()

    def test_search_no_embedder_skips_l2(self):
        searcher = LearningsSearcher(self.conn, embedder=None)
        results = searcher.search("startup", "com.new.app")
        for r in results:
            self.assertNotEqual(r.get("retrieval_method"), "semantic")

    def test_search_unique_ids(self):
        searcher = LearningsSearcher(self.conn)
        results = searcher.search("jank", "com.test.app", limit=3)
        ids = [r["id"] for r in results]
        self.assertEqual(len(ids), len(set(ids)))


class TestHitCountUpdate(unittest.TestCase):
    """hit_count 条件更新。"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        self.ids = _seed_learnings(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_update_on_matching_tags(self):
        searcher = LearningsSearcher(self.conn)
        updated = searcher.update_hit_counts(
            [self.ids[0]], {"cpu_throttle"},
        )
        self.assertEqual(updated, 1)
        row = self.conn.execute(
            "SELECT hit_count, last_used FROM pa_learnings WHERE id = ?",
            (self.ids[0],),
        ).fetchone()
        self.assertEqual(row["hit_count"], 1)
        self.assertIsNotNone(row["last_used"])

    def test_no_update_on_non_matching_tags(self):
        searcher = LearningsSearcher(self.conn)
        updated = searcher.update_hit_counts(
            [self.ids[0]], {"io_block"},
        )
        self.assertEqual(updated, 0)
        row = self.conn.execute(
            "SELECT hit_count FROM pa_learnings WHERE id = ?",
            (self.ids[0],),
        ).fetchone()
        self.assertEqual(row["hit_count"], 0)

    def test_empty_inputs(self):
        searcher = LearningsSearcher(self.conn)
        self.assertEqual(searcher.update_hit_counts([], {"cpu"}), 0)
        self.assertEqual(searcher.update_hit_counts([1], set()), 0)

    def test_multiple_ids_partial_match(self):
        searcher = LearningsSearcher(self.conn)
        updated = searcher.update_hit_counts(
            [self.ids[0], self.ids[3]], {"cpu_throttle"},
        )
        self.assertEqual(updated, 1)


class TestExtractIssueTags(unittest.TestCase):
    """issue_tags 从预取结果提取。"""

    def test_from_jank_frames(self):
        ctx = {
            "jank_frames": {
                "jank_records": [
                    {"jank_type": "cpu_throttle", "jank_num": 3},
                    {"jank_type": "gc_pause", "jank_num": 1},
                ],
            },
        }
        tags = AnalysisOrchestrator._extract_issue_tags_from_prefetch(ctx)
        self.assertIn("cpu_throttle", tags)
        self.assertIn("gc_pause", tags)

    def test_from_issues_field(self):
        ctx = {
            "thread_analysis": {
                "issues": [
                    {"type": "binder_timeout"},
                    {"type": "lock_contention"},
                ],
            },
        }
        tags = AnalysisOrchestrator._extract_issue_tags_from_prefetch(ctx)
        self.assertIn("binder_timeout", tags)
        self.assertIn("lock_contention", tags)

    def test_empty_context(self):
        tags = AnalysisOrchestrator._extract_issue_tags_from_prefetch({})
        self.assertEqual(tags, [])

    def test_no_duplicate_tags(self):
        ctx = {
            "jank_frames": {
                "jank_records": [
                    {"jank_type": "cpu_throttle"},
                    {"jank_type": "cpu_throttle"},
                ],
            },
        }
        tags = AnalysisOrchestrator._extract_issue_tags_from_prefetch(ctx)
        self.assertEqual(tags.count("cpu_throttle"), 1)


class TestFormatLearningsBlock(unittest.TestCase):
    """格式化注入区块。"""

    def test_format_with_results(self):
        learnings = [
            {
                "id": 1, "scene": "jank", "process_name": "com.test",
                "root_cause_tags": "cpu_throttle",
                "insight": "CPU 降频", "key_metrics": '{"freq": 1200}',
                "confidence": 0.8, "hit_count": 5,
            },
        ]
        block = AnalysisOrchestrator._format_learnings_block(learnings)
        self.assertIn("历史分析参考", block)
        self.assertIn("cpu_throttle", block)
        self.assertIn("0.8", block)
        self.assertIn("命中 5 次", block)

    def test_format_empty(self):
        block = AnalysisOrchestrator._format_learnings_block([])
        self.assertEqual(block, "")

    def test_format_semantic_label(self):
        learnings = [
            {
                "id": 1, "scene": "jank", "process_name": "com.test",
                "root_cause_tags": "cpu",
                "insight": "test", "confidence": 0.5,
                "hit_count": 0, "retrieval_method": "semantic",
            },
        ]
        block = AnalysisOrchestrator._format_learnings_block(learnings)
        self.assertIn("语义召回", block)

    def test_long_insight_truncated(self):
        learnings = [
            {
                "id": 1, "scene": "jank", "process_name": "",
                "root_cause_tags": "t",
                "insight": "A" * 1000, "confidence": 0.5,
                "hit_count": 0,
            },
        ]
        block = AnalysisOrchestrator._format_learnings_block(learnings)
        self.assertIn("...", block)
        self.assertLess(len(block), 1500)


class TestOrchestratorIntegration(unittest.TestCase):
    """编排器集成：案例检索 + hit_count 更新。"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        self.ids = _seed_learnings(self.conn)

        self.llm = MagicMock()
        self.pa_svc = MagicMock()
        db_mgr = MagicMock()
        db_mgr.conn = self.conn
        self.pa_svc._db_manager = db_mgr
        self.orch = AnalysisOrchestrator(self.llm, self.pa_svc)

    def tearDown(self):
        self.conn.close()

    def test_search_similar_cases_returns_ids(self):
        routing = AnalysisRouting(scene="jank", process_name="com.test.app")
        ids = self.orch._search_similar_cases(routing, {}, None)
        self.assertGreater(len(ids), 0)

    def test_search_similar_cases_injects_context(self):
        routing = AnalysisRouting(scene="jank", process_name="com.test.app")
        ctx: dict = {}
        self.orch._search_similar_cases(routing, ctx, None)
        self.assertIn("historical_learnings", ctx)

    def test_search_similar_cases_no_db(self):
        self.pa_svc._db_manager = None
        routing = AnalysisRouting(scene="jank", process_name="com.test.app")
        ids = self.orch._search_similar_cases(routing, {}, None)
        self.assertEqual(ids, [])

    def test_update_injected_hit_counts(self):
        ao = AnalysisOutput(
            user_intent_summary="", trace_info="",
            scene="jank", overall_conclusion="c",
            root_causes=[
                RootCauseItem(
                    tag="cpu_throttle", severity="HIGH",
                    qualitative="q", evidence="e", reasoning="r",
                ),
            ],
        )
        self.orch._update_injected_hit_counts([self.ids[0]], ao)
        row = self.conn.execute(
            "SELECT hit_count FROM pa_learnings WHERE id = ?",
            (self.ids[0],),
        ).fetchone()
        self.assertEqual(row["hit_count"], 1)

    def test_update_injected_no_match(self):
        ao = AnalysisOutput(
            user_intent_summary="", trace_info="",
            scene="jank", overall_conclusion="c",
            root_causes=[
                RootCauseItem(
                    tag="io_block", severity="HIGH",
                    qualitative="q", evidence="e", reasoning="r",
                ),
            ],
        )
        self.orch._update_injected_hit_counts([self.ids[0]], ao)
        row = self.conn.execute(
            "SELECT hit_count FROM pa_learnings WHERE id = ?",
            (self.ids[0],),
        ).fetchone()
        self.assertEqual(row["hit_count"], 0)

    def test_update_injected_none_output(self):
        self.orch._update_injected_hit_counts([self.ids[0]], None)


if __name__ == "__main__":
    unittest.main()
