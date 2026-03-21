"""左侧导航面板 — 模块页面切换"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class NavPanel(QWidget):
    """左侧导航面板，根据已加载模块动态生成导航按钮。"""

    tab_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("navPanel")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 8, 4, 8)
        self._layout.setSpacing(2)

        self._buttons: list[QPushButton] = []
        self._current_index = -1

        self._layout.addStretch()

    def add_tab_button(self, title: str, icon_text: str = "") -> None:
        """添加一个导航按钮。"""
        btn = QPushButton(f" {icon_text}  {title}" if icon_text else f"  {title}")
        btn.setCheckable(True)
        btn.setObjectName("navButton")
        btn.setMinimumHeight(36)

        index = len(self._buttons)
        btn.clicked.connect(lambda checked, i=index: self._on_clicked(i))

        insert_pos = self._layout.count() - 1
        self._layout.insertWidget(insert_pos, btn)
        self._buttons.append(btn)

        if self._current_index == -1:
            self.select(0)

    def select(self, index: int) -> None:
        """选中指定索引的按钮。"""
        if 0 <= index < len(self._buttons):
            for i, btn in enumerate(self._buttons):
                btn.setChecked(i == index)
            self._current_index = index
            self.tab_selected.emit(index)

    def _on_clicked(self, index: int) -> None:
        self.select(index)
