"""游戏性能配置模块 — 插件注册入口"""

from __future__ import annotations

import logging
import os

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class GamePerfPlugin(BasePlugin):

    def __init__(self) -> None:
        super().__init__()
        self._service = None

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

        tab = GamePerfTab(context=self.context)
        return tab

    @hookimpl
    def register_agent_tools(self) -> list:
        if not self._service:
            return []
        return [
            {
                "name": "perf_push",
                "description": "推送性能配置文件到设备",
                "method": self._service.push,
            },
            {
                "name": "perf_reset",
                "description": "将设备性能配置还原为备份版本",
                "method": self._service.reset,
            },
            {
                "name": "perf_info",
                "description": "查询设备上的性能配置信息",
                "method": self._service.get_info,
            },
        ]

    @hookimpl
    def on_startup(self, context: dict):
        self.context = context

        from toolkit.core.adb_manager import AdbManager
        from .service import GamePerfService

        adb: AdbManager = context.get("adb")
        if adb is None:
            adb = AdbManager()

        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )
        os.makedirs(data_dir, exist_ok=True)

        self._service = GamePerfService(adb, data_dir)

        db_manager = context.get("db_manager")
        if db_manager is not None:
            self._run_migrations(db_manager)

        self.context["gp_adb"] = adb
        self.context["gp_service"] = self._service
        self.context["gp_data_dir"] = data_dir

    @hookimpl
    def on_shutdown(self):
        pass

    @staticmethod
    def _run_migrations(db_manager) -> None:
        try:
            db_manager.execute("""
                CREATE TABLE IF NOT EXISTS perf_push_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game TEXT NOT NULL,
                    package TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    notes TEXT DEFAULT '',
                    version INTEGER DEFAULT 0,
                    json_path TEXT DEFAULT '',
                    saved_at TEXT NOT NULL
                )
            """)
        except Exception as e:
            logger.warning("perf_push_history 表创建失败: %s", e)
