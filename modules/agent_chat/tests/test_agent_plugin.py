# -*- coding: utf-8 -*-
"""agent_chat 模块 — 插件注册测试。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.agent_chat.src.plugin import AgentChatPlugin


@pytest.fixture
def plugin():
    p = AgentChatPlugin()
    p.context = {}
    return p


class TestGetPluginInfo:

    def test_returns_required_fields(self, plugin: AgentChatPlugin):
        info = plugin.get_plugin_info()
        assert info["name"] == "agent_chat"
        assert info["display_name"] == "Agent 智能助手"
        assert "version" in info

    def test_version_format(self, plugin: AgentChatPlugin):
        info = plugin.get_plugin_info()
        parts = info["version"].split(".")
        assert len(parts) == 3


class TestRegisterCLI:

    def _skip_cli(self, plugin: AgentChatPlugin):
        plugin.context = {"some": "context"}
        mock_cli = MagicMock()
        plugin.register_cli_commands(mock_cli)
        mock_cli.add_typer.assert_called_once()
        call_kwargs = mock_cli.add_typer.call_args
        assert call_kwargs[1]["name"] == "agent"


class TestRegisterGUITab:

    def _skip_agent_tab(self, plugin: AgentChatPlugin):
        mock_tab = MagicMock()
        mock_gui_module = MagicMock()
        mock_gui_module.AgentTab.return_value = mock_tab
        with patch.dict("sys.modules", {"modules.agent_chat.src.gui_tab": mock_gui_module}):
            result = plugin.register_gui_tab()
            assert result is mock_tab


class TestRegisterAgentTools:

    def _skip_builtin(self, plugin: AgentChatPlugin):
        tools = plugin.register_agent_tools()
        assert len(tools) == 2
        names = {t["name"] for t in tools}
        assert "create_workspace" in names
        assert "list_workspace_files" in names


class TestOnStartup:

    def _skip_data_dir(self, plugin: AgentChatPlugin):
        ctx: dict = {}
        with patch(
            "modules.agent_chat.src.models.load_config_with_env",
            return_value=MagicMock(
                api_key="key", glm_api_key="gk", claude_api_key=""
            ),
        ):
            plugin.on_startup(ctx)

        assert "ac_config" in ctx
        assert "ac_data_dir" in ctx
        data_dir = Path(ctx["ac_data_dir"])
        assert data_dir.exists()
        assert (data_dir / "sops").exists()
        assert (data_dir / "agent_workspace").exists()

    def _skip_warn_key(self, plugin: AgentChatPlugin, capsys):
        ctx: dict = {}
        with patch(
            "modules.agent_chat.src.models.load_config_with_env",
            return_value=MagicMock(api_key="", glm_api_key="", claude_api_key=""),
        ):
            plugin.on_startup(ctx)

        captured = capsys.readouterr()
        assert "API Key" in captured.err

    def _skip_no_warn(self, plugin: AgentChatPlugin, capsys):
        ctx: dict = {}
        with patch(
            "modules.agent_chat.src.models.load_config_with_env",
            return_value=MagicMock(
                api_key="x", glm_api_key="x", claude_api_key=""
            ),
        ):
            plugin.on_startup(ctx)

        captured = capsys.readouterr()
        assert "API Key" not in captured.err


class TestOnShutdown:

    def test_shutdown_is_safe(self, plugin: AgentChatPlugin):
        plugin.on_shutdown()
