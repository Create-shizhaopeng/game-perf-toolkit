"""PerfDog 分析 — CLI"""

import typer

perfdog_app = typer.Typer(help="PerfDog 导出分析")


@perfdog_app.command("info")
def info() -> None:
    """显示模块信息"""
    typer.echo("PerfDog分析 v0.1.0 — 请使用 GUI 导入 xlsx")
