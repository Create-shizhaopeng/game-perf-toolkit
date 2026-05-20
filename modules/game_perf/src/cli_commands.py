"""游戏性能配置模块 — CLI 命令"""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.table import Table

from toolkit.core.adb_manager import AdbManager
from toolkit.sdk.exceptions import AdbError

from . import strings_cli as sc

perf_app = typer.Typer(help=sc.CLI_HELP_ROOT)

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
        rprint(sc.RICH_ERR_NO_DEVICES)
        raise typer.Exit(1)
    return devices[0]


@perf_app.command("info")
def perf_info():
    serial = _get_serial()
    svc = _get_service()
    info = svc.get_info(serial)

    table = Table(title=sc.TABLE_TITLE_DEVICE_INFO)
    table.add_column(sc.TABLE_COL_PROPERTY, style="cyan")
    table.add_column(sc.TABLE_COL_VALUE, style="green")
    table.add_row(sc.TABLE_ROW_SERIAL, info["serial"])
    table.add_row(sc.TABLE_ROW_REMOTE_PATH, info["remote_path"])
    table.add_row(sc.TABLE_ROW_VERSION, str(info["version"]))
    table.add_row(sc.TABLE_ROW_HAS_BACKUP, sc.TABLE_YES if info["has_backup"] else sc.TABLE_NO)
    rprint(table)


perf_info.__doc__ = sc.CLI_DOC_INFO


@perf_app.command("push")
def perf_push(
    config_file: str = typer.Argument(..., help=sc.CLI_HELP_CONFIG_FILE),
    notes: str = typer.Option("", "--notes", "-n", help=sc.CLI_HELP_NOTES),
):
    serial = _get_serial()
    svc = _get_service()

    def on_progress(msg: str) -> None:
        rprint(f"  {msg}")

    try:
        from .service import XmlValidationError

        version = svc.push(serial, config_file, on_progress=on_progress, notes=notes)
        rprint(sc.RICH_PUSH_SUCCESS_FMT.format(version=version))
    except XmlValidationError as e:
        rprint(sc.RICH_ERR_FMT.format(e=e))
        for line_no, line_text, is_err in e.context.context_lines:
            prefix = "→" if is_err else " "
            style = "bold red" if is_err else "dim"
            rprint(f"  [{style}]{prefix} {line_no:>4}| {line_text}[/{style}]")
        raise typer.Exit(1)
    except AdbError as e:
        rprint(sc.RICH_ERR_FMT.format(e=e))
        raise typer.Exit(1)


@perf_app.command("reset")
def perf_reset():
    serial = _get_serial()
    svc = _get_service()

    def on_progress(msg: str) -> None:
        rprint(f"  {msg}")

    try:
        version = svc.reset(serial, on_progress=on_progress)
        rprint(sc.RICH_RESET_SUCCESS_FMT.format(version=version))
    except AdbError as e:
        rprint(sc.RICH_ERR_FMT.format(e=e))
        raise typer.Exit(1)
