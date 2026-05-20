"""Agent 智能助手 — CLI 文案常量"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Typer 命令 help
# ---------------------------------------------------------------------------

CLI_HELP_ROOT: Final = "Agent 智能助手"
CLI_HELP_SOP: Final = "SOP 文档管理"
CLI_HELP_ASK: Final = "向 Agent 发送消息并获取回复"
CLI_HELP_INFO: Final = "显示 Agent 模块信息与当前配置"
CLI_HELP_SOP_LIST: Final = "列出所有可用的 SOP 文档"
CLI_HELP_SOP_SHOW: Final = "显示指定 SOP 的完整内容"

# ---------------------------------------------------------------------------
# Typer 选项 help
# ---------------------------------------------------------------------------

CLI_OPT_MESSAGE: Final = "发送给 Agent 的消息"
CLI_OPT_SOP: Final = "指定 SOP 名称"
CLI_OPT_PROVIDER: Final = "LLM Provider (glm/claude)"
CLI_OPT_SOP_NAME: Final = "SOP 名称"

# ---------------------------------------------------------------------------
# Console 输出
# ---------------------------------------------------------------------------

CONSOLE_ERR_NO_API_KEY: Final = "[bold red]错误: 未配置 API Key[/bold red]"
CONSOLE_HINT_SET_KEY: Final = "请设置环境变量 ZHIPUAI_API_KEY 或 ANTHROPIC_API_KEY，"
CONSOLE_HINT_GUI_CONFIG: Final = "或在 GUI 设置中配置。"
CONSOLE_ERR_PROVIDER_INIT_FAILED: Final = "[bold red]错误: LLM Provider 初始化失败[/bold red]"
CONSOLE_HINT_CHECK_KEY: Final = "请检查 API Key 是否正确。"
CONSOLE_TOOL_CALL_FMT: Final = "\n[dim][🔧 调用: {}][/dim]"
CONSOLE_TOOL_STATUS_FAIL: Final = "❌ 失败"
CONSOLE_TOOL_STATUS_OK: Final = "✅ 完成"
CONSOLE_TOOL_END_FMT: Final = " [dim][{} {:.0f}ms][/dim]"
CONSOLE_ERR_FMT: Final = "\n[bold red]错误: {}[/bold red]"
CONSOLE_TOKEN_USAGE_FMT: Final = "\n[dim]Token: {}+{}={}[/dim]"
CONSOLE_SOP_NOT_FOUND_FMT: Final = "[bold red]SOP '{}' 未找到。[/bold red]"
CONSOLE_NO_SOP: Final = "[dim]暂无 SOP 文档。[/dim]"

# ---------------------------------------------------------------------------
# 表格
# ---------------------------------------------------------------------------

TABLE_TITLE_SOP_LIST: Final = "SOP 文档列表"
TABLE_COL_NAME: Final = "名称"
TABLE_COL_SOURCE: Final = "来源"
TABLE_COL_KEYWORDS: Final = "关键词"
TABLE_COL_DESCRIPTION: Final = "描述"

# ---------------------------------------------------------------------------
# SOP 来源标签
# ---------------------------------------------------------------------------

SOP_SOURCE_BUILTIN: Final = "内置"
SOP_SOURCE_CUSTOM: Final = "自定义"

# ---------------------------------------------------------------------------
# SOP / Info 面板标题
# ---------------------------------------------------------------------------

CLI_TITLE_SOP_FMT: Final = "SOP: {}"

# ---------------------------------------------------------------------------
# Info 面板
# ---------------------------------------------------------------------------

INFO_TITLE: Final = "Agent 智能助手"
INFO_KEY_CONFIGURED: Final = "✅ 已配置"
INFO_KEY_NOT_CONFIGURED: Final = "❌ 未配置"
