import os
import re
import tempfile
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.adb_manager import AdbManager, AdbRootError, AdbNotFoundError, AdbError


@dataclass
class DeviceState:
    is_connected: bool = False
    current_brand: str = ""
    current_manufacturer: str = ""
    current_model: str = ""
    original_brand: str = ""
    original_manufacturer: str = ""
    original_model: str = ""

    @property
    def is_disguised(self) -> bool:
        if not self.is_connected:
            return False
        return (
            self.current_brand != self.original_brand
            or self.current_manufacturer != self.original_manufacturer
            or self.current_model != self.original_model
        )


class DeviceService(QThread):
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    finished_signal = pyqtSignal(object)

    def __init__(self, adb_manager: AdbManager, parent=None):
        super().__init__(parent)
        self._adb = adb_manager
        self._action: Optional[str] = None
        self._target_brand = ""
        self._target_manufacturer = ""
        self._target_model = ""

    def get_device_state(self) -> DeviceState:
        state = DeviceState()
        devices = self._adb.get_connected_devices()
        if not devices:
            return state

        state.is_connected = True
        props = self._adb.get_device_props()
        state.current_brand = props.get("ro.product.odm.brand", "")
        state.current_manufacturer = props.get("ro.product.odm.manufacturer", "")
        state.current_model = props.get("ro.product.odm.model", "")
        state.original_brand = props.get("ro.product.vendor.brand", "")
        state.original_manufacturer = props.get("ro.product.vendor.manufacturer", "")
        state.original_model = props.get("ro.product.vendor.model", "")
        return state

    def disguise(self, brand: str, manufacturer: str, model: str):
        self._action = "disguise"
        self._target_brand = brand
        self._target_manufacturer = manufacturer
        self._target_model = model
        self.start()

    def reset(self):
        self._action = "reset"
        self.start()

    def run(self):
        try:
            if self._action == "disguise":
                self._run_disguise()
            elif self._action == "reset":
                self._run_reset()
        except AdbRootError as e:
            self.error.emit(str(e))
        except AdbNotFoundError as e:
            self.error.emit(str(e))
        except AdbError as e:
            self.error.emit(f"ADB 错误: {e}")
        except Exception as e:
            self.error.emit(f"未知错误: {e}")

    def _run_disguise(self):
        props = {
            "ro.product.odm.brand": self._target_brand,
            "ro.product.odm.manufacturer": self._target_manufacturer,
            "ro.product.odm.model": self._target_model,
        }
        self._execute_modify(props, "伪装")

    def _run_reset(self):
        self.progress.emit("正在读取原始设备信息......")
        state = self.get_device_state()
        if not state.is_connected:
            self.error.emit("设备未连接")
            return

        props = {
            "ro.product.odm.brand": state.original_brand,
            "ro.product.odm.manufacturer": state.original_manufacturer,
            "ro.product.odm.model": state.original_model,
        }
        self._execute_modify(props, "重置")

    def _execute_modify(self, props: dict, action_name: str):
        self.progress.emit("设备信息修改中......")

        self.progress.emit("  adb root...")
        self._adb.run_cmd(["root"], timeout=15)
        self.progress.emit("  ✓ adb root 成功")

        self.progress.emit("  adb remount...")
        self._adb.run_cmd(["remount"], timeout=15)
        self.progress.emit("  ✓ adb remount 成功")

        self.progress.emit("  setenforce 0...")
        self._adb.run_cmd(["shell", "setenforce", "0"], timeout=10)
        self.progress.emit("  ✓ setenforce 0 成功")

        self.progress.emit("  拉取 build.prop...")
        tmp_dir = tempfile.mkdtemp()
        local_prop = os.path.join(tmp_dir, "build.prop")
        self._adb.run_cmd(["pull", "/odm/etc/build.prop", local_prop], timeout=15)
        self.progress.emit("  ✓ 拉取 build.prop 成功")

        self.progress.emit("  修改 build.prop...")
        self._modify_build_prop(local_prop, props)
        self.progress.emit("  ✓ 修改 build.prop 成功")

        self.progress.emit("  推送 build.prop...")
        self._adb.run_cmd(["push", local_prop, "/odm/etc/build.prop"], timeout=15)
        self.progress.emit("  ✓ 推送 build.prop 成功")

        self.progress.emit("正在重启设备请稍后......")
        self._adb.run_cmd(["reboot"], timeout=10)

        self.progress.emit("  等待设备重启完成...")
        self._adb.run_cmd(["wait-for-device"], timeout=120)
        self._wait_boot_completed()
        self.progress.emit("  ✓ 设备重启完成")

        self.progress.emit("  验证设备属性...")
        new_state = self.get_device_state()

        target_brand = props["ro.product.odm.brand"]
        target_mfr = props["ro.product.odm.manufacturer"]
        target_model = props["ro.product.odm.model"]

        if (new_state.current_brand == target_brand
                and new_state.current_manufacturer == target_mfr
                and new_state.current_model == target_model):
            self.progress.emit(
                f"  ✓ 设备信息{action_name}成功: "
                f"brand={target_brand}, manufacturer={target_mfr}, model={target_model}"
            )
            self.finished_signal.emit(new_state)
        else:
            self.error.emit(
                f"设备信息{action_name}验证失败: 属性值与预期不一致\n"
                f"  期望: brand={target_brand}, manufacturer={target_mfr}, model={target_model}\n"
                f"  实际: brand={new_state.current_brand}, "
                f"manufacturer={new_state.current_manufacturer}, model={new_state.current_model}"
            )

        try:
            os.unlink(local_prop)
            os.rmdir(tmp_dir)
        except OSError:
            pass

    def _modify_build_prop(self, path: str, props: dict):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        modified_keys = set()
        new_lines = []
        for line in lines:
            replaced = False
            for key, value in props.items():
                if line.strip().startswith(f"{key}="):
                    new_lines.append(f"{key}={value}\n")
                    modified_keys.add(key)
                    replaced = True
                    break
            if not replaced:
                new_lines.append(line)

        for key, value in props.items():
            if key not in modified_keys:
                new_lines.append(f"{key}={value}\n")

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    def _wait_boot_completed(self, timeout: int = 120):
        import time
        start = time.time()
        while time.time() - start < timeout:
            try:
                val = self._adb.get_prop("sys.boot_completed")
                if val == "1":
                    return
            except Exception:
                pass
            time.sleep(2)
        raise AdbError("等待设备启动超时")
