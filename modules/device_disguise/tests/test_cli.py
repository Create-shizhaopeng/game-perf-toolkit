"""设备伪装工具 — CLI 测试"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from modules.device_disguise.src.cli_commands import device_app
from toolkit.sdk.models import DeviceState

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_globals():
    """重置 CLI 模块的全局单例"""
    import modules.device_disguise.src.cli_commands as cli_mod

    cli_mod._service = None
    cli_mod._profile_mgr = None
    yield
    cli_mod._service = None
    cli_mod._profile_mgr = None


@pytest.fixture
def mock_svc_and_adb():
    """直接注入 mock service 和 mock adb，绕过 lazy import"""
    import modules.device_disguise.src.cli_commands as cli_mod

    svc = MagicMock()
    cli_mod._service = svc

    with patch("toolkit.core.adb_manager.AdbManager") as adb_cls:
        adb = MagicMock()
        adb.get_connected_devices.return_value = ["ABC123"]
        adb_cls.return_value = adb
        yield svc, adb


class TestDeviceStatus:
    def test_status_output(self, mock_svc_and_adb):
        svc, adb = mock_svc_and_adb
        svc.get_device_state.return_value = DeviceState(
            is_connected=True,
            current_brand="Samsung",
            current_manufacturer="Samsung",
            current_model="SM-G991B",
            original_brand="Samsung",
            original_manufacturer="Samsung",
            original_model="SM-G991B",
        )
        result = runner.invoke(device_app, ["status"])
        assert result.exit_code == 0
        assert "Samsung" in result.output
        assert "未伪装" in result.output

    def test_status_disguised(self, mock_svc_and_adb):
        svc, adb = mock_svc_and_adb
        svc.get_device_state.return_value = DeviceState(
            is_connected=True,
            current_brand="Apple",
            current_manufacturer="Apple",
            current_model="iPhone15",
            original_brand="Samsung",
            original_manufacturer="Samsung",
            original_model="SM-G991B",
        )
        result = runner.invoke(device_app, ["status"])
        assert result.exit_code == 0
        assert "已伪装" in result.output


class TestDeviceDisguise:
    def test_disguise_command(self, mock_svc_and_adb):
        svc, adb = mock_svc_and_adb
        svc.disguise.return_value = DeviceState(
            is_connected=True,
            current_brand="Apple",
            current_manufacturer="Apple",
            current_model="iPhone15",
            original_brand="Samsung",
            original_manufacturer="Samsung",
            original_model="SM-G991B",
        )
        result = runner.invoke(
            device_app,
            ["disguise", "--brand", "Apple", "--manufacturer", "Apple", "--model", "iPhone15"],
        )
        assert result.exit_code == 0
        assert "伪装完成" in result.output
        svc.disguise.assert_called_once()


class TestDeviceReset:
    def test_reset_command(self, mock_svc_and_adb):
        svc, adb = mock_svc_and_adb
        svc.reset.return_value = DeviceState(
            is_connected=True,
            current_brand="Samsung",
            current_manufacturer="Samsung",
            current_model="SM-G991B",
            original_brand="Samsung",
            original_manufacturer="Samsung",
            original_model="SM-G991B",
        )
        result = runner.invoke(device_app, ["reset"])
        assert result.exit_code == 0
        assert "还原完成" in result.output


class TestNoDevice:
    def test_no_device_exits(self):
        with patch("toolkit.core.adb_manager.AdbManager") as cls:
            adb = MagicMock()
            adb.get_connected_devices.return_value = []
            cls.return_value = adb

            result = runner.invoke(device_app, ["status"])
            assert result.exit_code == 1
            assert "未检测到" in result.output
