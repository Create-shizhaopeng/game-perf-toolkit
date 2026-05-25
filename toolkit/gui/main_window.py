"""主窗口 — 自定义标题栏 + 左侧面板(导航+历史) + 内容区 + 底部日志 + 右侧Agent(Overlay)"""

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


class _BodyContainer(QWidget):
    """承载主分割器和右侧 Overlay 面板的容器。"""

    def __init__(
        self, splitter: QSplitter, right_panel: QWidget,
        bottom_wrapper: QWidget, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._splitter = splitter
        self._right_panel = right_panel
        self._bottom_wrapper = bottom_wrapper

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(splitter)

        right_panel.setParent(self)
        right_panel.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_overlay()

    def _update_overlay(self) -> None:
        rp = self._right_panel
        if rp.isVisible():
            w = rp.width()
            h = self.height()
            x = self.width() - w
            rp.setGeometry(x, 0, w, h)
            self._bottom_wrapper.setContentsMargins(0, 0, w, 0)
        rp.raise_()

from toolkit.core.adb_manager import AdbManager
from toolkit.gui.base_tab import BaseTab
from toolkit.gui.device_monitor import DeviceMonitor
from toolkit.gui.home_tab import HomeTab
from toolkit.gui.log_manager import LogManager
from toolkit.gui.panels.bottom_panel import BottomPanel
from toolkit.gui.panels.left_panel import LeftPanel
from toolkit.gui.panels.right_panel import RightPanel
from toolkit.gui.styles import get_theme_stylesheet
from toolkit.gui.widgets.title_bar import TitleBar
from toolkit.gui import strings as s

logger = logging.getLogger(__name__)


class MainWindow(QWidget):
    """无边框主窗口，包含自定义标题栏、左侧面板、内容堆栈、底部日志和右侧 Agent。"""

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
        self._intended_size = self.size()

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(
            self._resize_margin, self._resize_margin,
            self._resize_margin, self._resize_margin,
        )
        self._root_layout.setSpacing(0)

        self._log_manager = LogManager(self)
        self.context["log_manager"] = self._log_manager
        self.context["show_right_panel"] = self._show_right_panel
        self.context["hide_right_panel"] = self._hide_right_panel

        self._title_bar = TitleBar(self)
        self._title_bar.minimize_clicked.connect(self.showMinimized)
        self._title_bar.maximize_clicked.connect(self._toggle_maximize)
        self._title_bar.close_clicked.connect(self.close)
        self._title_bar.theme_toggled.connect(self._toggle_theme)
        self._title_bar.llm_settings_requested.connect(self._open_llm_settings)
        self._title_bar.agent_settings_requested.connect(self._open_agent_settings)
        self._title_bar.toggle_nav_panel.connect(self._on_toggle_nav)
        self._title_bar.toggle_bottom_panel.connect(self._on_toggle_bottom)
        self._title_bar.toggle_right_panel.connect(self._on_toggle_right)
        self._root_layout.addWidget(self._title_bar)

        self._left_panel = LeftPanel(self)
        self._left_panel.tab_selected.connect(self._on_tab_selected)
        self._left_panel.setMinimumWidth(48)
        self._left_panel.setMaximumWidth(480)

        self._content_stack = QStackedWidget()
        self._content_stack.setMinimumWidth(300)
        self._content_stack.setMinimumHeight(120)

        self._bottom_panel = BottomPanel(self._log_manager, self)
        self._right_panel = RightPanel(self)

        # 设置菜单日志操作 → 底部面板
        self._title_bar.log_export_requested.connect(self._bottom_panel.export_logs)
        self._title_bar.log_open_dir_requested.connect(self._bottom_panel.open_log_directory)
        self._title_bar.log_clear_history_requested.connect(self._bottom_panel.clear_log_history)

        self._bottom_panel.setMinimumHeight(35)

        self._bottom_wrapper = QWidget()
        self._bottom_wrapper.setObjectName("bottomWrapper")
        bw_layout = QVBoxLayout(self._bottom_wrapper)
        bw_layout.setContentsMargins(0, 0, 0, 0)
        bw_layout.setSpacing(0)
        bw_layout.addWidget(self._bottom_panel)

        self._center_splitter = QSplitter(Qt.Orientation.Vertical)
        self._center_splitter.setObjectName("centerSplitter")
        self._center_splitter.setChildrenCollapsible(False)
        self._center_splitter.addWidget(self._content_stack)
        self._center_splitter.addWidget(self._bottom_wrapper)
        self._center_splitter.setStretchFactor(0, 1)
        self._center_splitter.setStretchFactor(1, 0)
        self._center_splitter.setHandleWidth(4)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("bodySplitter")
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._left_panel)
        self._splitter.addWidget(self._center_splitter)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([180, 1020])
        self._splitter.setHandleWidth(4)

        self._bottom_panel.hide()
        self._bottom_wrapper.hide()
        self._right_panel.hide()
        self._nav_saved_width = 180
        self._bottom_saved_height = 200
        self._right_saved_width = 320

        self._right_panel.resize_requested.connect(self._on_right_resize_requested)

        self._log_manager.error_logged.connect(self._on_error_logged)

        self._body_container = _BodyContainer(
            self._splitter, self._right_panel, self._bottom_wrapper, self,
        )
        self._root_layout.addWidget(self._body_container)

        self._status_bar = QWidget()
        self._status_bar.setObjectName("statusBar")
        self._status_bar.setFixedHeight(24)
        sb_layout = QHBoxLayout(self._status_bar)
        sb_layout.setContentsMargins(12, 0, 12, 0)
        sb_layout.setSpacing(12)

        self._status_text = QLabel(s.MAIN_WINDOW_STATUS_READY)
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
        self._agent_tab: BaseTab | None = None
        self._devices: list[str] = []

        self._home_tab = HomeTab(context, self)
        self.add_tab(self._home_tab)

        event_bus = context.get("event_bus")
        if event_bus:
            event_bus.on("device_disguise.state_changed", self._on_disguise_state_changed)

        self._apply_theme()
        self._title_bar.set_theme(self._current_theme)
        self._left_panel.set_theme(self._current_theme)
        self._home_tab.set_theme(self._current_theme)

    def add_tab(self, tab: BaseTab) -> None:
        """添加一个模块页面到内容区。"""
        tab_index = len(self._tabs)
        self._tabs.append(tab)
        self._content_stack.addWidget(tab)
        self._left_panel.add_tab_button(tab.tab_title, tab.tab_icon)
        tab.set_theme(self._current_theme)

        for title, hw in tab.history_widgets():
            self._left_panel.register_history(title, hw)

        logger.info("注册 GUI Tab: %s", tab.tab_title)

    def set_agent_panel(self, tab: BaseTab) -> None:
        """将 AgentTab 设置为右侧面板内容（不进入 ContentStack）。"""
        self._agent_tab = tab
        tab.set_theme(self._current_theme)
        self._right_panel.set_agent_widget(tab)
        if self._devices:
            tab.on_devices_changed(self._devices)
        logger.info("Agent Chat 已加载到右侧面板")

    def set_module_info(self, modules: list[dict]) -> None:
        """设置已加载模块信息，更新首页。"""
        self._home_tab.update_modules_list(modules)
        self._home_tab.update_status(
            self._devices, len(modules), self._current_theme,
        )

    def show(self) -> None:
        super().show()
        self._device_monitor.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not hasattr(self, "_screen_connected"):
            self._intended_size = self.size()
            win = self.windowHandle()
            if win:
                win.screenChanged.connect(self._on_screen_changed)
                self._screen_connected = True

    def closeEvent(self, event) -> None:
        self._device_monitor.stop()
        super().closeEvent(event)

    def _on_tab_selected(self, index: int) -> None:
        if 0 <= index < len(self._tabs):
            old_index = self._content_stack.currentIndex()
            if 0 <= old_index < len(self._tabs):
                self._tabs[old_index].on_deactivated()
            self._content_stack.setCurrentIndex(index)
            tab = self._tabs[index]
            tab.on_activated()
            hw_list = tab.history_widgets()
            if hw_list:
                self._left_panel.switch_history_to_module(hw_list[0][0])
            else:
                self._left_panel.switch_history_to_module(tab.tab_title)

    def _on_devices_changed(self, devices: list[str]) -> None:
        self._devices = devices
        pm = self.context.get("plugin_manager")
        module_count = len(pm.loaded_modules) if pm else 0
        self._home_tab.update_status(devices, module_count, self._current_theme)

        for tab in self._tabs:
            tab.on_devices_changed(devices)
        if self._agent_tab:
            self._agent_tab.on_devices_changed(devices)

        if len(devices) == 1:
            status = s.MAIN_WINDOW_STATUS_CONNECTED_FMT.format(device=devices[0])
        elif devices:
            status = s.MAIN_WINDOW_STATUS_MULTIPLE_FMT.format(count=len(devices))
        else:
            status = s.MAIN_WINDOW_STATUS_NO_DEVICE
        self._status_text.setText(status)

    def _on_disguise_state_changed(self, **kwargs) -> None:
        """设备伪装状态变化时更新状态栏显示"""
        serial = kwargs.get("serial", "")
        is_disguised = kwargs.get("is_disguised", False)
        if serial:
            disguise_info = (
                s.MAIN_WINDOW_STATUS_DISGUISED
                if is_disguised
                else s.MAIN_WINDOW_STATUS_NOT_DISGUISED
            )
            self._status_text.setText(
                s.MAIN_WINDOW_STATUS_DISGUISED_FMT.format(
                    serial=serial, disguise=disguise_info
                )
            )

    def _toggle_maximize(self, center_on_cursor: bool = False) -> None:
        if self._is_maximized:
            self._root_layout.setContentsMargins(
                self._resize_margin, self._resize_margin,
                self._resize_margin, self._resize_margin,
            )
            self.showNormal()
            self._is_maximized = False
            self._intended_size = self.size()

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
        if self._resize_edge:
            self._intended_size = self.size()
        self._resize_edge = 0
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._resize_edge:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def _on_toggle_nav(self, visible: bool) -> None:
        """切换左侧面板可见性。"""
        if visible:
            self._left_panel.show()
            from PyQt6.QtCore import QTimer
            w = self._nav_saved_width
            QTimer.singleShot(0, lambda: self._apply_nav_size(w))
        else:
            self._nav_saved_width = max(self._splitter.sizes()[0], 120)
            self._left_panel.hide()

    def _apply_nav_size(self, w: int) -> None:
        sizes = self._splitter.sizes()
        total = sum(sizes)
        sizes[0] = w
        sizes[1] = total - w
        self._splitter.setSizes(sizes)

    def _on_toggle_bottom(self, visible: bool) -> None:
        """切换底部日志面板可见性。"""
        if visible:
            self._bottom_panel.show()
            self._bottom_wrapper.show()
            if self._right_panel.isVisible():
                self._bottom_wrapper.setContentsMargins(0, 0, self._right_panel.width(), 0)
            from PyQt6.QtCore import QTimer
            h = self._bottom_saved_height
            QTimer.singleShot(0, lambda: self._apply_bottom_size(h))
        else:
            sizes = self._center_splitter.sizes()
            if sizes[1] > 0:
                self._bottom_saved_height = sizes[1]
            self._bottom_panel.hide()
            self._bottom_wrapper.hide()

    def _apply_bottom_size(self, h: int) -> None:
        sizes = self._center_splitter.sizes()
        total = sum(sizes)
        h = min(h, total * 2 // 3)
        self._center_splitter.setSizes([total - h, h])

    def _on_toggle_right(self, visible: bool) -> None:
        """切换右侧 Agent 面板可见性（Overlay 模式）。"""
        if visible:
            if self._agent_tab:
                self._agent_tab.on_activated()
            self._right_panel.show()
            from PyQt6.QtCore import QTimer
            w = self._right_saved_width
            QTimer.singleShot(0, lambda: self._apply_right_size(w))
        else:
            cur_w = self._right_panel.width()
            if cur_w > 0:
                self._right_saved_width = cur_w
            if self._agent_tab:
                self._agent_tab.on_deactivated()
            self._right_panel.hide()
            self._bottom_wrapper.setContentsMargins(0, 0, 0, 0)

    def _apply_right_size(self, w: int) -> None:
        w = self._clamp_right_width(w)
        container = self._body_container
        h = container.height()
        x = container.width() - w
        self._right_panel.setGeometry(x, 0, w, h)
        self._right_panel.raise_()
        self._bottom_wrapper.setContentsMargins(0, 0, w, 0)

    def _clamp_right_width(self, w: int) -> int:
        """限制右侧面板宽度：最小 280，最大不超过 body - 左侧面板宽度。"""
        container = self._body_container
        left_w = self._splitter.sizes()[0] if self._left_panel.isVisible() else 0
        max_w = container.width() - left_w
        return max(280, min(w, max_w))

    def _on_right_resize_requested(self, new_width: int) -> None:
        """响应右侧面板拖拽手柄的宽度调整请求。"""
        self._apply_right_size(new_width)

    def _show_right_panel(self) -> None:
        """供模块调用：显示右侧面板。"""
        if not self._right_panel.isVisible():
            self._title_bar.set_panel_active("right", True)
            self._on_toggle_right(True)

    def _hide_right_panel(self) -> None:
        """供模块调用：隐藏右侧面板。"""
        if self._right_panel.isVisible():
            self._title_bar.set_panel_active("right", False)
            self._on_toggle_right(False)

    def _on_error_logged(self) -> None:
        """error/warning 日志自动弹出底部面板。"""
        if not self._bottom_panel.isVisible():
            self._title_bar.set_panel_active("bottom", True)
            self._on_toggle_bottom(True)

    def _toggle_theme(self) -> None:
        self._current_theme = "light" if self._current_theme == "dark" else "dark"

        config = self.context.get("config_manager")
        if config:
            config.set_theme(self._current_theme)

        self._apply_theme()
        self._propagate_theme()

        logger.info("主题已切换: %s", self._current_theme)

    def _propagate_theme(self) -> None:
        """将当前主题通知到所有子组件。"""
        theme = self._current_theme
        self._title_bar.set_theme(theme)
        self._left_panel.set_theme(theme)
        self._bottom_panel.set_theme(theme)
        self._right_panel.set_theme(theme)

        for tab in self._tabs:
            tab.set_theme(theme)

        if self._agent_tab:
            self._agent_tab.set_theme(theme)

        pm = self.context.get("plugin_manager")
        module_count = len(pm.loaded_modules) if pm else 0
        self._home_tab.update_status(self._devices, module_count, theme)

    def _on_budget_alert(self, ratio: float) -> None:
        """Token 预算到达告警阈值。"""
        from toolkit.gui.toolkit_dialog import confirm_dialog

        pct = int(ratio * 100)
        ok = confirm_dialog(
            self,
            s.MAIN_WINDOW_BUDGET_ALERT_TITLE,
            s.MAIN_WINDOW_BUDGET_ALERT_MSG_FMT.format(pct=pct),
            confirm_text=s.MAIN_WINDOW_BUDGET_CONTINUE,
        )
        llm_mgr = self.context.get("llm_manager")
        if llm_mgr and hasattr(llm_mgr, "set_budget_paused"):
            llm_mgr.set_budget_paused(not ok)

    def _on_degradation(self, from_provider: str, to_provider: str) -> None:
        """LLM Provider 降级通知。"""
        from PyQt6.QtCore import QTimer

        original = self._status_text.text()
        self._status_text.setText(
            s.MAIN_WINDOW_LLM_DEGRADED_FMT.format(
                from_provider=from_provider, to_provider=to_provider
            )
        )
        QTimer.singleShot(3000, lambda: self._status_text.setText(original))

    def _open_llm_settings(self) -> None:
        """打开 LLM 模型设置对话框。"""
        from toolkit.gui.llm_settings_dialog import LLMSettingsDialog

        llm_manager = self.context.get("llm_manager")
        if not llm_manager:
            logger.warning("LLM Manager 未初始化")
            return
        dialog = LLMSettingsDialog(llm_manager, parent=self)
        dialog.exec()

    def _open_agent_settings(self) -> None:
        """打开 Agent 设置对话框。"""
        if self._agent_tab and hasattr(self._agent_tab, "_on_open_settings"):
            self._agent_tab._on_open_settings()
            return
        for tab in self._tabs:
            if hasattr(tab, "_on_open_settings"):
                tab._on_open_settings()
                return
        logger.warning("Agent 模块未加载，无法打开设置")

    def _on_screen_changed(self, screen) -> None:
        """跨屏拖动后恢复窗口大小。"""
        if self._is_maximized:
            return
        from PyQt6.QtCore import QTimer

        target = self._intended_size
        QTimer.singleShot(100, lambda: self._restore_after_screen_change(target))

    def _restore_after_screen_change(self, target_size) -> None:
        """DPI 缩放稳定后恢复到目标大小。"""
        if self._is_maximized:
            return
        screen = self.screen()
        if screen:
            avail = screen.availableGeometry()
            w = min(target_size.width(), avail.width())
            h = min(target_size.height(), avail.height())
            self.resize(w, h)

    def _apply_theme(self) -> None:
        """应用主题样式表到整个应用。"""
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_theme_stylesheet(self._current_theme))
