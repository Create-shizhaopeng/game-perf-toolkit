# -*- coding: utf-8 -*-
"""Perfetto 解析分析模块 — 单元测试。

测试重点：
- models.py: AnalysisConfig 默认值、加载/保存、数据类
- service.py: 公共 API（使用 mock 模拟引擎）
- engine/config.py: from_pydantic 转换
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# models 测试
# ---------------------------------------------------------------------------

class TestAnalysisConfig:
    """AnalysisConfig Pydantic 模型测试。"""

    def test_defaults(self) -> None:
        from modules.perfetto_analysis.src.models import AnalysisConfig

        cfg = AnalysisConfig()
        assert cfg.output_dir == "output/trace_report"
        assert cfg.db_path == "perfetto_analysis.db"
        assert cfg.refresh_rate_preset == 60
        assert cfg.app_type == "auto"
        assert cfg.analyze_top == 20
        assert cfg.slow_binder_threshold_ms == 2.0
        assert cfg.sched_latency_threshold_ms == 1.0
        assert cfg.auto_analyze_on_capture is False
        assert cfg.default_process == ""
        assert cfg.dimensions == []

    def test_custom_values(self) -> None:
        from modules.perfetto_analysis.src.models import AnalysisConfig

        cfg = AnalysisConfig(
            output_dir="custom/output",
            app_type="game",
            analyze_top=10,
            default_process="com.test.app",
            dimensions=["cpu", "thread"],
        )
        assert cfg.output_dir == "custom/output"
        assert cfg.app_type == "game"
        assert cfg.analyze_top == 10
        assert cfg.default_process == "com.test.app"
        assert cfg.dimensions == ["cpu", "thread"]

    def test_model_dump(self) -> None:
        from modules.perfetto_analysis.src.models import AnalysisConfig

        cfg = AnalysisConfig()
        d = cfg.model_dump()
        assert isinstance(d, dict)
        assert "output_dir" in d
        assert "dimensions" in d

    def test_load_config_fallback(self) -> None:
        from modules.perfetto_analysis.src.models import AnalysisConfig, load_config

        cfg = load_config(Path("nonexistent/path/config.json"))
        assert isinstance(cfg, AnalysisConfig)
        assert cfg.output_dir == "output/trace_report"

    def test_save_and_load_config(self) -> None:
        from modules.perfetto_analysis.src.models import AnalysisConfig, load_config, save_config

        with tempfile.TemporaryDirectory() as tmp:
            cfg = AnalysisConfig(app_type="camera", analyze_top=5)
            saved_path = save_config(cfg, Path(tmp) / "test_config.json")
            assert saved_path.exists()

            loaded = load_config(saved_path)
            assert loaded.app_type == "camera"
            assert loaded.analyze_top == 5


class TestAnalysisTask:
    """AnalysisTask dataclass 测试。"""

    def test_defaults(self) -> None:
        from modules.perfetto_analysis.src.models import AnalysisTask

        task = AnalysisTask(
            task_id="test-123",
            trace_path="/path/to/trace",
        )
        assert task.task_id == "test-123"
        assert task.mode == "full"
        assert task.status == "pending"
        assert task.dimensions == []

    def test_fields(self) -> None:
        from modules.perfetto_analysis.src.models import AnalysisTask

        task = AnalysisTask(
            task_id="t1",
            trace_path="/trace",
            process_name="com.app",
            mode="dimensions",
            dimensions=["cpu"],
            status="running",
        )
        assert task.process_name == "com.app"
        assert task.mode == "dimensions"
        assert task.dimensions == ["cpu"]


class TestAnalysisResult:
    """AnalysisResult dataclass 测试。"""

    def test_defaults(self) -> None:
        from modules.perfetto_analysis.src.models import AnalysisResult

        result = AnalysisResult()
        assert result.jank_times == 0
        assert result.frame_num == 0
        assert result.refresh_rate_hz == 60.0
        assert result.dimensions_completed == []
        assert result.parse_result == {}

    def test_with_data(self) -> None:
        from modules.perfetto_analysis.src.models import AnalysisResult

        result = AnalysisResult(
            trace_path="/trace",
            jank_times=5,
            frame_num=100,
            refresh_rate_hz=120.0,
            dimensions_completed=["cpu", "thread"],
        )
        assert result.jank_times == 5
        assert result.dimensions_completed == ["cpu", "thread"]


# ---------------------------------------------------------------------------
# engine/config 测试
# ---------------------------------------------------------------------------

class TestEngineConfig:
    """engine/config.py 适配层测试。"""

    def test_from_pydantic(self) -> None:
        from modules.perfetto_analysis.src.engine.config import from_pydantic
        from modules.perfetto_analysis.src.models import AnalysisConfig

        cfg = AnalysisConfig(analyze_top=10, app_type="game")
        d = from_pydantic(cfg)
        assert isinstance(d, dict)
        assert d["analyze_top"] == 10
        assert d["app_type"] == "game"

    def test_from_pydantic_with_dict(self) -> None:
        from modules.perfetto_analysis.src.engine.config import from_pydantic

        d = from_pydantic({"analyze_top": 5})
        assert d["analyze_top"] == 5

    def test_from_pydantic_fallback(self) -> None:
        from modules.perfetto_analysis.src.engine.config import DEFAULTS, from_pydantic

        d = from_pydantic(None)
        assert d["refresh_rate_preset"] == DEFAULTS["refresh_rate_preset"]


# ---------------------------------------------------------------------------
# service 测试
# ---------------------------------------------------------------------------

class TestServiceInfo:
    """PerfettoAnalysisService 基础测试。"""

    def test_get_service_info(self) -> None:
        from modules.perfetto_analysis.src.service import PerfettoAnalysisService

        with tempfile.TemporaryDirectory() as tmp:
            svc = PerfettoAnalysisService(data_dir=tmp)
            info = svc.get_service_info()
            assert info["name"] == "perfetto_analysis"
            assert "version" in info

    def test_get_config(self) -> None:
        from modules.perfetto_analysis.src.models import AnalysisConfig
        from modules.perfetto_analysis.src.service import PerfettoAnalysisService

        with tempfile.TemporaryDirectory() as tmp:
            svc = PerfettoAnalysisService(data_dir=tmp)
            cfg = svc.get_config()
            assert isinstance(cfg, AnalysisConfig)

    @mock.patch("modules.perfetto_analysis.src.engine.parser.parse_trace_with_tp")
    @mock.patch("modules.perfetto_analysis.src.engine.analyzer.analyze_jank")
    @mock.patch("modules.perfetto_analysis.src.engine.report_writer.ensure_report_dir")
    @mock.patch("modules.perfetto_analysis.src.engine.report_writer.write_full_report")
    @mock.patch("modules.perfetto_analysis.src.engine.report_writer.write_jank_data_file")
    @mock.patch("modules.perfetto_analysis.src.engine.report_writer.write_summary_data_file")
    @mock.patch("modules.perfetto_analysis.src.engine.export.build_full_report")
    def test_analyze(
        self,
        mock_build_report,
        mock_write_summary,
        mock_write_jank,
        mock_write_full,
        mock_ensure_dir,
        mock_analyze_jank,
        mock_parse,
    ) -> None:
        from modules.perfetto_analysis.src.service import PerfettoAnalysisService

        mock_tp = mock.MagicMock()
        mock_tp.close = mock.MagicMock()
        mock_parse.return_value = (
            {
                "jank_times": 3,
                "frame_num": 60,
                "inferred_refresh_rate_hz": 60,
                "vsync_cycles": [],
                "jank_records": [],
                "realtime_offset_ns": 0,
            },
            mock_tp,
        )
        mock_analyze_jank.return_value = {
            "app_type": "app",
            "cpu_topology": {},
            "per_jank_analyses": [],
            "summary_analysis": {},
        }
        mock_ensure_dir.return_value = Path("/tmp/test_report")
        mock_write_full.return_value = Path("/tmp/test_report/jank_report.md")
        mock_build_report.return_value = "# Report"

        with tempfile.TemporaryDirectory() as tmp:
            trace_file = Path(tmp) / "test.perfetto-trace"
            trace_file.touch()

            svc = PerfettoAnalysisService(data_dir=tmp)
            progress_msgs = []
            result = svc.analyze(
                str(trace_file),
                process_name="com.test",
                on_progress=lambda msg: progress_msgs.append(msg),
            )

            assert result.jank_times == 3
            assert result.frame_num == 60
            assert len(progress_msgs) > 0

    def test_list_dimensions(self) -> None:
        from modules.perfetto_analysis.src.service import PerfettoAnalysisService

        with tempfile.TemporaryDirectory() as tmp:
            svc = PerfettoAnalysisService(data_dir=tmp)
            dims = svc.list_dimensions()
            assert isinstance(dims, str)

    def test_get_analysis_history_empty(self) -> None:
        from modules.perfetto_analysis.src.service import PerfettoAnalysisService

        with tempfile.TemporaryDirectory() as tmp:
            svc = PerfettoAnalysisService(data_dir=tmp)
            history = svc.get_analysis_history()
            assert isinstance(history, list)

    @mock.patch("modules.perfetto_analysis.src.engine.parser.run_parser_and_save")
    def test_parse_only(self, mock_run_parser) -> None:
        from modules.perfetto_analysis.src.service import PerfettoAnalysisService

        mock_run_parser.return_value = {
            "jank_times": 2,
            "frame_num": 50,
            "inferred_refresh_rate_hz": 120,
            "vsync_cycles": [],
            "jank_records": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            trace_file = Path(tmp) / "test.perfetto-trace"
            trace_file.touch()
            svc = PerfettoAnalysisService(data_dir=tmp)
            progress_msgs = []
            result = svc.parse_only(
                str(trace_file),
                on_progress=lambda msg: progress_msgs.append(msg),
            )
            assert result.jank_times == 2
            assert result.frame_num == 50
            assert result.refresh_rate_hz == 120
            assert len(progress_msgs) > 0

    @mock.patch("modules.perfetto_analysis.src.engine.parser.parse_trace_with_tp")
    @mock.patch("modules.perfetto_analysis.src.engine.analyzer.analyze_dimensions")
    @mock.patch("modules.perfetto_analysis.src.engine.report_writer.ensure_report_dir")
    @mock.patch("modules.perfetto_analysis.src.engine.report_writer.write_analysis_file")
    def test_analyze_dimensions(
        self, mock_write, mock_ensure_dir, mock_analyze_dims, mock_parse,
    ) -> None:
        from modules.perfetto_analysis.src.service import PerfettoAnalysisService

        mock_tp = mock.MagicMock()
        mock_tp.close = mock.MagicMock()
        mock_parse.return_value = (
            {
                "jank_times": 1,
                "frame_num": 30,
                "inferred_refresh_rate_hz": 60,
                "vsync_cycles": [],
                "jank_records": [],
                "realtime_offset_ns": 0,
            },
            mock_tp,
        )
        mock_analyze_dims.return_value = {"cpu": {"data": "test"}}
        mock_ensure_dir.return_value = Path("/tmp/test_report")
        mock_write.return_value = Path("/tmp/test_report/cpu_analysis.md")

        with tempfile.TemporaryDirectory() as tmp:
            trace_file = Path(tmp) / "test.perfetto-trace"
            trace_file.touch()
            svc = PerfettoAnalysisService(data_dir=tmp)
            result = svc.analyze_dimensions(
                str(trace_file), dimensions=["cpu"],
            )
            assert result.jank_times == 1
            assert "cpu" in result.dimensions_completed

    @mock.patch("modules.perfetto_analysis.src.engine.export.export_to_markdown")
    def test_export_report(self, mock_export) -> None:
        from modules.perfetto_analysis.src.service import PerfettoAnalysisService

        mock_export.return_value = True

        with tempfile.TemporaryDirectory() as tmp:
            svc = PerfettoAnalysisService(data_dir=tmp)
            result = svc.export_report()
            assert result is True
            mock_export.assert_called_once()

    def test_reload_config(self) -> None:
        from modules.perfetto_analysis.src.models import AnalysisConfig
        from modules.perfetto_analysis.src.service import PerfettoAnalysisService

        with tempfile.TemporaryDirectory() as tmp:
            svc = PerfettoAnalysisService(data_dir=tmp)
            cfg = svc.reload_config()
            assert isinstance(cfg, AnalysisConfig)

    def test_save_current_config(self) -> None:
        from modules.perfetto_analysis.src.service import PerfettoAnalysisService

        with tempfile.TemporaryDirectory() as tmp:
            svc = PerfettoAnalysisService(data_dir=tmp)
            path = svc.save_current_config()
            assert path.exists()

    def test_perfetto_available_property(self) -> None:
        from modules.perfetto_analysis.src.service import PerfettoAnalysisService

        with tempfile.TemporaryDirectory() as tmp:
            svc = PerfettoAnalysisService(data_dir=tmp)
            assert isinstance(svc.perfetto_available, bool)
