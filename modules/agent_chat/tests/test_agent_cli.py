# -*- coding: utf-8 -*-
"""agent_chat 模块 — CLI 命令测试。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from modules.agent_chat.src.cli_commands import agent_app
from modules.agent_chat.src.models import AgentConfig

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_context():
    """每个测试重置 CLI 模块的上下文。"""
    import modules.agent_chat.src.cli_commands as cli_mod
    original = cli_mod._ac_context
    cli_mod._ac_context = None
    yield
    cli_mod._ac_context = original


def _inject_config(**overrides):
    """通过 context 注入配置（绕过 lazy import）。"""
    import modules.agent_chat.src.cli_commands as cli_mod
    cfg = AgentConfig(**overrides)
    cli_mod._ac_context = {"ac_config": cfg}
    return cfg


# ---------------------------------------------------------------------------
# info 命令
# ---------------------------------------------------------------------------

class TestInfoCommand:

    def test_info_shows_provider(self):
        _inject_config(provider="glm", model_name="glm-4-plus")
        result = runner.invoke(agent_app, ["info"])
        assert result.exit_code == 0
        assert "glm" in result.output
        assert "glm-4-plus" in result.output

    def test_info_shows_claude_provider(self):
        _inject_config(provider="claude", model_name="claude-3-opus")
        result = runner.invoke(agent_app, ["info"])
        assert result.exit_code == 0
        assert "claude" in result.output

    def test_info_shows_key_status_configured(self):
        _inject_config(glm_api_key="key123")
        result = runner.invoke(agent_app, ["info"])
        assert result.exit_code == 0

    def test_info_shows_key_status_unconfigured(self):
        _inject_config()
        result = runner.invoke(agent_app, ["info"])
        assert result.exit_code == 0

    def test_info_shows_temperature_and_language(self):
        _inject_config(temperature=0.7, language="en")
        result = runner.invoke(agent_app, ["info"])
        assert result.exit_code == 0
        assert "0.7" in result.output
        assert "en" in result.output


# ---------------------------------------------------------------------------
# ask 命令
# ---------------------------------------------------------------------------

class TestAskCommand:

    def test_ask_no_api_key_exits(self):
        _inject_config()
        result = runner.invoke(agent_app, ["ask", "你好"])
        assert result.exit_code == 1
        assert "API Key" in result.output

    def _mock_service(self):
        from modules.agent_chat.src.models import LLMResponse
        mock_svc = MagicMock()
        mock_svc.is_ready = True
        mock_svc.chat.return_value = LLMResponse(text="ok")
        return mock_svc

    @patch("modules.agent_chat.src.cli_commands._create_service")
    def test_ask_with_key_runs_service(self, mock_create):
        _inject_config(api_key="test-key")
        mock_svc = self._mock_service()
        mock_create.return_value = (mock_svc, MagicMock())

        result = runner.invoke(agent_app, ["ask", "分析卡顿"])
        assert result.exit_code == 0
        mock_svc.chat.assert_called_once()

    @patch("modules.agent_chat.src.cli_commands._create_service")
    def test_ask_with_sop_option(self, mock_create):
        _inject_config(api_key="key")
        mock_svc = self._mock_service()
        mock_create.return_value = (mock_svc, MagicMock())

        result = runner.invoke(agent_app, ["ask", "hello", "--sop", "jank"])
        assert result.exit_code == 0
        call_kwargs = mock_svc.chat.call_args
        assert "jank" in str(call_kwargs)

    @patch("modules.agent_chat.src.cli_commands._create_service")
    def test_ask_with_provider_option(self, mock_create):
        _inject_config(api_key="key")
        mock_svc = self._mock_service()
        mock_create.return_value = (mock_svc, MagicMock())

        result = runner.invoke(
            agent_app, ["ask", "hello", "--provider", "claude"]
        )
        assert result.exit_code == 0

    @patch("modules.agent_chat.src.cli_commands._create_service")
    def test_ask_auto_match_sop(self, mock_create):
        _inject_config(api_key="key")
        mock_svc = self._mock_service()
        mock_create.return_value = (mock_svc, MagicMock())

        result = runner.invoke(agent_app, ["ask", "hello"])
        assert result.exit_code == 0

    def test_ask_missing_message_exits(self):
        result = runner.invoke(agent_app, ["ask"])
        assert result.exit_code != 0

    @patch("modules.agent_chat.src.cli_commands._create_service")
    def test_ask_with_glm_key_only_succeeds(self, mock_create):
        _inject_config(glm_api_key="glm-key")
        mock_svc = self._mock_service()
        mock_create.return_value = (mock_svc, MagicMock())

        result = runner.invoke(agent_app, ["ask", "test"])
        assert result.exit_code == 0

    @patch("modules.agent_chat.src.cli_commands._create_service")
    def test_ask_with_claude_key_only_succeeds(self, mock_create):
        _inject_config(claude_api_key="claude-key")
        mock_svc = self._mock_service()
        mock_create.return_value = (mock_svc, MagicMock())

        result = runner.invoke(agent_app, ["ask", "test"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# sop 子命令
# ---------------------------------------------------------------------------

class TestSOPCommands:

    def test_sop_list_empty(self):
        result = runner.invoke(agent_app, ["sop", "list"])
        assert result.exit_code == 0

    @patch("modules.agent_chat.src.cli_commands._get_sop_manager")
    def test_sop_list_with_sops(self, mock_mgr):
        from modules.agent_chat.src.models import SOPDocument, SOPSource
        from pathlib import Path

        mgr = MagicMock()
        mgr.load_all.return_value = [
            SOPDocument(
                title="Trace分析",
                path=Path("trace.md"),
                keywords=["trace", "perfetto"],
                description="执行 Perfetto trace 分析",
                source=SOPSource.BUILTIN,
            ),
        ]
        mock_mgr.return_value = mgr

        result = runner.invoke(agent_app, ["sop", "list"])
        assert result.exit_code == 0
        assert "Trace" in result.output

    def test_sop_show_not_found(self):
        result = runner.invoke(agent_app, ["sop", "show", "nonexistent_sop"])
        assert result.exit_code == 1

    @patch("modules.agent_chat.src.cli_commands._get_sop_manager")
    def test_sop_show_success(self, mock_mgr):
        mgr = MagicMock()
        mgr.load_all.return_value = []
        mgr.get_sop_content.return_value = "# 测试 SOP\n\n步骤 1"
        mock_mgr.return_value = mgr

        result = runner.invoke(agent_app, ["sop", "show", "test_sop"])
        assert result.exit_code == 0
        assert "测试 SOP" in result.output

    def test_sop_show_missing_name_exits(self):
        result = runner.invoke(agent_app, ["sop", "show"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------

class TestHelp:

    def test_agent_help(self):
        result = runner.invoke(agent_app, ["--help"])
        assert result.exit_code == 0
        assert "Agent" in result.output

    def test_sop_help(self):
        result = runner.invoke(agent_app, ["sop", "--help"])
        assert result.exit_code == 0
        assert "SOP" in result.output
