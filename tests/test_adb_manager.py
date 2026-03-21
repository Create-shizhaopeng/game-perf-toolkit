"""AdbManager 基本场景测试（路径解析、命令拼接）"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from toolkit.core.adb_manager import AdbManager


class TestAdbManagerBasic:
    @patch("shutil.which", return_value=None)
    def test_fallback_adb_path(self, mock_which: MagicMock) -> None:
        mgr = AdbManager("")
        assert mgr.adb_path == "adb"

    @patch("shutil.which", return_value="/usr/bin/adb")
    def test_system_adb_found(self, mock_which: MagicMock) -> None:
        mgr = AdbManager("")
        assert mgr.adb_path == "/usr/bin/adb"

    @patch("subprocess.run")
    def test_run_cmd_builds_correct_args(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="output", stderr="", returncode=0,
        )
        mgr = AdbManager.__new__(AdbManager)
        mgr._adb_path = "/my/adb"
        result = mgr.run_cmd(["devices"])
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "/my/adb"
        assert "devices" in args

    @patch("subprocess.run")
    def test_run_cmd_with_serial(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="model_name", stderr="", returncode=0,
        )
        mgr = AdbManager.__new__(AdbManager)
        mgr._adb_path = "adb"
        mgr.get_prop("ro.build.model", serial="ABC123")
        args = mock_run.call_args[0][0]
        assert "-s" in args
        assert "ABC123" in args

    @patch("subprocess.run")
    def test_get_connected_devices_parses_output(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="List of devices attached\n1234\tdevice\n5678\toffline\n",
            stderr="",
            returncode=0,
        )
        mgr = AdbManager.__new__(AdbManager)
        mgr._adb_path = "adb"
        devices = mgr.get_connected_devices()
        assert devices == ["1234"]
