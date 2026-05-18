# -*- coding: utf-8 -*-
"""右侧面板 — Agent Chat 专用容器（Overlay 模式）。

以覆盖层形式浮在中间内容区上方，不压缩中间内容。
左边缘可拖拽调整宽度。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget


class _ResizeHandle(QWidget):
    """左边缘拖拽手柄，用于调整右侧面板宽度。"""

    width_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(5)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setObjectName("rightPanelResizeHandle")
        self._dragging = False
        self._start_global_x = 0
        self._start_panel_width = 0

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_global_x = event.globalPosition().toPoint().x()
            p = self.parent()
            self._start_panel_width = p.width() if p else 280
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            dx = self._start_global_x - event.globalPosition().toPoint().x()
            new_width = self._start_panel_width + dx
            self.width_changed.emit(new_width)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False
        super().mouseReleaseEvent(event)


class RightPanel(QWidget):
    """右侧面板 — Agent Chat 专用容器（Overlay 模式）。"""

    resize_requested = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rightPanel")
        self.setMinimumWidth(280)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._resize_handle = _ResizeHandle(self)
        self._resize_handle.width_changed.connect(self.resize_requested.emit)
        outer.addWidget(self._resize_handle)

        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        outer.addWidget(self._content, 1)

        self._agent_widget: QWidget | None = None

    def set_agent_widget(self, widget: QWidget) -> None:
        """设置 Agent Chat widget 为面板内容。"""
        layout = self._content.layout()
        if self._agent_widget is not None:
            layout.removeWidget(self._agent_widget)
        self._agent_widget = widget
        layout.addWidget(widget)

    def set_theme(self, theme: str) -> None:
        if self._agent_widget and hasattr(self._agent_widget, "set_theme"):
            self._agent_widget.set_theme(theme)
