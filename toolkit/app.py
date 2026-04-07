"""应用引导器 — 根据启动方式选择 GUI 或 CLI 模式"""

from __future__ import annotations

import faulthandler
import logging
import os
import sys
from pathlib import Path


def _fix_frozen_stdio() -> None:
    """PyInstaller --noconsole 模式下 sys.stdout/stderr 可能为 None 或无效句柄。

    用 os.devnull 替换，防止 logging / subprocess / print 触发
    [WinError 6] ERROR_INVALID_HANDLE。
    """
    if not getattr(sys, "frozen", False):
        return
    devnull = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = devnull
    if sys.stderr is None:
        sys.stderr = devnull


_fix_frozen_stdio()

if getattr(sys, "frozen", False):
    os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "1")

if sys.stderr is not None:
    faulthandler.enable()

from toolkit.core.config_manager import ConfigManager
from toolkit.core.db_manager import DatabaseManager
from toolkit.core.event_bus import EventBus
from toolkit.core.llm.manager import LLMManager
from toolkit.core.logger import setup_logging
from toolkit.core.plugin_manager import PluginManager
from toolkit.core.service_registry import ServiceRegistry

logger = logging.getLogger(__name__)

def _resolve_root() -> Path:
    """解析项目根目录：PyInstaller frozen 模式下使用 _MEIPASS。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent


ROOT_DIR = _resolve_root()
MODULES_DIR = ROOT_DIR / "modules"
DATA_DIR = Path(sys.executable).parent / "data" if getattr(sys, "frozen", False) else ROOT_DIR / "data"


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


def _init_llm_manager(context: dict) -> None:
    """初始化 LLM Manager 并注入 context。需在 QApplication 创建后调用。"""
    config_manager = context["config_manager"]
    llm_manager = LLMManager(config_manager)
    context["llm_manager"] = llm_manager


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

    from PyQt6.QtGui import QIcon

    app = QApplication(sys.argv)
    app.setApplicationName("LV Game Toolkit")

    icon_path = ROOT_DIR / "assets" / "app.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    context = _build_context()
    _init_llm_manager(context)
    pm = _load_plugins(context)
    context["plugin_manager"] = pm

    window = MainWindow(context)

    tabs = pm.pm.hook.register_gui_tab()
    agent_tab = None
    other_tabs = []
    for tab in tabs:
        if tab is not None:
            if getattr(tab, "tab_title", "") == "Agent 智能助手":
                agent_tab = tab
            else:
                other_tabs.append(tab)
    if agent_tab:
        window.add_tab(agent_tab)
    for tab in other_tabs:
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
