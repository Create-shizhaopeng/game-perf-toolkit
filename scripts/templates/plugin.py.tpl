"""{{display_name}} — 插件注册入口"""

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin


class {{class_name}}Plugin(BasePlugin):

    @hookimpl
    def get_plugin_info(self) -> dict:
        return {
            "name": "{{module_name}}",
            "display_name": "{{display_name}}",
            "version": "0.1.0",
        }

    @hookimpl
    def register_cli_commands(self, cli_app):
        from .cli_commands import {{cli_namespace}}_app
        cli_app.add_typer({{cli_namespace}}_app, name="{{cli_namespace}}")

    @hookimpl
    def register_gui_tab(self):
        from .gui_tab import {{class_name}}Tab
        return {{class_name}}Tab()

    @hookimpl
    def register_agent_tools(self) -> list:
        return []

    @hookimpl
    def on_startup(self, context: dict):
        self.context = context

    @hookimpl
    def on_shutdown(self):
        pass
