"""PerfDog 分析 — 服务层（纯 Python，无 PyQt/Typer）。

业务编排入口：解析、导出 Markdown。
实现细节委托 `toolkit.core.perfdog`。
"""

from __future__ import annotations

from collections.abc import Callable

from toolkit.core.perfdog import AnalyzeOptions, build_markdown, load_and_analyze

from .models import AnalysisReport


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
    def compose_export_markdown(report: AnalysisReport) -> str:
        """PerfDog 全文 Markdown（UTF-8 文本，含秒级全量表）。"""
        return build_markdown(report)
