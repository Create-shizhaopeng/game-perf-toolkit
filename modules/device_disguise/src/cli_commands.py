"""设备伪装工具 — CLI 子命令"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

device_app = typer.Typer(help="设备伪装工具")
profile_app = typer.Typer(help="设备档案管理")
device_app.add_typer(profile_app, name="profile")

console = Console()

_service = None
_profile_mgr = None


def _get_service():
    global _service
    if _service is None:
        from toolkit.core.adb_manager import AdbManager

        from .service import DeviceDisguiseService

        _service = DeviceDisguiseService(AdbManager())
    return _service


def _get_profile_mgr():
    global _profile_mgr
    if _profile_mgr is None:
        from .models import ProfileManager

        _profile_mgr = ProfileManager()
    return _profile_mgr


def _resolve_serial(serial: str | None) -> str:
    """解析设备序列号：指定则使用，否则自动选第一个。"""
    from toolkit.core.adb_manager import AdbManager

    adb = AdbManager()
    devices = adb.get_connected_devices()
    if not devices:
        console.print("[red]✗ 未检测到已连接的设备[/red]")
        raise typer.Exit(1)
    if serial and serial not in devices:
        console.print(f"[red]✗ 设备 {serial} 未连接[/red]")
        raise typer.Exit(1)
    return serial or devices[0]


@device_app.command("status")
def status(
    serial: Optional[str] = typer.Option(None, "--serial", "-s", help="设备序列号"),
) -> None:
    """查看设备连接状态和伪装信息"""
    resolved = _resolve_serial(serial)
    svc = _get_service()
    state = svc.get_device_state(resolved)

    table = Table(title=f"设备状态 [{resolved}]")
    table.add_column("属性", style="cyan")
    table.add_column("当前值 (ODM)", style="green")
    table.add_column("原始值 (Vendor)", style="yellow")

    table.add_row("品牌", state.current_brand, state.original_brand)
    table.add_row("厂商", state.current_manufacturer, state.original_manufacturer)
    table.add_row("型号", state.current_model, state.original_model)

    console.print(table)

    if state.is_disguised:
        console.print("[bold magenta]状态: 已伪装[/bold magenta]")
    else:
        console.print("[bold green]状态: 未伪装[/bold green]")


@device_app.command("disguise")
def disguise(
    brand: str = typer.Option(..., "--brand", "-b", help="目标品牌"),
    manufacturer: str = typer.Option(..., "--manufacturer", "-m", help="目标厂商"),
    model: str = typer.Option(..., "--model", help="目标型号"),
    serial: Optional[str] = typer.Option(None, "--serial", "-s", help="设备序列号"),
) -> None:
    """执行设备信息伪装"""
    resolved = _resolve_serial(serial)
    svc = _get_service()

    def on_progress(msg: str) -> None:
        console.print(msg)

    try:
        state = svc.disguise(resolved, brand, manufacturer, model, on_progress)
        console.print("[bold green]✓ 伪装完成[/bold green]")
    except Exception as e:
        console.print(f"[bold red]✗ 伪装失败: {e}[/bold red]")
        raise typer.Exit(1)


@device_app.command("reset")
def reset(
    serial: Optional[str] = typer.Option(None, "--serial", "-s", help="设备序列号"),
) -> None:
    """还原设备信息到原始状态"""
    resolved = _resolve_serial(serial)
    svc = _get_service()

    def on_progress(msg: str) -> None:
        console.print(msg)

    try:
        state = svc.reset(resolved, on_progress)
        console.print("[bold green]✓ 还原完成[/bold green]")
    except Exception as e:
        console.print(f"[bold red]✗ 还原失败: {e}[/bold red]")
        raise typer.Exit(1)


# ------------------------------------------------------------------
# device profile 子命令
# ------------------------------------------------------------------


@profile_app.command("list")
def profile_list() -> None:
    """列出所有设备档案"""
    mgr = _get_profile_mgr()
    profiles = mgr.get_all()

    if not profiles:
        console.print("[dim]档案库为空[/dim]")
        return

    table = Table(title="设备档案库")
    table.add_column("#", style="dim")
    table.add_column("品牌", style="cyan")
    table.add_column("厂商", style="green")
    table.add_column("型号", style="yellow")
    table.add_column("备注", style="dim")

    for i, p in enumerate(profiles, 1):
        table.add_row(str(i), p.brand, p.manufacturer, p.model, p.notes)

    console.print(table)


@profile_app.command("add")
def profile_add(
    brand: str = typer.Option(..., "--brand", "-b", help="品牌"),
    manufacturer: str = typer.Option(..., "--manufacturer", "-m", help="厂商"),
    model: str = typer.Option(..., "--model", help="型号"),
    notes: str = typer.Option("", "--notes", "-n", help="备注"),
) -> None:
    """添加设备档案"""
    from .models import DeviceProfile

    mgr = _get_profile_mgr()
    try:
        mgr.add(DeviceProfile(brand=brand, manufacturer=manufacturer, model=model, notes=notes))
        console.print(f"[green]✓ 已添加: {brand}/{manufacturer}/{model}[/green]")
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)


@profile_app.command("import")
def profile_import(
    file: Path = typer.Option(..., "--file", "-f", help="JSON 文件路径", exists=True),
) -> None:
    """从 JSON 文件批量导入设备档案"""
    mgr = _get_profile_mgr()
    try:
        result = mgr.import_from(str(file))
        console.print(
            f"[green]✓ 导入完成: {result['imported']} 条导入, "
            f"{result['skipped']} 条跳过[/green]"
        )
    except (json.JSONDecodeError, FileNotFoundError) as e:
        console.print(f"[red]✗ 导入失败: {e}[/red]")
        raise typer.Exit(1)
