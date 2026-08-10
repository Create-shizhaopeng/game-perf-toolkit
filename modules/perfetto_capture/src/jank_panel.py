"""Perfetto Capture 模块 — Jank 配置面板

紧凑竖向布局，含配置、状态、操作按钮，放置在 Jank 监控区的左侧。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .models import AppInfo, JankConfig

if TYPE_CHECKING:
    from .jank_service import JankMonitorService


class AppSelector(QWidget):
    """应用选择器。"""

    app_selected = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._apps: list[AppInfo] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        label = QLabel("监控应用")
        label.setObjectName("jankSectionLabel")
        header.addWidget(label)
        header.addStretch()
        self._refresh_btn = QPushButton("🔄 刷新")
        self._refresh_btn.setObjectName("jankSmallBtn")
        self._refresh_btn.setFixedHeight(22)
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        header.addWidget(self._refresh_btn)
        layout.addLayout(header)

        self._combo = QComboBox()
        self._combo.setFixedHeight(24)
        self._combo.setPlaceholderText("请连接设备...")
        self._combo.currentIndexChanged.connect(self._on_selection_changed)
        layout.addWidget(self._combo)

    def set_apps(
        self,
        apps: list[AppInfo],
        select_foreground: bool = False,
    ) -> None:
        """填充应用列表。

        Args:
            apps: 应用列表（is_foreground 标记当前前台应用）。
            select_foreground: 为 True 时，刷新后自动选中当前前台应用
                （用于启动监测/勾选检测时跟随前台，支持前台应用热切换）。
                为 False 时保留当前选中项。
        """
        self._apps = apps
        current_pkg = self.selected_package

        self._combo.blockSignals(True)
        self._combo.clear()

        if not apps:
            self._combo.setPlaceholderText("无运行中的应用")
        else:
            self._combo.setPlaceholderText("选择应用...")

        foreground_pkg = ""
        for app in apps:
            display = app.package_name
            if app.is_foreground:
                display = f"★ {display}"
                if not foreground_pkg:
                    foreground_pkg = app.package_name
            self._combo.addItem(display, app.package_name)

        if select_foreground and foreground_pkg:
            idx = self._combo.findData(foreground_pkg)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
        elif current_pkg:
            idx = self._combo.findData(current_pkg)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)

        self._combo.blockSignals(False)

        if self._combo.currentIndex() != -1:
            self._on_selection_changed(self._combo.currentIndex())

    @property
    def selected_package(self) -> str:
        return self._combo.currentData() or ""

    def set_enabled(self, enabled: bool) -> None:
        self._combo.setEnabled(enabled)
        self._refresh_btn.setEnabled(enabled)

    def _on_selection_changed(self, index: int) -> None:
        pkg = self._combo.itemData(index) or ""
        self.app_selected.emit(pkg)

    def _on_refresh_clicked(self) -> None:
        self.refresh_requested.emit()


class JankConfigPanel(QWidget):
    """Jank 配置面板（紧凑竖向，含配置+状态+操作按钮）。

    信号:
        config_changed: 配置变化
        pause_clicked: 暂停/恢复判定
        export_clicked: 导出数据
    """

    config_changed = pyqtSignal(JankConfig)
    pause_clicked = pyqtSignal()
    export_clicked = pyqtSignal()

    PANEL_WIDTH = 200

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._config = JankConfig()
        self._paused = False
        self.setFixedWidth(self.PANEL_WIDTH)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self._app_selector = AppSelector()
        self._app_selector.app_selected.connect(self._on_app_selected)
        layout.addWidget(self._app_selector)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._threshold_spin = QSpinBox()
        self._threshold_spin.setRange(1, 30)
        self._threshold_spin.setValue(3)
        self._threshold_spin.setSuffix(" 帧")
        self._threshold_spin.setFixedHeight(24)
        self._threshold_spin.setToolTip("1 秒内 Jank 帧数超过此阈值触发抓取")
        self._threshold_spin.valueChanged.connect(self._on_threshold_changed)
        lbl1 = QLabel("Jank 阈值")
        lbl1.setObjectName("jankSectionLabel")
        form.addRow(lbl1, self._threshold_spin)

        self._max_captures_spin = QSpinBox()
        self._max_captures_spin.setRange(1, 10)
        self._max_captures_spin.setValue(3)
        self._max_captures_spin.setSuffix(" 次")
        self._max_captures_spin.setFixedHeight(24)
        self._max_captures_spin.setToolTip("单次监控最多自动抓取次数")
        self._max_captures_spin.valueChanged.connect(self._on_max_captures_changed)
        lbl2 = QLabel("最大抓取")
        lbl2.setObjectName("jankSectionLabel")
        form.addRow(lbl2, self._max_captures_spin)

        self._duration_spin = QSpinBox()
        self._duration_spin.setRange(1, 12)
        self._duration_spin.setValue(3)
        self._duration_spin.setSuffix(" 小时")
        self._duration_spin.setFixedHeight(24)
        self._duration_spin.setToolTip("监控最大持续时长，到期自动停止")
        self._duration_spin.valueChanged.connect(self._on_duration_changed)
        lbl3 = QLabel("监控时长")
        lbl3.setObjectName("jankSectionLabel")
        form.addRow(lbl3, self._duration_spin)

        layout.addLayout(form)

        # 抓取状态
        self._capture_label = QLabel("抓取: 0/3")
        self._capture_label.setObjectName("jankCaptureLabel")
        layout.addWidget(self._capture_label)

        layout.addStretch()

        # 操作按钮
        self._pause_btn = QPushButton("⏸ 暂停判定")
        self._pause_btn.setObjectName("jankSmallBtn")
        self._pause_btn.setFixedHeight(26)
        self._pause_btn.clicked.connect(self._on_pause_clicked)
        layout.addWidget(self._pause_btn)

        self._export_btn = QPushButton("📊 导出数据")
        self._export_btn.setObjectName("jankSmallBtn")
        self._export_btn.setFixedHeight(26)
        self._export_btn.clicked.connect(self.export_clicked.emit)
        layout.addWidget(self._export_btn)

    @property
    def app_selector(self) -> AppSelector:
        return self._app_selector

    def get_config(self) -> JankConfig:
        return JankConfig(
            enabled=True,
            target_package=self._app_selector.selected_package,
            jank_threshold=self._threshold_spin.value(),
            max_captures=self._max_captures_spin.value(),
            max_duration_hours=self._duration_spin.value(),
        )

    def set_config(self, config: JankConfig) -> None:
        self._config = config
        self._threshold_spin.setValue(config.jank_threshold)
        self._max_captures_spin.setValue(config.max_captures)
        self._duration_spin.setValue(config.max_duration_hours)

    def set_default_threshold(self, threshold: int) -> None:
        self._threshold_spin.setValue(threshold)

    def set_enabled(self, enabled: bool) -> None:
        self._app_selector.set_enabled(enabled)
        self._threshold_spin.setEnabled(enabled)
        self._max_captures_spin.setEnabled(enabled)
        self._duration_spin.setEnabled(enabled)

    def update_capture_count(self, current: int, max_count: int) -> None:
        """更新抓取进度。"""
        self._capture_label.setText(f"抓取: {current}/{max_count}")

    def set_paused(self, paused: bool) -> None:
        """设置暂停状态。"""
        self._paused = paused
        self._pause_btn.setText("▶ 恢复判定" if paused else "⏸ 暂停判定")

    def _on_pause_clicked(self) -> None:
        self._paused = not self._paused
        self.set_paused(self._paused)
        self.pause_clicked.emit()

    def _on_app_selected(self, package: str) -> None:
        self._config.target_package = package
        self.config_changed.emit(self.get_config())

    def _on_threshold_changed(self, value: int) -> None:
        self._config.jank_threshold = value
        self.config_changed.emit(self.get_config())

    def _on_max_captures_changed(self, value: int) -> None:
        self._config.max_captures = value
        self.config_changed.emit(self.get_config())

    def _on_duration_changed(self, value: int) -> None:
        self._config.max_duration_hours = value
        self.config_changed.emit(self.get_config())
