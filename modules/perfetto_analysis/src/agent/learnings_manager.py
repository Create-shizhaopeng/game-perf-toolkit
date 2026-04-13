# -*- coding: utf-8 -*-
"""G3 经验淘汰与晋升 — 评分、淘汰、LLM 驱动晋升。"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量 (T001)
# ---------------------------------------------------------------------------
DECAY_FACTOR = 0.95
EVICT_THRESHOLD = 0.05
MIN_RETAIN_COUNT = 20
COOLDOWN_DAYS = 7
PROMOTE_HIT_THRESHOLD = 3
PROMOTE_CONFIDENCE_THRESHOLD = 0.6
PROMOTE_CANDIDATE_LIMIT = 10
AUTO_TRIGGER_INTERVAL = 20

# ---------------------------------------------------------------------------
# Pydantic 模型 (T002)
# ---------------------------------------------------------------------------

class PromotionAction(BaseModel):
    """LLM 返回的单条晋升决策。"""

    id: int = Field(description="经验记录 ID")
    action: Literal["promote", "merge", "keep", "archive"] = Field(
        description="操作类型"
    )
    merge_target_id: int | None = Field(
        default=None, description="merge 操作的目标 ID"
    )
    reason: str = Field(default="", description="决策理由")


# ---------------------------------------------------------------------------
# 评分引擎 (T003)
# ---------------------------------------------------------------------------

def memory_score(learning: dict, now: datetime | None = None) -> float:
    """OpenClaw 风格的记忆价值评估。

    公式: recency × importance × frequency
    - recency  = DECAY_FACTOR ^ days_since_last_access
    - importance = confidence
    - frequency  = log(hit_count + 1)
    """
    now = now or datetime.now()
    last_access = learning.get("last_used") or learning.get("created_at")
    if not last_access:
        return 0.0
    if isinstance(last_access, str):
        last_access = datetime.fromisoformat(last_access)
    days_since = max((now - last_access).days, 0)

    recency = DECAY_FACTOR ** days_since
    importance = float(learning.get("confidence", 0.5))
    frequency = math.log(int(learning.get("hit_count", 0)) + 1)

    return recency * importance * frequency


# ---------------------------------------------------------------------------
# 淘汰流程 (T004)
# ---------------------------------------------------------------------------

def evict_low_score_learnings(
    conn: sqlite3.Connection,
    now: datetime | None = None,
) -> dict:
    """淘汰低价值经验：score < EVICT_THRESHOLD → archived = 1。

    FR-003: 至少保留 MIN_RETAIN_COUNT 条未归档记录。
    FR-004: 跳过创建不足 COOLDOWN_DAYS 天的记录。
    """
    now = now or datetime.now()
    cooldown_cutoff = now - timedelta(days=COOLDOWN_DAYS)

    rows = conn.execute(
        "SELECT id, confidence, hit_count, last_used, created_at "
        "FROM pa_learnings WHERE archived = 0"
    ).fetchall()

    total_active = len(rows)
    eligible: list[tuple[int, float]] = []

    for row in rows:
        r = dict(row)
        created = datetime.fromisoformat(r["created_at"])
        if created > cooldown_cutoff:
            continue
        score = memory_score(r, now)
        if score < EVICT_THRESHOLD:
            eligible.append((r["id"], score))

    eligible.sort(key=lambda x: x[1])

    archived_count = 0
    for row_id, _ in eligible:
        if total_active - archived_count <= MIN_RETAIN_COUNT:
            break
        conn.execute(
            "UPDATE pa_learnings SET archived = 1 WHERE id = ?", (row_id,)
        )
        archived_count += 1

    if archived_count > 0:
        conn.commit()

    return {"archived": archived_count, "remaining": total_active - archived_count}


# ---------------------------------------------------------------------------
# 自动触发判断 (T005)
# ---------------------------------------------------------------------------

def should_trigger_maintenance(conn: sqlite3.Connection) -> bool:
    """判断是否应自动触发经验库维护。

    规则: pa_telemetry 行数 > 0 且 行数 % AUTO_TRIGGER_INTERVAL == 0。
    """
    try:
        count = conn.execute("SELECT COUNT(*) FROM pa_telemetry").fetchone()[0]
        return count > 0 and count % AUTO_TRIGGER_INTERVAL == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 遥测记录 (T007)
# ---------------------------------------------------------------------------

def record_maintenance_telemetry(
    conn: sqlite3.Connection,
    trigger: str,
    evict_result: dict,
    promote_result: dict,
) -> None:
    """记录一次维护操作的遥测数据到 pa_telemetry。"""
    try:
        from ..engine.storage import insert_telemetry

        event_data = {
            "type": "maintenance",
            "trigger": trigger,
            "evict": evict_result,
            "promote": promote_result,
        }
        insert_telemetry(
            conn=conn,
            task_id=f"maintenance_{trigger}",
            trace_id="",
            scene="maintenance",
            model_name=promote_result.get("model", ""),
            tool_call_count=0,
            tool_calls_detail=json.dumps(event_data, ensure_ascii=False),
            total_prompt_tokens=promote_result.get("prompt_tokens", 0),
            total_completion_tokens=promote_result.get("completion_tokens", 0),
            conclusion_quality=trigger,
            elapsed_sec=promote_result.get("elapsed_sec", 0),
        )
    except Exception as exc:
        logger.warning("记录维护遥测失败: %s", exc)


# ---------------------------------------------------------------------------
# LLM 晋升 Prompt 构建 (T008)
# ---------------------------------------------------------------------------

def _build_promotion_prompt(candidates: list[dict]) -> str:
    """将候选经验格式化为 LLM 评审 prompt。"""
    entries = []
    for c in candidates:
        entries.append(
            f"ID={c['id']} | 场景={c.get('scene', '')} | "
            f"标签={c.get('root_cause_tags', '')} | "
            f"置信度={c.get('confidence', 0):.2f} | "
            f"命中={c.get('hit_count', 0)} | "
            f"经验={c.get('insight', '')[:300]}"
        )
    entries_text = "\n".join(entries)
    return (
        "以下是 Perfetto 性能分析中积累的经验条目。请评估每条经验：\n"
        "1. 是否值得长期保留？（通用性、可复用性、跨设备/应用的适用性）\n"
        "2. 是否与其他条目重复或高度相似？如果是，指出合并对象\n"
        "3. 给出建议操作：promote（晋升为已验证经验）/ merge（合并到指定条目）"
        " / keep（保持现状）/ archive（归档淘汰）\n\n"
        f"经验列表：\n{entries_text}"
    )


# ---------------------------------------------------------------------------
# 合并操作 (T010)
# ---------------------------------------------------------------------------

def _merge_learnings(
    conn: sqlite3.Connection, source_id: int, target_id: int,
) -> bool:
    """合并两条经验：源 archived，目标累加 hit_count + max confidence。"""
    if source_id == target_id:
        return False

    source = conn.execute(
        "SELECT hit_count, confidence FROM pa_learnings WHERE id = ?",
        (source_id,),
    ).fetchone()
    target = conn.execute(
        "SELECT hit_count, confidence FROM pa_learnings WHERE id = ?",
        (target_id,),
    ).fetchone()

    if not source or not target:
        return False

    new_hit = target["hit_count"] + source["hit_count"]
    new_conf = max(target["confidence"], source["confidence"])

    conn.execute(
        "UPDATE pa_learnings SET hit_count = ?, confidence = ? WHERE id = ?",
        (new_hit, new_conf, target_id),
    )
    conn.execute(
        "UPDATE pa_learnings SET archived = 1 WHERE id = ?",
        (source_id,),
    )
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# 执行 LLM 动作 (T011)
# ---------------------------------------------------------------------------

def _apply_promotion_actions(
    conn: sqlite3.Connection,
    actions: list[PromotionAction],
    candidates: list[dict],
) -> dict:
    """遍历 LLM 决策列表执行 promote/merge/archive/keep。"""
    candidate_ids = {c["id"] for c in candidates}
    stats: dict[str, int] = {"promoted": 0, "merged": 0, "archived": 0, "kept": 0}

    for act in actions:
        if act.id not in candidate_ids:
            continue

        if act.action == "promote":
            conn.execute(
                "UPDATE pa_learnings SET promoted = 1 WHERE id = ?", (act.id,),
            )
            stats["promoted"] += 1

        elif act.action == "merge":
            if act.merge_target_id and act.merge_target_id in candidate_ids:
                if _merge_learnings(conn, act.id, act.merge_target_id):
                    stats["merged"] += 1

        elif act.action == "archive":
            conn.execute(
                "UPDATE pa_learnings SET archived = 1 WHERE id = ?", (act.id,),
            )
            stats["archived"] += 1

        elif act.action == "keep":
            stats["kept"] += 1

    conn.commit()
    return stats


# ---------------------------------------------------------------------------
# LLM 晋升主流程 (T009)
# ---------------------------------------------------------------------------

async def promote_learnings(
    conn: sqlite3.Connection,
    llm_manager: Any,
) -> dict:
    """LLM 驱动的经验晋升。

    FR-005 ~ FR-007: 筛选候选 → top 10 → LLM 评审 → 执行动作。
    FR-009: LLM 失败时安全降级。
    """
    try:
        rows = conn.execute(
            "SELECT id, scene, root_cause_tags, insight, key_metrics, "
            "       confidence, hit_count, last_used, created_at "
            "FROM pa_learnings "
            "WHERE promoted = 0 AND archived = 0 "
            "  AND hit_count >= ? AND confidence >= ?",
            (PROMOTE_HIT_THRESHOLD, PROMOTE_CONFIDENCE_THRESHOLD),
        ).fetchall()
    except Exception as exc:
        logger.error("查询晋升候选失败: %s", exc)
        return {"promoted": 0, "merged": 0, "archived": 0, "error": str(exc)}

    if not rows:
        return {"promoted": 0, "merged": 0, "archived": 0, "skipped": True}

    candidates = [dict(r) for r in rows]
    now = datetime.now()
    candidates.sort(key=lambda x: memory_score(x, now), reverse=True)
    candidates = candidates[:PROMOTE_CANDIDATE_LIMIT]

    prompt = _build_promotion_prompt(candidates)

    import time
    start = time.time()
    try:
        from pydantic_ai import Agent

        model = llm_manager.get_model()
        agent = Agent(model, output_type=list[PromotionAction])
        result = await agent.run(prompt)
        actions = result.output
        elapsed = time.time() - start
    except Exception as exc:
        elapsed = time.time() - start
        logger.error("LLM 晋升评审失败 (%.1fs): %s", elapsed, exc)
        return {
            "promoted": 0, "merged": 0, "archived": 0,
            "error": str(exc), "elapsed_sec": elapsed,
        }

    stats = _apply_promotion_actions(conn, actions, candidates)
    stats["elapsed_sec"] = elapsed
    stats["candidates_count"] = len(candidates)
    return stats
