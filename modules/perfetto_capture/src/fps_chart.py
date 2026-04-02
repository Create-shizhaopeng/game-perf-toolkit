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
    """FPS 图表数据管理。"""

    def __init__(self, max_seconds: int = 300) -> None:
        self._max_points = max_seconds * 5
        self._timestamps = np.zeros(self._max_points, dtype=np.float64)
        self._fps_values = np.zeros(self._max_points, dtype=np.float64)
        self._current_idx = 0
        self._start_time: datetime.datetime | None = None
        self._max_fps_seen = 0.0

        self._jank_points: list[tuple[float, float]] = []
        self._big_jank_points: list[tuple[float, float]] = []

    def add_stats(self, stats: FrameStats) -> None:
        if self._start_time is None:
            self._start_time = stats.timestamp

        elapsed = (stats.timestamp - self._start_time).total_seconds()

        if self._current_idx >= self._max_points:
            self._timestamps[:-1] = self._timestamps[1:]
            self._fps_values[:-1] = self._fps_values[1:]
            self._current_idx = self._max_points - 1
            cutoff = elapsed - 300
            self._jank_points = [(x, y) for x, y in self._jank_points if x > cutoff]
            self._big_jank_points = [(x, y) for x, y in self._big_jank_points if x > cutoff]

        self._timestamps[self._current_idx] = elapsed
        self._fps_values[self._current_idx] = stats.fps
        self._current_idx += 1

        if stats.fps > self._max_fps_seen:
            self._max_fps_seen = stats.fps

        if stats.jank_count > 0:
            self._jank_points.append((elapsed, stats.fps))
        if stats.big_jank_count > 0:
            self._big_jank_points.append((elapsed, stats.fps))

    def get_curve_data(self) -> tuple[np.ndarray, np.ndarray]:
        return (
            self._timestamps[: self._current_idx].copy(),
            self._fps_values[: self._current_idx].copy(),
        )

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
        if self._current_idx == 0:
            return 0.0
        return self._timestamps[self._current_idx - 1]

    @property
    def latest_fps(self) -> float:
        if self._current_idx == 0:
            return 0.0
        return self._fps_values[self._current_idx - 1]

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
        self._timestamps.fill(0)
        self._fps_values.fill(0)
        self._current_idx = 0
        self._start_time = None
        self._max_fps_seen = 0.0
        self._jank_points.clear()
        self._big_jank_points.clear()


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

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._data = FpsChartData()
        self._paused = False
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
        self._plot.setYRange(0, 70)
        self._plot.setXRange(0, 60)
        vb = self._plot.getViewBox()
        vb.setMouseEnabled(x=False, y=False)
        vb.setLimits(xMin=0, yMin=0, yMax=200)

        self._fps_curve = self._plot.plot(
            pen=pg.mkPen(color=_FPS_COLOR, width=2),
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
        self._plot.setXRange(0, 60, padding=0)
        self._plot.setYRange(0, 70, padding=0)

    def _update_chart(self) -> None:
        timestamps, fps_values = self._data.get_curve_data()
        if len(timestamps) > 0:
            self._fps_curve.setData(timestamps, fps_values)

            latest = timestamps[-1]
            x_max = max(latest + 5, 60)
            self._plot.setXRange(0, x_max, padding=0)

            y_max = self._calc_y_max(self._data.max_fps)
            self._plot.setYRange(0, y_max, padding=0)

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
