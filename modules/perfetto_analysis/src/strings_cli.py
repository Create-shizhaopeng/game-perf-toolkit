from __future__ import annotations

from typing import Final


# =============================================================================
# CLI Help Texts
# =============================================================================

CLI_HELP_ROOT: Final[str] = "Perfetto 解析分析"
CLI_HELP_CONFIG: Final[str] = "分析配置管理"


# =============================================================================
# CLI Docstrings (Typer command descriptions)
# =============================================================================

CLI_DOC_INFO: Final[str] = "显示模块信息与当前配置。"
CLI_DOC_PARSE: Final[str] = "仅执行 Phase 1 丢帧解析（不做 Phase 2 分析）。"
CLI_DOC_EXPORT: Final[str] = "完整分析：Phase 1 + Phase 2 + 导出报告。"
CLI_DOC_ANALYZE_DIMENSIONS: Final[str] = "按维度独立分析。"
CLI_DOC_CONFIG_SHOW: Final[str] = "显示当前分析模式配置。"
CLI_DOC_CONFIG_SET: Final[str] = "设置分析模式。"
CLI_DOC_DIMS: Final[str] = "列出可用分析维度。"
CLI_DOC_REPORT: Final[str] = "从已有 DB 导出 Markdown 报告（不重新分析）。"
CLI_DOC_REVIEW_LEARNINGS: Final[str] = (
    "手动触发经验库整理（淘汰低价值 + LLM 晋升评审）。"
)
CLI_DOC_HISTORY: Final[str] = "查看分析历史记录。"


# =============================================================================
# CLI Option / Argument Help Texts
# =============================================================================

CLI_OPT_TRACE_PATH: Final[str] = "Trace 文件路径（支持多个）"
CLI_OPT_PROCESS: Final[str] = "目标进程/包名"
CLI_OPT_JSON: Final[str] = "JSON 格式输出"
CLI_OPT_OUTPUT_DIR: Final[str] = "输出目录"
CLI_OPT_APP_TYPE: Final[str] = "应用类型"
CLI_OPT_ANALYZE_TOP: Final[str] = "分析 Top N"
CLI_OPT_FORMAT: Final[str] = "输出格式 md/json"
CLI_OPT_DIMS: Final[str] = "分析维度"
CLI_OPT_ANALYSIS_MODE: Final[str] = (
    "分析模式: mcp_preferred / engine_only / mcp_only"
)


# =============================================================================
# Table Labels
# =============================================================================

TABLE_TITLE_MODULE: Final[str] = "Perfetto 解析分析"
TABLE_COL_PROJECT: Final[str] = "项目"
TABLE_COL_VALUE: Final[str] = "值"
TABLE_ROW_PERFETTO_AVAILABLE: Final[str] = "perfetto 可用"
TABLE_ROW_OUTPUT_DIR: Final[str] = "输出目录"
TABLE_ROW_DEFAULT_PROCESS: Final[str] = "默认进程"
VALUE_NOT_SET: Final[str] = "(未设置)"
TABLE_ROW_ANALYZE_TOP: Final[str] = "分析 Top N"
PERFETTO_AVAILABLE_YES: Final[str] = "✅"
PERFETTO_AVAILABLE_NO: Final[str] = "❌ 请安装 perfetto>=0.16.0"

TABLE_TITLE_LEARNINGS_RANK_FMT: Final[str] = "经验评分排名 (共 {} 条)"
LEARNINGS_TABLE_COL_SCENE: Final[str] = "场景"
LEARNINGS_TABLE_COL_TAGS: Final[str] = "标签"
LEARNINGS_TABLE_COL_CONFIDENCE: Final[str] = "置信度"
LEARNINGS_TABLE_COL_HITS: Final[str] = "命中"
LEARNINGS_TABLE_COL_STATUS: Final[str] = "状态"
STATUS_VERIFIED: Final[str] = "已验证"
STATUS_ARCHIVED: Final[str] = "归档"
STATUS_ACTIVE: Final[str] = "活跃"

TABLE_TITLE_HISTORY: Final[str] = "分析历史"
HISTORY_TABLE_COL_TIME: Final[str] = "时间"
HISTORY_TABLE_COL_STATUS: Final[str] = "状态"


# =============================================================================
# Console Output Messages
# =============================================================================

# -- Error messages --
CONSOLE_FILE_NOT_FOUND_FMT: Final[str] = "[red]文件不存在: {}[/red]"
CONSOLE_DB_CONN_FAIL: Final[str] = "[red]无法获取数据库连接[/red]"
CONSOLE_ERROR_FMT: Final[str] = "[red]{}[/red]"
CONSOLE_EXPORT_FAIL: Final[str] = "[red]导出失败[/red]"
CONSOLE_FAIL_FMT: Final[str] = "  [red]失败: {}[/red]"

# -- Info command --
CONSOLE_ANALYSIS_MODE_FMT: Final[str] = "[bold]分析模式:[/bold] {}"
CONSOLE_MCP_TIMEOUT_FMT: Final[str] = "[bold]MCP 超时:[/bold] {}ms"
CONSOLE_DIMENSION_OVERRIDES: Final[str] = "[bold]维度覆盖:[/bold]"
CONSOLE_MODE_SET_FMT: Final[str] = "[green]分析模式已设置为: {}[/green]"

# -- Parse command --
CONSOLE_PARSE_FMT: Final[str] = "[bold]解析: {}[/bold]"
CONSOLE_PARSE_RESULT_FMT: Final[str] = (
    "  丢帧: [bold]{}[/bold] 次 | "
    "帧数: {} | "
    "刷新率: {}Hz | "
    "耗时: {}s"
)

# -- Export/Analyze command --
CONSOLE_ANALYZE_FMT: Final[str] = "[bold]完整分析: {}[/bold]"
CONSOLE_ANALYZE_COMPLETE_FMT: Final[str] = "  ✅ 完成 ({}s)\n  报告: {}"

# -- Dimension analysis --
CONSOLE_DIM_ANALYZE_FMT: Final[str] = "[bold]维度分析: {}[/bold]"
CONSOLE_DIMS_FMT: Final[str] = "  维度: {}"
CONSOLE_DIM_COMPLETE_FMT: Final[str] = "  ✅ 完成 ({}s)\n  报告目录: {}"

# -- Report command --
CONSOLE_EXPORT_DONE: Final[str] = "✅ 导出完成"

# -- Learnings review --
CONSOLE_LEARNINGS_TITLE: Final[str] = "[bold]经验库整理[/bold]\n"
NO_LEARNINGS_RECORD: Final[str] = "无经验记录"
NO_CANDIDATE_ENTRIES: Final[str] = "[dim]无候选条目[/dim]"
CONSOLE_EVICT_TITLE: Final[str] = "[bold]执行淘汰...[/bold]"
CONSOLE_EVICT_RESULT_FMT: Final[str] = "  淘汰: {} 条, 剩余: {} 条"
CONSOLE_PROMOTE_TITLE: Final[str] = "[bold]执行 LLM 晋升评审...[/bold]"
CONSOLE_SKIP_PROMOTE: Final[str] = "  [dim]未配置 LLM，跳过晋升[/dim]"
CONSOLE_PROMOTE_FAIL_FMT: Final[str] = "  [yellow]LLM 晋升失败: {}[/yellow]"
CONSOLE_DONE: Final[str] = "[green]完成![/green]"
CONSOLE_PROMOTED_FMT: Final[str] = "  晋升: {} 条"
CONSOLE_MERGED_FMT: Final[str] = "  合并: {} 条"
CONSOLE_ARCHIVED_FMT: Final[str] = "  归档: {} 条"

# -- History --
NO_HISTORY: Final[str] = "[dim]暂无分析历史[/dim]"
