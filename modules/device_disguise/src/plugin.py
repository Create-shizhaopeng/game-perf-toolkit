"""设备伪装工具 — 插件注册入口"""

from __future__ import annotations

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin


class DeviceDisguisePlugin(BasePlugin):

    def __init__(self) -> None:
        super().__init__()
        self._service = None
        self._profile_mgr = None

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

        tab = DeviceDisguiseTab(context=self.context)
        return tab

    @hookimpl
    def register_agent_tools(self) -> list:
        if not self._service:
            return []
        return [
            {
                "name": "device_status",
                "description": "获取设备连接状态和伪装信息",
                "method": self._service.get_device_state,
            },
            {
                "name": "device_disguise",
                "description": "执行设备信息伪装",
                "method": self._service.disguise,
            },
            {
                "name": "device_reset",
                "description": "还原设备信息到原始状态",
                "method": self._service.reset,
            },
        ]

    @hookimpl
    def on_startup(self, context: dict):
        self.context = context

        from toolkit.core.adb_manager import AdbManager

        from .models import ProfileManager
        from .service import DeviceDisguiseService

        adb: AdbManager = context.get("adb")
        if adb is None:
            adb = AdbManager()

        self._service = DeviceDisguiseService(adb)
        self._profile_mgr = ProfileManager()

        self.context["dd_adb"] = adb
        self.context["dd_service"] = self._service
        self.context["dd_profile_mgr"] = self._profile_mgr

    @hookimpl
    def on_shutdown(self):
        pass
