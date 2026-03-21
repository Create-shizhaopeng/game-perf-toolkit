"""设备伪装工具 — 服务层测试"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from modules.device_disguise.src.service import DeviceDisguiseService
from toolkit.sdk.exceptions import AdbError


@pytest.fixture
def mock_adb() -> MagicMock:
    adb = MagicMock()
    adb.get_device_props.return_value = {
        "ro.product.odm.brand": "Samsung",
        "ro.product.odm.manufacturer": "Samsung",
        "ro.product.odm.model": "SM-G991B",
        "ro.product.vendor.brand": "Samsung",
        "ro.product.vendor.manufacturer": "Samsung",
        "ro.product.vendor.model": "SM-G991B",
    }
    adb.get_connected_devices.return_value = ["ABC123"]
    adb.root.return_value = ""
    adb.remount.return_value = ""
    adb.shell.return_value = ""
    adb.push.return_value = ""
    adb.reboot.return_value = ""
    adb.wait_for_device.return_value = None
    adb.wait_boot_completed.return_value = None
    adb.get_prop.return_value = "1"
    return adb


@pytest.fixture
def svc(mock_adb: MagicMock) -> DeviceDisguiseService:
    return DeviceDisguiseService(mock_adb)


class TestGetDeviceState:
    def test_returns_device_state(self, svc, mock_adb):
        state = svc.get_device_state("ABC123")
        assert state.is_connected is True
        assert state.current_brand == "Samsung"
        assert state.original_brand == "Samsung"
        assert state.is_disguised is False
        mock_adb.get_device_props.assert_called_once_with("ABC123")

    def test_disguised_state(self, svc, mock_adb):
        mock_adb.get_device_props.return_value = {
            "ro.product.odm.brand": "Apple",
            "ro.product.odm.manufacturer": "Apple",
            "ro.product.odm.model": "iPhone15",
            "ro.product.vendor.brand": "Samsung",
            "ro.product.vendor.manufacturer": "Samsung",
            "ro.product.vendor.model": "SM-G991B",
        }
        state = svc.get_device_state("ABC123")
        assert state.is_disguised is True


class TestModifyBuildProp:
    def test_replace_existing_key(self, tmp_path: Path):
        prop_file = tmp_path / "build.prop"
        prop_file.write_text(
            "ro.product.odm.brand=Samsung\nro.product.odm.model=SM-G991B\n",
            encoding="utf-8",
        )
        DeviceDisguiseService.modify_build_prop(
            str(prop_file),
            {"ro.product.odm.brand": "Apple", "ro.product.odm.model": "iPhone15"},
        )
        content = prop_file.read_text(encoding="utf-8")
        assert "ro.product.odm.brand=Apple" in content
        assert "ro.product.odm.model=iPhone15" in content

    def test_append_missing_key(self, tmp_path: Path):
        prop_file = tmp_path / "build.prop"
        prop_file.write_text(
            "ro.product.odm.brand=Samsung\n", encoding="utf-8"
        )
        DeviceDisguiseService.modify_build_prop(
            str(prop_file),
            {"ro.product.odm.manufacturer": "Apple"},
        )
        content = prop_file.read_text(encoding="utf-8")
        assert "ro.product.odm.brand=Samsung" in content
        assert "ro.product.odm.manufacturer=Apple" in content

    def test_mixed_replace_and_append(self, tmp_path: Path):
        prop_file = tmp_path / "build.prop"
        prop_file.write_text(
            textwrap.dedent("""\
                ro.product.odm.brand=Samsung
                ro.product.odm.model=SM-G991B
                some.other.prop=value
            """),
            encoding="utf-8",
        )
        DeviceDisguiseService.modify_build_prop(
            str(prop_file),
            {
                "ro.product.odm.brand": "Apple",
                "ro.product.odm.manufacturer": "Apple",
            },
        )
        content = prop_file.read_text(encoding="utf-8")
        assert "ro.product.odm.brand=Apple" in content
        assert "ro.product.odm.manufacturer=Apple" in content
        assert "some.other.prop=value" in content
        assert "Samsung" not in content


class TestDisguise:
    def test_full_flow(self, svc, mock_adb, tmp_path):
        progress = []

        prop_content = "ro.product.odm.brand=Samsung\nro.product.odm.manufacturer=Samsung\nro.product.odm.model=SM-G991B\n"

        def fake_pull(serial, remote, local):
            Path(local).write_text(prop_content, encoding="utf-8")
            return ""

        mock_adb.pull.side_effect = fake_pull

        disguised_props = {
            "ro.product.odm.brand": "Apple",
            "ro.product.odm.manufacturer": "Apple",
            "ro.product.odm.model": "iPhone15",
            "ro.product.vendor.brand": "Samsung",
            "ro.product.vendor.manufacturer": "Samsung",
            "ro.product.vendor.model": "SM-G991B",
        }
        # _execute_modify 在 verify 步骤调用一次 get_device_props
        mock_adb.get_device_props.side_effect = [disguised_props]

        state = svc.disguise(
            "ABC123", "Apple", "Apple", "iPhone15",
            on_progress=progress.append,
        )

        assert state.current_brand == "Apple"
        assert state.is_disguised is True

        mock_adb.root.assert_called_once_with("ABC123")
        mock_adb.remount.assert_called_once()
        mock_adb.shell.assert_called_once_with("ABC123", "setenforce 0")
        mock_adb.reboot.assert_called_once_with("ABC123")
        mock_adb.wait_for_device.assert_called_once_with("ABC123", timeout=120)
        mock_adb.wait_boot_completed.assert_called_once_with("ABC123", timeout=120)

        assert any("root 成功" in p for p in progress)
        assert any("伪装成功" in p for p in progress)

    def test_verify_failure_raises(self, svc, mock_adb, tmp_path):
        prop_content = "ro.product.odm.brand=Samsung\n"

        def fake_pull(serial, remote, local):
            Path(local).write_text(prop_content, encoding="utf-8")
            return ""

        mock_adb.pull.side_effect = fake_pull

        with pytest.raises(AdbError, match="验证失败"):
            svc.disguise("ABC123", "Apple", "Apple", "iPhone15")


class TestReset:
    def test_not_disguised_skips(self, svc, mock_adb):
        progress = []
        state = svc.reset("ABC123", on_progress=progress.append)
        assert state.is_disguised is False
        assert any("无需还原" in p for p in progress)
        mock_adb.root.assert_not_called()

    def test_reset_flow(self, svc, mock_adb):
        disguised_props = {
            "ro.product.odm.brand": "Apple",
            "ro.product.odm.manufacturer": "Apple",
            "ro.product.odm.model": "iPhone15",
            "ro.product.vendor.brand": "Samsung",
            "ro.product.vendor.manufacturer": "Samsung",
            "ro.product.vendor.model": "SM-G991B",
        }
        restored_props = {
            "ro.product.odm.brand": "Samsung",
            "ro.product.odm.manufacturer": "Samsung",
            "ro.product.odm.model": "SM-G991B",
            "ro.product.vendor.brand": "Samsung",
            "ro.product.vendor.manufacturer": "Samsung",
            "ro.product.vendor.model": "SM-G991B",
        }
        # reset() 调用 get_device_state (1st)，_execute_modify 验证调用 get_device_state (2nd)
        mock_adb.get_device_props.side_effect = [
            disguised_props,
            restored_props,
        ]

        prop_content = (
            "ro.product.odm.brand=Apple\n"
            "ro.product.odm.manufacturer=Apple\n"
            "ro.product.odm.model=iPhone15\n"
        )

        def fake_pull(serial, remote, local):
            Path(local).write_text(prop_content, encoding="utf-8")
            return ""

        mock_adb.pull.side_effect = fake_pull
        progress = []

        state = svc.reset("ABC123", on_progress=progress.append)
        assert state.is_disguised is False
        mock_adb.root.assert_called_once_with("ABC123")
