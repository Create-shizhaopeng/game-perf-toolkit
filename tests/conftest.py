"""pytest 共享 fixtures — 为所有测试提供临时隔离环境"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    """提供一个临时数据目录。"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture()
def config_path(tmp_data_dir: Path) -> Path:
    """提供临时配置文件路径。"""
    return tmp_data_dir / "config.json"


@pytest.fixture()
def db_path(tmp_data_dir: Path) -> Path:
    """提供临时数据库文件路径。"""
    return tmp_data_dir / "toolkit.db"


@pytest.fixture()
def sample_module_dir(tmp_path: Path) -> Path:
    """创建一个合法的模块目录结构用于测试。"""
    mod_dir = tmp_path / "modules" / "test_module"
    mod_dir.mkdir(parents=True)

    manifest = {
        "name": "test_module",
        "display_name": "Test Module",
        "version": "0.1.0",
        "description": "A test module",
        "entry": "src.plugin",
        "cli_namespace": "testmod",
        "dependencies": {"toolkit_modules": []},
    }
    (mod_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    src_dir = mod_dir / "src"
    src_dir.mkdir()
    (src_dir / "__init__.py").touch()

    plugin_code = '''"""Test plugin"""
from toolkit.core.hookspecs import hookimpl

class TestModulePlugin:
    @hookimpl
    def get_plugin_info(self):
        return {"name": "test_module", "version": "0.1.0"}

    @hookimpl
    def register_cli_commands(self, cli_app):
        pass

    @hookimpl
    def register_gui_tab(self):
        return None

    @hookimpl
    def register_agent_tools(self):
        return []

    @hookimpl
    def on_startup(self, context):
        pass

    @hookimpl
    def on_shutdown(self):
        pass
'''
    (src_dir / "plugin.py").write_text(plugin_code, encoding="utf-8")

    return mod_dir


@pytest.fixture()
def modules_dir(sample_module_dir: Path) -> Path:
    """返回包含测试模块的 modules/ 目录。"""
    return sample_module_dir.parent
