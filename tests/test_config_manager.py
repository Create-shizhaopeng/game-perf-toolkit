"""ConfigManager 单元测试"""

from __future__ import annotations

import json
from pathlib import Path

from toolkit.core.config_manager import ConfigManager


class TestConfigManager:
    def test_default_config_created(self, config_path: Path) -> None:
        cm = ConfigManager(config_path)
        assert config_path.exists()
        data = json.loads(config_path.read_text("utf-8"))
        assert data["theme"] == "dark"

    def test_get_simple_key(self, config_path: Path) -> None:
        cm = ConfigManager(config_path)
        assert cm.get("theme") == "dark"

    def test_get_nested_key(self, config_path: Path) -> None:
        cm = ConfigManager(config_path)
        assert cm.get("window.width") == 1200

    def test_get_missing_key_returns_default(self, config_path: Path) -> None:
        cm = ConfigManager(config_path)
        assert cm.get("nonexistent") is None
        assert cm.get("nonexistent", "fallback") == "fallback"

    def test_set_simple_key(self, config_path: Path) -> None:
        cm = ConfigManager(config_path)
        cm.set("language", "en-US")
        assert cm.get("language") == "en-US"
        reloaded = json.loads(config_path.read_text("utf-8"))
        assert reloaded["language"] == "en-US"

    def test_set_nested_key(self, config_path: Path) -> None:
        cm = ConfigManager(config_path)
        cm.set("window.height", 900)
        assert cm.get("window.height") == 900

    def test_set_creates_intermediate_dicts(self, config_path: Path) -> None:
        cm = ConfigManager(config_path)
        cm.set("new.deeply.nested.key", "value")
        assert cm.get("new.deeply.nested.key") == "value"

    def test_get_theme_and_set_theme(self, config_path: Path) -> None:
        cm = ConfigManager(config_path)
        assert cm.get_theme() == "dark"
        cm.set_theme("light")
        assert cm.get_theme() == "light"

    def test_get_adb_path_and_set(self, config_path: Path) -> None:
        cm = ConfigManager(config_path)
        assert cm.get_adb_path() == ""
        cm.set_adb_path("/usr/bin/adb")
        assert cm.get_adb_path() == "/usr/bin/adb"

    def test_to_dict(self, config_path: Path) -> None:
        cm = ConfigManager(config_path)
        d = cm.to_dict()
        assert isinstance(d, dict)
        assert "theme" in d

    def test_corrupt_config_falls_back(self, config_path: Path) -> None:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("not valid json", encoding="utf-8")
        cm = ConfigManager(config_path)
        assert cm.get("theme") == "dark"

    def test_parent_dir_auto_created(self, tmp_path: Path) -> None:
        deep_path = tmp_path / "a" / "b" / "config.json"
        cm = ConfigManager(deep_path)
        assert deep_path.exists()
