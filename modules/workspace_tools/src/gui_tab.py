"""性能配置对比 — GUI 页面（含 gameperfconfig 配置对比子页）"""

from __future__ import annotations

import os
import threading
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.base_tab import BaseTab
from toolkit.gui.toolkit_dialog import (
    confirm_dialog,
    info_dialog,
    warning_dialog,
)

from . import strings_gui as s
from .gameperf_diff_errors import DiffValidationError, GamePerfDevicePullError
from .gameperf_diff_models import DiffItem
from .gameperf_diff_service import GamePerfConfigDiffService
from .gameperf_xml import is_valid_gameperf_config_filename


class _DiffThread(QThread):
    """后台执行语义对比。"""

    finished_ok = pyqtSignal(list)
    finished_err = pyqtSignal(str)

    def __init__(self, svc: GamePerfConfigDiffService, cancel_event: threading.Event) -> None:
        super().__init__()
        self._svc = svc
        self._cancel = cancel_event

    def run(self) -> None:
        try:
            items = self._svc.run_diff(self._cancel)
            self.finished_ok.emit(items)
        except Exception as e:
            self.finished_err.emit(str(e))


class _PullThread(QThread):
    """后台从设备拉取对比文件。"""

    log_msg = pyqtSignal(str)
    finished_ok = pyqtSignal()
    finished_err = pyqtSignal(str)

    def __init__(
        self,
        svc: GamePerfConfigDiffService,
        serial: str,
        cancel_event: threading.Event,
    ) -> None:
        super().__init__()
        self._svc = svc
        self._serial = serial
        self._cancel = cancel_event

    def run(self) -> None:
        try:

            def on_progress(m: str) -> None:
                self.log_msg.emit(m)

            self._svc.add_comparator_from_device(
                self._serial,
                cancel_event=self._cancel,
                on_progress=on_progress,
            )
            self.finished_ok.emit()
        except GamePerfDevicePullError as e:
            self.finished_err.emit(e.user_message)
        except Exception as e:
            self.finished_err.emit(str(e))


class _ComparatorDropArea(QFrame):
    """接受 gameperfconfig*.xml 拖拽。"""

    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("comparatorDropArea")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        if mime and mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if path and is_valid_gameperf_config_filename(os.path.basename(path)):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        mime = event.mimeData()
        if mime and mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if path and is_valid_gameperf_config_filename(os.path.basename(path)):
                    self.file_dropped.emit(path)
                    event.acceptProposedAction()
                    return
        event.ignore()


class WorkspaceToolsTab(BaseTab):
    """性能配置对比 Tab：说明页 + gameperfconfig 多文件对比与合并。"""

    tab_title = s.TAB_TITLE
    tab_icon = s.TAB_ICON

    def __init__(self, context: dict | None = None, parent=None) -> None:
        super().__init__(context, parent)
        self._gp_svc: GamePerfConfigDiffService | None = (
            (context or {}).get("wo_gameperf_diff_service")
        )
        self._devices: list[str] = []
        self._diff_thread: _DiffThread | None = None
        self._pull_thread: _PullThread | None = None
        self._diff_cancel = threading.Event()
        self._pull_cancel = threading.Event()
        self._pending_save_stat: os.stat_result | None = None
        self._last_items: list[DiffItem] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        self._build_intro_tab()
        self._build_diff_tab()

    def _build_intro_tab(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(16, 16, 16, 16)
        title = QLabel(s.INTRO_TITLE)
        title.setProperty("class", "sectionTitleBlue")
        lay.addWidget(title)
        body = QLabel(s.MSG_INTRO_BODY)
        body.setWordWrap(True)
        body.setProperty("class", "fieldLabel")
        lay.addWidget(body)
        lay.addStretch()
        self._tabs.addTab(page, s.TAB_INTRO_LABEL)

    def _build_diff_tab(self) -> None:
        page = QWidget()
        page_lay = QVBoxLayout(page)
        page_lay.setContentsMargins(4, 4, 4, 4)

        if self._gp_svc is None:
            page_lay.addWidget(QLabel(s.MSG_SERVICE_UNAVAILABLE))
            self._tabs.addTab(page, s.TAB_DIFF_LABEL)
            return

        # —— 左栏：基准、对比文件、操作、摘要、日志 ——
        left_col = QWidget()
        left_col.setMinimumWidth(300)
        left_lay = QVBoxLayout(left_col)
        left_lay.setContentsMargins(0, 0, 6, 0)

        base_box = QGroupBox(s.GROUP_BASELINE)
        base_lay = QHBoxLayout(base_box)
        self._baseline_edit = QLineEdit()
        self._baseline_edit.setPlaceholderText(s.PLACEHOLDER_BASELINE)
        btn_browse_base = QPushButton(s.BTN_BROWSE)
        btn_browse_base.clicked.connect(self._on_browse_baseline)
        base_lay.addWidget(self._baseline_edit, 1)
        base_lay.addWidget(btn_browse_base)
        left_lay.addWidget(base_box)

        cmp_box = QGroupBox(s.GROUP_COMPARATORS)
        cmp_lay = QVBoxLayout(cmp_box)
        row = QHBoxLayout()
        self._cmp_list = QListWidget()
        self._cmp_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        btn_add = QPushButton(s.BTN_ADD_LOCAL)
        btn_add.clicked.connect(self._on_add_comparator)
        btn_rm = QPushButton(s.BTN_REMOVE)
        btn_rm.clicked.connect(self._on_remove_comparator)
        btn_as_base = QPushButton(s.BTN_SET_BASELINE)
        btn_as_base.clicked.connect(self._on_set_baseline_from_list)
        btn_device = QPushButton(s.BTN_ADD_FROM_DEVICE)
        btn_device.clicked.connect(self._on_pull_device)
        row.addWidget(btn_add)
        row.addWidget(btn_rm)
        row.addWidget(btn_as_base)
        row.addWidget(btn_device)
        row.addStretch()
        cmp_lay.addLayout(row)
        self._cmp_list.setMinimumHeight(72)
        self._cmp_list.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        cmp_lay.addWidget(self._cmp_list, 1)
        drop = _ComparatorDropArea()
        drop.file_dropped.connect(self._on_drop_comparator)
        drop.setMinimumHeight(48)
        drop_l = QVBoxLayout(drop)
        drop_l.addWidget(QLabel(s.HINT_DROP))
        cmp_lay.addWidget(drop)
        left_lay.addWidget(cmp_box, 1)

        op_row = QHBoxLayout()
        op_row.addWidget(QLabel(s.LABEL_ACTIVE_COMP))
        self._active_combo = QComboBox()
        self._active_combo.currentIndexChanged.connect(self._on_active_comparator_changed)
        op_row.addWidget(self._active_combo, 1)
        self._btn_start_diff = QPushButton(s.BTN_START_DIFF)
        self._btn_start_diff.clicked.connect(self._on_start_diff)
        self._btn_cancel_diff = QPushButton(s.BTN_CANCEL_DIFF)
        self._btn_cancel_diff.setEnabled(False)
        self._btn_cancel_diff.clicked.connect(self._on_cancel_diff)
        op_row.addWidget(self._btn_start_diff)
        op_row.addWidget(self._btn_cancel_diff)
        left_lay.addLayout(op_row)

        sum_box = QGroupBox(s.GROUP_SUMMARY)
        sum_lay = QVBoxLayout(sum_box)
        self._summary_list = QListWidget()
        self._summary_list.setMaximumHeight(72)
        sum_lay.addWidget(self._summary_list)
        left_lay.addWidget(sum_box)

        pull_row = QHBoxLayout()
        self._btn_cancel_pull = QPushButton(s.BTN_CANCEL_PULL)
        self._btn_cancel_pull.setEnabled(False)
        self._btn_cancel_pull.clicked.connect(self._on_cancel_pull)
        pull_row.addWidget(self._btn_cancel_pull)
        pull_row.addStretch()
        left_lay.addLayout(pull_row)

        # —— 右栏：差异明细（占满高度）+ 底部操作按钮 ——
        right_col = QWidget()
        right_col.setMinimumWidth(360)
        right_lay = QVBoxLayout(right_col)
        right_lay.setContentsMargins(6, 0, 0, 0)

        tree_box = QGroupBox(s.GROUP_DIFF_DETAIL)
        tree_lay = QVBoxLayout(tree_box)
        self._diff_tree = QTreeWidget()
        self._diff_tree.setObjectName("gameperfDiffTree")
        self._diff_tree.setHeaderLabels([s.TABLE_HEADER_SEMANTIC_PATH, s.TABLE_HEADER_BASELINE_SIDE, s.TABLE_HEADER_COMP_SIDE])
        self._diff_tree.setMinimumHeight(200)
        self._diff_tree.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._diff_tree.setRootIsDecorated(False)
        self._diff_tree.setUniformRowHeights(False)
        hdr = self._diff_tree.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setMinimumSectionSize(80)
        self._diff_tree.setColumnWidth(1, 100)
        self._diff_tree.setColumnWidth(2, 100)
        # QSS 样式由全局 styles.py 通过 #gameperfDiffTree 管理
        tree_lay.addWidget(self._diff_tree, 1)
        btn_row = QHBoxLayout()
        self._btn_adopt_base = QPushButton(s.BTN_ADOPT_BASE)
        self._btn_adopt_comp = QPushButton(s.BTN_ADOPT_COMP)
        self._btn_undo = QPushButton(s.BTN_UNDO)
        self._btn_reset = QPushButton(s.BTN_RESET)
        self._btn_save = QPushButton(s.BTN_SAVE_AS)
        self._btn_adopt_base.clicked.connect(lambda: self._on_adopt("baseline"))
        self._btn_adopt_comp.clicked.connect(lambda: self._on_adopt("comparator"))
        self._btn_undo.clicked.connect(self._on_undo)
        self._btn_reset.clicked.connect(self._on_reset)
        self._btn_save.clicked.connect(self._on_save_as)
        btn_row.addWidget(self._btn_adopt_base)
        btn_row.addWidget(self._btn_adopt_comp)
        btn_row.addWidget(self._btn_undo)
        btn_row.addWidget(self._btn_reset)
        btn_row.addWidget(self._btn_save)
        btn_row.addStretch()
        tree_lay.addLayout(btn_row)
        right_lay.addWidget(tree_box, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("gameperfConfigDiffSplitter")
        splitter.addWidget(left_col)
        splitter.addWidget(right_col)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([400, 720])

        page_lay.addWidget(splitter, 1)
        self._tabs.addTab(page, s.TAB_DIFF_LABEL)
        self._update_buttons_state()

    def _append_log(self, msg: str) -> None:
        if "失败" in msg or "✗" in msg:
            level = "error"
        elif "✓" in msg or "成功" in msg or "完成" in msg:
            level = "success"
        else:
            level = "info"
        self._log(msg, level=level)

    def _update_buttons_state(self) -> None:
        has_svc = self._gp_svc is not None
        busy = (self._diff_thread and self._diff_thread.isRunning()) or (
            self._pull_thread and self._pull_thread.isRunning()
        )
        if has_svc:
            n_cmp = self._gp_svc.comparator_count
            has_base = self._gp_svc.get_session() is not None
            self._btn_start_diff.setEnabled(has_base and n_cmp >= 1 and not busy)
        self._btn_cancel_diff.setEnabled(bool(self._diff_thread and self._diff_thread.isRunning()))
        self._btn_cancel_pull.setEnabled(bool(self._pull_thread and self._pull_thread.isRunning()))

    def _refresh_comparator_ui(self) -> None:
        if not self._gp_svc:
            return
        self._cmp_list.clear()
        self._active_combo.blockSignals(True)
        self._active_combo.clear()
        sess = self._gp_svc.get_session()
        if sess:
            for i, (prov, _p) in enumerate(sess.comparators):
                self._cmp_list.addItem(QListWidgetItem(prov.display_label))
                self._active_combo.addItem(prov.display_label, i)
        self._active_combo.blockSignals(False)
        self._update_buttons_state()

    def _on_browse_baseline(self) -> None:
        if not self._gp_svc:
            return
        path, _ = QFileDialog.getOpenFileName(
            self.window(),
            s.DLG_TITLE_SELECT_BASELINE,
            "",
            s.FILE_FILTER_XML,
        )
        if not path:
            return
        if not is_valid_gameperf_config_filename(os.path.basename(path)):
            warning_dialog(self.window(), s.DLG_TITLE_INVALID_FILENAME, s.MSG_INVALID_FILENAME_BASELINE)
            return
        try:
            self._gp_svc.load_session(path)
            self._baseline_edit.setText(path)
            self._diff_tree.clear()
            self._summary_list.clear()
            self._last_items.clear()
            self._append_log(s.LOG_BASELINE_LOADED_FMT.format(path=path))
        except Exception as e:
            warning_dialog(self.window(), s.DLG_TITLE_LOAD_FAILED, str(e))
        self._refresh_comparator_ui()

    def _on_add_comparator(self) -> None:
        if not self._gp_svc:
            return
        if self._gp_svc.get_session() is None:
            info_dialog(self.window(), s.DLG_TITLE_HINT, s.MSG_SELECT_BASELINE_FIRST)
            return
        path, _ = QFileDialog.getOpenFileName(
            self.window(),
            s.DLG_TITLE_ADD_COMP,
            "",
            s.FILE_FILTER_XML,
        )
        if path:
            self._add_comparator_path(path)

    def _on_drop_comparator(self, path: str) -> None:
        if not self._gp_svc or self._gp_svc.get_session() is None:
            info_dialog(self.window(), s.DLG_TITLE_HINT, s.MSG_SELECT_BASELINE_FIRST)
            return
        self._add_comparator_path(path)

    def _add_comparator_path(self, path: str) -> None:
        assert self._gp_svc is not None
        self._gp_svc.clear_parse_errors()
        self._gp_svc.add_comparator_local(path)
        for err in self._gp_svc.get_parse_errors():
            self._append_log(err)
        self._refresh_comparator_ui()

    def _on_remove_comparator(self) -> None:
        if not self._gp_svc:
            return
        row = self._cmp_list.currentRow()
        if row < 0:
            return
        try:
            self._gp_svc.remove_comparator(row)
        except DiffValidationError as e:
            warning_dialog(self.window(), s.DLG_TITLE_REMOVE_FAILED, str(e))
        self._diff_tree.clear()
        self._summary_list.clear()
        self._refresh_comparator_ui()

    def _on_set_baseline_from_list(self) -> None:
        if not self._gp_svc:
            return
        row = self._cmp_list.currentRow()
        if row < 0:
            info_dialog(self.window(), s.DLG_TITLE_HINT, s.MSG_SELECT_COMPARATOR_FIRST)
            return
        try:
            self._gp_svc.set_baseline_from_comparator(row)
            self._baseline_edit.setText(self._gp_svc.get_session().baseline_path if self._gp_svc.get_session() else "")
            self._append_log(s.LOG_SET_BASELINE)
        except Exception as e:
            warning_dialog(self.window(), s.DLG_TITLE_OPERATION_FAILED, str(e))
        self._diff_tree.clear()
        self._summary_list.clear()
        self._refresh_comparator_ui()

    def _on_active_comparator_changed(self, _idx: int) -> None:
        if not self._gp_svc:
            return
        ci = self._active_combo.currentData()
        if ci is None:
            return
        try:
            self._gp_svc.set_active_comparator(int(ci))
        except DiffValidationError:
            return
        self._populate_diff_tree(self._gp_svc.get_diff_for_comparator(int(ci)))

    def _on_start_diff(self) -> None:
        if not self._gp_svc:
            return
        self._diff_cancel.clear()
        self._diff_thread = _DiffThread(self._gp_svc, self._diff_cancel)
        self._diff_thread.finished_ok.connect(self._on_diff_ok)
        self._diff_thread.finished_err.connect(self._on_diff_err)
        self._diff_thread.finished.connect(self._on_diff_thread_finished)
        self._append_log(s.LOG_START_DIFF)
        self._btn_start_diff.setEnabled(False)
        self._btn_cancel_diff.setEnabled(True)
        self._diff_thread.start()

    def _on_cancel_diff(self) -> None:
        self._diff_cancel.set()
        self._append_log(s.LOG_CANCEL_DIFF_REQUESTED)

    def _on_diff_ok(self, items: list) -> None:
        assert self._gp_svc is not None
        self._last_items = list(items)
        ci = self._active_combo.currentData()
        if ci is not None:
            self._populate_diff_tree(self._gp_svc.get_diff_for_comparator(int(ci)))
        self._summary_list.clear()
        for label, n in self._gp_svc.diff_counts_summary():
            self._summary_list.addItem(s.SUMMARY_DIFF_COUNT_FMT.format(label=label, n=n) if n else s.SUMMARY_NO_DIFF.format(label=label))
        self._append_log(s.LOG_DIFF_COMPLETE)

    def _on_diff_err(self, msg: str) -> None:
        self._append_log(s.LOG_DIFF_FAILED_FMT.format(msg=msg))
        warning_dialog(self.window(), s.DLG_TITLE_DIFF_FAILED, msg)

    def _on_diff_thread_finished(self) -> None:
        self._btn_cancel_diff.setEnabled(False)
        self._update_buttons_state()

    def _populate_diff_tree(self, items: list[DiffItem]) -> None:
        self._diff_tree.clear()
        for it in items:
            twi = QTreeWidgetItem(
                [
                    it.semantic_path,
                    it.left_snippet or s.DASH,
                    it.right_snippet or s.DASH,
                ]
            )
            twi.setData(0, Qt.ItemDataRole.UserRole, it.id)
            twi.setData(0, Qt.ItemDataRole.UserRole + 1, it.mergeable)
            self._diff_tree.addTopLevelItem(twi)

    def _on_adopt(self, side: str) -> None:
        if not self._gp_svc:
            return
        twi = self._diff_tree.currentItem()
        if twi is None:
            info_dialog(self.window(), s.DLG_TITLE_HINT, s.MSG_SELECT_DIFF_ROW)
            return
        did = twi.data(0, Qt.ItemDataRole.UserRole)
        mergeable = twi.data(0, Qt.ItemDataRole.UserRole + 1)
        if not did or not mergeable:
            info_dialog(self.window(), s.DLG_TITLE_HINT, s.MSG_NOT_MERGEABLE)
            return
        ci = self._active_combo.currentData()
        if ci is None:
            return
        try:
            self._gp_svc.apply_merge(str(did), side, int(ci))
            self._append_log(s.LOG_ADOPT_FMT.format(side=side, path=twi.text(0)))
        except Exception as e:
            warning_dialog(self.window(), s.DLG_TITLE_ADOPT_FAILED, str(e))

    def _on_undo(self) -> None:
        if not self._gp_svc:
            return
        ok, detail = self._gp_svc.undo_merge()
        if ok:
            if detail:
                self._append_log(s.LOG_UNDO_WITH_DETAIL_FMT.format(detail=detail))
            else:
                self._append_log(s.LOG_UNDO)
        else:
            self._append_log(s.LOG_NOTHING_TO_UNDO)

    def _on_reset(self) -> None:
        if not self._gp_svc:
            return
        self._gp_svc.reset_merge()
        self._append_log(s.LOG_RESET_MERGE)

    def _on_save_as(self) -> None:
        if not self._gp_svc:
            return
        dirty = self._gp_svc.get_merge_dirty()
        path, _ = QFileDialog.getSaveFileName(
            self.window(),
            s.DLG_TITLE_SAVE_AS,
            "",
            s.FILE_FILTER_XML,
        )
        if not path:
            return
        if not is_valid_gameperf_config_filename(os.path.basename(path)):
            warning_dialog(self.window(), s.DLG_TITLE_INVALID_FILENAME, s.MSG_INVALID_FILENAME_SAVE)
            return
        initial_stat = None
        if os.path.isfile(path):
            initial_stat = GamePerfConfigDiffService.stat_path(path)
        overwrite = os.path.isfile(path)
        msg = s.MSG_CONFIRM_SAVE_FMT.format(
            path=path,
            will_overwrite=s.MSG_FILE_OVERWRITE_YES if overwrite else s.MSG_FILE_OVERWRITE_NO,
            dirty=s.MSG_DIRTY_YES if dirty else s.MSG_DIRTY_NO,
        )
        if not confirm_dialog(self.window(), s.DLG_TITLE_CONFIRM_SAVE, msg):
            return
        if initial_stat is not None:
            now_stat = GamePerfConfigDiffService.stat_path(path)
            if now_stat is not None and (
                now_stat.st_mtime != initial_stat.st_mtime
                or now_stat.st_size != initial_stat.st_size
            ):
                if not confirm_dialog(
                    self.window(), s.DLG_TITLE_FILE_CHANGED,
                    s.MSG_FILE_CHANGED,
                ):
                    return
        try:
            self._gp_svc.save_merged_as(path, atomic=True)
            self._append_log(s.LOG_SAVED_FMT.format(path=path))
            info_dialog(self.window(), s.DLG_TITLE_COMPLETE, s.MSG_SAVE_SUCCESS)
        except Exception as e:
            warning_dialog(self.window(), s.DLG_TITLE_SAVE_FAILED, str(e))

    def _on_pull_device(self) -> None:
        if not self.require_device() or not self._gp_svc:
            return
        if self._gp_svc.get_session() is None:
            info_dialog(self.window(), s.DLG_TITLE_HINT, s.MSG_SELECT_BASELINE_FIRST)
            return
        serial = self._devices[0] if self._devices else ""
        if not serial:
            warning_dialog(self.window(), s.DLG_TITLE_DEVICE, s.MSG_NO_SERIAL)
            return
        self._pull_cancel.clear()
        self._pull_thread = _PullThread(self._gp_svc, serial, self._pull_cancel)
        self._pull_thread.log_msg.connect(self._append_log)
        self._pull_thread.finished_ok.connect(self._on_pull_ok)
        self._pull_thread.finished_err.connect(self._on_pull_err)
        self._pull_thread.finished.connect(self._on_pull_finished)
        self._btn_cancel_pull.setEnabled(True)
        self._pull_thread.start()
        self._append_log(s.LOG_PULL_START_FMT.format(serial=serial))

    def _on_cancel_pull(self) -> None:
        self._pull_cancel.set()
        self._append_log(s.LOG_CANCEL_PULL_REQUESTED)

    def _on_pull_ok(self) -> None:
        self._append_log(s.LOG_PULL_SUCCESS)
        self._refresh_comparator_ui()

    def _on_pull_err(self, msg: str) -> None:
        self._append_log(s.LOG_PULL_FAILED_FMT.format(msg=msg))
        warning_dialog(self.window(), s.DLG_TITLE_PULL_FAILED, msg)

    def _on_pull_finished(self) -> None:
        self._btn_cancel_pull.setEnabled(False)
        self._update_buttons_state()

    def on_devices_changed(self, devices: list[str]) -> None:
        super().on_devices_changed(devices)
        self._devices = list(devices)
