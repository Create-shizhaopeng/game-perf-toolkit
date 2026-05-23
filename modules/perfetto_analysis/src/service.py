# -*- coding: utf-8 -*-
"""Perfetto 解析分析 — 服务层（配置 + 历史记录）。

分析能力已迁移至 Skill YAML + pa_execute_sql 工具。
本服务仅保留配置管理和历史记录查询。
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from .models import AnalysisConfig, load_config, save_config

from . import strings_service as s


class PerfettoAnalysisService:
    """Perfetto 解析分析服务 — 配置管理与历史记录。"""

    def __init__(
        self,
        data_dir: str | Path,
        db_manager: Any = None,
        root_dir: str | Path | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db_manager = db_manager
        self._root_dir = Path(root_dir) if root_dir else None
        self._cfg = load_config()
        self._check_perfetto_available()

    # ------------------------------------------------------------------
    # 配置管理
    # ------------------------------------------------------------------

    def get_service_info(self) -> dict[str, str]:
        return {
            "name": "perfetto_analysis",
            "display_name": s.SERVICE_DISPLAY_NAME,
            "version": "0.2.0",
        }

    def get_config(self) -> AnalysisConfig:
        return self._cfg

    def reload_config(self, config_path: Path | None = None) -> AnalysisConfig:
        self._cfg = load_config(config_path)
        return self._cfg

    def save_current_config(self) -> Path:
        return save_config(self._cfg)

    @property
    def perfetto_available(self) -> bool:
        return self._perfetto_available

    # ------------------------------------------------------------------
    # 历史记录
    # ------------------------------------------------------------------

    def get_analysis_history(self, limit: int = 0) -> list[dict[str, Any]]:
        """查询分析历史记录。

        Args:
            limit: 最大返回条数，0 表示不限制。
        """
        db_records: list[dict[str, Any]] = []
        if self._db_manager:
            try:
                conn = self._db_manager.connection
                sql = "SELECT * FROM pa_analysis_tasks ORDER BY created_at DESC"
                if limit > 0:
                    sql += f" LIMIT {int(limit)}"
                cursor = conn.execute(sql)
                columns = [desc[0] for desc in cursor.description]
                db_records = [dict(zip(columns, row)) for row in cursor.fetchall()]
            except Exception:
                pass

        output_dir = Path(self._get_output_dir())
        if output_dir.exists():
            tracked_dirs = {
                str(Path(r.get("report_dir_path", "")).resolve())
                for r in db_records
                if r.get("report_dir_path")
            }
            for child in sorted(output_dir.iterdir(), reverse=True):
                if limit > 0 and len(db_records) >= limit:
                    break
                if not child.is_dir():
                    continue
                resolved = str(child.resolve())
                if resolved in tracked_dirs:
                    continue
                has_report = (child / "jank_report.md").exists()
                has_data = (child / "data").exists()
                if not has_report and not has_data:
                    continue
                db_records.append({
                    "task_id": "",
                    "trace_path": "",
                    "process_name": "",
                    "mode": "",
                    "dimensions": "",
                    "report_dir_path": str(child),
                    "status": "completed",
                    "created_at": int(child.stat().st_mtime * 1e9),
                })

        return db_records

    def delete_analysis_record(
        self,
        task_id: str = "",
        trace_path: str = "",
        report_dir: str = "",
    ) -> bool:
        """从共享 DB 中删除单条分析记录。

        Returns:
            True 表示可以安全删除磁盘目录。
        """
        db_path = self._get_shared_db_path()
        if not db_path:
            return True
        try:
            conn = sqlite3.connect(str(db_path))
            if task_id:
                conn.execute(
                    "DELETE FROM pa_analysis_tasks WHERE task_id = ?",
                    (task_id,),
                )
            elif report_dir:
                conn.execute(
                    "DELETE FROM pa_analysis_tasks WHERE report_dir_path = ?",
                    (report_dir,),
                )

            can_delete_dir = True
            if report_dir:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM pa_analysis_tasks "
                    "WHERE report_dir_path = ?",
                    (report_dir,),
                )
                can_delete_dir = (cursor.fetchone()[0] == 0)

            conn.commit()
            conn.close()
            return can_delete_dir
        except Exception:
            return True

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _get_output_dir(self) -> str:
        """开发环境: data/output/trace_report/"""
        from toolkit.core.app_paths import get_exe_dir, is_frozen

        if is_frozen():
            return str(get_exe_dir() / "output" / "trace_report")
        if self._root_dir:
            return str(self._root_dir / "data" / "output" / "trace_report")
        return str(self._data_dir / "output" / "trace_report")

    def _check_perfetto_available(self) -> None:
        try:
            import perfetto  # noqa: F401
            self._perfetto_available = True
        except ImportError:
            self._perfetto_available = False

    def _get_shared_db_path(self) -> Path | None:
        if not self._db_manager:
            return None
        return getattr(self._db_manager, "_db_path", None)
