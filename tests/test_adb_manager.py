"""AdbManager 基本场景测试（路径解析、命令拼接）+ 高级操作测试"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from toolkit.core.adb_manager import AdbManager
from toolkit.sdk.exceptions import AdbError


def _make_mgr() -> AdbManager:
    mgr = AdbManager.__new__(AdbManager)
    mgr._adb_path = "adb"
    return mgr


def _mock_ok(stdout: str = "") -> MagicMock:
    return MagicMock(stdout=stdout, stderr="", returncode=0)


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
        mock_run.return_value = _mock_ok("output")
        mgr = _make_mgr()
        mgr._adb_path = "/my/adb"
        mgr.run_cmd(["devices"])
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "/my/adb"
        assert "devices" in args

    @patch("subprocess.run")
    def test_run_cmd_with_serial(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_ok("model_name")
        mgr = _make_mgr()
        mgr.get_prop("ro.build.model", serial="ABC123")
        args = mock_run.call_args[0][0]
        assert "-s" in args
        assert "ABC123" in args

    @patch("subprocess.run")
    def test_get_connected_devices_parses_output(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_ok(
            "List of devices attached\n1234\tdevice\n5678\toffline\n"
        )
        mgr = _make_mgr()
        devices = mgr.get_connected_devices()
        assert devices == ["1234"]


class TestAdbManagerAdvanced:
    """T009: root/remount/push/pull/reboot/wait_for_device/shell 的 mock 测试"""

    @patch("subprocess.run")
    def test_root_sends_serial(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_ok("restarting adbd as root")
        mgr = _make_mgr()
        result = mgr.root("DEV001")
        args = mock_run.call_args[0][0]
        assert args == ["adb", "-s", "DEV001", "root"]
        assert "root" in result

    @patch("subprocess.run")
    def test_remount_sends_serial(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_ok("remount succeeded")
        mgr = _make_mgr()
        result = mgr.remount("DEV001")
        args = mock_run.call_args[0][0]
        assert args == ["adb", "-s", "DEV001", "remount"]
        assert "succeeded" in result

    @patch("subprocess.run")
    def test_push_sends_serial_and_paths(self, mock_run: MagicMock, tmp_path) -> None:
        local_file = tmp_path / "test.xml"
        local_file.write_text("<config/>")
        mock_run.return_value = _mock_ok("1 file pushed")
        mgr = _make_mgr()
        mgr.push("DEV001", str(local_file), "/system/etc/config.xml")
        args = mock_run.call_args[0][0]
        assert args[:3] == ["adb", "-s", "DEV001"]
        assert args[3] == "push"
        assert str(local_file) in args
        assert "/system/etc/config.xml" in args

    def test_push_nonexistent_file_raises(self) -> None:
        mgr = _make_mgr()
        with pytest.raises(AdbError, match="本地文件不存在"):
            mgr.push("DEV001", "/nonexistent/file.txt", "/remote/path")

    @patch("subprocess.run")
    def test_pull_sends_serial_and_paths(self, mock_run: MagicMock, tmp_path) -> None:
        mock_run.return_value = _mock_ok("1 file pulled")
        mgr = _make_mgr()
        mgr.pull("DEV001", "/odm/etc/build.prop", str(tmp_path / "local.prop"))
        args = mock_run.call_args[0][0]
        assert args[:3] == ["adb", "-s", "DEV001"]
        assert args[3] == "pull"

    @patch("subprocess.run")
    def test_reboot_sends_serial(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_ok("")
        mgr = _make_mgr()
        mgr.reboot("DEV001")
        args = mock_run.call_args[0][0]
        assert args == ["adb", "-s", "DEV001", "reboot"]

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_wait_for_device_returns_on_ready(
        self, mock_run: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_run.return_value = _mock_ok("device")
        mgr = _make_mgr()
        mgr.wait_for_device("DEV001", timeout=10)
        args = mock_run.call_args[0][0]
        assert args[:3] == ["adb", "-s", "DEV001"]
        assert "get-state" in args

    @patch("time.monotonic")
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_wait_for_device_timeout_raises(
        self, mock_run: MagicMock, mock_sleep: MagicMock, mock_time: MagicMock
    ) -> None:
        mock_run.return_value = _mock_ok("offline")
        mock_time.side_effect = [0.0, 0.0, 5.0, 10.0, 20.0]
        mgr = _make_mgr()
        with pytest.raises(AdbError, match="超时"):
            mgr.wait_for_device("DEV001", timeout=10)

    @patch("subprocess.run")
    def test_shell_sends_serial_and_command(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_ok("prop_value")
        mgr = _make_mgr()
        result = mgr.shell("DEV001", "getprop ro.build.model")
        args = mock_run.call_args[0][0]
        assert args[:3] == ["adb", "-s", "DEV001"]
        assert args[3] == "shell"
        assert "getprop ro.build.model" in args
        assert result.strip() == "prop_value"
