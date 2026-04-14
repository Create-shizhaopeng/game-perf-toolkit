# -*- coding: utf-8 -*-
"""左侧面板 — 导航按钮(上) + 历史记录(下)，垂直 QSplitter 可拖拽。

LeftPanel 包装 NavPanel 和 HistoryArea，对 MainWindow 提供统一接口。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from toolkit.gui.panels.history_area import HistoryArea
from toolkit.gui.widgets.nav_panel import NavPanel


class LeftPanel(QWidget):
    """左侧面板容器 — NavPanel + HistoryArea 的垂直分割布局。"""

    tab_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("leftPanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setObjectName("leftSplitter")
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(4)

        self._nav_panel = NavPanel()
        self._nav_panel.tab_selected.connect(self.tab_selected.emit)

        self._history_area = HistoryArea()
        self._history_area.collapse_toggled.connect(self._on_history_collapsed)

        self._splitter.addWidget(self._nav_panel)
        self._splitter.addWidget(self._history_area)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([400, 300])
        self._splitter.splitterMoved.connect(self._on_splitter_moved)

        self._history_saved_height = 300

        root.addWidget(self._splitter)

    @property
    def nav_panel(self) -> NavPanel:
        return self._nav_panel

    @property
    def history_area(self) -> HistoryArea:
        return self._history_area

    def add_tab_button(self, title: str, icon_text: str = "") -> None:
        self._nav_panel.add_tab_button(title, icon_text)

    def register_history(self, tab_title: str, widget: QWidget) -> None:
        self._history_area.register_history(tab_title, widget)

    def switch_history_to_module(self, tab_title: str) -> None:
        self._history_area.switch_to_module(tab_title)

    def set_theme(self, theme: str) -> None:
        self._nav_panel.set_theme(theme)
        self._history_area.set_theme(theme)

    def _on_splitter_moved(self, pos: int, index: int) -> None:
        """拖到最底部时自动折叠历史区域。"""
        sizes = self._splitter.sizes()
        history_h = sizes[1]
        header_h = 28
        if history_h <= header_h + 10:
            if not self._history_area._collapsed:
                self._history_area.set_collapsed(True)
        elif self._history_area._collapsed:
            self._history_area.set_collapsed(False)

    def _on_history_collapsed(self, collapsed: bool) -> None:
        sizes = self._splitter.sizes()
        total = sum(sizes)
        if collapsed:
            if sizes[1] > 28:
                self._history_saved_height = sizes[1]
            self._splitter.setSizes([total - 28, 28])
        else:
            h = max(self._history_saved_height, total * 35 // 100)
            self._splitter.setSizes([total - h, h])
