# -*- coding: utf-8 -*-
"""G3 经验淘汰与晋升 — 单元测试。"""
from __future__ import annotations

import asyncio
import math
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mem_conn():
    """带 pa_learnings + pa_telemetry 表的内存 DB。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE pa_learnings (
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
    conn.execute("""
        CREATE TABLE pa_telemetry (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id                 TEXT,
            trace_id                TEXT,
            scene                   TEXT,
            model_name              TEXT,
            tool_call_count         INTEGER,
            tool_calls_detail       TEXT,
            total_prompt_tokens     INTEGER,
            total_completion_tokens INTEGER,
            conclusion_quality      TEXT,
            elapsed_sec             REAL,
            created_at              TEXT NOT NULL
        )
    """)
    conn.commit()
    yield conn
    conn.close()


def _insert_learning(conn, **kwargs):
    defaults = {
        "task_id": "t1", "trace_id": "tr1", "scene": "jank",
        "root_cause_tags": "cpu_throttle", "insight": "test insight",
        "confidence": 0.5, "hit_count": 0, "promoted": 0, "archived": 0,
        "created_at": (datetime.now() - timedelta(days=30)).isoformat(),
        "last_used": None, "process_name": "com.test", "device_model": None,
        "key_metrics": None,
    }
    defaults.update(kwargs)
    cursor = conn.execute(
        """INSERT INTO pa_learnings
           (task_id, trace_id, scene, root_cause_tags, insight,
            confidence, hit_count, promoted, archived, created_at,
            last_used, process_name, device_model, key_metrics)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (defaults["task_id"], defaults["trace_id"], defaults["scene"],
         defaults["root_cause_tags"], defaults["insight"],
         defaults["confidence"], defaults["hit_count"],
         defaults["promoted"], defaults["archived"],
         defaults["created_at"], defaults["last_used"],
         defaults["process_name"], defaults["device_model"],
         defaults["key_metrics"]),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_telemetry_rows(conn, count):
    for i in range(count):
        conn.execute(
            "INSERT INTO pa_telemetry (task_id, trace_id, scene, created_at) VALUES (?,?,?,?)",
            (f"t{i}", f"tr{i}", "jank", datetime.now().isoformat()),
        )
    conn.commit()


# ===========================================================================
# memory_score 测试
# ===========================================================================

class TestMemoryScore:
    def test_zero_hit_count(self):
        from modules.perfetto_analysis.src.agent.learnings_manager import memory_score
        r = memory_score({"confidence": 0.8, "hit_count": 0, "created_at": datetime.now().isoformat()})
        assert r == 0.0

    def test_recent_high_hit(self):
        from modules.perfetto_analysis.src.agent.learnings_manager import memory_score
        now = datetime.now()
        r = memory_score({
            "confidence": 0.9, "hit_count": 10,
            "last_used": now.isoformat(),
        }, now)
        expected = 1.0 * 0.9 * math.log(11)
        assert abs(r - expected) < 0.01

    def test_old_record_decays(self):
        from modules.perfetto_analysis.src.agent.learnings_manager import memory_score
        now = datetime.now()
        old = (now - timedelta(days=30)).isoformat()
        r = memory_score({"confidence": 0.9, "hit_count": 5, "created_at": old}, now)
        recent = memory_score({
            "confidence": 0.9, "hit_count": 5, "last_used": now.isoformat(),
        }, now)
        assert r < recent

    def test_no_dates_returns_zero(self):
        from modules.perfetto_analysis.src.agent.learnings_manager import memory_score
        r = memory_score({"confidence": 0.5, "hit_count": 3})
        assert r == 0.0


# ===========================================================================
# 淘汰流程测试
# ===========================================================================

class TestEviction:
    def test_evict_old_low_score(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import evict_low_score_learnings
        old_date = (datetime.now() - timedelta(days=30)).isoformat()
        for i in range(25):
            _insert_learning(mem_conn, created_at=old_date, hit_count=0, confidence=0.1)
        result = evict_low_score_learnings(mem_conn)
        assert result["archived"] == 5
        assert result["remaining"] == 20

    def test_min_retain_count(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import evict_low_score_learnings
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        for _ in range(15):
            _insert_learning(mem_conn, created_at=old_date, hit_count=0, confidence=0.1)
        result = evict_low_score_learnings(mem_conn)
        assert result["archived"] == 0
        assert result["remaining"] == 15

    def test_cooldown_protection(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import evict_low_score_learnings
        new_date = (datetime.now() - timedelta(days=2)).isoformat()
        for _ in range(30):
            _insert_learning(mem_conn, created_at=new_date, hit_count=0, confidence=0.1)
        result = evict_low_score_learnings(mem_conn)
        assert result["archived"] == 0

    def test_high_score_not_evicted(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import evict_low_score_learnings
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        for _ in range(25):
            _insert_learning(
                mem_conn, created_at=old_date,
                hit_count=10, confidence=0.9,
                last_used=datetime.now().isoformat(),
            )
        result = evict_low_score_learnings(mem_conn)
        assert result["archived"] == 0

    def test_empty_table(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import evict_low_score_learnings
        result = evict_low_score_learnings(mem_conn)
        assert result["archived"] == 0
        assert result["remaining"] == 0


# ===========================================================================
# 自动触发判断测试
# ===========================================================================

class TestShouldTrigger:
    def test_zero_count(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import should_trigger_maintenance
        assert should_trigger_maintenance(mem_conn) is False

    def test_count_20(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import should_trigger_maintenance
        _insert_telemetry_rows(mem_conn, 20)
        assert should_trigger_maintenance(mem_conn) is True

    def test_count_21(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import should_trigger_maintenance
        _insert_telemetry_rows(mem_conn, 21)
        assert should_trigger_maintenance(mem_conn) is False

    def test_count_40(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import should_trigger_maintenance
        _insert_telemetry_rows(mem_conn, 40)
        assert should_trigger_maintenance(mem_conn) is True


# ===========================================================================
# 合并操作测试
# ===========================================================================

class TestMergeLearnings:
    def test_merge_success(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import _merge_learnings
        sid = _insert_learning(mem_conn, hit_count=3, confidence=0.7)
        tid = _insert_learning(mem_conn, hit_count=5, confidence=0.8)
        assert _merge_learnings(mem_conn, sid, tid) is True

        target = mem_conn.execute("SELECT * FROM pa_learnings WHERE id=?", (tid,)).fetchone()
        source = mem_conn.execute("SELECT * FROM pa_learnings WHERE id=?", (sid,)).fetchone()
        assert target["hit_count"] == 8
        assert target["confidence"] == 0.8
        assert source["archived"] == 1

    def test_merge_self_reference(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import _merge_learnings
        rid = _insert_learning(mem_conn)
        assert _merge_learnings(mem_conn, rid, rid) is False

    def test_merge_nonexistent(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import _merge_learnings
        rid = _insert_learning(mem_conn)
        assert _merge_learnings(mem_conn, rid, 9999) is False

    def test_merge_confidence_max(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import _merge_learnings
        sid = _insert_learning(mem_conn, confidence=0.9, hit_count=2)
        tid = _insert_learning(mem_conn, confidence=0.6, hit_count=1)
        _merge_learnings(mem_conn, sid, tid)
        target = mem_conn.execute("SELECT confidence FROM pa_learnings WHERE id=?", (tid,)).fetchone()
        assert target["confidence"] == 0.9


# ===========================================================================
# LLM 晋升流程测试
# ===========================================================================

class TestPromoteLearnings:
    def test_no_candidates(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import promote_learnings
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(promote_learnings(mem_conn, MagicMock()))
        finally:
            loop.close()
        assert result.get("skipped") is True

    def test_promote_action(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import (
            PromotionAction,
            promote_learnings,
        )
        rid = _insert_learning(mem_conn, hit_count=5, confidence=0.8)

        mock_result = MagicMock()
        mock_result.output = [
            PromotionAction(id=rid, action="promote", reason="good"),
        ]
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_result)

        mock_llm = MagicMock()
        mock_llm.get_model.return_value = MagicMock()

        with patch("pydantic_ai.Agent", return_value=mock_agent_instance):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(promote_learnings(mem_conn, mock_llm))
            finally:
                loop.close()

        assert result["promoted"] == 1
        row = mem_conn.execute("SELECT promoted FROM pa_learnings WHERE id=?", (rid,)).fetchone()
        assert row["promoted"] == 1

    def test_llm_failure_safe_degradation(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import promote_learnings
        _insert_learning(mem_conn, hit_count=5, confidence=0.8)

        mock_llm = MagicMock()
        mock_llm.get_model.side_effect = RuntimeError("API down")

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(promote_learnings(mem_conn, mock_llm))
        finally:
            loop.close()
        assert result["promoted"] == 0
        assert "error" in result


# ===========================================================================
# _apply_promotion_actions 测试
# ===========================================================================

class TestApplyActions:
    def test_all_action_types(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import (
            PromotionAction,
            _apply_promotion_actions,
        )
        ids = [_insert_learning(mem_conn, hit_count=5, confidence=0.8) for _ in range(4)]
        candidates = [{"id": i} for i in ids]
        actions = [
            PromotionAction(id=ids[0], action="promote", reason="good"),
            PromotionAction(id=ids[1], action="archive", reason="outdated"),
            PromotionAction(id=ids[2], action="merge", merge_target_id=ids[3], reason="dup"),
            PromotionAction(id=ids[3], action="keep", reason="ok"),
        ]
        stats = _apply_promotion_actions(mem_conn, actions, candidates)
        assert stats["promoted"] == 1
        assert stats["archived"] == 1
        assert stats["merged"] == 1
        assert stats["kept"] == 1

    def test_unknown_id_skipped(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import (
            PromotionAction,
            _apply_promotion_actions,
        )
        actions = [PromotionAction(id=9999, action="promote", reason="ghost")]
        stats = _apply_promotion_actions(mem_conn, actions, [{"id": 1}])
        assert stats["promoted"] == 0


# ===========================================================================
# PromotionAction 模型测试
# ===========================================================================

class TestPromotionAction:
    def test_valid_model(self):
        from modules.perfetto_analysis.src.agent.learnings_manager import PromotionAction
        a = PromotionAction(id=1, action="promote", reason="good")
        assert a.merge_target_id is None

    def test_merge_with_target(self):
        from modules.perfetto_analysis.src.agent.learnings_manager import PromotionAction
        a = PromotionAction(id=1, action="merge", merge_target_id=2, reason="dup")
        assert a.merge_target_id == 2


# ===========================================================================
# _build_promotion_prompt 测试
# ===========================================================================

class TestBuildPrompt:
    def test_format(self):
        from modules.perfetto_analysis.src.agent.learnings_manager import _build_promotion_prompt
        candidates = [
            {"id": 1, "scene": "jank", "root_cause_tags": "cpu",
             "confidence": 0.8, "hit_count": 5, "insight": "test"},
        ]
        prompt = _build_promotion_prompt(candidates)
        assert "ID=1" in prompt
        assert "jank" in prompt
        assert "promote" in prompt


# ===========================================================================
# Orchestrator 集成测试
# ===========================================================================

class TestOrchestratorIntegration:
    def test_format_learnings_block_promoted_label(self):
        from modules.perfetto_analysis.src.agent.orchestrator import AnalysisOrchestrator
        learnings = [
            {"id": 1, "scene": "jank", "process_name": "com.test",
             "root_cause_tags": "cpu", "confidence": 0.9, "hit_count": 5,
             "insight": "test insight", "key_metrics": "", "promoted": 1},
            {"id": 2, "scene": "jank", "process_name": "com.test",
             "root_cause_tags": "gpu", "confidence": 0.7, "hit_count": 2,
             "insight": "another insight", "key_metrics": "", "promoted": 0},
        ]
        block = AnalysisOrchestrator._format_learnings_block(learnings)
        assert "[已验证]" in block
        lines = block.split("\n")
        promoted_line = [l for l in lines if "案例 1" in l][0]
        assert "[已验证]" in promoted_line
        non_promoted_line = [l for l in lines if "案例 2" in l][0]
        assert "[已验证]" not in non_promoted_line

    def test_l1_exact_match_promoted_order(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_search import LearningsSearcher
        _insert_learning(mem_conn, scene="jank", process_name="com.a",
                         confidence=0.9, hit_count=5, promoted=0)
        _insert_learning(mem_conn, scene="jank", process_name="com.a",
                         confidence=0.7, hit_count=3, promoted=1)
        searcher = LearningsSearcher(mem_conn)
        results = searcher._l1_exact_match("jank", "com.a", limit=5)
        assert len(results) == 2
        assert results[0]["promoted"] == 1

    def test_l1_tag_cross_promoted_order(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_search import LearningsSearcher
        _insert_learning(mem_conn, scene="jank", process_name="com.b",
                         root_cause_tags="cpu_throttle",
                         confidence=0.9, hit_count=5, promoted=0)
        _insert_learning(mem_conn, scene="jank", process_name="com.c",
                         root_cause_tags="cpu_throttle",
                         confidence=0.7, hit_count=3, promoted=1)
        searcher = LearningsSearcher(mem_conn)
        results = searcher._l1_tag_cross_match("jank", ["cpu_throttle"], [], limit=5)
        assert len(results) == 2
        assert results[0]["promoted"] == 1


# ===========================================================================
# record_maintenance_telemetry 测试
# ===========================================================================

class TestTelemetry:
    def test_record_maintenance(self, mem_conn):
        from modules.perfetto_analysis.src.agent.learnings_manager import record_maintenance_telemetry
        with patch("modules.perfetto_analysis.src.engine.storage.insert_telemetry") as mock_insert:
            record_maintenance_telemetry(
                mem_conn, "manual",
                {"archived": 3, "remaining": 17},
                {"promoted": 1, "merged": 0, "archived": 0},
            )
            mock_insert.assert_called_once()
