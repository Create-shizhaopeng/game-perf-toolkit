"""Perfetto Capture 模块 — FPS 图表组件

深色主题 FPS 曲线图，右侧数值面板，底部选区条。
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollBar,
    QVBoxLayout,
    QWidget,
)

from .models import CaptureRegion, FrameStats

if TYPE_CHECKING:
    pass

_BG = "#1e1e2e"
_AXIS = "#6c7086"
_FPS_COLOR = "#cba6f7"
_JANK_COLOR = "#FABF42"
_BIGJANK_COLOR = "#F85149"
_REGION_CAPTURE = "#4CAF50"
_REGION_NON = "#45475a"
_REGION_BAR_BG = "#313244"


class FpsChartData:
    """FPS 图表数据管理（1 秒聚合，分块增长 numpy 数组）。"""

    INITIAL_CAPACITY = 1800

    def __init__(self) -> None:
        self._capacity = self.INITIAL_CAPACITY
        self._timestamps = np.empty(self._capacity, dtype=np.float64)
        self._fps_values = np.empty(self._capacity, dtype=np.float64)
        self._size = 0
        self._start_time: datetime.datetime | None = None
        self._max_fps_seen = 0.0

        self._jank_points: list[tuple[float, float]] = []
        self._big_jank_points: list[tuple[float, float]] = []

        self._pending_fps: list[float] = []
        self._pending_jank: int = 0
        self._pending_big_jank: int = 0
        self._last_second: int = -1
        self._latest_fps: float = 0.0

    def add_stats(self, stats: FrameStats) -> None:
        if self._start_time is None:
            self._start_time = stats.timestamp

        elapsed = (stats.timestamp - self._start_time).total_seconds()
        current_second = int(elapsed)

        self._latest_fps = stats.fps
        self._pending_fps.append(stats.fps)
        self._pending_jank += stats.jank_count
        self._pending_big_jank += stats.big_jank_count

        if current_second > self._last_second and self._last_second >= 0:
            self._flush_second(float(self._last_second))

        self._last_second = current_second

    def _flush_second(self, timestamp: float) -> None:
        """将累积的 200ms 样本聚合为 1 秒数据点。"""
        if not self._pending_fps:
            return

        avg_fps = sum(self._pending_fps) / len(self._pending_fps)

        if self._size >= self._capacity:
            self._grow()

        self._timestamps[self._size] = timestamp
        self._fps_values[self._size] = avg_fps
        self._size += 1

        if avg_fps > self._max_fps_seen:
            self._max_fps_seen = avg_fps

        if self._pending_jank > 0:
            self._jank_points.append((timestamp, avg_fps))
        if self._pending_big_jank > 0:
            self._big_jank_points.append((timestamp, avg_fps))

        self._pending_fps.clear()
        self._pending_jank = 0
        self._pending_big_jank = 0

    def _grow(self) -> None:
        new_cap = self._capacity * 2
        new_ts = np.empty(new_cap, dtype=np.float64)
        new_fps = np.empty(new_cap, dtype=np.float64)
        new_ts[: self._capacity] = self._timestamps
        new_fps[: self._capacity] = self._fps_values
        self._timestamps = new_ts
        self._fps_values = new_fps
        self._capacity = new_cap

    def get_curve_data(self) -> tuple[np.ndarray, np.ndarray]:
        return self._timestamps[: self._size], self._fps_values[: self._size]

    def get_jank_markers(self) -> tuple[np.ndarray, np.ndarray]:
        if not self._jank_points:
            return np.array([]), np.array([])
        x, y = zip(*self._jank_points)
        return np.array(x), np.array(y)

    def get_big_jank_markers(self) -> tuple[np.ndarray, np.ndarray]:
        if not self._big_jank_points:
            return np.array([]), np.array([])
        x, y = zip(*self._big_jank_points)
        return np.array(x), np.array(y)

    @property
    def elapsed_seconds(self) -> float:
        if self._last_second < 0:
            return 0.0
        return float(self._last_second)

    @property
    def latest_fps(self) -> float:
        return self._latest_fps

    @property
    def total_jank(self) -> int:
        return len(self._jank_points)

    @property
    def total_big_jank(self) -> int:
        return len(self._big_jank_points)

    @property
    def max_fps(self) -> float:
        return self._max_fps_seen

    def clear(self) -> None:
        self._capacity = self.INITIAL_CAPACITY
        self._timestamps = np.empty(self._capacity, dtype=np.float64)
        self._fps_values = np.empty(self._capacity, dtype=np.float64)
        self._size = 0
        self._start_time = None
        self._max_fps_seen = 0.0
        self._latest_fps = 0.0
        self._jank_points.clear()
        self._big_jank_points.clear()
        self._pending_fps.clear()
        self._pending_jank = 0
        self._pending_big_jank = 0
        self._last_second = -1


class ChartStatsOverlay(QWidget):
    """图表右侧数值显示（覆盖在 PlotWidget 上）。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(60)
        self._fps = 0.0
        self._jank = 0
        self._big_jank = 0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_values(self, fps: float, jank: int, big_jank: int) -> None:
        self._fps = fps
        self._jank = jank
        self._big_jank = big_jank
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        y_offset = 20

        font = QFont()
        font.setPixelSize(13)
        font.setBold(True)
        painter.setFont(font)

        painter.setPen(QColor(_FPS_COLOR))
        painter.drawText(4, y_offset, f"{self._fps:.0f}")

        font.setPixelSize(11)
        painter.setFont(font)
        y_offset += 18

        painter.setPen(QColor(_JANK_COLOR))
        painter.drawText(4, y_offset, f"{self._jank}")
        y_offset += 16

        painter.setPen(QColor(_BIGJANK_COLOR))
        painter.drawText(4, y_offset, f"{self._big_jank}")

        painter.end()


class FpsChartWidget(QWidget):
    """FPS 图表组件（深色主题，右侧数值）。

    信号:
        pause_clicked: 暂停按钮点击
        export_clicked: 导出按钮点击
    """

    pause_clicked = pyqtSignal()
    export_clicked = pyqtSignal()

    _FOLLOW_TOLERANCE = 2.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._data = FpsChartData()
        self._paused = False
        self._following = True
        self._syncing_scrollbar = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        chart_container = QWidget()
        chart_layout = QHBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(0)

        pg.setConfigOptions(antialias=True)
        self._plot = pg.PlotWidget()
        self._plot.setBackground(_BG)
        self._plot.showGrid(x=False, y=False)

        axis_pen = pg.mkPen(color=_AXIS, width=1)
        axis_style = {"color": _AXIS, "font-size": "10px"}
        self._plot.setLabel("left", "FPS", **axis_style)
        self._plot.setLabel("bottom", "", **axis_style)

        for axis_name in ("left", "bottom"):
            ax = self._plot.getAxis(axis_name)
            ax.setPen(axis_pen)
            ax.setTextPen(pg.mkPen(color=_AXIS))

        y_axis = self._plot.getAxis("left")
        y_axis.setTicks([[(v, str(v)) for v in (30, 60, 90, 120, 150)]])

        x_axis = self._plot.getAxis("bottom")
        x_axis.setTickSpacing(major=10, minor=1)
        self._plot.setYRange(0, 70)
        self._plot.setXRange(0, 60)
        vb = self._plot.getViewBox()
        vb.setMouseEnabled(x=True, y=False)
        vb.setLimits(xMin=0, yMin=0, yMax=200)
        vb.enableAutoRange(axis="x", enable=False)
        vb.enableAutoRange(axis="y", enable=False)
        vb.sigRangeChangedManually.connect(self._on_range_changed_manually)

        self._fps_curve = self._plot.plot(
            pen=pg.mkPen(color=_FPS_COLOR, width=2),
            clipToView=True,
            downsample=1,
            downsampleMethod="peak",
        )
        self._jank_scatter = self._plot.plot(
            pen=None, symbol="o",
            symbolBrush=_JANK_COLOR, symbolPen=None, symbolSize=7,
        )
        self._big_jank_scatter = self._plot.plot(
            pen=None, symbol="o",
            symbolBrush=_BIGJANK_COLOR, symbolPen=None, symbolSize=9,
        )

        self._region_items: list[pg.LinearRegionItem] = []
        self._region_labels: list[pg.TextItem] = []
        self._region_start_time: datetime.datetime | None = None
        self._current_regions: list[CaptureRegion] = []

        chart_layout.addWidget(self._plot)

        self._stats_overlay = ChartStatsOverlay()
        self._stats_overlay.setStyleSheet(f"background: {_BG};")
        chart_layout.addWidget(self._stats_overlay)

        layout.addWidget(chart_container)

        self._scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        self._scrollbar.setStyleSheet(f"""
            QScrollBar:horizontal {{
                background: {_BG}; height: 12px; border: none;
            }}
            QScrollBar::handle:horizontal {{
                background: {_AXIS}; min-width: 20px; border-radius: 4px;
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                width: 0px;
            }}
        """)
        self._scrollbar.setRange(0, 0)
        self._scrollbar.valueChanged.connect(self._on_scrollbar_changed)
        layout.addWidget(self._scrollbar)

        self._crosshair_v = pg.InfiniteLine(angle=90, pen=pg.mkPen("#585b70", width=1, style=Qt.PenStyle.DashLine))
        self._crosshair_h = pg.InfiniteLine(angle=0, pen=pg.mkPen("#585b70", width=1, style=Qt.PenStyle.DashLine))
        self._crosshair_v.setVisible(False)
        self._crosshair_h.setVisible(False)
        self._plot.addItem(self._crosshair_v, ignoreBounds=True)
        self._plot.addItem(self._crosshair_h, ignoreBounds=True)

        self._hover_text = pg.TextItem(color="#cdd6f4", anchor=(0, 1))
        self._hover_text.setVisible(False)
        font = QFont()
        font.setPixelSize(11)
        self._hover_text.setFont(font)
        self._plot.addItem(self._hover_text, ignoreBounds=True)

        self._proxy = pg.SignalProxy(
            self._plot.scene().sigMouseMoved, rateLimit=60, slot=self._on_mouse_moved
        )
        self._plot.scene().sigMouseClicked.connect(lambda _: None)

    def _on_mouse_moved(self, evt) -> None:
        pos = evt[0]
        if not self._plot.sceneBoundingRect().contains(pos):
            self._hide_crosshair()
            return
        mouse_point = self._plot.getViewBox().mapSceneToView(pos)
        mx = mouse_point.x()

        idx = self._find_nearest_point(mx)
        if idx < 0:
            self._hide_crosshair()
            return

        ts_val = float(self._data._timestamps[idx])
        fps_val = float(self._data._fps_values[idx])

        self._crosshair_v.setPos(ts_val)
        self._crosshair_h.setPos(fps_val)
        self._crosshair_v.setVisible(True)
        self._crosshair_h.setVisible(True)

        if self._data._start_time:
            abs_time = self._data._start_time + datetime.timedelta(seconds=ts_val)
            time_str = abs_time.strftime("%H:%M:%S")
        else:
            time_str = f"{ts_val:.1f}s"

        label = f"{time_str}  FPS: {fps_val:.0f}"
        jank_type = self._check_jank_at(ts_val)
        if jank_type:
            label += f"  {jank_type}"

        self._hover_text.setText(label)
        self._hover_text.setPos(ts_val + 1, fps_val + 5)
        self._hover_text.setVisible(True)

    def _hide_crosshair(self) -> None:
        self._crosshair_v.setVisible(False)
        self._crosshair_h.setVisible(False)
        self._hover_text.setVisible(False)

    def _find_nearest_point(self, mouse_x: float) -> int:
        if self._data._size == 0:
            return -1
        timestamps = self._data._timestamps[: self._data._size]
        idx = int(np.searchsorted(timestamps, mouse_x))
        if idx >= self._data._size:
            idx = self._data._size - 1
        if idx > 0:
            left_dist = abs(mouse_x - timestamps[idx - 1])
            right_dist = abs(mouse_x - timestamps[idx])
            if left_dist < right_dist:
                idx -= 1
        return idx

    def _check_jank_at(self, elapsed: float, tolerance: float = 0.3) -> str:
        for t, _ in self._data._big_jank_points:
            if abs(t - elapsed) < tolerance:
                return "BigJank"
        for t, _ in self._data._jank_points:
            if abs(t - elapsed) < tolerance:
                return "Jank"
        return ""

    def leaveEvent(self, event) -> None:
        self._hide_crosshair()
        super().leaveEvent(event)

    def update_stats(self, stats: FrameStats) -> None:
        self._data.add_stats(stats)
        self._update_chart()

    def set_regions(self, regions: list[CaptureRegion]) -> None:
        self._current_regions = regions
        self._refresh_regions()

    def _refresh_regions(self) -> None:
        """重新绘制所有选区（含活跃选区的实时范围更新）。"""
        for item in self._region_items:
            self._plot.removeItem(item)
        for item in self._region_labels:
            self._plot.removeItem(item)
        self._region_items.clear()
        self._region_labels.clear()

        regions = self._current_regions
        if not regions:
            return

        if not self._region_start_time:
            self._region_start_time = regions[0].start_time

        for region in regions:
            s = (region.start_time - self._region_start_time).total_seconds()
            e = ((region.end_time or datetime.datetime.now()) - self._region_start_time).total_seconds()

            color = QColor(_REGION_CAPTURE) if region.is_capture else QColor(_REGION_NON)
            color.setAlpha(60)
            brush = pg.mkBrush(color)

            edge_color = QColor(_REGION_CAPTURE) if region.is_capture else QColor(_REGION_NON)
            edge_color.setAlpha(120)

            item = pg.LinearRegionItem(
                values=[s, e],
                orientation="vertical",
                brush=brush,
                pen=pg.mkPen(edge_color, width=1),
                movable=False,
            )
            item.setZValue(-10)
            self._plot.addItem(item)
            self._region_items.append(item)

            if region.label:
                label = pg.TextItem(region.label, color="#a6adc8", anchor=(0, 0))
                label.setPos(s + 1, 140)
                font = QFont()
                font.setPixelSize(10)
                label.setFont(font)
                self._plot.addItem(label)
                self._region_labels.append(label)

    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    def clear(self) -> None:
        self._data.clear()
        self._fps_curve.setData([], [])
        self._jank_scatter.setData([], [])
        self._big_jank_scatter.setData([], [])
        self._current_regions = []
        self._refresh_regions()
        self._region_start_time = None
        self._stats_overlay.set_values(0, 0, 0)
        self._following = True
        self._plot.setXRange(0, 60, padding=0)
        self._plot.setYRange(0, 70, padding=0)
        vb = self._plot.getViewBox()
        vb.setLimits(xMax=62)
        self._scrollbar.setRange(0, 0)

    def _on_range_changed_manually(self, _mask: list) -> None:
        """用户手动缩放/拖动后判断是否恢复跟随模式。"""
        if self._data._size == 0:
            return
        x_range = self._plot.getViewBox().viewRange()[0]
        latest = self._data.elapsed_seconds
        covers_all_data = (
            x_range[0] <= self._FOLLOW_TOLERANCE
            and x_range[1] >= latest - self._FOLLOW_TOLERANCE
        )
        self._following = covers_all_data
        if not self._following:
            self._update_y_axis_for_visible_range()
        self._sync_scrollbar_from_view()

    def _on_scrollbar_changed(self, value: int) -> None:
        if self._syncing_scrollbar:
            return
        if self._data._size == 0:
            return
        vb = self._plot.getViewBox()
        x_range = vb.viewRange()[0]
        view_width = x_range[1] - x_range[0]
        scale = self._data.elapsed_seconds / max(self._scrollbar.maximum(), 1)
        new_x_min = value * scale
        new_x_max = new_x_min + view_width
        self._syncing_scrollbar = True
        vb.setXRange(new_x_min, new_x_max, padding=0)
        self._syncing_scrollbar = False
        self._update_y_axis_for_visible_range()

    def _sync_scrollbar_from_view(self) -> None:
        if self._syncing_scrollbar or self._data._size == 0:
            return
        self._syncing_scrollbar = True
        vb = self._plot.getViewBox()
        x_range = vb.viewRange()[0]
        latest = self._data.elapsed_seconds
        total = max(latest, 1.0)
        view_width = x_range[1] - x_range[0]
        sb_max = 1000
        if view_width >= total:
            self._scrollbar.setRange(0, 0)
        else:
            page = int(sb_max * view_width / total)
            self._scrollbar.setRange(0, sb_max - page)
            self._scrollbar.setPageStep(page)
            pos = int(x_range[0] / total * sb_max)
            self._scrollbar.setValue(pos)
        self._syncing_scrollbar = False

    def _update_y_axis_for_visible_range(self) -> None:
        """根据当前可见 X 范围内的数据自适应调整 Y 轴。"""
        if self._data._size == 0:
            return
        x_range = self._plot.getViewBox().viewRange()[0]
        timestamps, fps_values = self._data.get_curve_data()
        mask = (timestamps >= x_range[0]) & (timestamps <= x_range[1])
        visible = fps_values[mask]
        if len(visible) > 0:
            y_max = self._calc_y_max(float(visible.max()))
        else:
            y_max = 70
        self._plot.setYRange(0, y_max, padding=0)

    def _update_chart(self) -> None:
        timestamps, fps_values = self._data.get_curve_data()
        if len(timestamps) > 0:
            self._fps_curve.setData(timestamps, fps_values)

            latest = float(timestamps[-1])
            full_x_max = max(latest + 5, 60)

            vb = self._plot.getViewBox()
            vb.setLimits(xMax=latest + 2)

            if self._following:
                self._plot.setXRange(0, full_x_max, padding=0)
                y_max = self._calc_y_max(self._data.max_fps)
                self._plot.setYRange(0, y_max, padding=0)
            else:
                self._update_y_axis_for_visible_range()

            self._sync_scrollbar_from_view()

            jx, jy = self._data.get_jank_markers()
            if len(jx) > 0:
                self._jank_scatter.setData(jx, jy)
            else:
                self._jank_scatter.setData([], [])

            bx, by = self._data.get_big_jank_markers()
            if len(bx) > 0:
                self._big_jank_scatter.setData(bx, by)
            else:
                self._big_jank_scatter.setData([], [])

            if self._current_regions:
                self._refresh_regions()

            self._stats_overlay.set_values(
                self._data.latest_fps,
                self._data.total_jank,
                self._data.total_big_jank,
            )

    @staticmethod
    def _calc_y_max(fps: float) -> float:
        """根据当前帧率计算 Y 轴最大值。"""
        if fps <= 30:
            return 70
        if fps <= 60:
            return 100
        if fps <= 90:
            return 130
        if fps <= 120:
            return 160
        return 180
