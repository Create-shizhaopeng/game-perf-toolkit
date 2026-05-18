# -*- coding: utf-8 -*-
"""中央日志路由 — 所有模块日志的统一分发入口。

模块通过 BaseTab._log() 调用 LogManager.log()，
BottomPanel 订阅 log_added 信号实现实时展示。
"""

from __future__ import annotations

import datetime
from collections import deque
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class LogEntry:
    """一条日志记录。"""
    timestamp: str
    source: str
    message: str
    level: str


class LogManager(QObject):
    """中央日志管理器 — 接收各模块日志并广播给订阅者。

    Signals:
        log_added(timestamp, source, message, level)
        error_logged()  — 仅在 error/warning 时触发，用于自动弹出底部面板
        source_registered(source_name)  — 新日志源首次出现
    """

    log_added = pyqtSignal(str, str, str, str)
    error_logged = pyqtSignal()
    source_registered = pyqtSignal(str)

    _MAX_ENTRIES = 5000

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._entries: deque[LogEntry] = deque(maxlen=self._MAX_ENTRIES)
        self._sources: list[str] = []

    def log(self, source: str, msg: str, *, level: str = "info") -> None:
        """记录一条日志并广播。"""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        entry = LogEntry(timestamp=ts, source=source, message=msg, level=level)
        self._entries.append(entry)

        if source not in self._sources:
            self._sources.append(source)
            self.source_registered.emit(source)

        self.log_added.emit(ts, source, msg, level)

        if level in ("error", "warning"):
            self.error_logged.emit()

    def clear(self, source: str | None = None) -> None:
        """清除日志。source 为 None 时清除全部。"""
        if source is None:
            self._entries.clear()
        else:
            self._entries = deque(
                (e for e in self._entries if e.source != source),
                maxlen=self._MAX_ENTRIES,
            )

    def get_sources(self) -> list[str]:
        """返回已注册的日志源列表（按首次出现顺序）。"""
        return list(self._sources)

    def get_entries(
        self,
        source: str | None = None,
        levels: set[str] | None = None,
    ) -> list[LogEntry]:
        """返回过滤后的日志条目（用于面板打开时回填）。"""
        result = list(self._entries)
        if source is not None:
            result = [e for e in result if e.source == source]
        if levels is not None:
            result = [e for e in result if e.level in levels]
        return result
