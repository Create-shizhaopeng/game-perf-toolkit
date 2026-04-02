"""历史存储模块单元测试"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from modules.perfetto_capture.src.history_storage import HistoryStorage
from modules.perfetto_capture.src.models import HistorySession, HistoryTrace
from modules.perfetto_capture.src.utils import (
    TraceFilenameInfo,
    parse_session_dirname,
    parse_trace_filename,
)


class TestParseTraceFilename:
    """Trace 文件名解析测试。"""

    def test_standard_format(self):
        """标准格式解析。"""
        info = parse_trace_filename("SM8750P_TB321FU_20260402_201530.perfetto-trace")
        assert info.model == "SM8750P"
        assert info.soc == "TB321FU"
        assert info.timestamp == datetime(2026, 4, 2, 20, 15, 30)

    def test_format_with_sequence(self):
        """带序号格式解析。"""
        info = parse_trace_filename("Pixel7_Tensor_20260402_201530_001.perfetto-trace")
        assert info.model == "Pixel7"
        assert info.soc == "Tensor"
        assert info.timestamp == datetime(2026, 4, 2, 20, 15, 30)

    def test_hyphen_separated_timestamp(self):
        """连字符分隔的时间戳。"""
        info = parse_trace_filename("Model_SoC_2026-04-02-20-15-30.perfetto-trace")
        assert info.model == "Model"
        assert info.soc == "SoC"
        assert info.timestamp == datetime(2026, 4, 2, 20, 15, 30)

    def test_invalid_format_returns_empty(self):
        """无效格式返回空字段。"""
        info = parse_trace_filename("random_file.perfetto-trace")
        assert info.model is None
        assert info.soc is None
        assert info.timestamp is None

    def test_non_trace_extension(self):
        """非 trace 扩展名返回空。"""
        info = parse_trace_filename("SM8750P_TB321FU_20260402_201530.txt")
        assert info.model is None


class TestParseSessionDirname:
    """会话目录名解析测试。"""

    def test_new_format(self):
        """新格式：yyyy_MM_dd-HH_mm_ss"""
        dt = parse_session_dirname("2026_04_02-20_15_30")
        assert dt == datetime(2026, 4, 2, 20, 15, 30)

    def test_new_format_with_suffix(self):
        """新格式带后缀：yyyy_MM_dd-HH_mm_ss_1"""
        dt = parse_session_dirname("2026_04_02-20_15_30_1")
        assert dt == datetime(2026, 4, 2, 20, 15, 30)

    def test_compact_format(self):
        """紧凑格式：yyyyMMdd_HHmmss"""
        dt = parse_session_dirname("20260402_201530")
        assert dt == datetime(2026, 4, 2, 20, 15, 30)

    def test_invalid_format(self):
        """无效格式返回 None。"""
        dt = parse_session_dirname("random_dirname")
        assert dt is None

    def test_invalid_date_values(self):
        """无效日期值返回 None。"""
        dt = parse_session_dirname("2026_13_40-25_70_80")  # 无效月日时分秒
        assert dt is None


class TestHistoryStorage:
    """历史存储 CRUD 测试。"""

    @pytest.fixture
    def storage(self, tmp_path):
        """创建临时数据库存储。"""
        db_path = tmp_path / "test_history.db"
        return HistoryStorage(db_path)

    @pytest.fixture
    def sample_session(self, tmp_path):
        """创建示例会话。"""
        session_dir = tmp_path / "2026_04_02-20_15_30"
        session_dir.mkdir(parents=True)
        return HistorySession(
            id="2026_04_02-20_15_30",
            dir_path=session_dir,
            created_at=datetime(2026, 4, 2, 20, 15, 30),
            device_model="SM8750P",
            device_soc="TB321FU",
            trace_count=2,
            total_size_bytes=100_000_000,
        )

    @pytest.fixture
    def sample_trace(self, tmp_path):
        """创建示例 trace。"""
        trace_path = tmp_path / "test.perfetto-trace"
        trace_path.write_bytes(b"fake trace data")
        return HistoryTrace(
            session_id="2026_04_02-20_15_30",
            file_path=trace_path,
            file_name="test.perfetto-trace",
            file_size_bytes=15,
            device_model="SM8750P",
            device_soc="TB321FU",
            captured_at=datetime(2026, 4, 2, 20, 15, 30),
        )

    def test_insert_and_get_session(self, storage, sample_session):
        """插入并获取会话。"""
        storage.insert_session(sample_session)
        sessions = storage.get_all_sessions()

        assert len(sessions) == 1
        assert sessions[0].id == sample_session.id
        assert sessions[0].device_model == "SM8750P"

    def test_insert_and_get_trace(self, storage, sample_session, sample_trace):
        """插入并获取 trace。"""
        storage.insert_session(sample_session)
        trace_id = storage.insert_trace(sample_trace)

        traces = storage.get_traces_by_session(sample_session.id)
        assert len(traces) == 1
        assert traces[0].file_name == "test.perfetto-trace"
        assert traces[0].id == trace_id

    def test_delete_session_cascades(self, storage, sample_session, sample_trace):
        """删除会话级联删除 traces。"""
        storage.insert_session(sample_session)
        storage.insert_trace(sample_trace)

        storage.delete_session(sample_session.id)

        sessions = storage.get_all_sessions()
        traces = storage.get_traces_by_session(sample_session.id)
        assert len(sessions) == 0
        assert len(traces) == 0

    def test_get_stats(self, storage, sample_session, sample_trace):
        """获取统计信息。"""
        storage.insert_session(sample_session)
        storage.insert_trace(sample_trace)

        stats = storage.get_stats()
        assert stats.total_sessions == 1
        assert stats.total_traces == 1
        assert stats.total_size_bytes == 15

    def test_get_session_ids(self, storage, sample_session):
        """获取会话 ID 集合。"""
        storage.insert_session(sample_session)
        ids = storage.get_session_ids()

        assert sample_session.id in ids

    def test_upsert_session(self, storage, sample_session):
        """更新已存在的会话。"""
        storage.insert_session(sample_session)

        # 修改并重新插入
        sample_session.trace_count = 5
        storage.insert_session(sample_session)

        sessions = storage.get_all_sessions()
        assert len(sessions) == 1
        assert sessions[0].trace_count == 5

    def test_clear_all(self, storage, sample_session, sample_trace):
        """清空所有历史。"""
        storage.insert_session(sample_session)
        storage.insert_trace(sample_trace)

        count = storage.clear_all()
        assert count == 1

        sessions = storage.get_all_sessions()
        assert len(sessions) == 0
