"""设备监控线程 — 轮询 ADB 检测设备连接/断开"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QThread, pyqtSignal

from toolkit.core.adb_manager import AdbManager

logger = logging.getLogger(__name__)


class DeviceMonitor(QThread):
    """后台线程，定期检查设备连接状态变化。"""

    devices_changed = pyqtSignal(list)

    def __init__(self, adb_manager: AdbManager, interval_ms: int = 2000, parent=None) -> None:
        super().__init__(parent)
        self._adb = adb_manager
        self._interval = interval_ms
        self._running = True
        self._last_devices: list[str] = []

    def run(self) -> None:
        while self._running:
            try:
                devices = self._adb.get_connected_devices()
            except Exception:
                devices = []

            if devices != self._last_devices:
                logger.debug("设备列表变化: %s -> %s", self._last_devices, devices)
                self.devices_changed.emit(devices)
                self._last_devices = devices

            self.msleep(self._interval)

    def stop(self) -> None:
        self._running = False
        self.wait(5000)
