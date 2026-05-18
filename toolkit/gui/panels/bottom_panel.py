# -*- coding: utf-8 -*-
"""底部日志面板 — VS Code 风格的统一日志输出区域。

聚合所有模块日志，支持频道切换和级别过滤。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QTextCharFormat
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTabBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.codicons import codicon_font, icon_char
from toolkit.gui.log_manager import LogManager
from toolkit.gui.theme_colors import get_colors

_ALL_TAB = "全部"


class _FilterButton(QPushButton):
    """日志级别过滤切换按钮。"""

    def __init__(self, label: str, level: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.setObjectName("logFilterBtn")
        self.setCheckable(True)
        self.setChecked(True)
        self.level = level
        self.setFixedHeight(20)


class BottomPanel(QWidget):
    """底部日志面板 — 聚合所有模块日志。

    Header: [频道Tabs] --- [级别过滤] [清除]
    Content: QTextEdit
    """

    def __init__(self, log_manager: LogManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("bottomPanel")
        self._log_manager = log_manager
        self._theme = "dark"
        self._current_source: str | None = None  # None = 全部

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("bottomPanelHeader")
        header.setFixedHeight(28)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 0, 4, 0)
        h_layout.setSpacing(4)

        self._tab_bar = QTabBar()
        self._tab_bar.setObjectName("logChannelBar")
        self._tab_bar.setDrawBase(False)
        self._tab_bar.setExpanding(False)
        self._tab_bar.addTab(_ALL_TAB)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        h_layout.addWidget(self._tab_bar)

        h_layout.addStretch()

        self._filters: dict[str, _FilterButton] = {}
        for label, level in [("Error", "error"), ("Warning", "warning"), ("Info", "info")]:
            btn = _FilterButton(label, level, self)
            btn.toggled.connect(self._on_filter_changed)
            self._filters[level] = btn
            h_layout.addWidget(btn)

        clear_icon = icon_char("clear-all")
        clear_btn = QPushButton(clear_icon, self)
        clear_btn.setObjectName("logClearBtn")
        clear_btn.setFixedSize(24, 20)
        clear_btn.setToolTip("清除日志")
        font = codicon_font(12)
        if font:
            clear_btn.setFont(font)
        clear_btn.clicked.connect(self._on_clear)
        self._clear_btn = clear_btn
        h_layout.addWidget(clear_btn)

        root.addWidget(header)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setObjectName("bottomPanelLog")
        root.addWidget(self._log_view)

        log_manager.log_added.connect(self._on_log_added)
        log_manager.source_registered.connect(self._on_source_registered)

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self._refresh_view()

    def _on_source_registered(self, source: str) -> None:
        self._tab_bar.addTab(source)

    def _on_tab_changed(self, index: int) -> None:
        if index == 0:
            self._current_source = None
        else:
            self._current_source = self._tab_bar.tabText(index)
        self._refresh_view()

    def _on_filter_changed(self) -> None:
        self._refresh_view()

    def _on_clear(self) -> None:
        self._log_manager.clear(self._current_source)
        self._refresh_view()

    def _active_levels(self) -> set[str]:
        levels = set()
        for level, btn in self._filters.items():
            if btn.isChecked():
                levels.add(level)
        levels.add("success")
        return levels

    def _on_log_added(self, ts: str, source: str, msg: str, level: str) -> None:
        if self._current_source is not None and source != self._current_source:
            return
        if level not in self._active_levels():
            return
        self._append_line(ts, source, msg, level)

    def _append_line(self, ts: str, source: str, msg: str, level: str) -> None:
        c = get_colors(self._theme)
        color_map = {
            "error": c["error"],
            "warning": c["warning"],
            "success": c["success"],
            "info": c["fg"],
        }
        fg = color_map.get(level, c["fg"])

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(fg))

        src_fmt = QTextCharFormat()
        src_fmt.setForeground(QColor(c["fg_muted"]))

        cursor = self._log_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        if self._current_source is None:
            cursor.insertText(f"[{ts}] ", src_fmt)
            cursor.insertText(f"[{source}] ", src_fmt)
            cursor.insertText(f"{msg}\n", fmt)
        else:
            cursor.insertText(f"[{ts}] ", src_fmt)
            cursor.insertText(f"{msg}\n", fmt)

        self._log_view.setTextCursor(cursor)
        self._log_view.ensureCursorVisible()

    def _refresh_view(self) -> None:
        """重绘全部内容（频道/过滤切换时）。"""
        self._log_view.clear()
        levels = self._active_levels()
        entries = self._log_manager.get_entries(
            source=self._current_source,
            levels=levels,
        )
        for e in entries:
            self._append_line(e.timestamp, e.source, e.message, e.level)
