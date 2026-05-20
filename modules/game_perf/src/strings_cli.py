"""游戏性能配置 — CLI 文案常量"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Typer help
# ---------------------------------------------------------------------------

CLI_HELP_ROOT: Final = "游戏性能配置管理"
CLI_HELP_CONFIG_FILE: Final = "gameperfconfig XML 文件路径"
CLI_HELP_NOTES: Final = "推送备注"

# ---------------------------------------------------------------------------
# 命令 docstring
# ---------------------------------------------------------------------------

CLI_DOC_INFO: Final = "查看设备上的 gameperfconfig 信息"
CLI_DOC_PUSH: Final = "推送性能配置文件到设备"
CLI_DOC_RESET: Final = "将设备配置还原为推送前的备份"

# ---------------------------------------------------------------------------
# Rich Table
# ---------------------------------------------------------------------------

TABLE_TITLE_DEVICE_INFO: Final = "设备性能配置信息"
TABLE_COL_PROPERTY: Final = "属性"
TABLE_COL_VALUE: Final = "值"
TABLE_ROW_SERIAL: Final = "设备序列号"
TABLE_ROW_REMOTE_PATH: Final = "配置文件路径"
TABLE_ROW_VERSION: Final = "当前 version"
TABLE_ROW_HAS_BACKUP: Final = "有备份"
TABLE_YES: Final = "是"
TABLE_NO: Final = "否"

# ---------------------------------------------------------------------------
# Rich 状态消息
# ---------------------------------------------------------------------------

RICH_ERR_NO_DEVICES: Final = "[red]✗ 未检测到已连接的设备[/red]"
RICH_PUSH_SUCCESS_FMT: Final = "\n[green]✓ 推送成功，设备 version = {version}[/green]"
RICH_RESET_SUCCESS_FMT: Final = "\n[green]✓ 还原成功，设备 version = {version}[/green]"
RICH_ERR_FMT: Final = "\n[red]✗ {e}[/red]"
