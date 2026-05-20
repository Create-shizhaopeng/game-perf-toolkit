"""统一日志框架 — 基于 loguru 的三层路由日志系统。

将 Python 标准 logging、终端输出、GUI 面板和文件持久化统一为一个入口。
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from loguru import logger


class _InterceptHandler(logging.Handler):
    """拦截标准库 logging 的所有记录，转发到 loguru。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).bind(
            logger_name=record.name
        ).log(level, record.getMessage())


class _GUISink(QObject):
    """线程安全 GUI 日志 Sink — 将 loguru 记录通过 pyqtSignal 推送到 LogManager。

    write() 可在任意线程调用，pyqtSignal 通过 QueuedConnection
    自动将日志排队到接收者（GUI 主线程）处理，无需自行管理 QTimer。
    """

    log_record = pyqtSignal(str, str, str, str)  # ts, source, msg, level

    def write(self, message: str) -> None:
        """loguru sink 回调接口 — 解析格式化的 tab 分隔字符串并 emit。"""
        parts = message.strip().split("\t", 3)
        if len(parts) >= 4:
            ts, level, source, msg = parts
        elif len(parts) == 3:
            ts, level, source = parts
            msg = ""
        else:
            ts = datetime.now().strftime("%H:%M:%S")
            level = "info"
            source = "控制台"
            msg = message.strip()

        self.log_record.emit(ts, source, msg, level.lower())

    def stop(self) -> None:
        """清理资源。"""
        pass


class UnifiedLogger:
    """统一日志单例 — 管理 loguru 的所有 sink 配置。

    提供：
    - 终端输出（stdout）
    - 文件持久化（按天轮转）
    - GUI 面板桥接（GUISink，可后期启用）
    - 模块级独立日志文件（opt-in）
    """

    _instance: "UnifiedLogger | None" = None
    _initialized = False

    # 级别映射：standard logging -> loguru level
    _LEVEL_MAP = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def __new__(cls) -> "UnifiedLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if UnifiedLogger._initialized:
            return
        UnifiedLogger._initialized = True

        self._gui_sink: _GUISink | None = None
        self._gui_sink_id: int | None = None
        self._module_sinks: dict[str, int] = {}
        self._log_dir: Path | None = None
        self._base_level: str = "INFO"

    def setup(
        self,
        level: int | str = logging.INFO,
        log_dir: Path | None = None,
    ) -> None:
        """初始化基础日志系统（终端 + 文件）。

        GUI sink 需通过 enable_gui_sink() 在 QApplication 创建后启用。

        Args:
            level: 全局日志级别（int logging level 或字符串如 "INFO"）
            log_dir: 日志文件目录（默认 data/logs/）
        """
        self._base_level = self._resolve_level(level)

        # 移除默认 sink
        logger.remove()

        # 全局 patcher：确保 extra 字段存在（避免 KeyError）
        def _patch(record):
            record["extra"].setdefault("module", "控制台")
            record["extra"].setdefault("logger_name", record.get("name", "控制台"))

        logger.configure(patcher=_patch)

        # 1. 终端 sink
        logger.add(
            sys.stdout,
            level=self._base_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | <level>{level: <8}</level> | {extra[logger_name]: <20} | {message}",
            filter=lambda r: r["extra"].get("_console", True),
            colorize=True,
        )

        # 2. 文件 sink（主日志）
        if log_dir is None:
            log_dir = Path.cwd() / "data" / "logs"
        self._log_dir = log_dir
        log_dir.mkdir(parents=True, exist_ok=True)

        logger.add(
            str(log_dir / "app_{time:YYYY-MM-DD}.log"),
            level=self._base_level,
            rotation="1 day",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[module]: <20} | {message}",
        )

        # 3. 接管标准库 logging
        logging.basicConfig(
            handlers=[_InterceptHandler()], level=level, force=True
        )

    def enable_gui_sink(self, parent: QObject) -> _GUISink:
        """在 QApplication 创建后启用 GUISink。

        Args:
            parent: GUI 父 QObject（通常传入 MainWindow 或 BottomPanel）

        Returns:
            GUISink 实例，外部需连接其 log_record 信号到 LogManager
        """
        if self._gui_sink is not None:
            return self._gui_sink

        self._gui_sink = _GUISink(parent)
        self._gui_sink_id = logger.add(
            self._gui_sink,
            level=self._base_level,
            format="{message}",  # GUISink 自行格式化
        )
        return self._gui_sink

    def get_gui_sink(self) -> "_GUISink | None":
        """返回 GUISink 实例（供 MainWindow 连接信号使用）。"""
        return self._gui_sink

    def add_module_sink(
        self, module_name: str, level: int | str = logging.INFO
    ) -> None:
        """为指定模块注册独立的日志文件 sink。

        Args:
            module_name: 模块标识名（用于文件名和 extra["module"] 过滤）
            level: 该 sink 的日志级别
        """
        if self._log_dir is None:
            raise RuntimeError(
                "UnifiedLogger.setup() 必须在 add_module_sink() 之前调用"
            )

        if module_name in self._module_sinks:
            return

        resolved = self._resolve_level(level)
        sink_id = logger.add(
            str(self._log_dir / f"{module_name}_{{time:YYYY-MM-DD}}.log"),
            level=resolved,
            rotation="1 day",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
            filter=lambda r, mn=module_name: r["extra"].get("module") == mn,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        )
        self._module_sinks[module_name] = sink_id

    def remove_module_sink(self, module_name: str) -> None:
        """移除模块级 sink。"""
        sink_id = self._module_sinks.pop(module_name, None)
        if sink_id is not None:
            logger.remove(sink_id)

    @staticmethod
    def bind_module(module_name: str) -> Any:
        """返回已绑定 module 字段的 logger，供模块使用。

        用法::
            log = UnifiedLogger.bind_module("perfetto_analysis")
            log.info("开始分析", trace_id="abc123")
        """
        return logger.bind(module=module_name)

    @staticmethod
    def _resolve_level(level: int | str) -> str:
        if isinstance(level, int):
            return UnifiedLogger._LEVEL_MAP.get(level, "INFO")
        if isinstance(level, str):
            return level.upper()
        return "INFO"

    def shutdown(self) -> None:
        """关闭所有 sink 和 GUISink。"""
        if self._gui_sink is not None:
            self._gui_sink.stop()
            self._gui_sink = None
        if self._gui_sink_id is not None:
            logger.remove(self._gui_sink_id)
            self._gui_sink_id = None
        for sink_id in list(self._module_sinks.values()):
            logger.remove(sink_id)
        self._module_sinks.clear()
        logger.remove()


# 兼容旧接口：保持 setup_logging / resolve_log_level 可用
_setup_once = False


def setup_logging(
    level: int | str = logging.INFO, log_file: Path | None = None
) -> None:
    """兼容旧接口，初始化统一日志系统。

    Args:
        level: 日志级别
        log_file: 已废弃参数（保留兼容），文件日志统一由 UnifiedLogger 管理
    """
    global _setup_once
    if _setup_once:
        return
    _setup_once = True

    log_dir = Path(log_file).parent if log_file else None
    UnifiedLogger().setup(level=level, log_dir=log_dir)


def resolve_log_level(level: int | str = logging.INFO) -> int:
    """将字符串或整数日志级别统一为 int。（兼容旧接口）"""
    if isinstance(level, str):
        return getattr(logging, level.upper(), logging.INFO)
    return level
