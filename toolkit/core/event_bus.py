"""事件总线 — 模块间松耦合通信机制"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventBus:
    """进程内事件总线，支持同步事件的发布与订阅。

    事件命名规范: {模块名}.{动作}
    例: device.connected, game_perf.config_pushed
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event: str, callback: Callable) -> None:
        """注册事件监听器。"""
        self._listeners[event].append(callback)
        logger.debug("事件监听注册: %s -> %s", event, callback.__qualname__)

    def off(self, event: str, callback: Callable) -> None:
        """移除事件监听器。"""
        try:
            self._listeners[event].remove(callback)
        except ValueError:
            logger.warning("尝试移除未注册的监听器: %s -> %s", event, callback.__qualname__)

    def emit(self, event: str, **kwargs: Any) -> None:
        """同步触发事件，按注册顺序调用所有监听器。"""
        listeners = self._listeners.get(event, [])
        if not listeners:
            return
        logger.debug("触发事件: %s (监听器数: %d)", event, len(listeners))
        for callback in listeners:
            try:
                callback(**kwargs)
            except Exception:
                logger.exception("事件处理异常: %s -> %s", event, callback.__qualname__)

    def list_events(self) -> dict[str, int]:
        """返回所有已注册事件及其监听器数量。"""
        return {event: len(cbs) for event, cbs in self._listeners.items() if cbs}

    def clear(self) -> None:
        """清除所有事件监听。"""
        self._listeners.clear()
