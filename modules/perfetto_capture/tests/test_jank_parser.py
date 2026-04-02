"""帧数据解析器测试"""

import datetime

import pytest

from modules.perfetto_capture.src.jank_parser import (
    JANK_THRESHOLD_MS,
    BIG_JANK_THRESHOLD_MS,
    apply_dynamic_jank_detection,
    parse_framestats,
    parse_sf_latency,
    calculate_fps,
    calculate_frame_stats,
    detect_jank_event,
    get_default_jank_threshold,
)
from modules.perfetto_capture.src.models import FrameData


SAMPLE_FRAMESTATS_OUTPUT = """
Applications Graphics Acceleration Info:

Uptime: 12345678 Realtime: 12345678

** Graphics info for pid 1234 [com.example.app] **

Stats since: 1234567890ns
Total frames rendered: 100
Janky frames: 10 (10.00%)
50th percentile: 8ms
90th percentile: 16ms
95th percentile: 25ms
99th percentile: 40ms

---PROFILEDATA---
Flags,IntendedVsync,Vsync,OldestInputEvent,NewestInputEvent,HandleInputStart,AnimationStart,PerformTraversalsStart,DrawStart,SyncQueued,SyncStart,IssueDrawCommandsStart,SwapBuffers,FrameCompleted,DequeueBufferDuration,QueueBufferDuration,GpuCompleted
0,100000000,100000000,9223372036854775807,0,100100000,100200000,100300000,100400000,100500000,100600000,100700000,100800000,110000000,500,600,111000000
0,120000000,120000000,9223372036854775807,0,120100000,120200000,120300000,120400000,120500000,120600000,120700000,120800000,125000000,500,600,126000000
0,140000000,140000000,9223372036854775807,0,140100000,140200000,140300000,140400000,140500000,140600000,140700000,140800000,200000000,500,600,201000000
0,160000000,160000000,9223372036854775807,0,160100000,160200000,160300000,160400000,160500000,160600000,160700000,160800000,170000000,500,600,171000000
---PROFILEDATA---
"""


class TestParseFramestats:
    """测试帧数据解析。"""

    def test_parse_valid_output(self):
        """测试解析有效输出。"""
        frames = parse_framestats(SAMPLE_FRAMESTATS_OUTPUT)
        assert len(frames) == 4

    def test_frame_duration_calculation(self):
        """测试帧耗时计算。"""
        frames = parse_framestats(SAMPLE_FRAMESTATS_OUTPUT)

        assert frames[0].frame_duration_ms == pytest.approx(10.0, rel=0.1)
        assert frames[1].frame_duration_ms == pytest.approx(5.0, rel=0.1)
        assert frames[2].frame_duration_ms == pytest.approx(60.0, rel=0.1)
        assert frames[3].frame_duration_ms == pytest.approx(10.0, rel=0.1)

    def test_no_jank_flags_before_detection(self):
        """解析器不设置 jank 标记，由动态判定处理。"""
        frames = parse_framestats(SAMPLE_FRAMESTATS_OUTPUT)

        assert all(not f.is_jank for f in frames)
        assert all(not f.is_big_jank for f in frames)

    def test_parse_empty_output(self):
        """测试解析空输出。"""
        frames = parse_framestats("")
        assert len(frames) == 0

    def test_parse_no_profiledata(self):
        """测试无 PROFILEDATA 的输出。"""
        output = "Some other output without PROFILEDATA"
        frames = parse_framestats(output)
        assert len(frames) == 0

    def test_parse_invalid_lines(self):
        """测试跳过无效行。"""
        output = """---PROFILEDATA---
Flags,IntendedVsync,...
invalid line here
0,100000000,100000000,9223372036854775807,0,100100000,100200000,100300000,100400000,100500000,100600000,100700000,100800000,110000000,500,600,111000000
---PROFILEDATA---"""
        frames = parse_framestats(output)
        assert len(frames) == 1


class TestCalculateFps:
    """测试 FPS 计算。"""

    def test_empty_frames(self):
        """测试空帧列表。"""
        fps = calculate_fps([])
        assert fps == 0.0

    def test_single_frame(self):
        """测试单帧。"""
        frames = [FrameData(timestamp_ns=100_000_000, frame_duration_ms=10.0)]
        fps = calculate_fps(frames)
        assert fps == 1.0

    def test_multiple_frames(self):
        """测试多帧 FPS 计算。"""
        frames = [
            FrameData(timestamp_ns=0, frame_duration_ms=16.6),
            FrameData(timestamp_ns=16_666_667, frame_duration_ms=16.6),
            FrameData(timestamp_ns=33_333_333, frame_duration_ms=16.6),
            FrameData(timestamp_ns=50_000_000, frame_duration_ms=16.6),
            FrameData(timestamp_ns=66_666_667, frame_duration_ms=16.6),
            FrameData(timestamp_ns=83_333_333, frame_duration_ms=16.6),
        ]
        fps = calculate_fps(frames, window_ns=100_000_000)
        assert fps == pytest.approx(60.0, rel=0.1)

    def test_fps_with_window(self):
        """测试窗口计算。"""
        base_ts = 1_000_000_000
        frames = [
            FrameData(timestamp_ns=base_ts + i * 16_666_667, frame_duration_ms=16.6)
            for i in range(60)
        ]
        fps = calculate_fps(frames, window_ns=1_000_000_000)
        assert fps == pytest.approx(60.0, rel=0.05)


class TestFrameStats:
    """测试帧统计计算。"""

    def test_calculate_frame_stats(self):
        """测试帧统计计算。"""
        frames = [
            FrameData(timestamp_ns=0, frame_duration_ms=10.0, is_jank=False),
            FrameData(timestamp_ns=16_666_667, frame_duration_ms=40.0, is_jank=True),
            FrameData(timestamp_ns=66_666_667, frame_duration_ms=130.0, is_jank=True, is_big_jank=True),
            FrameData(timestamp_ns=200_000_000, frame_duration_ms=16.0, is_jank=False),
        ]
        ts = datetime.datetime.now()
        stats = calculate_frame_stats(frames, timestamp=ts)

        assert stats.timestamp == ts
        assert stats.jank_count == 1
        assert stats.big_jank_count == 1
        assert len(stats.frames) == 4


class TestDetectJankEvent:
    """测试 Jank 事件检测。"""

    def test_no_jank_event(self):
        """测试无 Jank 事件。"""
        frames = [
            FrameData(timestamp_ns=0, frame_duration_ms=10.0),
            FrameData(timestamp_ns=16_666_667, frame_duration_ms=10.0),
        ]
        event = detect_jank_event(frames, threshold_count=3)
        assert event is None

    def test_jank_event_triggered(self):
        """测试 Jank 事件触发。"""
        frames = [
            FrameData(timestamp_ns=0, frame_duration_ms=40.0, is_jank=True),
            FrameData(timestamp_ns=50_000_000, frame_duration_ms=50.0, is_jank=True),
            FrameData(timestamp_ns=100_000_000, frame_duration_ms=60.0, is_jank=True),
        ]
        event = detect_jank_event(frames, threshold_count=3)

        assert event is not None
        assert event.jank_count == 3
        assert event.avg_frame_time_ms == pytest.approx(50.0, rel=0.1)
        assert event.max_frame_time_ms == pytest.approx(60.0, rel=0.1)


SAMPLE_SF_LATENCY_60FPS = """\
16666666
100000000000\t100000000000\t100000000000
100016666667\t100016666667\t100016666667
100033333334\t100033333334\t100033333334
100050000001\t100050000001\t100050000001
100066666668\t100066666668\t100066666668
100083333335\t100083333335\t100083333335
100100000002\t100100000002\t100100000002
"""


class TestParseSfLatency:
    """测试 SurfaceFlinger latency 解析。"""

    def test_parse_valid_output(self):
        frames = parse_sf_latency(SAMPLE_SF_LATENCY_60FPS)
        assert len(frames) == 6

    def test_frame_duration_calculation(self):
        frames = parse_sf_latency(SAMPLE_SF_LATENCY_60FPS)
        for f in frames:
            assert 15.0 < f.frame_duration_ms < 18.0

    def test_no_jank_flags_before_detection(self):
        """解析器不设置 jank 标记。"""
        frames = parse_sf_latency(SAMPLE_SF_LATENCY_60FPS)
        assert all(not f.is_jank for f in frames)
        assert all(not f.is_big_jank for f in frames)

    def test_parse_empty_output(self):
        assert parse_sf_latency("") == []

    def test_parse_only_refresh_rate(self):
        assert parse_sf_latency("16666666\n") == []

    def test_parse_with_invalid_timestamps(self):
        output = "16666666\n9223372036854775807\t9223372036854775807\t9223372036854775807\n"
        assert parse_sf_latency(output) == []

    def test_frame_duration_with_jank(self):
        """帧间距差异大的情况下帧耗时计算正确。"""
        output = (
            "16666666\n"
            "100000000000\t100000000000\t100000000000\n"
            "100016666667\t100016666667\t100016666667\n"
            "100083333334\t100083333334\t100083333334\n"
        )
        frames = parse_sf_latency(output)
        assert len(frames) == 2
        assert frames[0].frame_duration_ms == pytest.approx(16.67, rel=0.01)
        assert frames[1].frame_duration_ms == pytest.approx(66.67, rel=0.01)


class TestDynamicJankDetection:
    """测试 PerfDog 风格动态 Jank 判定。"""

    def test_stable_60fps_no_jank(self):
        """稳定 60fps 不产生 Jank。"""
        frames = [
            FrameData(timestamp_ns=i * 16_666_667, frame_duration_ms=16.67)
            for i in range(10)
        ]
        apply_dynamic_jank_detection(frames, vsync_ms=16.67)
        assert all(not f.is_jank for f in frames)

    def test_sudden_spike_triggers_jank(self):
        """帧耗时突然飙升触发 Jank。"""
        frames = [
            FrameData(timestamp_ns=0, frame_duration_ms=16.67),
            FrameData(timestamp_ns=16_666_667, frame_duration_ms=16.67),
            FrameData(timestamp_ns=33_333_334, frame_duration_ms=16.67),
            FrameData(timestamp_ns=50_000_001, frame_duration_ms=80.0),
        ]
        apply_dynamic_jank_detection(frames, vsync_ms=16.67)
        assert frames[3].is_jank is True

    def test_stable_30fps_no_jank(self):
        """稳定 30fps（~33ms 帧耗时）不应判为 Jank。"""
        frames = [
            FrameData(timestamp_ns=i * 33_333_333, frame_duration_ms=33.33)
            for i in range(10)
        ]
        apply_dynamic_jank_detection(frames, vsync_ms=16.67)
        assert all(not f.is_jank for f in frames[3:])

    def test_big_jank_detection(self):
        """帧耗时 > 前3帧均值×2 且 > 6×VSYNC 为 BigJank。"""
        frames = [
            FrameData(timestamp_ns=0, frame_duration_ms=16.67),
            FrameData(timestamp_ns=16_666_667, frame_duration_ms=16.67),
            FrameData(timestamp_ns=33_333_334, frame_duration_ms=16.67),
            FrameData(timestamp_ns=50_000_001, frame_duration_ms=150.0),
        ]
        apply_dynamic_jank_detection(frames, vsync_ms=16.67)
        assert frames[3].is_big_jank is True

    def test_first_three_frames_no_jank(self):
        """前 3 帧没有足够历史数据，不判定。"""
        frames = [
            FrameData(timestamp_ns=0, frame_duration_ms=100.0),
            FrameData(timestamp_ns=100_000_000, frame_duration_ms=100.0),
            FrameData(timestamp_ns=200_000_000, frame_duration_ms=100.0),
        ]
        apply_dynamic_jank_detection(frames, vsync_ms=16.67)
        assert all(not f.is_jank for f in frames)

    def test_game_running_at_15fps_no_jank(self):
        """游戏稳定以 ~15fps 运行（~66ms帧耗时），不应误判为 Jank。"""
        frames = [
            FrameData(timestamp_ns=i * 66_666_667, frame_duration_ms=66.67)
            for i in range(10)
        ]
        apply_dynamic_jank_detection(frames, vsync_ms=16.67)
        assert all(not f.is_jank for f in frames[3:])


class TestGetDefaultJankThreshold:
    """测试默认 Jank 阈值。"""

    def test_60hz_threshold(self):
        """测试 60Hz 阈值。"""
        assert get_default_jank_threshold(60) == 3

    def test_90hz_threshold(self):
        """测试 90Hz 阈值。"""
        assert get_default_jank_threshold(90) == 5

    def test_120hz_threshold(self):
        """测试 120Hz 阈值。"""
        assert get_default_jank_threshold(120) == 5

    def test_144hz_threshold(self):
        """测试 144Hz 阈值。"""
        assert get_default_jank_threshold(144) == 7

    def test_unknown_refresh_rate(self):
        """测试未知刷新率。"""
        assert get_default_jank_threshold(30) == 3
        assert get_default_jank_threshold(240) == 7
