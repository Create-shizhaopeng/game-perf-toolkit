"""PerfDog Insights — CLI 子命令测试"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from modules.perfdog_insights.src.cli_commands import perfdog_app

runner = CliRunner()


class TestPerfDogInfo:
    @patch("modules.perfdog_insights.src.cli_commands.PerfdogInsightsService")
    def test_info_output(self, mock_cls):
        svc = MagicMock()
        svc.get_service_info.return_value = {
            "display_name": "PerfDog 分析",
            "version": "1.0.0",
        }
        mock_cls.return_value = svc
        result = runner.invoke(perfdog_app, [])
        assert result.exit_code == 0
        assert "PerfDog" in result.output
