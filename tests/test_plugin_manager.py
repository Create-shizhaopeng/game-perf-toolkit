"""PluginManager 单元测试"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from toolkit.core.plugin_manager import PluginManager, PluginConflictError, PluginLoadError


class TestPluginManager:
    def test_discover_valid_module(self, modules_dir: Path) -> None:
        pm = PluginManager(modules_dir)
        manifests = pm.discover_modules()
        assert len(manifests) == 1
        assert manifests[0]["name"] == "test_module"

    def test_discover_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "modules"
        empty.mkdir()
        pm = PluginManager(empty)
        assert pm.discover_modules() == []

    def test_discover_skips_invalid_manifest(self, tmp_path: Path) -> None:
        mods = tmp_path / "modules"
        bad_mod = mods / "bad_module"
        bad_mod.mkdir(parents=True)
        (bad_mod / "manifest.json").write_text("not json", encoding="utf-8")

        good_mod = mods / "good_module"
        good_mod.mkdir()
        manifest = {
            "name": "good_module",
            "display_name": "Good",
            "version": "1.0.0",
            "entry": "src.plugin",
            "cli_namespace": "good",
            "dependencies": {"toolkit_modules": []},
        }
        (good_mod / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8",
        )

        pm = PluginManager(mods)
        manifests = pm.discover_modules()
        names = [m["name"] for m in manifests]
        assert "good_module" in names

    def test_cli_namespace_conflict_detected(self) -> None:
        pm = PluginManager(Path("dummy"))
        manifest_a = {"name": "mod_a", "cli_namespace": "same_ns", "_path": Path("a")}
        manifest_b = {"name": "mod_b", "cli_namespace": "same_ns", "_path": Path("b")}
        pm._validate_cli_namespace(manifest_a)
        with pytest.raises(PluginConflictError, match="冲突"):
            pm._validate_cli_namespace(manifest_b)

    def test_reserved_namespace_rejected(self) -> None:
        pm = PluginManager(Path("dummy"))
        manifest = {"name": "bad_ns", "cli_namespace": "config", "_path": Path("x")}
        with pytest.raises(PluginConflictError, match="预留"):
            pm._validate_cli_namespace(manifest)
