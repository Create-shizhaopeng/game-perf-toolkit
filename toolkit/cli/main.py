"""CLI 主入口 — 根命令组定义与内置子命令"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def create_cli_app(context: dict) -> typer.Typer:
    """创建 CLI 应用实例并注册内置命令。"""
    app = typer.Typer(
        name="toolkit",
        help="LV Game Toolkit — 游戏开发测试工具集 CLI",
        no_args_is_help=True,
        rich_markup_mode="rich",
    )

    @app.command()
    def version():
        """显示版本信息"""
        from toolkit import __version__

        console.print(f"[bold]LV Game Toolkit[/bold] v{__version__}")

    config_app = typer.Typer(help="配置管理")
    app.add_typer(config_app, name="config")

    @config_app.command("get")
    def config_get(key: str = typer.Argument(..., help="配置键名（支持嵌套，如 adb.path）")):
        """获取配置值"""
        config_mgr = context.get("config_manager")
        if config_mgr:
            value = config_mgr.get(key)
            if value is not None:
                console.print(f"[bold]{key}[/bold] = {value}")
            else:
                console.print(f"[yellow]未找到配置项: {key}[/yellow]")

    @config_app.command("set")
    def config_set(
        key: str = typer.Argument(..., help="配置键名"),
        value: str = typer.Argument(..., help="配置值"),
    ):
        """设置配置值"""
        config_mgr = context.get("config_manager")
        if config_mgr:
            config_mgr.set(key, value)
            console.print(f"[green]已设置 {key} = {value}[/green]")

    @config_app.command("list")
    def config_list():
        """列出所有配置"""
        config_mgr = context.get("config_manager")
        if config_mgr:
            table = Table(title="当前配置")
            table.add_column("键", style="cyan")
            table.add_column("值", style="green")
            for k, v in config_mgr.to_dict().items():
                table.add_row(str(k), str(v))
            console.print(table)

    plugin_app = typer.Typer(help="插件管理")
    app.add_typer(plugin_app, name="plugin")

    @plugin_app.command("list")
    def plugin_list():
        """列出已加载插件"""
        pm = context.get("plugin_manager")
        if pm:
            table = Table(title="已加载模块")
            table.add_column("名称", style="cyan")
            table.add_column("版本", style="green")
            table.add_column("描述")
            for name in pm.list_loaded():
                info = pm.get_module_info(name) or {}
                table.add_row(
                    info.get("display_name", name),
                    info.get("version", "?"),
                    info.get("description", ""),
                )
            console.print(table)

    device_app = typer.Typer(help="设备管理")
    app.add_typer(device_app, name="device")

    @device_app.command("list")
    def device_list():
        """列出已连接设备"""
        from toolkit.core.adb_manager import AdbManager

        config_mgr = context.get("config_manager")
        adb_path = config_mgr.get_adb_path() if config_mgr else ""
        adb = AdbManager(adb_path)

        if not adb.check_available():
            console.print("[red]ADB 不可用，请检查环境配置[/red]")
            raise typer.Exit(1)

        devices = adb.get_connected_devices()
        if not devices:
            console.print("[yellow]无已连接设备[/yellow]")
            return

        table = Table(title="已连接设备")
        table.add_column("序列号", style="cyan")
        table.add_column("品牌", style="green")
        table.add_column("型号")
        for serial in devices:
            try:
                info = adb.get_device_info(serial)
                table.add_row(serial, info.get("brand", ""), info.get("model", ""))
            except Exception:
                table.add_row(serial, "?", "?")
        console.print(table)

    return app
