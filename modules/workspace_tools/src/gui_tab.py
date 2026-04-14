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
    QTextEdit,
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

    tab_title = "性能配置对比"
    tab_icon = "🧰"

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
        title = QLabel("性能配置对比")
        title.setProperty("class", "sectionTitleBlue")
        lay.addWidget(title)
        body = QLabel(
            "本模块用于多份游戏性能策略 XML（gameperfconfig*.xml）的对比与合并。\n\n"
            "「配置对比」页支持选定基准与多个对比源、语义差异展示、按条采纳、另存为（原子写盘），"
            "以及从已连接设备拉取标准路径配置参与对比。"
        )
        body.setWordWrap(True)
        body.setProperty("class", "fieldLabel")
        lay.addWidget(body)
        lay.addStretch()
        self._tabs.addTab(page, "工具说明")

    def _build_diff_tab(self) -> None:
        page = QWidget()
        page_lay = QVBoxLayout(page)
        page_lay.setContentsMargins(4, 4, 4, 4)

        if self._gp_svc is None:
            page_lay.addWidget(QLabel("未注入 wo_gameperf_diff_service，配置对比不可用。"))
            self._tabs.addTab(page, "配置对比")
            return

        # —— 左栏：基准、对比文件、操作、摘要、日志 ——
        left_col = QWidget()
        left_col.setMinimumWidth(300)
        left_lay = QVBoxLayout(left_col)
        left_lay.setContentsMargins(0, 0, 6, 0)

        base_box = QGroupBox("基准文件")
        base_lay = QHBoxLayout(base_box)
        self._baseline_edit = QLineEdit()
        self._baseline_edit.setPlaceholderText("选择包含 gameperfconfig 的 .xml 作为基准")
        btn_browse_base = QPushButton("浏览…")
        btn_browse_base.clicked.connect(self._on_browse_baseline)
        base_lay.addWidget(self._baseline_edit, 1)
        base_lay.addWidget(btn_browse_base)
        left_lay.addWidget(base_box)

        cmp_box = QGroupBox("对比文件（可拖拽 gameperfconfig*.xml 到下方区域）")
        cmp_lay = QVBoxLayout(cmp_box)
        row = QHBoxLayout()
        self._cmp_list = QListWidget()
        self._cmp_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        btn_add = QPushButton("添加本地…")
        btn_add.clicked.connect(self._on_add_comparator)
        btn_rm = QPushButton("移除选中")
        btn_rm.clicked.connect(self._on_remove_comparator)
        btn_as_base = QPushButton("设为基准")
        btn_as_base.clicked.connect(self._on_set_baseline_from_list)
        btn_device = QPushButton("从当前设备添加")
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
        drop_l.addWidget(QLabel("拖拽文件到此处添加为对比项"))
        cmp_lay.addWidget(drop)
        left_lay.addWidget(cmp_box, 1)

        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("当前对比："))
        self._active_combo = QComboBox()
        self._active_combo.currentIndexChanged.connect(self._on_active_comparator_changed)
        op_row.addWidget(self._active_combo, 1)
        self._btn_start_diff = QPushButton("开始对比")
        self._btn_start_diff.clicked.connect(self._on_start_diff)
        self._btn_cancel_diff = QPushButton("取消")
        self._btn_cancel_diff.setEnabled(False)
        self._btn_cancel_diff.clicked.connect(self._on_cancel_diff)
        op_row.addWidget(self._btn_start_diff)
        op_row.addWidget(self._btn_cancel_diff)
        left_lay.addLayout(op_row)

        sum_box = QGroupBox("各对比文件差异条数")
        sum_lay = QVBoxLayout(sum_box)
        self._summary_list = QListWidget()
        self._summary_list.setMaximumHeight(72)
        sum_lay.addWidget(self._summary_list)
        left_lay.addWidget(sum_box)

        log_box = QGroupBox("日志")
        log_lay = QVBoxLayout(log_box)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(96)
        self._log.setMaximumHeight(140)
        log_lay.addWidget(self._log)
        pull_row = QHBoxLayout()
        self._btn_cancel_pull = QPushButton("取消拉取")
        self._btn_cancel_pull.setEnabled(False)
        self._btn_cancel_pull.clicked.connect(self._on_cancel_pull)
        pull_row.addWidget(self._btn_cancel_pull)
        pull_row.addStretch()
        log_lay.addLayout(pull_row)
        left_lay.addWidget(log_box)

        # —— 右栏：差异明细（占满高度）+ 底部操作按钮 ——
        right_col = QWidget()
        right_col.setMinimumWidth(360)
        right_lay = QVBoxLayout(right_col)
        right_lay.setContentsMargins(6, 0, 0, 0)

        tree_box = QGroupBox("差异明细（选中一行后采纳一侧）")
        tree_lay = QVBoxLayout(tree_box)
        self._diff_tree = QTreeWidget()
        self._diff_tree.setObjectName("gameperfDiffTree")
        self._diff_tree.setHeaderLabels(["语义路径", "基准侧", "对比侧"])
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
        self._diff_tree.setStyleSheet(
            """
            QTreeWidget#gameperfDiffTree::item:selected,
            QTreeWidget#gameperfDiffTree::item:selected:active {
                background-color: #585b70;
                color: #f5f5f5;
            }
            QTreeWidget#gameperfDiffTree::item:selected:!active {
                background-color: #45475a;
                color: #e8e8e8;
            }
            QTreeWidget#gameperfDiffTree::item:hover {
                background-color: #313244;
            }
            """
        )
        tree_lay.addWidget(self._diff_tree, 1)
        btn_row = QHBoxLayout()
        self._btn_adopt_base = QPushButton("采纳基准侧")
        self._btn_adopt_comp = QPushButton("采纳对比侧")
        self._btn_undo = QPushButton("撤销上次采纳")
        self._btn_reset = QPushButton("重置合并")
        self._btn_save = QPushButton("另存为…")
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
        self._tabs.addTab(page, "配置对比")
        self._update_buttons_state()

    def _append_log(self, msg: str) -> None:
        self._log.append(msg)

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
            "选择基准 gameperfconfig XML",
            "",
            "XML (*.xml)",
        )
        if not path:
            return
        if not is_valid_gameperf_config_filename(os.path.basename(path)):
            warning_dialog(self.window(), "文件名无效", "须为文件名包含 gameperfconfig 的 .xml")
            return
        try:
            self._gp_svc.load_session(path)
            self._baseline_edit.setText(path)
            self._diff_tree.clear()
            self._summary_list.clear()
            self._last_items.clear()
            self._append_log(f"已载入基准：{path}")
        except Exception as e:
            warning_dialog(self.window(), "载入失败", str(e))
        self._refresh_comparator_ui()

    def _on_add_comparator(self) -> None:
        if not self._gp_svc:
            return
        if self._gp_svc.get_session() is None:
            info_dialog(self.window(), "提示", "请先选择基准文件。")
            return
        path, _ = QFileDialog.getOpenFileName(
            self.window(),
            "添加对比文件",
            "",
            "XML (*.xml)",
        )
        if path:
            self._add_comparator_path(path)

    def _on_drop_comparator(self, path: str) -> None:
        if not self._gp_svc or self._gp_svc.get_session() is None:
            info_dialog(self.window(), "提示", "请先选择基准文件。")
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
            warning_dialog(self.window(), "移除失败", str(e))
        self._diff_tree.clear()
        self._summary_list.clear()
        self._refresh_comparator_ui()

    def _on_set_baseline_from_list(self) -> None:
        if not self._gp_svc:
            return
        row = self._cmp_list.currentRow()
        if row < 0:
            info_dialog(self.window(), "提示", "请先在列表中选中一个对比文件。")
            return
        try:
            self._gp_svc.set_baseline_from_comparator(row)
            self._baseline_edit.setText(self._gp_svc.get_session().baseline_path if self._gp_svc.get_session() else "")
            self._append_log("已将该对比文件设为基准，对比列表已清空。")
        except Exception as e:
            warning_dialog(self.window(), "操作失败", str(e))
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
        self._append_log("开始语义对比…")
        self._btn_start_diff.setEnabled(False)
        self._btn_cancel_diff.setEnabled(True)
        self._diff_thread.start()

    def _on_cancel_diff(self) -> None:
        self._diff_cancel.set()
        self._append_log("已请求取消对比（步骤间隙生效）…")

    def _on_diff_ok(self, items: list) -> None:
        assert self._gp_svc is not None
        self._last_items = list(items)
        ci = self._active_combo.currentData()
        if ci is not None:
            self._populate_diff_tree(self._gp_svc.get_diff_for_comparator(int(ci)))
        self._summary_list.clear()
        for label, n in self._gp_svc.diff_counts_summary():
            self._summary_list.addItem(f"{label}：{n} 条差异" if n else f"{label}：无差异")
        self._append_log("对比完成。")

    def _on_diff_err(self, msg: str) -> None:
        self._append_log(f"对比失败：{msg}")
        warning_dialog(self.window(), "对比失败", msg)

    def _on_diff_thread_finished(self) -> None:
        self._btn_cancel_diff.setEnabled(False)
        self._update_buttons_state()

    def _populate_diff_tree(self, items: list[DiffItem]) -> None:
        self._diff_tree.clear()
        for it in items:
            twi = QTreeWidgetItem(
                [
                    it.semantic_path,
                    it.left_snippet or "—",
                    it.right_snippet or "—",
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
            info_dialog(self.window(), "提示", "请在差异树中选择一行。")
            return
        did = twi.data(0, Qt.ItemDataRole.UserRole)
        mergeable = twi.data(0, Qt.ItemDataRole.UserRole + 1)
        if not did or not mergeable:
            info_dialog(self.window(), "提示", "该项不可一键采纳。")
            return
        ci = self._active_combo.currentData()
        if ci is None:
            return
        try:
            self._gp_svc.apply_merge(str(did), side, int(ci))
            self._append_log(f"已采纳：{side} ← {twi.text(0)}")
        except Exception as e:
            warning_dialog(self.window(), "采纳失败", str(e))

    def _on_undo(self) -> None:
        if not self._gp_svc:
            return
        ok, detail = self._gp_svc.undo_merge()
        if ok:
            if detail:
                self._append_log(f"已撤销上次采纳。{detail}")
            else:
                self._append_log("已撤销上次采纳。")
        else:
            self._append_log("无可撤销操作。")

    def _on_reset(self) -> None:
        if not self._gp_svc:
            return
        self._gp_svc.reset_merge()
        self._append_log("已重置合并为基准副本。")

    def _on_save_as(self) -> None:
        if not self._gp_svc:
            return
        dirty = self._gp_svc.get_merge_dirty()
        path, _ = QFileDialog.getSaveFileName(
            self.window(),
            "另存为 gameperfconfig",
            "",
            "XML (*.xml)",
        )
        if not path:
            return
        if not is_valid_gameperf_config_filename(os.path.basename(path)):
            warning_dialog(self.window(), "文件名无效", "建议文件名包含 gameperfconfig 且为 .xml")
            return
        initial_stat = None
        if os.path.isfile(path):
            initial_stat = GamePerfConfigDiffService.stat_path(path)
        overwrite = os.path.isfile(path)
        msg = (
            f"目标路径：\n{path}\n\n"
            f"{'将覆盖已存在文件。' if overwrite else '将创建新文件。'}\n"
            f"合并脏状态（相对基准已修改）：{'是' if dirty else '否'}\n\n"
            f"确认保存？"
        )
        if not confirm_dialog(self.window(), "确认保存", msg):
            return
        if initial_stat is not None:
            now_stat = GamePerfConfigDiffService.stat_path(path)
            if now_stat is not None and (
                now_stat.st_mtime != initial_stat.st_mtime
                or now_stat.st_size != initial_stat.st_size
            ):
                if not confirm_dialog(
                    self.window(), "文件已变化",
                    "目标文件在操作过程中已被外部修改，仍要覆盖写入吗？",
                ):
                    return
        try:
            self._gp_svc.save_merged_as(path, atomic=True)
            self._append_log(f"已保存：{path}")
            info_dialog(self.window(), "完成", "保存成功。")
        except Exception as e:
            warning_dialog(self.window(), "保存失败", str(e))

    def _on_pull_device(self) -> None:
        if not self.require_device() or not self._gp_svc:
            return
        if self._gp_svc.get_session() is None:
            info_dialog(self.window(), "提示", "请先选择基准文件。")
            return
        serial = self._devices[0] if self._devices else ""
        if not serial:
            warning_dialog(self.window(), "设备", "无当前设备序列号。")
            return
        self._pull_cancel.clear()
        self._pull_thread = _PullThread(self._gp_svc, serial, self._pull_cancel)
        self._pull_thread.log_msg.connect(self._append_log)
        self._pull_thread.finished_ok.connect(self._on_pull_ok)
        self._pull_thread.finished_err.connect(self._on_pull_err)
        self._pull_thread.finished.connect(self._on_pull_finished)
        self._btn_cancel_pull.setEnabled(True)
        self._pull_thread.start()
        self._append_log(f"[设备] 开始拉取 {serial} …")

    def _on_cancel_pull(self) -> None:
        self._pull_cancel.set()
        self._append_log("已请求取消拉取（步骤间隙生效）…")

    def _on_pull_ok(self) -> None:
        self._append_log("设备配置已加入对比列表。")
        self._refresh_comparator_ui()

    def _on_pull_err(self, msg: str) -> None:
        self._append_log(f"拉取失败：{msg}")
        warning_dialog(self.window(), "拉取失败", msg)

    def _on_pull_finished(self) -> None:
        self._btn_cancel_pull.setEnabled(False)
        self._update_buttons_state()

    def on_devices_changed(self, devices: list[str]) -> None:
        super().on_devices_changed(devices)
        self._devices = list(devices)
