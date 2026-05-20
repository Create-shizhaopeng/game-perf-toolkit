# -*- coding: utf-8 -*-
"""Perfetto 解析分析 — CLI 子命令（Typer）。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import strings_cli as s

analysis_app = typer.Typer(help=s.CLI_HELP_ROOT)
config_app = typer.Typer(help=s.CLI_HELP_CONFIG)
analysis_app.add_typer(config_app, name="config")
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
    as_json: Annotated[bool, typer.Option("--json", help=s.CLI_OPT_JSON)] = False,
) -> None:
    """显示模块信息与当前配置。"""
    svc = _get_service()
    info_data = svc.get_service_info()
    cfg = svc.get_config()

    if as_json:
        data = {**info_data, "config": cfg.model_dump()}
        console.print_json(json.dumps(data, ensure_ascii=False))
        return

    table = Table(title=s.TABLE_TITLE_MODULE, show_header=False)
    table.add_column(s.TABLE_COL_PROJECT, style="cyan")
    table.add_column(s.TABLE_COL_VALUE)
    for k, v in info_data.items():
        table.add_row(k, str(v))
    table.add_row(s.TABLE_ROW_PERFETTO_AVAILABLE, s.PERFETTO_AVAILABLE_YES if svc.perfetto_available else s.PERFETTO_AVAILABLE_NO)
    table.add_row(s.TABLE_ROW_OUTPUT_DIR, cfg.output_dir)
    table.add_row(s.TABLE_ROW_DEFAULT_PROCESS, cfg.default_process or s.VALUE_NOT_SET)
    table.add_row(s.TABLE_ROW_ANALYZE_TOP, str(cfg.analyze_top))
    console.print(table)


@analysis_app.command("parse")
def parse_cmd(
    traces: Annotated[list[Path], typer.Argument(help=s.CLI_OPT_TRACE_PATH)],
    process: Annotated[str, typer.Option("--process", "-p", help=s.CLI_OPT_PROCESS)] = "",
    as_json: Annotated[bool, typer.Option("--json", help=s.CLI_OPT_JSON)] = False,
) -> None:
    """仅执行 Phase 1 丢帧解析（不做 Phase 2 分析）。"""
    svc = _get_service()
    for trace_path in traces:
        if not trace_path.exists():
            console.print(s.CONSOLE_FILE_NOT_FOUND_FMT.format(trace_path))
            continue

        console.print(s.CONSOLE_PARSE_FMT.format(trace_path.name))
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
                s.CONSOLE_PARSE_RESULT_FMT.format(
                    result.jank_times, result.frame_num,
                    result.refresh_rate_hz, result.elapsed_seconds,
                )
            )


@analysis_app.command("export")
def export_cmd(
    traces: Annotated[list[Path], typer.Argument(help=s.CLI_OPT_TRACE_PATH)],
    process: Annotated[str, typer.Option("--process", "-p", help=s.CLI_OPT_PROCESS)] = "",
    output_dir: Annotated[Optional[str], typer.Option("--output-dir", "-o")] = None,
    app_type: Annotated[str, typer.Option("--app-type")] = "auto",
    analyze_top: Annotated[int, typer.Option("--analyze-top")] = 20,
    as_json: Annotated[bool, typer.Option("--json", help=s.CLI_OPT_JSON)] = False,
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
            console.print(s.CONSOLE_FILE_NOT_FOUND_FMT.format(trace_path))
            continue

        console.print(s.CONSOLE_ANALYZE_FMT.format(trace_path.name))
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
                    s.CONSOLE_ANALYZE_COMPLETE_FMT.format(
                        result.elapsed_seconds, result.report_path,
                    )
                )
        except Exception as e:
            console.print(s.CONSOLE_FAIL_FMT.format(e))


@analysis_app.command("analyze")
def analyze_cmd(
    traces: Annotated[list[Path], typer.Argument(help=s.CLI_OPT_TRACE_PATH)],
    dims: Annotated[Optional[list[str]], typer.Option("--dims", "-d", help=s.CLI_OPT_DIMS)] = None,
    process: Annotated[str, typer.Option("--process", "-p", help=s.CLI_OPT_PROCESS)] = "",
    fmt: Annotated[str, typer.Option("--format", "-f", help=s.CLI_OPT_FORMAT)] = "md",
    as_json: Annotated[bool, typer.Option("--json", help=s.CLI_OPT_JSON)] = False,
    mode: Annotated[Optional[str], typer.Option("--mode", help=s.CLI_OPT_ANALYSIS_MODE)] = None,
) -> None:
    """按维度独立分析。"""
    svc = _get_service()
    if mode is not None:
        svc.set_analysis_mode(mode)

    if not dims:
        console.print(svc.list_dimensions())
        return

    for trace_path in traces:
        if not trace_path.exists():
            console.print(s.CONSOLE_FILE_NOT_FOUND_FMT.format(trace_path))
            continue

        console.print(s.CONSOLE_DIM_ANALYZE_FMT.format(trace_path.name))
        console.print(s.CONSOLE_DIMS_FMT.format(", ".join(dims)))
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
                    s.CONSOLE_DIM_COMPLETE_FMT.format(
                        result.elapsed_seconds, result.report_dir,
                    )
                )
        except Exception as e:
            console.print(s.CONSOLE_FAIL_FMT.format(e))


@config_app.command("show")
def config_show(
    as_json: Annotated[bool, typer.Option("--json", help=s.CLI_OPT_JSON)] = False,
) -> None:
    """显示当前分析模式配置。"""
    svc = _get_service()
    mode_info = svc.get_analysis_mode()
    if as_json:
        import json
        console.print(json.dumps(mode_info, ensure_ascii=False, indent=2))
    else:
        console.print(s.CONSOLE_ANALYSIS_MODE_FMT.format(mode_info['analysis_mode']))
        console.print(s.CONSOLE_MCP_TIMEOUT_FMT.format(mode_info['mcp_timeout_ms']))
        if mode_info['dimension_overrides']:
            console.print(s.CONSOLE_DIMENSION_OVERRIDES)
            for dim, m in mode_info['dimension_overrides'].items():
                console.print(f"  {dim}: {m}")


@config_app.command("set")
def config_set(
    mode: Annotated[str, typer.Argument(help=s.CLI_OPT_ANALYSIS_MODE)],
) -> None:
    """设置分析模式。"""
    svc = _get_service()
    try:
        svc.set_analysis_mode(mode)
        console.print(s.CONSOLE_MODE_SET_FMT.format(mode))
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@analysis_app.command("dims")
def dims_cmd(
    as_json: Annotated[bool, typer.Option("--json", help=s.CLI_OPT_JSON)] = False,
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
    as_json: Annotated[bool, typer.Option("--json", help=s.CLI_OPT_JSON)] = False,
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
            console.print(s.CONSOLE_EXPORT_DONE if result else s.CONSOLE_EXPORT_FAIL)
    except Exception as e:
        console.print(s.CONSOLE_ERROR_FMT.format(f"导出失败: {e}"))


@analysis_app.command("review-learnings")
def review_learnings_cmd(
    as_json: Annotated[bool, typer.Option("--json", help=s.CLI_OPT_JSON)] = False,
) -> None:
    """手动触发经验库整理（淘汰低价值 + LLM 晋升评审）。"""
    svc = _get_service()
    db = svc._db_manager
    conn = getattr(db, "conn", None) or getattr(db, "_conn", None)
    if conn is None:
        console.print(s.CONSOLE_DB_CONN_FAIL)
        raise typer.Exit(1)

    from .agent.learnings_manager import (
        evict_low_score_learnings,
        memory_score,
        promote_learnings,
        record_maintenance_telemetry,
    )
    from datetime import datetime

    console.print(s.CONSOLE_LEARNINGS_TITLE)

    rows = conn.execute(
        "SELECT id, scene, root_cause_tags, insight, confidence, "
        "       hit_count, last_used, created_at, promoted, archived "
        "FROM pa_learnings ORDER BY confidence DESC"
    ).fetchall()

    if not rows:
        if as_json:
            console.print_json(json.dumps({"message": s.NO_LEARNINGS_RECORD}, ensure_ascii=False))
        else:
            console.print(s.NO_CANDIDATE_ENTRIES)
        return

    now = datetime.now()
    scored = [(dict(r), memory_score(dict(r), now)) for r in rows]
    scored.sort(key=lambda x: x[1], reverse=True)

    if not as_json:
        table = Table(title=s.TABLE_TITLE_LEARNINGS_RANK_FMT.format(len(scored)))
        table.add_column("ID", style="cyan")
        table.add_column(s.LEARNINGS_TABLE_COL_SCENE)
        table.add_column(s.LEARNINGS_TABLE_COL_TAGS, max_width=20)
        table.add_column(s.LEARNINGS_TABLE_COL_CONFIDENCE, justify="right")
        table.add_column(s.LEARNINGS_TABLE_COL_HITS, justify="right")
        table.add_column("Score", justify="right")
        table.add_column(s.LEARNINGS_TABLE_COL_STATUS)
        for r, score in scored[:30]:
            status = s.STATUS_VERIFIED if r.get("promoted") else (s.STATUS_ARCHIVED if r.get("archived") else s.STATUS_ACTIVE)
            table.add_row(
                str(r["id"]), r.get("scene", ""),
                (r.get("root_cause_tags", ""))[:20],
                f"{r.get('confidence', 0):.2f}",
                str(r.get("hit_count", 0)),
                f"{score:.4f}",
                status,
            )
        console.print(table)

    console.print(s.CONSOLE_EVICT_TITLE)
    evict_result = evict_low_score_learnings(conn, now)
    console.print(s.CONSOLE_EVICT_RESULT_FMT.format(evict_result['archived'], evict_result['remaining']))

    console.print(s.CONSOLE_PROMOTE_TITLE)
    try:
        from ..src.agent.orchestrator import AnalysisOrchestrator
        llm_mgr = getattr(svc, "_llm_manager", None)
        if llm_mgr:
            promote_result = asyncio.run(promote_learnings(conn, llm_mgr))
        else:
            promote_result = {"promoted": 0, "merged": 0, "archived": 0, "skipped": True}
            console.print(s.CONSOLE_SKIP_PROMOTE)
    except Exception as exc:
        promote_result = {"promoted": 0, "merged": 0, "archived": 0, "error": str(exc)}
        console.print(s.CONSOLE_PROMOTE_FAIL_FMT.format(exc))

    record_maintenance_telemetry(conn, "manual", evict_result, promote_result)

    if as_json:
        console.print_json(json.dumps({
            "evict": evict_result,
            "promote": promote_result,
        }, ensure_ascii=False))
    else:
        console.print(s.CONSOLE_DONE)
        console.print(s.CONSOLE_PROMOTED_FMT.format(promote_result.get('promoted', 0)))
        console.print(s.CONSOLE_MERGED_FMT.format(promote_result.get('merged', 0)))
        console.print(s.CONSOLE_ARCHIVED_FMT.format(promote_result.get('archived', 0)))


@analysis_app.command("history")
def history_cmd(
    as_json: Annotated[bool, typer.Option("--json", help=s.CLI_OPT_JSON)] = False,
) -> None:
    """查看分析历史记录。"""
    svc = _get_service()
    records = svc.get_analysis_history()

    if as_json:
        console.print_json(json.dumps(records, ensure_ascii=False, default=str))
        return

    if not records:
        console.print(s.NO_HISTORY)
        return

    table = Table(title=s.TABLE_TITLE_HISTORY)
    table.add_column(s.HISTORY_HEADER_TRACE, max_width=40)
    table.add_column(s.HISTORY_TABLE_COL_TIME)
    table.add_column(s.HISTORY_TABLE_COL_STATUS)
    for r in records:
        trace_name = Path(r.get("trace_path", "")).name or r.get("trace_id", "")
        parsed_at = r.get("parsed_at_ns", "")
        if isinstance(parsed_at, int) and parsed_at > 0:
            import datetime
            dt = datetime.datetime.fromtimestamp(parsed_at / 1e9)
            parsed_at = dt.strftime("%m-%d %H:%M")
        table.add_row(str(trace_name), str(parsed_at), s.PERFETTO_AVAILABLE_YES)
    console.print(table)
