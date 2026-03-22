"""Perfetto 抓取模块 — 插件注册入口"""

from __future__ import annotations

import logging

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class PerfettoCapturePlugin(BasePlugin):

    @hookimpl
    def get_plugin_info(self) -> dict:
        return {
            "name": "perfetto_capture",
            "display_name": "Perfetto 抓取",
            "version": "1.0.0",
        }

    @hookimpl
    def register_cli_commands(self, cli_app):
        from .cli_commands import perfetto_app, _context
        from . import cli_commands
        cli_commands._context = self.context
        cli_app.add_typer(perfetto_app, name="perfetto")

    @hookimpl
    def register_gui_tab(self):
        from .gui_tab import PerfettoCaptureTab
        return PerfettoCaptureTab(context=self.context)

    @hookimpl
    def register_agent_tools(self) -> list:
        return []

    @hookimpl
    def on_startup(self, context: dict):
        self.context = context
        from toolkit.core.adb_manager import AdbManager
        from .service import PerfettoCaptureService

        adb = context.get("adb")
        if adb is None:
            adb = AdbManager()

        service = PerfettoCaptureService(adb=adb)
        context["pe_service"] = service
        context["pe_adb"] = adb
        logger.info("Perfetto 抓取服务已注册 (pe_service, pe_adb)")

    @hookimpl
    def on_shutdown(self):
        service = self.context.get("pe_service") if self.context else None
        if service and service.session:
            logger.info("关闭时清理: 尝试停止活动会话")
