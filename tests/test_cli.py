"""CLI 命令测试 — T016/T017/T018

验证 version / config / plugin 内置命令行为。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from toolkit.cli.main import create_cli_app


runner = CliRunner()


@pytest.fixture()
def config_manager(config_path: Path):
    from toolkit.core.config_manager import ConfigManager

    return ConfigManager(config_path)


@pytest.fixture()
def plugin_manager_mock():
    pm = MagicMock()
    pm.loaded_modules = {
        "device_disguise": {
            "name": "device_disguise",
            "display_name": "设备伪装工具",
            "version": "1.0.0",
            "description": "设备 model 名称修改",
        },
    }
    pm.list_loaded.return_value = ["device_disguise"]
    pm.get_module_info.side_effect = lambda n: pm.loaded_modules.get(n)
    return pm


@pytest.fixture()
def cli_app(config_manager, plugin_manager_mock):
    ctx = {
        "config_manager": config_manager,
        "plugin_manager": plugin_manager_mock,
    }
    return create_cli_app(ctx)


class TestVersionCommand:
    """T016 — CLI version 命令测试"""

    def test_version_output(self, cli_app):
        result = runner.invoke(cli_app, ["version"])
        assert result.exit_code == 0
        assert "LV Game Toolkit" in result.output
        from toolkit import __version__
        assert __version__ in result.output

    def test_version_contains_semver(self, cli_app):
        result = runner.invoke(cli_app, ["version"])
        import re
        assert re.search(r"\d+\.\d+\.\d+", result.output)


class TestConfigCommands:
    """T017 — CLI config 命令组测试"""

    def test_config_get_existing(self, cli_app, config_manager):
        config_manager.set("theme", "dark")
        result = runner.invoke(cli_app, ["config", "get", "theme"])
        assert result.exit_code == 0
        assert "dark" in result.output

    def test_config_get_nested(self, cli_app, config_manager):
        config_manager.set("window.width", 1200)
        result = runner.invoke(cli_app, ["config", "get", "window.width"])
        assert result.exit_code == 0
        assert "1200" in result.output

    def test_config_get_missing(self, cli_app):
        result = runner.invoke(cli_app, ["config", "get", "nonexistent.key"])
        assert result.exit_code == 0
        assert "未找到" in result.output

    def test_config_set(self, cli_app, config_manager):
        result = runner.invoke(cli_app, ["config", "set", "adb_path", "/usr/bin/adb"])
        assert result.exit_code == 0
        assert "已设置" in result.output
        assert config_manager.get("adb_path") == "/usr/bin/adb"

    def test_config_set_nested(self, cli_app, config_manager):
        result = runner.invoke(cli_app, ["config", "set", "window.height", "900"])
        assert result.exit_code == 0
        assert config_manager.get("window.height") == "900"

    def test_config_list(self, cli_app, config_manager):
        result = runner.invoke(cli_app, ["config", "list"])
        assert result.exit_code == 0
        assert "theme" in result.output
        assert "adb_path" in result.output

    def test_config_list_shows_table(self, cli_app):
        result = runner.invoke(cli_app, ["config", "list"])
        assert result.exit_code == 0
        assert "当前配置" in result.output


class TestPluginCommands:
    """T018 — CLI plugin 命令组测试"""

    def test_plugin_list_shows_modules(self, cli_app):
        result = runner.invoke(cli_app, ["plugin", "list"])
        assert result.exit_code == 0
        assert "设备伪装工具" in result.output
        assert "1.0.0" in result.output

    def test_plugin_list_shows_table(self, cli_app):
        result = runner.invoke(cli_app, ["plugin", "list"])
        assert result.exit_code == 0
        assert "已加载模块" in result.output

    def test_plugin_list_empty(self, config_manager):
        pm = MagicMock()
        pm.list_loaded.return_value = []
        ctx = {"config_manager": config_manager, "plugin_manager": pm}
        app = create_cli_app(ctx)
        result = runner.invoke(app, ["plugin", "list"])
        assert result.exit_code == 0
        assert "已加载模块" in result.output


class TestHelpAndErrors:
    """CLI 基本交互测试"""

    def test_no_args_shows_help(self, cli_app):
        result = runner.invoke(cli_app, [])
        assert "Usage" in result.output or "usage" in result.output.lower()

    def test_invalid_command(self, cli_app):
        result = runner.invoke(cli_app, ["nonexistent"])
        assert result.exit_code != 0

    def test_config_without_subcommand(self, cli_app):
        result = runner.invoke(cli_app, ["config", "--help"])
        assert "get" in result.output.lower()
        assert "list" in result.output.lower()
