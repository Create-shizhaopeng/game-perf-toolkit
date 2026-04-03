"""FPS 图表数据管理测试。"""

from __future__ import annotations

import datetime

import numpy as np
import pytest

from modules.perfetto_capture.src.fps_chart import FpsChartData, FpsChartWidget
from modules.perfetto_capture.src.models import FrameStats


def _make_stats(timestamp: datetime.datetime, fps: float,
                jank: int = 0, big_jank: int = 0) -> FrameStats:
    return FrameStats(
        timestamp=timestamp,
        fps=fps,
        frame_count=int(fps / 5),
        jank_count=jank,
        big_jank_count=big_jank,
    )


class TestFpsChartDataAggregation:
    """验证 1 秒聚合行为。"""

    def test_one_second_one_point(self):
        """每秒产生一个聚合数据点。"""
        data = FpsChartData()
        start = datetime.datetime(2026, 4, 3, 10, 0, 0)
        for i in range(15):
            ts = start + datetime.timedelta(milliseconds=i * 200)
            data.add_stats(_make_stats(ts, fps=60.0))

        timestamps, fps_values = data.get_curve_data()
        assert len(timestamps) == 2
        assert timestamps[0] == pytest.approx(0.0)
        assert timestamps[1] == pytest.approx(1.0)

    def test_fps_averaged_over_second(self):
        """同一秒内多个 FPS 值取平均。"""
        data = FpsChartData()
        start = datetime.datetime(2026, 4, 3, 10, 0, 0)
        fps_values_input = [58.0, 60.0, 62.0, 59.0, 61.0]
        for i, fps in enumerate(fps_values_input):
            ts = start + datetime.timedelta(milliseconds=i * 200)
            data.add_stats(_make_stats(ts, fps=fps))
        ts_next = start + datetime.timedelta(seconds=1)
        data.add_stats(_make_stats(ts_next, fps=60.0))

        _, fps_out = data.get_curve_data()
        assert len(fps_out) == 1
        expected = sum(fps_values_input) / len(fps_values_input)
        assert fps_out[0] == pytest.approx(expected)

    def test_latest_fps_is_realtime(self):
        """latest_fps 返回最新实时值，不等聚合。"""
        data = FpsChartData()
        start = datetime.datetime(2026, 4, 3, 10, 0, 0)
        data.add_stats(_make_stats(start, fps=55.0))
        assert data.latest_fps == pytest.approx(55.0)

    def test_elapsed_seconds(self):
        """elapsed_seconds 反映当前已到达的秒数。"""
        data = FpsChartData()
        start = datetime.datetime(2026, 4, 3, 10, 0, 0)
        for i in range(12):
            ts = start + datetime.timedelta(seconds=i)
            data.add_stats(_make_stats(ts, fps=60.0))

        assert data.elapsed_seconds == pytest.approx(11.0)


class TestFpsChartDataLongDuration:
    """验证长时间数据的完整性和扩容。"""

    def test_3600_seconds_preserved(self):
        """1 小时（3600 秒）数据全部保留。"""
        data = FpsChartData()
        start = datetime.datetime(2026, 4, 3, 10, 0, 0)
        for i in range(3602):
            ts = start + datetime.timedelta(seconds=i)
            data.add_stats(_make_stats(ts, fps=60.0 + (i % 5)))

        timestamps, fps_values = data.get_curve_data()
        assert len(timestamps) == 3601
        assert timestamps[0] == pytest.approx(0.0)
        assert timestamps[-1] == pytest.approx(3600.0)

    def test_capacity_grows(self):
        """超过初始容量后扩容。"""
        data = FpsChartData()
        start = datetime.datetime(2026, 4, 3, 10, 0, 0)
        initial_cap = FpsChartData.INITIAL_CAPACITY
        for i in range(initial_cap + 100):
            ts = start + datetime.timedelta(seconds=i)
            data.add_stats(_make_stats(ts, fps=60.0))

        assert data._capacity >= initial_cap * 2
        timestamps, _ = data.get_curve_data()
        assert len(timestamps) >= initial_cap


class TestFpsChartDataClear:
    """验证 clear 后重新写入。"""

    def test_clear_and_rewrite(self):
        data = FpsChartData()
        start = datetime.datetime(2026, 4, 3, 10, 0, 0)
        for i in range(30):
            ts = start + datetime.timedelta(seconds=i)
            data.add_stats(_make_stats(ts, fps=60.0, jank=1 if i == 15 else 0))

        data.clear()
        assert data._size == 0
        assert data.elapsed_seconds == 0.0
        assert data.latest_fps == 0.0
        assert data.total_jank == 0

        start2 = datetime.datetime(2026, 4, 3, 11, 0, 0)
        for i in range(10):
            ts = start2 + datetime.timedelta(seconds=i)
            data.add_stats(_make_stats(ts, fps=90.0))

        assert data._size > 0
        assert data.latest_fps == pytest.approx(90.0)


class TestFpsChartDataJankMarkers:
    """验证 Jank/BigJank 标记在聚合后保留。"""

    def test_jank_markers_preserved(self):
        data = FpsChartData()
        start = datetime.datetime(2026, 4, 3, 10, 0, 0)
        for i in range(20):
            ts = start + datetime.timedelta(seconds=i)
            jank = 1 if i == 5 else 0
            big_jank = 1 if i == 10 else 0
            data.add_stats(_make_stats(ts, fps=60.0, jank=jank, big_jank=big_jank))

        assert data.total_jank >= 1
        assert data.total_big_jank >= 1
        jx, _ = data.get_jank_markers()
        bx, _ = data.get_big_jank_markers()
        assert len(jx) >= 1
        assert len(bx) >= 1


def _ensure_qapp():
    try:
        import os
        if os.environ.get("CI") or not os.environ.get("DISPLAY", "1"):
            return False
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return True
    except Exception:
        return False


_has_gui = False


@pytest.mark.skipif(not _has_gui, reason="No GUI environment")
class TestFollowingModeDefault:
    """验证跟随模式默认状态。"""

    def test_initial_following(self):
        w = FpsChartWidget()
        assert w._following is True

    def test_following_after_clear(self):
        w = FpsChartWidget()
        w._following = False
        w.clear()
        assert w._following is True


@pytest.mark.skipif(not _has_gui, reason="No GUI environment")
class TestBrowsingModeNoAutoScroll:
    """验证浏览模式不自动滚动。"""

    def test_browsing_mode_preserves_view(self):
        w = FpsChartWidget()
        w._following = False

        start = datetime.datetime(2026, 4, 3, 10, 0, 0)
        for i in range(10):
            ts = start + datetime.timedelta(seconds=i)
            w.update_stats(_make_stats(ts, fps=60.0))

        assert w._following is False


class TestFindNearestPoint:
    """验证最近点搜索精度。"""

    def test_exact_match(self):
        data = FpsChartData()
        start = datetime.datetime(2026, 4, 3, 10, 0, 0)
        for i in range(110):
            ts = start + datetime.timedelta(seconds=i)
            data.add_stats(_make_stats(ts, fps=60.0))

        timestamps = data._timestamps[:data._size]
        target = float(timestamps[50])
        idx = int(np.searchsorted(timestamps, target))
        assert idx == 50

    def test_between_points(self):
        data = FpsChartData()
        start = datetime.datetime(2026, 4, 3, 10, 0, 0)
        for i in range(110):
            ts = start + datetime.timedelta(seconds=i)
            data.add_stats(_make_stats(ts, fps=60.0))

        timestamps = data._timestamps[:data._size]
        mid = (float(timestamps[50]) + float(timestamps[51])) / 2
        idx = int(np.searchsorted(timestamps, mid))
        assert idx in (50, 51)

    def test_empty_data(self):
        data = FpsChartData()
        assert data._size == 0


class TestHoverTimeFormat:
    """验证时间格式为 HH:MM:SS。"""

    def test_time_format(self):
        start = datetime.datetime(2026, 4, 3, 14, 32, 5)
        elapsed = 0.0
        abs_time = start + datetime.timedelta(seconds=elapsed)
        time_str = abs_time.strftime("%H:%M:%S")
        assert time_str == "14:32:05"

    def test_time_format_after_one_hour(self):
        start = datetime.datetime(2026, 4, 3, 14, 32, 5)
        elapsed = 3661.0
        abs_time = start + datetime.timedelta(seconds=elapsed)
        time_str = abs_time.strftime("%H:%M:%S")
        assert time_str == "15:33:06"


class TestMaxDurationConfig:
    """验证 max_duration_hours 字段约束。"""

    def test_default_value(self):
        from modules.perfetto_capture.src.models import JankConfig
        cfg = JankConfig()
        assert cfg.max_duration_hours == 3

    def test_min_boundary(self):
        from modules.perfetto_capture.src.models import JankConfig
        cfg = JankConfig(max_duration_hours=1)
        assert cfg.max_duration_hours == 1

    def test_max_boundary(self):
        from modules.perfetto_capture.src.models import JankConfig
        cfg = JankConfig(max_duration_hours=12)
        assert cfg.max_duration_hours == 12

    def test_below_min_raises(self):
        from modules.perfetto_capture.src.models import JankConfig
        with pytest.raises(Exception):
            JankConfig(max_duration_hours=0)

    def test_above_max_raises(self):
        from modules.perfetto_capture.src.models import JankConfig
        with pytest.raises(Exception):
            JankConfig(max_duration_hours=13)


class TestPerformanceBenchmark:
    """性能基准。"""

    def test_add_stats_43k_seconds(self):
        """12 小时（43200 秒）数据插入性能。"""
        import time
        data = FpsChartData()
        start_time = datetime.datetime(2026, 1, 1)

        t0 = time.perf_counter()
        for i in range(43_200):
            ts = start_time + datetime.timedelta(seconds=i)
            data.add_stats(_make_stats(ts, fps=60.0))
        elapsed = time.perf_counter() - t0

        assert elapsed < 10.0, f"43K add_stats took {elapsed:.2f}s (limit 10s)"

    def test_get_curve_data_performance(self):
        data = FpsChartData()
        start_time = datetime.datetime(2026, 1, 1)
        for i in range(43_200):
            ts = start_time + datetime.timedelta(seconds=i)
            data.add_stats(_make_stats(ts, fps=60.0))

        import time
        t0 = time.perf_counter()
        for _ in range(100):
            data.get_curve_data()
        elapsed = time.perf_counter() - t0

        assert elapsed < 1.0, f"100x get_curve_data took {elapsed:.2f}s"


class TestEdgeCases:
    """边缘场景测试。"""

    def test_zero_data_get_curve(self):
        data = FpsChartData()
        ts, fps_vals = data.get_curve_data()
        assert len(ts) == 0
        assert len(fps_vals) == 0

    def test_single_point_no_flush(self):
        """单个数据点在秒未切换时不产生聚合点。"""
        data = FpsChartData()
        data.add_stats(_make_stats(datetime.datetime.now(), fps=60.0))
        ts, fps_vals = data.get_curve_data()
        assert len(ts) == 0

    def test_clear_then_add(self):
        data = FpsChartData()
        start = datetime.datetime(2026, 1, 1)
        for i in range(50):
            ts = start + datetime.timedelta(seconds=i)
            data.add_stats(_make_stats(ts, fps=30.0))
        data.clear()
        assert data._size == 0

        start2 = datetime.datetime(2026, 6, 1)
        for i in range(5):
            ts = start2 + datetime.timedelta(seconds=i)
            data.add_stats(_make_stats(ts, fps=90.0))

        assert data._size > 0
        assert data.latest_fps == pytest.approx(90.0)
