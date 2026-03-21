import os
import shutil
import subprocess
import re
from typing import List, Optional, Dict

from PyQt6.QtCore import QThread, pyqtSignal


class AdbError(Exception):
    pass


class AdbRootError(AdbError):
    pass


class AdbNotFoundError(AdbError):
    pass


class AdbManager:
    def __init__(self, config_adb_path: str = ""):
        self._adb_path = self._resolve_adb_path(config_adb_path)

    def _resolve_adb_path(self, config_path: str) -> str:
        system_adb = shutil.which("adb")
        if system_adb:
            return system_adb

        if config_path and os.path.isfile(config_path):
            return config_path

        bundled = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "adb", "adb.exe"
        )
        if os.path.isfile(bundled):
            return bundled

        return "adb"

    def check_adb_available(self) -> bool:
        try:
            result = self.run_cmd(["version"], timeout=5)
            return "Android Debug Bridge" in result
        except Exception:
            return False

    def get_connected_devices(self) -> List[str]:
        try:
            output = self.run_cmd(["devices"], timeout=5)
        except Exception:
            return []

        devices = []
        for line in output.strip().splitlines()[1:]:
            parts = line.strip().split("\t")
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices

    def get_prop(self, key: str) -> str:
        output = self.run_cmd(["shell", "getprop", key], timeout=10)
        return output.strip()

    def get_device_props(self) -> Dict[str, str]:
        props = {}
        keys = [
            "ro.product.odm.brand",
            "ro.product.odm.manufacturer",
            "ro.product.odm.model",
            "ro.product.vendor.brand",
            "ro.product.vendor.manufacturer",
            "ro.product.vendor.model",
        ]
        for key in keys:
            props[key] = self.get_prop(key)
        return props

    def run_cmd(self, args: List[str], timeout: int = 30) -> str:
        cmd = [self._adb_path] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                if "adbd cannot run as root" in stderr or "not allowed" in stderr.lower():
                    raise AdbRootError("设备无 root 权限，请使用已 root 的设备")
                raise AdbError(f"ADB 命令失败: {' '.join(args)}\n{stderr}")
            return result.stdout
        except FileNotFoundError:
            raise AdbNotFoundError("未检测到 adb 环境，请配置 adb 环境变量")
        except subprocess.TimeoutExpired:
            raise AdbError(f"ADB 命令超时: {' '.join(args)}")


class DeviceMonitor(QThread):
    device_connected = pyqtSignal(str)
    device_disconnected = pyqtSignal()

    def __init__(self, adb_manager: AdbManager, parent=None):
        super().__init__(parent)
        self._adb = adb_manager
        self._running = True
        self._last_devices: List[str] = []

    def run(self):
        while self._running:
            try:
                devices = self._adb.get_connected_devices()
            except Exception:
                devices = []

            if devices and not self._last_devices:
                self.device_connected.emit(devices[0])
            elif not devices and self._last_devices:
                self.device_disconnected.emit()
            elif devices and self._last_devices and devices[0] != self._last_devices[0]:
                self.device_disconnected.emit()
                self.device_connected.emit(devices[0])

            self._last_devices = devices
            self.msleep(2000)

    def stop(self):
        self._running = False
        self.wait(5000)
