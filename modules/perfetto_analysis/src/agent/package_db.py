"""包名↔进程名映射数据库 — 自动学习 + JSON 导入/导出。"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class PackageMappingDB:
    """维护包名与进程名的映射关系。"""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        with self._get_conn() as conn:
            # 迁移旧表名 pe_ → pa_
            try:
                conn.execute(
                    "ALTER TABLE pe_package_mappings RENAME TO pa_package_mappings"
                )
                logger.info("已迁移表名 pe_package_mappings → pa_package_mappings")
            except sqlite3.OperationalError:
                pass  # 旧表不存在或已迁移

            conn.execute("""
                CREATE TABLE IF NOT EXISTS pa_package_mappings (
                    package_name TEXT NOT NULL,
                    process_name TEXT NOT NULL,
                    app_label TEXT DEFAULT '',
                    hit_count INTEGER DEFAULT 1,
                    last_used TEXT NOT NULL,
                    PRIMARY KEY (package_name, process_name)
                )
            """)

    def learn(self, package_name: str, process_name: str, app_label: str = "") -> None:
        """学习/更新包名映射。"""
        if not package_name or not process_name:
            return
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO pa_package_mappings (package_name, process_name, app_label, hit_count, last_used)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(package_name, process_name) DO UPDATE SET
                    hit_count = hit_count + 1,
                    last_used = ?,
                    app_label = CASE WHEN ? != '' THEN ? ELSE app_label END
                """,
                (package_name, process_name, app_label, now, now, app_label, app_label),
            )
        logger.debug("学习包名映射: %s -> %s", package_name, process_name)

    def lookup(self, package_name: str) -> list[str]:
        """查询包名对应的进程名列表（按使用频次排序）。"""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT process_name FROM pa_package_mappings
                WHERE package_name = ?
                ORDER BY hit_count DESC
                """,
                (package_name,),
            ).fetchall()
        return [row["process_name"] for row in rows]

    def suggest(self, partial: str) -> list[dict]:
        """根据部分包名或进程名搜索建议。"""
        pattern = f"%{partial}%"
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT package_name, process_name, app_label, hit_count
                FROM pa_package_mappings
                WHERE package_name LIKE ? OR process_name LIKE ? OR app_label LIKE ?
                ORDER BY hit_count DESC
                LIMIT 10
                """,
                (pattern, pattern, pattern),
            ).fetchall()
        return [dict(row) for row in rows]

    def export_json(self, path: str | Path) -> int:
        """导出所有映射到 JSON 文件，返回导出数量。"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT package_name, process_name, app_label, hit_count FROM pa_package_mappings"
            ).fetchall()

        data = [dict(row) for row in rows]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("已导出 %d 条包名映射到: %s", len(data), path)
        return len(data)

    def import_json(self, path: str | Path) -> int:
        """从 JSON 文件导入映射，返回导入数量。"""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for entry in data:
            pkg = entry.get("package_name", "")
            proc = entry.get("process_name", "")
            label = entry.get("app_label", "")
            if pkg and proc:
                self.learn(pkg, proc, label)
                count += 1

        logger.info("已导入 %d 条包名映射从: %s", count, path)
        return count

    def get_all(self) -> list[dict]:
        """获取所有映射记录。"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pa_package_mappings ORDER BY hit_count DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def delete(self, package_name: str, process_name: str) -> bool:
        """删除指定映射。"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM pa_package_mappings WHERE package_name = ? AND process_name = ?",
                (package_name, process_name),
            )
            return cursor.rowcount > 0
