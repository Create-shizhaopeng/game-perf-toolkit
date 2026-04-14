# -*- coding: utf-8 -*-
"""右侧通用面板 — 各模块可注册自定义内容（如历史记录）。

通过 QStackedWidget 管理每个模块的面板内容，
切换 Tab 时自动同步切换面板页面。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class RightPanel(QWidget):
    """右侧面板容器 — 托管各模块注册的右侧 widget。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rightPanel")
        self.setMinimumWidth(250)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        self._placeholder = QLabel("当前模块无右侧面板内容")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setObjectName("rightPanelPlaceholder")
        self._stack.addWidget(self._placeholder)

        self._tab_indices: dict[int, int] = {}

    def register_widget(self, tab_index: int, widget: QWidget) -> None:
        """为指定 Tab 索引注册右侧面板 widget。"""
        stack_index = self._stack.addWidget(widget)
        self._tab_indices[tab_index] = stack_index

    def switch_to_tab(self, tab_index: int) -> None:
        """切换到指定 Tab 对应的面板内容。"""
        stack_index = self._tab_indices.get(tab_index)
        if stack_index is not None:
            self._stack.setCurrentIndex(stack_index)
        else:
            self._stack.setCurrentIndex(0)  # placeholder

    def has_content(self, tab_index: int) -> bool:
        """指定 Tab 是否有注册右侧面板内容。"""
        return tab_index in self._tab_indices

    def set_theme(self, theme: str) -> None:
        for i in range(self._stack.count()):
            w = self._stack.widget(i)
            if hasattr(w, "set_theme"):
                w.set_theme(theme)
