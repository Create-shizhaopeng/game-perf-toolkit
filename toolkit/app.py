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
from toolkit.core.app_paths import get_user_config_dir, get_user_data_dir
from toolkit.core.llm.manager import LLMManager
from toolkit.core.logger import setup_logging
from toolkit.core.perf_debug import (
    MainThreadWatchdog,
    TimeIt,
    is_debug_enabled,
    set_debug_enabled,
    start_main_thread_heartbeat,
)
from toolkit.core.plugin_manager import PluginManager
from toolkit.core.service_registry import ServiceRegistry
from toolkit.core.skill_registry import SkillRegistry
from toolkit.core.unified_logger import UnifiedLogger

logger = logging.getLogger(__name__)

def _resolve_root() -> Path:
    """解析项目根目录：PyInstaller frozen 模式下使用 _MEIPASS。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent


ROOT_DIR = _resolve_root()
MODULES_DIR = ROOT_DIR / "modules"


def _build_context() -> dict:
    """构建核心服务上下文，注入到所有模块。"""
    with TimeIt("构建核心服务上下文", min_ms=500):
        config_dir = get_user_config_dir()
        data_dir = get_user_data_dir()
        config_manager = ConfigManager(config_dir / "toolkit_config.json")

        db_manager = DatabaseManager(data_dir / "db" / "toolkit.db")
        db_manager.connect()

        event_bus = EventBus()
        service_registry = ServiceRegistry()

        from toolkit.core.mcp.registry import MCPRegistry
        from toolkit.core.tool_registry import tool_registry

        return {
            "config_manager": config_manager,
            "db_manager": db_manager,
            "event_bus": event_bus,
            "service_registry": service_registry,
            "root_dir": ROOT_DIR,
            "data_dir": data_dir,
            "tool_registry": tool_registry,
            "mcp_registry": MCPRegistry(tool_registry=tool_registry),
        }


def _init_llm_manager(context: dict) -> None:
    """初始化 LLM Manager 并注入 context。需在 QApplication 创建后调用。"""
    config_manager = context["config_manager"]
    llm_manager = LLMManager(config_manager)
    service_registry = context.get("service_registry")
    if service_registry:
        llm_manager.set_service_registry(service_registry)
    context["llm_manager"] = llm_manager


def _load_plugins(context: dict) -> PluginManager:
    """发现并加载所有模块。"""
    with TimeIt("加载插件 + on_startup", min_ms=1000):
        return _load_plugins_impl(context)


def _load_plugins_impl(context: dict) -> PluginManager:
    """_load_plugins 的实际执行体（TimeIt 包裹耗时统计）。"""
    pm = PluginManager(MODULES_DIR)
    pm.load_all()

    db_manager: DatabaseManager = context["db_manager"]
    for name, manifest in pm.loaded_modules.items():
        module_path: Path = manifest["_path"]
        migrations_dir = module_path / manifest.get("database", {}).get(
            "migrations", "src/migrations/"
        )
        db_manager.run_migrations(name, migrations_dir)

    # 创建 SkillRegistry 并注入 context（供模块 startup 使用）
    skill_registry = SkillRegistry()
    context["skill_registry"] = skill_registry

    # 调用模块 startup hooks
    pm.pm.hook.on_startup(context=context)

    # 收集各模块注册的 Skill 文件路径
    skill_paths_list = pm.pm.hook.register_skills()
    all_skill_paths: list[str] = []
    for paths in skill_paths_list:
        if paths:
            all_skill_paths.extend(paths)
    skill_registry.load_skills(all_skill_paths)
    if all_skill_paths:
        logger.info("已加载 %d 个 Skill 文件", len(skill_registry.get_skills()))

    return pm


def run_gui() -> None:
    """启动 GUI 应用。"""
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    from toolkit.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Game Perf Toolkit")

    # debug 模式：主线程卡死检测（心跳定时器 + 后台 watchdog 线程）
    _heartbeat_timer = None
    _watchdog = None
    if is_debug_enabled():
        _heartbeat_timer = start_main_thread_heartbeat(app)
        _watchdog = MainThreadWatchdog(timeout_s=5.0, parent=app)
        _watchdog.start()
        logger.debug("debug 模式：主线程卡死检测已启用")

    icon_path = ROOT_DIR / "assets" / "app.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    from toolkit.gui.codicons import load_codicons
    codicons_family = load_codicons()
    if codicons_family:
        logger.info("Codicons 字体已加载: %s", codicons_family)
    else:
        logger.warning("Codicons 字体加载失败，将使用 fallback 图标")

    context = _build_context()
    _init_llm_manager(context)
    pm = _load_plugins(context)
    context["plugin_manager"] = pm

    window = MainWindow(context)

    # 启用 GUI 日志 Sink，连接 UnifiedLogger -> LogManager -> BottomPanel

    gui_sink = UnifiedLogger().enable_gui_sink(window)
    log_mgr = context.get("log_manager")
    if log_mgr is not None:
        _LEVEL_GUI_MAP = {
            "debug": "info",
            "info": "info",
            "warning": "warning",
            "error": "error",
            "critical": "error",
        }

        def _route_log_record(ts, src, msg, lvl):
            mapped = _LEVEL_GUI_MAP.get(lvl, "info")
            log_mgr.log(src, msg, level=mapped)

        gui_sink.log_record.connect(_route_log_record)

    # Agent: 改为右侧面板，不再作为 Tab 出现在导航栏中
    from toolkit.agent.gui.agent_panel import AgentPanel
    from toolkit.agent.orchestrator import AgentOrchestrator

    tool_registry = context["tool_registry"]
    tool_registry.collect_from_plugins(pm)

    # Refresh LLM provider AFTER plugins have registered their services
    llm_mgr = context.get("llm_manager")
    if llm_mgr:
        llm_mgr.refresh_provider()

    orchestrator = AgentOrchestrator(context)
    orchestrator.init()
    agent_panel = AgentPanel(orchestrator=orchestrator)
    agent_panel.set_event_bus(context.get("event_bus"))
    window.set_agent_panel_widget(agent_panel)

    # Schedule async MCP connection after event loop starts
    import asyncio

    from PyQt6.QtCore import QTimer

    def _start_mcp() -> None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.create_task(orchestrator.init_async())

    QTimer.singleShot(100, _start_mcp)

    # 模块 Tab 统一通过 add_tab() 添加到中央区域
    with TimeIt("register_gui_tab（创建模块 Tab）", min_ms=500):
        tabs = pm.pm.hook.register_gui_tab()
    for tab in tabs:
        if tab is not None and getattr(tab, "tab_title", "") != "Agent 智能助手":
            window.add_tab(tab)

    modules_info = [
        {k: v for k, v in m.items() if not k.startswith("_")}
        for m in pm.loaded_modules.values()
    ]
    window.set_module_info(modules_info)

    logger.info("GUI 模式启动（已加载 %d 个模块）", len(pm.loaded_modules))

    # 便携版数据迁移助手（仅 frozen 安装版检查；dev 模式跳过）
    if getattr(sys, "frozen", False):
        from toolkit.gui.portable_migration_dialog import PortableMigrationDialog

        if PortableMigrationDialog.should_show():
            mig_dlg = PortableMigrationDialog(window)
            mig_dlg.exec()

    window.show()

    # 后台检查更新（Velopack UpdateManager）。非 Velopack 安装环境会 RuntimeError，
    # 包在 try 内仅 debug 日志，绝不中断启动。更新应用仅在下次启动经 App().run() 生效。
    def _check_update() -> None:
        try:
            import velopack

            cfg = context.get("config_manager")
            feed = cfg.get("update_feed", "") if cfg else ""
            if not feed:
                # 未配置更新源，跳过检查（待用户在设置中配 GitHub repo URL）
                logger.debug("未配置 update_feed，跳过更新检查")
                return
            # Velopack UpdateManager 需 GithubSource（或其他 Source），非 URL 字符串
            source = velopack.GithubSource(feed)
            um = velopack.UpdateManager(source)
            update = um.check_for_updates()
            if update is not None:
                logger.info("发现新版本 %s，后台下载中...", update.target_full_version)
                um.download_updates(update)
                logger.info("更新已下载，将在下次启动生效")
            else:
                logger.debug("已是最新版本")
        except Exception as e:
            logger.debug("更新检查跳过: %s", e)

    QTimer.singleShot(3000, _check_update)

    exit_code = app.exec()

    if _watchdog is not None:
        _watchdog.stop_watchdog()

    pm.pm.hook.on_shutdown()
    context["db_manager"].close()
    sys.exit(exit_code)


def run_mcp_server(transport: str = "stdio", port: int = 8765) -> None:
    """启动 MCP server。

    在所有模块 on_startup() 完成后调用，确保 ToolRegistry 已填充。
    """
    from toolkit.core.mcp.server import run_sse, run_stdio

    context = _build_context()
    pm = _load_plugins(context)
    context["plugin_manager"] = pm

    # 初始化 LLM Manager（需要 QApplication 上下文，MCP 模式可跳过）
    _init_llm_manager(context)

    # 使用 toolkit.core 单例 ToolRegistry + ToolExecutor
    from toolkit.core.tool_executor import ToolExecutor
    from toolkit.core.tool_registry import tool_registry

    tool_registry.collect_from_plugins(pm)

    # Register skill tools for MCP server mode
    from toolkit.agent.orchestrator import AgentOrchestrator
    orch = AgentOrchestrator(context)
    orch.init()

    executor = ToolExecutor(tool_registry)

    logger.info("MCP Server 启动（transport=%s, port=%d）", transport, port)
    if transport == "sse":
        run_sse(tool_registry, executor, port=port)
    else:
        run_stdio(tool_registry, executor)

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
            config = ConfigManager(get_user_config_dir() / "toolkit_config.json")
            level_name = config.get("log_level", "INFO")
            level = getattr(_logging, str(level_name).upper(), _logging.INFO)
        except Exception:
            pass

    return level


def main() -> None:
    """应用主入口：根据命令行参数决定启动模式。

    - 无参数 → GUI 模式
    - `mcp-serve` → MCP Server 模式（stdio/sse）
    - 其他参数 → CLI 模式
    """
    # Velopack 启动钩子：应用待处理更新（可能重启进程）。
    # 必须在任何 app 启动代码之前；MCP server 模式绕过以避免中断 stdio 会话。
    # 在非 Velopack 安装环境（dev/旧 zip）为安全 no-op。
    is_mcp = len(sys.argv) > 1 and sys.argv[1] == "mcp-serve"
    if not is_mcp:
        try:
            import velopack

            velopack.App().run()
        except Exception:
            pass

    log_level = _resolve_log_level()
    setup_logging(log_level)
    set_debug_enabled(log_level <= logging.DEBUG)

    if is_mcp:
        transport = "stdio"
        port = 8765
        if "--transport" in sys.argv:
            idx = sys.argv.index("--transport")
            if idx + 1 < len(sys.argv):
                transport = sys.argv[idx + 1]
        if "--port" in sys.argv:
            idx = sys.argv.index("--port")
            if idx + 1 < len(sys.argv):
                port = int(sys.argv[idx + 1])
        run_mcp_server(transport=transport, port=port)
    else:
        run_gui()


if __name__ == "__main__":
    main()
