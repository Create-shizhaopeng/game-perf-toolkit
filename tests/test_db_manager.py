"""DatabaseManager 单元测试"""

from __future__ import annotations

from pathlib import Path

import pytest

from toolkit.core.db_manager import DatabaseManager


class TestDatabaseManager:
    def test_connect_creates_db(self, db_path: Path) -> None:
        db = DatabaseManager(db_path)
        db.connect()
        assert db_path.exists()
        db.close()

    def test_connect_creates_parent_dirs(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "test.db"
        db = DatabaseManager(deep)
        db.connect()
        assert deep.exists()
        db.close()

    def test_migration_table_created(self, db_path: Path) -> None:
        db = DatabaseManager(db_path)
        db.connect()
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrations'"
        )
        assert len(rows) == 1
        db.close()

    def test_execute_insert_and_select(self, db_path: Path) -> None:
        db = DatabaseManager(db_path)
        db.connect()
        db.execute(
            "CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)", commit=True,
        )
        db.execute(
            "INSERT INTO test (val) VALUES (?)", ("hello",), commit=True,
        )
        rows = db.execute("SELECT val FROM test")
        assert len(rows) == 1
        assert rows[0]["val"] == "hello"
        db.close()

    def test_execute_many(self, db_path: Path) -> None:
        db = DatabaseManager(db_path)
        db.connect()
        db.execute("CREATE TABLE nums (n INTEGER)", commit=True)
        db.execute_many(
            "INSERT INTO nums (n) VALUES (?)", [(1,), (2,), (3,)],
        )
        rows = db.execute("SELECT n FROM nums ORDER BY n")
        assert [r["n"] for r in rows] == [1, 2, 3]
        db.close()

    def test_run_migrations(self, db_path: Path, tmp_path: Path) -> None:
        db = DatabaseManager(db_path)
        db.connect()

        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "001_init.sql").write_text(
            "CREATE TABLE devices (id INTEGER PRIMARY KEY, name TEXT);",
            encoding="utf-8",
        )

        db.run_migrations("test_mod", mig_dir)

        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='devices'"
        )
        assert len(rows) == 1

        applied = db.execute(
            "SELECT filename FROM _migrations WHERE module='test_mod'"
        )
        assert applied[0]["filename"] == "001_init.sql"
        db.close()

    def test_migrations_skip_applied(self, db_path: Path, tmp_path: Path) -> None:
        db = DatabaseManager(db_path)
        db.connect()

        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "001_init.sql").write_text(
            "CREATE TABLE t1 (id INTEGER);", encoding="utf-8",
        )

        db.run_migrations("mod", mig_dir)
        db.run_migrations("mod", mig_dir)

        applied = db.execute("SELECT * FROM _migrations WHERE module='mod'")
        assert len(applied) == 1
        db.close()

    def test_connection_property_raises_when_not_connected(self, db_path: Path) -> None:
        db = DatabaseManager(db_path)
        with pytest.raises(RuntimeError, match="数据库未连接"):
            _ = db.connection

    def test_close_idempotent(self, db_path: Path) -> None:
        db = DatabaseManager(db_path)
        db.connect()
        db.close()
        db.close()

    def test_wal_mode_enabled(self, db_path: Path) -> None:
        db = DatabaseManager(db_path)
        db.connect()
        rows = db.execute("PRAGMA journal_mode")
        assert rows[0][0] == "wal"
        db.close()
