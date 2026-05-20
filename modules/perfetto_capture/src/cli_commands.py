"""Perfetto 抓取模块 — CLI 子命令"""

from __future__ import annotations

import json
import time
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .strings_cli import *

perfetto_app = typer.Typer(help=CLI_HELP_ROOT)
console = Console()

_context: dict | None = None


def _get_service():
    """获取已注册的 PerfettoCaptureService 实例。"""
    if _context is None or "pe_service" not in _context:
        console.print(CONSOLE_ERR_SVC_INIT)
        raise typer.Exit(1)
    return _context["pe_service"]


def _get_adb():
    if _context is None or "pe_adb" not in _context:
        console.print(CONSOLE_ERR_ADB_INIT)
        raise typer.Exit(1)
    return _context["pe_adb"]


@perfetto_app.command("info")
def info():
    """显示模块信息与当前配置概要"""
    svc = _get_service()
    info_data = svc.get_service_info()
    cfg = svc.config

    console.print(f"[bold]{info_data['display_name']}[/bold] v{info_data['version']}")
    console.print()

    table = Table(title=TABLE_TITLE_CONFIG)
    table.add_column(TABLE_COL_CONFIG, style="cyan")
    table.add_column(TABLE_COL_VALUE, style="green")
    table.add_row("Duration", f"{cfg.duration_sec}s")
    table.add_row("Buffer", f"{cfg.buffer_size_kb} KB ({cfg.buffer_size_kb // 1024} MB)")
    table.add_row("Target Mode", cfg.target.mode)
    table.add_row("Categories", TABLE_ROW_CATEGORIES_FMT.format(len(cfg.atrace_categories)))
    table.add_row("Device Trace Dir", cfg.device_trace_dir)
    table.add_row("Output Dir", cfg.output_dir)
    console.print(table)


@perfetto_app.command("start")
def start(
    serial: Optional[str] = typer.Option(None, "--serial", "-s", help=CLI_OPT_SERIAL),
    duration: Optional[int] = typer.Option(None, "--duration", "-t", help=CLI_OPT_DURATION),
    buffer: Optional[int] = typer.Option(None, "--buffer", "-b", help=CLI_OPT_BUFFER),
    output: Optional[str] = typer.Option(None, "--output", "-o", help=CLI_OPT_OUTPUT),
):
    """启动一轮 Perfetto 抓取（非交互模式: start → save → export）"""
    svc = _get_service()
    adb = _get_adb()

    if serial is None:
        devices = adb.get_connected_devices()
        if not devices:
            console.print(CONSOLE_ERR_NO_DEVICE)
            raise typer.Exit(1)
        serial = devices[0]
        console.print(CONSOLE_AUTO_SELECT_DEVICE_FMT.format(serial))

    cfg = svc.config
    if duration is not None:
        cfg = cfg.model_copy(update={"duration_sec": duration})
    if buffer is not None:
        cfg = cfg.model_copy(update={"buffer_size_kb": buffer})
    svc.config = cfg

    console.print(CONSOLE_DEVICE_FMT.format(serial))
    console.print(CONSOLE_CONFIG_FMT.format(cfg.duration_sec, cfg.buffer_size_kb))

    device_info = svc.get_device_info(serial)
    device_dir = svc.ensure_device_trace_dir(serial)

    console.print(CONSOLE_START_CAPTURE)
    session = svc.create_session(serial)
    svc.session_start_capture(serial, device_dir)

    console.print(CONSOLE_WAIT_SEC_FMT.format(cfg.duration_sec))
    time.sleep(cfg.duration_sec)

    console.print(CONSOLE_SAVE_TRACE)
    svc.session_save_trace(serial, device_dir, device_info)

    console.print(CONSOLE_EXPORTING)
    exported = svc.session_stop_and_export(
        serial,
        on_progress=lambda msg: console.print(f"  {msg}"),
    )

    console.print()
    if exported:
        console.print(CONSOLE_EXPORT_DONE)
        for p in exported:
            console.print(f"  {p}")
    else:
        console.print(CONSOLE_NO_VALID_TRACE)


config_app = typer.Typer(help=CLI_HELP_CONFIG)
perfetto_app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show():
    """显示当前完整配置"""
    svc = _get_service()
    console.print_json(svc.config.model_dump_json(indent=2))


@config_app.command("reset")
def config_reset():
    """重置为默认配置"""
    from .config_manager import reset_config
    cfg = reset_config()
    console.print(CONSOLE_CONFIG_RESET)
