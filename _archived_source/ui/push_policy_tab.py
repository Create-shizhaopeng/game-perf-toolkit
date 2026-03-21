import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QProgressBar, QFrame, QMessageBox, QFileDialog, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSlot, QMimeData
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat, QFont, QDragEnterEvent, QDropEvent

from core.adb_manager import AdbManager, DeviceMonitor
from core.device_service import DeviceState
from core.push_policy_service import PushPolicyService, XmlErrorContext, is_valid_config_filename
from core.config_manager import ConfigManager


class PushPolicyTab(QWidget):
    def __init__(
        self,
        adb_manager: AdbManager,
        config_manager: ConfigManager,
        parent=None,
    ):
        super().__init__(parent)
        self._adb = adb_manager
        self._config_manager = config_manager
        self._current_state = DeviceState()

        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )
        self._push_service = PushPolicyService(adb_manager, data_dir)

        self._init_ui()
        self._connect_signals()
        self._update_button_states(False)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self._create_device_info_section(layout)
        self._create_file_section(layout)
        self._create_log_section(layout)
        self._create_button_section(layout)

    # ── Section 1: 当前设备信息 ─────────────────────────────────
    def _create_device_info_section(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 10, 16, 10)
        card_layout.setSpacing(6)

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

        fields = QGridLayout()
        fields.setHorizontalSpacing(8)
        fields.setVerticalSpacing(4)

        labels = ["brand:", "manufacturer:", "model:"]
        self._info_fields: list[QLineEdit] = []
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

    # ── Section 2: 配置文件选择 ─────────────────────────────────
    def _create_file_section(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card.setAcceptDrops(True)
        card.setMinimumHeight(100)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 10, 16, 10)
        card_layout.setSpacing(6)

        # 标题行：左侧「配置文件」，右侧提醒文字（同一行同一高度）
        header = QHBoxLayout()
        title = QLabel("配置文件")
        title.setProperty("class", "sectionTitleOrange")
        header.addWidget(title)

        drop_hint = QLabel("支持拖拽「文件名包含 gameperfconfig」的 .xml 到此区域")
        drop_hint.setProperty("class", "fieldLabel")
        drop_hint.setStyleSheet("font-size: 10px; font-style: italic;")
        header.addWidget(drop_hint)
        header.addStretch()

        card_layout.addLayout(header)

        row = QHBoxLayout()
        self._file_input = QLineEdit()
        self._file_input.setPlaceholderText("文件名须包含 gameperfconfig 的 .xml（如 gameperfconfig（11）.xml）；推送后设备上为 gameperfconfig.xml")
        self._file_input.setFixedHeight(28)
        self._file_input.setObjectName("fileInput")
        row.addWidget(self._file_input, 1)

        self._browse_btn = QPushButton("浏览...")
        self._browse_btn.setObjectName("browseButton")
        self._browse_btn.setFixedHeight(28)
        self._browse_btn.setFixedWidth(70)
        row.addWidget(self._browse_btn)

        card_layout.addLayout(row)

        self._file_card = card
        card.dragEnterEvent = self._on_drag_enter
        card.dropEvent = self._on_drop
        parent_layout.addWidget(card)

    # ── Section 3: 执行日志 ─────────────────────────────────────
    def _create_log_section(self, parent_layout: QVBoxLayout):
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
        self._progress_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        prog_layout.addWidget(self._progress_label)

        bottom.addLayout(prog_layout)
        card_layout.addLayout(bottom)

        parent_layout.addWidget(card, 1)

    # ── Section 4: 操作按钮 ─────────────────────────────────────
    def _create_button_section(self, parent_layout: QVBoxLayout):
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

        parent_layout.addWidget(card)

    # ── Signals ─────────────────────────────────────────────────
    def _connect_signals(self):
        self._browse_btn.clicked.connect(self._on_browse)
        self._start_btn.clicked.connect(self._on_start)
        self._clear_btn.clicked.connect(self._on_clear)
        self._reset_btn.clicked.connect(self._on_reset)

        self._push_service.progress.connect(self._on_progress)
        self._push_service.error.connect(self._on_error)
        self._push_service.xml_error.connect(self._on_xml_error)
        self._push_service.finished_signal.connect(self._on_finished)

    # ── Drag & Drop ─────────────────────────────────────────────
    def _on_drag_enter(self, event: QDragEnterEvent):
        mime: QMimeData = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                if is_valid_config_filename(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def _on_drop(self, event: QDropEvent):
        mime: QMimeData = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if is_valid_config_filename(path):
                    self._file_input.setText(path)
                    event.acceptProposedAction()
                    return
            self._append_log(
                "✗ 仅支持「文件名包含 gameperfconfig」的 .xml 文件（如 gameperfconfig（11）.xml）",
                self._error_color(),
            )
        event.ignore()

    # ── Action Slots ────────────────────────────────────────────
    @pyqtSlot()
    def _on_browse(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择配置文件", "", "XML 文件 (*.xml);;所有文件 (*)"
        )
        if filepath:
            self._file_input.setText(filepath)

    @pyqtSlot()
    def _on_start(self):
        filepath = self._file_input.text().strip()
        if not filepath:
            QMessageBox.warning(self, "未选择文件", "请先选择要推送的配置文件")
            return
        if not os.path.isfile(filepath):
            QMessageBox.warning(self, "文件不存在", f"找不到文件:\n{filepath}")
            return
        if not is_valid_config_filename(filepath):
            QMessageBox.warning(
                self,
                "无效的配置文件",
                "文件名须包含 gameperfconfig 且扩展名为 .xml\n例如：gameperfconfig（11）.xml、aaagameperfconfig.xml",
            )
            return

        self._log_area.clear()
        self._set_progress(0)
        self._update_button_states(False)
        self._push_service.push(filepath)

    @pyqtSlot()
    def _on_clear(self):
        self._file_input.clear()

    @pyqtSlot()
    def _on_reset(self):
        self._log_area.clear()
        self._set_progress(0)
        self._update_button_states(False)
        self._push_service.reset()

    # ── Service Slots ───────────────────────────────────────────
    @pyqtSlot(str)
    def _on_progress(self, msg: str):
        color = self._progress_color()
        if "✓" in msg:
            color = self._success_color()
        self._append_log(msg, color)
        self._increment_progress()

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._append_log(f"✗ {msg}", self._error_color())
        self._update_button_states(self._current_state.is_connected)

    @pyqtSlot(object)
    def _on_xml_error(self, ctx: XmlErrorContext):
        self._append_log(
            f"✗ XML 格式错误（第 {ctx.error_line} 行，第 {ctx.error_col} 列）: {ctx.error_msg}",
            self._error_color(),
        )
        if ctx.context_lines:
            self._append_log("", "#888888")
            for line_no, line_text, is_err in ctx.context_lines:
                if is_err:
                    marker = " →"
                    self._append_error_context_line(f"{marker} {line_no:>4}| {line_text}", True)
                else:
                    marker = "  "
                    self._append_error_context_line(f"{marker} {line_no:>4}| {line_text}", False)
            self._append_log("", "#888888")

    @pyqtSlot(bool, str)
    def _on_finished(self, success: bool, message: str):
        if success:
            self._set_progress(100)
        self._update_button_states(self._current_state.is_connected)

    # ── Device State (called by MainWindow) ─────────────────────
    def on_device_connected(self, serial: str, state: DeviceState):
        self._current_state = state
        self._info_fields[0].setText(state.current_brand)
        self._info_fields[1].setText(state.current_manufacturer)
        self._info_fields[2].setText(state.current_model)
        self._conn_dot.setVisible(True)
        self._conn_text.setText(f"设备已连接 · {serial}")
        self._update_button_states(True)

    def on_device_disconnected(self):
        self._current_state = DeviceState()
        for field in self._info_fields:
            field.clear()
        self._conn_dot.setVisible(False)
        self._conn_text.setText("未连接设备")
        self._badge.setVisible(False)
        self._update_button_states(False)

    # ── UI Helpers ──────────────────────────────────────────────
    def _update_button_states(self, enabled: bool):
        self._start_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(True)
        self._reset_btn.setEnabled(enabled)

    def _append_log(self, text: str, color: str = "#d4d4d4"):
        cursor = self._log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text + "\n", fmt)
        self._log_area.setTextCursor(cursor)
        self._log_area.ensureCursorVisible()

    def _append_error_context_line(self, text: str, is_error: bool):
        cursor = self._log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()

        if is_error:
            fmt.setForeground(QColor("#ff6b6b"))
            fmt.setFontWeight(QFont.Weight.Bold)
            fmt.setBackground(QColor("#3d1f1f"))
        else:
            fmt.setForeground(QColor("#888888"))
            fmt.setFont(QFont("Consolas", 10))

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

    def _is_light_theme(self) -> bool:
        return self._config_manager.get_theme() == "light"

    def _error_color(self) -> str:
        return "#d83b3b" if self._is_light_theme() else "#f44747"

    def _success_color(self) -> str:
        return "#22863a" if self._is_light_theme() else "#608b4e"

    def _progress_color(self) -> str:
        return "#0066b8" if self._is_light_theme() else "#dcdcaa"
