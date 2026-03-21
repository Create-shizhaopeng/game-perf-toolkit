"""游戏性能配置 — 插件注册入口"""

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin


class GamePerfPlugin(BasePlugin):

    @hookimpl
    def get_plugin_info(self) -> dict:
        return {
            "name": "game_perf",
            "display_name": "游戏性能配置",
            "version": "1.0.0",
        }

    @hookimpl
    def register_cli_commands(self, cli_app):
        from .cli_commands import perf_app
        cli_app.add_typer(perf_app, name="perf")

    @hookimpl
    def register_gui_tab(self):
        from .gui_tab import GamePerfTab
        return GamePerfTab()

    @hookimpl
    def register_agent_tools(self) -> list:
        return []

    @hookimpl
    def on_startup(self, context: dict):
        self.context = context

    @hookimpl
    def on_shutdown(self):
        pass
