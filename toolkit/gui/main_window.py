"""主窗口 — 自定义标题栏 + 左侧导航 + 内容区"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QRect, QPoint
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from toolkit.core.adb_manager import AdbManager
from toolkit.gui.base_tab import BaseTab
from toolkit.gui.device_monitor import DeviceMonitor
from toolkit.gui.home_tab import HomeTab
from toolkit.gui.styles import get_theme_stylesheet
from toolkit.gui.widgets.nav_panel import NavPanel
from toolkit.gui.widgets.title_bar import TitleBar

logger = logging.getLogger(__name__)


class MainWindow(QWidget):
    """无边框主窗口，包含自定义标题栏、左侧导航面板和内容堆栈。"""

    def __init__(self, context: dict) -> None:
        super().__init__()
        self.context = context
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMouseTracking(True)
        self.setMinimumSize(1024, 640)
        self.resize(1200, 800)
        self.setObjectName("mainWindow")

        self._current_theme = "dark"
        self._is_maximized = False
        config = context.get("config_manager")
        if config:
            self._current_theme = config.get_theme() or "dark"

        self._resize_margin = 4
        self._resize_edge = 0
        self._resize_start_pos = QPoint()
        self._resize_start_geo = QRect()

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(
            self._resize_margin, self._resize_margin,
            self._resize_margin, self._resize_margin,
        )
        self._root_layout.setSpacing(0)

        self._title_bar = TitleBar(self)
        self._title_bar.minimize_clicked.connect(self.showMinimized)
        self._title_bar.maximize_clicked.connect(self._toggle_maximize)
        self._title_bar.close_clicked.connect(self.close)
        self._title_bar.theme_toggled.connect(self._toggle_theme)
        self._title_bar.llm_settings_requested.connect(self._open_llm_settings)
        self._root_layout.addWidget(self._title_bar)

        self._nav_panel = NavPanel(self)
        self._nav_panel.tab_selected.connect(self._on_tab_selected)
        self._nav_panel.setMinimumWidth(120)
        self._nav_panel.setMaximumWidth(300)

        self._content_stack = QStackedWidget()

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("bodySplitter")
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._nav_panel)
        self._splitter.addWidget(self._content_stack)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([180, 1020])
        self._splitter.setHandleWidth(2)

        self._root_layout.addWidget(self._splitter)

        self._status_bar = QWidget()
        self._status_bar.setObjectName("statusBar")
        self._status_bar.setFixedHeight(24)
        sb_layout = QHBoxLayout(self._status_bar)
        sb_layout.setContentsMargins(12, 0, 12, 0)
        sb_layout.setSpacing(12)

        self._status_text = QLabel("就绪")
        self._status_text.setObjectName("statusBarText")
        sb_layout.addWidget(self._status_text)

        sb_layout.addStretch()

        llm_manager = context.get("llm_manager")
        if llm_manager:
            from toolkit.gui.widgets.llm_status_widget import LLMStatusWidget

            self._llm_status = LLMStatusWidget(llm_manager, self)
            sb_layout.addWidget(self._llm_status)

            if hasattr(llm_manager, "budget_alert"):
                llm_manager.budget_alert.connect(self._on_budget_alert)
            if hasattr(llm_manager, "degradation_occurred"):
                llm_manager.degradation_occurred.connect(self._on_degradation)
        else:
            self._llm_status = None

        from toolkit import __version__
        self._status_version = QLabel(f"v{__version__}")
        self._status_version.setObjectName("statusBarText")
        sb_layout.addWidget(self._status_version)

        self._root_layout.addWidget(self._status_bar)

        adb_path_val = ""
        if config and hasattr(config, "get_adb_path"):
            adb_path_val = config.get_adb_path()

        self._adb_manager = AdbManager(adb_path_val)
        self._device_monitor = DeviceMonitor(self._adb_manager, parent=self)
        self._device_monitor.devices_changed.connect(self._title_bar.update_devices)
        self._device_monitor.devices_changed.connect(self._on_devices_changed)

        self._tabs: list[BaseTab] = []
        self._devices: list[str] = []

        self._home_tab = HomeTab(context, self)
        self.add_tab(self._home_tab)

        event_bus = context.get("event_bus")
        if event_bus:
            event_bus.on("device_disguise.state_changed", self._on_disguise_state_changed)

        self._apply_theme()

    def add_tab(self, tab: BaseTab) -> None:
        """添加一个模块页面到内容区。"""
        self._tabs.append(tab)
        self._content_stack.addWidget(tab)
        self._nav_panel.add_tab_button(tab.tab_title, tab.tab_icon)
        logger.info("注册 GUI Tab: %s", tab.tab_title)

    def set_module_info(self, modules: list[dict]) -> None:
        """设置已加载模块信息，更新首页。"""
        self._home_tab.update_modules_list(modules)
        self._home_tab.update_status(
            self._devices, len(modules), self._current_theme,
        )

    def show(self) -> None:
        super().show()
        self._device_monitor.start()

    def closeEvent(self, event) -> None:
        self._device_monitor.stop()
        super().closeEvent(event)

    def _on_tab_selected(self, index: int) -> None:
        if 0 <= index < len(self._tabs):
            old_index = self._content_stack.currentIndex()
            if 0 <= old_index < len(self._tabs):
                self._tabs[old_index].on_deactivated()
            self._content_stack.setCurrentIndex(index)
            self._tabs[index].on_activated()

    def _on_devices_changed(self, devices: list[str]) -> None:
        self._devices = devices
        pm = self.context.get("plugin_manager")
        module_count = len(pm.loaded_modules) if pm else 0
        self._home_tab.update_status(devices, module_count, self._current_theme)

        for tab in self._tabs:
            tab.on_devices_changed(devices)

        status = f"已连接: {devices[0]}" if len(devices) == 1 else (
            f"{len(devices)} 台设备已连接" if devices else "未连接设备"
        )
        self._status_text.setText(status)

    def _on_disguise_state_changed(self, **kwargs) -> None:
        """设备伪装状态变化时更新状态栏显示"""
        serial = kwargs.get("serial", "")
        is_disguised = kwargs.get("is_disguised", False)
        if serial:
            disguise_info = "已伪装" if is_disguised else "未伪装"
            self._status_text.setText(f"已连接: {serial} ({disguise_info})")

    def _toggle_maximize(self, center_on_cursor: bool = False) -> None:
        if self._is_maximized:
            self._root_layout.setContentsMargins(
                self._resize_margin, self._resize_margin,
                self._resize_margin, self._resize_margin,
            )
            self.showNormal()
            self._is_maximized = False

            if center_on_cursor:
                from PyQt6.QtGui import QCursor
                cursor = QCursor.pos()
                x = cursor.x() - self.width() // 2
                y = cursor.y() - self.height() // 2
                self.move(max(0, x), max(0, y))
        else:
            self._root_layout.setContentsMargins(0, 0, 0, 0)
            self.showMaximized()
            self._is_maximized = True
        self._title_bar.set_maximized(self._is_maximized)

    def _get_edge(self, pos: QPoint) -> int:
        m = self._resize_margin
        w, h = self.width(), self.height()
        edge = 0
        if pos.x() < m:
            edge |= 1
        if pos.x() > w - m:
            edge |= 2
        if pos.y() < m:
            edge |= 4
        if pos.y() > h - m:
            edge |= 8
        return edge

    _EDGE_CURSORS = {
        1: Qt.CursorShape.SizeHorCursor,   2: Qt.CursorShape.SizeHorCursor,
        4: Qt.CursorShape.SizeVerCursor,    8: Qt.CursorShape.SizeVerCursor,
        5: Qt.CursorShape.SizeFDiagCursor,  10: Qt.CursorShape.SizeFDiagCursor,
        6: Qt.CursorShape.SizeBDiagCursor,  9: Qt.CursorShape.SizeBDiagCursor,
    }

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self._is_maximized:
            edge = self._get_edge(event.pos())
            if edge:
                self._resize_edge = edge
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geo = self.geometry()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._resize_edge and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geo = QRect(self._resize_start_geo)
            min_w, min_h = self.minimumWidth(), self.minimumHeight()

            if self._resize_edge & 1:
                new_left = geo.left() + delta.x()
                if geo.right() - new_left < min_w:
                    new_left = geo.right() - min_w
                geo.setLeft(new_left)
            if self._resize_edge & 2:
                new_right = geo.right() + delta.x()
                if new_right - geo.left() < min_w:
                    new_right = geo.left() + min_w
                geo.setRight(new_right)
            if self._resize_edge & 4:
                new_top = geo.top() + delta.y()
                if geo.bottom() - new_top < min_h:
                    new_top = geo.bottom() - min_h
                geo.setTop(new_top)
            if self._resize_edge & 8:
                new_bottom = geo.bottom() + delta.y()
                if new_bottom - geo.top() < min_h:
                    new_bottom = geo.top() + min_h
                geo.setBottom(new_bottom)

            self.setGeometry(geo)
        elif not (event.buttons() & Qt.MouseButton.LeftButton):
            edge = self._get_edge(event.pos())
            cursor = self._EDGE_CURSORS.get(edge)
            self.setCursor(cursor if cursor else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._resize_edge = 0
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._resize_edge:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def _toggle_theme(self) -> None:
        self._current_theme = "light" if self._current_theme == "dark" else "dark"

        config = self.context.get("config_manager")
        if config:
            config.set_theme(self._current_theme)

        self._apply_theme()

        self._title_bar.set_theme(self._current_theme)
        self._home_tab.set_theme(self._current_theme)

        pm = self.context.get("plugin_manager")
        module_count = len(pm.loaded_modules) if pm else 0
        self._home_tab.update_status(self._devices, module_count, self._current_theme)

        logger.info("主题已切换: %s", self._current_theme)

    def _on_budget_alert(self, ratio: float) -> None:
        """Token 预算到达告警阈值。"""
        from PyQt6.QtWidgets import QMessageBox

        pct = int(ratio * 100)
        result = QMessageBox.warning(
            self,
            "Token 预算告警",
            f"当前会话 Token 用量已达预算的 {pct}%。\n\n"
            "是否继续后续请求？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        llm_mgr = self.context.get("llm_manager")
        if llm_mgr and hasattr(llm_mgr, "set_budget_paused"):
            llm_mgr.set_budget_paused(result == QMessageBox.StandardButton.No)

    def _on_degradation(self, from_provider: str, to_provider: str) -> None:
        """LLM Provider 降级通知。"""
        from PyQt6.QtCore import QTimer

        original = self._status_text.text()
        self._status_text.setText(f"⚠ LLM 已降级: {from_provider} → {to_provider}")
        QTimer.singleShot(3000, lambda: self._status_text.setText(original))

    def _open_llm_settings(self) -> None:
        """打开 LLM 模型设置对话框（T018-T020 实现）。"""
        from toolkit.gui.llm_settings_dialog import LLMSettingsDialog

        llm_manager = self.context.get("llm_manager")
        if not llm_manager:
            logger.warning("LLM Manager 未初始化")
            return
        dialog = LLMSettingsDialog(llm_manager, parent=self)
        dialog.exec()

    def _apply_theme(self) -> None:
        """应用主题样式表到整个应用。"""
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_theme_stylesheet(self._current_theme))
