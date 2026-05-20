"""设备伪装工具 — GUI 页面（方案 A：左右分栏）"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.base_tab import BaseTab
from toolkit.gui.toolkit_dialog import (
    ToolkitDialog,
    confirm_dialog,
    info_dialog,
    three_button_dialog,
    warning_dialog,
)



from . import strings_gui as sg

logger = logging.getLogger(__name__)


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

    tab_title = sg.TAB_TITLE
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

        left = self._build_left_panel()
        root.addWidget(left)

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
        group = QGroupBox(sg.GROUP_DEVICE_STATUS)
        form = QFormLayout(group)
        form.setSpacing(6)

        self._lbl_brand = QLabel(sg.DASH)
        self._lbl_manufacturer = QLabel(sg.DASH)
        self._lbl_model = QLabel(sg.DASH)
        self._lbl_status = QLabel(sg.STATUS_NOT_CONNECTED)
        self._lbl_disguise = QLabel(sg.DASH)

        form.addRow(sg.LABEL_BRAND + ":", self._lbl_brand)
        form.addRow(sg.LABEL_MANUFACTURER + ":", self._lbl_manufacturer)
        form.addRow(sg.LABEL_MODEL + ":", self._lbl_model)
        form.addRow(sg.LABEL_CONNECTION + ":", self._lbl_status)
        form.addRow(sg.LABEL_DISGUISE + ":", self._lbl_disguise)

        return group

    def _build_input_group(self) -> QGroupBox:
        group = QGroupBox(sg.GROUP_DISGUISE_SETTINGS)
        form = QFormLayout(group)
        form.setSpacing(8)

        self._combo_brand = self._make_combo(sg.LABEL_BRAND, "ro.product.odm.brand")
        self._combo_manufacturer = self._make_combo(sg.LABEL_MANUFACTURER, "ro.product.odm.manufacturer")
        self._combo_model = self._make_combo(sg.LABEL_MODEL, "ro.product.odm.model")

        form.addRow(sg.LABEL_TARGET_BRAND + ":", self._combo_brand)
        form.addRow(sg.LABEL_TARGET_MANUFACTURER + ":", self._combo_manufacturer)
        form.addRow(sg.LABEL_TARGET_MODEL + ":", self._combo_model)

        return group

    def _make_combo(self, placeholder: str, prop_name: str) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.lineEdit().setPlaceholderText(sg.PLACEHOLDER_PROP_HINT_FMT.format(prop_name))
        combo.lineEdit().textChanged.connect(self._on_input_changed)
        return combo

    def _build_button_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self._btn_profile = QPushButton(sg.BTN_SELECT_PROFILE)
        self._btn_profile.clicked.connect(self._on_select_profile)

        self._btn_save_profile = QPushButton(sg.BTN_SAVE_PROFILE)
        self._btn_save_profile.clicked.connect(self._on_save_profile)

        self._btn_import_config = QPushButton(sg.BTN_IMPORT_CONFIG)
        self._btn_import_config.setToolTip(sg.TOOLTIP_IMPORT_CONFIG)
        self._btn_import_config.clicked.connect(self._on_import_config)

        self._btn_disguise = QPushButton(sg.BTN_DISGUISE)
        self._btn_disguise.setObjectName("primaryBtn")
        self._btn_disguise.setEnabled(False)
        self._btn_disguise.clicked.connect(self._on_disguise)

        self._btn_reset = QPushButton(sg.BTN_RESET)
        self._btn_reset.setObjectName("secondaryBtn")
        self._btn_reset.setEnabled(False)
        self._btn_reset.clicked.connect(self._on_reset)

        bar.addWidget(self._btn_profile)
        bar.addWidget(self._btn_save_profile)
        bar.addWidget(self._btn_import_config)
        bar.addStretch()
        bar.addWidget(self._btn_disguise)
        bar.addWidget(self._btn_reset)

        return bar

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------

    def set_theme(self, theme: str) -> None:
        self._theme = theme

    # ------------------------------------------------------------------
    # 设备状态感知
    # ------------------------------------------------------------------

    def on_devices_changed(self, devices: list[str]) -> None:
        super().on_devices_changed(devices)
        has_device = len(devices) > 0
        self._btn_reset.setEnabled(has_device)
        self._on_input_changed()

        if has_device:
            self._lbl_status.setText(sg.STATUS_CONNECTED_FMT.format(len(devices)))
            self._async_refresh_state(devices[0])
        else:
            self._lbl_status.setText(sg.STATUS_NOT_CONNECTED)
            self._lbl_brand.setText(sg.DASH)
            self._lbl_manufacturer.setText(sg.DASH)
            self._lbl_model.setText(sg.DASH)
            self._lbl_disguise.setText(sg.DASH)

    def _refresh_device_state(self, state) -> None:
        """更新 UI 上的设备状态显示（必须在 GUI 线程调用）"""
        self._lbl_brand.setText(state.current_brand or sg.DASH)
        self._lbl_manufacturer.setText(state.current_manufacturer or sg.DASH)
        self._lbl_model.setText(state.current_model or sg.DASH)
        self._lbl_disguise.setText(sg.STATUS_DISGUISED if state.is_disguised else sg.STATUS_NOT_DISGUISED)

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
            choice = three_button_dialog(
                self,
                sg.DLG_TITLE_SAVE_PROFILE,
                sg.MSG_PROFILE_NOT_EXISTS_FMT.format(brand, mfr, model),
                sg.BTN_SAVE, sg.BTN_DONT_SAVE, sg.BTN_CANCEL,
            )
            if choice == 2:
                return
            if choice == 0:
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
        self._append_log(sg.LOG_ACTION_COMPLETE, success=True)
        serial = self._get_serial()
        if serial:
            self._async_refresh_state(serial)
        if hasattr(state, "is_disguised"):
            self._emit_state_event(state)
        self.refresh_completers()

    def _on_worker_error(self, msg: str) -> None:
        self._set_buttons_enabled(True)
        self._append_log(sg.LOG_ACTION_FAILED_FMT.format(msg), error=True)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self._btn_disguise.setEnabled(enabled and self.device_connected)
        self._btn_reset.setEnabled(enabled and self.device_connected)
        self._btn_profile.setEnabled(enabled)
        self._btn_save_profile.setEnabled(enabled)
        self._btn_import_config.setEnabled(enabled)

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------

    def _append_log(self, text: str, *, success: bool = False, error: bool = False, ok: bool | None = None) -> None:
        if ok is not None:
            level = "success" if ok else "error"
        else:
            level = "success" if success else ("error" if error else "info")
        self._log(text, level=level)

    # ------------------------------------------------------------------
    # 档案弹窗
    # ------------------------------------------------------------------

    def _on_select_profile(self) -> None:
        profile_mgr = self.context.get("dd_profile_mgr")
        if not profile_mgr:
            return

        profiles = profile_mgr.get_all()
        if not profiles:
            info_dialog(self, sg.DLG_TITLE_LIBRARY, sg.MSG_PROFILE_LIBRARY_EMPTY)
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
            warning_dialog(self, sg.DLG_TITLE_SAVE_PROFILE, sg.MSG_FILL_ALL_FIELDS)
            return

        dlg = _ProfileSaveDialog(brand, mfr, model, self._theme, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            notes = dlg.notes_text
            self._save_profile_record(brand, mfr, model, notes)

    def _on_import_config(self) -> None:
        profile_mgr = self.context.get("dd_profile_mgr")
        if not profile_mgr:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            sg.DLG_TITLE_IMPORT_FILE,
            "",
            sg.FILE_FILTER_JSON,
        )
        if not path:
            return
        try:
            result = profile_mgr.import_from(path)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            warning_dialog(self, sg.DLG_TITLE_IMPORT_FAILED, str(e))
            self._append_log(sg.LOG_IMPORT_FAILED_FMT.format(e), ok=False)
            return
        except Exception as e:
            warning_dialog(self, sg.DLG_TITLE_IMPORT_FAILED, str(e))
            self._append_log(sg.LOG_IMPORT_FAILED_FMT.format(e), ok=False)
            return
        msg = sg.MSG_IMPORT_RESULT_FMT.format(result['imported'], result['skipped'])
        info_dialog(self, sg.DLG_TITLE_IMPORT_COMPLETE, msg)
        self._append_log(
            sg.LOG_IMPORT_SUCCEEDED_FMT.format(result['imported'], result['skipped'])
        )
        self.refresh_completers()

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
            self._append_log(sg.LOG_PROFILE_SAVED_FMT.format(brand, mfr, model))
        except ValueError as e:
            self._append_log(sg.LOG_SAVE_FAILED_FMT.format(e), error=True)

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


class _ProfileSelectDialog(ToolkitDialog):
    """档案选取弹窗：搜索 + 列表 + 选取 / 编辑 / 删除"""

    def __init__(self, profile_mgr, theme: str, parent=None):
        super().__init__(sg.DLG_TITLE_SELECT_PROFILE, parent, min_width=480)
        self.setMinimumHeight(360)
        self.selected = None
        self._profile_mgr = profile_mgr
        self._theme = theme
        self._init_ui()

    def _init_ui(self) -> None:
        self._search = QLineEdit()
        self._search.setPlaceholderText(sg.PLACEHOLDER_SEARCH_PROFILE)
        self._search.textChanged.connect(self._filter)
        self.content_layout.addWidget(self._search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(4)
        self._list_layout.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(self._list_container)
        self.content_layout.addWidget(scroll)

        self._populate(self._profile_mgr.get_all())

    def _populate(self, profiles) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for p in profiles:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            label_text = f"{p.brand} / {p.manufacturer} / {p.model}"
            select_btn = QPushButton(label_text)
            select_btn.setObjectName("profileSelectBtn")
            select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if p.notes:
                select_btn.setToolTip(p.notes)
            select_btn.clicked.connect(lambda checked, profile=p: self._select(profile))

            edit_btn = QPushButton(sg.BTN_EDIT)
            edit_btn.setObjectName("secondaryBtn")
            edit_btn.setFixedWidth(64)
            edit_btn.setStyleSheet("padding: 4px 8px;")
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.clicked.connect(lambda checked, profile=p: self._edit(profile))

            del_btn = QPushButton(sg.BTN_DELETE)
            del_btn.setObjectName("dangerBtn")
            del_btn.setFixedWidth(64)
            del_btn.setStyleSheet("padding: 4px 8px;")
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
                warning_dialog(self, sg.DLG_TITLE_EDIT_FAILED, str(e))

    def _delete(self, profile) -> None:
        ok = confirm_dialog(
            self,
            sg.DLG_TITLE_CONFIRM_DELETE,
            sg.MSG_CONFIRM_DELETE_FMT.format(profile.brand, profile.manufacturer, profile.model),
            confirm_text=sg.BTN_DELETE, danger=True,
        )
        if ok:
            try:
                self._profile_mgr.delete(profile)
                self._populate(self._get_filtered_profiles())
            except ValueError as e:
                warning_dialog(self, sg.DLG_TITLE_DELETE_FAILED, str(e))


# ======================================================================
# 编辑档案对话框
# ======================================================================


class _ProfileEditDialog(ToolkitDialog):
    """编辑设备档案对话框"""

    def __init__(self, profile, theme: str, parent=None):
        super().__init__(sg.DLG_TITLE_EDIT_PROFILE, parent, min_width=380)
        self.result_profile = None
        self._original = profile
        self._init_ui(profile)

    def _init_ui(self, profile) -> None:
        form = QFormLayout()

        self._brand_input = QLineEdit(profile.brand)
        self._mfr_input = QLineEdit(profile.manufacturer)
        self._model_input = QLineEdit(profile.model)
        self._notes_input = QLineEdit(profile.notes)

        form.addRow(sg.LABEL_BRAND + ":", self._brand_input)
        form.addRow(sg.LABEL_MANUFACTURER + ":", self._mfr_input)
        form.addRow(sg.LABEL_MODEL + ":", self._model_input)
        form.addRow(sg.LABEL_NOTES + ":", self._notes_input)

        self.content_layout.addLayout(form)

        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        cancel_btn = QPushButton(sg.BTN_CANCEL)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton(sg.BTN_SAVE)
        ok_btn.setObjectName("primaryBtn")
        ok_btn.clicked.connect(self._on_ok)

        btn_bar.addWidget(cancel_btn)
        btn_bar.addWidget(ok_btn)
        self.content_layout.addLayout(btn_bar)

    def _on_ok(self) -> None:
        from .models import DeviceProfile

        brand = self._brand_input.text().strip()
        mfr = self._mfr_input.text().strip()
        model = self._model_input.text().strip()
        notes = self._notes_input.text().strip()

        if not (brand and mfr and model):
            warning_dialog(self, sg.DLG_TITLE_EDIT_PROFILE, sg.MSG_EMPTY_FIELDS)
            return

        self.result_profile = DeviceProfile(
            brand=brand, manufacturer=mfr, model=model, notes=notes
        )
        self.accept()


# ======================================================================
# 保存对话框
# ======================================================================


class _ProfileSaveDialog(ToolkitDialog):
    """保存档案对话框"""

    def __init__(self, brand: str, mfr: str, model: str, theme: str, parent=None):
        super().__init__(sg.DLG_TITLE_SAVE_PROFILE, parent, min_width=380)
        self.notes_text = ""
        self._init_ui(brand, mfr, model)

    def _init_ui(self, brand: str, mfr: str, model: str) -> None:
        form = QFormLayout()
        form.addRow(sg.LABEL_BRAND + ":", QLabel(brand))
        form.addRow(sg.LABEL_MANUFACTURER + ":", QLabel(mfr))
        form.addRow(sg.LABEL_MODEL + ":", QLabel(model))

        self._notes_input = QLineEdit()
        self._notes_input.setPlaceholderText(sg.PLACEHOLDER_NOTES)
        form.addRow(sg.LABEL_NOTES + ":", self._notes_input)

        self.content_layout.addLayout(form)

        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        cancel_btn = QPushButton(sg.BTN_CANCEL)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton(sg.BTN_SAVE)
        ok_btn.setObjectName("primaryBtn")
        ok_btn.clicked.connect(self._on_ok)

        btn_bar.addWidget(cancel_btn)
        btn_bar.addWidget(ok_btn)
        self.content_layout.addLayout(btn_bar)

    def _on_ok(self) -> None:
        self.notes_text = self._notes_input.text().strip()
        self.accept()
