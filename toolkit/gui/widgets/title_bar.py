"""自定义标题栏 — Logo + 设备选择器(居中) + 状态灯 + 设置 + 窗口控制

窗口控制按钮和设置按钮使用 Codicons 字体图标（VS Code 官方图标集）。
"""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QEvent
from PyQt6.QtGui import QPainter, QColor, QFont, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QWidget,
)

from toolkit.gui.codicons import codicon_font, icon_char
from toolkit.gui import strings as s


_LOGO_STYLES = {
    "dual_color": {
        "dark": {"t": "#3B82F6", "s": "#60A5FA", "dot": "#3B82F6", "gt": "#6B7280"},
        "light": {"t": "#2563EB", "s": "#3B82F6", "dot": "#2563EB", "gt": "#6B7280"},
    },
    "underline": {
        "dark": {"ts": "#E2E8F0", "bar": "#3B82F6", "gt": "#6B7280"},
        "light": {"ts": "#1E293B", "bar": "#2563EB", "gt": "#6B7280"},
    },
    "gradient_weight": {
        "dark": {"t": "#F8FAFC", "s": "#94A3B8", "gt": "#4B5563"},
        "light": {"t": "#0F172A", "s": "#475569", "gt": "#6B7280"},
    },
}


class LogoWidget(QWidget):
    """矢量 Logo — TS 纯文字设计 + GT 后缀。

    支持三种风格:
    - dual_color: T/S 双色分体
    - underline: TS 整体 + 底部彩色横线
    - gradient_weight: T 粗 S 细 字重渐变
    """

    def __init__(self, style: str = "dual_color", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(100, 30)
        self._style = style
        self._theme = "dark"

    def set_style(self, style: str) -> None:
        self._style = style
        self.update()

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        scheme = _LOGO_STYLES.get(self._style, _LOGO_STYLES["dual_color"])
        c = scheme[self._theme]

        if self._style == "dual_color":
            self._paint_dual_color(p, c)
        elif self._style == "underline":
            self._paint_underline(p, c)
        elif self._style == "gradient_weight":
            self._paint_gradient_weight(p, c)

        p.end()

    def _paint_dual_color(self, p: QPainter, c: dict) -> None:
        """T/S 双色紧凑排列 + 分隔点 + GT"""
        f_bold = QFont("Consolas", 13)
        f_bold.setBold(True)
        fm = p.fontMetrics()

        p.setFont(f_bold)
        p.setPen(QColor(c["t"]))
        t_w = fm.horizontalAdvance("T")
        p.drawText(QRectF(6, 0, t_w, 30), Qt.AlignmentFlag.AlignCenter, "T")

        p.setPen(QColor(c["s"]))
        p.drawText(QRectF(6 + t_w + 2, 0, t_w, 30), Qt.AlignmentFlag.AlignCenter, "S")

        dot_x = 6 + t_w * 2 + 2 + 6
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(c["dot"]))
        p.drawEllipse(QPointF(dot_x, 15), 2, 2)

        f_gt = QFont("Segoe UI", 9)
        f_gt.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        p.setFont(f_gt)
        p.setPen(QColor(c["gt"]))
        p.drawText(QRectF(dot_x + 6, 0, 50, 30), Qt.AlignmentFlag.AlignVCenter, "GT")

    def _paint_underline(self, p: QPainter, c: dict) -> None:
        """TS 整体 + 底部彩色强调线 + GT"""
        f_ts = QFont("Consolas", 13)
        f_ts.setBold(True)

        p.setFont(f_ts)
        p.setPen(QColor(c["ts"]))
        p.drawText(QRectF(6, -1, 30, 28), Qt.AlignmentFlag.AlignCenter, "TS")

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(c["bar"]))
        p.drawRoundedRect(QRectF(8, 24, 26, 2.5), 1.2, 1.2)

        f_gt = QFont("Segoe UI", 9)
        f_gt.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        p.setFont(f_gt)
        p.setPen(QColor(c["gt"]))
        p.drawText(QRectF(40, 0, 50, 30), Qt.AlignmentFlag.AlignVCenter, "GT")

    def _paint_gradient_weight(self, p: QPainter, c: dict) -> None:
        """T 粗 S 细 字重对比 + GT"""
        f_t = QFont("Consolas", 14)
        f_t.setBold(True)

        p.setFont(f_t)
        p.setPen(QColor(c["t"]))
        p.drawText(QRectF(6, 0, 16, 30), Qt.AlignmentFlag.AlignCenter, "T")

        f_s = QFont("Consolas", 12)
        f_s.setWeight(QFont.Weight.Normal)
        p.setFont(f_s)
        p.setPen(QColor(c["s"]))
        p.drawText(QRectF(21, 1, 14, 30), Qt.AlignmentFlag.AlignCenter, "S")

        f_gt = QFont("Segoe UI", 9)
        f_gt.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        p.setFont(f_gt)
        p.setPen(QColor(c["gt"]))
        p.drawText(QRectF(40, 0, 50, 30), Qt.AlignmentFlag.AlignVCenter, "GT")


class ThemeButton(QPushButton):
    """矢量极简主题指示按钮 — 暗色模式显示月亮，亮色模式显示太阳。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 28)
        self.setObjectName("themeBtn")
        self.setToolTip(s.TITLEBAR_TOOLTIP_THEME)
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


class _CodiconButton(QPushButton):
    """Codicons 字体图标按钮 — 统一基类。"""

    def __init__(
        self,
        icon_name: str,
        obj_name: str,
        size: tuple[int, int] = (46, 30),
        font_size: int = 14,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._icon_char = icon_char(icon_name)
        self._font_size = font_size
        self.setFixedSize(*size)
        self.setObjectName(obj_name)
        self._is_dark = True
        self._fg = QColor("#a6adc8")
        self._fg_hover = QColor("#cdd6f4")
        self._hover_bg = QColor("#313244")
        self._close_mode = icon_name == "chrome-close"

    def set_theme(self, theme: str) -> None:
        self._is_dark = theme == "dark"
        self._fg = QColor("#a6adc8") if self._is_dark else QColor("#444444")
        self._fg_hover = QColor("#cdd6f4") if self._is_dark else QColor("#1a1a1a")
        self._hover_bg = QColor("#313244") if self._is_dark else QColor("#ccd0da")
        self.update()

    def set_maximized(self, maximized: bool) -> None:
        if maximized:
            self._icon_char = icon_char("chrome-restore")
        else:
            self._icon_char = icon_char("chrome-maximize")
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        hovered = self.underMouse()
        if self._close_mode and hovered:
            p.fillRect(
                self.rect(),
                QColor("#f38ba8") if self._is_dark else QColor("#d20f39"),
            )
            icon_color = QColor("#ffffff")
        elif hovered:
            p.fillRect(self.rect(), self._hover_bg)
            icon_color = self._fg_hover
        else:
            icon_color = self._fg

        font = codicon_font(self._font_size)
        if font:
            p.setPen(icon_color)
            p.setFont(font)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._icon_char)
        else:
            p.setPen(QPen(icon_color, 1.0))
            cx, cy = self.width() / 2, self.height() / 2
            if self._icon_name == "chrome-minimize":
                p.drawLine(QPointF(cx - 5, cy), QPointF(cx + 5, cy))
            elif self._icon_name in ("chrome-maximize", "chrome-restore"):
                p.drawRect(int(cx - 5), int(cy - 4), 10, 9)
            elif self._icon_name == "chrome-close":
                p.drawLine(QPointF(cx - 5, cy - 4), QPointF(cx + 5, cy + 4))
                p.drawLine(QPointF(cx + 5, cy - 4), QPointF(cx - 5, cy + 4))

        p.end()


class SettingsButton(QPushButton):
    """Codicons 齿轮设置按钮。"""

    theme_toggled = pyqtSignal()
    llm_settings_requested = pyqtSignal()
    agent_settings_requested = pyqtSignal()
    log_export_requested = pyqtSignal()
    log_open_dir_requested = pyqtSignal()
    log_clear_history_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 28)
        self.setObjectName("settingsBtn")
        self.setToolTip(s.TITLEBAR_TOOLTIP_SETTINGS)
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

        theme_action = menu.addAction(s.TITLEBAR_MENU_THEME)
        theme_action.triggered.connect(self.theme_toggled.emit)

        llm_action = menu.addAction(s.TITLEBAR_MENU_LLM_SETTINGS)
        llm_action.triggered.connect(self.llm_settings_requested.emit)

        agent_action = menu.addAction(s.TITLEBAR_MENU_AGENT_SETTINGS)
        agent_action.triggered.connect(self.agent_settings_requested.emit)

        menu.addSeparator()

        log_menu = QMenu(s.TITLEBAR_MENU_LOG, menu)
        log_menu.setObjectName("logSubMenu")

        export_action = log_menu.addAction(s.TITLEBAR_MENU_LOG_EXPORT)
        export_action.triggered.connect(self.log_export_requested.emit)

        open_dir_action = log_menu.addAction(s.TITLEBAR_MENU_LOG_OPEN_DIR)
        open_dir_action.triggered.connect(self.log_open_dir_requested.emit)

        clear_action = log_menu.addAction(s.TITLEBAR_MENU_LOG_CLEAR_HISTORY)
        clear_action.triggered.connect(self.log_clear_history_requested.emit)

        menu.addMenu(log_menu)

        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.underMouse():
            p.fillRect(self.rect(), self._hover_bg)

        font = codicon_font(10)
        if font:
            p.setPen(self._fg)
            p.setFont(font)
            p.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, icon_char("settings-gear")
            )
        else:
            from PyQt6.QtGui import QPainterPath

            cx = self.width() / 2
            cy = self.height() / 2
            p.setPen(QPen(self._fg, 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            teeth = 8
            r_outer, r_inner, r_center = 8.0, 5.5, 2.5
            path = QPainterPath()
            for i in range(teeth * 2):
                angle = math.radians(i * (360 / (teeth * 2)) - 90)
                r = r_outer if i % 2 == 0 else r_inner
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            path.closeSubpath()
            p.drawPath(path)
            p.drawEllipse(QPointF(cx, cy), r_center, r_center)

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
        self.lineEdit().setPlaceholderText(s.TITLEBAR_NO_DEVICE)
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


class _LayoutToggleButton(_CodiconButton):
    """布局面板切换按钮 — 带激活态的 Codicon 按钮。"""

    def __init__(
        self,
        icon_on: str,
        icon_off: str,
        obj_name: str,
        tooltip: str,
        active: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(icon_on, obj_name, size=(36, 28), font_size=10, parent=parent)
        self._icon_on = icon_on
        self._icon_off = icon_off
        self._active = active
        self.setToolTip(tooltip)
        self._update_icon()
        self.clicked.connect(self._toggle)

    def _toggle(self) -> None:
        self._active = not self._active
        self._update_icon()

    def _update_icon(self) -> None:
        name = self._icon_on if self._active else self._icon_off
        self._icon_char = icon_char(name)
        self.update()

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        self._active = value
        self._update_icon()


class TitleBar(QWidget):
    """自定义标题栏，VS Code 风格。

    布局：[Logo] --- [设备选择器(绝对居中)] --- [面板切换x3] [设置] [最小化] [最大化] [关闭]
    """

    minimize_clicked = pyqtSignal()
    maximize_clicked = pyqtSignal()
    close_clicked = pyqtSignal()
    device_selected = pyqtSignal(list)
    theme_toggled = pyqtSignal()
    llm_settings_requested = pyqtSignal()
    agent_settings_requested = pyqtSignal()
    toggle_nav_panel = pyqtSignal(bool)
    toggle_bottom_panel = pyqtSignal(bool)
    toggle_right_panel = pyqtSignal(bool)
    log_export_requested = pyqtSignal()
    log_open_dir_requested = pyqtSignal()
    log_clear_history_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setObjectName("titleBar")
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(0)

        self._logo = LogoWidget(style="dual_color", parent=self)
        layout.addWidget(self._logo)

        layout.addStretch(1)

        self._nav_toggle = _LayoutToggleButton(
            "layout-sidebar-left", "layout-sidebar-left-off",
            "navToggleBtn", s.TITLEBAR_NAV_PANEL, active=True, parent=self,
        )
        self._nav_toggle.clicked.connect(
            lambda: self.toggle_nav_panel.emit(self._nav_toggle.active)
        )
        layout.addWidget(self._nav_toggle)

        self._bottom_toggle = _LayoutToggleButton(
            "layout-panel", "layout-panel-off",
            "bottomToggleBtn", s.TITLEBAR_BOTTOM_PANEL, active=False, parent=self,
        )
        self._bottom_toggle.clicked.connect(
            lambda: self.toggle_bottom_panel.emit(self._bottom_toggle.active)
        )
        layout.addWidget(self._bottom_toggle)

        self._right_toggle = _LayoutToggleButton(
            "layout-sidebar-right", "layout-sidebar-right-off",
            "rightToggleBtn", s.TITLEBAR_RIGHT_PANEL, active=False, parent=self,
        )
        self._right_toggle.clicked.connect(
            lambda: self.toggle_right_panel.emit(self._right_toggle.active)
        )
        layout.addWidget(self._right_toggle)

        self._settings_btn = SettingsButton(self)
        self._settings_btn.theme_toggled.connect(self.theme_toggled.emit)
        self._settings_btn.llm_settings_requested.connect(
            self.llm_settings_requested.emit
        )
        self._settings_btn.agent_settings_requested.connect(
            self.agent_settings_requested.emit
        )
        self._settings_btn.log_export_requested.connect(
            self.log_export_requested.emit
        )
        self._settings_btn.log_open_dir_requested.connect(
            self.log_open_dir_requested.emit
        )
        self._settings_btn.log_clear_history_requested.connect(
            self.log_clear_history_requested.emit
        )
        layout.addWidget(self._settings_btn)

        self._ctrl_btns: list[_CodiconButton] = []
        for icon_name, signal, obj_name in [
            ("chrome-minimize", self.minimize_clicked, "minBtn"),
            ("chrome-maximize", self.maximize_clicked, "maxBtn"),
            ("chrome-close", self.close_clicked, "closeBtn"),
        ]:
            btn = _CodiconButton(icon_name, obj_name, size=(46, 30), font_size=10, parent=self)
            btn.clicked.connect(signal.emit)
            layout.addWidget(btn)
            self._ctrl_btns.append(btn)

        # DeviceCombo 不加入 layout，使用绝对定位确保水平居中
        self._device_combo = DeviceComboBox(self)
        self._device_combo.setFixedHeight(22)
        self._device_combo.setFixedWidth(200)
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)

        self._devices: list[str] = []
        self._update_status([])

    def set_theme(self, theme: str) -> None:
        """通知所有子组件切换主题配色。"""
        self._logo.set_theme(theme)
        self._nav_toggle.set_theme(theme)
        self._bottom_toggle.set_theme(theme)
        self._right_toggle.set_theme(theme)
        self._settings_btn.set_theme(theme)
        for btn in self._ctrl_btns:
            btn.set_theme(theme)

    def set_maximized(self, maximized: bool) -> None:
        """更新最大化按钮图标。"""
        for btn in self._ctrl_btns:
            if btn._icon_name == "chrome-maximize":
                btn.set_maximized(maximized)

    def set_panel_active(self, panel: str, active: bool) -> None:
        """外部同步面板按钮状态（如自动弹出时）。"""
        btn_map = {
            "nav": self._nav_toggle,
            "bottom": self._bottom_toggle,
            "right": self._right_toggle,
        }
        btn = btn_map.get(panel)
        if btn:
            btn.active = active

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        combo_w = self._device_combo.width()
        x = (self.width() - combo_w) // 2
        y = (self.height() - self._device_combo.height()) // 2
        self._device_combo.move(x, y)
        self._device_combo.raise_()

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
            self._device_combo.setPlaceholderText(s.TITLEBAR_NO_DEVICE)
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
            self._device_combo.setToolTip(s.TITLEBAR_NO_DEVICE)
        elif len(devices) == 1:
            self._device_combo.set_dot_color("#2ecc71")
            self._device_combo.setToolTip(s.TITLEBAR_CONNECTED_FMT.format(device=devices[0]))
        else:
            self._device_combo.set_dot_color("#3498db")
            self._device_combo.setToolTip(s.TITLEBAR_DEVICES_CONNECTED_FMT.format(count=len(devices)))

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
