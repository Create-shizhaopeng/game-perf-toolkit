"""日志服务 — 统一日志格式和配置"""

from __future__ import annotations

import io
import logging
import sys
from pathlib import Path


def _ensure_utf8_stdout() -> None:
    """确保 stdout/stderr 使用 UTF-8 编码，解决 Windows 控制台中文乱码。

    PyInstaller --noconsole 模式下 sys.stdout/stderr 可能为 None。
    """
    if sys.stdout is not None and hasattr(sys.stdout, "encoding"):
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True,
            )
    if sys.stderr is not None and hasattr(sys.stderr, "encoding"):
        if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True,
            )


def resolve_log_level(level: int | str = logging.INFO) -> int:
    """将字符串或整数日志级别统一为 int。"""
    if isinstance(level, str):
        return getattr(logging, level.upper(), logging.INFO)
    return level


def setup_logging(level: int | str = logging.INFO, log_file: Path | None = None) -> None:
    """配置全局日志格式。

    Args:
        level: 日志级别，支持 int (logging.DEBUG) 或字符串 ("DEBUG")。
        log_file: 可选的日志文件路径。
    """
    _ensure_utf8_stdout()

    resolved = resolve_log_level(level)

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = []
    stream = sys.stdout or sys.stderr
    if stream is not None:
        handlers.append(logging.StreamHandler(stream))

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(str(log_file), encoding="utf-8"))

    logging.basicConfig(level=resolved, format=fmt, datefmt=datefmt, handlers=handlers)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
