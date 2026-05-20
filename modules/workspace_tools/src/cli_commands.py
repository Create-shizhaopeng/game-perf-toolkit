"""性能配置对比 — CLI 子命令（workspace）"""

import typer

from . import strings_cli as s

workspace_app = typer.Typer(help=s.CLI_HELP_ROOT)


@workspace_app.command("info")
def info():
    """显示模块信息"""
    typer.echo(s.CLI_INFO_OUTPUT)
