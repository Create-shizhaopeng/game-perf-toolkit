"""设备监控 — 定时轮询 ADB 检测设备连接/断开。

使用 QTimer 在 GUI 线程中轮询，避免 QThread 下的 Windows COM 线程问题。
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import QTimer, pyqtSignal, QObject

from toolkit.core.adb_manager import AdbManager

logger = logging.getLogger(__name__)


class DeviceMonitor(QObject):
    """定时检查设备连接状态变化。"""

    devices_changed = pyqtSignal(list)

    def __init__(self, adb_manager: AdbManager, interval_ms: int = 2000, parent=None) -> None:
        super().__init__(parent)
        self._adb = adb_manager
        self._interval = interval_ms
        self._last_devices: list[str] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._timer.start(self._interval)

    def stop(self) -> None:
        self._timer.stop()

    def _poll(self) -> None:
        try:
            devices = self._adb.get_connected_devices()
        except Exception:
            devices = []

        if devices != self._last_devices:
            logger.debug("设备列表变化: %s -> %s", self._last_devices, devices)
            self.devices_changed.emit(devices)
            self._last_devices = devices
