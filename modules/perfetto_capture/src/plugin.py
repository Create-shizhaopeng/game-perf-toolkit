"""Perfetto卡顿抓取 — 插件注册入口"""

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin


class PerfettoCapturePlugin(BasePlugin):

    @hookimpl
    def get_plugin_info(self) -> dict:
        return {
            "name": "perfetto_capture",
            "display_name": "Perfetto卡顿抓取",
            "version": "0.1.0",
        }

    @hookimpl
    def register_cli_commands(self, cli_app):
        from .cli_commands import perfetto_app
        cli_app.add_typer(perfetto_app, name="perfetto")

    @hookimpl
    def register_gui_tab(self):
        from .gui_tab import PerfettoCaptureTab
        return PerfettoCaptureTab()

    @hookimpl
    def register_agent_tools(self) -> list:
        return []

    @hookimpl
    def on_startup(self, context: dict):
        self.context = context
        # 使用模块前缀注册 context 键，避免跨模块冲突
        # context["perfetto_capture_service"] = PerfettoCaptureService(...)

    @hookimpl
    def on_shutdown(self):
        pass
