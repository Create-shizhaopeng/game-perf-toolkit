"""设备伪装工具 — GUI 页面（方案 A：左右分栏）"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QTextCharFormat
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.base_tab import BaseTab

logger = logging.getLogger(__name__)

_THEME_COLORS = {
    "dark": {
        "bg": "#1e1e2e",
        "card_bg": "#313244",
        "border": "#45475a",
        "fg": "#cdd6f4",
        "fg_dim": "#a6adc8",
        "accent": "#cba6f7",
        "success": "#a6e3a1",
        "error": "#f38ba8",
        "btn_primary_bg": "#cba6f7",
        "btn_primary_fg": "#1e1e2e",
        "btn_secondary_bg": "#45475a",
        "btn_secondary_fg": "#cdd6f4",
        "input_bg": "#313244",
        "input_border": "#45475a",
    },
    "light": {
        "bg": "#eff1f5",
        "card_bg": "#e6e9ef",
        "border": "#ccd0da",
        "fg": "#333333",
        "fg_dim": "#616161",
        "accent": "#8839ef",
        "success": "#40a02b",
        "error": "#d20f39",
        "btn_primary_bg": "#8839ef",
        "btn_primary_fg": "#ffffff",
        "btn_secondary_bg": "#ccd0da",
        "btn_secondary_fg": "#333333",
        "input_bg": "#dce0e8",
        "input_border": "#bcc0cc",
    },
}


class _BackgroundWorker(QThread):
    """通用后台线程：执行任意 callable"""

    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(object)
    finished_err = pyqtSignal(str)

    def __init__(
        self,
        action: Callable,
        args: tuple = (),
        kwargs: dict | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._action = action
        self._args = args
        self._kwargs = kwargs or {}

    def run(self) -> None:
        try:
            result = self._action(*self._args, **self._kwargs)
            self.finished_ok.emit(result)
        except Exception as e:
            self.finished_err.emit(str(e))


class DeviceDisguiseTab(BaseTab):
    """设备伪装 Tab — 方案 A 左右分栏布局"""

    tab_title = "设备伪装"
    tab_icon = "🎭"

    def __init__(self, context: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._theme = "dark"
        self._worker: _DisguiseWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("disguiseSplitter")

        left = self._build_left_panel()
        right = self._build_right_panel()

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 45)
        splitter.setStretchFactor(1, 55)
        splitter.setHandleWidth(3)

        root.addWidget(splitter)

    # ------------------------------------------------------------------
    # 左侧面板
    # ------------------------------------------------------------------

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 8, 12)
        layout.setSpacing(12)

        self._status_group = self._build_status_group()
        layout.addWidget(self._status_group)

        self._input_group = self._build_input_group()
        layout.addWidget(self._input_group)

        self._button_bar = self._build_button_bar()
        layout.addLayout(self._button_bar)

        layout.addStretch()
        return panel

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("设备状态")
        form = QFormLayout(group)
        form.setSpacing(6)

        self._lbl_brand = QLabel("--")
        self._lbl_manufacturer = QLabel("--")
        self._lbl_model = QLabel("--")
        self._lbl_status = QLabel("未连接设备")
        self._lbl_disguise = QLabel("--")

        form.addRow("品牌:", self._lbl_brand)
        form.addRow("厂商:", self._lbl_manufacturer)
        form.addRow("型号:", self._lbl_model)
        form.addRow("连接:", self._lbl_status)
        form.addRow("伪装:", self._lbl_disguise)

        return group

    def _build_input_group(self) -> QGroupBox:
        group = QGroupBox("伪装设置")
        form = QFormLayout(group)
        form.setSpacing(8)

        self._combo_brand = self._make_combo("品牌", "ro.product.odm.brand")
        self._combo_manufacturer = self._make_combo("厂商", "ro.product.odm.manufacturer")
        self._combo_model = self._make_combo("型号", "ro.product.odm.model")

        form.addRow("目标品牌:", self._combo_brand)
        form.addRow("目标厂商:", self._combo_manufacturer)
        form.addRow("目标型号:", self._combo_model)

        return group

    def _make_combo(self, placeholder: str, prop_name: str) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.lineEdit().setPlaceholderText(f"通过 '{prop_name}' 属性获取")
        combo.lineEdit().textChanged.connect(self._on_input_changed)
        return combo

    def _build_button_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self._btn_profile = QPushButton("选择档案")
        self._btn_profile.clicked.connect(self._on_select_profile)

        self._btn_save_profile = QPushButton("保存档案")
        self._btn_save_profile.clicked.connect(self._on_save_profile)

        self._btn_disguise = QPushButton("伪装")
        self._btn_disguise.setEnabled(False)
        self._btn_disguise.clicked.connect(self._on_disguise)

        self._btn_reset = QPushButton("还原")
        self._btn_reset.setEnabled(False)
        self._btn_reset.clicked.connect(self._on_reset)

        bar.addWidget(self._btn_profile)
        bar.addWidget(self._btn_save_profile)
        bar.addStretch()
        bar.addWidget(self._btn_disguise)
        bar.addWidget(self._btn_reset)

        return bar

    # ------------------------------------------------------------------
    # 右侧日志面板
    # ------------------------------------------------------------------

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 12, 16, 12)
        layout.setSpacing(4)

        header = QLabel("操作日志")
        header.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(header)
        self._log_header = header

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setObjectName("disguiseLog")
        layout.addWidget(self._log_view)

        clear_btn = QPushButton("清空日志")
        clear_btn.setMaximumWidth(80)
        clear_btn.clicked.connect(self._log_view.clear)
        layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self._btn_clear_log = clear_btn

        return panel

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        c = _THEME_COLORS[theme]

        self._btn_disguise.setStyleSheet(
            f"QPushButton {{ background-color: {c['btn_primary_bg']}; "
            f"color: {c['btn_primary_fg']}; border-radius: 6px; padding: 8px 20px; "
            f"font-weight: bold; }}"
            f"QPushButton:hover {{ opacity: 0.9; }}"
            f"QPushButton:disabled {{ background-color: {c['btn_secondary_bg']}; "
            f"color: {c['fg_dim']}; }}"
        )
        self._btn_reset.setStyleSheet(
            f"QPushButton {{ background-color: {c['btn_secondary_bg']}; "
            f"color: {c['btn_secondary_fg']}; border-radius: 6px; padding: 8px 20px; }}"
            f"QPushButton:disabled {{ color: {c['fg_dim']}; }}"
        )

        self._log_header.setStyleSheet(
            f"font-weight: bold; font-size: 13px; color: {c['fg']};"
        )

    # ------------------------------------------------------------------
    # 设备状态感知
    # ------------------------------------------------------------------

    def on_devices_changed(self, devices: list[str]) -> None:
        super().on_devices_changed(devices)
        has_device = len(devices) > 0
        self._btn_reset.setEnabled(has_device)
        self._on_input_changed()

        if has_device:
            self._lbl_status.setText(f"已连接 ({len(devices)})")
            self._async_refresh_state(devices[0])
        else:
            self._lbl_status.setText("未连接设备")
            self._lbl_brand.setText("--")
            self._lbl_manufacturer.setText("--")
            self._lbl_model.setText("--")
            self._lbl_disguise.setText("--")

    def _refresh_device_state(self, state) -> None:
        """更新 UI 上的设备状态显示（必须在 GUI 线程调用）"""
        self._lbl_brand.setText(state.current_brand or "--")
        self._lbl_manufacturer.setText(state.current_manufacturer or "--")
        self._lbl_model.setText(state.current_model or "--")
        self._lbl_disguise.setText("已伪装" if state.is_disguised else "未伪装")

    def _async_refresh_state(self, serial: str) -> None:
        """在后台线程获取设备状态，避免阻塞 GUI"""
        svc = self.context.get("dd_service")
        if not svc:
            return
        worker = _BackgroundWorker(svc.get_device_state, (serial,), parent=self)
        worker.finished_ok.connect(self._on_state_loaded)
        worker.finished_err.connect(lambda msg: logger.warning("获取设备状态失败: %s", msg))
        worker.start()
        self._state_worker = worker

    def _on_state_loaded(self, state) -> None:
        """设备状态加载完成，更新 UI 并通知框架"""
        self._refresh_device_state(state)
        self._emit_state_event(state)

    # ------------------------------------------------------------------
    # 联想数据
    # ------------------------------------------------------------------

    def refresh_completers(self) -> None:
        """从档案库刷新输入框联想数据，保留当前输入文本"""
        profile_mgr = self.context.get("dd_profile_mgr")
        if not profile_mgr:
            return

        profiles = profile_mgr.get_all()
        brands = sorted({p.brand for p in profiles})
        manufacturers = sorted({p.manufacturer for p in profiles})
        models = sorted({p.model for p in profiles})

        self._set_completer(self._combo_brand, brands)
        self._set_completer(self._combo_manufacturer, manufacturers)
        self._set_completer(self._combo_model, models)

    @staticmethod
    def _set_completer(combo: QComboBox, items: list[str]) -> None:
        current_text = combo.currentText()
        combo.clear()
        combo.addItems(items)
        combo.setCurrentText(current_text)
        completer = QCompleter(items)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        combo.setCompleter(completer)

    # ------------------------------------------------------------------
    # 操作
    # ------------------------------------------------------------------

    def _on_input_changed(self) -> None:
        brand = self._combo_brand.currentText().strip()
        mfr = self._combo_manufacturer.currentText().strip()
        model = self._combo_model.currentText().strip()
        has_input = bool(brand and mfr and model)
        self._btn_disguise.setEnabled(has_input and self.device_connected)

    def _get_serial(self) -> str | None:
        from toolkit.core.adb_manager import AdbManager

        adb: AdbManager | None = self.context.get("dd_adb")
        if not adb:
            return None
        devices = adb.get_connected_devices()
        return devices[0] if devices else None

    def _on_disguise(self) -> None:
        if not self.require_device():
            return

        serial = self._get_serial()
        if not serial:
            return

        brand = self._combo_brand.currentText().strip()
        mfr = self._combo_manufacturer.currentText().strip()
        model = self._combo_model.currentText().strip()

        if not (brand and mfr and model):
            return

        profile_mgr = self.context.get("dd_profile_mgr")
        if profile_mgr and not profile_mgr.exists(brand, mfr, model):
            reply = QMessageBox.question(
                self,
                "保存档案",
                f"目标组合 {brand}/{mfr}/{model} 不在档案库中。\n是否保存为新档案？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Yes:
                self._save_profile_record(brand, mfr, model)

        svc = self.context.get("dd_service")
        if not svc:
            return

        self._start_worker(svc.disguise, (serial, brand, mfr, model))

    def _on_reset(self) -> None:
        if not self.require_device():
            return

        serial = self._get_serial()
        if not serial:
            return

        svc = self.context.get("dd_service")
        if not svc:
            return

        self._start_worker(svc.reset, (serial,))

    def _start_worker(self, action: Callable, args: tuple) -> None:
        self._set_buttons_enabled(False)
        self._worker = _BackgroundWorker(
            action, args, kwargs={"on_progress": self._thread_safe_log}, parent=self
        )
        self._worker.progress.connect(self._append_log)
        self._worker.finished_ok.connect(self._on_worker_done)
        self._worker.finished_err.connect(self._on_worker_error)
        self._worker.start()

    def _thread_safe_log(self, msg: str) -> None:
        """由 worker 线程调用，通过 signal 安全地更新 GUI"""
        if self._worker:
            self._worker.progress.emit(msg)

    def _on_worker_done(self, state: object) -> None:
        self._set_buttons_enabled(True)
        self._append_log("✓ 操作完成", success=True)
        serial = self._get_serial()
        if serial:
            self._async_refresh_state(serial)
        if hasattr(state, "is_disguised"):
            self._emit_state_event(state)
        self.refresh_completers()

    def _on_worker_error(self, msg: str) -> None:
        self._set_buttons_enabled(True)
        self._append_log(f"✗ {msg}", error=True)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self._btn_disguise.setEnabled(enabled and self.device_connected)
        self._btn_reset.setEnabled(enabled and self.device_connected)
        self._btn_profile.setEnabled(enabled)
        self._btn_save_profile.setEnabled(enabled)

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------

    def _append_log(self, text: str, *, success: bool = False, error: bool = False) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        c = _THEME_COLORS[self._theme]

        fmt = QTextCharFormat()
        if success:
            fmt.setForeground(QColor(c["success"]))
        elif error:
            fmt.setForeground(QColor(c["error"]))
        else:
            fmt.setForeground(QColor(c["fg"]))

        cursor = self._log_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(f"[{ts}] {text}\n", fmt)
        self._log_view.setTextCursor(cursor)
        self._log_view.ensureCursorVisible()

    # ------------------------------------------------------------------
    # 档案弹窗
    # ------------------------------------------------------------------

    def _on_select_profile(self) -> None:
        profile_mgr = self.context.get("dd_profile_mgr")
        if not profile_mgr:
            return

        profiles = profile_mgr.get_all()
        if not profiles:
            QMessageBox.information(self, "档案库", "档案库为空，请先添加档案。")
            return

        dlg = _ProfileSelectDialog(profile_mgr, self._theme, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected:
            p = dlg.selected
            self._combo_brand.setCurrentText(p.brand)
            self._combo_manufacturer.setCurrentText(p.manufacturer)
            self._combo_model.setCurrentText(p.model)
            self.refresh_completers()

    def _on_save_profile(self) -> None:
        brand = self._combo_brand.currentText().strip()
        mfr = self._combo_manufacturer.currentText().strip()
        model = self._combo_model.currentText().strip()
        if not (brand and mfr and model):
            QMessageBox.warning(self, "保存档案", "请先填写品牌、厂商和型号。")
            return

        dlg = _ProfileSaveDialog(brand, mfr, model, self._theme, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            notes = dlg.notes_text
            self._save_profile_record(brand, mfr, model, notes)

    def _save_profile_record(
        self, brand: str, mfr: str, model: str, notes: str = ""
    ) -> None:
        from .models import DeviceProfile

        profile_mgr = self.context.get("dd_profile_mgr")
        if not profile_mgr:
            return
        try:
            profile_mgr.add(
                DeviceProfile(brand=brand, manufacturer=mfr, model=model, notes=notes)
            )
            self.refresh_completers()
            self._append_log(f"档案已保存: {brand}/{mfr}/{model}")
        except ValueError as e:
            self._append_log(f"保存失败: {e}", error=True)

    def _emit_state_event(self, state) -> None:
        """通过 EventBus 通知主框架伪装状态变化（解耦方式，不直接操作主窗口）"""
        event_bus = self.context.get("event_bus")
        if event_bus:
            event_bus.emit(
                "device_disguise.state_changed",
                serial=self._get_serial(),
                is_disguised=state.is_disguised if hasattr(state, "is_disguised") else False,
            )

    def on_activated(self) -> None:
        self.refresh_completers()
        serial = self._get_serial()
        if serial:
            self._async_refresh_state(serial)


# ======================================================================
# 档案选取弹窗
# ======================================================================


class _ProfileSelectDialog(QDialog):
    """档案选取弹窗：搜索 + 列表 + 选取 / 编辑 / 删除"""

    def __init__(self, profile_mgr, theme: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择设备档案")
        self.setMinimumSize(480, 360)
        self.selected = None
        self._profile_mgr = profile_mgr
        self._theme = theme
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索档案...")
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(4)
        self._list_layout.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(self._list_container)
        layout.addWidget(scroll)

        self._populate(self._profile_mgr.get_all())

    def _populate(self, profiles) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        c = _THEME_COLORS[self._theme]
        for p in profiles:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            label_text = f"{p.brand} / {p.manufacturer} / {p.model}"
            select_btn = QPushButton(label_text)
            select_btn.setStyleSheet(
                f"text-align: left; padding: 8px; border-radius: 4px; "
                f"color: {c['fg']}; background: {c['card_bg']};"
            )
            select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if p.notes:
                select_btn.setToolTip(p.notes)
            select_btn.clicked.connect(lambda checked, profile=p: self._select(profile))

            edit_btn = QPushButton("编辑")
            edit_btn.setFixedWidth(48)
            edit_btn.setStyleSheet(
                f"padding: 6px; border-radius: 4px; "
                f"color: {c['accent']}; background: {c['card_bg']}; "
                f"border: 1px solid {c['accent']};"
            )
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.clicked.connect(lambda checked, profile=p: self._edit(profile))

            del_btn = QPushButton("删除")
            del_btn.setFixedWidth(48)
            del_btn.setStyleSheet(
                f"padding: 6px; border-radius: 4px; "
                f"color: {c['error']}; background: {c['card_bg']}; "
                f"border: 1px solid {c['error']};"
            )
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.clicked.connect(lambda checked, profile=p: self._delete(profile))

            row_layout.addWidget(select_btn, stretch=1)
            row_layout.addWidget(edit_btn)
            row_layout.addWidget(del_btn)
            self._list_layout.addWidget(row)

        self._list_layout.addStretch()

    def _get_filtered_profiles(self) -> list:
        text = self._search.text().strip().lower()
        all_profiles = self._profile_mgr.get_all()
        if not text:
            return all_profiles
        return [
            p
            for p in all_profiles
            if text in p.brand.lower()
            or text in p.manufacturer.lower()
            or text in p.model.lower()
            or text in p.notes.lower()
        ]

    def _filter(self, _text: str) -> None:
        self._populate(self._get_filtered_profiles())

    def _select(self, profile) -> None:
        self.selected = profile
        self.accept()

    def _edit(self, profile) -> None:
        dlg = _ProfileEditDialog(profile, self._theme, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_profile = dlg.result_profile
            try:
                self._profile_mgr.update(profile, new_profile)
                self._populate(self._get_filtered_profiles())
            except ValueError as e:
                QMessageBox.warning(self, "编辑失败", str(e))

    def _delete(self, profile) -> None:
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确认删除档案 {profile.brand}/{profile.manufacturer}/{profile.model}？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._profile_mgr.delete(profile)
                self._populate(self._get_filtered_profiles())
            except ValueError as e:
                QMessageBox.warning(self, "删除失败", str(e))


# ======================================================================
# 编辑档案对话框
# ======================================================================


class _ProfileEditDialog(QDialog):
    """编辑设备档案对话框"""

    def __init__(self, profile, theme: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑设备档案")
        self.setMinimumWidth(350)
        self.result_profile = None
        self._original = profile
        self._init_ui(profile, theme)

    def _init_ui(self, profile, theme: str) -> None:
        layout = QVBoxLayout(self)
        c = _THEME_COLORS[theme]

        form = QFormLayout()

        self._brand_input = QLineEdit(profile.brand)
        self._mfr_input = QLineEdit(profile.manufacturer)
        self._model_input = QLineEdit(profile.model)
        self._notes_input = QLineEdit(profile.notes)

        form.addRow("品牌:", self._brand_input)
        form.addRow("厂商:", self._mfr_input)
        form.addRow("型号:", self._model_input)
        form.addRow("备注:", self._notes_input)

        layout.addLayout(form)

        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("保存")
        ok_btn.setStyleSheet(
            f"background-color: {c['btn_primary_bg']}; "
            f"color: {c['btn_primary_fg']}; font-weight: bold; "
            f"border-radius: 6px; padding: 6px 16px;"
        )
        ok_btn.clicked.connect(self._on_ok)

        btn_bar.addWidget(cancel_btn)
        btn_bar.addWidget(ok_btn)
        layout.addLayout(btn_bar)

    def _on_ok(self) -> None:
        from .models import DeviceProfile

        brand = self._brand_input.text().strip()
        mfr = self._mfr_input.text().strip()
        model = self._model_input.text().strip()
        notes = self._notes_input.text().strip()

        if not (brand and mfr and model):
            QMessageBox.warning(self, "编辑档案", "品牌、厂商和型号不能为空。")
            return

        self.result_profile = DeviceProfile(
            brand=brand, manufacturer=mfr, model=model, notes=notes
        )
        self.accept()


# ======================================================================
# 保存对话框
# ======================================================================


class _ProfileSaveDialog(QDialog):
    """保存档案对话框"""

    def __init__(self, brand: str, mfr: str, model: str, theme: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("保存设备档案")
        self.setMinimumWidth(350)
        self.notes_text = ""
        self._init_ui(brand, mfr, model, theme)

    def _init_ui(self, brand: str, mfr: str, model: str, theme: str) -> None:
        layout = QVBoxLayout(self)
        c = _THEME_COLORS[theme]

        form = QFormLayout()
        form.addRow("品牌:", QLabel(brand))
        form.addRow("厂商:", QLabel(mfr))
        form.addRow("型号:", QLabel(model))

        self._notes_input = QLineEdit()
        self._notes_input.setPlaceholderText("可选备注...")
        form.addRow("备注:", self._notes_input)

        layout.addLayout(form)

        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("保存")
        ok_btn.setStyleSheet(
            f"background-color: {c['btn_primary_bg']}; "
            f"color: {c['btn_primary_fg']}; font-weight: bold; "
            f"border-radius: 6px; padding: 6px 16px;"
        )
        ok_btn.clicked.connect(self._on_ok)

        btn_bar.addWidget(cancel_btn)
        btn_bar.addWidget(ok_btn)
        layout.addLayout(btn_bar)

    def _on_ok(self) -> None:
        self.notes_text = self._notes_input.text().strip()
        self.accept()
