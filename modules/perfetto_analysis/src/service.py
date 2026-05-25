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
        """查询分析历史记录，返回归一化字段名。

        Args:
            limit: 最大返回条数，0 表示不限制。

        Returns:
            每个 dict 包含：id, trace_path, process_name, mode, dimensions,
            result_dir, status, created_at (ISO 字符串), error_message
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
                has_report = (
                    (child / "jank_report.md").exists()
                    or (child / "report.html").exists()
                )
                has_data = (child / "data").exists() or (child / "chapters").exists()
                if not has_report and not has_data:
                    continue
                db_records.append({
                    "task_id": "",
                    "trace_path": "",
                    "process_name": "",
                    "mode": "",
                    "dimensions": "",
                    "report_dir_path": str(child),
                    "status": "COMPLETED",
                    "created_at": int(child.stat().st_mtime),
                })

        return self._normalize_history(db_records)

    def create_analysis_record(
        self,
        task_id: str,
        trace_path: str,
        process_name: str = "",
        status: str = "PENDING",
        result_dir: str = "",
    ) -> None:
        """写入分析任务记录到 pa_analysis_tasks。

        Args:
            task_id: 分析任务唯一标识
            trace_path: 关联的 trace 文件路径
            process_name: 目标进程名
            status: 任务状态（PENDING/COMPLETED/FAILED 等）
            result_dir: 结果目录路径
        """
        import time
        now = int(time.time())
        conn = self._get_shared_db_conn()
        if conn:
            try:
                conn.execute(
                    """
                    INSERT INTO pa_analysis_tasks
                        (task_id, trace_path, process_name, status, report_dir_path, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (task_id, trace_path, process_name, status.upper(), result_dir, now),
                )
                conn.commit()
                logger.debug("分析任务已创建: %s", task_id)
            except Exception as e:
                logger.warning("创建分析任务失败: %s", e)
            finally:
                if conn != self._db_manager.connection if self._db_manager else None:
                    conn.close()

    def update_analysis_record(
        self,
        task_id: str,
        status: str,
        result_dir: str = "",
        error_message: str = "",
    ) -> None:
        """更新分析任务状态。

        Args:
            task_id: 分析任务唯一标识
            status: 新状态（COMPLETED/FAILED/TIMEOUT/CANCELLED）
            result_dir: 结果目录路径
            error_message: 错误信息（失败时）
        """
        import time
        now = int(time.time())
        completed_at = now if status.upper() in ("COMPLETED", "FAILED", "TIMEOUT", "CANCELLED") else None
        conn = self._get_shared_db_conn()
        if conn:
            try:
                if completed_at is not None:
                    conn.execute(
                        """
                        UPDATE pa_analysis_tasks
                        SET status = ?, report_dir_path = ?, error_message = ?, completed_at = ?
                        WHERE task_id = ?
                        """,
                        (status.upper(), result_dir, error_message, completed_at, task_id),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE pa_analysis_tasks
                        SET status = ?, report_dir_path = ?, error_message = ?
                        WHERE task_id = ?
                        """,
                        (status.upper(), result_dir, error_message, task_id),
                    )
                conn.commit()
                logger.debug("分析任务已更新: %s → %s", task_id, status)
            except Exception as e:
                logger.warning("更新分析任务失败: %s", e)
            finally:
                if conn != self._db_manager.connection if self._db_manager else None:
                    conn.close()

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _normalize_history(self, records: list[dict]) -> list[dict]:
        """归一化历史记录字段名和时间格式。"""
        from datetime import datetime as _dt

        result = []
        for r in records:
            normalized = {
                "id": r.get("task_id", ""),
                "trace_path": r.get("trace_path", ""),
                "process_name": r.get("process_name", ""),
                "mode": r.get("mode", ""),
                "dimensions": r.get("dimensions", ""),
                "result_dir": r.get("report_dir_path", ""),
                "status": str(r.get("status", "PENDING")).upper(),
                "error_message": r.get("error_message", ""),
                "created_at": self._convert_timestamp(r.get("created_at")),
            }
            result.append(normalized)
        return result

    @staticmethod
    def _convert_timestamp(ts) -> str:
        """将 INTEGER epoch 时间戳转换为 ISO 格式字符串。"""
        from datetime import datetime as _dt

        if ts is None or ts == 0 or ts == "":
            return ""
        try:
            if isinstance(ts, (int, float)):
                if ts > 1e15:  # nanoseconds (Perfetto convention)
                    ts = ts / 1e9
                return _dt.fromtimestamp(ts).isoformat()
            return str(ts)
        except (ValueError, OSError):
            return str(ts)

    def _get_shared_db_conn(self):
        """获取共享 DB 连接（用于写入）。"""
        if self._db_manager:
            return self._db_manager.connection
        db_path = self._get_shared_db_path()
        if db_path:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            return conn
        return None

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
        """统一输出目录: dev: <root>/data/output/trace_report/；frozen: <exe>/output/trace_report/"""
        from toolkit.core.app_paths import get_output_dir
        return str(get_output_dir("trace_report"))

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
