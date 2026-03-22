"""ADB 设备管理器 — 纯逻辑层，不依赖任何 GUI 框架"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from toolkit.sdk.exceptions import AdbError, DeviceNotFoundError

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None] | None


class AdbCmdResult(NamedTuple):
    """ADB 命令原始执行结果"""

    stdout: str
    stderr: str
    returncode: int


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

    # ------------------------------------------------------------------
    # 基础命令执行
    # ------------------------------------------------------------------

    def _run_cmd_raw(
        self,
        args: list[str],
        timeout: int = 30,
        input_text: str | None = None,
    ) -> AdbCmdResult:
        """执行 adb 命令并返回原始结果（不抛异常）。

        Args:
            input_text: 通过 stdin 传入子进程的文本（UTF-8 编码），
                        用于如 ``perfetto --txt -c -`` 等需要 stdin 输入的场景。
        """
        cmd = [self._adb_path, *args]
        logger.debug("执行: %s", " ".join(cmd))
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            if input_text is not None:
                result = subprocess.run(
                    cmd,
                    input=input_text.encode("utf-8"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                    creationflags=creation_flags,
                )
                stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
                stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    creationflags=creation_flags,
                )
                stdout = result.stdout or ""
                stderr = result.stderr or ""
            return AdbCmdResult(stdout, stderr, result.returncode)
        except FileNotFoundError:
            raise DeviceNotFoundError("未检测到 adb 环境，请配置 adb 环境变量") from None
        except subprocess.TimeoutExpired:
            raise AdbError(f"ADB 命令超时: {' '.join(args)}") from None

    def run_cmd(self, args: list[str], timeout: int = 30, input_text: str | None = None) -> str:
        """执行 adb 命令并返回 stdout（向后兼容）。"""
        result = self._run_cmd_raw(args, timeout, input_text=input_text)
        stdout = result.stdout or ""
        stderr = (result.stderr or "").strip()
        if result.returncode != 0:
            if "adbd cannot run as root" in stderr or "not allowed" in stderr.lower():
                raise AdbError("设备无 root 权限，请使用已 root 的设备")
            raise AdbError(f"ADB 命令失败: {' '.join(args)}\n{stderr}")
        return stdout

    # ------------------------------------------------------------------
    # 设备发现与属性
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # 设备操作
    # ------------------------------------------------------------------

    def _serial_args(self, serial: str) -> list[str]:
        """构造 -s serial 前缀参数。"""
        return ["-s", serial]

    def root(self, serial: str) -> str:
        """获取 root 权限，自动等待 adbd 重启完成。

        - "already running as root" → 跳过等待
        - "restarting adbd as root" → 等待 adbd 重启 + wait_for_device
        - "cannot run as root" → 抛出 AdbError
        """
        result = self._run_cmd_raw(
            [*self._serial_args(serial), "root"], timeout=15
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        combined = (stdout + stderr).lower()

        if "cannot run as root" in combined or "not allowed" in combined:
            raise AdbError(
                "设备无法获取 root 权限（adbd cannot run as root）。"
                "请使用 userdebug 或 eng 版本的设备。"
            )

        if result.returncode != 0:
            raise AdbError(f"adb root 失败: {stderr.strip()}")

        if "already running as root" in combined:
            logger.debug("设备已处于 root 状态")
            return stdout

        # adbd 重启，等待设备恢复
        time.sleep(2)
        self.wait_for_device(serial, timeout=30)
        return stdout

    def remount(
        self,
        serial: str,
        on_progress: ProgressCallback = None,
    ) -> str:
        """智能 remount：自动检测是否需要重启并处理完整流程。

        流程：
        1. 执行 remount，检查 stdout + stderr
        2. 如果输出包含重启提示 → reboot → wait → root → 再次 remount
        3. 第二次仍需重启 → 抛出异常，提示 disable-verity
        """
        result = self._run_cmd_raw(
            [*self._serial_args(serial), "remount"], timeout=30
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        combined = stdout + stderr

        if result.returncode != 0 and not self._needs_reboot_for_remount(combined):
            raise AdbError(f"adb remount 失败: {stderr.strip()}")

        if self._needs_reboot_for_remount(combined):
            self._notify(on_progress, "⚠ remount 提示需要重启后生效")
            self._notify(on_progress, f"[remount] {combined.strip()[:200]}")

            self._notify(on_progress, "正在重启设备...")
            self.reboot(serial)
            self.wait_for_device(serial, timeout=120)
            self._wait_boot_completed(serial, timeout=120)
            self._notify(on_progress, "✓ 设备重启完成")

            self._notify(on_progress, "adb root (重启后)...")
            self.root(serial)
            self._notify(on_progress, "✓ adb root 成功")

            self._notify(on_progress, "adb remount (第二次)...")
            result2 = self._run_cmd_raw(
                [*self._serial_args(serial), "remount"], timeout=30
            )
            stdout2 = result2.stdout or ""
            stderr2 = result2.stderr or ""
            combined2 = stdout2 + stderr2

            if self._needs_reboot_for_remount(combined2):
                raise AdbError(
                    "remount 两次均提示需要重启，请手动执行:\n"
                    "  adb disable-verity && adb reboot\n"
                    "重启后再试。"
                )
            if result2.returncode != 0:
                raise AdbError(
                    f"重启后 remount 仍然失败: {stderr2.strip()}"
                )
            self._notify(on_progress, "✓ adb remount 成功")
            return stdout2

        self._notify(on_progress, "✓ adb remount 成功")
        return stdout

    def push(self, serial: str, local_path: str, remote_path: str) -> str:
        """将本地文件推送到设备。推送前检查本地文件是否存在。"""
        if not Path(local_path).is_file():
            raise AdbError(f"本地文件不存在: {local_path}")
        result = self._run_cmd_raw(
            [*self._serial_args(serial), "push", local_path, remote_path],
            timeout=30,
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        combined = (stdout + stderr).lower()
        if "read-only file system" in combined:
            raise AdbError(
                "文件系统仍为只读，remount 未生效。"
                "请执行 `adb disable-verity && adb reboot` 后重试。"
            )
        if result.returncode != 0:
            raise AdbError(
                f"ADB push 失败: {stderr.strip()}"
            )
        return stdout

    def pull(self, serial: str, remote_path: str, local_path: str) -> str:
        """从设备拉取文件到本地。"""
        return self.run_cmd(
            [*self._serial_args(serial), "pull", remote_path, local_path], timeout=30
        )

    def pull_raw(self, serial: str, remote_path: str, local_path: str, timeout: int = 60) -> AdbCmdResult:
        """从设备拉取文件到本地，返回完整结果（不自动抛异常）。"""
        return self._run_cmd_raw(
            [*self._serial_args(serial), "pull", remote_path, local_path], timeout=timeout
        )

    def reboot(self, serial: str) -> str:
        """重启设备。"""
        return self.run_cmd([*self._serial_args(serial), "reboot"], timeout=15)

    def wait_for_device(self, serial: str, timeout: int = 120) -> None:
        """轮询等待设备恢复到 device 状态，超时抛出异常。"""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            try:
                output = self.run_cmd(
                    [*self._serial_args(serial), "get-state"], timeout=5
                )
                if output.strip() == "device":
                    return
            except AdbError:
                pass
            time.sleep(2)
        raise AdbError(f"等待设备 {serial} 恢复超时（{timeout}s）")

    def wait_boot_completed(self, serial: str, timeout: int = 120) -> None:
        """轮询等待 sys.boot_completed == 1，超时抛出异常。"""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            try:
                val = self.get_prop("sys.boot_completed", serial)
                if val == "1":
                    return
            except AdbError:
                pass
            time.sleep(2)
        raise AdbError(f"等待设备 {serial} 启动超时（{timeout}s）")

    def shell(self, serial: str, command: str) -> str:
        """在设备上执行 shell 命令。"""
        return self.run_cmd(
            [*self._serial_args(serial), "shell", command], timeout=30
        )

    def shell_raw(
        self,
        serial: str,
        command: str,
        *,
        input_text: str | None = None,
        timeout: int = 30,
    ) -> AdbCmdResult:
        """在设备上执行 shell 命令，返回完整结果（不自动抛异常）。

        适用于需要检查 returncode/stderr 或传递 stdin 的场景，
        如 ``perfetto --background --txt -c -``。
        """
        return self._run_cmd_raw(
            [*self._serial_args(serial), "shell", command],
            timeout=timeout,
            input_text=input_text,
        )

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _needs_reboot_for_remount(output: str) -> bool:
        """检测 remount 输出（stdout+stderr）是否提示需要重启"""
        lower = output.lower()
        if "reboot" not in lower:
            return False
        return any(
            kw in lower
            for kw in ("remount", "take effect", "overlayfs", "settings")
        )

    def _wait_boot_completed(self, serial: str, timeout: int = 120) -> None:
        """内部使用的 boot completed 等待（兼容旧代码）"""
        self.wait_boot_completed(serial, timeout)

    @staticmethod
    def _notify(callback: ProgressCallback, message: str) -> None:
        if callback:
            callback(message)
