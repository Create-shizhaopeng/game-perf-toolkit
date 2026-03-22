"""Perfetto 抓取模块 — 迁移测试"""

from __future__ import annotations

import datetime
import re

import pytest
from unittest.mock import MagicMock, patch

from toolkit.core.adb_manager import AdbCmdResult

from modules.perfetto_capture.src.models import (
    CaptureConfig,
    CaptureMode,
    DeviceConnectionState,
    TraceKind,
)
from modules.perfetto_capture.src.utils import (
    build_export_session_dirname,
    build_trace_filename,
    choose_non_conflicting_path,
    ensure_fault_prefix,
    ensure_unique_dir,
    is_device_unavailable,
    normalize_filename_part,
)
from modules.perfetto_capture.src.service import PerfettoCaptureService


# ── 原 test_perfetto_config: pbtxt 生成 ──────────────────────────


class TestPbtxtConfig:
    def test_pbtxt_no_duration_and_has_proc_stats(self) -> None:
        cfg = CaptureConfig(
            atrace_categories=["sched", "freq"],
            duration_sec=15,
            buffer_size_kb=1024,
        )
        adb = MagicMock()
        svc = PerfettoCaptureService(adb=adb)
        pbtxt = svc.build_pbtxt_config(cfg)
        assert "duration_ms:" not in pbtxt
        assert 'name: "linux.process_stats"' in pbtxt
        assert "proc_stats_poll_ms: 1000" in pbtxt

    def test_pbtxt_ring_buffer(self) -> None:
        cfg = CaptureConfig(buffer_size_kb=2048, buffer_manual_override=True)
        adb = MagicMock()
        svc = PerfettoCaptureService(adb=adb)
        svc.config = cfg
        pbtxt = svc.build_pbtxt_config(cfg)
        assert "fill_policy: RING_BUFFER" in pbtxt
        assert "size_kb: 2048" in pbtxt

    def test_pbtxt_global_mode_uses_wildcard(self) -> None:
        cfg = CaptureConfig()
        adb = MagicMock()
        svc = PerfettoCaptureService(adb=adb)
        pbtxt = svc.build_pbtxt_config(cfg)
        assert 'atrace_apps: "*"' in pbtxt

    def test_pbtxt_packages_mode(self) -> None:
        from modules.perfetto_capture.src.models import TargetConfig
        cfg = CaptureConfig(
            target=TargetConfig(mode="packages", packages=["com.example.app"])
        )
        adb = MagicMock()
        svc = PerfettoCaptureService(adb=adb)
        pbtxt = svc.build_pbtxt_config(cfg)
        assert 'atrace_apps: "com.example.app"' in pbtxt
        assert 'atrace_apps: "*"' not in pbtxt

    def test_pbtxt_has_packages_list_source(self) -> None:
        cfg = CaptureConfig()
        adb = MagicMock()
        svc = PerfettoCaptureService(adb=adb)
        pbtxt = svc.build_pbtxt_config(cfg)
        assert 'name: "android.packages_list"' in pbtxt


# ── 原 test_export_session_dir: 会话目录命名 ─────────────────────


class TestExportSessionDir:
    def test_session_dirname_format(self) -> None:
        fixed = datetime.datetime(2026, 1, 27, 12, 34, 56)
        name = build_export_session_dirname(fixed)
        assert re.fullmatch(r"\d{4}_\d{2}_\d{2}-\d{2}_\d{2}_\d{2}", name)

    def test_unique_dir_creates_and_deduplicates(self, tmp_path) -> None:
        name = "2026_01_27-12_34_56"
        d1 = ensure_unique_dir(tmp_path, name)
        assert d1.exists() and d1.name == name

        d2 = ensure_unique_dir(tmp_path, name)
        assert d2.exists() and d2.name.startswith(name + "_")


# ── 原 test_fault_segment: FAULT_ 前缀 ──────────────────────────


class TestFaultSegment:
    def test_fault_prefix_normalization(self) -> None:
        assert ensure_fault_prefix("A.perfetto-trace") == "FAULT_A.perfetto-trace"
        assert ensure_fault_prefix("FAULT_A.perfetto-trace") == "FAULT_A.perfetto-trace"


# ── 原 test_reconnect: 断线识别 ─────────────────────────────────


class TestDeviceUnavailable:
    def test_disconnect_error_recognition(self) -> None:
        samples = [
            AdbCmdResult(stdout="", stderr="error: device offline", returncode=1),
            AdbCmdResult(stdout="", stderr="error: device unauthorized", returncode=1),
            AdbCmdResult(stdout="", stderr="error: device 'ABC' not found", returncode=1),
            AdbCmdResult(stdout="", stderr="no devices/emulators found", returncode=1),
            AdbCmdResult(stdout="", stderr="protocol fault: Connection reset", returncode=1),
            AdbCmdResult(stdout="", stderr="error: closed", returncode=1),
        ]
        for r in samples:
            assert is_device_unavailable(r) is True, f"Should detect: {r.stderr}"

    def test_success_not_detected_as_unavailable(self) -> None:
        ok = AdbCmdResult(stdout="OK", stderr="", returncode=0)
        assert is_device_unavailable(ok) is False


# ── 文件命名工具函数 ─────────────────────────────────────────────


class TestFilenameUtils:
    def test_normalize_filename_part(self) -> None:
        assert normalize_filename_part("  Hello World  ") == "Hello_World"
        assert normalize_filename_part("") == "UNKNOWN"

    def test_build_trace_filename(self) -> None:
        name = build_trace_filename("Pixel 7", "Tensor G2", "20260327_123456")
        assert name.endswith(".perfetto-trace")
        assert "Pixel_7" in name

    def test_choose_non_conflicting_path(self, tmp_path) -> None:
        p = tmp_path / "a.trace"
        assert choose_non_conflicting_path(p) == p

        p.write_text("x")
        p2 = choose_non_conflicting_path(p)
        assert p2 != p
        assert "_1" in p2.name


# ── CaptureConfig Pydantic 模型 ──────────────────────────────────


class TestCaptureConfig:
    def test_default_config_valid(self) -> None:
        cfg = CaptureConfig()
        cfg.validate_semantics()
        assert cfg.duration_sec == 15
        assert cfg.buffer_size_kb is None
        assert cfg.buffer_manual_override is False
        assert len(cfg.atrace_categories) > 0

    def test_invalid_duration_raises(self) -> None:
        with pytest.raises(Exception):
            CaptureConfig(duration_sec=0)

    def test_empty_categories_raises(self) -> None:
        cfg = CaptureConfig(atrace_categories=[])
        with pytest.raises(ValueError, match="不能为空"):
            cfg.validate_semantics()

    def test_packages_mode_requires_packages(self) -> None:
        from modules.perfetto_capture.src.models import TargetConfig
        cfg = CaptureConfig(target=TargetConfig(mode="packages", packages=[]))
        with pytest.raises(ValueError, match="不能为空"):
            cfg.validate_semantics()

    def test_json_roundtrip(self) -> None:
        cfg = CaptureConfig()
        json_str = cfg.model_dump_json()
        cfg2 = CaptureConfig.model_validate_json(json_str)
        assert cfg == cfg2


# ── Service 核心功能 ─────────────────────────────────────────────


class TestService:
    def test_service_info(self) -> None:
        adb = MagicMock()
        svc = PerfettoCaptureService(adb=adb)
        info = svc.get_service_info()
        assert info["name"] == "perfetto_capture"

    def test_ensure_device_trace_dir_success(self) -> None:
        adb = MagicMock()
        adb.shell_raw.return_value = AdbCmdResult("", "", 0)
        svc = PerfettoCaptureService(adb=adb)
        result = svc.ensure_device_trace_dir("DEV001")
        assert result == "/data/misc/perfetto-traces"

    def test_ensure_device_trace_dir_fallback(self) -> None:
        adb = MagicMock()
        adb.shell_raw.side_effect = [
            AdbCmdResult("", "Permission denied", 1),
            AdbCmdResult("", "", 0),
        ]
        svc = PerfettoCaptureService(adb=adb)
        cfg = svc.config.model_copy(update={"device_trace_dir": "/data/local/tmp/perfetto-traces"})
        svc.config = cfg
        result = svc.ensure_device_trace_dir("DEV001")
        assert result == "/data/misc/perfetto-traces"

    def test_start_tracing_detach_mode(self) -> None:
        adb = MagicMock()
        adb.shell_raw.return_value = AdbCmdResult("", "Connected to traced", 0)
        svc = PerfettoCaptureService(adb=adb)
        running = svc.start_tracing("DEV001", "/data/trace.pb")
        assert running.mode == CaptureMode.SNAPSHOT
        assert running.detach_key is not None and running.detach_key.startswith("lv_")
        assert running.session_name is not None and running.session_name.startswith("lv_capture_")
        assert running.device_output_path == "/data/trace.pb"

    def test_start_tracing_legacy_mode(self) -> None:
        adb = MagicMock()
        adb.shell_raw.return_value = AdbCmdResult("[1234]", "", 0)
        svc = PerfettoCaptureService(adb=adb)
        running = svc.start_tracing_legacy("DEV001", "/data/trace.pb")
        assert running.mode == CaptureMode.AUTOBUFFER
        assert running.pid == 1234
        assert running.detach_key is None
        assert running.device_output_path == "/data/trace.pb"

    def test_start_tracing_sends_pbtxt_via_input_text(self) -> None:
        adb = MagicMock()
        adb.shell_raw.return_value = AdbCmdResult("", "Connected", 0)
        svc = PerfettoCaptureService(adb=adb)
        svc.start_tracing("DEV001", "/data/trace.pb")
        call_kwargs = adb.shell_raw.call_args
        assert call_kwargs.kwargs.get("input_text") is not None
        assert "RING_BUFFER" in call_kwargs.kwargs["input_text"]

    def test_stop_tracing_dispatches_by_mode(self) -> None:
        from modules.perfetto_capture.src.models import RunningTrace, CaptureMode
        adb = MagicMock()
        adb.shell_raw.return_value = AdbCmdResult("", "", 0)
        svc = PerfettoCaptureService(adb=adb)

        snap = RunningTrace("/data/t.pb", CaptureMode.SNAPSHOT, detach_key="lv_abc", session_name="s")
        svc.stop_tracing("DEV001", snap)
        assert "--attach=lv_abc" in adb.shell_raw.call_args[0][1]

        adb.shell_raw.reset_mock()
        adb.shell_raw.return_value = AdbCmdResult("", "", 0)
        legacy = RunningTrace("/data/t.pb", CaptureMode.AUTOBUFFER, pid=5678)
        svc.stop_tracing("DEV001", legacy)
        assert "kill 5678" in adb.shell_raw.call_args[0][1]

    def test_probe_snapshot_support(self) -> None:
        from modules.perfetto_capture.src.models import PerfettoCapabilities
        caps_full = PerfettoCapabilities(help_text="--detach --clone --attach --stop")
        assert caps_full.supports_snapshot_mode is True

        caps_old = PerfettoCapabilities(help_text="--background --txt -c")
        assert caps_old.supports_snapshot_mode is False

    def test_create_session(self, tmp_path) -> None:
        adb = MagicMock()
        svc = PerfettoCaptureService(adb=adb, data_dir=tmp_path)
        session = svc.create_session("DEV001")
        assert session.device_serial == "DEV001"
        assert not session.export_session_dir.exists()
