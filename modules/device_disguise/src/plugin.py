"""设备伪装工具 — 插件注册入口"""

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin


class DeviceDisguisePlugin(BasePlugin):

    @hookimpl
    def get_plugin_info(self) -> dict:
        return {
            "name": "device_disguise",
            "display_name": "设备伪装工具",
            "version": "1.0.0",
        }

    @hookimpl
    def register_cli_commands(self, cli_app):
        from .cli_commands import device_app
        cli_app.add_typer(device_app, name="device")

    @hookimpl
    def register_gui_tab(self):
        from .gui_tab import DeviceDisguiseTab
        return DeviceDisguiseTab()

    @hookimpl
    def register_agent_tools(self) -> list:
        return []

    @hookimpl
    def on_startup(self, context: dict):
        self.context = context

    @hookimpl
    def on_shutdown(self):
        pass
