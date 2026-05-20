"""设备伪装 — CLI 文案常量"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Typer 命令帮助
# ---------------------------------------------------------------------------

CLI_HELP_ROOT: Final = "设备伪装工具"
CLI_HELP_PROFILE: Final = "设备档案管理"
CLI_HELP_STATUS: Final = "查看设备连接状态和伪装信息"
CLI_HELP_DISGUISE: Final = "执行设备信息伪装"
CLI_HELP_RESET: Final = "还原设备信息到原始状态"
CLI_HELP_PROFILE_LIST: Final = "列出所有设备档案"
CLI_HELP_PROFILE_ADD: Final = "添加设备档案"
CLI_HELP_PROFILE_IMPORT: Final = "从 JSON 文件批量导入设备档案"

# ---------------------------------------------------------------------------
# Typer 选项帮助
# ---------------------------------------------------------------------------

CLI_OPT_SERIAL: Final = "设备序列号"
CLI_OPT_BRAND: Final = "目标品牌"
CLI_OPT_MANUFACTURER: Final = "目标厂商"
CLI_OPT_MODEL: Final = "目标型号"
CLI_OPT_NOTES: Final = "备注"
CLI_OPT_FILE: Final = "JSON 文件路径"

# ---------------------------------------------------------------------------
# 表格标题与列
# ---------------------------------------------------------------------------

TABLE_TITLE_DEVICE_STATUS_FMT: Final = "设备状态 [{}]"
TABLE_TITLE_PROFILE_LIBRARY: Final = "设备档案库"
TABLE_COL_PROPERTY: Final = "属性"
TABLE_COL_CURRENT_VALUE: Final = "当前值 (ODM)"
TABLE_COL_ORIGINAL_VALUE: Final = "原始值 (Vendor)"
TABLE_COL_INDEX: Final = "#"

# ---------------------------------------------------------------------------
# Rich 状态消息
# ---------------------------------------------------------------------------

RICH_STATUS_DISGUISED: Final = "[bold magenta]状态: 已伪装[/bold magenta]"
RICH_STATUS_NOT_DISGUISED: Final = "[bold green]状态: 未伪装[/bold green]"
RICH_OK_DISGUISE: Final = "[bold green]✓ 伪装完成[/bold green]"
RICH_ERR_DISGUISE_FMT: Final = "[bold red]✗ 伪装失败: {}[/bold red]"
RICH_OK_RESET: Final = "[bold green]✓ 还原完成[/bold green]"
RICH_ERR_RESET_FMT: Final = "[bold red]✗ 还原失败: {}[/bold red]"
RICH_PROFILE_EMPTY: Final = "[dim]档案库为空[/dim]"
RICH_OK_PROFILE_ADDED_FMT: Final = "[green]✓ 已添加: {}/{}/{}[/green]"
RICH_ERR_FMT: Final = "[red]✗ {}[/red]"
RICH_OK_IMPORT_RESULT_FMT: Final = "[green]✓ 导入完成: {} 条导入, {} 条跳过[/green]"
RICH_ERR_IMPORT_FAILED_FMT: Final = "[red]✗ 导入失败: {}[/red]"

# ---------------------------------------------------------------------------
# Rich 验证错误
# ---------------------------------------------------------------------------

RICH_ERR_NO_DEVICES: Final = "[red]✗ 未检测到已连接的设备[/red]"
RICH_ERR_DEVICE_NOT_CONNECTED_FMT: Final = "[red]✗ 设备 {} 未连接[/red]"
