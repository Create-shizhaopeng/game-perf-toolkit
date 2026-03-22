"""AdbManager 测试 — 基础 + 高级操作（smart remount / safe root / AdbCmdResult）"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, call

from toolkit.core.adb_manager import AdbManager, AdbCmdResult
from toolkit.sdk.exceptions import AdbError


def _make_mgr() -> AdbManager:
    mgr = AdbManager.__new__(AdbManager)
    mgr._adb_path = "adb"
    return mgr


def _mock_ok(stdout: str = "") -> MagicMock:
    return MagicMock(stdout=stdout, stderr="", returncode=0)


# ===========================================================================
# 基础功能
# ===========================================================================


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


# ===========================================================================
# T006: _run_cmd_raw 测试
# ===========================================================================


class TestRunCmdRaw:
    @patch("subprocess.run")
    def test_returns_full_result(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="ok\n", stderr="warn\n", returncode=0
        )
        mgr = _make_mgr()
        r = mgr._run_cmd_raw(["devices"])
        assert isinstance(r, AdbCmdResult)
        assert r.stdout == "ok\n"
        assert r.stderr == "warn\n"
        assert r.returncode == 0

    @patch("subprocess.run")
    def test_nonzero_returncode_not_raised(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="", stderr="error", returncode=1
        )
        mgr = _make_mgr()
        r = mgr._run_cmd_raw(["fail"])
        assert r.returncode == 1

    @patch("subprocess.run")
    def test_run_cmd_backward_compatible(self, mock_run: MagicMock) -> None:
        """run_cmd 仍然只返回 stdout 并在 rc!=0 时抛异常"""
        mock_run.return_value = _mock_ok("hello")
        mgr = _make_mgr()
        assert mgr.run_cmd(["version"]) == "hello"

    @patch("subprocess.run")
    def test_run_cmd_raises_on_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="", stderr="bad", returncode=1)
        mgr = _make_mgr()
        with pytest.raises(AdbError):
            mgr.run_cmd(["fail"])


# ===========================================================================
# T007: root 增强测试
# ===========================================================================


class TestRootEnhanced:
    @patch("time.sleep")
    @patch("subprocess.run")
    def test_root_already_running(self, mock_run: MagicMock, mock_sleep: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="adbd is already running as root\n",
            stderr="", returncode=0,
        )
        mgr = _make_mgr()
        result = mgr.root("DEV001")
        assert "already running" in result
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("subprocess.run")
    def test_root_restarts_adbd(self, mock_run: MagicMock, mock_sleep: MagicMock) -> None:
        mock_run.side_effect = [
            MagicMock(stdout="restarting adbd as root\n", stderr="", returncode=0),
            _mock_ok("device"),  # wait_for_device → get-state
        ]
        mgr = _make_mgr()
        result = mgr.root("DEV001")
        assert "restarting" in result
        mock_sleep.assert_any_call(2)

    @patch("subprocess.run")
    def test_root_cannot_run(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="", stderr="adbd cannot run as root in production builds",
            returncode=1,
        )
        mgr = _make_mgr()
        with pytest.raises(AdbError, match="userdebug"):
            mgr.root("DEV001")


# ===========================================================================
# T008: smart remount 测试
# ===========================================================================


class TestSmartRemount:
    @patch("subprocess.run")
    def test_remount_success_no_reboot(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_ok("remount succeeded")
        mgr = _make_mgr()
        progress = []
        result = mgr.remount("DEV001", on_progress=progress.append)
        assert "succeeded" in result
        assert any("成功" in m for m in progress)

    @patch("time.sleep")
    @patch("time.monotonic")
    @patch("subprocess.run")
    def test_remount_with_reboot(
        self, mock_run: MagicMock, mock_time: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        """需要重启的 remount 场景：reboot → wait → root → re-remount"""
        mock_time.side_effect = [0.0, 0.0] + [0.0, 0.0] + [0.0, 0.0] + [0.0]
        mock_run.side_effect = [
            # 1) 第一次 remount → 提示需重启
            _mock_ok("Using overlayfs for /odm\nNow reboot your device for settings to take effect"),
            # 2) reboot
            _mock_ok(""),
            # 3) wait_for_device → get-state
            _mock_ok("device"),
            # 4) wait_boot_completed → getprop
            _mock_ok("1"),
            # 5) root → already running
            MagicMock(stdout="already running as root", stderr="", returncode=0),
            # 6) 第二次 remount → 成功
            _mock_ok("remount succeeded"),
        ]
        mgr = _make_mgr()
        progress = []
        result = mgr.remount("DEV001", on_progress=progress.append)
        assert "succeeded" in result
        assert any("重启" in m for m in progress)
        assert any("成功" in m for m in progress)

    @patch("time.sleep")
    @patch("time.monotonic")
    @patch("subprocess.run")
    def test_remount_two_reboots_raises(
        self, mock_run: MagicMock, mock_time: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        """两次 remount 都需要重启 → 抛出异常提示 disable-verity"""
        mock_time.side_effect = [0.0, 0.0] + [0.0, 0.0] + [0.0, 0.0] + [0.0]
        mock_run.side_effect = [
            # 1) 第一次 remount → 提示重启
            _mock_ok("Verity disabled; overlayfs enabled.\nNow reboot your device for settings to take effect"),
            # 2) reboot
            _mock_ok(""),
            # 3) wait_for_device
            _mock_ok("device"),
            # 4) wait_boot_completed
            _mock_ok("1"),
            # 5) root
            MagicMock(stdout="already running as root", stderr="", returncode=0),
            # 6) 第二次 remount → 仍需重启
            _mock_ok("Now reboot your device for settings to take effect"),
        ]
        mgr = _make_mgr()
        with pytest.raises(AdbError, match="disable-verity"):
            mgr.remount("DEV001")

    @patch("subprocess.run")
    def test_remount_detects_stderr_reboot(self, mock_run: MagicMock) -> None:
        """stderr 中的 reboot 提示也应该被检测"""
        assert AdbManager._needs_reboot_for_remount(
            "some error\nNow reboot your device for settings to take effect"
        )

    def test_needs_reboot_false_for_normal(self) -> None:
        assert not AdbManager._needs_reboot_for_remount("remount succeeded")

    @patch("subprocess.run")
    def test_remount_progress_callback(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_ok("remount succeeded")
        mgr = _make_mgr()
        progress = []
        mgr.remount("DEV001", on_progress=progress.append)
        assert len(progress) >= 1


# ===========================================================================
# 高级操作（兼容旧测试）
# ===========================================================================


class TestAdbManagerAdvanced:

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

    def test_push_nonexistent_file_raises(self) -> None:
        mgr = _make_mgr()
        with pytest.raises(AdbError, match="本地文件不存在"):
            mgr.push("DEV001", "/nonexistent/file.txt", "/remote/path")

    @patch("subprocess.run")
    def test_push_readonly_raises(self, mock_run: MagicMock, tmp_path) -> None:
        local_file = tmp_path / "test.xml"
        local_file.write_text("<config/>")
        mock_run.return_value = MagicMock(
            stdout="", stderr="Read-only file system", returncode=1
        )
        mgr = _make_mgr()
        with pytest.raises(AdbError, match="只读"):
            mgr.push("DEV001", str(local_file), "/system/etc/config.xml")

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
        assert result.strip() == "prop_value"

    @patch("time.sleep")
    @patch("time.monotonic")
    @patch("subprocess.run")
    def test_wait_boot_completed(
        self, mock_run: MagicMock, mock_time: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_run.return_value = _mock_ok("1")
        mock_time.side_effect = [0.0, 0.0]
        mgr = _make_mgr()
        mgr.wait_boot_completed("DEV001", timeout=60)


# ===========================================================================
# T001-T003: ADB Perfetto 支持扩展
# ===========================================================================


class TestAdbPerfettoSupport:
    """验证 input_text + shell_raw + pull_raw 扩展。"""

    @patch("subprocess.run")
    def test_run_cmd_raw_with_input_text(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout=b"12345\n", stderr=b"", returncode=0
        )
        mgr = _make_mgr()
        r = mgr._run_cmd_raw(
            ["-s", "DEV001", "shell", "perfetto --background --txt -c -"],
            input_text="buffers { size_kb: 1024 }",
        )
        assert r.returncode == 0
        assert "12345" in r.stdout
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("input") == b"buffers { size_kb: 1024 }"

    @patch("subprocess.run")
    def test_run_cmd_raw_without_input_text_unchanged(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_ok("ok")
        mgr = _make_mgr()
        r = mgr._run_cmd_raw(["devices"])
        assert r.stdout == "ok"
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("text") is True
        assert call_kwargs.kwargs.get("capture_output") is True

    @patch("subprocess.run")
    def test_shell_raw_returns_adb_cmd_result(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_ok("prop_val")
        mgr = _make_mgr()
        r = mgr.shell_raw("DEV001", "getprop ro.build.model")
        assert isinstance(r, AdbCmdResult)
        assert r.returncode == 0

    @patch("subprocess.run")
    def test_shell_raw_no_exception_on_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="", stderr="error msg", returncode=1)
        mgr = _make_mgr()
        r = mgr.shell_raw("DEV001", "bad-command")
        assert r.returncode == 1
        assert "error" in r.stderr

    @patch("subprocess.run")
    def test_shell_raw_with_input_text(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout=b"99999\n", stderr=b"", returncode=0
        )
        mgr = _make_mgr()
        pbtxt = "buffers { size_kb: 2048\n  fill_policy: RING_BUFFER\n}"
        r = mgr.shell_raw("DEV001", "perfetto --background --txt -c -", input_text=pbtxt)
        assert r.returncode == 0
        assert "99999" in r.stdout

    @patch("subprocess.run")
    def test_pull_raw_returns_result(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_ok("1 file pulled")
        mgr = _make_mgr()
        r = mgr.pull_raw("DEV001", "/data/trace.pb", "/tmp/trace.pb")
        assert isinstance(r, AdbCmdResult)
        assert r.returncode == 0

    @patch("subprocess.run")
    def test_pull_raw_no_exception_on_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="", stderr="remote object does not exist", returncode=1
        )
        mgr = _make_mgr()
        r = mgr.pull_raw("DEV001", "/nonexistent", "/tmp/out")
        assert r.returncode == 1
