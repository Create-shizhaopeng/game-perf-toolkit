"""设备伪装工具 — 服务层（纯同步，不依赖 GUI 框架）"""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from toolkit.core.adb_manager import AdbManager
from toolkit.sdk.exceptions import AdbError
from toolkit.sdk.models import DeviceState

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None] | None


class DeviceDisguiseService:
    """设备伪装核心业务逻辑。

    所有方法均为同步调用。GUI 层应在 QThread 中调用本服务，
    CLI 和 Agent 可直接调用。
    """

    def __init__(self, adb: AdbManager) -> None:
        self._adb = adb

    def get_service_info(self) -> dict:
        return {"name": "device_disguise", "display_name": "设备伪装工具"}

    # ------------------------------------------------------------------
    # FR-001: 获取设备状态
    # ------------------------------------------------------------------

    def get_device_state(self, serial: str) -> DeviceState:
        """读取设备 ODM/vendor 属性，返回 DeviceState。"""
        props = self._adb.get_device_props(serial)
        return DeviceState(
            is_connected=True,
            current_brand=props.get("ro.product.odm.brand", ""),
            current_manufacturer=props.get("ro.product.odm.manufacturer", ""),
            current_model=props.get("ro.product.odm.model", ""),
            original_brand=props.get("ro.product.vendor.brand", ""),
            original_manufacturer=props.get("ro.product.vendor.manufacturer", ""),
            original_model=props.get("ro.product.vendor.model", ""),
        )

    # ------------------------------------------------------------------
    # FR-002: 伪装
    # ------------------------------------------------------------------

    def disguise(
        self,
        serial: str,
        brand: str,
        manufacturer: str,
        model: str,
        on_progress: ProgressCallback = None,
    ) -> DeviceState:
        """执行完整伪装流程，返回验证后的 DeviceState。"""
        props = {
            "ro.product.odm.brand": brand,
            "ro.product.odm.manufacturer": manufacturer,
            "ro.product.odm.model": model,
        }
        return self._execute_modify(serial, props, "伪装", on_progress)

    # ------------------------------------------------------------------
    # FR-003: 还原
    # ------------------------------------------------------------------

    def reset(
        self,
        serial: str,
        on_progress: ProgressCallback = None,
    ) -> DeviceState:
        """将 ODM 属性还原为 vendor 原始值。"""
        self._notify(on_progress, "正在读取原始设备信息...")
        state = self.get_device_state(serial)
        if not state.is_disguised:
            self._notify(on_progress, "✓ 设备未伪装，无需还原")
            return state

        props = {
            "ro.product.odm.brand": state.original_brand,
            "ro.product.odm.manufacturer": state.original_manufacturer,
            "ro.product.odm.model": state.original_model,
        }
        return self._execute_modify(serial, props, "还原", on_progress)

    # ------------------------------------------------------------------
    # FR-007: 修改 build.prop
    # ------------------------------------------------------------------

    @staticmethod
    def modify_build_prop(path: str | Path, props: dict[str, str]) -> None:
        """修改 build.prop：已有键替换值，缺失键追加到末尾。"""
        file_path = Path(path)
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines(
            keepends=True
        )

        modified_keys: set[str] = set()
        new_lines: list[str] = []
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

        file_path.write_text("".join(new_lines), encoding="utf-8")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _execute_modify(
        self,
        serial: str,
        props: dict[str, str],
        action_name: str,
        on_progress: ProgressCallback,
    ) -> DeviceState:
        """通用修改流程：root → remount → setenforce → pull → modify → push → reboot → verify

        root 和 remount 均委托给框架级 AdbManager 的增强方法，
        无需在模块中重复实现等待、重启、重试逻辑。
        """
        self._notify(on_progress, "设备信息修改中...")

        self._notify(on_progress, "  adb root...")
        self._adb.root(serial)
        self._notify(on_progress, "  ✓ adb root 成功")

        self._notify(on_progress, "  adb remount...")
        self._adb.remount(serial, on_progress=on_progress)

        self._notify(on_progress, "  setenforce 0...")
        self._adb.shell(serial, "setenforce 0")
        self._notify(on_progress, "  ✓ setenforce 0 成功")

        self._notify(on_progress, "  拉取 build.prop...")
        tmp_dir = tempfile.mkdtemp()
        local_prop = os.path.join(tmp_dir, "build.prop")
        self._adb.pull(serial, "/odm/etc/build.prop", local_prop)
        self._notify(on_progress, "  ✓ 拉取 build.prop 成功")

        self._notify(on_progress, "  修改 build.prop...")
        self.modify_build_prop(local_prop, props)
        self._notify(on_progress, "  ✓ 修改 build.prop 成功")

        self._notify(on_progress, "  推送 build.prop...")
        self._adb.push(serial, local_prop, "/odm/etc/build.prop")
        self._notify(on_progress, "  ✓ 推送 build.prop 成功")

        self._notify(on_progress, "正在重启设备请稍后...")
        self._adb.reboot(serial)

        self._notify(on_progress, "  等待设备重启完成...")
        self._adb.wait_for_device(serial, timeout=120)
        self._adb.wait_boot_completed(serial, timeout=120)
        self._notify(on_progress, "  ✓ 设备重启完成")

        self._notify(on_progress, "  验证设备属性...")
        new_state = self.get_device_state(serial)

        target_brand = props["ro.product.odm.brand"]
        target_mfr = props["ro.product.odm.manufacturer"]
        target_model = props["ro.product.odm.model"]

        if (
            new_state.current_brand == target_brand
            and new_state.current_manufacturer == target_mfr
            and new_state.current_model == target_model
        ):
            self._notify(
                on_progress,
                f"  ✓ 设备信息{action_name}成功: "
                f"brand={target_brand}, manufacturer={target_mfr}, model={target_model}",
            )
        else:
            msg = (
                f"设备信息{action_name}验证失败: 属性值与预期不一致\n"
                f"  期望: brand={target_brand}, manufacturer={target_mfr}, model={target_model}\n"
                f"  实际: brand={new_state.current_brand}, "
                f"manufacturer={new_state.current_manufacturer}, model={new_state.current_model}"
            )
            raise AdbError(msg)

        self._cleanup_tmp(tmp_dir, local_prop)
        return new_state

    @staticmethod
    def _notify(callback: ProgressCallback, message: str) -> None:
        if callback:
            callback(message)

    @staticmethod
    def _cleanup_tmp(tmp_dir: str, local_prop: str) -> None:
        try:
            os.unlink(local_prop)
            os.rmdir(tmp_dir)
        except OSError:
            pass
