"""toolkit.core.portable_migration 单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from toolkit.core.portable_migration import (
    MIGRATION_MARKER,
    PortableMigrator,
)


@pytest.fixture
def isolated_migrator(monkeypatch, tmp_path):
    """用 tmp_path 隔离三层根，避免污染真实 APPDATA。"""
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    config_dir.mkdir()
    data_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(
        "toolkit.core.portable_migration.get_user_config_dir", lambda: config_dir
    )
    monkeypatch.setattr(
        "toolkit.core.portable_migration.get_user_data_dir", lambda: data_dir
    )
    monkeypatch.setattr(
        "toolkit.core.portable_migration.get_user_output_dir", lambda: output_dir
    )
    return PortableMigrator(), {"config": config_dir, "data": data_dir, "output": output_dir}


def _make_portable_source(tmp_path: Path) -> Path:
    """构造一个旧便携版目录结构。"""
    src = tmp_path / "old_toolkit"
    (src / "data" / "config").mkdir(parents=True)
    (src / "data" / "db").mkdir(parents=True)
    (src / "data" / "backup" / "game_perf").mkdir(parents=True)
    (src / "data" / "logs").mkdir(parents=True)
    (src / "output" / "trace").mkdir(parents=True)
    (src / "output" / "trace_report").mkdir(parents=True)

    # config
    (src / "data" / "config" / "toolkit_config.json").write_text(
        json.dumps({"theme": "dark"}), encoding="utf-8"
    )
    (src / "data" / "config" / "llm_manager_llm_providers.json").write_text("{}", encoding="utf-8")
    # db
    (src / "data" / "db" / "toolkit.db").write_bytes(b"dbcontent")
    (src / "data" / "db" / "perfetto_capture_history.db").write_bytes(b"hist")
    # backup
    (src / "data" / "backup" / "game_perf" / "gameperfconfig.xml").write_text(
        "<config/>", encoding="utf-8"
    )
    # logs（应跳过）
    (src / "data" / "logs" / "app_2026.log").write_text("log", encoding="utf-8")
    # output
    (src / "output" / "trace" / "current_1.perfetto-trace").write_bytes(b"trace")
    (src / "output" / "trace_report" / "session1").mkdir(parents=True, exist_ok=True)
    (src / "output" / "trace_report" / "session1" / "jank_report.md").write_text(
        "# report", encoding="utf-8"
    )
    return src


class TestValidateSource:
    def test_valid_source(self, tmp_path):
        src = _make_portable_source(tmp_path)
        m = PortableMigrator.__new__(PortableMigrator)
        assert m.validate_source(src) is True

    def test_invalid_no_data_dir(self, tmp_path):
        src = tmp_path / "empty"
        src.mkdir()
        m = PortableMigrator.__new__(PortableMigrator)
        assert m.validate_source(src) is False

    def test_invalid_not_dir(self, tmp_path):
        m = PortableMigrator.__new__(PortableMigrator)
        assert m.validate_source(tmp_path / "nonexistent") is False


class TestIsMigrationNeeded:
    def test_needed_when_no_marker_no_configs(self, isolated_migrator):
        m, dirs = isolated_migrator
        assert m.is_migration_needed() is True

    def test_not_needed_when_marker_exists(self, isolated_migrator):
        m, dirs = isolated_migrator
        (dirs["config"] / MIGRATION_MARKER).write_text("ts|src", encoding="utf-8")
        assert m.is_migration_needed() is False

    def test_not_needed_when_configs_exist(self, isolated_migrator):
        m, dirs = isolated_migrator
        (dirs["config"] / "toolkit_config.json").write_text("{}", encoding="utf-8")
        assert m.is_migration_needed() is False


class TestMigrateMappings:
    """验证各层映射规则。"""

    def test_config_migrated_to_roaming(self, isolated_migrator, tmp_path):
        m, dirs = isolated_migrator
        src = _make_portable_source(tmp_path)
        result = m.migrate(src)
        dst = dirs["config"] / "toolkit_config.json"
        assert dst.exists()
        assert json.loads(dst.read_text(encoding="utf-8"))["theme"] == "dark"
        assert any("toolkit_config.json" in f for f in result.migrated_files)

    def test_db_migrated_to_local_db(self, isolated_migrator, tmp_path):
        m, dirs = isolated_migrator
        src = _make_portable_source(tmp_path)
        m.migrate(src)
        assert (dirs["data"] / "db" / "toolkit.db").read_bytes() == b"dbcontent"
        assert (dirs["data"] / "db" / "perfetto_capture_history.db").exists()

    def test_backup_migrated_to_local_backup(self, isolated_migrator, tmp_path):
        m, dirs = isolated_migrator
        src = _make_portable_source(tmp_path)
        m.migrate(src)
        assert (dirs["data"] / "backup" / "game_perf" / "gameperfconfig.xml").read_text(
            encoding="utf-8"
        ) == "<config/>"

    def test_logs_not_migrated(self, isolated_migrator, tmp_path):
        m, dirs = isolated_migrator
        src = _make_portable_source(tmp_path)
        m.migrate(src)
        # logs 不应出现在任何目标层
        assert not (dirs["data"] / "logs").exists()
        assert not any("logs" in f for f in m.migrate(src).migrated_files)

    def test_trace_migrated_to_output(self, isolated_migrator, tmp_path):
        m, dirs = isolated_migrator
        src = _make_portable_source(tmp_path)
        m.migrate(src)
        assert (dirs["output"] / "trace" / "current_1.perfetto-trace").read_bytes() == b"trace"

    def test_trace_report_migrated_to_output(self, isolated_migrator, tmp_path):
        m, dirs = isolated_migrator
        src = _make_portable_source(tmp_path)
        m.migrate(src)
        assert (dirs["output"] / "trace_report" / "session1" / "jank_report.md").read_text(
            encoding="utf-8"
        ) == "# report"


class TestSkipExistingNewer:
    def test_skips_when_dst_newer(self, isolated_migrator, tmp_path):
        m, dirs = isolated_migrator
        src = _make_portable_source(tmp_path)
        # 预置一个更新的目标
        dst = dirs["config"] / "toolkit_config.json"
        dst.write_text(json.dumps({"existing": True}), encoding="utf-8")
        result = m.migrate(src)
        assert any(str(dst) in f for f in result.skipped_files)
        # 内容未被覆盖
        assert json.loads(dst.read_text(encoding="utf-8"))["existing"] is True


class TestMarker:
    def test_marker_written_after_migrate(self, isolated_migrator, tmp_path):
        m, dirs = isolated_migrator
        src = _make_portable_source(tmp_path)
        result = m.migrate(src)
        assert result.marker_written is True
        assert (dirs["config"] / MIGRATION_MARKER).exists()

    def test_marker_suppresses_recheck(self, isolated_migrator, tmp_path):
        m, dirs = isolated_migrator
        src = _make_portable_source(tmp_path)
        m.migrate(src)
        assert m.is_migration_needed() is False

    def test_skip_marker_written(self, isolated_migrator):
        m, dirs = isolated_migrator
        m.write_skip_marker()
        assert (dirs["config"] / MIGRATION_MARKER).exists()
        assert m.is_migration_needed() is False

    def test_read_marker_returns_content(self, isolated_migrator):
        m, dirs = isolated_migrator
        m.write_skip_marker()
        info = m.read_marker()
        assert info is not None
        assert "timestamp" in info


class TestFailureHandling:
    def test_invalid_source_returns_failure(self, isolated_migrator, tmp_path):
        m, dirs = isolated_migrator
        bad = tmp_path / "nope"
        bad.mkdir()
        result = m.migrate(bad)
        assert result.success is False
        assert result.failed_files

    def test_partial_failure_preserves_copied(self, isolated_migrator, tmp_path, monkeypatch):
        m, dirs = isolated_migrator
        src = _make_portable_source(tmp_path)

        # 让第二个文件的复制抛异常
        original_copy = m._copy_if_needed
        call_count = {"n": 0}

        def flaky_copy(s, d, r):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise OSError("simulated")
            original_copy(s, d, r)

        monkeypatch.setattr(m, "_copy_if_needed", flaky_copy)
        result = m.migrate(src)
        assert result.failed_files
        assert result.migrated_files  # 第一个仍成功

    def test_progress_callback_invoked(self, isolated_migrator, tmp_path):
        m, dirs = isolated_migrator
        src = _make_portable_source(tmp_path)
        progress = []
        m.migrate(src, on_progress=lambda f, d, t: progress.append((d, t)))
        assert progress  # 回调被调用
        assert all(d <= t for d, t in progress)  # done <= total
