"""Perfetto Capture 模块 — Jank 统计显示组件

紧凑的单行统计信息。
"""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .models import MonitorStats


class MonitorStatsWidget(QWidget):
    """监控统计显示（单行紧凑）。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(22)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(12)

        self._labels: dict[str, QLabel] = {}
        items = [
            ("fps", "FPS", None),
            ("jank", "Jank", "#FABF42"),
            ("bigjank", "BigJank", "#F85149"),
            ("capture", "抓取", None),
            ("duration", "时长", None),
        ]
        for key, title, color in items:
            lbl = QLabel(f"{title}: --")
            style = "font-size: 11px;"
            if color:
                style += f" color: {color};"
            lbl.setStyleSheet(style)
            layout.addWidget(lbl)
            self._labels[key] = lbl

        layout.addStretch()

    def update_stats(self, stats: MonitorStats, max_captures: int = 3) -> None:
        self._labels["fps"].setText(f"FPS: {stats.avg_fps:.1f}")
        self._labels["jank"].setText(f"Jank: {stats.total_jank_count}")
        self._labels["bigjank"].setText(f"BigJank: {stats.total_big_jank_count}")
        self._labels["capture"].setText(f"抓取: {stats.capture_count}/{max_captures}")
        m, s = divmod(int(stats.monitor_duration_sec), 60)
        self._labels["duration"].setText(f"时长: {m:02d}:{s:02d}")

    def clear(self) -> None:
        for lbl in self._labels.values():
            parts = lbl.text().split(":")
            lbl.setText(f"{parts[0]}: --")
