from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit,
    QProgressBar, QFrame, QMessageBox, QSizePolicy, QCompleter,
    QTabWidget,
)
from PyQt6.QtCore import Qt, pyqtSlot, QSize, QStringListModel, QTimer
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat, QFont

from core.adb_manager import AdbManager, DeviceMonitor
from core.device_service import DeviceService, DeviceState
from core.profile_manager import ProfileManager, DeviceProfile
from core.config_manager import ConfigManager
from ui.save_dialog import SaveDialog
from ui.device_popup import DevicePopup
from ui.settings_menu import SettingsMenu
from ui.styles import apply_theme
from ui.game_perf_tab import GamePerfToolTab


class MainWindow(QMainWindow):
    def __init__(
        self,
        adb_manager: AdbManager,
        device_service: DeviceService,
        profile_manager: ProfileManager,
        config_manager: ConfigManager,
        parent=None,
    ):
        super().__init__(parent)
        self._adb = adb_manager
        self._device_service = device_service
        self._profile_manager = profile_manager
        self._config_manager = config_manager
        self._device_monitor: DeviceMonitor = None
        self._current_state = DeviceState()

        self._init_ui()
        self._setup_settings_menu()
        self._setup_auto_complete()
        self._connect_signals()
        self._update_button_states(False)

    def _init_ui(self):
        self.setWindowTitle("Toolkit")
        self.setMinimumSize(640, 520)
        self.resize(720, 580)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar
        self._create_title_bar(main_layout)

        # Tab widget
        self._tab_widget = QTabWidget()
        self._tab_widget.setObjectName("mainTabWidget")

        # Tab 0: ModifyModelNameTool (original functionality)
        model_tab = QWidget()
        model_tab_layout = QVBoxLayout(model_tab)
        model_tab_layout.setContentsMargins(12, 8, 12, 8)
        model_tab_layout.setSpacing(8)

        self._create_section1(model_tab_layout)
        self._create_section2(model_tab_layout)
        self._create_section3(model_tab_layout)
        self._create_section4(model_tab_layout)

        self._tab_widget.addTab(model_tab, "ModifyModelNameTool")

        # Tab 1: 游戏性能配置（编辑 gameperfconfig.xml + 推送到设备）
        self._game_perf_tab = GamePerfToolTab(
            adb_manager=self._adb,
            config_manager=self._config_manager,
            parent=self,
        )
        self._tab_widget.addTab(self._game_perf_tab, "游戏性能配置")
        self._game_perf_tab.refresh_device_requested.connect(self._on_push_finished_request_refresh_device)

        # 右侧占位，避免标签栏空白区域看起来像“空标签”
        tab_corner = QWidget()
        tab_corner.setObjectName("tabBarCorner")
        tab_corner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._tab_widget.setCornerWidget(tab_corner, Qt.Corner.TopRightCorner)

        main_layout.addWidget(self._tab_widget, 1)

    # ── Title Bar ────────────────────────────────────────────────
    def _create_title_bar(self, parent_layout: QVBoxLayout):
        bar = QWidget()
        bar.setObjectName("titleBar")
        bar.setFixedHeight(36)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 8, 0)

        title = QLabel("Toolkit")
        title.setObjectName("titleLabel")
        layout.addWidget(title)
        layout.addStretch()

        self._gear_btn = QPushButton("\u2699")
        self._gear_btn.setObjectName("gearButton")
        self._gear_btn.setFixedSize(28, 22)
        self._gear_btn.setToolTip("设置")
        layout.addWidget(self._gear_btn)

        parent_layout.addWidget(bar)

    # ── Section 1: Current Device Info ───────────────────────────
    def _create_section1(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 10, 16, 10)
        card_layout.setSpacing(6)

        # Header row: title + badge + connection
        header = QHBoxLayout()
        title = QLabel("当前设备信息")
        title.setProperty("class", "sectionTitleBlue")
        header.addWidget(title)
        header.addStretch()

        self._badge = QLabel()
        self._badge.setProperty("class", "badgeGreen")
        self._badge.setVisible(False)
        header.addWidget(self._badge)

        card_layout.addLayout(header)

        # Fields row
        fields = QGridLayout()
        fields.setHorizontalSpacing(8)
        fields.setVerticalSpacing(4)

        labels = ["brand:", "manufacturer:", "model:"]
        self._info_fields = []
        for i, lbl_text in enumerate(labels):
            lbl = QLabel(lbl_text)
            lbl.setProperty("class", "fieldLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            field = QLineEdit()
            field.setReadOnly(True)
            field.setProperty("class", "readonlyField")
            field.setFixedHeight(26)
            fields.addWidget(lbl, 0, i * 2)
            fields.addWidget(field, 0, i * 2 + 1)
            self._info_fields.append(field)

        card_layout.addLayout(fields)

        # Connection indicator
        conn_layout = QHBoxLayout()
        self._conn_dot = QLabel("●")
        self._conn_dot.setProperty("class", "connectionDot")
        self._conn_dot.setVisible(False)
        conn_layout.addWidget(self._conn_dot)

        self._conn_text = QLabel("未连接设备")
        self._conn_text.setProperty("class", "fieldLabel")
        self._conn_text.setStyleSheet("font-size: 11px;")
        conn_layout.addWidget(self._conn_text)
        conn_layout.addStretch()
        card_layout.addLayout(conn_layout)

        parent_layout.addWidget(card)

    # ── Section 2: Disguise Device Info ──────────────────────────
    def _create_section2(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card.setMinimumHeight(100)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 10, 16, 10)
        card_layout.setSpacing(6)

        # Header row: title + star button
        header = QHBoxLayout()
        title = QLabel("伪装设备信息")
        title.setProperty("class", "sectionTitleOrange")
        header.addWidget(title)

        self._star_btn = QPushButton("☆")
        self._star_btn.setObjectName("starButton")
        self._star_btn.setFixedSize(20, 20)
        self._star_btn.setToolTip("快捷选取设备档案")
        header.addWidget(self._star_btn)
        header.addStretch()

        card_layout.addLayout(header)

        # ComboBox fields
        fields = QGridLayout()
        fields.setHorizontalSpacing(8)
        fields.setVerticalSpacing(4)

        labels = ["brand:", "manufacturer:", "model:"]
        self._combo_fields: list[QComboBox] = []
        for i, lbl_text in enumerate(labels):
            lbl = QLabel(lbl_text)
            lbl.setProperty("class", "fieldLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            combo = QComboBox()
            combo.setEditable(True)
            combo.setFixedHeight(28)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            fields.addWidget(lbl, 0, i * 2)
            fields.addWidget(combo, 0, i * 2 + 1)
            self._combo_fields.append(combo)

        card_layout.addLayout(fields)
        parent_layout.addWidget(card)

    # ── Section 3: Execution Log ─────────────────────────────────
    def _create_section3(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 10, 16, 10)
        card_layout.setSpacing(6)

        title = QLabel("执行日志")
        title.setProperty("class", "sectionTitleBlue")
        card_layout.addWidget(title)

        self._log_area = QTextEdit()
        self._log_area.setObjectName("logArea")
        self._log_area.setReadOnly(True)
        card_layout.addWidget(self._log_area, 1)

        # Bottom fixed area: separator + progress bar + percentage
        bottom = QVBoxLayout()
        bottom.setSpacing(8)

        sep = QFrame()
        sep.setProperty("class", "separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        bottom.addWidget(sep)

        prog_layout = QHBoxLayout()
        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        prog_layout.addWidget(self._progress_bar, 1)

        self._progress_label = QLabel("0%")
        self._progress_label.setStyleSheet("font-size: 10px;")
        self._progress_label.setFixedWidth(36)
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        prog_layout.addWidget(self._progress_label)

        bottom.addLayout(prog_layout)
        card_layout.addLayout(bottom)

        parent_layout.addWidget(card, 1)

    # ── Section 4: Action Buttons ────────────────────────────────
    def _create_section4(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)

        card_layout.addStretch()

        self._start_btn = QPushButton("▶ Start")
        self._start_btn.setObjectName("startButton")
        card_layout.addWidget(self._start_btn)

        card_layout.addStretch()

        self._clear_btn = QPushButton("✕ Clear")
        self._clear_btn.setObjectName("clearButton")
        card_layout.addWidget(self._clear_btn)

        card_layout.addStretch()

        self._reset_btn = QPushButton("↺ Reset")
        self._reset_btn.setObjectName("resetButton")
        card_layout.addWidget(self._reset_btn)

        card_layout.addStretch()

        # Tab order
        self.setTabOrder(self._start_btn, self._clear_btn)
        self.setTabOrder(self._clear_btn, self._reset_btn)

        parent_layout.addWidget(card)

    # ── Settings Menu ────────────────────────────────────────────
    def _setup_settings_menu(self):
        self._settings_menu = SettingsMenu(
            self._profile_manager, self._config_manager, parent=self
        )
        self._settings_menu.theme_changed.connect(self._on_theme_changed)
        self._settings_menu.data_imported.connect(self._refresh_completers)
        self._gear_btn.clicked.connect(self._on_gear_clicked)

    def _on_gear_clicked(self):
        btn = self._gear_btn
        pos = btn.mapToGlobal(btn.rect().bottomLeft())
        self._settings_menu.show_at(pos)

    @pyqtSlot(str)
    def _on_theme_changed(self, theme: str):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            apply_theme(app, theme)

    # ── Auto-complete ────────────────────────────────────────────
    def _setup_auto_complete(self):
        self._completers = []
        fields = ["brand", "manufacturer", "model"]
        for i, field_name in enumerate(fields):
            completer = QCompleter([], self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self._combo_fields[i].setCompleter(completer)
            self._completers.append(completer)

        self._refresh_completers()

        for i, combo in enumerate(self._combo_fields):
            combo.currentTextChanged.connect(
                lambda text, idx=i: self._on_combo_text_changed(idx, text)
            )

    def _refresh_completers(self):
        profiles = self._profile_manager.get_all()
        fields = ["brand", "manufacturer", "model"]
        for i, field_name in enumerate(fields):
            values = sorted(set(getattr(p, field_name) for p in profiles))
            model = QStringListModel(values)
            self._completers[i].setModel(model)

            combo = self._combo_fields[i]
            current_text = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(values)
            combo.setCurrentText(current_text)
            combo.blockSignals(False)

    def _on_combo_text_changed(self, idx: int, text: str):
        if not text.strip():
            return
        text_lower = text.strip().lower()
        fields = ["brand", "manufacturer", "model"]
        field_name = fields[idx]

        profiles = self._profile_manager.find(field_name, text_lower)
        if not profiles:
            return

        profiles.sort(key=lambda p: getattr(p, field_name).lower())
        best = profiles[0]

        for i, fname in enumerate(fields):
            if i != idx:
                self._combo_fields[i].blockSignals(True)
                self._combo_fields[i].setCurrentText(getattr(best, fname))
                self._combo_fields[i].blockSignals(False)

    # ── Signals ──────────────────────────────────────────────────
    def _connect_signals(self):
        self._start_btn.clicked.connect(self._on_start)
        self._clear_btn.clicked.connect(self._on_clear)
        self._reset_btn.clicked.connect(self._on_reset)
        self._star_btn.clicked.connect(self._on_star)

        self._device_service.progress.connect(self._on_progress)
        self._device_service.error.connect(self._on_error)
        self._device_service.finished_signal.connect(self._on_finished)

    def set_device_monitor(self, monitor: DeviceMonitor):
        self._device_monitor = monitor
        monitor.device_connected.connect(self._on_device_connected)
        monitor.device_disconnected.connect(self._on_device_disconnected)

    # ── Device Monitor Slots ─────────────────────────────────────
    @pyqtSlot(str)
    def _on_device_connected(self, serial: str):
        try:
            state = self._device_service.get_device_state()
            self._current_state = state
            self._info_fields[0].setText(state.current_brand)
            self._info_fields[1].setText(state.current_manufacturer)
            self._info_fields[2].setText(state.current_model)

            self._conn_dot.setVisible(True)
            self._conn_text.setText(f"设备已连接 · {serial}")

            self._update_badge(state.is_disguised)
            self._update_button_states(True)

            self._game_perf_tab.on_device_connected(serial, state)
        except Exception as e:
            self._append_log(f"✗ 读取设备信息失败: {e}", "red")

    @pyqtSlot()
    def _on_device_disconnected(self):
        self._current_state = DeviceState()
        for field in self._info_fields:
            field.clear()
        self._conn_dot.setVisible(False)
        self._conn_text.setText("未连接设备")
        self._badge.setVisible(False)
        self._update_button_states(False)

        self._game_perf_tab.on_device_disconnected()

    @pyqtSlot()
    def _on_push_finished_request_refresh_device(self):
        """push 完成且设备重启后，延迟刷新当前设备信息与连接状态。"""
        QTimer.singleShot(5000, self._refresh_device_after_reboot)

    def _refresh_device_after_reboot(self):
        """重启后重新读取设备状态并更新所有 Tab 的当前设备信息。"""
        try:
            devices = self._adb.get_connected_devices()
            if not devices:
                return
            state = self._device_service.get_device_state()
            self._on_device_connected(devices[0])
        except Exception:
            pass

    # ── Action Slots ─────────────────────────────────────────────
    @pyqtSlot()
    def _on_start(self):
        brand = self._combo_fields[0].currentText().strip()
        manufacturer = self._combo_fields[1].currentText().strip()
        model = self._combo_fields[2].currentText().strip()

        if not brand or not manufacturer or not model:
            QMessageBox.warning(self, "输入不完整", "请填写所有伪装字段 (brand, manufacturer, model)")
            return

        if (brand == self._current_state.current_brand
                and manufacturer == self._current_state.current_manufacturer
                and model == self._current_state.current_model):
            QMessageBox.information(
                self, "无需伪装",
                "当前设备信息与待伪装设备信息一致，无需执行伪装操作。"
            )
            return

        # FR-7: save-before-disguise check
        if not self._profile_manager.exists(brand, manufacturer, model):
            dlg = SaveDialog(
                self._profile_manager,
                brand=brand,
                manufacturer=manufacturer,
                model=model,
                parent=self,
            )
            result = dlg.exec()
            if result != SaveDialog.DialogCode.Accepted:
                return
            self._refresh_completers()

        self._log_area.clear()
        self._set_progress(0)
        self._update_button_states(False)
        self._device_service.disguise(brand, manufacturer, model)

    @pyqtSlot()
    def _on_star(self):
        popup = DevicePopup(self._profile_manager, parent=self)
        popup.profile_selected.connect(self._on_profile_selected)
        btn_pos = self._star_btn.mapToGlobal(
            self._star_btn.rect().bottomRight()
        )
        popup.show_at(btn_pos)

    @pyqtSlot(object)
    def _on_profile_selected(self, profile: DeviceProfile):
        self._combo_fields[0].setCurrentText(profile.brand)
        self._combo_fields[1].setCurrentText(profile.manufacturer)
        self._combo_fields[2].setCurrentText(profile.model)

    @pyqtSlot()
    def _on_clear(self):
        for combo in self._combo_fields:
            combo.setCurrentText("")

    @pyqtSlot()
    def _on_reset(self):
        self._log_area.clear()
        self._set_progress(0)
        self._update_button_states(False)
        self._device_service.reset()

    # ── DeviceService Slots ──────────────────────────────────────
    @pyqtSlot(str)
    def _on_progress(self, msg: str):
        color = "#dcdcaa"
        if "✓" in msg:
            color = "#608b4e"

        current_theme = self._config_manager.get_theme()
        if current_theme == "light":
            if "✓" in msg:
                color = "#22863a"
            else:
                color = "#0066b8"

        self._append_log(msg, color)
        self._increment_progress()

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        color = "#f44747"
        if self._config_manager.get_theme() == "light":
            color = "#d83b3b"
        self._append_log(f"✗ {msg}", color)
        self._update_button_states(self._current_state.is_connected)

    @pyqtSlot(object)
    def _on_finished(self, state: DeviceState):
        self._current_state = state
        self._info_fields[0].setText(state.current_brand)
        self._info_fields[1].setText(state.current_manufacturer)
        self._info_fields[2].setText(state.current_model)
        self._update_badge(state.is_disguised)
        self._set_progress(100)
        self._update_button_states(True)

    # ── UI Helpers ───────────────────────────────────────────────
    def _update_badge(self, is_disguised: bool):
        self._badge.setVisible(True)
        if is_disguised:
            self._badge.setText("● 已伪装")
            self._badge.setProperty("class", "badgeYellow")
        else:
            self._badge.setText("● 未伪装")
            self._badge.setProperty("class", "badgeGreen")
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)

    def _update_button_states(self, enabled: bool):
        self._start_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)
        self._reset_btn.setEnabled(enabled)

    def _append_log(self, text: str, color: str = "#d4d4d4"):
        cursor = self._log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text + "\n", fmt)

        self._log_area.setTextCursor(cursor)
        self._log_area.ensureCursorVisible()

    def _set_progress(self, value: int):
        self._progress_bar.setValue(value)
        self._progress_label.setText(f"{value}%")

    def _increment_progress(self):
        val = self._progress_bar.value()
        total_steps = 12
        step = 100 // total_steps
        new_val = min(val + step, 95)
        self._set_progress(new_val)

    # ── Public API for settings_menu / save_dialog / device_popup ─
    def get_gear_button(self) -> QPushButton:
        return self._gear_btn

    def get_star_button(self) -> QPushButton:
        return self._star_btn

    def get_combo_fields(self) -> list:
        return self._combo_fields

    def get_profile_manager(self) -> ProfileManager:
        return self._profile_manager

    def get_config_manager(self) -> ConfigManager:
        return self._config_manager

    def get_log_area(self) -> QTextEdit:
        return self._log_area

    def refresh_device_state(self):
        try:
            state = self._device_service.get_device_state()
            if state.is_connected:
                self._on_device_connected("")
        except Exception:
            pass
