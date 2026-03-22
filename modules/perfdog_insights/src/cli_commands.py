"""PerfDog 分析 — CLI（仅信息类；解析走 GUI 或未来扩展子命令）。"""

import typer

from .service import PerfdogInsightsService

perfdog_app = typer.Typer(help="PerfDog 导出分析")


@perfdog_app.command("info")
def info() -> None:
    """显示模块信息（数据来自 Service，与 GUI 同源）。"""
    meta = PerfdogInsightsService().get_service_info()
    typer.echo(
        f"{meta.get('display_name', 'PerfDog分析')} v{meta.get('version', '')} — "
        "完整分析请使用 GUI 导入 .xlsx/.xlsm",
    )
