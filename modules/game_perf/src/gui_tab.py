"""游戏性能配置模块 — GUI Tab 页（上下分栏布局）"""

from __future__ import annotations

import functools
import os
from typing import Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QComboBox, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFrame, QLineEdit, QGridLayout, QTextEdit, QProgressBar, QSizePolicy,
    QScrollArea, QSplitter, QTabWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat, QFont, QDragEnterEvent, QDropEvent

from toolkit.gui.base_tab import BaseTab


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
        self._create_freq_lists_section(mid_layout)
        self._create_strategy_section(mid_layout)
        splitter.addWidget(mid_widget)

        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)
        self._create_log_section(bottom_layout)
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
        hint.setProperty("class", "fieldLabel")
        hint.setStyleSheet("font-size: 10px; font-style: italic;")
        header.addWidget(hint)
        header.addStretch()
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

        row.addWidget(QLabel("备注:"))
        self._notes_input = QLineEdit()
        self._notes_input.setPlaceholderText("push 时随记录保存")
        self._notes_input.setFixedHeight(28)
        row.addWidget(self._notes_input, 1)

        self._save_as_btn = QPushButton("另存为")
        self._save_as_btn.setFixedHeight(28)
        self._save_as_btn.setEnabled(False)
        row.addWidget(self._save_as_btn)

        row.addStretch()
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
        cl.addWidget(self._config_table, 1)

    def _create_freq_lists_section(self, parent_layout: QHBoxLayout):
        freq_wrap = QWidget()
        freq_wrap.setFixedWidth(420)
        freq_layout = QHBoxLayout(freq_wrap)
        freq_layout.setContentsMargins(0, 0, 0, 0)
        freq_layout.setSpacing(4)

        self._freq_edits: dict[str, QTextEdit] = {}
        for name in ("Gold", "Prime", "GPU"):
            card = QFrame()
            card.setProperty("class", "sectionCard")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(6, 4, 6, 4)
            cl.setSpacing(2)
            lbl = QLabel(f"{name} 频率")
            lbl.setProperty("class", "sectionTitleBlue")
            lbl.setStyleSheet("font-size: 10px;")
            cl.addWidget(lbl)
            te = QTextEdit()
            te.setReadOnly(True)
            te.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
            te.setStyleSheet("font-size: 10px;")
            cl.addWidget(te, 1)
            self._freq_edits[name] = te
            freq_layout.addWidget(card, 1)

        parent_layout.addWidget(freq_wrap)

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

    def _create_log_section(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(8, 4, 8, 4)
        cl.setSpacing(2)

        title = QLabel("执行日志")
        title.setProperty("class", "sectionTitleBlue")
        cl.addWidget(title)

        self._log_area = QTextEdit()
        self._log_area.setReadOnly(True)
        self._log_area.setMaximumHeight(150)
        cl.addWidget(self._log_area, 1)

        prog = QHBoxLayout()
        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        prog.addWidget(self._progress_bar, 1)
        self._progress_label = QLabel("0%")
        self._progress_label.setFixedWidth(36)
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        prog.addWidget(self._progress_label)
        cl.addLayout(prog)

        parent_layout.addWidget(card, 1)

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

    def _load_file(self, path: str):
        from .parser import GamePerfParser

        try:
            self.parser = GamePerfParser(path)
        except Exception as e:
            QMessageBox.warning(self.window(), "解析失败", f"解析 XML 失败: {e}")
            return

        if not self.parser.freq_rows:
            QMessageBox.warning(self.window(), "解析失败", "未解析到有效配置数据！")
            return

        self._game_cbx.blockSignals(True)
        self._game_cbx.clear()
        self._game_cbx.addItems(self.parser.get_game_names())
        self._game_cbx.blockSignals(False)

        self._fill_freq_lists()
        self._save_as_btn.setEnabled(True)
        self._on_game_changed()

    def _fill_freq_lists(self):
        if not self.parser:
            return
        for name in ("Gold", "Prime"):
            cluster = self.parser.cpu_clusters.get(name)
            if cluster:
                lines = [f"{i}: {v} Hz" for i, v in enumerate(cluster.frequencies)]
                self._freq_edits[name].setPlainText("\n".join(lines))
            else:
                self._freq_edits[name].clear()
        if self.parser.gpu_cluster:
            lines = [f"{i}: {v} Hz" for i, v in enumerate(self.parser.gpu_cluster.frequencies)]
            self._freq_edits["GPU"].setPlainText("\n".join(lines))
        else:
            self._freq_edits["GPU"].clear()

    # ------------------------------------------------------------------
    # 过滤与刷新
    # ------------------------------------------------------------------

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

    def _refresh_table(self):
        if not self.parser:
            return
        game = self._game_cbx.currentText()
        mode = self._mode_cbx.currentText()
        if not game or not mode:
            return

        self._current_filtered_rows = self.parser.get_filtered_rows(game, mode)
        self._config_table.blockSignals(True)
        self._config_table.setRowCount(len(self._current_filtered_rows))

        for r_idx, row in enumerate(self._current_filtered_rows):
            items = [
                row.temp_level, row.trigger_temp,
                str(row.gold_min), str(row.gold_max), row.gold_index,
                str(row.prime_min), str(row.prime_max), row.prime_index,
                str(row.gpu_min), str(row.gpu_max), row.gpu_index,
            ]
            for c_idx, val in enumerate(items):
                item = QTableWidgetItem(val)
                if c_idx in (1, 4, 7, 10):
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._config_table.setItem(r_idx, c_idx, item)
        self._config_table.blockSignals(False)

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
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 3)

        row_idx = 1
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
                QMessageBox.warning(self.window(), "格式错误", "触发温度请填写 0～200 的整数")
                self._refresh_table()
                return
            self.parser.update_temperature(global_idx, str(t))
            self._refresh_table()
        elif col in (4, 7, 10):
            if "_" not in new_val:
                QMessageBox.warning(self.window(), "格式错误", "索引须为 start_end 格式（如 2_8）")
                self._refresh_table()
                return
            cluster = {4: "Gold", 7: "Prime", 10: "Gpu"}[col]
            self.parser.update_freq_index(global_idx, cluster, new_val)
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
            self._refresh()

    def _on_remove_subtree(self, element):
        r = QMessageBox.question(
            self.window(), "确认删除", "确定删除该节点及其所有子项？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r == QMessageBox.StandardButton.Yes and self.parser:
            if self.parser.remove_subtree(element):
                self._refresh()

    def _on_save_as(self):
        if not self.parser:
            return
        path, _ = QFileDialog.getSaveFileName(
            self.window(), "另存为", "", "XML文件 (*.xml)"
        )
        if path and self.parser.save_as(path):
            QMessageBox.information(self.window(), "保存成功", f"已保存到：\n{path}")

    # ------------------------------------------------------------------
    # 推送/清除/还原
    # ------------------------------------------------------------------

    def _on_push_start(self):
        import logging as _log
        _logger = _log.getLogger(__name__)

        if not self.require_device():
            return
        filepath = self._file_input.text().strip()
        if not filepath:
            QMessageBox.warning(self.window(), "未选择文件", "请先选择要推送的配置文件")
            return
        if not os.path.isfile(filepath):
            QMessageBox.warning(self.window(), "文件不存在", f"找不到文件:\n{filepath}")
            return

        if self.parser and self.parser.xml_path == filepath:
            self.parser.write_to_path(filepath)

        self._save_push_record()
        self._log_area.clear()
        self._set_progress(0)
        self._update_push_button_states(False)

        serial = self._get_serial()
        notes = self._notes_input.text().strip()
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
            self._notes_input.clear()
            self._append_log("↺ 已重置为文件原始内容（保持当前游戏/模式）", "#dcdcaa")
        else:
            self._game_cbx.clear()
            self._mode_cbx.clear()
            self._config_table.setRowCount(0)
            self._notes_input.clear()
            self.parser = None

    def _on_reset(self):
        if not self.require_device():
            return
        self._log_area.clear()
        self._set_progress(0)
        self._update_push_button_states(False)

        serial = self._get_serial()

        def do_reset():
            return self._service.reset(serial, on_progress=self._on_progress_safe)

        self._run_background(do_reset, self._on_push_done)

    def _on_push_done(self, result):
        self._set_progress(100)
        self._update_push_button_states(self._device_connected)

    def _on_push_error(self, exc):
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

    def _save_push_record(self):
        if not self.parser or not self._current_filtered_rows or not self._service:
            return
        from .models import PushRecord

        game = self._game_cbx.currentText()
        mode = self._mode_cbx.currentText()
        pkg = self.parser.get_package_for_alias(game)
        notes = self._notes_input.text().strip()

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
        new_val = min(val + 8, 95)
        self._set_progress(new_val)

    def on_devices_changed(self, devices: list[str]):
        super().on_devices_changed(devices)
        self._update_push_button_states(bool(devices))

    @staticmethod
    def _clear_layout(layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
