"""游戏性能配置 — CLI 子命令"""

import typer

perf_app = typer.Typer(help="游戏性能配置")


@perf_app.command("info")
def info():
    """显示模块信息"""
    typer.echo("游戏性能配置 v1.0.0")
