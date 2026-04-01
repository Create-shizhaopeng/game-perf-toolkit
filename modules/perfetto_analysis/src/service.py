# -*- coding: utf-8 -*-
"""Perfetto 解析分析 — 服务层。

纯同步 API，不依赖 GUI 框架。GUI/CLI/Agent 共享此接口。
后台长时间操作通过 on_progress 回调报告进度。
"""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

from .models import (
    AnalysisConfig, AnalysisResult, AnalysisTask,
    CompressedSummary, DimensionResult, TraceOverview,
    load_config, save_config,
)

ProgressCallback = Callable[[str], None] | None


class PerfettoAnalysisService:
    """Perfetto 解析分析核心业务逻辑。"""

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
    # 公共 API
    # ------------------------------------------------------------------

    def get_service_info(self) -> dict[str, str]:
        return {
            "name": "perfetto_analysis",
            "display_name": "Perfetto 解析分析",
            "version": "0.1.0",
        }

    def get_config(self) -> AnalysisConfig:
        return self._cfg

    def reload_config(self, config_path: Path | None = None) -> AnalysisConfig:
        self._cfg = load_config(config_path)
        return self._cfg

    def save_current_config(self) -> Path:
        return save_config(self._cfg)

    def analyze(
        self,
        trace_path: str | Path,
        process_name: str = "",
        on_progress: ProgressCallback = None,
    ) -> AnalysisResult:
        """完整分析：Phase 1 解析 + Phase 2 全维度分析 + 导出报告。"""
        trace_path = str(Path(trace_path).resolve())
        process_name = process_name or self._cfg.default_process
        task = self._create_task(trace_path, process_name, "full")

        t0 = time.perf_counter()
        try:
            self._notify(on_progress, "正在加载 trace 文件...")
            self._update_task_status(task, "running")

            from .engine import parser, analyzer, export, report_writer

            # Phase 1: 解析
            self._notify(on_progress, "Phase 1: 丢帧解析中...")
            parse_result, tp = parser.parse_trace_with_tp(
                trace_path,
                self._cfg.refresh_rate_preset,
                process_filter=process_name or None,
            )

            db_path = self._get_db_path()
            self._save_phase1_to_db(parse_result, trace_path, db_path)

            jt = parse_result.get("jank_times", 0)
            fn = parse_result.get("frame_num", 0)
            hz = parse_result.get("inferred_refresh_rate_hz", 60)
            self._notify(
                on_progress,
                f"Phase 1 完成: {jt} 次丢帧, {fn} 帧, {hz}Hz",
            )

            # Phase 2: 分析
            self._notify(on_progress, "Phase 2: 卡顿归因分析中...")
            track_name = parse_result.get("buffer_track_name", "")
            auto_process = self._extract_process_from_track(track_name)
            effective_process_for_analysis = process_name or auto_process
            if effective_process_for_analysis and not process_name:
                self._notify(
                    on_progress,
                    f"自动识别进程: {effective_process_for_analysis}",
                )
                logger.info("BufferTX 轨道: %s → 进程: %s", track_name, auto_process)
            analysis_result = analyzer.analyze_jank(
                tp,
                parse_result,
                process_name=effective_process_for_analysis or None,
                app_type_override=self._cfg.app_type,
                analyze_top=self._cfg.analyze_top,
                slow_binder_ms=self._cfg.slow_binder_threshold_ms,
                sched_latency_ms=self._cfg.sched_latency_threshold_ms,
            )
            self._notify(on_progress, "Phase 2 分析完成")

            # 导出报告
            self._notify(on_progress, "导出报告中...")
            report_dir = report_writer.ensure_report_dir(
                trace_path, self._get_output_dir(),
            )
            offset_ns = parse_result.get("realtime_offset_ns", 0)
            effective_process = process_name or self._extract_process_from_track(
                parse_result.get("buffer_track_name", ""),
            )
            report_content = export.build_full_report(
                trace_path,
                effective_process or None,
                analysis_result.get("app_type", "app"),
                analysis_result.get("cpu_topology", {}),
                parse_result,
                analysis_result,
                offset_ns=offset_ns,
            )
            report_path = report_writer.write_full_report(report_dir, report_content)

            # 写入逐帧 JSON
            for jank_data in analysis_result.get("per_jank_analyses", []):
                idx = jank_data.get("jank_index", 0)
                report_writer.write_jank_data_file(report_dir, idx, jank_data)

            # 写入 summary JSON
            summary = analysis_result.get("summary_analysis", {})
            if summary:
                report_writer.write_summary_data_file(report_dir, summary)

            self._safe_close_tp(tp)

            elapsed = time.perf_counter() - t0
            dims_completed = list(analysis_result.get("dimensions_completed", []))
            if not dims_completed:
                from .engine import dimension_registry
                dims_completed = dimension_registry.ALL_DIMENSION_IDS[:]

            detected = process_name or self._extract_process_from_track(
                parse_result.get("buffer_track_name", ""),
            )

            result = AnalysisResult(
                trace_path=trace_path,
                detected_process=detected,
                jank_times=jt,
                frame_num=fn,
                refresh_rate_hz=hz,
                app_type=analysis_result.get("app_type", "app"),
                elapsed_seconds=round(elapsed, 2),
                report_path=str(report_path),
                report_dir=str(report_dir),
                dimensions_completed=dims_completed,
                parse_result=parse_result,
                analysis_data=analysis_result,
            )

            task.status = "completed"
            task.report_dir = str(report_dir)
            task.process_name = detected or process_name
            self._update_task_status(task, "completed")
            self._notify(
                on_progress,
                f"分析完成 ({elapsed:.1f}s), 报告: {report_path}",
            )
            return result

        except Exception as e:
            task.error_message = str(e)
            self._update_task_status(task, "failed", str(e))
            self._notify(on_progress, f"分析失败: {e}")
            raise

    def parse_only(
        self,
        trace_path: str | Path,
        process_name: str = "",
        on_progress: ProgressCallback = None,
    ) -> AnalysisResult:
        """仅执行 Phase 1 丢帧解析，不做 Phase 2 分析。"""
        trace_path = str(Path(trace_path).resolve())
        process_name = process_name or self._cfg.default_process
        task = self._create_task(trace_path, process_name, "parse")

        t0 = time.perf_counter()
        try:
            self._notify(on_progress, "Phase 1: 丢帧解析中...")
            self._update_task_status(task, "running")

            from .engine import parser

            db_path = self._get_db_path()
            parse_result = parser.run_parser_and_save(
                trace_path,
                db_path,
                refresh_rate_preset=self._cfg.refresh_rate_preset,
                log_timing=True,
                process_filter=process_name or None,
            )

            elapsed = time.perf_counter() - t0
            jt = parse_result.get("jank_times", 0)
            fn = parse_result.get("frame_num", 0)
            hz = parse_result.get("inferred_refresh_rate_hz", 60)

            detected = process_name or self._extract_process_from_track(
                parse_result.get("buffer_track_name", ""),
            )

            result = AnalysisResult(
                trace_path=trace_path,
                detected_process=detected,
                jank_times=jt,
                frame_num=fn,
                refresh_rate_hz=hz,
                elapsed_seconds=round(elapsed, 2),
                parse_result=parse_result,
            )

            task.process_name = detected or process_name
            from .engine import report_writer
            rd = report_writer.ensure_report_dir(trace_path, self._get_output_dir())
            task.report_dir = str(rd)
            self._update_task_status(task, "completed")
            self._notify(
                on_progress,
                f"解析完成 ({elapsed:.1f}s): {jt} 次丢帧, {fn} 帧",
            )
            return result

        except Exception as e:
            self._update_task_status(task, "failed", str(e))
            self._notify(on_progress, f"解析失败: {e}")
            raise

    def analyze_dimensions(
        self,
        trace_path: str | Path,
        process_name: str = "",
        dimensions: list[str] | None = None,
        on_progress: ProgressCallback = None,
    ) -> AnalysisResult:
        """按维度独立分析。"""
        trace_path = str(Path(trace_path).resolve())
        process_name = process_name or self._cfg.default_process

        if not dimensions:
            from .engine import dimension_registry
            return AnalysisResult(
                trace_path=trace_path,
                parse_result={"dimensions_list": dimension_registry.list_dimensions()},
            )

        from .engine import dimension_registry
        resolved = dimension_registry.resolve_dependencies(dimensions)
        auto_added = dimension_registry.get_auto_completed(dimensions, resolved)
        if auto_added:
            self._notify(
                on_progress,
                f"自动补全依赖维度: {', '.join(auto_added)}",
            )

        task = self._create_task(trace_path, process_name, "dimensions")
        task.dimensions = resolved

        t0 = time.perf_counter()
        try:
            self._notify(on_progress, "正在加载 trace...")
            self._update_task_status(task, "running")

            from .engine import parser, analyzer, report_writer

            parse_result, tp = parser.parse_trace_with_tp(
                trace_path,
                self._cfg.refresh_rate_preset,
                process_filter=process_name or None,
            )

            db_path = self._get_db_path()
            self._save_phase1_to_db(parse_result, trace_path, db_path)

            for dim in resolved:
                self._notify(on_progress, f"分析维度: {dim}...")

            analysis_result = analyzer.analyze_dimensions(
                tp,
                parse_result,
                process_name=process_name or None,
                dimensions=resolved,
                app_type_override=self._cfg.app_type,
                analyze_top=self._cfg.analyze_top,
                slow_binder_ms=self._cfg.slow_binder_threshold_ms,
                sched_latency_ms=self._cfg.sched_latency_threshold_ms,
            )

            # 写入维度报告
            report_dir = report_writer.ensure_report_dir(
                trace_path, self._get_output_dir(),
            )
            for dim in resolved:
                dim_data = analysis_result.get(dim, {})
                if dim_data:
                    report_writer.write_analysis_file(
                        report_dir, dim, dim_data, fmt="md",
                        trace_path=trace_path,
                        process_name=process_name,
                    )
                    report_writer.write_analysis_file(
                        report_dir, dim, dim_data, fmt="json",
                        trace_path=trace_path,
                        process_name=process_name,
                    )

            self._safe_close_tp(tp)

            elapsed = time.perf_counter() - t0
            detected = process_name or self._extract_process_from_track(
                parse_result.get("buffer_track_name", ""),
            )

            result = AnalysisResult(
                trace_path=trace_path,
                detected_process=detected,
                jank_times=parse_result.get("jank_times", 0),
                frame_num=parse_result.get("frame_num", 0),
                refresh_rate_hz=parse_result.get("inferred_refresh_rate_hz", 60),
                elapsed_seconds=round(elapsed, 2),
                report_dir=str(report_dir),
                dimensions_completed=resolved,
                parse_result=parse_result,
                analysis_data=analysis_result,
            )

            task.process_name = detected or process_name
            task.report_dir = str(report_dir)
            self._update_task_status(task, "completed")
            self._notify(
                on_progress,
                f"维度分析完成 ({elapsed:.1f}s): {', '.join(resolved)}",
            )
            return result

        except Exception as e:
            self._update_task_status(task, "failed", str(e))
            self._notify(on_progress, f"维度分析失败: {e}")
            raise

    def list_dimensions(self) -> str:
        """返回可用分析维度列表（格式化字符串）。"""
        from .engine import dimension_registry
        return dimension_registry.list_dimensions()

    def get_analysis_history(self) -> list[dict[str, Any]]:
        """查询分析历史记录。

        合并 DB 记录和磁盘上已存在的报告目录（未入库的旧报告也会显示）。
        """
        db_records: list[dict[str, Any]] = []
        shared_db_ok = False
        if self._db_manager:
            try:
                conn = self._db_manager.connection
                cursor = conn.execute(
                    "SELECT * FROM pa_analysis_tasks ORDER BY created_at DESC",
                )
                columns = [desc[0] for desc in cursor.description]
                db_records = [dict(zip(columns, row)) for row in cursor.fetchall()]
                shared_db_ok = True
            except Exception:
                pass

        if not shared_db_ok:
            db_records = self._get_history_from_module_db()

        tracked_dirs: set[str] = set()
        for r in db_records:
            rd = r.get("report_dir_path", "")
            if rd:
                tracked_dirs.add(str(Path(rd).resolve()))

        output_dir = Path(self._get_output_dir())
        if output_dir.exists():
            for child in sorted(output_dir.iterdir(), reverse=True):
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

        优先按 task_id 精确删除；若 task_id 为空则按 report_dir_path 删除。
        当该 trace_path 下已无任何记录时，清理模块 DB 中的基础数据。

        Returns:
            True 表示可以安全删除磁盘目录（无其他记录引用该目录）。
        """
        db_path = self._get_shared_db_path()
        if not db_path:
            return True
        try:
            import sqlite3
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
                dir_refs = cursor.fetchone()[0]
                can_delete_dir = (dir_refs == 0)

            remaining = 0
            if trace_path:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM pa_analysis_tasks WHERE trace_path = ?",
                    (trace_path,),
                )
                remaining = cursor.fetchone()[0]

            conn.commit()
            conn.close()

            if trace_path and remaining == 0:
                self._cleanup_module_db(trace_path)

            return can_delete_dir
        except Exception:
            return True

    def _cleanup_module_db(self, trace_path: str) -> None:
        """当共享 DB 中某 trace 的所有记录被删除后，清理模块 DB 数据。"""
        try:
            from .engine import storage
            db_path = self._get_db_path()
            conn = storage.get_connection(db_path)
            cursor = conn.execute(
                "SELECT trace_id FROM trace_run WHERE trace_path = ?",
                (trace_path,),
            )
            row = cursor.fetchone()
            if row:
                tid = row[0] if isinstance(row, tuple) else row["trace_id"]
                for table in ("jank_record", "buffer_event", "vsync_cycle",
                              "trace_summary", "cpu_topology", "analysis_report"):
                    try:
                        conn.execute(
                            f"DELETE FROM {table} WHERE trace_run_id = ?",
                            (tid,),
                        )
                    except Exception:
                        pass
                conn.execute(
                    "DELETE FROM trace_run WHERE trace_id = ?", (tid,),
                )
                conn.commit()
            conn.close()
        except Exception:
            pass

    def export_report(
        self,
        trace_path: str | Path | None = None,
        output_dir: str | None = None,
        on_progress: ProgressCallback = None,
    ) -> bool:
        """导出已有分析结果为 Markdown 报告。"""
        from .engine import export
        db_path = self._get_db_path()
        out = output_dir or self._get_output_dir()
        self._notify(on_progress, "导出 Markdown 报告中...")
        result = export.export_to_markdown(db_path, out)
        self._notify(on_progress, "导出完成" if result else "导出失败")
        return result

    def regenerate_report(
        self,
        trace_path: str,
        on_progress: ProgressCallback = None,
    ) -> str:
        """基于数据库已有数据重新生成报告（不重新分析 trace）。

        Returns:
            报告文件路径，失败返回空字符串。
        """
        from .engine import export, report_writer, storage

        db_path = self._get_db_path()
        self._notify(on_progress, "从数据库读取分析数据...")

        try:
            conn = storage.get_connection(db_path)
            runs = storage.list_trace_runs(conn)
            target_run = None
            for run in runs:
                if run.get("trace_path", "") == trace_path:
                    target_run = run
                    break

            if not target_run:
                self._notify(on_progress, "数据库中未找到该 trace 的分析数据")
                conn.close()
                return ""

            tid = target_run["trace_id"]
            offset_ns = target_run.get("realtime_offset_ns") or 0
            summary = storage.get_trace_summary(conn, tid)
            jank_records = storage.get_jank_records(conn, tid)
            conn.close()

            self._notify(on_progress, "重新生成报告文件...")
            report_dir = report_writer.ensure_report_dir(
                trace_path, self._get_output_dir(),
            )
            lines = export._build_trace_report(
                target_run, summary, jank_records, offset_ns,
            )
            report_path = report_dir / "jank_report.md"
            report_path.write_text("\n".join(lines), encoding="utf-8")

            self._notify(on_progress, f"报告已重新生成: {report_path}")
            return str(report_path)
        except Exception as e:
            self._notify(on_progress, f"重新生成报告失败: {e}")
            return ""

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _get_db_path(self) -> str:
        return str(self._data_dir / self._cfg.db_path)

    def _get_output_dir(self) -> str:
        """开发环境: data/output/trace_report/
        打包模式: <exe_dir>/output/trace_report/
        """
        import sys
        if getattr(sys, "frozen", False):
            return str(Path(sys.executable).parent / "output" / "trace_report")
        if self._root_dir:
            return str(self._root_dir / "data" / "output" / "trace_report")
        return str(self._data_dir / "output" / "trace_report")

    @staticmethod
    def _safe_close_tp(tp: Any) -> None:
        """安全关闭 TraceProcessor，忽略 --noconsole 模式下的无效句柄错误。"""
        try:
            if hasattr(tp, "subprocess") and tp.subprocess:
                tp.subprocess.kill()
                tp.subprocess.wait(timeout=5)
                tp.subprocess = None
            if hasattr(tp, "http"):
                tp.http.conn.close()
        except OSError:
            pass
        except Exception:
            pass

    def _notify(self, callback: ProgressCallback, message: str) -> None:
        if callback:
            try:
                callback(message)
            except Exception:
                pass

    def _check_perfetto_available(self) -> None:
        """检查 perfetto 包是否可用。"""
        try:
            import perfetto  # noqa: F401
            self._perfetto_available = True
        except ImportError:
            self._perfetto_available = False

    @property
    def perfetto_available(self) -> bool:
        return self._perfetto_available

    def _create_task(
        self, trace_path: str, process_name: str, mode: str,
    ) -> AnalysisTask:
        return AnalysisTask(
            task_id=str(uuid.uuid4()),
            trace_path=trace_path,
            process_name=process_name,
            mode=mode,
            status="pending",
            analysis_db_path=self._get_db_path(),
        )

    def _update_task_status(
        self,
        task: AnalysisTask,
        status: str,
        error_message: str = "",
    ) -> None:
        task.status = status
        task.error_message = error_message
        if self._db_manager:
            try:
                self._write_task_to_shared_db(task)
            except Exception:
                pass

    def _get_shared_db_path(self) -> Path | None:
        """获取共享数据库文件路径。"""
        if not self._db_manager:
            return None
        return getattr(self._db_manager, "_db_path", None)

    def _write_task_to_shared_db(self, task: AnalysisTask) -> None:
        """将任务状态写入共享 DB 的 pa_analysis_tasks 表。

        使用独立连接以支持从工作线程安全写入。
        同一 trace_path 只保留最新一条记录。
        """
        db_path = self._get_shared_db_path()
        if not db_path:
            return
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            self._ensure_extra_columns(conn)
            now_ns = int(time.time() * 1e9)
            completed_at = now_ns if task.status in ("completed", "failed") else None
            dims_str = ",".join(task.dimensions) if task.dimensions else ""
            conn.execute(
                "DELETE FROM pa_analysis_tasks WHERE trace_path = ? AND mode = ?",
                (task.trace_path, task.mode),
            )
            conn.execute(
                """INSERT INTO pa_analysis_tasks
                   (task_id, trace_path, device_serial, analysis_db_path,
                    report_dir_path, process_name, mode, dimensions,
                    status, created_at, completed_at, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.task_id,
                    task.trace_path,
                    "",
                    task.analysis_db_path,
                    task.report_dir,
                    task.process_name,
                    task.mode,
                    dims_str,
                    task.status,
                    now_ns,
                    completed_at,
                    task.error_message,
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    @staticmethod
    def _ensure_extra_columns(conn) -> None:
        """确保 pa_analysis_tasks 表有所有扩展列（兼容旧数据库）。"""
        try:
            cursor = conn.execute("PRAGMA table_info(pa_analysis_tasks)")
            columns = {row[1] for row in cursor.fetchall()}
            extras = {
                "process_name": "TEXT DEFAULT ''",
                "mode": "TEXT DEFAULT 'full'",
                "dimensions": "TEXT DEFAULT ''",
            }
            for col, typedef in extras.items():
                if col not in columns:
                    conn.execute(
                        f"ALTER TABLE pa_analysis_tasks ADD COLUMN {col} {typedef}",
                    )
            conn.commit()
        except Exception:
            pass

    def _save_phase1_to_db(
        self, parse_result: dict[str, Any], trace_path: str, db_path: str,
    ) -> None:
        """将 Phase 1 解析结果保存到模块独立 DB。"""
        from .engine import storage
        import time as _time

        conn = storage.get_connection(db_path)
        path_norm = str(Path(trace_path).resolve())
        parsed_at_ns = int(_time.time() * 1e9)
        trace_id = storage.insert_trace_run(
            conn,
            path_norm,
            parsed_at_ns,
            trace_start_ns=parse_result.get("trace_start_ns"),
            trace_end_ns=parse_result.get("trace_end_ns"),
            realtime_offset_ns=parse_result.get("realtime_offset_ns", 0),
        )

        cycles = [
            (cy["pre_vt_ns"], cy["vt_ns"], cy["stand_vsync_ms"])
            for cy in parse_result.get("vsync_cycles", [])
        ]
        if cycles:
            storage.insert_vsync_cycles_batch(conn, trace_id, cycles)
        if parse_result.get("jank_records"):
            storage.insert_jank_records_batch(
                conn, trace_id, parse_result["jank_records"],
            )
        storage.insert_trace_summary(
            conn,
            trace_id,
            parse_result.get("jank_times", 0),
            parse_result.get("frame_num", 0),
            inferred_refresh_rate_hz=parse_result.get("inferred_refresh_rate_hz"),
            refresh_rate_switches=parse_result.get("refresh_rate_switches"),
            max_buffer_count=parse_result.get("max_buffer_count", 0),
        )
        conn.close()

    @staticmethod
    def _extract_process_from_track(buffer_track_name: str) -> str:
        """从 BufferTX 轨道名提取纯包名（不含 PID / SurfaceView）。

        常见格式：
          "BufferTX - com.tencent.letsgo/SurfaceView[...]#0"
          "BufferTX - SurfaceView - com.tencent.letsgo/...#0"
          "BufferTX - com.tencent.letsgo(12345)/SurfaceView[...]#0"
        提取结果: "com.tencent.letsgo"
        """
        import re

        if not buffer_track_name:
            return ""
        parts = buffer_track_name.split(" - ", 1)
        if len(parts) < 2:
            return ""
        raw = parts[1].strip()

        pkg_pattern = re.compile(r'([a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+){2,})')
        match = pkg_pattern.search(raw)
        if match:
            return match.group(1)

        slash_idx = raw.find("/")
        if slash_idx > 0:
            candidate = raw[:slash_idx]
            candidate = re.sub(r'\(\d+\)$', '', candidate).strip()
            if candidate and not candidate.startswith("SurfaceView"):
                return candidate

        return ""

    def _get_history_from_module_db(self) -> list[dict[str, Any]]:
        """从模块独立 DB 读取分析历史（降级方案）。"""
        from .engine import storage
        db_path = self._get_db_path()
        try:
            conn = storage.get_connection(db_path)
            runs = storage.list_trace_runs(conn)
            conn.close()
            return runs
        except Exception:
            return []

    # ------------------------------------------------------------------
    # 原子工具集 API（AnalysisToolkit 委托）
    # ------------------------------------------------------------------

    def _get_toolkit(self):
        """惰性创建 AnalysisToolkit 实例。"""
        if not hasattr(self, "_toolkit"):
            from .analysis_toolkit import AnalysisToolkit
            from .mcp_client import McpAnalysisClient
            from .analysis_mode import FeatureFlagManager

            self._toolkit = AnalysisToolkit(
                config=self._cfg,
                mcp_client=McpAnalysisClient(
                    timeout_ms=self._cfg.mcp_timeout_ms,
                ),
                flag_manager=FeatureFlagManager(self._cfg),
            )
        return self._toolkit

    def get_trace_overview(
        self,
        trace_path: str,
        process: str | None = None,
    ) -> TraceOverview:
        """获取 trace 元数据概览。"""
        return self._get_toolkit().get_trace_overview(trace_path, process)

    def detect_jank_frames(
        self,
        trace_path: str,
        process: str = "",
        time_range: dict | None = None,
    ) -> list[dict[str, Any]]:
        """检测卡顿帧，可选 time_range 过滤。"""
        process = process or self._cfg.default_process
        return self._get_toolkit().detect_jank_frames(
            trace_path, process, time_range,
        )

    def analyze_dimension(
        self,
        trace_path: str,
        process: str = "",
        dimension: str = "cpu",
        time_range: dict | None = None,
    ) -> DimensionResult:
        """对指定维度执行分析（MCP/引擎路由）。"""
        process = process or self._cfg.default_process
        return self._get_toolkit().analyze_dimension(
            trace_path, process, dimension, time_range,
        )

    def get_cpu_overview(
        self,
        trace_path: str,
        process: str = "",
    ) -> dict[str, Any] | None:
        """获取全 trace CPU 概览（MCP）。"""
        process = process or self._cfg.default_process
        return self._get_toolkit().get_cpu_overview(trace_path, process)

    def find_slices_tool(
        self,
        trace_path: str,
        pattern: str,
        process: str | None = None,
        compact: bool = False,
    ) -> dict[str, Any] | None:
        """按名称模式搜索 slice（MCP）。"""
        return self._get_toolkit().find_slices(
            trace_path, pattern, process, compact,
        )

    def execute_sql_tool(
        self,
        trace_path: str,
        sql: str,
        compact: bool = False,
    ) -> dict[str, Any] | None:
        """执行任意 Perfetto SQL 查询（MCP）。"""
        return self._get_toolkit().execute_sql(trace_path, sql, compact)

    def thread_state_summary(
        self,
        trace_path: str,
        process: str = "",
        time_range: dict[str, float] | None = None,
        compact: bool = False,
    ) -> Any:
        """查询主线程各状态（Running/S/R/D/R+）的耗时和占比。"""
        process = process or self._cfg.default_process
        return self._get_toolkit().thread_state_summary(
            trace_path, process, time_range, compact,
        )

    def cpu_freq_analysis(
        self,
        trace_path: str,
        process: str = "",
        time_range: dict[str, float] | None = None,
        compact: bool = False,
    ) -> Any:
        """查询主线程运行的 CPU 核心分布和各核心频率统计。"""
        process = process or self._cfg.default_process
        return self._get_toolkit().cpu_freq_analysis(
            trace_path, process, time_range, compact,
        )

    def analyze_anr(
        self,
        trace_path: str,
        process: str = "",
    ) -> dict[str, Any]:
        """ANR 检测与根因分析。"""
        process = process or self._cfg.default_process
        return self._get_toolkit().analyze_anr(trace_path, process)

    def analyze_memory(
        self,
        trace_path: str,
        process: str = "",
    ) -> dict[str, Any]:
        """内存泄漏检测与堆分析。"""
        process = process or self._cfg.default_process
        return self._get_toolkit().analyze_memory(trace_path, process)

    def compress_results(
        self,
        trace_overview: TraceOverview,
        dimension_results: list[DimensionResult],
        jank_frames: list[dict[str, Any]] | None = None,
    ) -> CompressedSummary:
        """将分析结果压缩为 CompressedSummary。"""
        from .result_compressor import ResultCompressor

        compressor = ResultCompressor()
        return compressor.compress(trace_overview, dimension_results, jank_frames)

    def set_analysis_mode(
        self,
        mode: str,
        dimension_overrides: dict[str, str] | None = None,
    ) -> None:
        """设置分析模式并持久化到 config.json。"""
        from .models import AnalysisMode
        if mode not in [m.value for m in AnalysisMode]:
            raise ValueError(f"无效的分析模式: {mode}，可选: {[m.value for m in AnalysisMode]}")
        self._cfg.analysis_mode = mode
        if dimension_overrides is not None:
            self._cfg.dimension_overrides = dimension_overrides
        save_config(self._cfg)
        if hasattr(self, "_toolkit"):
            del self._toolkit

    def get_analysis_mode(self) -> dict[str, Any]:
        """获取当前分析模式和维度覆盖设置。"""
        return {
            "analysis_mode": self._cfg.analysis_mode,
            "dimension_overrides": self._cfg.dimension_overrides,
            "mcp_timeout_ms": self._cfg.mcp_timeout_ms,
        }
