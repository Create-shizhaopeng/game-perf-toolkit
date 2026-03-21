"""game_perf CLI 命令单元测试"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from modules.game_perf.src.cli_commands import perf_app

runner = CliRunner()

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")
FIXTURE_XML = os.path.join(FIXTURE_DIR, "test_gameperfconfig.xml")


@pytest.fixture(autouse=True)
def reset_globals():
    import modules.game_perf.src.cli_commands as mod
    mod._adb = None
    mod._service = None
    yield
    mod._adb = None
    mod._service = None


class TestPerfInfo:
    @patch("modules.game_perf.src.cli_commands._get_adb")
    @patch("modules.game_perf.src.cli_commands._get_service")
    def test_info_displays_table(self, mock_get_svc, mock_get_adb):
        adb = MagicMock()
        adb.get_connected_devices.return_value = ["DEV001"]
        mock_get_adb.return_value = adb

        svc = MagicMock()
        svc.get_info.return_value = {
            "serial": "DEV001",
            "remote_path": "/system/etc/gameperfconfig.xml",
            "version": 5,
            "has_backup": False,
        }
        mock_get_svc.return_value = svc

        result = runner.invoke(perf_app, ["info"])
        assert result.exit_code == 0
        assert "DEV001" in result.output
        assert "5" in result.output


class TestPerfPush:
    @patch("modules.game_perf.src.cli_commands._get_adb")
    @patch("modules.game_perf.src.cli_commands._get_service")
    def test_push_success(self, mock_get_svc, mock_get_adb):
        adb = MagicMock()
        adb.get_connected_devices.return_value = ["DEV001"]
        mock_get_adb.return_value = adb

        svc = MagicMock()
        svc.push.return_value = 6
        mock_get_svc.return_value = svc

        result = runner.invoke(perf_app, ["push", FIXTURE_XML])
        assert result.exit_code == 0
        assert "6" in result.output

    @patch("modules.game_perf.src.cli_commands._get_adb")
    def test_push_no_device(self, mock_get_adb):
        adb = MagicMock()
        adb.get_connected_devices.return_value = []
        mock_get_adb.return_value = adb

        result = runner.invoke(perf_app, ["push", FIXTURE_XML])
        assert result.exit_code == 1
        assert "未检测到" in result.output


class TestPerfReset:
    @patch("modules.game_perf.src.cli_commands._get_adb")
    @patch("modules.game_perf.src.cli_commands._get_service")
    def test_reset_success(self, mock_get_svc, mock_get_adb):
        adb = MagicMock()
        adb.get_connected_devices.return_value = ["DEV001"]
        mock_get_adb.return_value = adb

        svc = MagicMock()
        svc.reset.return_value = 7
        mock_get_svc.return_value = svc

        result = runner.invoke(perf_app, ["reset"])
        assert result.exit_code == 0
        assert "7" in result.output

    @patch("modules.game_perf.src.cli_commands._get_adb")
    @patch("modules.game_perf.src.cli_commands._get_service")
    def test_reset_no_backup(self, mock_get_svc, mock_get_adb):
        from toolkit.sdk.exceptions import AdbError

        adb = MagicMock()
        adb.get_connected_devices.return_value = ["DEV001"]
        mock_get_adb.return_value = adb

        svc = MagicMock()
        svc.reset.side_effect = AdbError("无可用备份")
        mock_get_svc.return_value = svc

        result = runner.invoke(perf_app, ["reset"])
        assert result.exit_code == 1
        assert "无可用备份" in result.output
