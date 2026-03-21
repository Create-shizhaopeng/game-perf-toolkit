"""应用引导器 — 根据启动方式选择 GUI 或 CLI 模式"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from toolkit.core.config_manager import ConfigManager
from toolkit.core.db_manager import DatabaseManager
from toolkit.core.event_bus import EventBus
from toolkit.core.logger import setup_logging
from toolkit.core.plugin_manager import PluginManager
from toolkit.core.service_registry import ServiceRegistry

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
MODULES_DIR = ROOT_DIR / "modules"
DATA_DIR = ROOT_DIR / "data"


def _build_context() -> dict:
    """构建核心服务上下文，注入到所有模块。"""
    config_manager = ConfigManager(DATA_DIR / "config.json")

    db_manager = DatabaseManager(DATA_DIR / "toolkit.db")
    db_manager.connect()

    event_bus = EventBus()
    service_registry = ServiceRegistry()

    return {
        "config_manager": config_manager,
        "db_manager": db_manager,
        "event_bus": event_bus,
        "service_registry": service_registry,
        "root_dir": ROOT_DIR,
        "data_dir": DATA_DIR,
    }


def _load_plugins(context: dict) -> PluginManager:
    """发现并加载所有模块。"""
    pm = PluginManager(MODULES_DIR)
    pm.load_all()

    db_manager: DatabaseManager = context["db_manager"]
    for name, manifest in pm.loaded_modules.items():
        module_path: Path = manifest["_path"]
        migrations_dir = module_path / manifest.get("database", {}).get(
            "migrations", "src/migrations/"
        )
        db_manager.run_migrations(name, migrations_dir)

    pm.pm.hook.on_startup(context=context)
    return pm


def run_gui() -> None:
    """启动 GUI 应用。"""
    from PyQt6.QtWidgets import QApplication

    from toolkit.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("LV Game Toolkit")

    context = _build_context()
    pm = _load_plugins(context)
    context["plugin_manager"] = pm

    window = MainWindow(context)

    tabs = pm.pm.hook.register_gui_tab()
    for tab in tabs:
        if tab is not None:
            window.add_tab(tab)

    modules_info = [
        {k: v for k, v in m.items() if not k.startswith("_")}
        for m in pm.loaded_modules.values()
    ]
    window.set_module_info(modules_info)

    logger.info("GUI 模式启动（已加载 %d 个模块）", len(pm.loaded_modules))
    window.show()
    exit_code = app.exec()

    pm.pm.hook.on_shutdown()
    context["db_manager"].close()
    sys.exit(exit_code)


def run_cli() -> None:
    """启动 CLI 应用。"""
    from toolkit.cli.main import create_cli_app

    context = _build_context()
    pm = _load_plugins(context)
    context["plugin_manager"] = pm

    cli_app = create_cli_app(context)
    pm.pm.hook.register_cli_commands(cli_app=cli_app)

    cli_app()

    pm.pm.hook.on_shutdown()
    context["db_manager"].close()


def _resolve_log_level() -> int:
    """解析日志级别：CLI 参数 > config.json > 默认 INFO。"""
    import logging as _logging

    cli_override = False
    level = _logging.INFO

    for flag in ("--debug", "--verbose", "-v"):
        if flag in sys.argv:
            level = _logging.DEBUG
            cli_override = True
            sys.argv.remove(flag)

    if not cli_override:
        try:
            config = ConfigManager(DATA_DIR / "config.json")
            level_name = config.get("log_level", "INFO")
            level = getattr(_logging, str(level_name).upper(), _logging.INFO)
        except Exception:
            pass

    return level


def main() -> None:
    """应用主入口：根据是否有命令行参数决定启动模式。"""
    log_level = _resolve_log_level()
    setup_logging(log_level)

    if len(sys.argv) > 1:
        run_cli()
    else:
        run_gui()


if __name__ == "__main__":
    main()
