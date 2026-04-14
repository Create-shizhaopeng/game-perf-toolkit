"""左侧导航面板 — 模块页面切换

使用 Codicons 字体图标替代 Emoji。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.codicons import codicon_font, icon_char

# tab_icon (emoji) → codicon name 映射
_ICON_MAP: dict[str, str] = {
    "🏠": "home",
    "🔍": "search",
    "📊": "graph-line",
    "📈": "pulse",
    "🤖": "robot",
    "💬": "comment-discussion",
    "📱": "device-mobile",
    "🔧": "tools",
    "⚙": "gear",
    "⚙️": "gear",
    "🎮": "play",
    "🛡": "shield",
    "🛡️": "shield",
    "📋": "dashboard",
    "📄": "file-code",
    "📂": "folder",
    "🔬": "beaker",
    "🏷": "record",
    "🎭": "wand",
    "🧰": "git-compare",
}


class _NavButton(QPushButton):
    """导航按钮 — Codicons 图标 + 文字。"""

    def __init__(self, title: str, icon_text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._codicon_name = _ICON_MAP.get(icon_text, "")
        self._icon_text = icon_text
        self.setCheckable(True)
        self.setObjectName("navButton")
        self.setMinimumHeight(36)
        self._is_dark = True

        if self._codicon_name:
            self.setText(f"        {title}")
        else:
            self.setText(f" {icon_text}   {title}" if icon_text else f"  {title}")

    def set_theme(self, theme: str) -> None:
        self._is_dark = theme == "dark"
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._codicon_name:
            return

        font = codicon_font(14)
        if not font:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.isChecked():
            icon_color = QColor("#cba6f7") if self._is_dark else QColor("#8839ef")
        else:
            icon_color = QColor("#bac2de") if self._is_dark else QColor("#444444")

        p.setPen(icon_color)
        p.setFont(font)
        p.drawText(12, 0, 20, self.height(), Qt.AlignmentFlag.AlignVCenter, icon_char(self._codicon_name))
        p.end()


class NavPanel(QWidget):
    """左侧导航面板，根据已加载模块动态生成导航按钮。"""

    tab_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("navPanel")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 8, 4, 8)
        self._layout.setSpacing(2)

        self._buttons: list[_NavButton] = []
        self._current_index = -1

        self._layout.addStretch()

    def add_tab_button(self, title: str, icon_text: str = "") -> None:
        """添加一个导航按钮。"""
        btn = _NavButton(title, icon_text)

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

    def set_theme(self, theme: str) -> None:
        """通知所有按钮切换主题。"""
        for btn in self._buttons:
            btn.set_theme(theme)

    def _on_clicked(self, index: int) -> None:
        self.select(index)
