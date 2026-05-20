from __future__ import annotations

from typing import Final


# =============================================================================
# CLI Help Texts
# =============================================================================

CLI_HELP_ROOT: Final[str] = "Perfetto 卡顿抓取"
CLI_HELP_CONFIG: Final[str] = "配置管理"


# =============================================================================
# CLI Docstrings
# =============================================================================

CLI_DOC_INFO: Final[str] = "显示模块信息与当前配置概要"
CLI_DOC_START: Final[str] = "启动一轮 Perfetto 抓取（非交互模式: start → save → export）"
CLI_DOC_CONFIG_SHOW: Final[str] = "显示当前完整配置"
CLI_DOC_CONFIG_RESET: Final[str] = "重置为默认配置"


# =============================================================================
# CLI Option Help Texts
# =============================================================================

CLI_OPT_SERIAL: Final[str] = "设备序列号"
CLI_OPT_DURATION: Final[str] = "保存窗口(秒)"
CLI_OPT_BUFFER: Final[str] = "缓冲区大小(KB)"
CLI_OPT_OUTPUT: Final[str] = "输出目录"


# =============================================================================
# Table Labels
# =============================================================================

TABLE_TITLE_CONFIG: Final[str] = "当前配置"
TABLE_COL_CONFIG: Final[str] = "配置项"
TABLE_COL_VALUE: Final[str] = "值"
TABLE_ROW_CATEGORIES_FMT: Final[str] = "{} 项"


# =============================================================================
# Console Output Messages
# =============================================================================

# -- Error messages --
CONSOLE_ERR_SVC_INIT: Final[str] = "[red]错误: Perfetto 服务未初始化[/red]"
CONSOLE_ERR_ADB_INIT: Final[str] = "[red]错误: ADB 服务未初始化[/red]"
CONSOLE_ERR_NO_DEVICE: Final[str] = "[red]未检测到已连接设备[/red]"

# -- Format templates (device / config info) --
CONSOLE_AUTO_SELECT_DEVICE_FMT: Final[str] = "自动选择设备: {}"
CONSOLE_DEVICE_FMT: Final[str] = "[bold]设备:[/bold] {}"
CONSOLE_CONFIG_FMT: Final[str] = "[bold]配置:[/bold] duration={}s, buffer={}KB"

# -- Progress / status messages --
CONSOLE_START_CAPTURE: Final[str] = "[bold green]▶ 开始抓取...[/bold green]"
CONSOLE_WAIT_SEC_FMT: Final[str] = "等待 {} 秒..."
CONSOLE_SAVE_TRACE: Final[str] = "[bold yellow]⏹ 保存 trace...[/bold yellow]"
CONSOLE_EXPORTING: Final[str] = "[bold blue]■ 导出中...[/bold blue]"

# -- Result messages --
CONSOLE_EXPORT_DONE: Final[str] = "[bold green]✓ 导出完成:[/bold green]"
CONSOLE_NO_VALID_TRACE: Final[str] = "[yellow]本次抓取未保存有效 trace[/yellow]"
CONSOLE_CONFIG_RESET: Final[str] = "[green]✓ 已重置为默认配置[/green]"
