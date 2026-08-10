"""待导出清单 — service 层入队/出队/接续导出测试"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from toolkit.core.adb_manager import AdbCmdResult

from modules.perfetto_capture.src.models import (
    CaptureMode,
    DeviceInfo,
    RunningTrace,
)
from modules.perfetto_capture.src.pending_export_store import PendingExportItem
from modules.perfetto_capture.src.service import DeviceUnavailableError, PerfettoCaptureService


def _mk_item(
    serial: str = "DEV001",
    filename: str = "a.pb",
    device_path: str = "/data/current_1.pb",
    session_dir: str = "2026_08_08-10_00_00",
) -> PendingExportItem:
    return PendingExportItem(
        serial=serial,
        device_path=device_path,
        export_filename=filename,
        session_dir=session_dir,
        device_model="SM8750P",
    )


class TestResumePendingExports:
    def test_no_pending(self, tmp_path: Path) -> None:
        adb = MagicMock()
        svc = PerfettoCaptureService(adb=adb, data_dir=tmp_path)
        result = svc.resume_pending_exports("DEV001")
        assert result == {"exported": [], "skipped_missing": [], "failed": []}

    def test_pull_success_enqueues_and_removes(self, tmp_path: Path) -> None:
        def _fake_pull(serial: str, src: str, dst: str) -> AdbCmdResult:
            Path(dst).write_bytes(b"x")
            return AdbCmdResult("", "", 0)

        adb = MagicMock()
        adb.shell_raw.return_value = AdbCmdResult("", "", 0)
        adb.pull_raw.side_effect = _fake_pull
        svc = PerfettoCaptureService(adb=adb, data_dir=tmp_path)
        svc.pending_store.add(_mk_item())

        result = svc.resume_pending_exports("DEV001")
        assert len(result["exported"]) == 1
        assert result["skipped_missing"] == []
        assert result["failed"] == []
        assert result["exported"][0].exists()      # pull 成功落盘
        assert svc.pending_store.all() == []       # 已出队
        adb.pull_raw.assert_called_once()

    def test_local_already_exists_no_pull(self, tmp_path: Path) -> None:
        item = _mk_item(filename="a.pb")
        adb = MagicMock()
        svc = PerfettoCaptureService(adb=adb, data_dir=tmp_path)
        svc.pending_store.add(item)
        dest = svc.output_dir / item.session_dir / item.export_filename
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"x")

        result = svc.resume_pending_exports("DEV001")
        assert len(result["exported"]) == 1
        assert result["exported"][0] == dest
        assert svc.pending_store.all() == []
        adb.pull_raw.assert_not_called()

    def test_device_file_missing_skipped(self, tmp_path: Path) -> None:
        adb = MagicMock()
        adb.shell_raw.return_value = AdbCmdResult("", "No such file", 1)
        svc = PerfettoCaptureService(adb=adb, data_dir=tmp_path)
        svc.pending_store.add(_mk_item())

        result = svc.resume_pending_exports("DEV001")
        assert result["skipped_missing"] == ["a.pb"]
        assert result["exported"] == []
        assert svc.pending_store.all() == []  # 已出队，避免反复失败

    def test_pull_failure_keeps_item(self, tmp_path: Path) -> None:
        adb = MagicMock()
        adb.shell_raw.return_value = AdbCmdResult("", "", 0)
        adb.pull_raw.return_value = AdbCmdResult("", "some error", 1)
        svc = PerfettoCaptureService(adb=adb, data_dir=tmp_path)
        svc.pending_store.add(_mk_item())

        result = svc.resume_pending_exports("DEV001")
        assert result["failed"] == ["a.pb"]
        assert result["exported"] == []
        assert len(svc.pending_store.all()) == 1  # 失败项保留待下次

    def test_device_unavailable_raises(self, tmp_path: Path) -> None:
        adb = MagicMock()
        adb.shell_raw.return_value = AdbCmdResult("", "", 0)
        adb.pull_raw.return_value = AdbCmdResult("", "error: device 'X' not found", 1)
        svc = PerfettoCaptureService(adb=adb, data_dir=tmp_path)
        svc.pending_store.add(_mk_item())

        with pytest.raises(DeviceUnavailableError):
            svc.resume_pending_exports("DEV001")

    def test_serial_scoped_other_device_untouched(self, tmp_path: Path) -> None:
        def _fake_pull(serial: str, src: str, dst: str) -> AdbCmdResult:
            Path(dst).write_bytes(b"x")
            return AdbCmdResult("", "", 0)

        adb = MagicMock()
        adb.shell_raw.return_value = AdbCmdResult("", "", 0)
        adb.pull_raw.side_effect = _fake_pull
        svc = PerfettoCaptureService(adb=adb, data_dir=tmp_path)
        svc.pending_store.add(_mk_item(serial="DEV001", filename="a.pb"))
        svc.pending_store.add(_mk_item(serial="DEV002", filename="b.pb"))

        result = svc.resume_pending_exports("DEV001")
        assert len(result["exported"]) == 1
        assert result["exported"][0].name == "a.pb"
        remaining = svc.pending_store.all()
        assert len(remaining) == 1
        assert remaining[0].serial == "DEV002"  # 其他设备项不受影响


class TestEnqueueOnSave:
    def test_save_trace_enqueues_pending(self, tmp_path: Path) -> None:
        adb = MagicMock()
        adb.shell_raw.return_value = AdbCmdResult("", "", 0)
        svc = PerfettoCaptureService(adb=adb, data_dir=tmp_path)
        session = svc.create_session("DEV001")
        session.running = RunningTrace("/data/current_1.pb", CaptureMode.AUTOBUFFER, pid=1)
        session.trace_idx = 1
        # 替换后续调用为 mock，专注验证入队
        svc.get_device_timestamp = MagicMock(return_value="20260808_100000")
        svc.stop_tracing = MagicMock()
        svc.start_tracing_legacy = MagicMock(
            return_value=RunningTrace("/data/current_2.pb", CaptureMode.AUTOBUFFER, pid=2)
        )

        svc.session_save_trace("DEV001", "/data", DeviceInfo(serial="DEV001", model="SM8750P", soc="SM8750"))

        items = svc.pending_store.all()
        assert len(items) == 1
        assert items[0].serial == "DEV001"
        assert items[0].device_path == "/data/current_1.pb"
        assert items[0].device_model == "SM8750P"
        assert items[0].session_dir == session.export_session_dir.name


class TestDequeueOnExport:
    def test_export_removes_pending(self, tmp_path: Path) -> None:
        def _fake_pull(serial: str, src: str, dst: str) -> AdbCmdResult:
            Path(dst).write_bytes(b"x")
            return AdbCmdResult("", "", 0)

        adb = MagicMock()
        adb.shell_raw.return_value = AdbCmdResult("", "", 0)
        adb.pull_raw.side_effect = _fake_pull
        svc = PerfettoCaptureService(adb=adb, data_dir=tmp_path)
        session = svc.create_session("DEV001")
        svc.pending_store.add(_mk_item(filename="a.pb", session_dir=session.export_session_dir.name))
        # 会话内对应 saved_traces 项（pending 出队按 serial+filename 匹配，不依赖 item 对象）
        from modules.perfetto_capture.src.models import TraceItem, TraceKind
        session.saved_traces.append(
            TraceItem(kind=TraceKind.NORMAL, device_path="/data/current_1.pb", export_filename="a.pb")
        )

        exported = svc.session_stop_and_export("DEV001")
        assert len(exported) == 1
        assert svc.pending_store.all() == []  # 导出成功后出队
