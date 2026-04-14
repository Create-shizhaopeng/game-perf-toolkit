"""游戏性能配置模块 — GUI Tab 页（上下分栏布局）"""

from __future__ import annotations

import functools
import os
import threading
from typing import Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QComboBox, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QLineEdit, QGridLayout, QTextEdit, QProgressBar,
    QScrollArea, QSplitter, QTabWidget, QDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent

from toolkit.gui.base_tab import BaseTab
from toolkit.gui.toolkit_dialog import (
    confirm_dialog,
    info_dialog,
    warning_dialog,
)

from .models import GamePerfDocumentOrigin
from .parser import GamePerfParser


class _BackgroundWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        import logging as _log
        _log.getLogger(__name__).info("BackgroundWorker.run() started")
        try:
            result = self._fn()
            self.finished.emit(result)
        except Exception as e:
            _log.getLogger(__name__).error("BackgroundWorker error: %s", e, exc_info=True)
            self.error.emit(e)


class GamePerfTab(BaseTab):
    """游戏性能配置工具的 Tab 页"""

    tab_title = "性能配置"
    tab_icon = "📊"

    def __init__(self, context: dict, parent=None):
        super().__init__(parent)
        self._context = context
        self._adb = context.get("gp_adb")
        self._service = context.get("gp_service")
        self._db_manager = context.get("db_manager")
        self._config_manager = context.get("config_manager")

        self.parser = None
        self._current_filtered_rows: list = []
        self._worker: _BackgroundWorker | None = None
        self._document_origin = GamePerfDocumentOrigin.NONE
        self._document_dirty = False
        # 避免设备列表轮询时重复自动拉取；仅在序列号变化或断连后重连时拉取
        self._last_known_device_serial = ""
        self._cancel_pull_event: threading.Event | None = None
        # 上次在 Start 弹窗中填写的备注，用于下次弹窗预填（主界面不展示备注框）
        self._push_notes_cache = ""
        # 整表刷新或行内同步频率下限时，忽略 QComboBox 的 currentIndexChanged，避免误触发/顺序错乱
        self._refreshing_bounds_table = False
        self._syncing_cluster_bounds = False

        self._init_ui()
        self._connect_signals()
        self._update_push_button_states(False)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(6)

        self._create_file_section(main_layout)
        self._create_filter_section(main_layout)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(True)

        self._create_table_widget()
        splitter.addWidget(self._table_card)

        mid_widget = QWidget()
        mid_layout = QHBoxLayout(mid_widget)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(6)
        self._create_strategy_section(mid_layout)
        splitter.addWidget(mid_widget)

        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)
        self._create_progress_section(bottom_layout)
        self._create_button_section(bottom_layout)
        splitter.addWidget(bottom_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 2)
        main_layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    # UI 区域创建
    # ------------------------------------------------------------------

    def _create_file_section(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card.setAcceptDrops(True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("配置文件")
        title.setProperty("class", "sectionTitleBlue")
        header.addWidget(title)
        hint = QLabel("选择或拖拽「文件名包含 gameperfconfig」的 .xml")
        hint.setObjectName("fieldHint")
        header.addWidget(hint)
        header.addStretch()
        self._origin_lbl = QLabel("")
        self._origin_lbl.setObjectName("fieldHint")
        header.addWidget(self._origin_lbl)
        card_layout.addLayout(header)

        row = QHBoxLayout()
        self._file_input = QLineEdit()
        self._file_input.setPlaceholderText("gameperfconfig.xml 文件路径")
        self._file_input.setFixedHeight(28)
        row.addWidget(self._file_input, 1)
        self._browse_btn = QPushButton("浏览...")
        self._browse_btn.setFixedHeight(28)
        self._browse_btn.setFixedWidth(70)
        row.addWidget(self._browse_btn)
        card_layout.addLayout(row)

        self._file_card = card
        card.dragEnterEvent = self._on_drag_enter
        card.dropEvent = self._on_drop
        parent_layout.addWidget(card)

    def _create_filter_section(self, parent_layout: QVBoxLayout):
        row = QHBoxLayout()
        row.setSpacing(6)

        row.addWidget(QLabel("游戏:"))
        self._game_cbx = QComboBox()
        self._game_cbx.setMinimumWidth(120)
        self._game_cbx.setMaximumWidth(200)
        row.addWidget(self._game_cbx)

        row.addWidget(QLabel("模式:"))
        self._mode_cbx = QComboBox()
        self._mode_cbx.setMinimumWidth(100)
        self._mode_cbx.setMaximumWidth(160)
        row.addWidget(self._mode_cbx)

        self._save_as_btn = QPushButton("另存为")
        self._save_as_btn.setFixedHeight(28)
        self._save_as_btn.setEnabled(False)
        row.addWidget(self._save_as_btn)

        row.addStretch(1)

        self._policy_version_lbl = QLabel("")
        self._policy_version_lbl.setObjectName("fieldLabel")
        self._policy_version_lbl.setMinimumWidth(140)
        self._policy_version_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._policy_version_lbl)
        parent_layout.addLayout(row)

    def _create_table_widget(self):
        self._table_card = QFrame()
        self._table_card.setProperty("class", "sectionCard")
        cl = QVBoxLayout(self._table_card)
        cl.setContentsMargins(8, 4, 8, 4)
        cl.setSpacing(2)

        title = QLabel("频率配置表")
        title.setProperty("class", "sectionTitleBlue")
        cl.addWidget(title)

        self._config_table = QTableWidget()
        self._config_table.setColumnCount(11)
        self._config_table.setHorizontalHeaderLabels([
            "温度等级", "触发温度(℃)",
            "Gold下限", "Gold上限", "Gold索引",
            "Prime下限", "Prime上限", "Prime索引",
            "GPU下限", "GPU上限", "GPU索引",
        ])
        self._config_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._config_table.verticalHeader().setDefaultSectionSize(32)
        cl.addWidget(self._config_table, 1)

    def _create_strategy_section(self, parent_layout: QHBoxLayout):
        self._strategy_tabs = QTabWidget()
        self._strategy_tabs.setMinimumWidth(300)

        self._overall_scroll = QScrollArea()
        self._overall_scroll.setWidgetResizable(True)
        self._overall_inner = QWidget()
        self._overall_layout = QVBoxLayout(self._overall_inner)
        self._overall_layout.setContentsMargins(4, 4, 4, 4)
        self._overall_layout.setSpacing(8)
        self._overall_scroll.setWidget(self._overall_inner)
        self._strategy_tabs.addTab(self._overall_scroll, "整体策略")

        self._mode_scroll = QScrollArea()
        self._mode_scroll.setWidgetResizable(True)
        self._mode_inner = QWidget()
        self._mode_layout = QVBoxLayout(self._mode_inner)
        self._mode_layout.setContentsMargins(4, 4, 4, 4)
        self._mode_layout.setSpacing(8)
        self._mode_scroll.setWidget(self._mode_inner)
        self._strategy_tabs.addTab(self._mode_scroll, "性能模式策略")

        parent_layout.addWidget(self._strategy_tabs, 1)

    def _create_progress_section(self, parent_layout: QVBoxLayout):
        prog = QHBoxLayout()
        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        prog.addWidget(self._progress_bar, 1)
        self._progress_label = QLabel("0%")
        self._progress_label.setFixedWidth(36)
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        prog.addWidget(self._progress_label)
        self._cancel_bg_btn = QPushButton("取消")
        self._cancel_bg_btn.setFixedWidth(52)
        self._cancel_bg_btn.setVisible(False)
        self._cancel_bg_btn.setToolTip("取消正在进行的从设备拉取（各步骤间隙生效）")
        self._cancel_bg_btn.clicked.connect(self._on_cancel_background_pull)
        prog.addWidget(self._cancel_bg_btn)
        parent_layout.addLayout(prog)

    def _create_button_section(self, parent_layout: QVBoxLayout):
        row = QHBoxLayout()
        row.addStretch()
        self._start_btn = QPushButton("▶ Start")
        row.addWidget(self._start_btn)
        row.addStretch()
        self._clear_btn = QPushButton("↺ 重置修改")
        row.addWidget(self._clear_btn)
        row.addStretch()
        self._reset_btn = QPushButton("↺ Reset")
        row.addWidget(self._reset_btn)
        row.addStretch()
        parent_layout.addLayout(row)

    # ------------------------------------------------------------------
    # 信号连接
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self._browse_btn.clicked.connect(self._on_browse)
        self._game_cbx.currentTextChanged.connect(self._on_game_changed)
        self._mode_cbx.currentTextChanged.connect(self._on_mode_changed)
        self._save_as_btn.clicked.connect(self._on_save_as)
        self._config_table.cellChanged.connect(self._on_cell_changed)
        self._start_btn.clicked.connect(self._on_push_start)
        self._clear_btn.clicked.connect(self._on_clear)
        self._reset_btn.clicked.connect(self._on_reset)

    # ------------------------------------------------------------------
    # 文件操作
    # ------------------------------------------------------------------

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self.window(), "选择配置文件", "", "XML文件 (*.xml)"
        )
        if path:
            self._file_input.setText(path)
            self._load_file(path)

    def _on_drag_enter(self, event: QDragEnterEvent):
        from .service import is_valid_config_filename
        mime = event.mimeData()
        if mime and mime.hasUrls():
            for url in mime.urls():
                if is_valid_config_filename(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def _on_drop(self, event: QDropEvent):
        from .service import is_valid_config_filename
        mime = event.mimeData()
        if mime and mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if is_valid_config_filename(path):
                    self._file_input.setText(path)
                    self._load_file(path)
                    event.acceptProposedAction()
                    return
        self._append_log("✗ 仅支持 gameperfconfig*.xml 文件", "#f44747")
        event.ignore()

    def _load_file(
        self,
        path: str,
        document_origin: GamePerfDocumentOrigin | None = None,
    ) -> None:
        from .parser import GamePerfParser

        if document_origin is None:
            document_origin = GamePerfDocumentOrigin.LOCAL_FILE

        try:
            self.parser = GamePerfParser(path)
        except Exception as e:
            warning_dialog(self.window(), "解析失败", f"解析 XML 失败: {e}")
            return

        if not self.parser.freq_rows:
            self._update_policy_version_label()
            warning_dialog(self.window(), "解析失败", "未解析到有效配置数据！")
            return

        self._document_origin = document_origin
        self._document_dirty = False
        self._update_origin_label()

        self._game_cbx.blockSignals(True)
        self._game_cbx.clear()
        self._game_cbx.addItems(self.parser.get_game_names())
        self._game_cbx.blockSignals(False)

        self._save_as_btn.setEnabled(True)
        self._update_policy_version_label()
        self._on_game_changed()

    # ------------------------------------------------------------------
    # 过滤与刷新
    # ------------------------------------------------------------------

    def _update_policy_version_label(self) -> None:
        """显示当前已载入 XML 根节点 GameOptPolicy 的 version 属性（另存为按钮右侧）。"""
        if not self.parser:
            self._policy_version_lbl.setText("")
            return
        v = self.parser.get_game_opt_policy_version()
        if v:
            self._policy_version_lbl.setText(f"策略版本: {v}")
        else:
            self._policy_version_lbl.setText("策略版本: —")

    def _on_game_changed(self):
        if not self.parser:
            return
        game = self._game_cbx.currentText()
        if not game:
            return
        modes = self.parser.get_modes_for_game(game)
        self._mode_cbx.blockSignals(True)
        self._mode_cbx.clear()
        self._mode_cbx.addItems(modes)
        self._mode_cbx.blockSignals(False)
        self._refresh()

    def _on_mode_changed(self):
        self._refresh()

    def _refresh(self):
        self._refresh_table()
        self._refresh_strategy()

    def _clear_table_freq_bound_widgets(self) -> None:
        """移除 Gold/Prime/GPU 上下限列上的 QComboBox，避免刷新残留。"""
        bound_cols = (2, 3, 5, 6, 8, 9)
        for r in range(self._config_table.rowCount()):
            for c in bound_cols:
                w = self._config_table.cellWidget(r, c)
                if w is not None:
                    self._config_table.removeCellWidget(r, c)
                    w.deleteLater()

    def _freq_list_for_cluster(self, cluster: str) -> list[int]:
        if not self.parser:
            return []
        if cluster == "Gpu":
            if self.parser.gpu_cluster:
                return self.parser.gpu_cluster.frequencies
            return []
        cl = self.parser.cpu_clusters.get(cluster)
        return list(cl.frequencies) if cl else []

    @staticmethod
    def _combo_indices_for_bounds(index_str: str, n: int) -> tuple[int, int]:
        """由索引串得到 (下限列下标, 上限列下标)。Gold/Prime/Gpu 均为 ``下限下标_上限下标``（左→右）。"""
        if n <= 0:
            return (0, 0)
        pair = GamePerfParser.parse_freq_index_pair(index_str)
        if pair is None:
            return (0, 0)
        a, b = pair
        a = max(0, min(a, n - 1))
        b = max(0, min(b, n - 1))
        return (a, b)

    @staticmethod
    def _combo_freq_index(cb: QComboBox) -> int | None:
        """读取 QComboBox 当前项对应的频率表下标（行序与 PreEnv 下标一致）。"""
        idx = cb.currentIndex()
        if idx < 0:
            return None
        v = cb.itemData(idx, Qt.ItemDataRole.UserRole)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
        return idx

    def _make_freq_bound_combo(self, freqs: list[int], selected_idx: int) -> QComboBox:
        cb = QComboBox()
        cb.setMaxVisibleItems(14)
        cb.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        cb.blockSignals(True)
        for i, hz in enumerate(freqs):
            cb.addItem(f"{hz} Hz", i)
        sel = max(0, min(selected_idx, len(freqs) - 1))
        cb.setCurrentIndex(sel)
        cb.blockSignals(False)
        return cb

    def _place_cluster_bound_combos(
        self,
        table_row: int,
        cluster: str,
        lo_col: int,
        hi_col: int,
        index_str: str,
    ) -> None:
        freqs = self._freq_list_for_cluster(cluster)
        if not freqs:
            self._config_table.setItem(
                table_row, lo_col, QTableWidgetItem("—")
            )
            self._config_table.setItem(
                table_row, hi_col, QTableWidgetItem("—")
            )
            for c in (lo_col, hi_col):
                it = self._config_table.item(table_row, c)
                if it is not None:
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            return

        lo_i, hi_i = self._combo_indices_for_bounds(index_str, len(freqs))
        cb_lo = self._make_freq_bound_combo(freqs, lo_i)
        cb_hi = self._make_freq_bound_combo(freqs, hi_i)
        cb_lo.blockSignals(True)
        cb_hi.blockSignals(True)
        cb_lo.setCurrentIndex(lo_i)
        cb_hi.setCurrentIndex(hi_i)
        cb_lo.blockSignals(False)
        cb_hi.blockSignals(False)

        def on_change(_: int = 0) -> None:
            self._on_cluster_bounds_combo_changed(
                table_row, cluster, lo_col, hi_col
            )

        cb_lo.currentIndexChanged.connect(on_change)
        cb_hi.currentIndexChanged.connect(on_change)

        self._config_table.setCellWidget(table_row, lo_col, cb_lo)
        self._config_table.setCellWidget(table_row, hi_col, cb_hi)

    def _on_cluster_bounds_combo_changed(
        self,
        table_row: int,
        cluster: str,
        lo_col: int,
        hi_col: int,
    ) -> None:
        if self._refreshing_bounds_table or self._syncing_cluster_bounds:
            return
        if not self.parser or table_row < 0 or table_row >= len(
            self._current_filtered_rows
        ):
            return
        w_lo = self._config_table.cellWidget(table_row, lo_col)
        w_hi = self._config_table.cellWidget(table_row, hi_col)
        if not isinstance(w_lo, QComboBox) or not isinstance(w_hi, QComboBox):
            return
        i_lo = self._combo_freq_index(w_lo)
        i_hi = self._combo_freq_index(w_hi)
        if i_lo is None or i_hi is None:
            return
        new_index_str = f"{i_lo}_{i_hi}"
        freq_row = self._current_filtered_rows[table_row]
        cur = {
            "Gold": freq_row.gold_index,
            "Prime": freq_row.prime_index,
            "Gpu": freq_row.gpu_index,
        }[cluster]
        cur_fmt = GamePerfParser.format_freq_index_str(cur)
        new_fmt = GamePerfParser.format_freq_index_str(new_index_str)
        if cur_fmt == new_fmt:
            return
        global_idx = self.parser.freq_rows.index(freq_row)
        self._config_table.blockSignals(True)
        try:
            if self.parser.update_freq_index(global_idx, cluster, new_index_str):
                self._document_dirty = True
                index_col = {"Gold": 4, "Prime": 7, "Gpu": 10}[cluster]
                item = self._config_table.item(table_row, index_col)
                if item is not None:
                    stored = {
                        "Gold": freq_row.gold_index,
                        "Prime": freq_row.prime_index,
                        "Gpu": freq_row.gpu_index,
                    }[cluster]
                    item.setText(stored)
        finally:
            self._config_table.blockSignals(False)

    def _refresh_table(self):
        if not self.parser:
            return
        game = self._game_cbx.currentText()
        mode = self._mode_cbx.currentText()
        if not game or not mode:
            return

        self._refreshing_bounds_table = True
        try:
            self._clear_table_freq_bound_widgets()
            self._current_filtered_rows = self.parser.get_filtered_rows(game, mode)
            self._config_table.blockSignals(True)
            self._config_table.setRowCount(len(self._current_filtered_rows))

            for r_idx, row in enumerate(self._current_filtered_rows):
                item0 = QTableWidgetItem(row.temp_level)
                item0.setFlags(item0.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._config_table.setItem(r_idx, 0, item0)

                item1 = QTableWidgetItem(row.trigger_temp)
                item1.setFlags(item1.flags() | Qt.ItemFlag.ItemIsEditable)
                self._config_table.setItem(r_idx, 1, item1)

                self._place_cluster_bound_combos(
                    r_idx, "Gold", 2, 3, row.gold_index
                )
                self._place_cluster_bound_combos(
                    r_idx, "Prime", 5, 6, row.prime_index
                )
                self._place_cluster_bound_combos(
                    r_idx, "Gpu", 8, 9, row.gpu_index
                )

                for col, val in (
                    (4, row.gold_index),
                    (7, row.prime_index),
                    (10, row.gpu_index),
                ):
                    item = QTableWidgetItem(val)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                    self._config_table.setItem(r_idx, col, item)

            self._config_table.blockSignals(False)
        finally:
            self._refreshing_bounds_table = False

    def _refresh_strategy(self):
        self._refresh_overall_strategy()
        self._refresh_mode_strategy()

    def _refresh_overall_strategy(self):
        self._clear_layout(self._overall_layout)
        if not self.parser:
            return
        game = self._game_cbx.currentText()
        pkg = self.parser.get_package_for_alias(game) if game else ""
        if not pkg:
            return
        for item in self.parser.get_game_level_data(pkg):
            self._append_strategy_block(self._overall_layout, item, mode_context=False)
        self._overall_layout.addStretch(1)

    def _refresh_mode_strategy(self):
        self._clear_layout(self._mode_layout)
        if not self.parser:
            return
        game = self._game_cbx.currentText()
        mode = self._mode_cbx.currentText()
        pkg = self.parser.get_package_for_alias(game) if game else ""
        if not pkg or not mode:
            return
        for item in self.parser.get_mode_level_data(pkg, mode):
            self._append_strategy_block(self._mode_layout, item, mode_context=True)
        self._mode_layout.addStretch(1)

    def _append_strategy_block(
        self, parent_layout: QVBoxLayout, item: Any, mode_context: bool
    ) -> None:
        from lxml import etree

        block = QFrame()
        block.setProperty("class", "sectionCard")
        bl = QVBoxLayout(block)
        bl.setContentsMargins(6, 4, 6, 4)
        bl.setSpacing(4)

        is_perfhint = item.tag == "PerfHint" and item.element is not None
        is_bindcore = item.tag == "BindCore" and item.element is not None

        if is_perfhint:
            opcode = item.element.find("opcode")
            if opcode is not None:
                self._append_perfhint_block(bl, item.tag, opcode, mode_context)
                parent_layout.addWidget(block)
                return

        if is_bindcore:
            title_row = QHBoxLayout()
            st = QLabel(item.tag)
            st.setProperty("class", "sectionTitleBlue")
            title_row.addWidget(st)
            title_row.addStretch()
            add_btn = QPushButton("+ 添加")
            add_btn.setFixedHeight(24)
            add_btn.clicked.connect(functools.partial(self._on_bindcore_add, item.element))
            title_row.addWidget(add_btn)
            del_btn = QPushButton("× 删除整块")
            del_btn.setFixedHeight(24)
            del_btn.clicked.connect(functools.partial(self._on_remove_subtree, item.element))
            title_row.addWidget(del_btn)
            bl.addLayout(title_row)
        else:
            st = QLabel(item.tag)
            st.setProperty("class", "sectionTitleBlue")
            st.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            bl.addWidget(st)

        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(2)
        grid.addWidget(QLabel("Key"), 0, 0)
        grid.addWidget(QLabel("Value"), 0, 1)
        if is_bindcore:
            grid.addWidget(QLabel("操作"), 0, 2)
            grid.setColumnStretch(0, 2)
            grid.setColumnStretch(1, 3)
            grid.setColumnStretch(2, 0)
        else:
            grid.setColumnStretch(0, 2)
            grid.setColumnStretch(1, 3)

        row_idx = 1
        seen_bindcore_children: set[int] = set()
        for p in (item.pairs or []):
            if not isinstance(p, dict) or p.get("dom") is None:
                continue
            key_text = p.get("attr") or (p["dom"].tag if hasattr(p["dom"], "tag") else str(p.get("header", "")))
            kl = QLabel(key_text)
            kl.setWordWrap(True)
            ed = QLineEdit(str(p.get("value", "")))
            ed.setFixedHeight(26)
            ed.editingFinished.connect(
                functools.partial(self._on_strategy_edit, p, ed, mode_context)
            )
            grid.addWidget(kl, row_idx, 0)
            grid.addWidget(ed, row_idx, 1)
            if is_bindcore:
                target = self._bindcore_direct_child_for_remove(item.element, p["dom"])
                del_btn: Optional[QPushButton] = None
                if target is not None:
                    tid = id(target)
                    if tid not in seen_bindcore_children:
                        seen_bindcore_children.add(tid)
                        del_btn = QPushButton("删此行")
                        del_btn.setFixedHeight(26)
                        del_btn.clicked.connect(
                            functools.partial(self._on_bindcore_remove_row, target)
                        )
                if del_btn is not None:
                    grid.addWidget(del_btn, row_idx, 2)
                else:
                    grid.addWidget(QLabel(""), row_idx, 2)
            row_idx += 1
        bl.addLayout(grid)
        parent_layout.addWidget(block)

    def _append_perfhint_block(
        self, parent_layout: QVBoxLayout, title: str,
        opcode, mode_context: bool,
    ) -> None:
        st = QLabel(title)
        st.setProperty("class", "sectionTitleBlue")
        st.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        parent_layout.addWidget(st)

        row = QHBoxLayout()
        meta_id = {"dom": opcode, "mode": "attr", "attr": "id", "value": opcode.get("id", "")}
        ed_id = QLineEdit(meta_id["value"])
        ed_id.setFixedHeight(26)
        ed_id.editingFinished.connect(functools.partial(self._on_strategy_edit, meta_id, ed_id, mode_context))

        meta_time = {"dom": opcode, "mode": "attr", "attr": "time", "value": opcode.get("time", "")}
        ed_time = QLineEdit(meta_time["value"])
        ed_time.setFixedHeight(26)
        ed_time.editingFinished.connect(functools.partial(self._on_strategy_edit, meta_time, ed_time, mode_context))

        row.addWidget(QLabel("id:"))
        row.addWidget(ed_id, 1)
        row.addWidget(QLabel("time:"))
        row.addWidget(ed_time, 1)
        parent_layout.addLayout(row)

        body = (opcode.text or "").strip()
        meta_txt = {"dom": opcode, "mode": "text", "attr": None, "value": body, "sync_df": "PerfHint"}
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("数据:"))
        ed_body = QLineEdit(body)
        ed_body.setFixedHeight(26)
        ed_body.editingFinished.connect(functools.partial(self._on_strategy_edit, meta_txt, ed_body, mode_context))
        row2.addWidget(ed_body, 1)
        parent_layout.addLayout(row2)

    # ------------------------------------------------------------------
    # 编辑回调
    # ------------------------------------------------------------------

    def _on_cell_changed(self, row: int, col: int):
        if not self.parser or not self._current_filtered_rows:
            return
        if row < 0 or row >= len(self._current_filtered_rows):
            return
        item = self._config_table.item(row, col)
        if item is None:
            return
        freq_row = self._current_filtered_rows[row]
        global_idx = self.parser.freq_rows.index(freq_row)
        new_val = item.text().strip()

        if col == 1:
            try:
                t = int(new_val)
                if t < 0 or t > 200:
                    raise ValueError
            except ValueError:
                warning_dialog(self.window(), "格式错误", "触发温度请填写 0～200 的整数")
                self._refresh_table()
                return
            self.parser.update_temperature(global_idx, str(t))
            self._document_dirty = True
            self._refresh_table()
        elif col in (4, 7, 10):
            if "_" not in new_val:
                warning_dialog(self.window(), "格式错误", "索引须为 start_end 格式（如 2_8）")
                self._refresh_table()
                return
            cluster = {4: "Gold", 7: "Prime", 10: "Gpu"}[col]
            cur_idx = {
                "Gold": freq_row.gold_index,
                "Prime": freq_row.prime_index,
                "Gpu": freq_row.gpu_index,
            }[cluster]
            cur_n = GamePerfParser.format_freq_index_str(cur_idx)
            new_n = GamePerfParser.format_freq_index_str(new_val)
            if new_n is None:
                warning_dialog(self.window(), "格式错误", "索引须为 start_end 格式（如 2_8）")
                self._refresh_table()
                return
            if new_n == cur_n:
                if item.text().strip().replace(" ", "") != new_n:
                    self._config_table.blockSignals(True)
                    try:
                        item.setText(new_n)
                    finally:
                        self._config_table.blockSignals(False)
                return
            self.parser.update_freq_index(global_idx, cluster, new_val)
            self._document_dirty = True
            self._refresh_table()

    def _on_strategy_edit(self, meta: dict, edit: QLineEdit, mode_context: bool):
        if not self.parser:
            return
        new_val = edit.text().strip()
        if new_val == str(meta.get("value", "")):
            return
        if not self.parser.apply_strategy_edit(meta["dom"], meta["mode"], meta.get("attr"), new_val):
            edit.setText(str(meta.get("value", "")))
            return
        self._document_dirty = True
        meta["value"] = new_val
        if mode_context:
            game = self._game_cbx.currentText()
            mode = self._mode_cbx.currentText()
            pkg = self.parser.get_package_for_alias(game)
            sync_col = meta.get("sync_df")
            if sync_col and pkg:
                self.parser.sync_mode_fields_to_freq_rows(pkg, mode, sync_col, new_val)
        self._refresh()

    def _on_bindcore_add(self, root_el):
        if self.parser and self.parser.add_bindcore_row(root_el):
            self._document_dirty = True
            self._refresh()

    @staticmethod
    def _bindcore_direct_child_for_remove(bind_root, dom) -> Any:
        """从扁平化后的 dom 定位到 BindCore 的直接子节点（用于整段删除）。"""
        if bind_root is None or dom is None:
            return None
        cur = dom
        while cur is not None:
            par = cur.getparent()
            if par == bind_root:
                return None if cur.tag == "BindCore" else cur
            if par is None:
                return None
            cur = par
        return None

    def _on_bindcore_remove_row(self, child_el) -> None:
        if not self.parser:
            return
        ok = confirm_dialog(
            self.window(), "确认删除", "确定删除该绑核子项？",
            confirm_text="删除", danger=True,
        )
        if not ok:
            return
        if self.parser.remove_bindcore_child(child_el):
            self._document_dirty = True
            self._refresh_strategy()

    def _on_remove_subtree(self, element):
        ok = confirm_dialog(
            self.window(), "确认删除", "确定删除该节点及其所有子项？",
            confirm_text="删除", danger=True,
        )
        if ok and self.parser:
            if self.parser.remove_subtree(element):
                self._document_dirty = True
                self._refresh()

    def _on_save_as(self):
        if not self.parser:
            return
        path, _ = QFileDialog.getSaveFileName(
            self.window(), "另存为", "", "XML文件 (*.xml)"
        )
        if path and self.parser.save_as(path):
            info_dialog(self.window(), "保存成功", f"已保存到：\n{path}")

    # ------------------------------------------------------------------
    # 推送/清除/还原
    # ------------------------------------------------------------------

    def _prompt_mandatory_push_notes(self) -> str | None:
        """Start 前强制填写备注。确定返回非空字符串；取消返回 None。"""
        from toolkit.gui.toolkit_dialog import ToolkitDialog

        dlg = ToolkitDialog("填写推送备注", self.window(), min_width=420)
        lbl = QLabel("推送前必须填写备注，将写入推送记录。请简要说明本次变更目的：")
        lbl.setWordWrap(True)
        lbl.setObjectName("dlgMsgLabel")
        dlg.content_layout.addWidget(lbl)

        edit = QLineEdit()
        edit.setText(self._push_notes_cache)
        edit.setPlaceholderText("必填，例如：修复 XX 游戏温控策略")
        dlg.content_layout.addWidget(edit)

        from PyQt6.QtWidgets import QHBoxLayout as _HBox
        btn_row = _HBox()
        btn_row.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("secondaryBtn")
        btn_cancel.setFixedWidth(80)
        btn_cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_cancel)

        ok_btn = QPushButton("确定")
        ok_btn.setObjectName("primaryBtn")
        ok_btn.setFixedWidth(80)
        ok_btn.setEnabled(bool(edit.text().strip()))
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(ok_btn)

        edit.textChanged.connect(lambda t: ok_btn.setEnabled(bool(t.strip())))
        dlg.content_layout.addLayout(btn_row)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        notes = edit.text().strip()
        if not notes:
            warning_dialog(self.window(), "备注为空", "请填写非空备注后再推送。")
            return None
        self._push_notes_cache = notes
        return notes

    def _on_push_start(self):
        import logging as _log
        _logger = _log.getLogger(__name__)

        if not self.require_device():
            return
        filepath = self._file_input.text().strip()
        if not filepath:
            warning_dialog(self.window(), "未选择文件", "请先选择要推送的配置文件")
            return
        if not os.path.isfile(filepath):
            warning_dialog(self.window(), "文件不存在", f"找不到文件:\n{filepath}")
            return

        notes = self._prompt_mandatory_push_notes()
        if notes is None:
            return

        if self.parser and self.parser.xml_path == filepath:
            self.parser.write_to_path(filepath)

        self._save_push_record(notes)
        self._set_progress(0)
        self._update_push_button_states(False)

        serial = self._get_serial()
        _logger.info("push start: serial=%s, file=%s", serial, filepath)

        svc = self._service

        def do_push():
            _logger.info("worker: calling service.push()")
            return svc.push(serial, filepath, on_progress=self._on_progress_safe, notes=notes)

        self._run_background(do_push, self._on_push_done)

    def _on_clear(self):
        filepath = self._file_input.text().strip()
        if filepath and os.path.isfile(filepath):
            prev_game = self._game_cbx.currentText()
            prev_mode = self._mode_cbx.currentText()
            self._load_file(filepath)
            if prev_game:
                idx = self._game_cbx.findText(prev_game)
                if idx >= 0:
                    self._game_cbx.setCurrentIndex(idx)
                    self._on_game_changed()
                    if prev_mode:
                        midx = self._mode_cbx.findText(prev_mode)
                        if midx >= 0:
                            self._mode_cbx.setCurrentIndex(midx)
                            self._on_mode_changed()
            self._append_log("↺ 已重置为文件原始内容（保持当前游戏/模式）", "#dcdcaa")
        else:
            self._game_cbx.clear()
            self._mode_cbx.clear()
            self._config_table.setRowCount(0)
            self.parser = None
            self._document_origin = GamePerfDocumentOrigin.NONE
            self._document_dirty = False
            self._update_origin_label()
            self._update_policy_version_label()

    def _on_reset(self):
        if not self.require_device():
            return
        self._set_progress(0)
        self._update_push_button_states(False)

        serial = self._get_serial()

        def do_reset():
            return self._service.reset(serial, on_progress=self._on_progress_safe)

        self._run_background(do_reset, self._on_push_done)

    def _finish_background_pull_ui(self) -> None:
        self._cancel_bg_btn.setVisible(False)
        self._cancel_pull_event = None

    def _on_cancel_background_pull(self) -> None:
        if self._cancel_pull_event is not None:
            self._cancel_pull_event.set()
            self._append_log("… 已请求取消拉取（等待当前步骤结束）", "#dcdcaa")

    def _on_push_done(self, result):
        self._finish_background_pull_ui()
        self._set_progress(100)
        self._update_push_button_states(self._device_connected)

    def _on_auto_pull_done(self, result):
        from .models import AutoDevicePullResult

        self._finish_background_pull_ui()
        self._set_progress(100)
        self._update_push_button_states(self._device_connected)
        if not isinstance(result, AutoDevicePullResult):
            self._append_log("✗ 从设备载入失败：内部错误", "#f44747")
            return
        if not result.ok:
            if result.failure_kind == "cancelled":
                self._append_log(f"○ {result.user_message}", "#dcdcaa")
            else:
                self._append_log(f"✗ {result.user_message}", "#f44747")
            return
        path = result.local_path
        if not path or not os.path.isfile(path):
            self._append_log("✗ 从设备载入失败：本地缓存文件不存在", "#f44747")
            return
        self._file_input.setText(path)
        self._load_file(path, document_origin=result.origin)
        if self.parser:
            self._append_log("✓ 已从设备载入并显示配置", "#608b4e")

    def _on_push_error(self, exc):
        self._finish_background_pull_ui()
        from .service import XmlValidationError
        if isinstance(exc, XmlValidationError):
            self._append_log(f"✗ {exc}", "#f44747")
            for line_no, line_text, is_err in exc.context.context_lines:
                prefix = "→" if is_err else " "
                color = "#f44747" if is_err else "#808080"
                self._append_log(f"  {prefix} {line_no:>4}| {line_text}", color)
        else:
            self._append_log(f"✗ {exc}", "#f44747")
        self._update_push_button_states(self._device_connected)

    def _on_progress_safe(self, msg: str):
        if self._worker:
            self._worker.progress.emit(msg)

    def _on_progress_ui(self, msg: str):
        color = "#dcdcaa"
        if "✓" in msg:
            color = "#608b4e"
        elif "✗" in msg:
            color = "#f44747"
        self._append_log(msg, color)
        self._increment_progress()

    def _save_push_record(self, notes: str) -> None:
        if not self.parser or not self._current_filtered_rows or not self._service:
            return
        from .models import PushRecord

        game = self._game_cbx.currentText()
        mode = self._mode_cbx.currentText()
        pkg = self.parser.get_package_for_alias(game)

        rows = self.parser.get_filtered_rows(game, mode)
        data = [r.to_dict() for r in rows]

        record = PushRecord(game=game, package=pkg, mode=mode, notes=notes, data=data)
        self._service.save_push_record(record, db_manager=self._db_manager)

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _run_background(self, fn, on_done):
        self._worker = _BackgroundWorker(fn, self)
        self._worker.finished.connect(on_done)
        self._worker.error.connect(self._on_push_error)
        self._worker.progress.connect(self._on_progress_ui)
        self._worker.start()

    def _update_origin_label(self) -> None:
        if self._document_origin == GamePerfDocumentOrigin.DEVICE:
            self._origin_lbl.setText("来源：设备")
        elif self._document_origin == GamePerfDocumentOrigin.LOCAL_FILE:
            self._origin_lbl.setText("来源：本地文件")
        else:
            self._origin_lbl.setText("")

    def _confirm_discard_local_for_device_pull(self) -> bool:
        """用户确认放弃本地未保存修改并从设备载入。True 表示继续拉取。"""
        return confirm_dialog(
            self.window(),
            "未保存的修改",
            "当前配置有未保存的修改。是否放弃修改并从设备重新载入 gameperfconfig.xml？",
            confirm_text="放弃并载入",
            danger=True,
        )

    def _maybe_auto_pull_from_device(self) -> None:
        """设备可用时从 /system/etc/gameperfconfig.xml 拉取并加载（US6 / T027）。"""
        if not self._service or not self._device_connected:
            return
        serial = self._get_serial()
        if not serial:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        if self._document_dirty:
            if not self._confirm_discard_local_for_device_pull():
                self._append_log("[设备] 已取消自动载入（保留本地修改）", "#dcdcaa")
                return
            self._document_dirty = False

        self._set_progress(0)
        self._append_log(
            "[设备] 正在从 /system/etc/gameperfconfig.xml 拉取…", "#569cd6"
        )
        self._update_push_button_states(False)

        self._cancel_pull_event = threading.Event()
        self._cancel_bg_btn.setVisible(True)

        svc = self._service
        cancel_ev = self._cancel_pull_event

        def do_pull():
            return svc.pull_device_config_from_device(
                serial,
                on_progress=self._on_progress_safe,
                cancel_event=cancel_ev,
            )

        self._run_background(do_pull, self._on_auto_pull_done)

    def _get_serial(self) -> str:
        if self._adb:
            devices = self._adb.get_connected_devices()
            if devices:
                return devices[0]
        return ""

    def _update_push_button_states(self, enabled: bool):
        self._start_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(True)
        self._reset_btn.setEnabled(enabled)

    def _append_log(self, text: str, color: str = "#d4d4d4"):
        if "✓" in text or "#608b4e" in color:
            level = "success"
        elif "✗" in text or "#f44747" in color:
            level = "error"
        elif "#dcdcaa" in color or "#569cd6" in color:
            level = "warning"
        else:
            level = "info"
        self._log(text, level=level)

    def _set_progress(self, value: int):
        self._progress_bar.setValue(value)
        self._progress_label.setText(f"{value}%")

    def _increment_progress(self):
        val = self._progress_bar.value()
        new_val = min(val + 8, 95)
        self._set_progress(new_val)

    def on_activated(self) -> None:
        super().on_activated()
        # 先点开 Tab、后完成设备枚举时补拉（与 on_devices_changed 去重）
        if not (self._device_connected and self._service and self.parser is None):
            return
        serial = self._get_serial()
        if not serial:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        if self._last_known_device_serial == serial:
            return
        self._last_known_device_serial = serial
        self._maybe_auto_pull_from_device()

    def on_devices_changed(self, devices: list[str]):
        super().on_devices_changed(devices)
        self._update_push_button_states(bool(devices))
        if not devices or not self._service:
            self._last_known_device_serial = ""
            return
        serial = devices[0]
        if serial == self._last_known_device_serial:
            return
        self._last_known_device_serial = serial
        self._maybe_auto_pull_from_device()

    @staticmethod
    def _clear_layout(layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
