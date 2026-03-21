"""设备伪装工具 — CLI 子命令"""

import typer

device_app = typer.Typer(help="设备伪装工具")


@device_app.command("info")
def info():
    """显示模块信息"""
    typer.echo("设备伪装工具 v1.0.0")
