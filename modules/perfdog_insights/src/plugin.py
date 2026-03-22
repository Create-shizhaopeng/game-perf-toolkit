"""PerfDog 分析 — 插件注册入口"""

from __future__ import annotations

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin


class PerfdogInsightsPlugin(BasePlugin):

    @hookimpl
    def get_plugin_info(self) -> dict:
        return {
            "name": "perfdog_insights",
            "display_name": "PerfDog分析",
            "version": "0.1.0",
        }

    @hookimpl
    def register_cli_commands(self, cli_app):
        from .cli_commands import perfdog_app

        cli_app.add_typer(perfdog_app, name="perfdog")

    @hookimpl
    def register_gui_tab(self):
        from .gui_tab import PerfdogInsightsTab

        return PerfdogInsightsTab(context=self.context)

    @hookimpl
    def register_agent_tools(self) -> list:
        return []

    @hookimpl
    def on_startup(self, context: dict) -> None:
        self.context = context
        from .service import PerfdogInsightsService

        self.context["pdi_service"] = PerfdogInsightsService()

    @hookimpl
    def on_shutdown(self) -> None:
        pass
