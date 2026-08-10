"""Perfetto 抓取模块 — 历史记录服务层

提供历史会话扫描、索引更新、删除、自动清理等业务逻辑。
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

from .history_storage import HistoryStorage
from .models import HistoryConfig, HistorySession, HistoryStats, HistoryTrace
from .utils import parse_session_dirname, parse_trace_filename

logger = logging.getLogger(__name__)

TRACE_EXTENSION = ".perfetto-trace"

# 扫描时对"可能正在抓取、尚未导出 trace"的空会话目录的宽限时间（秒）。
# 抓取会话目录在首次 save 时创建，但 trace 文件要等导出阶段才 pull 进来，
# 期间的目录是空的；若扫描立即清理会被误删，导致后续导出 pull 目标目录不存在。
_EMPTY_DIR_GRACE_SECONDS = 600


class HistoryService:
    """历史记录服务。"""

    def __init__(self, storage: HistoryStorage, output_dir: Path, config: HistoryConfig) -> None:
        self.storage = storage
        self.output_dir = output_dir
        self.trace_dir = output_dir / "trace"
        self.config = config

    def scan_sessions(self) -> list[HistorySession]:
        """
        扫描目录并更新索引，返回所有会话列表。

        执行流程：
        1. 扫描 trace_dir 获取当前会话目录列表
        2. 与 SQLite 索引对比，增量更新
        3. 清理空目录
        4. 返回最新会话列表
        """
        if not self.trace_dir.exists():
            logger.debug("Trace 目录不存在: %s", self.trace_dir)
            return []

        # 1. 获取当前目录中的会话
        current_sessions = self._scan_directory()

        # 2. 同步索引
        self._sync_index(current_sessions)

        # 3. 返回最新数据（从数据库读取，带 traces）
        sessions = self.storage.get_all_sessions()
        for session in sessions:
            session.traces = self.storage.get_traces_by_session(session.id)

        return sessions

    def _scan_directory(self) -> dict[str, HistorySession]:
        """扫描目录，返回会话 ID 到 HistorySession 的映射。"""
        sessions: dict[str, HistorySession] = {}

        for item in self.trace_dir.iterdir():
            if not item.is_dir():
                continue

            session = self._parse_session_dir(item)
            if session:
                sessions[session.id] = session

        return sessions

    def _parse_session_dir(self, dir_path: Path) -> HistorySession | None:
        """解析单个会话目录。"""
        dirname = dir_path.name
        created_at = parse_session_dirname(dirname)

        if created_at is None:
            # 无法解析时间，使用目录修改时间
            try:
                mtime = dir_path.stat().st_mtime
                created_at = datetime.fromtimestamp(mtime)
            except OSError:
                logger.warning("无法获取目录时间: %s", dir_path)
                return None

        # 扫描 trace 文件
        traces: list[HistoryTrace] = []
        total_size = 0
        device_model = None
        device_soc = None

        for trace_file in dir_path.glob(f"*{TRACE_EXTENSION}"):
            if not trace_file.is_file():
                continue

            try:
                file_size = trace_file.stat().st_size
            except OSError:
                continue

            # 解析文件名
            info = parse_trace_filename(trace_file.name)

            trace = HistoryTrace(
                session_id=dirname,
                file_path=trace_file,
                file_name=trace_file.name,
                file_size_bytes=file_size,
                device_model=info.model,
                device_soc=info.soc,
                captured_at=info.timestamp,
            )
            traces.append(trace)
            total_size += file_size

            # 从第一个有效的 trace 获取设备信息
            if device_model is None and info.model:
                device_model = info.model
            if device_soc is None and info.soc:
                device_soc = info.soc

        # 空目录处理：自动清理（带宽限期，避免误删正在抓取的会话目录）
        if not traces:
            self._cleanup_empty_dir(dir_path, _EMPTY_DIR_GRACE_SECONDS)
            return None

        return HistorySession(
            id=dirname,
            dir_path=dir_path,
            created_at=created_at,
            device_model=device_model,
            device_soc=device_soc,
            trace_count=len(traces),
            total_size_bytes=total_size,
            traces=traces,
        )

    def _sync_index(self, current_sessions: dict[str, HistorySession]) -> None:
        """同步索引：添加新会话、删除无效会话。"""
        indexed_ids = self.storage.get_session_ids()
        current_ids = set(current_sessions.keys())

        # 新增会话
        new_ids = current_ids - indexed_ids
        for session_id in new_ids:
            session = current_sessions[session_id]
            self.storage.insert_session(session)
            for trace in session.traces:
                self.storage.insert_trace(trace)
            logger.debug("索引新增会话: %s (%d traces)", session_id, len(session.traces))

        # 删除无效会话
        stale_ids = indexed_ids - current_ids
        for session_id in stale_ids:
            self.storage.delete_session(session_id)
            logger.debug("索引删除无效会话: %s", session_id)

        # 更新已存在会话的 trace 列表
        for session_id in current_ids & indexed_ids:
            session = current_sessions[session_id]
            self.storage.insert_session(session)  # 更新会话统计
            # 重新插入所有 traces（使用 ON CONFLICT 更新）
            for trace in session.traces:
                self.storage.insert_trace(trace)

    def _cleanup_empty_dir(self, dir_path: Path, grace_seconds: int = 0) -> None:
        """清理空的会话目录。

        grace_seconds > 0 时，仅清理修改时间距今超过宽限期的目录，
        避免误删刚创建、尚未导出 trace 的抓取会话目录。
        """
        if grace_seconds > 0:
            try:
                mtime = dir_path.stat().st_mtime
            except OSError:
                return
            if time.time() - mtime < grace_seconds:
                return
        try:
            # 只删除空目录或只包含非 trace 文件的目录
            contents = list(dir_path.iterdir())
            trace_files = [f for f in contents if f.suffix == TRACE_EXTENSION]
            if not trace_files:
                shutil.rmtree(dir_path)
                logger.info("已清理空会话目录: %s", dir_path)
        except OSError as e:
            logger.warning("清理空目录失败: %s - %s", dir_path, e)

    def validate_index(self) -> int:
        """校验索引一致性，清理无效条目，返回清理数量。"""
        indexed_paths = self.storage.get_session_dir_paths()
        removed_count = 0

        for session_id, dir_path in indexed_paths.items():
            if not dir_path.exists():
                self.storage.delete_session(session_id)
                removed_count += 1
                logger.debug("清理无效索引: %s", session_id)

        return removed_count

    def delete_session(self, session_id: str) -> bool:
        """删除会话：删除目录 + 更新索引。"""
        # 先从索引获取目录路径
        paths = self.storage.get_session_dir_paths()
        dir_path = paths.get(session_id)

        if dir_path and dir_path.exists():
            try:
                shutil.rmtree(dir_path)
                logger.info("已删除会话目录: %s", dir_path)
            except OSError as e:
                logger.error("删除会话目录失败: %s - %s", dir_path, e)
                return False

        # 更新索引
        return self.storage.delete_session(session_id)

    def delete_trace(self, trace_path: Path) -> bool:
        """删除单个 trace 文件 + 更新索引。"""
        if trace_path.exists():
            try:
                trace_path.unlink()
                logger.info("已删除 trace 文件: %s", trace_path)
            except OSError as e:
                logger.error("删除 trace 文件失败: %s - %s", trace_path, e)
                return False

        # 更新索引
        self.storage.delete_trace_by_path(trace_path)

        # 检查会话目录是否为空，如是则删除会话
        session_dir = trace_path.parent
        if session_dir.exists():
            remaining_traces = list(session_dir.glob(f"*{TRACE_EXTENSION}"))
            if not remaining_traces:
                self._cleanup_empty_dir(session_dir)
                # 删除会话索引
                self.storage.delete_session(session_dir.name)

        return True

    def cleanup_expired(self) -> int:
        """
        根据配置清理过期会话。

        清理策略：
        1. 按天数清理：删除超过 max_history_days 的会话
        2. 按数量清理：保留最新的 max_history_count 个会话

        返回清理的会话数。
        """
        sessions = self.storage.get_all_sessions()
        if not sessions:
            return 0

        to_delete: set[str] = set()

        # 1. 按天数清理
        if self.config.max_history_days > 0:
            cutoff_date = datetime.now() - timedelta(days=self.config.max_history_days)
            for session in sessions:
                if session.created_at < cutoff_date:
                    to_delete.add(session.id)
                    logger.debug("标记过期会话（超过 %d 天）: %s", self.config.max_history_days, session.id)

        # 2. 按数量清理（保留最新的 N 个）
        if self.config.max_history_count > 0:
            # 按时间倒序排序，保留前 N 个
            sorted_sessions = sorted(sessions, key=lambda s: s.created_at, reverse=True)
            if len(sorted_sessions) > self.config.max_history_count:
                excess_sessions = sorted_sessions[self.config.max_history_count:]
                for session in excess_sessions:
                    to_delete.add(session.id)
                    logger.debug("标记超量会话: %s", session.id)

        # 执行删除
        deleted_count = 0
        for session_id in to_delete:
            if self.delete_session(session_id):
                deleted_count += 1

        if deleted_count > 0:
            logger.info("已清理 %d 个过期会话", deleted_count)

        return deleted_count

    def get_stats(self) -> HistoryStats:
        """获取历史记录统计信息。"""
        return self.storage.get_stats()

    def open_session_directory(self, session_id: str) -> Path | None:
        """获取会话目录路径（用于打开文件管理器）。"""
        paths = self.storage.get_session_dir_paths()
        dir_path = paths.get(session_id)
        if dir_path and dir_path.exists():
            return dir_path
        return None

    def get_session_size_formatted(self, size_bytes: int) -> str:
        """格式化文件大小显示。"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
