"""Perfetto Capture 模块 — 帧数据解析器

解析 `dumpsys gfxinfo <pkg> framestats` 和 `dumpsys SurfaceFlinger --latency`
输出，计算 FPS 和 Jank 事件。
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import TYPE_CHECKING

from .models import FrameData, FrameStats, JankEvent

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

JANK_THRESHOLD_MS = 33.3
BIG_JANK_THRESHOLD_MS = 125.0

_PROFILEDATA_START = "---PROFILEDATA---"
_PROFILEDATA_END = "---PROFILEDATA---"
_FRAME_LINE_PATTERN = re.compile(r"^\d+,")


def parse_framestats(output: str) -> list[FrameData]:
    """解析 dumpsys gfxinfo framestats 输出。

    Args:
        output: dumpsys gfxinfo <pkg> framestats 的输出文本

    Returns:
        解析出的帧数据列表

    Raises:
        ValueError: 无法解析输出格式
    """
    frames: list[FrameData] = []

    in_profile_data = False
    header_found = False

    for line in output.splitlines():
        line = line.strip()

        if _PROFILEDATA_START in line:
            in_profile_data = True
            header_found = False
            continue

        if not in_profile_data:
            continue

        if line.startswith("Flags,"):
            header_found = True
            continue

        if not header_found:
            continue

        if not _FRAME_LINE_PATTERN.match(line):
            if line == _PROFILEDATA_END or not line:
                in_profile_data = False
            continue

        frame = _parse_frame_line(line)
        if frame:
            frames.append(frame)

    return frames


def parse_sf_latency(output: str) -> list[FrameData]:
    """解析 dumpsys SurfaceFlinger --latency 输出。

    格式：第一行为刷新周期（ns），之后每行 3 个时间戳（ns）：
    desiredPresentTime  actualPresentTime  frameReadyTime

    通过相邻帧 actualPresentTime 差值计算帧耗时。

    Args:
        output: dumpsys SurfaceFlinger --latency <layer> 的输出文本

    Returns:
        解析出的帧数据列表
    """
    lines = output.strip().splitlines()
    if len(lines) < 3:
        return []

    timestamps: list[int] = []
    for line in lines[1:]:
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        try:
            actual_present = int(parts[1])
            if actual_present <= 0 or actual_present == 0x7FFFFFFFFFFFFFFF:
                continue
            timestamps.append(actual_present)
        except (ValueError, IndexError):
            continue

    if len(timestamps) < 2:
        return []

    frames: list[FrameData] = []
    for i in range(1, len(timestamps)):
        delta_ns = timestamps[i] - timestamps[i - 1]
        if delta_ns <= 0 or delta_ns > 1_000_000_000:
            continue

        duration_ms = delta_ns / 1_000_000
        frames.append(
            FrameData(
                timestamp_ns=timestamps[i],
                frame_duration_ms=duration_ms,
            )
        )

    return frames


def _parse_frame_line(line: str) -> FrameData | None:
    """解析单行帧数据。

    Framestats 格式 (以逗号分隔):
    Flags,IntendedVsync,Vsync,OldestInputEvent,NewestInputEvent,
    HandleInputStart,AnimationStart,PerformTraversalsStart,DrawStart,
    SyncQueued,SyncStart,IssueDrawCommandsStart,SwapBuffers,
    FrameCompleted,DequeueBufferDuration,QueueBufferDuration,GpuCompleted

    帧耗时 = FrameCompleted - IntendedVsync (纳秒)
    """
    parts = line.split(",")
    if len(parts) < 14:
        return None

    try:
        intended_vsync_ns = int(parts[1])
        frame_completed_ns = int(parts[13])

        if intended_vsync_ns <= 0 or frame_completed_ns <= 0:
            return None

        if frame_completed_ns < intended_vsync_ns:
            return None

        duration_ns = frame_completed_ns - intended_vsync_ns
        duration_ms = duration_ns / 1_000_000

        return FrameData(
            timestamp_ns=frame_completed_ns,
            frame_duration_ms=duration_ms,
        )
    except (ValueError, IndexError):
        return None


def apply_dynamic_jank_detection(
    frames: list[FrameData],
    vsync_ms: float = 16.67,
) -> list[FrameData]:
    """PerfDog 风格动态 Jank 判定。

    基于游戏实际帧率而非固定阈值来判定卡顿：
    - Jank: 帧耗时 > 前 3 帧均值 × 2 且 > 2 × VSYNC
    - BigJank: 帧耗时 > 前 3 帧均值 × 2 且 > 6 × VSYNC

    Args:
        frames: 帧数据列表（已计算 frame_duration_ms）
        vsync_ms: VSYNC 周期（ms），来自屏幕刷新率

    Returns:
        更新了 is_jank/is_big_jank 标记的帧列表
    """
    two_vsync = 2 * vsync_ms
    six_vsync = 6 * vsync_ms

    for i, frame in enumerate(frames):
        if i < 3:
            frame.is_jank = False
            frame.is_big_jank = False
            continue

        prev_avg = sum(frames[j].frame_duration_ms for j in range(i - 3, i)) / 3
        is_slow = frame.frame_duration_ms > 2 * prev_avg

        frame.is_jank = is_slow and frame.frame_duration_ms > two_vsync
        frame.is_big_jank = is_slow and frame.frame_duration_ms > six_vsync

    return frames


def calculate_fps(frames: list[FrameData], window_ns: int = 1_000_000_000) -> float:
    """计算 FPS。

    Args:
        frames: 帧数据列表（按 timestamp_ns 排序）
        window_ns: 计算窗口大小（纳秒），默认 1 秒

    Returns:
        FPS 值；如果帧数不足返回 0.0
    """
    if not frames:
        return 0.0

    if len(frames) == 1:
        return 1.0

    sorted_frames = sorted(frames, key=lambda f: f.timestamp_ns)
    latest_ts = sorted_frames[-1].timestamp_ns
    cutoff_ts = latest_ts - window_ns

    recent_frames = [f for f in sorted_frames if f.timestamp_ns >= cutoff_ts]

    if len(recent_frames) < 2:
        return float(len(recent_frames))

    time_span_ns = recent_frames[-1].timestamp_ns - recent_frames[0].timestamp_ns
    if time_span_ns <= 0:
        return float(len(recent_frames))

    time_span_sec = time_span_ns / 1_000_000_000
    return (len(recent_frames) - 1) / time_span_sec


def calculate_frame_stats(
    frames: list[FrameData],
    timestamp: datetime.datetime | None = None,
) -> FrameStats:
    """计算帧统计信息。

    Args:
        frames: 帧数据列表
        timestamp: 统计时间戳，默认为当前时间

    Returns:
        帧统计对象
    """
    if timestamp is None:
        timestamp = datetime.datetime.now()

    fps = calculate_fps(frames)
    jank_count = sum(1 for f in frames if f.is_jank and not f.is_big_jank)
    big_jank_count = sum(1 for f in frames if f.is_big_jank)

    return FrameStats(
        timestamp=timestamp,
        fps=fps,
        jank_count=jank_count,
        big_jank_count=big_jank_count,
        frames=frames,
    )


def detect_jank_event(
    frames: list[FrameData],
    threshold_count: int = 3,
) -> JankEvent | None:
    """检测是否触发 Jank 事件。

    Args:
        frames: 帧数据列表（最近 1 秒内的帧）
        threshold_count: Jank 帧数阈值

    Returns:
        触发事件或 None
    """
    jank_frames = [f for f in frames if f.is_jank or f.is_big_jank]

    if len(jank_frames) < threshold_count:
        return None

    frame_times = [f.frame_duration_ms for f in jank_frames]

    return JankEvent(
        timestamp=datetime.datetime.now(),
        jank_count=len(jank_frames),
        avg_frame_time_ms=sum(frame_times) / len(frame_times),
        max_frame_time_ms=max(frame_times),
    )


def get_default_jank_threshold(refresh_rate: int) -> int:
    """根据刷新率获取默认 Jank 阈值。

    Args:
        refresh_rate: 屏幕刷新率 (Hz)

    Returns:
        默认 Jank 阈值（帧数/秒）
    """
    thresholds = {
        60: 3,
        90: 5,
        120: 5,
        144: 7,
    }

    if refresh_rate in thresholds:
        return thresholds[refresh_rate]

    if refresh_rate <= 60:
        return 3
    if refresh_rate <= 90:
        return 5
    if refresh_rate <= 120:
        return 5
    return 7
