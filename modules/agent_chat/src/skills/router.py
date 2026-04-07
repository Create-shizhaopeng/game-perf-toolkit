# -*- coding: utf-8 -*-
"""SkillRouter — 基于关键词 + TF-IDF 的意图匹配。"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter

from ..models import SkillMetadata

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """简易中英文分词。"""
    text = text.lower()
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text)
    return tokens


class SkillRouter:
    """根据用户意图匹配最合适的 Skill。"""

    def __init__(self) -> None:
        self._skills: list[SkillMetadata] = []
        self._skill_docs: list[list[str]] = []
        self._idf: dict[str, float] = {}

    def update_index(self, skills: list[SkillMetadata]) -> None:
        """重建 Skill 索引。"""
        self._skills = list(skills)
        self._skill_docs = []

        for meta in self._skills:
            doc_tokens = (
                _tokenize(meta.name)
                + _tokenize(meta.description)
                + [t.lower() for t in meta.tags]
                + [t.lower() for t in meta.triggers]
            )
            self._skill_docs.append(doc_tokens)

        self._compute_idf()

    def _compute_idf(self) -> None:
        """计算 IDF 权重。"""
        n = len(self._skill_docs)
        if n == 0:
            self._idf = {}
            return

        df: Counter[str] = Counter()
        for doc in self._skill_docs:
            unique_tokens = set(doc)
            for t in unique_tokens:
                df[t] += 1

        self._idf = {
            t: math.log((n + 1) / (freq + 1)) + 1 for t, freq in df.items()
        }

    def match(self, query: str, top_k: int = 3) -> list[tuple[SkillMetadata, float]]:
        """匹配最相关的 Skill，返回 [(metadata, score), ...]。"""
        if not self._skills:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        query_tf = Counter(query_tokens)
        scores: list[tuple[SkillMetadata, float]] = []

        for i, meta in enumerate(self._skills):
            doc_tokens = self._skill_docs[i]
            doc_tf = Counter(doc_tokens)
            score = self._cosine_similarity(query_tf, doc_tf)

            trigger_boost = sum(
                2.0 for t in meta.triggers if t.lower() in query.lower()
            )
            score += trigger_boost

            scores.append((meta, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [(m, s) for m, s in scores[:top_k] if s > 0]

    def _cosine_similarity(
        self, tf_a: Counter[str], tf_b: Counter[str]
    ) -> float:
        """TF-IDF 余弦相似度。"""
        all_terms = set(tf_a) | set(tf_b)
        if not all_terms:
            return 0.0

        dot = 0.0
        mag_a = 0.0
        mag_b = 0.0

        for t in all_terms:
            w_a = tf_a.get(t, 0) * self._idf.get(t, 1.0)
            w_b = tf_b.get(t, 0) * self._idf.get(t, 1.0)
            dot += w_a * w_b
            mag_a += w_a * w_a
            mag_b += w_b * w_b

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot / (math.sqrt(mag_a) * math.sqrt(mag_b))
