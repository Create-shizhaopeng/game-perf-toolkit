"""toolkit.core.app_paths 单元测试"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from toolkit.core.app_paths import (
    get_backup_path,
    get_config_path,
    get_db_path,
    get_exe_dir,
    is_frozen,
)

_FAKE_EXE = "/fake_dir/Toolkit.exe"


class TestIsFrozen:
    def test_dev_mode(self):
        assert is_frozen() is False

    def test_frozen_mode(self):
        with patch.object(sys, "frozen", True, create=True):
            assert is_frozen() is True


class TestGetExeDir:
    def test_dev_returns_project_root(self):
        result = get_exe_dir()
        assert (result / "toolkit").is_dir()
        assert (result / "modules").is_dir()

    def test_frozen_returns_exe_parent(self):
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", _FAKE_EXE):
                result = get_exe_dir()
                assert result == Path(_FAKE_EXE).resolve().parent


class TestGetConfigPath:
    def test_dev_path(self):
        p = get_config_path("device_disguise", "device_info.json")
        expected = get_exe_dir() / "modules" / "device_disguise" / "config" / "device_info.json"
        assert p == expected

    def test_frozen_path(self):
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", _FAKE_EXE):
                p = get_config_path("agent_chat", "config.json")
                parts = p.parts
                assert parts[-1] == "agent_chat_config.json"
                assert "config" in parts
                assert "data" in parts


class TestGetDbPath:
    def test_naming(self):
        p = get_db_path("agent_chat", "conversation")
        assert p.name == "agent_chat_conversation.db"

    def test_dev_and_frozen_same_structure(self):
        p1 = get_db_path("perfetto_analysis", "storage")
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", _FAKE_EXE):
                p2 = get_db_path("perfetto_analysis", "storage")
        assert p1.name == p2.name
        assert p1.parts[-1] == "perfetto_analysis_storage.db"

    def test_path_includes_db_dir(self):
        p = get_db_path("test_mod", "test")
        assert "db" in p.parts


class TestGetBackupPath:
    def test_without_filename_returns_dir(self):
        p = get_backup_path("game_perf")
        assert p.parts[-1] == "game_perf"
        assert "backup" in p.parts

    def test_with_filename(self):
        p = get_backup_path("game_perf", "gameperfconfig.xml")
        assert p.parts[-2] == "game_perf"
        assert p.parts[-1] == "gameperfconfig.xml"
