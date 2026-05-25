"""Perfetto 抓取模块 — 历史记录存储层

使用 SQLite 存储历史会话和 trace 文件索引，支持 CRUD 操作。
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

from .models import HistorySession, HistoryStats, HistoryTrace

logger = logging.getLogger(__name__)


class HistoryStorage:
    """历史记录 SQLite 存储。"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._ensure_db_dir()
        self._ensure_tables()

    def _ensure_db_dir(self) -> None:
        """确保数据库目录存在。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        """获取数据库连接（上下文管理器）。"""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_tables(self) -> None:
        """创建历史记录表（如不存在）。"""
        with self._get_conn() as conn:
            conn.executescript("""
                -- sessions 表：会话索引
                CREATE TABLE IF NOT EXISTS pe_history_sessions (
                    id TEXT PRIMARY KEY,
                    dir_path TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    device_model TEXT,
                    device_soc TEXT,
                    trace_count INTEGER DEFAULT 0,
                    total_size_bytes INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                -- traces 表：trace 文件索引
                CREATE TABLE IF NOT EXISTS pe_history_traces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    file_path TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL,
                    device_model TEXT,
                    device_soc TEXT,
                    captured_at TEXT,
                    analysis_status TEXT,
                    target_package TEXT,
                    last_analysis_id TEXT,
                    FOREIGN KEY (session_id) REFERENCES pe_history_sessions(id) ON DELETE CASCADE
                );

                -- 索引
                CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON pe_history_sessions(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_traces_session_id ON pe_history_traces(session_id);
            """)
            self._ensure_extra_columns(conn)
            logger.debug("历史记录表已就绪: %s", self.db_path)

    def _ensure_extra_columns(self, conn: sqlite3.Connection) -> None:
        """向后兼容：为旧数据库动态添加新列。"""
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(pe_history_traces)").fetchall()
        }
        new_cols = [
            ("analysis_status", "TEXT"),
            ("target_package", "TEXT"),
            ("last_analysis_id", "TEXT"),
        ]
        for col_name, col_type in new_cols:
            if col_name not in existing:
                try:
                    conn.execute(
                        f"ALTER TABLE pe_history_traces ADD COLUMN {col_name} {col_type}"
                    )
                    logger.info("已添加列: pe_history_traces.%s", col_name)
                except sqlite3.OperationalError:
                    pass

    def insert_session(self, session: HistorySession) -> None:
        """插入或更新会话记录。"""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO pe_history_sessions 
                    (id, dir_path, created_at, device_model, device_soc, trace_count, total_size_bytes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    trace_count = excluded.trace_count,
                    total_size_bytes = excluded.total_size_bytes,
                    updated_at = excluded.updated_at
                """,
                (
                    session.id,
                    str(session.dir_path),
                    session.created_at.isoformat(),
                    session.device_model,
                    session.device_soc,
                    session.trace_count,
                    session.total_size_bytes,
                    now,
                ),
            )
        logger.debug("会话已保存: %s", session.id)

    def insert_trace(self, trace: HistoryTrace) -> int:
        """插入 trace 记录，返回自增 ID。"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pe_history_traces 
                    (session_id, file_path, file_name, file_size_bytes, device_model, device_soc, captured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_size_bytes = excluded.file_size_bytes
                """,
                (
                    trace.session_id,
                    str(trace.file_path),
                    trace.file_name,
                    trace.file_size_bytes,
                    trace.device_model,
                    trace.device_soc,
                    trace.captured_at.isoformat() if trace.captured_at else None,
                ),
            )
            trace_id = cursor.lastrowid
        logger.debug("Trace 已保存: %s (id=%d)", trace.file_name, trace_id or 0)
        return trace_id or 0

    def get_all_sessions(self) -> list[HistorySession]:
        """获取所有会话（按时间倒序）。"""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT id, dir_path, created_at, device_model, device_soc, trace_count, total_size_bytes
                FROM pe_history_sessions
                ORDER BY created_at DESC
                """
            ).fetchall()

        sessions = []
        for row in rows:
            sessions.append(
                HistorySession(
                    id=row["id"],
                    dir_path=Path(row["dir_path"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    device_model=row["device_model"],
                    device_soc=row["device_soc"],
                    trace_count=row["trace_count"],
                    total_size_bytes=row["total_size_bytes"],
                )
            )
        return sessions

    def get_traces_by_session(self, session_id: str) -> list[HistoryTrace]:
        """获取指定会话的所有 trace。"""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, file_path, file_name, file_size_bytes, device_model, device_soc, captured_at
                FROM pe_history_traces
                WHERE session_id = ?
                ORDER BY captured_at DESC, file_name
                """,
                (session_id,),
            ).fetchall()

        traces = []
        for row in rows:
            traces.append(
                HistoryTrace(
                    id=row["id"],
                    session_id=row["session_id"],
                    file_path=Path(row["file_path"]),
                    file_name=row["file_name"],
                    file_size_bytes=row["file_size_bytes"],
                    device_model=row["device_model"],
                    device_soc=row["device_soc"],
                    captured_at=(
                        datetime.fromisoformat(row["captured_at"])
                        if row["captured_at"]
                        else None
                    ),
                )
            )
        return traces

    def delete_session(self, session_id: str) -> bool:
        """删除会话（级联删除关联 traces）。"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM pe_history_sessions WHERE id = ?",
                (session_id,),
            )
            deleted = cursor.rowcount > 0
        if deleted:
            logger.info("会话已删除: %s", session_id)
        return deleted

    def delete_trace(self, trace_id: int) -> bool:
        """删除单个 trace 记录。"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM pe_history_traces WHERE id = ?",
                (trace_id,),
            )
            deleted = cursor.rowcount > 0
        if deleted:
            logger.debug("Trace 已删除: id=%d", trace_id)
        return deleted

    def delete_trace_by_path(self, file_path: Path) -> bool:
        """根据文件路径删除 trace 记录。"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM pe_history_traces WHERE file_path = ?",
                (str(file_path),),
            )
            deleted = cursor.rowcount > 0
        if deleted:
            logger.debug("Trace 已删除: %s", file_path)
        return deleted

    def get_stats(self) -> HistoryStats:
        """获取历史记录统计信息。"""
        with self._get_conn() as conn:
            session_row = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_sessions,
                    MIN(created_at) as oldest,
                    MAX(created_at) as newest
                FROM pe_history_sessions
                """
            ).fetchone()

            trace_row = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_traces,
                    COALESCE(SUM(file_size_bytes), 0) as total_size
                FROM pe_history_traces
                """
            ).fetchone()

        return HistoryStats(
            total_sessions=session_row["total_sessions"] or 0,
            total_traces=trace_row["total_traces"] or 0,
            total_size_bytes=trace_row["total_size"] or 0,
            oldest_session=(
                datetime.fromisoformat(session_row["oldest"])
                if session_row["oldest"]
                else None
            ),
            newest_session=(
                datetime.fromisoformat(session_row["newest"])
                if session_row["newest"]
                else None
            ),
        )

    def get_session_ids(self) -> set[str]:
        """获取所有会话 ID 集合。"""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT id FROM pe_history_sessions").fetchall()
        return {row["id"] for row in rows}

    def get_session_dir_paths(self) -> dict[str, Path]:
        """获取会话 ID 到目录路径的映射。"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, dir_path FROM pe_history_sessions"
            ).fetchall()
        return {row["id"]: Path(row["dir_path"]) for row in rows}

    def clear_all(self) -> int:
        """清空所有历史记录，返回删除的会话数。"""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM pe_history_sessions")
            count = cursor.rowcount
        logger.info("已清空 %d 个会话的历史记录", count)
        return count

    # ── 分析任务 CRUD 已迁移至 PerfettoAnalysisService (pa_analysis_tasks) ──
