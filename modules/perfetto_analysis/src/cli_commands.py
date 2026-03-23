# -*- coding: utf-8 -*-
"""Perfetto 解析分析 — CLI 子命令（Typer）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

analysis_app = typer.Typer(help="Perfetto 解析分析")
console = Console()

_pa_context: dict | None = None


def _get_service():
    """获取已注册的 PerfettoAnalysisService 实例。"""
    if _pa_context and "pa_service" in _pa_context:
        return _pa_context["pa_service"]
    from .service import PerfettoAnalysisService
    data_dir = Path(__file__).resolve().parent.parent / "data"
    return PerfettoAnalysisService(data_dir=data_dir)


def _progress_printer(msg: str) -> None:
    console.print(f"  [dim]{msg}[/dim]")


@analysis_app.command("info")
def info(
    as_json: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """显示模块信息与当前配置。"""
    svc = _get_service()
    info_data = svc.get_service_info()
    cfg = svc.get_config()

    if as_json:
        data = {**info_data, "config": cfg.model_dump()}
        console.print_json(json.dumps(data, ensure_ascii=False))
        return

    table = Table(title="Perfetto 解析分析", show_header=False)
    table.add_column("项目", style="cyan")
    table.add_column("值")
    for k, v in info_data.items():
        table.add_row(k, str(v))
    table.add_row("perfetto 可用", "✅" if svc.perfetto_available else "❌ 请安装 perfetto>=0.16.0")
    table.add_row("输出目录", cfg.output_dir)
    table.add_row("默认进程", cfg.default_process or "(未设置)")
    table.add_row("分析 Top N", str(cfg.analyze_top))
    console.print(table)


@analysis_app.command("parse")
def parse_cmd(
    traces: Annotated[list[Path], typer.Argument(help="Trace 文件路径（支持多个）")],
    process: Annotated[str, typer.Option("--process", "-p", help="目标进程/包名")] = "",
    as_json: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """仅执行 Phase 1 丢帧解析（不做 Phase 2 分析）。"""
    svc = _get_service()
    for trace_path in traces:
        if not trace_path.exists():
            console.print(f"[red]文件不存在: {trace_path}[/red]")
            continue

        console.print(f"\n[bold]解析: {trace_path.name}[/bold]")
        result = svc.parse_only(
            str(trace_path), process_name=process,
            on_progress=_progress_printer,
        )
        if as_json:
            console.print_json(json.dumps({
                "trace": str(trace_path),
                "jank_times": result.jank_times,
                "frame_num": result.frame_num,
                "refresh_rate_hz": result.refresh_rate_hz,
                "elapsed_seconds": result.elapsed_seconds,
            }, ensure_ascii=False))
        else:
            console.print(
                f"  丢帧: [bold]{result.jank_times}[/bold] 次 | "
                f"帧数: {result.frame_num} | "
                f"刷新率: {result.refresh_rate_hz}Hz | "
                f"耗时: {result.elapsed_seconds}s"
            )


@analysis_app.command("export")
def export_cmd(
    traces: Annotated[list[Path], typer.Argument(help="Trace 文件路径（支持多个）")],
    process: Annotated[str, typer.Option("--process", "-p", help="目标进程/包名")] = "",
    output_dir: Annotated[Optional[str], typer.Option("--output-dir", "-o")] = None,
    app_type: Annotated[str, typer.Option("--app-type")] = "auto",
    analyze_top: Annotated[int, typer.Option("--analyze-top")] = 20,
    as_json: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """完整分析：Phase 1 + Phase 2 + 导出报告。"""
    svc = _get_service()
    cfg = svc.get_config()
    if app_type != "auto":
        cfg.app_type = app_type
    if analyze_top != 20:
        cfg.analyze_top = analyze_top
    if output_dir:
        cfg.output_dir = output_dir

    for trace_path in traces:
        if not trace_path.exists():
            console.print(f"[red]文件不存在: {trace_path}[/red]")
            continue

        console.print(f"\n[bold]完整分析: {trace_path.name}[/bold]")
        try:
            result = svc.analyze(
                str(trace_path), process_name=process,
                on_progress=_progress_printer,
            )
            if as_json:
                console.print_json(json.dumps({
                    "trace": str(trace_path),
                    "jank_times": result.jank_times,
                    "frame_num": result.frame_num,
                    "refresh_rate_hz": result.refresh_rate_hz,
                    "app_type": result.app_type,
                    "elapsed_seconds": result.elapsed_seconds,
                    "report_path": result.report_path,
                    "report_dir": result.report_dir,
                    "dimensions_completed": result.dimensions_completed,
                }, ensure_ascii=False))
            else:
                console.print(
                    f"  ✅ 完成 ({result.elapsed_seconds}s)\n"
                    f"  报告: {result.report_path}"
                )
        except Exception as e:
            console.print(f"  [red]失败: {e}[/red]")


@analysis_app.command("analyze")
def analyze_cmd(
    traces: Annotated[list[Path], typer.Argument(help="Trace 文件路径")],
    dims: Annotated[Optional[list[str]], typer.Option("--dims", "-d", help="分析维度")] = None,
    process: Annotated[str, typer.Option("--process", "-p", help="目标进程/包名")] = "",
    fmt: Annotated[str, typer.Option("--format", "-f", help="输出格式 md/json")] = "md",
    as_json: Annotated[bool, typer.Option("--json", help="JSON 输出到 stdout")] = False,
) -> None:
    """按维度独立分析。"""
    svc = _get_service()

    if not dims:
        console.print(svc.list_dimensions())
        return

    for trace_path in traces:
        if not trace_path.exists():
            console.print(f"[red]文件不存在: {trace_path}[/red]")
            continue

        console.print(f"\n[bold]维度分析: {trace_path.name}[/bold]")
        console.print(f"  维度: {', '.join(dims)}")
        try:
            result = svc.analyze_dimensions(
                str(trace_path), process_name=process,
                dimensions=dims, on_progress=_progress_printer,
            )
            if as_json:
                console.print_json(json.dumps({
                    "trace": str(trace_path),
                    "dimensions_completed": result.dimensions_completed,
                    "elapsed_seconds": result.elapsed_seconds,
                    "report_dir": result.report_dir,
                }, ensure_ascii=False))
            else:
                console.print(
                    f"  ✅ 完成 ({result.elapsed_seconds}s)\n"
                    f"  报告目录: {result.report_dir}"
                )
        except Exception as e:
            console.print(f"  [red]失败: {e}[/red]")


@analysis_app.command("dims")
def dims_cmd(
    as_json: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """列出可用分析维度。"""
    svc = _get_service()
    if as_json:
        from modules.perfetto_analysis.src.engine.dimension_registry import DIMENSIONS
        console.print_json(json.dumps(
            {k: v["desc"] for k, v in DIMENSIONS.items()},
            ensure_ascii=False,
        ))
    else:
        console.print(svc.list_dimensions())


@analysis_app.command("report")
def report_cmd(
    output_dir: Annotated[Optional[str], typer.Option("--output-dir", "-o")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """从已有 DB 导出 Markdown 报告（不重新分析）。"""
    svc = _get_service()
    try:
        result = svc.export_report(
            output_dir=output_dir,
            on_progress=_progress_printer,
        )
        if as_json:
            console.print_json(json.dumps({"success": result}, ensure_ascii=False))
        else:
            console.print("✅ 导出完成" if result else "[red]导出失败[/red]")
    except Exception as e:
        console.print(f"[red]导出失败: {e}[/red]")


@analysis_app.command("history")
def history_cmd(
    as_json: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """查看分析历史记录。"""
    svc = _get_service()
    records = svc.get_analysis_history()

    if as_json:
        console.print_json(json.dumps(records, ensure_ascii=False, default=str))
        return

    if not records:
        console.print("[dim]暂无分析历史[/dim]")
        return

    table = Table(title="分析历史")
    table.add_column("Trace", max_width=40)
    table.add_column("时间")
    table.add_column("状态")
    for r in records:
        trace_name = Path(r.get("trace_path", "")).name or r.get("trace_id", "")
        parsed_at = r.get("parsed_at_ns", "")
        if isinstance(parsed_at, int) and parsed_at > 0:
            import datetime
            dt = datetime.datetime.fromtimestamp(parsed_at / 1e9)
            parsed_at = dt.strftime("%m-%d %H:%M")
        table.add_row(str(trace_name), str(parsed_at), "✅")
    console.print(table)
