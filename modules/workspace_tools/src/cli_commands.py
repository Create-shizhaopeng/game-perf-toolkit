"""性能配置对比 — CLI 子命令（workspace）"""

import typer

workspace_app = typer.Typer(help="性能配置对比（gameperfconfig 等多文件工具）")


@workspace_app.command("info")
def info():
    """显示模块信息"""
    typer.echo("性能配置对比（workspace_tools）v0.1.0")
