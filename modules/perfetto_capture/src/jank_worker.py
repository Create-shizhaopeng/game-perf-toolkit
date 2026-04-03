"""Perfetto Capture 模块 — Jank 监控 Worker

后台线程，定时轮询帧数据、检测 Jank 触发。
"""

from __future__ import annotations

import datetime
import logging
import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

from .jank_parser import (
    apply_dynamic_jank_detection,
    calculate_frame_stats,
    detect_jank_event,
    parse_framestats,
    parse_sf_latency,
)
from .jank_service import JankMonitorService
from .models import (
    CaptureRegion,
    FrameStats,
    JankConfig,
    JankEvent,
    MonitorState,
    MonitorStats,
)

if TYPE_CHECKING:
    from toolkit.core.adb_manager import AdbManager


class JankMonitorWorker(QThread):
    """Jank 监控 Worker。

    信号:
        frame_stats_ready: 帧数据更新（每 200ms）
        jank_triggered: Jank 触发事件
        app_state_changed: 应用前后台状态变化
        state_changed: 监控状态变化
        monitor_stats_updated: 监控统计更新
        capture_requested: 请求保存 trace
        capture_region_changed: 抓取选区变化
    """

    frame_stats_ready = pyqtSignal(FrameStats)
    jank_triggered = pyqtSignal(JankEvent)
    app_state_changed = pyqtSignal(bool)
    state_changed = pyqtSignal(MonitorState)
    monitor_stats_updated = pyqtSignal(MonitorStats)
    capture_requested = pyqtSignal()
    capture_region_changed = pyqtSignal(list)

    POLL_INTERVAL_MS = 200
    FOREGROUND_CHECK_INTERVAL_MS = 500
    FOREGROUND_RESUME_DELAY_SEC = 5

    def __init__(self, adb: AdbManager, serial: str, parent=None) -> None:
        super().__init__(parent)
        self._service = JankMonitorService(adb, serial)
        self._config: JankConfig | None = None
        self._target_package: str = ""

        self._state = MonitorState.IDLE
        self._running = False
        self._paused = False
        self._capture_paused = False

        self._trigger_time: datetime.datetime | None = None
        self._stabilize_start: datetime.datetime | None = None
        self._capture_count = 0

        self._total_jank_count = 0
        self._total_big_jank_count = 0
        self._total_fps_sum = 0.0
        self._fps_sample_count = 0
        self._start_time: datetime.datetime | None = None

        self._was_foreground = True
        self._foreground_resume_time: datetime.datetime | None = None
        self._last_foreground_check = 0.0

        self._capture_regions: list[CaptureRegion] = []
        self._current_region: CaptureRegion | None = None

        self._fps_history: list[float] = []
        self._game_vsync_ms: float | None = None

        self._last_sf_timestamp_ns: int = 0
        self._recent_frames_tail: list = []
        self._jank_window: list[tuple[float, int]] = []
        self._gfxinfo_empty_count: int = 0

    def configure(self, config: JankConfig, target_package: str) -> None:
        """配置监控参数。"""
        self._config = config
        self._target_package = target_package

    def start_monitor(self) -> None:
        """开始监控。"""
        if self._running:
            return

        self._running = True
        self._paused = False
        self._capture_paused = False
        self._state = MonitorState.MONITORING

        self._trigger_time = None
        self._stabilize_start = None
        self._capture_count = 0

        self._total_jank_count = 0
        self._total_big_jank_count = 0
        self._total_fps_sum = 0.0
        self._fps_sample_count = 0
        self._start_time = datetime.datetime.now()
        self._fps_history.clear()
        self._game_vsync_ms = None

        self._was_foreground = True
        self._foreground_resume_time = None
        self._last_foreground_check = 0.0

        self._capture_regions = []
        self._current_region = None
        self._last_sf_timestamp_ns = 0
        self._recent_frames_tail = []
        self._jank_window = []
        self._gfxinfo_empty_count = 0
        self._start_capture_region()

        self._service.clear_cache()
        frame_source = self._service.detect_frame_source(self._target_package)
        logger.info("帧数据来源: %s (pkg=%s)", frame_source, self._target_package)

        if frame_source == "sf_latency":
            self._service.reset_sf_latency(self._target_package)
        else:
            self._service.reset_framestats(self._target_package)

        self.state_changed.emit(self._state)
        self.start()

    def stop_monitor(self) -> None:
        """停止监控。"""
        self._running = False
        self._end_capture_region()
        self.wait()

    def pause_capture_detection(self) -> None:
        """暂停抓取判定（不暂停帧率统计）。"""
        if not self._capture_paused:
            self._capture_paused = True
            self._end_capture_region()
            self._start_non_capture_region("paused")

    def resume_capture_detection(self) -> None:
        """恢复抓取判定。"""
        if self._capture_paused:
            self._capture_paused = False
            self._end_capture_region()
            self._start_capture_region()

    @property
    def capture_regions(self) -> list[CaptureRegion]:
        """获取抓取选区列表。"""
        return self._capture_regions.copy()

    @property
    def monitor_state(self) -> MonitorState:
        """获取监控状态。"""
        return self._state

    def run(self) -> None:
        """Worker 主循环。"""
        poll_count = 0

        while self._running:
            now = time.time()

            if now - self._last_foreground_check >= self.FOREGROUND_CHECK_INTERVAL_MS / 1000:
                self._check_foreground_state()
                self._last_foreground_check = now

            if not self._paused:
                self._poll_frame_data()
                poll_count += 1

                if poll_count % 5 == 0:
                    self._emit_monitor_stats()

            self.msleep(self.POLL_INTERVAL_MS)

        self._state = MonitorState.IDLE
        self.state_changed.emit(self._state)

    GFXINFO_FALLBACK_THRESHOLD = 10

    def _poll_frame_data(self) -> None:
        """轮询帧数据，自动选择 gfxinfo 或 SurfaceFlinger 采集方式。

        如果 gfxinfo 连续返回空超过阈值，自动降级到 SF latency。
        """
        if self._service.using_sf_latency:
            frames = self._poll_sf_latency()
        else:
            frames = self._poll_gfxinfo()
            if not frames:
                self._gfxinfo_empty_count += 1
                if self._gfxinfo_empty_count >= self.GFXINFO_FALLBACK_THRESHOLD:
                    self._try_fallback_to_sf_latency()
            else:
                self._gfxinfo_empty_count = 0

        if not frames:
            return

        refresh_rate = self._service.get_display_refresh_rate()
        vsync_ms = 1000.0 / refresh_rate

        context_frames = self._recent_frames_tail + frames
        apply_dynamic_jank_detection(context_frames, vsync_ms)

        self._recent_frames_tail = context_frames[-3:]

        slow_frames = [f for f in frames if f.frame_duration_ms > 2 * vsync_ms]
        if slow_frames:
            max_ft = max(f.frame_duration_ms for f in slow_frames)
            jank_in_batch = sum(1 for f in frames if f.is_jank or f.is_big_jank)
            logger.debug(
                "慢帧检测: %d帧>%.0fms, max=%.1fms, jank=%d (vsync=%.1fms)",
                len(slow_frames), 2 * vsync_ms, max_ft, jank_in_batch, vsync_ms,
            )

        stats = calculate_frame_stats(frames)
        logger.debug(
            "帧统计: fps=%.1f, jank=%d, frames=%d, source=%s",
            stats.fps, stats.jank_count, len(frames),
            "sf_latency" if self._service.using_sf_latency else "gfxinfo",
        )
        self.frame_stats_ready.emit(stats)

        self._total_jank_count += stats.jank_count
        self._total_big_jank_count += stats.big_jank_count
        self._total_fps_sum += stats.fps
        self._fps_sample_count += 1

        if stats.fps > 0:
            self._fps_history.append(stats.fps)
            if len(self._fps_history) > self._FPS_HISTORY_SIZE:
                self._fps_history.pop(0)

        if not self._capture_paused and len(self._fps_history) >= self._STABILIZATION_POLLS:
            self._update_trigger_state(stats)

    def _try_fallback_to_sf_latency(self) -> None:
        """gfxinfo 持续返回空时，运行时降级到 SurfaceFlinger latency。"""
        layer = self._service._find_surface_layer(self._target_package)
        if layer:
            self._service._use_sf_latency = True
            self._service.reset_sf_latency(self._target_package)
            self._last_sf_timestamp_ns = 0
            self._gfxinfo_empty_count = 0
            logger.info(
                "gfxinfo 连续 %d 次为空，运行时降级到 SF latency (layer=%s)",
                self.GFXINFO_FALLBACK_THRESHOLD, layer,
            )
        else:
            self._gfxinfo_empty_count = 0
            logger.warning("gfxinfo 持续为空且未找到 SF 图层，无法降级")

    def _poll_gfxinfo(self) -> list:
        """通过 gfxinfo framestats 采集帧数据。"""
        output = self._service.get_framestats(self._target_package)
        if not output:
            return []
        frames = parse_framestats(output)
        if not frames:
            logger.debug("gfxinfo 解析帧数据为空 (output len=%d)", len(output))
        return frames

    def _poll_sf_latency(self) -> list:
        """通过 SurfaceFlinger --latency 采集帧数据。

        SF latency 返回累积的帧缓冲区，通过 _last_sf_timestamp_ns 过滤已处理的帧。
        """
        output = self._service.get_sf_latency(self._target_package)
        if not output:
            return []
        all_frames = parse_sf_latency(output)
        if not all_frames:
            logger.debug("SF latency 解析帧数据为空 (output len=%d)", len(output))
            return []

        new_frames = [f for f in all_frames if f.timestamp_ns > self._last_sf_timestamp_ns]
        if new_frames:
            self._last_sf_timestamp_ns = new_frames[-1].timestamp_ns
            logger.debug("SF latency 新帧: %d (总计 %d)", len(new_frames), len(all_frames))

        return new_frames

    def _check_foreground_state(self) -> None:
        """检查应用前后台状态。"""
        is_foreground = self._service.is_app_foreground(self._target_package)

        if self._was_foreground and not is_foreground:
            self._on_app_background()
        elif not self._was_foreground and is_foreground:
            self._on_app_foreground()

        self._was_foreground = is_foreground

        if self._foreground_resume_time:
            elapsed = (datetime.datetime.now() - self._foreground_resume_time).total_seconds()
            if elapsed >= self.FOREGROUND_RESUME_DELAY_SEC:
                self._foreground_resume_time = None
                if not self._capture_paused:
                    self._end_capture_region()
                    self._start_capture_region()

    def _on_app_background(self) -> None:
        """应用切到后台。"""
        self.app_state_changed.emit(False)
        self._end_capture_region()
        self._start_non_capture_region("background")
        self._paused = True

        zero_stats = FrameStats(
            timestamp=datetime.datetime.now(),
            fps=0.0,
            jank_count=0,
            big_jank_count=0,
            frames=[],
        )
        self.frame_stats_ready.emit(zero_stats)

    def _on_app_foreground(self) -> None:
        """应用恢复前台。"""
        self.app_state_changed.emit(True)
        self._paused = False
        self._foreground_resume_time = datetime.datetime.now()
        self._last_sf_timestamp_ns = 0
        self._recent_frames_tail = []
        self._service.invalidate_sf_layer_cache()

    _FPS_HISTORY_SIZE = 15
    _STABILIZATION_POLLS = 5

    def _get_game_vsync_ms(self) -> float:
        """用滚动中位数估算游戏目标帧周期。"""
        display_vsync = 1000.0 / self._service.get_display_refresh_rate()

        if len(self._fps_history) < self._STABILIZATION_POLLS:
            return display_vsync

        sorted_fps = sorted(self._fps_history)
        median_fps = sorted_fps[len(sorted_fps) // 2]
        game_vsync = 1000.0 / max(median_fps, 1)

        if self._game_vsync_ms is None or abs(game_vsync - self._game_vsync_ms) > 2.0:
            logger.info("游戏帧周期估算: %.1fms (median FPS=%.1f)", game_vsync, median_fps)
            self._game_vsync_ms = game_vsync

        return max(game_vsync, display_vsync)

    def _update_trigger_state(self, stats: FrameStats) -> None:
        """更新触发状态机（使用 1 秒滑动窗口累积 jank 计数）。"""
        if not self._config or self._capture_count >= self._config.max_captures:
            if self._state != MonitorState.COMPLETED:
                self._state = MonitorState.COMPLETED
                self.state_changed.emit(self._state)
            return

        threshold = self._config.jank_threshold
        batch_jank = stats.jank_count + stats.big_jank_count
        now = datetime.datetime.now()
        now_ts = now.timestamp()

        vsync_ms = self._get_game_vsync_ms()

        dropped_in_batch = 0
        for f in stats.frames:
            if f.frame_duration_ms > vsync_ms * 1.5:
                dropped = int(f.frame_duration_ms / vsync_ms) - 1
                dropped_in_batch += max(dropped, 0)

        if dropped_in_batch > 0:
            self._jank_window.append((now_ts, dropped_in_batch))

        cutoff = now_ts - 1.0
        self._jank_window = [(t, c) for t, c in self._jank_window if t >= cutoff]
        dropped_in_window = sum(c for _, c in self._jank_window)

        if dropped_in_window > 0:
            logger.debug(
                "丢帧累积: window=%d/%d, state=%s",
                dropped_in_window, threshold, self._state.value,
            )

        if self._state == MonitorState.MONITORING:
            if dropped_in_window >= threshold:
                slow_frames = [
                    f for f in stats.frames
                    if f.frame_duration_ms > vsync_ms * 1.5
                ]
                max_ft = max((f.frame_duration_ms for f in stats.frames), default=0)
                avg_ft = (
                    sum(f.frame_duration_ms for f in slow_frames) / len(slow_frames)
                    if slow_frames else max_ft
                )
                jank_event = JankEvent(
                    timestamp=now,
                    jank_count=dropped_in_window,
                    avg_frame_time_ms=avg_ft,
                    max_frame_time_ms=max_ft,
                )
                self._state = MonitorState.TRIGGERED
                self._trigger_time = now
                self._stabilize_start = None
                self.state_changed.emit(self._state)
                self.jank_triggered.emit(jank_event)
                self._jank_window.clear()

        elif self._state == MonitorState.TRIGGERED:
            elapsed = (now - self._trigger_time).total_seconds() if self._trigger_time else 0
            if elapsed >= self._config.stabilize_delay_sec:
                self._state = MonitorState.STABILIZING
                self._stabilize_start = now
                self.state_changed.emit(self._state)

        elif self._state == MonitorState.STABILIZING:
            total_since_trigger = (
                (now - self._trigger_time).total_seconds()
                if self._trigger_time else 0
            )
            quiet_elapsed = (
                (now - self._stabilize_start).total_seconds()
                if self._stabilize_start
                else 0
            )

            if dropped_in_window >= threshold:
                self._stabilize_start = now
                quiet_elapsed = 0

            if total_since_trigger >= self._config.max_stabilize_sec:
                logger.info("达到最大稳定等待 %.1fs，强制抓取", total_since_trigger)
                self._request_capture()
            elif quiet_elapsed >= self._config.stabilize_delay_sec:
                logger.info("安静期 %.1fs，触发抓取", quiet_elapsed)
                self._request_capture()

    def _request_capture(self) -> None:
        """请求保存 trace。"""
        logger.info(
            "请求抓取: capture_count=%d/%d",
            self._capture_count + 1,
            self._config.max_captures if self._config else 0,
        )
        self._state = MonitorState.SAVING
        self.state_changed.emit(self._state)
        self.capture_requested.emit()

        self._capture_count += 1
        self._trigger_time = None
        self._stabilize_start = None

        if self._capture_count < self._config.max_captures:
            self._state = MonitorState.MONITORING
            logger.info("抓取完成，恢复监控状态 (%d/%d)",
                        self._capture_count, self._config.max_captures)
        else:
            self._state = MonitorState.COMPLETED
            logger.info("已达最大抓取次数，监控完成")

        self.state_changed.emit(self._state)

    def _emit_monitor_stats(self) -> None:
        """发射监控统计信息。"""
        if not self._start_time:
            return

        duration = (datetime.datetime.now() - self._start_time).total_seconds()
        avg_fps = self._total_fps_sum / self._fps_sample_count if self._fps_sample_count > 0 else 0.0

        stats = MonitorStats(
            avg_fps=round(avg_fps, 1),
            total_jank_count=self._total_jank_count,
            total_big_jank_count=self._total_big_jank_count,
            capture_count=self._capture_count,
            monitor_duration_sec=round(duration, 1),
        )
        self.monitor_stats_updated.emit(stats)

    def _start_capture_region(self) -> None:
        """开始新的抓取选区。"""
        capture_count = sum(1 for r in self._capture_regions if r.is_capture)
        label = f"capture{capture_count + 1}"

        self._current_region = CaptureRegion(
            start_time=datetime.datetime.now(),
            is_capture=True,
            label=label,
        )
        self._capture_regions.append(self._current_region)
        self.capture_region_changed.emit(self._capture_regions.copy())

    def _start_non_capture_region(self, reason: str = "") -> None:
        """开始新的非抓取选区。"""
        self._current_region = CaptureRegion(
            start_time=datetime.datetime.now(),
            is_capture=False,
            label="",
        )
        self._capture_regions.append(self._current_region)
        self.capture_region_changed.emit(self._capture_regions.copy())

    def _end_capture_region(self) -> None:
        """结束当前选区。"""
        if self._current_region and self._current_region.end_time is None:
            self._current_region.end_time = datetime.datetime.now()
            idx = len(self._capture_regions) - 1
            if idx >= 0:
                self._capture_regions[idx] = self._current_region
            self.capture_region_changed.emit(self._capture_regions.copy())
            self._current_region = None
