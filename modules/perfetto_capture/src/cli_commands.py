"""Perfetto卡顿抓取 — CLI 子命令"""

import typer

perfetto_app = typer.Typer(help="Perfetto卡顿抓取")


@perfetto_app.command("info")
def info():
    """显示模块信息"""
    typer.echo("Perfetto卡顿抓取 v0.1.0")
