"""toolkit.core.app_paths 单元测试 — 三层分层路径架构。

覆盖：
- config 层 (roaming, %APPDATA%)
- data 层 (local, %LOCALAPPDATA% 的 db/backup)
- output 层 (Documents, 可配置)
- get_exe_dir 只读程序资源根语义
- LV_TOOLKIT_DATA_DIR dev 覆盖
- headless 模式路径一致性（无 QCoreApplication）
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from toolkit.core.app_paths import (
    APP_AUTHOR,
    APP_NAME,
    get_backup_path,
    get_config_path,
    get_db_path,
    get_exe_dir,
    get_output_dir,
    get_user_config_dir,
    get_user_data_dir,
    get_user_output_dir,
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
    """get_exe_dir 现在是只读程序资源根，不再用于写用户数据。"""

    def test_dev_returns_project_root(self):
        result = get_exe_dir()
        assert (result / "toolkit").is_dir()
        assert (result / "modules").is_dir()

    def test_frozen_returns_exe_parent(self):
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", _FAKE_EXE):
                result = get_exe_dir()
                assert result == Path(_FAKE_EXE).resolve().parent


class TestThreeTierRoots:
    """三层用户数据根：config roaming / data local / output Documents。"""

    def test_user_config_dir_is_roaming(self, monkeypatch):
        """config 层走 %APPDATA% roaming，路径含 appname 隔离。"""
        monkeypatch.delenv("LV_TOOLKIT_DATA_DIR", raising=False)
        p = get_user_config_dir()
        parts = p.parts
        assert APP_NAME in parts
        assert APP_AUTHOR in parts
        # roaming 标志：路径含 Roaming
        assert "Roaming" in parts or "AppData" in parts

    def test_user_data_dir_is_local(self, monkeypatch):
        """data 层走 %LOCALAPPDATA% local，路径含 appname 隔离。

        显式清除 dev 覆盖环境变量，确保测的是 OS 标准路径。
        """
        monkeypatch.delenv("LV_TOOLKIT_DATA_DIR", raising=False)
        p = get_user_data_dir()
        parts = p.parts
        assert APP_NAME in parts
        assert APP_AUTHOR in parts

    def test_user_output_dir_is_documents(self):
        """output 层默认 Documents/LV Game Toolkit。"""
        p = get_user_output_dir()
        assert p.name == APP_NAME

    def test_roaming_and_local_distinct(self):
        """config(roaming) 与 data(local) 在 Windows 下应不同路径。"""
        cfg = get_user_config_dir()
        data = get_user_data_dir()
        # 在 Windows 上 roaming 走 Roaming，local 走 Local
        if sys.platform == "win32":
            assert cfg != data


class TestGetConfigPath:
    def test_dev_path_uses_module_source_config(self):
        """dev 模式配置来自模块源码（只读模板）。"""
        p = get_config_path("device_disguise", "device_info.json")
        expected = get_exe_dir() / "modules" / "device_disguise" / "config" / "device_info.json"
        assert p == expected

    def test_frozen_path_uses_roaming_root_flattened(self):
        """frozen 模式配置走 roaming 根，扁平命名，无 data/config 子目录。"""
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", _FAKE_EXE):
                p = get_config_path("agent_chat", "config.json")
                # 扁平命名
                assert p.name == "agent_chat_config.json"
                # 在 roaming 根下
                assert p.parent == get_user_config_dir()
                # 不再有 data/config 子目录
                assert "data" not in p.parts


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

    def test_frozen_db_under_local_data_root(self):
        """frozen 模式 db 在 data 层根(db)下，不在 exe 同级。"""
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", _FAKE_EXE):
                p = get_db_path("m1", "d1")
                assert p.parent == get_user_data_dir() / "db"


class TestGetBackupPath:
    def test_without_filename_returns_dir(self):
        p = get_backup_path("game_perf")
        assert p.parts[-1] == "game_perf"
        assert "backup" in p.parts

    def test_with_filename(self):
        p = get_backup_path("game_perf", "gameperfconfig.xml")
        assert p.parts[-2] == "game_perf"
        assert p.parts[-1] == "gameperfconfig.xml"

    def test_frozen_backup_under_local_data_root(self):
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", _FAKE_EXE):
                p = get_backup_path("game_perf")
                assert "backup" in p.parts
                # 不在 exe 同级 data
                assert get_exe_dir() not in p.parents


class TestGetOutputDir:
    def test_dev_output_under_data_root(self):
        """dev 模式 output 在 data 层根下 output/。"""
        p = get_output_dir("trace")
        assert "output" in p.parts
        assert p.name == "trace"

    def test_frozen_output_under_documents(self):
        """frozen 模式 output 走 Documents/LV Game Toolkit。"""
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", _FAKE_EXE):
                p = get_output_dir("trace_report")
                # 在 user output 根下
                assert p.parent == get_user_output_dir()

    def test_creates_directory(self):
        p = get_output_dir("test_module_xyz")
        assert p.is_dir()

    def test_frozen_output_config_override(self, monkeypatch, tmp_path):
        """frozen 模式下 config output_dir 覆盖默认 Documents。"""
        override_dir = tmp_path / "custom_output"
        override_dir.mkdir()
        # 写一个临时 config 文件指向 override
        config_dir = get_user_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        import json

        (config_dir / "toolkit_config.json").write_text(
            json.dumps({"output_dir": str(override_dir)}), encoding="utf-8"
        )
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", _FAKE_EXE):
                p = get_output_dir("trace")
                assert str(p).startswith(str(override_dir))
        # 清理临时 config
        (config_dir / "toolkit_config.json").unlink(missing_ok=True)

    def test_frozen_output_empty_config_uses_default(self, monkeypatch):
        """frozen 模式下 config output_dir 为空时用默认 Documents。"""
        config_dir = get_user_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        import json

        (config_dir / "toolkit_config.json").write_text(
            json.dumps({"output_dir": ""}), encoding="utf-8"
        )
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", _FAKE_EXE):
                p = get_output_dir("trace_report")
                assert p.parent == get_user_output_dir()
        (config_dir / "toolkit_config.json").unlink(missing_ok=True)


class TestDevDataDirOverride:
    """LV_TOOLKIT_DATA_DIR 环境变量在 dev 模式覆盖 data 层根。"""

    def test_override_redirects_data_dir(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LV_TOOLKIT_DATA_DIR", str(tmp_path))
        assert get_user_data_dir() == tmp_path.resolve()

    def test_override_affects_db_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LV_TOOLKIT_DATA_DIR", str(tmp_path))
        p = get_db_path("m", "d")
        assert p.parent == tmp_path.resolve() / "db"

    def test_override_affects_backup_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LV_TOOLKIT_DATA_DIR", str(tmp_path))
        p = get_backup_path("m")
        assert "backup" in p.parts
        assert tmp_path.resolve() in p.parents

    def test_frozen_ignores_override(self, monkeypatch, tmp_path):
        """frozen 模式忽略 LV_TOOLKIT_DATA_DIR，走 OS 标准路径。"""
        monkeypatch.setenv("LV_TOOLKIT_DATA_DIR", str(tmp_path))
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", _FAKE_EXE):
                p = get_db_path("m", "d")
                # 不在 override 目录
                assert tmp_path.resolve() not in p.parents
                assert "db" in p.parts

    def test_unset_uses_os_standard(self, monkeypatch):
        monkeypatch.delenv("LV_TOOLKIT_DATA_DIR", raising=False)
        p = get_user_data_dir()
        # 含 appname 隔离
        assert APP_NAME in p.parts


class TestHeadlessConsistency:
    """headless 模式（无 QCoreApplication）路径仍带 appname 隔离。

    这是 platformdirs 优于 QStandardPaths 的关键约束。
    """

    def test_config_path_isolated_without_qapp(self):
        # 不创建任何 QCoreApplication，直接调用
        p = get_config_path("llm_manager", "llm_providers.json")
        # frozen 模拟
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", _FAKE_EXE):
                p = get_config_path("llm_manager", "llm_providers.json")
                # 必须含 appname 隔离（platformdirs 保证），不能只是 AppData 根
                assert APP_NAME in p.parts or APP_AUTHOR in p.parts

    def test_db_path_isolated_without_qapp(self):
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", _FAKE_EXE):
                p = get_db_path("perfetto_capture", "history")
                assert APP_NAME in p.parts or APP_AUTHOR in p.parts
