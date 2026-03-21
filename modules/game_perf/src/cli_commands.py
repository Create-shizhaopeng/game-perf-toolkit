"""游戏性能配置模块 — CLI 命令"""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.table import Table

from toolkit.core.adb_manager import AdbManager
from toolkit.sdk.exceptions import AdbError

perf_app = typer.Typer(help="游戏性能配置管理")

_service = None
_adb = None


def _get_adb() -> AdbManager:
    global _adb
    if _adb is None:
        _adb = AdbManager()
    return _adb


def _get_service():
    global _service
    if _service is None:
        import os
        from .service import GamePerfService

        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )
        _service = GamePerfService(_get_adb(), data_dir)
    return _service


def _get_serial() -> str:
    adb = _get_adb()
    devices = adb.get_connected_devices()
    if not devices:
        rprint("[red]✗ 未检测到已连接的设备[/red]")
        raise typer.Exit(1)
    return devices[0]


@perf_app.command("info")
def perf_info():
    """查看设备上的 gameperfconfig 信息"""
    serial = _get_serial()
    svc = _get_service()
    info = svc.get_info(serial)

    table = Table(title="设备性能配置信息")
    table.add_column("属性", style="cyan")
    table.add_column("值", style="green")
    table.add_row("设备序列号", info["serial"])
    table.add_row("配置文件路径", info["remote_path"])
    table.add_row("当前 version", str(info["version"]))
    table.add_row("有备份", "是" if info["has_backup"] else "否")
    rprint(table)


@perf_app.command("push")
def perf_push(
    config_file: str = typer.Argument(..., help="gameperfconfig XML 文件路径"),
    notes: str = typer.Option("", "--notes", "-n", help="推送备注"),
):
    """推送性能配置文件到设备"""
    serial = _get_serial()
    svc = _get_service()

    def on_progress(msg: str) -> None:
        rprint(f"  {msg}")

    try:
        from .service import XmlValidationError

        version = svc.push(serial, config_file, on_progress=on_progress, notes=notes)
        rprint(f"\n[green]✓ 推送成功，设备 version = {version}[/green]")
    except XmlValidationError as e:
        rprint(f"\n[red]✗ {e}[/red]")
        for line_no, line_text, is_err in e.context.context_lines:
            prefix = "→" if is_err else " "
            style = "bold red" if is_err else "dim"
            rprint(f"  [{style}]{prefix} {line_no:>4}| {line_text}[/{style}]")
        raise typer.Exit(1)
    except AdbError as e:
        rprint(f"\n[red]✗ {e}[/red]")
        raise typer.Exit(1)


@perf_app.command("reset")
def perf_reset():
    """将设备配置还原为推送前的备份"""
    serial = _get_serial()
    svc = _get_service()

    def on_progress(msg: str) -> None:
        rprint(f"  {msg}")

    try:
        version = svc.reset(serial, on_progress=on_progress)
        rprint(f"\n[green]✓ 还原成功，设备 version = {version}[/green]")
    except AdbError as e:
        rprint(f"\n[red]✗ {e}[/red]")
        raise typer.Exit(1)
