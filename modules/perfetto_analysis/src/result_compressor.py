# -*- coding: utf-8 -*-
"""Perfetto 分析结果压缩器。

将一组原子工具的分析结果压缩为结构化 JSON 摘要，供 agent_chat 使用。
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from .models import (
    CompressedSummary,
    DataCompleteness,
    DimensionHealth,
    DimensionResult,
    RootCause,
    TraceInfo,
    TraceOverview,
)

logger = logging.getLogger(__name__)

_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


class ResultCompressor:
    """分析结果压缩器。"""

    def __init__(self, top_n: int = 5) -> None:
        self._top_n = top_n

    def compress(
        self,
        overview: TraceOverview,
        dimension_results: list[DimensionResult],
        jank_frames: list[dict[str, Any]] | None = None,
    ) -> CompressedSummary:
        """压缩分析结果为 CompressedSummary。"""
        jank_count = len(jank_frames) if jank_frames else 0

        trace_info = TraceInfo(
            file=overview.file,
            process=overview.processes[0] if overview.processes else "",
            duration_s=overview.duration_s,
            refresh_rate_hz=overview.refresh_rate_hz,
            frame_count=overview.frame_count,
            jank_count=jank_count,
            avg_fps=self._calc_avg_fps(overview),
        )

        severity = self._calc_severity(jank_count, jank_frames)
        root_causes = self._extract_root_causes(dimension_results)
        health = self._build_health_summary(dimension_results)
        completeness = self._build_data_completeness(dimension_results)

        return CompressedSummary(
            trace_info=trace_info,
            severity=severity,
            root_causes=root_causes,
            health_summary=health,
            data_completeness=completeness,
        )

    def _calc_avg_fps(self, overview: TraceOverview) -> float:
        if overview.duration_s > 0 and overview.frame_count > 0:
            return round(overview.frame_count / overview.duration_s, 1)
        return 0.0

    def _calc_severity(
        self,
        jank_count: int,
        jank_frames: list[dict[str, Any]] | None,
    ) -> Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        max_jank_num = 0
        if jank_frames:
            max_jank_num = max(
                (f.get("jank_num", 0) for f in jank_frames), default=0,
            )

        if jank_count >= 10 or max_jank_num >= 20:
            return "CRITICAL"
        if jank_count >= 5 or max_jank_num >= 10:
            return "HIGH"
        if jank_count >= 2 or max_jank_num >= 5:
            return "MEDIUM"
        return "LOW"

    def _extract_root_causes(
        self, results: list[DimensionResult],
    ) -> list[RootCause]:
        """遍历维度结果按严重度排序取 Top N。"""
        candidates: list[RootCause] = []

        for dr in results:
            if dr.source == "unavailable" or not dr.data:
                continue

            issues = self._extract_issues_from_data(dr.dimension, dr.data)
            candidates.extend(issues)

        candidates.sort(key=lambda c: _SEVERITY_ORDER.get(c.severity, 99))
        for i, cause in enumerate(candidates[:self._top_n], 1):
            cause.rank = i

        return candidates[:self._top_n]

    def _extract_issues_from_data(
        self, dimension: str, data: dict[str, Any],
    ) -> list[RootCause]:
        """从维度数据中提取问题作为 RootCause 候选。"""
        causes: list[RootCause] = []

        if "issues" in data:
            for issue in data["issues"]:
                if isinstance(issue, dict):
                    causes.append(RootCause(
                        rank=0,
                        cause=issue.get("description", str(issue)),
                        evidence=issue.get("evidence", ""),
                        severity=self._issue_severity(issue),
                        dimension=dimension,
                    ))
                elif isinstance(issue, str):
                    causes.append(RootCause(
                        rank=0,
                        cause=issue,
                        evidence="",
                        severity="MEDIUM",
                        dimension=dimension,
                    ))

        if "per_jank_results" in data:
            for jank_result in data["per_jank_results"]:
                if isinstance(jank_result, dict):
                    sub_issues = self._extract_issues_from_data(
                        dimension, jank_result,
                    )
                    causes.extend(sub_issues)

        if "error" in data and data["error"]:
            causes.append(RootCause(
                rank=0,
                cause=f"{dimension} 分析异常: {data['error']}",
                evidence="",
                severity="HIGH",
                dimension=dimension,
            ))

        return causes

    @staticmethod
    def _issue_severity(
        issue: dict[str, Any],
    ) -> Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        sev = issue.get("severity", "MEDIUM")
        if isinstance(sev, str) and sev.upper() in _SEVERITY_ORDER:
            return sev.upper()  # type: ignore[return-value]
        return "MEDIUM"

    def _build_health_summary(
        self, results: list[DimensionResult],
    ) -> dict[str, DimensionHealth]:
        health: dict[str, DimensionHealth] = {}

        for dr in results:
            if dr.source == "unavailable":
                health[dr.dimension] = DimensionHealth(
                    status="UNAVAILABLE",
                    note=dr.error or "数据不可用",
                )
            elif dr.error:
                health[dr.dimension] = DimensionHealth(
                    status="WARNING",
                    note=dr.error,
                )
            elif not dr.data:
                health[dr.dimension] = DimensionHealth(
                    status="OK",
                    note="无异常",
                )
            else:
                issues = dr.data.get("issues", [])
                if issues:
                    health[dr.dimension] = DimensionHealth(
                        status="CRITICAL" if len(issues) >= 3 else "WARNING",
                        note=f"{len(issues)} 个问题",
                    )
                else:
                    health[dr.dimension] = DimensionHealth(
                        status="OK",
                        note="无异常",
                    )

        return health

    @staticmethod
    def _build_data_completeness(
        results: list[DimensionResult],
    ) -> DataCompleteness:
        degraded: list[str] = []
        mcp_src: list[str] = []
        engine_src: list[str] = []

        for dr in results:
            if dr.source == "mcp":
                mcp_src.append(dr.dimension)
            elif dr.source == "engine":
                engine_src.append(dr.dimension)
            elif dr.source == "degraded":
                degraded.append(dr.dimension)
                engine_src.append(dr.dimension)

        return DataCompleteness(
            degraded_dimensions=degraded,
            mcp_source=mcp_src,
            engine_source=engine_src,
        )
