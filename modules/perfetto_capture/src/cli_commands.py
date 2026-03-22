"""Perfetto 抓取模块 — CLI 子命令"""

from __future__ import annotations

import json
import time
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

perfetto_app = typer.Typer(help="Perfetto 卡顿抓取")
console = Console()

_context: dict | None = None


def _get_service():
    """获取已注册的 PerfettoCaptureService 实例。"""
    if _context is None or "pe_service" not in _context:
        console.print("[red]错误: Perfetto 服务未初始化[/red]")
        raise typer.Exit(1)
    return _context["pe_service"]


def _get_adb():
    if _context is None or "pe_adb" not in _context:
        console.print("[red]错误: ADB 服务未初始化[/red]")
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

    table = Table(title="当前配置")
    table.add_column("配置项", style="cyan")
    table.add_column("值", style="green")
    table.add_row("Duration", f"{cfg.duration_sec}s")
    table.add_row("Buffer", f"{cfg.buffer_size_kb} KB ({cfg.buffer_size_kb // 1024} MB)")
    table.add_row("Target Mode", cfg.target.mode)
    table.add_row("Categories", f"{len(cfg.atrace_categories)} 项")
    table.add_row("Device Trace Dir", cfg.device_trace_dir)
    table.add_row("Output Dir", cfg.output_dir)
    console.print(table)


@perfetto_app.command("start")
def start(
    serial: Optional[str] = typer.Option(None, "--serial", "-s", help="设备序列号"),
    duration: Optional[int] = typer.Option(None, "--duration", "-t", help="保存窗口(秒)"),
    buffer: Optional[int] = typer.Option(None, "--buffer", "-b", help="缓冲区大小(KB)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="输出目录"),
):
    """启动一轮 Perfetto 抓取（非交互模式: start → save → export）"""
    svc = _get_service()
    adb = _get_adb()

    if serial is None:
        devices = adb.get_connected_devices()
        if not devices:
            console.print("[red]未检测到已连接设备[/red]")
            raise typer.Exit(1)
        serial = devices[0]
        console.print(f"自动选择设备: {serial}")

    cfg = svc.config
    if duration is not None:
        cfg = cfg.model_copy(update={"duration_sec": duration})
    if buffer is not None:
        cfg = cfg.model_copy(update={"buffer_size_kb": buffer})
    svc.config = cfg

    console.print(f"[bold]设备:[/bold] {serial}")
    console.print(f"[bold]配置:[/bold] duration={cfg.duration_sec}s, buffer={cfg.buffer_size_kb}KB")

    device_info = svc.get_device_info(serial)
    device_dir = svc.ensure_device_trace_dir(serial)

    console.print("[bold green]▶ 开始抓取...[/bold green]")
    session = svc.create_session(serial)
    svc.session_start_capture(serial, device_dir)

    console.print(f"等待 {cfg.duration_sec} 秒...")
    time.sleep(cfg.duration_sec)

    console.print("[bold yellow]⏹ 保存 trace...[/bold yellow]")
    svc.session_save_trace(serial, device_dir, device_info)

    console.print("[bold blue]■ 导出中...[/bold blue]")
    exported = svc.session_stop_and_export(
        serial,
        on_progress=lambda msg: console.print(f"  {msg}"),
    )

    console.print()
    if exported:
        console.print("[bold green]✓ 导出完成:[/bold green]")
        for p in exported:
            console.print(f"  {p}")
    else:
        console.print("[yellow]本次抓取未保存有效 trace[/yellow]")


config_app = typer.Typer(help="配置管理")
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
    console.print("[green]✓ 已重置为默认配置[/green]")
