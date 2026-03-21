"""ADB 设备管理器 — 纯逻辑层，不依赖任何 GUI 框架"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from toolkit.sdk.exceptions import AdbError, DeviceNotFoundError, DeviceOfflineError

logger = logging.getLogger(__name__)


class AdbManager:
    """ADB 命令封装，提供设备发现、属性读取等能力。"""

    def __init__(self, config_adb_path: str = "") -> None:
        self._adb_path = self._resolve_adb_path(config_adb_path)
        logger.info("ADB 路径: %s", self._adb_path)

    def _resolve_adb_path(self, config_path: str) -> str:
        """按优先级查找 adb 可执行文件：系统 PATH > 用户配置 > 内置"""
        system_adb = shutil.which("adb")
        if system_adb:
            return system_adb

        if config_path and Path(config_path).is_file():
            return config_path

        bundled = Path(__file__).parent.parent.parent / "adb" / "adb.exe"
        if bundled.is_file():
            return str(bundled)

        return "adb"

    @property
    def adb_path(self) -> str:
        return self._adb_path

    def check_available(self) -> bool:
        """检查 adb 是否可用。"""
        try:
            result = self.run_cmd(["version"], timeout=5)
            return "Android Debug Bridge" in result
        except Exception:
            return False

    def get_connected_devices(self) -> list[str]:
        """返回已连接的设备序列号列表。"""
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

    def get_prop(self, key: str, serial: str | None = None) -> str:
        """获取设备属性。"""
        args = []
        if serial:
            args.extend(["-s", serial])
        args.extend(["shell", "getprop", key])
        return self.run_cmd(args, timeout=10).strip()

    def get_device_props(self, serial: str | None = None) -> dict[str, str]:
        """获取设备关键属性集合。"""
        keys = [
            "ro.product.odm.brand",
            "ro.product.odm.manufacturer",
            "ro.product.odm.model",
            "ro.product.vendor.brand",
            "ro.product.vendor.manufacturer",
            "ro.product.vendor.model",
        ]
        return {key: self.get_prop(key, serial) for key in keys}

    def get_device_info(self, serial: str) -> dict[str, str]:
        """获取单个设备的基本信息。"""
        props = self.get_device_props(serial)
        return {
            "serial": serial,
            "brand": props.get("ro.product.odm.brand", ""),
            "manufacturer": props.get("ro.product.odm.manufacturer", ""),
            "model": props.get("ro.product.odm.model", ""),
        }

    def run_cmd(self, args: list[str], timeout: int = 30) -> str:
        """执行 adb 命令并返回 stdout。"""
        cmd = [self._adb_path, *args]
        logger.debug("执行: %s", " ".join(cmd))
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=creation_flags,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                if "adbd cannot run as root" in stderr or "not allowed" in stderr.lower():
                    raise AdbError("设备无 root 权限，请使用已 root 的设备")
                raise AdbError(f"ADB 命令失败: {' '.join(args)}\n{stderr}")
            return result.stdout
        except FileNotFoundError:
            raise DeviceNotFoundError("未检测到 adb 环境，请配置 adb 环境变量") from None
        except subprocess.TimeoutExpired:
            raise AdbError(f"ADB 命令超时: {' '.join(args)}") from None
