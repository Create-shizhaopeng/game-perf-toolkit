"""Perfetto Capture — CLI 子命令测试"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from modules.perfetto_capture.src.cli_commands import perfetto_app

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_context():
    import modules.perfetto_capture.src.cli_commands as cli_mod

    cli_mod._context = None
    yield
    cli_mod._context = None


@pytest.fixture
def mock_ctx():
    import modules.perfetto_capture.src.cli_commands as cli_mod

    svc = MagicMock()
    adb = MagicMock()
    svc.get_service_info.return_value = {
        "name": "perfetto_capture",
        "display_name": "Perfetto 抓取",
        "version": "1.0.0",
    }
    cfg = MagicMock()
    cfg.duration_sec = 15
    cfg.buffer_size_kb = 91136
    cfg.target.mode = "global"
    cfg.atrace_categories = ["gfx", "view"]
    cfg.device_trace_dir = "/data/misc/perfetto-traces"
    cfg.output_dir = "data/output"
    cfg.model_dump_json.return_value = '{"duration_sec": 15}'
    svc.config = cfg
    adb.get_connected_devices.return_value = ["DEV001"]
    cli_mod._context = {"pe_service": svc, "pe_adb": adb}
    return svc, adb


class TestPerfettoInfo:
    def test_info_displays_table(self, mock_ctx):
        svc, _ = mock_ctx
        result = runner.invoke(perfetto_app, ["info"])
        assert result.exit_code == 0
        assert "Perfetto" in result.output

    def test_info_no_context(self):
        result = runner.invoke(perfetto_app, ["info"])
        assert result.exit_code == 1
        assert "未初始化" in result.output


class TestConfigShow:
    def test_config_show(self, mock_ctx):
        result = runner.invoke(perfetto_app, ["config", "show"])
        assert result.exit_code == 0


class TestConfigReset:
    @patch("modules.perfetto_capture.src.config_manager.reset_config")
    def test_config_reset(self, mock_reset, mock_ctx):
        mock_reset.return_value = MagicMock()
        result = runner.invoke(perfetto_app, ["config", "reset"])
        assert result.exit_code == 0
        assert "重置" in result.output or "默认" in result.output
