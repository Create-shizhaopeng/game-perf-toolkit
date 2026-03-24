"""Perfetto Analysis — CLI 子命令测试"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from modules.perfetto_analysis.src.cli_commands import analysis_app

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_context():
    import modules.perfetto_analysis.src.cli_commands as cli_mod

    cli_mod._pa_context = None
    yield
    cli_mod._pa_context = None


@pytest.fixture
def mock_svc():
    import modules.perfetto_analysis.src.cli_commands as cli_mod

    svc = MagicMock()
    svc.get_service_info.return_value = {
        "name": "perfetto_analysis",
        "display_name": "Perfetto 解析分析",
        "version": "1.0.0",
    }
    cfg = MagicMock()
    cfg.output_dir = "data/output"
    cfg.default_process = ""
    cfg.analyze_top = 20
    cfg.model_dump.return_value = {"output_dir": "data/output"}
    svc.get_config.return_value = cfg
    svc.perfetto_available = True
    cli_mod._pa_context = {"pa_service": svc}
    return svc


class TestAnalysisInfo:
    def test_info_table(self, mock_svc):
        result = runner.invoke(analysis_app, ["info"])
        assert result.exit_code == 0
        assert "Perfetto" in result.output

    def test_info_json(self, mock_svc):
        result = runner.invoke(analysis_app, ["info", "--json"])
        assert result.exit_code == 0


class TestAnalysisDims:
    def test_dims_list(self, mock_svc):
        mock_svc.list_dimensions.return_value = "cpu - CPU\ngpu - GPU"
        result = runner.invoke(analysis_app, ["dims"])
        assert result.exit_code == 0
        assert "cpu" in result.output.lower() or "CPU" in result.output


class TestAnalysisHistory:
    def test_history_empty(self, mock_svc):
        mock_svc.get_analysis_history.return_value = []
        result = runner.invoke(analysis_app, ["history"])
        assert result.exit_code == 0
        assert "暂无" in result.output

    def test_history_json_empty(self, mock_svc):
        mock_svc.get_analysis_history.return_value = []
        result = runner.invoke(analysis_app, ["history", "--json"])
        assert result.exit_code == 0


class TestAnalysisParse:
    def test_parse_file_not_found(self, mock_svc):
        result = runner.invoke(analysis_app, ["parse", "/nonexistent/file.trace"])
        assert result.exit_code == 0
        assert "不存在" in result.output

    def test_parse_success(self, mock_svc):
        result_obj = MagicMock()
        result_obj.jank_times = 5
        result_obj.frame_num = 100
        result_obj.refresh_rate_hz = 60
        result_obj.elapsed_seconds = 1.5
        mock_svc.parse_only.return_value = result_obj

        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "test.perfetto-trace"
            trace.touch()
            result = runner.invoke(analysis_app, ["parse", str(trace)])
            assert result.exit_code == 0
            assert "5" in result.output


class TestAnalysisReport:
    def test_report_success(self, mock_svc):
        mock_svc.export_report.return_value = True
        result = runner.invoke(analysis_app, ["report"])
        assert result.exit_code == 0

    def test_report_failure(self, mock_svc):
        mock_svc.export_report.return_value = False
        result = runner.invoke(analysis_app, ["report"])
        assert result.exit_code == 0
