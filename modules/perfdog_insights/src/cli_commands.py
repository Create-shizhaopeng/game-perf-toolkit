"""PerfDog 分析 — CLI（解析与导出 JSON/Markdown，不依赖 GUI）。"""

from __future__ import annotations

from pathlib import Path

import typer

from .service import PerfdogInsightsService

from . import strings_cli as s

perfdog_app = typer.Typer(help=s.CLI_HELP_ROOT)


@perfdog_app.command("info")
def info() -> None:
    """显示模块信息（数据来自 Service，与 GUI 同源）。"""
    meta = PerfdogInsightsService().get_service_info()
    typer.echo(
        f"{meta.get('display_name', s.CLI_FALLBACK_DISPLAY_NAME)} v{meta.get('version', '')} — "
        "也可用 `toolkit perfdog analyze` 离线导出 JSON/Markdown",
    )


@perfdog_app.command("analyze")
def analyze(
    path: str = typer.Argument(..., help=s.CLI_OPT_PATH),
    json_out: Path | None = typer.Option(
        None,
        "--json",
        "-j",
        help=s.CLI_OPT_JSON,
    ),
    markdown_out: Path | None = typer.Option(
        None,
        "--markdown",
        "-m",
        help=s.CLI_OPT_MARKDOWN,
    ),
    compact: bool = typer.Option(
        False,
        "--compact",
        help=s.CLI_OPT_COMPACT,
    ),
) -> None:
    """解析 PerfDog Excel，导出结构化 JSON 与/或 Markdown（无界面）。"""
    p = Path(path)
    if not p.is_file():
        typer.secho(s.CONSOLE_FILE_NOT_FOUND_FMT.format(path), err=True, fg="red")
        raise typer.Exit(code=1)
    if json_out is None and markdown_out is None:
        typer.secho(
            s.CONSOLE_NO_OUTPUT_SPECIFIED,
            err=True,
            fg="yellow",
        )
        raise typer.Exit(code=1)

    svc = PerfdogInsightsService()
    report = svc.load_report(str(p))

    if json_out is not None:
        text = svc.report_to_json(report, include_chunk_rows=not compact)
        json_out.write_text(text, encoding="utf-8")
        typer.echo(s.CONSOLE_JSON_WRITTEN_FMT.format(json_out))

    if markdown_out is not None:
        markdown_out.write_text(svc.compose_export_markdown(report), encoding="utf-8")
        typer.echo(s.CONSOLE_MD_WRITTEN_FMT.format(markdown_out))
