"""SQLite 数据库管理 — 统一的数据库访问和迁移机制"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DatabaseManager:
    """SQLite 数据库管理器。

    提供连接管理、SQL 执行和模块迁移支持。
    数据库文件默认位于 data/toolkit.db。
    """

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path("data/toolkit.db")
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """建立数据库连接。"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_migration_table()
        logger.info("数据库已连接: %s", self._db_path)

    def _init_migration_table(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                module      TEXT NOT NULL,
                filename    TEXT NOT NULL,
                applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(module, filename)
            )
        """)
        self._conn.commit()

    def run_migrations(self, module_name: str, migrations_dir: Path) -> None:
        """执行模块的数据库迁移脚本。

        按文件名排序，跳过已执行的迁移。
        """
        if not migrations_dir.exists():
            return
        sql_files = sorted(migrations_dir.glob("*.sql"))
        if not sql_files:
            return

        applied = {
            row["filename"]
            for row in self.execute(
                "SELECT filename FROM _migrations WHERE module = ?",
                (module_name,),
            )
        }

        for sql_file in sql_files:
            if sql_file.name in applied:
                continue
            sql = sql_file.read_text("utf-8")
            try:
                self._conn.executescript(sql)
                self.execute(
                    "INSERT INTO _migrations (module, filename) VALUES (?, ?)",
                    (module_name, sql_file.name),
                )
                self._conn.commit()
                logger.info("迁移完成: %s/%s", module_name, sql_file.name)
            except sqlite3.Error:
                logger.exception("迁移失败: %s/%s", module_name, sql_file.name)
                raise

    def execute(
        self, sql: str, params: tuple = (), *, commit: bool = False
    ) -> list[sqlite3.Row]:
        """执行 SQL 语句并返回结果行。"""
        cursor = self._conn.execute(sql, params)
        if commit:
            self._conn.commit()
        return cursor.fetchall()

    def execute_many(self, sql: str, params_list: list[tuple]) -> None:
        """批量执行 SQL。"""
        self._conn.executemany(sql, params_list)
        self._conn.commit()

    def commit(self) -> None:
        if self._conn:
            self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("数据库已关闭")

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("数据库未连接，请先调用 connect()")
        return self._conn
