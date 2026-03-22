"""模块级类型再导出（与 game_perf.models 对齐：集中暴露跨 GUI/CLI 的数据形态）。

PerfDog 报告主体由核心库 `toolkit.core.perfdog` 维护；此处仅作稳定导入入口，供本模块
`service` / `gui_tab` / 测试使用。
"""

from __future__ import annotations

from toolkit.core.perfdog.report_types import (
    AnalysisReport,
    AnalyzeOptions,
    SessionComparePair,
    SessionSummary,
)

__all__ = [
    "AnalysisReport",
    "AnalyzeOptions",
    "SessionComparePair",
    "SessionSummary",
]
