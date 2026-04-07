"""自定义标题栏 — Logo + 设备选择器(居中) + 状态灯 + 设置 + 窗口控制"""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QEvent
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QWidget,
)


class LogoWidget(QWidget):
    """矢量 Logo — 菱形图标 + LVGT 文字，自动适配主题。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(110, 30)
        self._accent = QColor("#cba6f7")
        self._bg = QColor("#1e1e2e")

    def set_theme(self, theme: str) -> None:
        self._accent = QColor("#cba6f7") if theme == "dark" else QColor("#8839ef")
        self._bg = QColor("#1e1e2e") if theme == "dark" else QColor("#e6e9ef")
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = 15, 15
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._accent)
        diamond = QPolygonF([
            QPointF(cx, cy - 10), QPointF(cx + 10, cy),
            QPointF(cx, cy + 10), QPointF(cx - 10, cy),
        ])
        p.drawPolygon(diamond)

        p.setBrush(self._bg)
        p.drawEllipse(QPointF(cx, cy), 3.5, 3.5)

        inner_pen = QPen(self._bg, 1.2)
        p.setPen(inner_pen)
        p.drawLine(QPointF(cx - 2, cy), QPointF(cx + 2, cy))
        p.drawLine(QPointF(cx, cy - 2), QPointF(cx, cy + 2))

        p.setPen(self._accent)
        f = QFont("Segoe UI", 11)
        f.setBold(True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        p.setFont(f)
        p.drawText(30, 0, 80, 30, Qt.AlignmentFlag.AlignVCenter, "LVGT")

        p.end()


class ThemeButton(QPushButton):
    """矢量极简主题指示按钮 — 暗色模式显示月亮，亮色模式显示太阳。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 28)
        self.setObjectName("themeBtn")
        self.setToolTip("切换主题")
        self._is_dark = True
        self._fg = QColor("#a6adc8")
        self._hover_bg = QColor("#313244")

    def set_theme(self, theme: str) -> None:
        self._is_dark = theme == "dark"
        self._fg = QColor("#a6adc8") if self._is_dark else QColor("#444444")
        self._hover_bg = QColor("#313244") if self._is_dark else QColor("#ccd0da")
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.underMouse():
            p.fillRect(self.rect(), self._hover_bg)

        cx = self.width() / 2
        cy = self.height() / 2
        pen = QPen(self._fg, 1.2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        if self._is_dark:
            p.drawArc(QRectF(cx - 5, cy - 5, 10, 10), 45 * 16, 270 * 16)
            p.drawEllipse(QPointF(cx + 1.5, cy - 2.5), 3.5, 3.5)
        else:
            p.drawEllipse(QPointF(cx, cy), 4, 4)
            for i in range(8):
                angle = math.radians(i * 45)
                x1 = cx + 6 * math.cos(angle)
                y1 = cy + 6 * math.sin(angle)
                x2 = cx + 8 * math.cos(angle)
                y2 = cy + 8 * math.sin(angle)
                p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        p.end()


class SettingsButton(QPushButton):
    """齿轮设置按钮 — 点击弹出设置菜单（主题切换、LLM 设置）。"""

    theme_toggled = pyqtSignal()
    llm_settings_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 28)
        self.setObjectName("settingsBtn")
        self.setToolTip("设置")
        self._is_dark = True
        self._fg = QColor("#a6adc8")
        self._hover_bg = QColor("#313244")
        self.clicked.connect(self._show_menu)

    def set_theme(self, theme: str) -> None:
        self._is_dark = theme == "dark"
        self._fg = QColor("#a6adc8") if self._is_dark else QColor("#444444")
        self._hover_bg = QColor("#313244") if self._is_dark else QColor("#ccd0da")
        self.update()

    def _show_menu(self) -> None:
        menu = QMenu(self)
        menu.setObjectName("settingsMenu")

        theme_action = menu.addAction("主题切换")
        theme_action.triggered.connect(self.theme_toggled.emit)

        llm_action = menu.addAction("LLM 模型设置")
        llm_action.triggered.connect(self.llm_settings_requested.emit)

        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.underMouse():
            p.fillRect(self.rect(), self._hover_bg)

        cx = self.width() / 2
        cy = self.height() / 2
        pen = QPen(self._fg, 1.2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        r_outer = 7.0
        r_inner = 4.5
        r_tooth = 2.0
        teeth = 6
        for i in range(teeth):
            angle = math.radians(i * (360 / teeth))
            x = cx + r_outer * math.cos(angle)
            y = cy + r_outer * math.sin(angle)
            p.drawEllipse(QPointF(x, y), r_tooth, r_tooth)

        p.drawEllipse(QPointF(cx, cy), r_inner, r_inner)
        p.drawEllipse(QPointF(cx, cy), 2.0, 2.0)

        p.end()


class DeviceComboBox(QComboBox):
    """自定义设备选择器 — 左侧绘制状态指示灯，文字居中，点击任意位置弹出下拉。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dot_color = QColor("#e74c3c")
        self.setObjectName("deviceCombo")
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit().setPlaceholderText("未连接设备")
        self.lineEdit().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.lineEdit() and event.type() == QEvent.Type.MouseButtonPress:
            self.showPopup()
            return True
        return super().eventFilter(obj, event)

    def set_dot_color(self, color: str) -> None:
        self._dot_color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._dot_color)
        dot_y = self.height() / 2
        p.drawEllipse(QPointF(10, dot_y), 3.5, 3.5)

        p.end()


class WinCtrlButton(QPushButton):
    """VS Code 风格的窗口控制按钮（统一 46x30）。"""

    def __init__(self, icon_type: str, obj_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_type = icon_type
        self.setFixedSize(46, 30)
        self.setObjectName(obj_name)
        self._is_dark = True
        self._is_maximized = False
        self._fg = QColor("#a6adc8")
        self._fg_hover = QColor("#cdd6f4")
        self._hover_bg = QColor("#313244")

    def set_theme(self, theme: str) -> None:
        self._is_dark = theme == "dark"
        self._fg = QColor("#a6adc8") if self._is_dark else QColor("#444444")
        self._fg_hover = QColor("#cdd6f4") if self._is_dark else QColor("#1a1a1a")
        self._hover_bg = QColor("#313244") if self._is_dark else QColor("#ccd0da")
        self.update()

    def set_maximized(self, maximized: bool) -> None:
        self._is_maximized = maximized
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        hovered = self.underMouse()
        if self._icon_type == "close" and hovered:
            p.fillRect(self.rect(), QColor("#f38ba8") if self._is_dark else QColor("#d20f39"))
        elif hovered:
            p.fillRect(self.rect(), self._hover_bg)

        if self._icon_type == "close" and hovered:
            icon_color = QColor("#ffffff")
        elif hovered:
            icon_color = self._fg_hover
        else:
            icon_color = self._fg

        pen = QPen(icon_color, 1.0)
        p.setPen(pen)

        cx = self.width() / 2
        cy = self.height() / 2

        if self._icon_type == "minimize":
            p.drawLine(QPointF(cx - 5, cy), QPointF(cx + 5, cy))
        elif self._icon_type == "maximize":
            if self._is_maximized:
                p.drawRect(int(cx - 3), int(cy - 5), 8, 7)
                p.drawRect(int(cx - 5), int(cy - 3), 8, 7)
            else:
                p.drawRect(int(cx - 5), int(cy - 4), 10, 9)
        elif self._icon_type == "close":
            p.drawLine(QPointF(cx - 5, cy - 4), QPointF(cx + 5, cy + 4))
            p.drawLine(QPointF(cx + 5, cy - 4), QPointF(cx - 5, cy + 4))

        p.end()


class TitleBar(QWidget):
    """自定义标题栏，VS Code 风格。

    布局：[Logo] --- [设备选择器] [状态灯] --- [主题切换] [最小化] [最大化] [关闭]
    """

    minimize_clicked = pyqtSignal()
    maximize_clicked = pyqtSignal()
    close_clicked = pyqtSignal()
    device_selected = pyqtSignal(list)
    theme_toggled = pyqtSignal()
    llm_settings_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setObjectName("titleBar")
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(0)

        self._logo = LogoWidget(self)
        layout.addWidget(self._logo)

        layout.addStretch(1)

        self._device_combo = DeviceComboBox(self)
        self._device_combo.setFixedHeight(22)
        self._device_combo.setFixedWidth(200)
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        layout.addWidget(self._device_combo)

        layout.addStretch(1)

        self._settings_btn = SettingsButton(self)
        self._settings_btn.theme_toggled.connect(self.theme_toggled.emit)
        self._settings_btn.llm_settings_requested.connect(
            self.llm_settings_requested.emit
        )
        layout.addWidget(self._settings_btn)

        self._ctrl_btns: list[WinCtrlButton] = []
        for icon_type, signal, obj_name in [
            ("minimize", self.minimize_clicked, "minBtn"),
            ("maximize", self.maximize_clicked, "maxBtn"),
            ("close", self.close_clicked, "closeBtn"),
        ]:
            btn = WinCtrlButton(icon_type, obj_name, self)
            btn.clicked.connect(signal.emit)
            layout.addWidget(btn)
            self._ctrl_btns.append(btn)

        self._devices: list[str] = []
        self._update_status([])

    def set_theme(self, theme: str) -> None:
        """通知所有子组件切换主题配色。"""
        self._logo.set_theme(theme)
        self._settings_btn.set_theme(theme)
        for btn in self._ctrl_btns:
            btn.set_theme(theme)

    def set_maximized(self, maximized: bool) -> None:
        """更新最大化按钮图标。"""
        for btn in self._ctrl_btns:
            if btn._icon_type == "maximize":
                btn.set_maximized(maximized)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            win = self.window()
            if hasattr(win, '_toggle_maximize'):
                win._toggle_maximize(center_on_cursor=True)
            else:
                self.maximize_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def update_devices(self, devices: list[str]) -> None:
        """更新设备列表。"""
        self._devices = devices
        self._device_combo.blockSignals(True)
        current = self._device_combo.currentText()
        self._device_combo.clear()

        if not devices:
            self._device_combo.setPlaceholderText("未连接设备")
        elif len(devices) == 1:
            self._device_combo.addItem(devices[0])
            self._device_combo.setCurrentIndex(0)
        else:
            self._device_combo.addItems(devices)
            if current in devices:
                self._device_combo.setCurrentText(current)
            else:
                self._device_combo.setCurrentIndex(0)

        self._device_combo.blockSignals(False)
        self._update_status(devices)

    def _update_status(self, devices: list[str]) -> None:
        """更新状态指示灯颜色。"""
        if not devices:
            self._device_combo.set_dot_color("#e74c3c")
            self._device_combo.setToolTip("未连接设备")
        elif len(devices) == 1:
            self._device_combo.set_dot_color("#2ecc71")
            self._device_combo.setToolTip(f"已连接: {devices[0]}")
        else:
            self._device_combo.set_dot_color("#3498db")
            self._device_combo.setToolTip(f"{len(devices)} 台设备已连接")

    def _on_device_changed(self, index: int) -> None:
        if index >= 0:
            self.device_selected.emit([self._device_combo.currentText()])

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            self._drag_started = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            win = self.window()
            if hasattr(win, '_is_maximized') and win._is_maximized:
                if not self._drag_started:
                    self._drag_started = True
                    ratio = event.pos().x() / self.width()
                    win._toggle_maximize()
                    new_x = int(win.width() * ratio)
                    self._drag_pos = event.globalPosition().toPoint() - win.frameGeometry().topLeft()
                    self._drag_pos.setX(new_x)
            win.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)
