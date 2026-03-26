"""PerfDog 分析 — CLI（解析与导出 JSON/Markdown，不依赖 GUI）。"""

from __future__ import annotations

from pathlib import Path

import typer

from .service import PerfdogInsightsService

perfdog_app = typer.Typer(help="PerfDog 导出分析")


@perfdog_app.command("info")
def info() -> None:
    """显示模块信息（数据来自 Service，与 GUI 同源）。"""
    meta = PerfdogInsightsService().get_service_info()
    typer.echo(
        f"{meta.get('display_name', 'PerfDog分析')} v{meta.get('version', '')} — "
        "也可用 `toolkit perfdog analyze` 离线导出 JSON/Markdown",
    )


@perfdog_app.command("analyze")
def analyze(
    path: str = typer.Argument(..., help="PerfDog 导出 .xlsx / .xlsm"),
    json_out: Path | None = typer.Option(
        None,
        "--json",
        "-j",
        help="写入完整分析 JSON（UTF-8）",
    ),
    markdown_out: Path | None = typer.Option(
        None,
        "--markdown",
        "-m",
        help="写入 Markdown 报告（UTF-8）",
    ),
    compact: bool = typer.Option(
        False,
        "--compact",
        help="JSON 省略 anomaly 切片中的逐行数据，仅保留 row_count",
    ),
) -> None:
    """解析 PerfDog Excel，导出结构化 JSON 与/或 Markdown（无界面）。"""
    p = Path(path)
    if not p.is_file():
        typer.secho(f"文件不存在: {path}", err=True, fg="red")
        raise typer.Exit(code=1)
    if json_out is None and markdown_out is None:
        typer.secho(
            "请至少指定 --json 和/或 --markdown",
            err=True,
            fg="yellow",
        )
        raise typer.Exit(code=1)

    svc = PerfdogInsightsService()
    report = svc.load_report(str(p))

    if json_out is not None:
        text = svc.report_to_json(report, include_chunk_rows=not compact)
        json_out.write_text(text, encoding="utf-8")
        typer.echo(f"已写入 JSON: {json_out}")

    if markdown_out is not None:
        markdown_out.write_text(svc.compose_export_markdown(report), encoding="utf-8")
        typer.echo(f"已写入 Markdown: {markdown_out}")
