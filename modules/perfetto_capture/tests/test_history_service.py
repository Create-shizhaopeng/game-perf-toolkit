"""历史服务模块单元测试"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from modules.perfetto_capture.src.history_service import HistoryService
from modules.perfetto_capture.src.history_storage import HistoryStorage
from modules.perfetto_capture.src.models import HistoryConfig


class TestHistoryService:
    """历史服务测试。"""

    @pytest.fixture
    def setup_dirs(self, tmp_path):
        """设置测试目录结构。"""
        output_dir = tmp_path / "output"
        trace_dir = output_dir / "trace"
        trace_dir.mkdir(parents=True)
        return output_dir, trace_dir

    @pytest.fixture
    def storage(self, tmp_path):
        """创建临时存储。"""
        db_path = tmp_path / "test_history.db"
        return HistoryStorage(db_path)

    @pytest.fixture
    def config(self):
        """默认配置。"""
        return HistoryConfig(
            max_history_days=30,
            max_history_count=50,
            auto_cleanup_on_start=True,
        )

    @pytest.fixture
    def service(self, storage, setup_dirs, config):
        """创建服务实例。"""
        output_dir, _ = setup_dirs
        return HistoryService(storage, output_dir, config)

    def _create_session_dir(self, trace_dir: Path, dirname: str, trace_count: int = 1):
        """创建模拟的会话目录和 trace 文件。"""
        session_dir = trace_dir / dirname
        session_dir.mkdir(parents=True, exist_ok=True)

        for i in range(trace_count):
            trace_file = session_dir / f"Model_SoC_{dirname.replace('-', '_').replace('_', '')}_{i:03d}.perfetto-trace"
            trace_file.write_bytes(b"x" * 1000)  # 1KB fake data

        return session_dir

    def test_scan_empty_directory(self, service):
        """扫描空目录。"""
        sessions = service.scan_sessions()
        assert len(sessions) == 0

    def test_scan_single_session(self, service, setup_dirs):
        """扫描单个会话。"""
        _, trace_dir = setup_dirs
        self._create_session_dir(trace_dir, "2026_04_02-20_15_30", trace_count=2)

        sessions = service.scan_sessions()
        assert len(sessions) == 1
        assert sessions[0].id == "2026_04_02-20_15_30"
        assert sessions[0].trace_count == 2

    def test_scan_multiple_sessions(self, service, setup_dirs):
        """扫描多个会话。"""
        _, trace_dir = setup_dirs
        self._create_session_dir(trace_dir, "2026_04_02-20_15_30", trace_count=1)
        self._create_session_dir(trace_dir, "2026_04_03-10_00_00", trace_count=3)

        sessions = service.scan_sessions()
        assert len(sessions) == 2

    def test_incremental_sync_new_session(self, service, setup_dirs, storage):
        """增量同步：检测新会话。"""
        _, trace_dir = setup_dirs

        # 首次扫描
        self._create_session_dir(trace_dir, "2026_04_02-20_15_30")
        service.scan_sessions()
        assert len(storage.get_session_ids()) == 1

        # 添加新会话后再次扫描
        self._create_session_dir(trace_dir, "2026_04_03-10_00_00")
        service.scan_sessions()
        assert len(storage.get_session_ids()) == 2

    def test_incremental_sync_removed_session(self, service, setup_dirs, storage):
        """增量同步：检测已删除会话。"""
        _, trace_dir = setup_dirs

        # 创建两个会话
        session1 = self._create_session_dir(trace_dir, "2026_04_02-20_15_30")
        self._create_session_dir(trace_dir, "2026_04_03-10_00_00")
        service.scan_sessions()
        assert len(storage.get_session_ids()) == 2

        # 删除一个会话目录
        import shutil
        shutil.rmtree(session1)

        # 再次扫描
        service.scan_sessions()
        assert len(storage.get_session_ids()) == 1

    def test_cleanup_empty_directory(self, service, setup_dirs):
        """自动清理空目录。"""
        _, trace_dir = setup_dirs

        # 创建空会话目录
        empty_dir = trace_dir / "2026_04_02-20_15_30"
        empty_dir.mkdir(parents=True)

        # 扫描应该清理空目录
        sessions = service.scan_sessions()
        assert len(sessions) == 0
        assert not empty_dir.exists()

    def test_delete_session(self, service, setup_dirs, storage):
        """删除会话。"""
        _, trace_dir = setup_dirs
        session_dir = self._create_session_dir(trace_dir, "2026_04_02-20_15_30", trace_count=2)
        service.scan_sessions()

        # 删除会话
        result = service.delete_session("2026_04_02-20_15_30")
        assert result is True
        assert not session_dir.exists()
        assert len(storage.get_session_ids()) == 0

    def test_delete_trace(self, service, setup_dirs, storage):
        """删除单个 trace。"""
        _, trace_dir = setup_dirs
        session_dir = self._create_session_dir(trace_dir, "2026_04_02-20_15_30", trace_count=2)
        service.scan_sessions()

        # 获取第一个 trace 路径
        traces = list(session_dir.glob("*.perfetto-trace"))
        assert len(traces) == 2

        # 删除一个 trace
        result = service.delete_trace(traces[0])
        assert result is True
        assert not traces[0].exists()

        # 会话仍然存在（还有一个 trace）
        sessions = service.scan_sessions()
        assert len(sessions) == 1
        assert sessions[0].trace_count == 1

    def test_delete_last_trace_removes_session(self, service, setup_dirs, storage):
        """删除最后一个 trace 自动删除会话。"""
        _, trace_dir = setup_dirs
        session_dir = self._create_session_dir(trace_dir, "2026_04_02-20_15_30", trace_count=1)
        service.scan_sessions()

        # 删除唯一的 trace
        traces = list(session_dir.glob("*.perfetto-trace"))
        result = service.delete_trace(traces[0])
        assert result is True

        # 会话目录也应该被删除
        assert not session_dir.exists()

    def test_cleanup_expired_by_days(self, service, setup_dirs, storage):
        """按天数清理过期会话。"""
        _, trace_dir = setup_dirs

        # 创建一个 35 天前的会话（超过默认 30 天）
        old_date = datetime.now() - timedelta(days=35)
        old_dirname = old_date.strftime("%Y_%m_%d-%H_%M_%S")
        self._create_session_dir(trace_dir, old_dirname)

        # 创建一个今天的会话
        new_dirname = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
        self._create_session_dir(trace_dir, new_dirname)

        service.scan_sessions()
        assert len(storage.get_session_ids()) == 2

        # 清理过期
        deleted = service.cleanup_expired()
        assert deleted == 1
        assert len(storage.get_session_ids()) == 1

    def test_cleanup_expired_by_count(self, service, setup_dirs, storage, config):
        """按数量清理超量会话。"""
        _, trace_dir = setup_dirs

        # 设置最大保留 2 个
        config.max_history_count = 2

        # 创建 4 个会话
        for i in range(4):
            dt = datetime.now() - timedelta(hours=i)
            dirname = dt.strftime("%Y_%m_%d-%H_%M_%S")
            self._create_session_dir(trace_dir, dirname)

        service.scan_sessions()
        assert len(storage.get_session_ids()) == 4

        # 清理
        deleted = service.cleanup_expired()
        assert deleted == 2
        assert len(storage.get_session_ids()) == 2

    def test_get_stats(self, service, setup_dirs):
        """获取统计信息。"""
        _, trace_dir = setup_dirs
        self._create_session_dir(trace_dir, "2026_04_02-20_15_30", trace_count=3)

        service.scan_sessions()
        stats = service.get_stats()

        assert stats.total_sessions == 1
        assert stats.total_traces == 3
        assert stats.total_size_bytes == 3000  # 3 x 1KB
