"""PerfettoAnalysisService 中文用户可见字符串常量。

通过 Final[str] 常量集中管理，避免在业务逻辑中硬编码。
"""

from __future__ import annotations

from typing import Final


# ── Service Info ──
SERVICE_DISPLAY_NAME: Final = "Perfetto 解析分析"

# ── Progress / Status ──
PROGRESS_LOADING_TRACE: Final = "正在加载 trace 文件..."
PROGRESS_PHASE1_PARSING: Final = "Phase 1: 丢帧解析中..."
PROGRESS_PHASE1_COMPLETE_FMT: Final = "Phase 1 完成: {} 次丢帧, {} 帧, {}Hz"
PROGRESS_PHASE2_ANALYZING: Final = "Phase 2: 卡顿归因分析中..."
PROGRESS_AUTO_DETECT_PROCESS_FMT: Final = "自动识别进程: {}"
PROGRESS_PHASE2_COMPLETE: Final = "Phase 2 分析完成"
PROGRESS_EXPORTING_REPORT: Final = "导出报告中..."
PROGRESS_ANALYSIS_COMPLETE_FMT: Final = "分析完成 ({:.1f}s), 报告: {}"
PROGRESS_ANALYSIS_FAIL_FMT: Final = "分析失败: {}"
PROGRESS_PARSE_COMPLETE_FMT: Final = "解析完成 ({:.1f}s): {} 次丢帧, {} 帧"
PROGRESS_PARSE_FAIL_FMT: Final = "解析失败: {}"
PROGRESS_AUTO_DIMS_FMT: Final = "自动补全依赖维度: {}"
PROGRESS_LOADING_TRACE_2: Final = "正在加载 trace..."
PROGRESS_ANALYZING_DIM_FMT: Final = "分析维度: {}..."
PROGRESS_DIM_ANALYSIS_COMPLETE_FMT: Final = "维度分析完成 ({:.1f}s): {}"
PROGRESS_DIM_ANALYSIS_FAIL_FMT: Final = "维度分析失败: {}"
PROGRESS_EXPORTING_MD: Final = "导出 Markdown 报告中..."
PROGRESS_EXPORT_DONE: Final = "导出完成"
PROGRESS_EXPORT_FAIL: Final = "导出失败"
PROGRESS_READING_DB: Final = "从数据库读取分析数据..."
PROGRESS_TRACE_NOT_IN_DB: Final = "数据库中未找到该 trace 的分析数据"
PROGRESS_REGENERATING: Final = "重新生成报告文件..."
PROGRESS_REGENERATED_FMT: Final = "报告已重新生成: {}"
PROGRESS_REGENERATE_FAIL_FMT: Final = "重新生成报告失败: {}"

# ── Error ──
ERR_INVALID_ANALYSIS_MODE_FMT: Final = "无效的分析模式: {}，可选: {}"