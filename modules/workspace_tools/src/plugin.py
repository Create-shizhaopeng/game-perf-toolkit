"""性能配置对比 — 插件注册入口（模块名仍为 workspace_tools）"""

from __future__ import annotations

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin


class WorkspaceToolsPlugin(BasePlugin):

    @hookimpl
    def get_plugin_info(self) -> dict:
        return {
            "name": "workspace_tools",
            "display_name": "性能配置对比",
            "version": "0.2.0",
        }

    @hookimpl
    def register_cli_commands(self, cli_app):
        from .cli_commands import workspace_app
        cli_app.add_typer(workspace_app, name="workspace")

    @hookimpl
    def register_gui_tab(self):
        from .gui_tab import WorkspaceToolsTab
        return WorkspaceToolsTab(context=self.context)

    @hookimpl
    def register_agent_tools(self) -> list:
        return []

    @hookimpl
    def on_startup(self, context: dict):
        self.context = context
        from toolkit.core.adb_manager import AdbManager

        from .gameperf_diff_service import GamePerfConfigDiffService
        from .service import WorkspaceToolsService

        context["wo_service"] = WorkspaceToolsService()

        cfg = context.get("config_manager")
        adb_path = cfg.get_adb_path() if cfg and hasattr(cfg, "get_adb_path") else ""
        adb = context.get("adb")
        if adb is None:
            adb = AdbManager(adb_path)
            context["adb"] = adb
        data_dir = context.get("data_dir")
        data_dir_s = str(data_dir) if data_dir is not None else ""
        context["wo_gameperf_diff_service"] = GamePerfConfigDiffService(adb, data_dir_s)

    @hookimpl
    def on_shutdown(self):
        pass
