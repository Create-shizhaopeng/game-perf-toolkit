"""PluginManager 单元测试"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from toolkit.core.plugin_manager import PluginManager, PluginLoadError


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
            "dependencies": {"toolkit_modules": []},
        }
        (good_mod / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8",
        )

        pm = PluginManager(mods)
        manifests = pm.discover_modules()
        names = [m["name"] for m in manifests]
        assert "good_module" in names

    def test_topological_sort(self, tmp_path: Path) -> None:
        mods = tmp_path / "modules"
        mods.mkdir()

        # mod_b 依赖 mod_a
        manifest_a = {
            "name": "mod_a",
            "entry": "src.plugin",
            "dependencies": {"toolkit_modules": []},
        }
        manifest_b = {
            "name": "mod_b",
            "entry": "src.plugin",
            "dependencies": {"toolkit_modules": ["mod_a"]},
        }
        for name, m in [("mod_a", manifest_a), ("mod_b", manifest_b)]:
            d = mods / name
            d.mkdir()
            (d / "manifest.json").write_text(json.dumps(m))

        pm = PluginManager(mods)
        manifests = pm.discover_modules()
        names = [m["name"] for m in manifests]
        assert names.index("mod_a") < names.index("mod_b")
