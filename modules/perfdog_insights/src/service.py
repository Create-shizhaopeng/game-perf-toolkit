"""PerfDog 分析 — 服务层（纯 Python，无 PyQt/Typer）。

业务编排入口：解析、双会话对比、导出 Markdown 拼接。
实现细节委托 `toolkit.core.perfdog`。
"""

from __future__ import annotations

from collections.abc import Callable

from toolkit.core.perfdog import (
    AnalyzeOptions,
    build_compare_markdown,
    build_markdown,
    compare_reports,
    load_and_analyze,
)

from .models import AnalysisReport, SessionComparePair


class PerfdogInsightsService:
    """模块对外 Service API；GUI/CLI 仅调用本类，不直接依赖 core 解析实现。"""

    def get_service_info(self) -> dict:
        return {
            "name": "perfdog_insights",
            "display_name": "PerfDog分析",
            "version": "0.1.0",
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
    def compare_reports_pair(a: AnalysisReport, b: AnalysisReport) -> SessionComparePair:
        return compare_reports(a, b)

    @staticmethod
    def compose_export_markdown(
        report: AnalysisReport,
        *,
        compare_pair: SessionComparePair | None = None,
    ) -> str:
        """PerfDog 全文 + 可选 A/B 对比节（UTF-8 文本）。"""
        body = build_markdown(report)
        if compare_pair is not None:
            body += "\n\n" + build_compare_markdown(compare_pair)
        return body
