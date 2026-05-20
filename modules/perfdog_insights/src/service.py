"""PerfDog 分析 — 服务层（纯 Python，无 PyQt）。

业务编排：`load_report`、Markdown、`report_to_plain_dict` / `report_to_json`（自定义 UI/CLI）。
实现委托 `toolkit.core.perfdog`。
"""

from __future__ import annotations

from collections.abc import Callable

from typing import Any

from toolkit.core.perfdog import (
    AnalyzeOptions,
    build_markdown,
    load_and_analyze,
    report_to_json,
    report_to_plain_dict,
)

from . import strings_service as s
from .models import AnalysisReport


class PerfdogInsightsService:
    """模块对外 Service API；GUI/CLI 仅调用本类，不直接依赖 core 解析实现。"""

    def get_service_info(self) -> dict:
        return {
            "name": "perfdog_insights",
            "display_name": s.SERVICE_DISPLAY_NAME,
            "version": "0.1.0",
        }

    def summarize_report(self, path: str) -> dict:
        """加载 PerfDog 报告并返回关键指标摘要。"""
        report = self.load_report(path)
        metrics = report.summary_metrics or {}
        session = report.session

        fps_stats: dict = {}
        for key in ("avg_fps", "min_fps", "max_fps", "p1_fps", "fps_avg", "fps_min", "fps_max"):
            if key in metrics:
                fps_stats[key] = metrics[key]

        bottlenecks = []
        for f in report.findings:
            bottlenecks.append({"detail": f.detail, "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity)})

        return {
            "package_name": session.package_name or "",
            "device_name": session.device_name or "",
            "duration_ms": session.duration_ms,
            "fps_stats": fps_stats,
            "jank_rate": metrics.get("jank_rate", metrics.get("jank_ratio", None)),
            "memory_peak": metrics.get("memory_peak", metrics.get("pss_max", None)),
            "power_avg": metrics.get("power_avg", metrics.get("current_avg", None)),
            "key_bottlenecks": bottlenecks[:10],
            "recommendations": [r.text for r in report.recommendations[:5]],
            "finding_count": len(report.findings),
            "source_path": path,
        }

    def load_report(
        self,
        path: str,
        *,
        interrupt_check: Callable[[], bool] | None = None,
    ) -> AnalysisReport:
        opts = AnalyzeOptions(interrupt_check=interrupt_check)
        return load_and_analyze(path, options=opts)

    @staticmethod
    def compose_export_markdown(report: AnalysisReport) -> str:
        """PerfDog 全文 Markdown（UTF-8）。"""
        return build_markdown(report)

    @staticmethod
    def report_to_plain_dict(
        report: AnalysisReport,
        *,
        include_chunk_rows: bool = True,
    ) -> dict[str, Any]:
        """机器可读报告（自定义 UI / 脚本）；与 PyQt 无关。"""
        return report_to_plain_dict(report, include_chunk_rows=include_chunk_rows)

    @staticmethod
    def report_to_json(
        report: AnalysisReport,
        *,
        include_chunk_rows: bool = True,
        ensure_ascii: bool = False,
        indent: int | None = 2,
    ) -> str:
        """UTF-8 JSON 字符串。"""
        return report_to_json(
            report,
            include_chunk_rows=include_chunk_rows,
            ensure_ascii=ensure_ascii,
            indent=indent,
        )
