from __future__ import annotations

from typing import Final


# =============================================================================
# CLI Help Texts
# =============================================================================

CLI_HELP_ROOT: Final[str] = "PerfDog 导出分析"


# =============================================================================
# CLI Docstrings
# =============================================================================

CLI_DOC_INFO: Final[str] = "显示模块信息（数据来自 Service，与 GUI 同源）。"
CLI_DOC_ANALYZE: Final[str] = (
    "解析 PerfDog Excel，导出结构化 JSON 与/或 Markdown（无界面）。"
)


# =============================================================================
# CLI Option / Argument Help Texts
# =============================================================================

CLI_OPT_PATH: Final[str] = "PerfDog 导出 .xlsx / .xlsm"
CLI_OPT_JSON: Final[str] = "写入完整分析 JSON（UTF-8）"
CLI_OPT_MARKDOWN: Final[str] = "写入 Markdown 报告（UTF-8）"
CLI_OPT_COMPACT: Final[str] = (
    "JSON 省略 anomaly 切片中的逐行数据，仅保留 row_count"
)


# =============================================================================
# Console Output Messages
# =============================================================================

CONSOLE_FILE_NOT_FOUND_FMT: Final[str] = "文件不存在: {}"
CONSOLE_NO_OUTPUT_SPECIFIED: Final[str] = "请至少指定 --json 和/或 --markdown"
CONSOLE_JSON_WRITTEN_FMT: Final[str] = "已写入 JSON: {}"
CONSOLE_MD_WRITTEN_FMT: Final[str] = "已写入 Markdown: {}"
CLI_FALLBACK_DISPLAY_NAME: Final[str] = "PerfDog分析"