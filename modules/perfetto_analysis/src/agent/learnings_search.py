# -*- coding: utf-8 -*-
"""两级经验检索：L1 SQL 标签匹配 → L2 向量语义搜索。"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class LearningsSearcher:
    """从 pa_learnings 表检索历史相似案例。

    L1: SQL 精确匹配 (scene+process) + 标签交叉匹配
    L2: sentence-transformers + sqlite-vec 语义搜索 (可选增强)
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        embedder: Any | None = None,
    ) -> None:
        self._conn = conn
        self._embedder = embedder

    def search(
        self,
        scene: str,
        process_name: str = "",
        issue_tags: list[str] | None = None,
        limit: int = 3,
    ) -> list[dict]:
        """两级检索主入口。返回最多 limit 条经验记录。"""
        results: list[dict] = []
        found_ids: list[int] = []

        exact = self._l1_exact_match(scene, process_name, limit=2)
        results.extend(exact)
        found_ids.extend(r["id"] for r in exact)

        if len(results) < limit:
            remaining = limit - len(results)
            cross = self._l1_tag_cross_match(
                scene, issue_tags or [], found_ids, limit=remaining,
            )
            results.extend(cross)
            found_ids.extend(r["id"] for r in cross)

        if len(results) < 2 and self._embedder is not None:
            remaining = limit - len(results)
            query = f"{scene} {' '.join(issue_tags or [])}"
            semantic = self._l2_semantic_search(query, found_ids, limit=remaining)
            results.extend(semantic)

        return results[:limit]

    def _l1_exact_match(
        self, scene: str, process_name: str, limit: int = 2,
    ) -> list[dict]:
        """L1 第一优先级：同场景 + 同进程精确匹配。"""
        try:
            cursor = self._conn.execute(
                """SELECT id, task_id, scene, process_name, root_cause_tags,
                          insight, key_metrics, confidence, hit_count, promoted
                   FROM pa_learnings
                   WHERE scene = ? AND process_name = ? AND archived = 0
                   ORDER BY promoted DESC, confidence DESC, hit_count DESC
                   LIMIT ?""",
                (scene, process_name, limit),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as exc:
            logger.debug("L1 精确匹配失败: %s", exc)
            return []

    def _l1_tag_cross_match(
        self,
        scene: str,
        issue_tags: list[str],
        exclude_ids: list[int],
        limit: int = 1,
    ) -> list[dict]:
        """L1 第二优先级：同场景 + 根因标签交叉。无 issue_tags 时按 scene 扩大匹配。"""
        try:
            placeholders = ",".join("?" for _ in exclude_ids) if exclude_ids else "0"
            params: list[Any] = [scene]
            params.extend(exclude_ids)

            if issue_tags:
                tag_conditions = []
                for tag in issue_tags:
                    tag_conditions.append("root_cause_tags LIKE ?")
                    params.append(f"%{tag}%")
                tag_where = f"AND ({' OR '.join(tag_conditions)})"
            else:
                tag_where = ""

            params.append(limit)

            query = f"""
                SELECT id, task_id, scene, process_name, root_cause_tags,
                       insight, key_metrics, confidence, hit_count, promoted
                FROM pa_learnings
                WHERE scene = ? AND id NOT IN ({placeholders})
                  AND archived = 0
                  {tag_where}
                ORDER BY promoted DESC, confidence DESC, hit_count DESC
                LIMIT ?
            """
            cursor = self._conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as exc:
            logger.debug("L1 标签交叉匹配失败: %s", exc)
            return []

    def _l2_semantic_search(
        self,
        query: str,
        exclude_ids: list[int],
        limit: int = 2,
    ) -> list[dict]:
        """L2 向量语义搜索。需要 embedder 和 sqlite-vec。"""
        if self._embedder is None:
            return []
        try:
            query_vec = self._embedder.encode(query)

            from sqlite_vec import serialize_float32
            query_blob = serialize_float32(query_vec.tolist())

            placeholders = ",".join("?" for _ in exclude_ids) if exclude_ids else "0"
            params: list[Any] = [query_blob]
            params.extend(exclude_ids)
            params.append(limit)

            cursor = self._conn.execute(
                f"""SELECT e.learning_id AS id, e.distance,
                           l.scene, l.process_name, l.root_cause_tags,
                           l.insight, l.key_metrics, l.confidence, l.hit_count
                    FROM pa_learning_embeddings e
                    JOIN pa_learnings l ON e.learning_id = l.id
                    WHERE l.id NOT IN ({placeholders})
                      AND l.archived = 0
                    ORDER BY e.distance ASC
                    LIMIT ?""",
                params,
            )
            results = [dict(row) for row in cursor.fetchall()]
            for r in results:
                r["retrieval_method"] = "semantic"
            return results
        except Exception as exc:
            logger.debug("L2 语义搜索失败 (静默降级): %s", exc)
            return []

    def update_hit_counts(
        self,
        injected_ids: list[int],
        conclusion_tags: set[str],
    ) -> int:
        """仅当结论根因标签与案例标签有交集时更新。返回更新条数。"""
        if not injected_ids or not conclusion_tags:
            return 0
        updated = 0
        try:
            now = datetime.now().isoformat()
            for learning_id in injected_ids:
                row = self._conn.execute(
                    "SELECT root_cause_tags FROM pa_learnings WHERE id = ?",
                    (learning_id,),
                ).fetchone()
                if not row or not row[0]:
                    continue
                learning_tags = {t.strip() for t in row[0].split(",") if t.strip()}
                if conclusion_tags & learning_tags:
                    self._conn.execute(
                        "UPDATE pa_learnings SET hit_count = hit_count + 1, last_used = ? WHERE id = ?",
                        (now, learning_id),
                    )
                    updated += 1
            if updated > 0:
                self._conn.commit()
        except Exception as exc:
            logger.debug("更新 hit_count 失败: %s", exc)
        return updated


def try_init_embedder() -> Any | None:
    """尝试初始化 sentence-transformers embedder。不可用返回 None。"""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("shibing624/text2vec-base-chinese")
    except ImportError:
        logger.debug("sentence-transformers 不可用，L2 语义搜索已禁用")
        return None
    except Exception as exc:
        logger.debug("初始化 embedder 失败: %s", exc)
        return None
