# -*- coding: utf-8 -*-
"""历史记录区域 — 左侧面板下半部分，带可折叠标题栏和模块 Tab 切换。

各模块可通过 BaseTab.history_widget() 注册历史面板内容，
HistoryArea 通过 QTabBar + QStackedWidget 管理切换。
双击标题栏折叠/展开。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)


class _DoubleClickHeader(QWidget):
    """双击触发折叠/展开的标题栏。"""

    double_clicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class HistoryArea(QWidget):
    """可折叠的历史记录区域，托管各模块注册的历史 widget。"""

    collapse_toggled = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("historyArea")
        self.setMinimumHeight(28)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = _DoubleClickHeader()
        header.setObjectName("historyAreaHeader")
        header.setFixedHeight(28)
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.double_clicked.connect(self._toggle_collapse)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 0, 4, 0)
        h_layout.setSpacing(4)

        title = QLabel("历史记录")
        title.setObjectName("historyAreaTitle")
        h_layout.addWidget(title)

        h_layout.addStretch()
        root.addWidget(header)

        self._tab_bar = QTabBar()
        self._tab_bar.setObjectName("historyTabBar")
        self._tab_bar.setDrawBase(False)
        self._tab_bar.setExpanding(False)
        self._tab_bar.setUsesScrollButtons(False)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tab_bar)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        self._placeholder = QLabel("暂无历史记录")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setObjectName("historyPlaceholder")
        self._stack.addWidget(self._placeholder)

        self._module_map: dict[str, int] = {}
        self._collapsed = False

    def register_history(self, tab_title: str, widget: QWidget) -> None:
        """为指定模块注册历史 widget。"""
        stack_idx = self._stack.addWidget(widget)
        tab_idx = self._tab_bar.addTab(tab_title)
        self._module_map[tab_title] = stack_idx

        if self._tab_bar.count() == 1:
            self._tab_bar.setCurrentIndex(tab_idx)
            self._stack.setCurrentIndex(stack_idx)

    def switch_to_module(self, tab_title: str) -> None:
        """切换到指定模块的历史页面。"""
        stack_idx = self._module_map.get(tab_title)
        if stack_idx is not None:
            for i in range(self._tab_bar.count()):
                if self._tab_bar.tabText(i) == tab_title:
                    self._tab_bar.setCurrentIndex(i)
                    break

    def has_module(self, tab_title: str) -> bool:
        return tab_title in self._module_map

    def set_collapsed(self, collapsed: bool) -> None:
        """外部控制折叠/展开。"""
        self._collapsed = collapsed
        self._tab_bar.setVisible(not collapsed)
        self._stack.setVisible(not collapsed)
        self.collapse_toggled.emit(collapsed)

    def set_theme(self, theme: str) -> None:
        for i in range(self._stack.count()):
            w = self._stack.widget(i)
            if hasattr(w, "set_theme"):
                w.set_theme(theme)

    def _on_tab_changed(self, index: int) -> None:
        text = self._tab_bar.tabText(index)
        stack_idx = self._module_map.get(text)
        if stack_idx is not None:
            self._stack.setCurrentIndex(stack_idx)
        else:
            self._stack.setCurrentIndex(0)

    def _toggle_collapse(self) -> None:
        self.set_collapsed(not self._collapsed)
