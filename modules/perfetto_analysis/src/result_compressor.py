# -*- coding: utf-8 -*-
"""Perfetto 分析结果压缩器。

将一组原子工具的分析结果压缩为结构化 JSON 摘要，供 agent_chat 使用。
同时提供工具返回值压缩（compress_tool_output），用于 ToolReturn 场景。
"""
from __future__ import annotations

import json
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

_CHAR_PER_TOKEN = 2.5


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

    def compress_tool_output(
        self,
        tool_name: str,
        raw_output: Any,
        token_budget: int = 300,
    ) -> str:
        """将工具原始返回值压缩为 LLM 可消费的文本摘要。

        Args:
            tool_name: 工具名称，用于选择压缩策略
            raw_output: 工具原始返回值
            token_budget: token 预算上限

        Returns:
            压缩后的文本摘要
        """
        if raw_output is None:
            return "工具未返回数据"
        if isinstance(raw_output, dict) and "error" in raw_output:
            return f"错误: {raw_output['error']}"
        if not raw_output:
            return "工具未返回数据"

        strategy = self._COMPRESS_STRATEGIES.get(tool_name)
        try:
            if strategy:
                result = strategy(self, raw_output, token_budget)
            else:
                result = self._compress_generic(raw_output, token_budget)
        except Exception as exc:
            logger.warning("压缩工具 %s 输出失败: %s", tool_name, exc)
            result = self._compress_generic(raw_output, token_budget)

        max_chars = int(token_budget * _CHAR_PER_TOKEN)
        if len(result) > max_chars:
            result = result[:max_chars - 20] + "\n...(结果已截断)"
        return result

    def _compress_jank(self, data: Any, token_budget: int) -> str:
        """pa_detect_jank: Top-5 严重 jank + 统计摘要。"""
        if not isinstance(data, dict):
            return self._compress_generic(data, token_budget)

        jank_frames = data.get("jank_frames", data.get("frames", []))
        if isinstance(jank_frames, list):
            total = len(jank_frames)
            if total == 0:
                return "未检测到 Jank 帧"

            sorted_frames = sorted(
                jank_frames,
                key=lambda f: f.get("jank_num", f.get("duration_ms", 0)),
                reverse=True,
            )
            top5 = sorted_frames[:self._top_n]

            durations = [
                f.get("duration_ms", f.get("jank_num", 0)) for f in jank_frames
            ]
            avg_dur = sum(durations) / len(durations) if durations else 0
            max_dur = max(durations) if durations else 0

            lines = [f"Jank 统计: 总计 {total} 条, 平均耗时 {avg_dur:.1f}ms, 最大耗时 {max_dur:.1f}ms"]
            lines.append(f"Top-{len(top5)} 严重帧:")
            for i, f in enumerate(top5, 1):
                frame_id = f.get("frame_number", f.get("idx", "?"))
                dur = f.get("duration_ms", f.get("jank_num", "?"))
                sev = f.get("severity", "")
                lines.append(f"  {i}. 帧#{frame_id}: {dur}ms {sev}")

            return "\n".join(lines)

        return self._compress_generic(data, token_budget)

    def _compress_dimension(self, data: Any, token_budget: int) -> str:
        """pa_analyze_dimension: 保留 issues + top 指标。"""
        if not isinstance(data, dict):
            return self._compress_generic(data, token_budget)

        parts: list[str] = []

        for dim_name, dim_data in data.items():
            if not isinstance(dim_data, dict):
                continue
            issues = dim_data.get("issues", [])
            if issues:
                parts.append(f"[{dim_name}] {len(issues)} 个问题:")
                for issue in issues[:3]:
                    desc = issue.get("description", str(issue)) if isinstance(issue, dict) else str(issue)
                    parts.append(f"  - {desc[:100]}")
            else:
                parts.append(f"[{dim_name}] 无异常")

        if not parts:
            keys = list(data.keys())[:5]
            parts.append(f"返回字段: {', '.join(keys)}")
            for k in keys[:3]:
                v = data[k]
                if isinstance(v, (str, int, float)):
                    parts.append(f"  {k}: {v}")
                elif isinstance(v, list):
                    parts.append(f"  {k}: {len(v)} 项")
                elif isinstance(v, dict):
                    parts.append(f"  {k}: {list(v.keys())[:3]}")

        return "\n".join(parts)

    def _compress_generic(self, data: Any, token_budget: int) -> str:
        """通用截断: 按 token 预算截断。"""
        max_chars = int(token_budget * _CHAR_PER_TOKEN)

        if isinstance(data, str):
            return data[:max_chars]

        if isinstance(data, (int, float, bool)):
            return str(data)

        if isinstance(data, list):
            if not data:
                return "空列表"
            total = len(data)
            preview_count = min(3, total)
            preview_items = []
            for item in data[:preview_count]:
                s = json.dumps(item, ensure_ascii=False, default=str)
                preview_items.append(s[:200])
            return f"共 {total} 项。前 {preview_count} 项:\n" + "\n".join(preview_items)

        if isinstance(data, dict):
            try:
                text = json.dumps(data, ensure_ascii=False, indent=None, default=str)
            except (TypeError, ValueError):
                text = str(data)
            if len(text) <= max_chars:
                return text
            return text[:max_chars - 20] + "\n...(结果已截断)"

        return str(data)[:max_chars]

    _COMPRESS_STRATEGIES: dict[str, Any] = {
        "pa_detect_jank": _compress_jank,
        "pa_analyze_dimension": _compress_dimension,
    }

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
