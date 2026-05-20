"""脚手架测试 — T020/T021/T022

验证 scripts/create_module.py 的模块创建、加载和错误处理。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def modules_tmp(tmp_path: Path, monkeypatch):
    """将脚手架的 MODULES_DIR 重定向到临时目录。"""
    import scripts.create_module as cm

    mod_dir = tmp_path / "modules"
    mod_dir.mkdir()
    monkeypatch.setattr(cm, "MODULES_DIR", mod_dir)
    return mod_dir


class TestScaffoldCreation:
    """T020 — 脚手架正常创建测试"""

    def test_creates_module_directory(self, modules_tmp):
        from scripts.create_module import create_module

        result = create_module("log_analysis", display_name="日志分析")
        assert result.exists()
        assert result.name == "log_analysis"

    def test_creates_manifest_json(self, modules_tmp):
        from scripts.create_module import create_module

        mod_dir = create_module("trace_viewer")
        manifest_path = mod_dir / "manifest.json"
        assert manifest_path.exists()

        manifest = json.loads(manifest_path.read_text("utf-8"))
        assert manifest["name"] == "trace_viewer"
        assert manifest["version"] == "0.1.0"
        assert manifest["entry"] == "src.plugin"

    def test_creates_plugin_entry(self, modules_tmp):
        from scripts.create_module import create_module

        mod_dir = create_module("data_compare")
        plugin_py = mod_dir / "src" / "plugin.py"
        assert plugin_py.exists()

        content = plugin_py.read_text("utf-8")
        assert "DataComparePlugin" in content
        assert "BasePlugin" in content
        assert "hookimpl" in content

    def test_creates_all_subdirs(self, modules_tmp):
        from scripts.create_module import create_module

        mod_dir = create_module("perf_test")
        for subdir in ["src", "src/migrations", "tests", "specs", "fixtures", "assets"]:
            assert (mod_dir / subdir).is_dir(), f"缺少子目录: {subdir}"

    def test_creates_service_file(self, modules_tmp):
        from scripts.create_module import create_module

        mod_dir = create_module("report_gen")
        service_py = mod_dir / "src" / "service.py"
        assert service_py.exists()
        content = service_py.read_text("utf-8")
        assert "ReportGenService" in content

    def test_no_cli_commands_created(self, modules_tmp):
        from scripts.create_module import create_module

        mod_dir = create_module("strategy_pred")
        cli_py = mod_dir / "src" / "cli_commands.py"
        assert not cli_py.exists()

    def test_creates_gui_tab(self, modules_tmp):
        from scripts.create_module import create_module

        mod_dir = create_module("strategy_pred")
        gui_py = mod_dir / "src" / "gui_tab.py"
        assert gui_py.exists()
        content = gui_py.read_text("utf-8")
        assert "StrategyPredTab" in content
        assert "BaseTab" in content

    def test_creates_test_file(self, modules_tmp):
        from scripts.create_module import create_module

        mod_dir = create_module("log_tool")
        test_file = mod_dir / "tests" / "test_log_tool.py"
        assert test_file.exists()
        content = test_file.read_text("utf-8")
        assert "LogToolService" in content

    def test_creates_agents_md(self, modules_tmp):
        from scripts.create_module import create_module

        mod_dir = create_module("my_module")
        agents_md = mod_dir / "AGENTS.md"
        assert agents_md.exists()

    def test_display_name_defaults(self, modules_tmp):
        from scripts.create_module import create_module

        mod_dir = create_module("log_analysis")
        manifest = json.loads((mod_dir / "manifest.json").read_text("utf-8"))
        assert manifest["display_name"] == "Log Analysis"

    def test_custom_display_name(self, modules_tmp):
        from scripts.create_module import create_module

        mod_dir = create_module("log_analysis", display_name="日志分析工具")
        manifest = json.loads((mod_dir / "manifest.json").read_text("utf-8"))
        assert manifest["display_name"] == "日志分析工具"

    def test_no_cli_namespace_in_manifest(self, modules_tmp):
        from scripts.create_module import create_module

        mod_dir = create_module("trace_analysis")
        manifest = json.loads((mod_dir / "manifest.json").read_text("utf-8"))
        assert "cli_namespace" not in manifest


class TestScaffoldLoading:
    """T021 — 脚手架创建的模块可被 PluginManager 发现"""

    def test_discover_created_module(self, modules_tmp):
        from scripts.create_module import create_module
        from toolkit.core.plugin_manager import PluginManager

        create_module("new_tool")
        pm = PluginManager(modules_tmp)
        manifests = pm.discover_modules()
        names = [m["name"] for m in manifests]
        assert "new_tool" in names

    def test_manifest_has_required_fields(self, modules_tmp):
        from scripts.create_module import create_module
        from toolkit.core.plugin_manager import PluginManager

        create_module("field_check")
        pm = PluginManager(modules_tmp)
        manifests = pm.discover_modules()
        m = next(x for x in manifests if x["name"] == "field_check")
        for key in ("name", "version", "entry"):
            assert key in m, f"manifest 缺少字段: {key}"


class TestScaffoldErrors:
    """T022 — 脚手架错误处理测试"""

    def test_invalid_name_uppercase(self, modules_tmp):
        from scripts.create_module import create_module

        with pytest.raises(SystemExit):
            create_module("MyModule")

    def test_invalid_name_starts_with_number(self, modules_tmp):
        from scripts.create_module import create_module

        with pytest.raises(SystemExit):
            create_module("1_module")

    def test_invalid_name_special_chars(self, modules_tmp):
        from scripts.create_module import create_module

        with pytest.raises(SystemExit):
            create_module("my-module")

    def test_duplicate_module_name(self, modules_tmp):
        from scripts.create_module import create_module

        create_module("dup_test")
        with pytest.raises(SystemExit):
            create_module("dup_test")

    def test_invalid_name_empty(self, modules_tmp):
        from scripts.create_module import create_module

        with pytest.raises(SystemExit):
            create_module("")
