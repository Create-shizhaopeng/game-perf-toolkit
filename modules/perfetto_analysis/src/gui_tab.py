# -*- coding: utf-8 -*-
"""Perfetto 解析分析 — GUI Tab（左右分栏布局）。"""
from __future__ import annotations

import datetime
import logging
import shutil
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.base_tab import BaseTab
from . import strings_gui as s

logger = logging.getLogger(__name__)

_LEFT_PANEL_W = 580


# ---------------------------------------------------------------------------
# 后台分析线程
# ---------------------------------------------------------------------------

class _AnalysisWorker(QThread):
    """在后台线程执行分析，通过信号更新 UI。

    abort() 设置 _abort 标志；run() 在每次 on_progress 回调中检查。
    若分析被中止，已完成的 Phase 1 数据会保留在 DB 中。
    """

    progress = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs) -> None:
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._abort = False

    def run(self) -> None:
        try:
            result = self._func(*self._args, **self._kwargs)
            if not self._abort:
                self.finished.emit(result)
        except _AbortedError:
            self.progress.emit(s.WORKER_ABORTED)
        except Exception as e:
            if not self._abort:
                self.error.emit(str(e))

    def abort(self) -> None:
        self._abort = True

    @property
    def aborted(self) -> bool:
        return self._abort


class _AbortedError(Exception):
    """分析被用户主动中止。"""


# ---------------------------------------------------------------------------
# 点击选项后不自动关闭的菜单
# ---------------------------------------------------------------------------

class _PersistentMenu(QMenu):
    """点击可勾选项后保持打开，点击其他区域才关闭。"""

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        action = self.activeAction()
        if action and action.isCheckable():
            action.trigger()
            return
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
# 维度多选下拉
# ---------------------------------------------------------------------------

class _DimensionSelector(QPushButton):
    """维度多选控件，外观模仿 QComboBox 下拉箭头样式。"""

    DIMS = [
        ("cpu", "CPU"), ("thread", s.DIM_LABEL_THREAD), ("binder", "Binder"),
        ("io", "IO"), ("gc", "GC"), ("gpu", "GPU"),
        ("sf", "SF"), ("input", "Input"), ("lock", "Lock"),
        ("summary", s.DIM_LABEL_SUMMARY),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(s.DIM_SELECTOR_ALL, parent)
        self.setFixedWidth(120)
        self.setObjectName("dimensionSelector")

        self._menu = _PersistentMenu(self)
        self._actions: dict[str, Any] = {}
        for dim_id, label in self.DIMS:
            action = self._menu.addAction(f"{label} ({dim_id})")
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(self._update_label)
            self._actions[dim_id] = action
        self._menu.addSeparator()
        all_action = self._menu.addAction(s.BTN_SELECT_ALL)
        all_action.triggered.connect(self._select_all)
        none_action = self._menu.addAction(s.BTN_SELECT_NONE)
        none_action.triggered.connect(self._select_none)

        self.clicked.connect(self._show_menu)

    def _show_menu(self) -> None:
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._menu.popup(pos)

    def selected_dims(self) -> list[str]:
        return [d for d, a in self._actions.items() if a.isChecked()]

    def _update_label(self) -> None:
        sel = self.selected_dims()
        if len(sel) == len(self.DIMS):
            self.setText(s.DIM_SELECTOR_ALL)
        elif sel:
            self.setText(s.DIM_SELECTOR_COUNT_FMT.format(len(sel)))
        else:
            self.setText(s.DIM_SELECTOR_NONE)

    def _select_all(self) -> None:
        for a in self._actions.values():
            a.setChecked(True)

    def _select_none(self) -> None:
        for a in self._actions.values():
            a.setChecked(False)


# ---------------------------------------------------------------------------
# 主 Tab
# ---------------------------------------------------------------------------

class PerfettoAnalysisTab(BaseTab):

    tab_title = s.TAB_TITLE
    tab_icon = "📊"

    def __init__(self, context: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(context=context, parent=parent)
        self._worker: _AnalysisWorker | None = None
        self._service = None
        self.setAcceptDrops(True)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root_layout.addWidget(splitter)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(_LEFT_PANEL_W)
        layout = QVBoxLayout(panel)

        # --- Trace 文件选择 ---
        grp_file = QGroupBox(s.GROUP_TRACE_FILE)
        file_layout = QVBoxLayout(grp_file)
        row = QHBoxLayout()
        self._trace_input = QLineEdit()
        self._trace_input.setPlaceholderText(s.PLACEHOLDER_TRACE_FILE)
        self._trace_input.setFixedWidth(320)
        self._trace_input.textChanged.connect(
            lambda text: self._trace_input.setToolTip(text),
        )
        row.addWidget(self._trace_input)
        btn_browse = QPushButton(s.BTN_BROWSE)
        btn_browse.setFixedWidth(60)
        btn_browse.clicked.connect(self._on_browse_trace)
        row.addWidget(btn_browse)
        row.addStretch()
        file_layout.addLayout(row)
        layout.addWidget(grp_file)

        # --- 分析配置 ---
        grp_cfg = QGroupBox(s.GROUP_ANALYSIS_CONFIG)
        cfg_layout = QVBoxLayout(grp_cfg)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel(s.LABEL_TARGET_PROCESS))
        self._process_input = QLineEdit()
        self._process_input.setPlaceholderText(s.PLACEHOLDER_PROCESS)
        self._process_input.setFixedWidth(240)
        row1.addWidget(self._process_input)
        row1.addStretch()
        cfg_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel(s.LABEL_APP_TYPE))
        self._app_type_combo = QComboBox()
        self._app_type_combo.addItems(["auto", "app", "game", "camera"])
        self._app_type_combo.setFixedWidth(100)
        row2.addWidget(self._app_type_combo)

        row2.addWidget(QLabel(s.LABEL_ANALYSIS_MODE))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems([s.MODE_ITEM_FULL, s.MODE_ITEM_PARSE, s.MODE_ITEM_DIMENSIONS])
        self._mode_combo.setFixedWidth(100)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        row2.addWidget(self._mode_combo)

        self._dim_selector = _DimensionSelector()
        self._dim_selector.setVisible(False)
        row2.addWidget(self._dim_selector)
        row2.addStretch()
        cfg_layout.addLayout(row2)

        # Top N / Binder 阈值 / 调度延迟使用 config.json 中的默认值

        layout.addWidget(grp_cfg)

        # --- 控制区（位于配置与历史之间） ---
        _BTN_W = 100
        style = self.style()

        ctrl_row = QHBoxLayout()
        self._status_label = QLabel(s.LABEL_STATUS_READY)
        ctrl_row.addWidget(self._status_label)

        self._btn_start = QPushButton(s.BTN_START_ANALYSIS)
        self._btn_start.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self._btn_start.setFixedWidth(_BTN_W)
        self._btn_start.clicked.connect(self._on_start)
        ctrl_row.addWidget(self._btn_start)
        self._btn_stop = QPushButton(s.BTN_STOP)
        self._btn_stop.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self._btn_stop.setFixedWidth(_BTN_W)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)
        ctrl_row.addWidget(self._btn_stop)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setObjectName("fieldHint")
        layout.addWidget(self._progress_label)

        # --- 分析历史 ---
        layout.addWidget(QLabel(s.LABEL_HISTORY_TITLE))
        self._history_table = QTableWidget(0, 6)
        self._history_table.setHorizontalHeaderLabels(
            [
                s.HISTORY_HEADER_TRACE,
                s.HISTORY_HEADER_TARGET_PROCESS,
                s.HISTORY_HEADER_MODE,
                s.HISTORY_HEADER_TIME,
                s.HISTORY_HEADER_STATUS,
                s.HISTORY_HEADER_OPERATION,
            ],
        )
        self._history_table.cellDoubleClicked.connect(self._on_history_double_click)
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self._history_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(0, 140)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(1, 120)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(2, 60)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(3, 80)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(4, 36)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(5, 120)
        layout.addWidget(self._history_table)

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # --- 分析结果预览 ---
        self._result_group = QGroupBox(s.GROUP_ANALYSIS_RESULT)
        result_layout = QVBoxLayout(self._result_group)
        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        self._result_text.setPlaceholderText(s.PLACEHOLDER_RESULT)
        result_layout.addWidget(self._result_text)
        self._result_group.setVisible(False)
        layout.addWidget(self._result_group)

        layout.addStretch()

        return panel

    # ------------------------------------------------------------------
    # 交互事件
    # ------------------------------------------------------------------

    def _get_service(self):
        if self._service:
            return self._service
        self._service = self.context.get("pa_service")
        if self._service:
            cfg = self._service.get_config()
            if cfg.default_process:
                self._process_input.setText(cfg.default_process)
            idx = ["auto", "app", "game", "camera"].index(cfg.app_type)
            self._app_type_combo.setCurrentIndex(idx)
        return self._service

    def _on_browse_trace(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, s.DLG_TITLE_SELECT_TRACE, "",
            s.FILE_FILTER_PERFETTO_TRACE,
        )
        if path:
            self._trace_input.setText(path)

    def _on_mode_changed(self, index: int) -> None:
        self._dim_selector.setVisible(index == 2)

    def _on_start(self) -> None:
        trace_path = self._trace_input.text().strip()
        if not trace_path:
            self._log(s.LOG_SELECT_TRACE_FIRST)
            return
        if not Path(trace_path).exists():
            self._log(s.LOG_FILE_NOT_FOUND_FMT.format(trace_path))
            return

        svc = self._get_service()
        if not svc:
            self._log(s.LOG_SERVICE_NOT_INIT)
            return

        cfg = svc.get_config()
        cfg.app_type = self._app_type_combo.currentText()

        process_name = self._process_input.text().strip()
        mode_idx = self._mode_combo.currentIndex()

        self._set_running(True)
        self._result_group.setVisible(False)

        if mode_idx == 0:  # 完整分析
            self._worker = _AnalysisWorker(
                svc.analyze, trace_path, process_name,
                on_progress=self._on_worker_progress_emit,
            )
        elif mode_idx == 1:  # 仅解析
            self._worker = _AnalysisWorker(
                svc.parse_only, trace_path, process_name,
                on_progress=self._on_worker_progress_emit,
            )
        else:  # 独立维度
            dims = self._dim_selector.selected_dims()
            if not dims:
                self._log(s.LOG_SELECT_DIMENSION)
                self._set_running(False)
                return
            self._worker = _AnalysisWorker(
                svc.analyze_dimensions, trace_path, process_name,
                dimensions=dims,
                on_progress=self._on_worker_progress_emit,
            )

        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()
        self._log(s.LOG_START_ANALYSIS_FMT.format(Path(trace_path).name))

    def _on_stop(self) -> None:
        if self._worker:
            self._worker.abort()
            self._log(s.LOG_STOPPING_ANALYSIS)
            self._set_running(False)

    def _on_worker_progress_emit(self, msg: str) -> None:
        """在工作线程内调用，通过信号发送到主线程。检测中止标志。"""
        if self._worker:
            if self._worker.aborted:
                raise _AbortedError("用户中止分析")
            self._worker.progress.emit(msg)

    def _on_progress(self, msg: str) -> None:
        self._progress_label.setText(msg)
        self._log(msg)

    def _on_finished(self, result: Any) -> None:
        self._set_running(False)
        if result is None:
            return

        self._result_group.setVisible(True)

        detected = getattr(result, "detected_process", "") or ""
        lines = []
        if detected:
            lines.append(s.RESULT_TARGET_PROCESS_FMT.format(detected))
        report_path = getattr(result, "report_path", "")
        if report_path:
            lines.append(s.RESULT_REPORT_PATH_FMT.format(report_path))
        lines.append(s.RESULT_JANK_TIMES_FMT.format(result.jank_times))
        lines.append(s.RESULT_FRAME_NUM_FMT.format(result.frame_num))
        lines.append(s.RESULT_REFRESH_RATE_FMT.format(result.refresh_rate_hz))
        if result.app_type:
            lines.append(s.RESULT_APP_TYPE_FMT.format(result.app_type))
        lines.append(s.RESULT_ELAPSED_FMT.format(result.elapsed_seconds))
        if result.dimensions_completed:
            lines.append(s.RESULT_DIMENSIONS_COMPLETED_FMT.format(", ".join(result.dimensions_completed)))
        if result.dimensions_skipped:
            lines.append(s.RESULT_DIMENSIONS_SKIPPED_FMT.format(", ".join(result.dimensions_skipped)))
        self._result_text.setPlainText("\n".join(lines))
        self._log(s.LOG_ANALYSIS_COMPLETE_FMT.format(result.elapsed_seconds))
        self._refresh_history()

    def _on_error(self, msg: str) -> None:
        self._set_running(False)
        self._log(s.LOG_ANALYSIS_FAILED_FMT.format(msg))

    # ------------------------------------------------------------------
    # 拖拽支持
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData() and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        if event.mimeData() and event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                self._trace_input.setText(path)

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _set_running(self, running: bool) -> None:
        self._btn_start.setEnabled(not running)
        self._btn_stop.setEnabled(running)
        self._progress_bar.setVisible(running)
        self._status_label.setText(
            s.LABEL_STATUS_ANALYZING if running else s.LABEL_STATUS_READY,
        )
        if not running:
            self._progress_label.setText("")

    def _log(self, msg: str, level: str = "info") -> None:
        if "❌" in msg or s.FAILURE_KEYWORD in msg:
            level = "error"
        elif "✅" in msg:
            level = "success"
        super()._log(msg, level=level)

    @staticmethod
    def _make_item(text: str) -> QTableWidgetItem:
        """创建带 tooltip 的表格项（超出列宽时悬停显示完整内容）。"""
        item = QTableWidgetItem(text)
        item.setToolTip(text)
        return item

    def _refresh_history(self) -> None:
        svc = self._get_service()
        if not svc:
            return
        try:
            records = svc.get_analysis_history()
        except Exception:
            return

        self._history_table.setRowCount(0)
        style = self.style()

        for r in records[:20]:
            row = self._history_table.rowCount()
            self._history_table.insertRow(row)

            trace_path = r.get("trace_path", "")
            report_dir = r.get("report_dir_path", "")
            if trace_path:
                trace_name = Path(trace_path).name
            elif report_dir:
                trace_name = Path(report_dir).name
            else:
                trace_name = r.get("trace_id", "")
            self._history_table.setItem(row, 0, self._make_item(str(trace_name)))

            proc = r.get("process_name", "") or ""
            self._history_table.setItem(row, 1, self._make_item(proc))

            mode_raw = r.get("mode", "full") or "full"
            dims_raw = r.get("dimensions", "") or ""
            mode_labels = s.MODE_LABELS
            mode_text = mode_labels.get(mode_raw, mode_raw)
            mode_item = QTableWidgetItem(mode_text)
            if mode_raw == "dimensions" and dims_raw:
                mode_item.setToolTip(s.MODE_DIMS_TIP_FMT.format(dims_raw))
            mode_item.setToolTip(mode_text)
            self._history_table.setItem(row, 2, mode_item)

            created_at = r.get("created_at")
            parsed_at = r.get("parsed_at_ns", "")
            ts_val = created_at or parsed_at
            if isinstance(ts_val, int) and ts_val > 0:
                dt = datetime.datetime.fromtimestamp(ts_val / 1e9)
                ts_str = dt.strftime("%m-%d %H:%M")
            else:
                ts_str = str(ts_val) if ts_val else ""
            self._history_table.setItem(row, 3, self._make_item(ts_str))

            if not report_dir and trace_path:
                _svc = self._get_service()
                if _svc:
                    stem = Path(trace_path).stem
                    if stem.endswith(".perfetto"):
                        stem = Path(stem).stem
                    report_dir = str(Path(_svc._get_output_dir()) / stem)

            report_exists = bool(report_dir) and Path(report_dir).exists()
            report_file = Path(report_dir) / "jank_report.md" if report_dir else None
            has_report = report_file and report_file.exists()
            if has_report:
                status = "✅"
            elif report_exists:
                status = "⚠"
            else:
                status = "—"
            self._history_table.setItem(row, 4, QTableWidgetItem(status))

            trace_exists = bool(trace_path) and Path(trace_path).is_file()

            ops_widget = QWidget()
            ops_layout = QHBoxLayout(ops_widget)
            ops_layout.setContentsMargins(2, 0, 2, 0)
            ops_layout.setSpacing(2)

            btn_redo = QPushButton()
            btn_redo.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
            btn_redo.setToolTip(s.TOOLTIP_REGENERATE_REPORT)
            btn_redo.setFixedSize(26, 22)
            btn_redo.setEnabled(trace_exists)
            btn_redo.clicked.connect(
                lambda checked, tp=trace_path: self._regenerate_report(tp),
            )
            ops_layout.addWidget(btn_redo)

            btn_report = QPushButton()
            btn_report.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon))
            btn_report.setToolTip(s.TOOLTIP_OPEN_REPORT)
            btn_report.setFixedSize(26, 22)
            btn_report.setEnabled(bool(has_report))
            rp = str(report_file) if report_file else ""
            btn_report.clicked.connect(
                lambda checked, p=rp: self._open_report_file(p),
            )
            ops_layout.addWidget(btn_report)

            btn_open = QPushButton()
            btn_open.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
            btn_open.setToolTip(s.TOOLTIP_OPEN_REPORT_DIR)
            btn_open.setFixedSize(26, 22)
            btn_open.setEnabled(report_exists)
            btn_open.clicked.connect(
                lambda checked, rd=report_dir: self._open_report_dir(rd),
            )
            ops_layout.addWidget(btn_open)

            btn_del = QPushButton()
            btn_del.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
            btn_del.setToolTip(s.TOOLTIP_DELETE_REPORT)
            btn_del.setObjectName("dangerIconBtn")
            btn_del.setFixedSize(26, 22)
            btn_del.setEnabled(report_exists)
            task_id = r.get("task_id", "")
            btn_del.clicked.connect(
                lambda checked, rd=report_dir, tp=trace_path, tid=task_id: (
                    self._delete_report(rd, tp, tid)
                ),
            )
            ops_layout.addWidget(btn_del)

            self._history_table.setCellWidget(row, 5, ops_widget)

    def _regenerate_report(self, trace_path: str) -> None:
        """从数据库重新生成报告（不重新分析 trace）。"""
        svc = self._get_service()
        if not svc:
            self._log(s.LOG_SERVICE_NOT_INIT)
            return
        self._log(s.LOG_REGENERATE_REPORT_FMT.format(Path(trace_path).name))
        result = svc.regenerate_report(
            trace_path,
            on_progress=lambda msg: self._log(msg),
        )
        if result:
            QTimer.singleShot(100, self._refresh_history)
        else:
            self._log(s.LOG_REGENERATE_FAIL)

    def _open_report_file(self, report_path: str) -> None:
        try:
            if report_path and Path(report_path).exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(report_path))
            else:
                self._log(s.LOG_REPORT_NOT_FOUND)
        except Exception as e:
            self._log(s.LOG_OPEN_REPORT_FAIL_FMT.format(e))

    def _open_report_dir(self, report_dir: str) -> None:
        try:
            if report_dir and Path(report_dir).exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(report_dir))
            else:
                self._log(s.LOG_REPORT_DIR_NOT_FOUND)
        except Exception as e:
            self._log(s.LOG_OPEN_DIR_FAIL_FMT.format(e))

    def _delete_report(
        self, report_dir: str, trace_path: str = "", task_id: str = "",
    ) -> None:
        dir_name = Path(report_dir).name if report_dir else ""

        svc = self._get_service()
        can_delete_dir = True
        if svc:
            try:
                can_delete_dir = svc.delete_analysis_record(
                    task_id=task_id,
                    trace_path=trace_path,
                    report_dir=report_dir,
                )
            except Exception:
                pass

        deleted_files = False
        if can_delete_dir and report_dir and Path(report_dir).exists():
            try:
                shutil.rmtree(report_dir)
                deleted_files = True
            except Exception as e:
                self._log(s.LOG_DELETE_FILE_FAIL_FMT.format(e))

        if deleted_files:
            self._log(s.LOG_DELETED_FMT.format(dir_name))
        elif can_delete_dir:
            self._log(s.LOG_DELETED_RECORD_FMT.format(dir_name or trace_path))
        else:
            self._log(s.LOG_DELETED_RECORD_KEEP_DIR)
        QTimer.singleShot(100, self._refresh_history)

    def _on_history_double_click(self, row: int, col: int) -> None:
        """双击历史记录行重新生成报告。"""
        item = self._history_table.item(row, 0)
        if not item:
            return
        trace_name = item.text()
        svc = self._get_service()
        if not svc:
            return
        try:
            records = svc.get_analysis_history()
            for r in records:
                if Path(r.get("trace_path", "")).name == trace_name:
                    self._regenerate_report(r["trace_path"])
                    return
        except Exception:
            pass

    def on_activated(self) -> None:
        self._get_service()
        self._refresh_history()
