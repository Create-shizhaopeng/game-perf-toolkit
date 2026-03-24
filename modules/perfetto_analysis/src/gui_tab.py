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

logger = logging.getLogger(__name__)

_BOTTOM_AREA_HEIGHT = 150
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
            self.progress.emit("分析已中止（已完成的数据已保留）")
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
        ("cpu", "CPU"), ("thread", "线程"), ("binder", "Binder"),
        ("io", "IO"), ("gc", "GC"), ("gpu", "GPU"),
        ("sf", "SF"), ("input", "Input"), ("lock", "Lock"),
        ("summary", "整体"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("全部维度 ▾", parent)
        self.setFixedWidth(120)
        self.setStyleSheet(
            "QPushButton { text-align: left; padding: 2px 6px; }"
        )

        self._menu = _PersistentMenu(self)
        self._actions: dict[str, Any] = {}
        for dim_id, label in self.DIMS:
            action = self._menu.addAction(f"{label} ({dim_id})")
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(self._update_label)
            self._actions[dim_id] = action
        self._menu.addSeparator()
        all_action = self._menu.addAction("全选")
        all_action.triggered.connect(self._select_all)
        none_action = self._menu.addAction("全不选")
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
            self.setText("全部维度 ▾")
        elif sel:
            self.setText(f"{len(sel)} 个维度 ▾")
        else:
            self.setText("未选维度 ▾")

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

    tab_title = "Perfetto 分析"
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
        grp_file = QGroupBox("Trace 文件")
        file_layout = QVBoxLayout(grp_file)
        row = QHBoxLayout()
        self._trace_input = QLineEdit()
        self._trace_input.setPlaceholderText("选择或拖拽 .perfetto-trace 文件")
        self._trace_input.setFixedWidth(320)
        self._trace_input.textChanged.connect(
            lambda text: self._trace_input.setToolTip(text),
        )
        row.addWidget(self._trace_input)
        btn_browse = QPushButton("浏览")
        btn_browse.setFixedWidth(60)
        btn_browse.clicked.connect(self._on_browse_trace)
        row.addWidget(btn_browse)
        row.addStretch()
        file_layout.addLayout(row)
        layout.addWidget(grp_file)

        # --- 分析配置 ---
        grp_cfg = QGroupBox("分析配置")
        cfg_layout = QVBoxLayout(grp_cfg)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("目标进程"))
        self._process_input = QLineEdit()
        self._process_input.setPlaceholderText("留空自动识别")
        self._process_input.setFixedWidth(240)
        row1.addWidget(self._process_input)
        row1.addStretch()
        cfg_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("App 类型"))
        self._app_type_combo = QComboBox()
        self._app_type_combo.addItems(["auto", "app", "game", "camera"])
        self._app_type_combo.setFixedWidth(100)
        row2.addWidget(self._app_type_combo)

        row2.addWidget(QLabel("分析模式"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["完整分析", "仅解析", "独立维度"])
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
        self._status_label = QLabel("● 就绪")
        ctrl_row.addWidget(self._status_label)

        self._btn_start = QPushButton("开始分析")
        self._btn_start.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self._btn_start.setFixedWidth(_BTN_W)
        self._btn_start.clicked.connect(self._on_start)
        ctrl_row.addWidget(self._btn_start)
        self._btn_stop = QPushButton("停止")
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
        self._progress_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._progress_label)

        # --- 分析历史 ---
        layout.addWidget(QLabel("📜 分析历史"))
        self._history_table = QTableWidget(0, 6)
        self._history_table.setHorizontalHeaderLabels(
            ["Trace", "目标进程", "模式", "时间", "状态", "操作"],
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
        self._result_group = QGroupBox("分析结果")
        result_layout = QVBoxLayout(self._result_group)
        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        self._result_text.setPlaceholderText("分析完成后显示结果概览")
        result_layout.addWidget(self._result_text)
        self._result_group.setVisible(False)
        layout.addWidget(self._result_group)

        layout.addStretch()

        # --- 操作日志（与左侧控制区等高对齐） ---
        log_box = QWidget()
        log_box.setFixedHeight(_BOTTOM_AREA_HEIGHT)
        log_box_layout = QVBoxLayout(log_box)
        log_box_layout.setContentsMargins(0, 4, 0, 0)
        log_box_layout.addWidget(QLabel("📋 操作日志"))
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setStyleSheet("font-size: 11px;")
        log_box_layout.addWidget(self._log_text)
        layout.addWidget(log_box)

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
            self, "选择 Trace 文件", "",
            "Perfetto Trace (*.perfetto-trace *.perfetto);;所有文件 (*)",
        )
        if path:
            self._trace_input.setText(path)

    def _on_mode_changed(self, index: int) -> None:
        self._dim_selector.setVisible(index == 2)

    def _on_start(self) -> None:
        trace_path = self._trace_input.text().strip()
        if not trace_path:
            self._log("请先选择 Trace 文件")
            return
        if not Path(trace_path).exists():
            self._log(f"文件不存在: {trace_path}")
            return

        svc = self._get_service()
        if not svc:
            self._log("服务未初始化")
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
                self._log("请至少选择一个分析维度")
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
        self._log(f"开始分析: {Path(trace_path).name}")

    def _on_stop(self) -> None:
        if self._worker:
            self._worker.abort()
            self._log("正在停止分析...")
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
            lines.append(f"目标进程: {detected}")
        report_path = getattr(result, "report_path", "")
        if report_path:
            lines.append(f"报告路径: {report_path}")
        lines.append(f"丢帧次数: {result.jank_times}")
        lines.append(f"总帧数: {result.frame_num}")
        lines.append(f"刷新率: {result.refresh_rate_hz}Hz")
        if result.app_type:
            lines.append(f"App 类型: {result.app_type}")
        lines.append(f"分析耗时: {result.elapsed_seconds}s")
        if result.dimensions_completed:
            lines.append(f"\n维度完成: {', '.join(result.dimensions_completed)}")
        if result.dimensions_skipped:
            lines.append(f"维度跳过: {', '.join(result.dimensions_skipped)}")
        self._result_text.setPlainText("\n".join(lines))
        self._log(f"✅ 分析完成 ({result.elapsed_seconds}s)")
        self._refresh_history()

    def _on_error(self, msg: str) -> None:
        self._set_running(False)
        self._log(f"❌ 分析失败: {msg}")

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
        self._status_label.setText("● 分析中..." if running else "● 就绪")
        if not running:
            self._progress_label.setText("")

    def _log(self, msg: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log_text.append(f"[{ts}] {msg}")

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
            mode_labels = {"full": "完整", "parse": "仅解析", "dimensions": "独立维度"}
            mode_text = mode_labels.get(mode_raw, mode_raw)
            mode_item = QTableWidgetItem(mode_text)
            if mode_raw == "dimensions" and dims_raw:
                mode_item.setToolTip(f"维度: {dims_raw}")
            else:
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
            btn_redo.setToolTip("从数据库重新生成报告")
            btn_redo.setFixedSize(26, 22)
            btn_redo.setEnabled(trace_exists)
            btn_redo.clicked.connect(
                lambda checked, tp=trace_path: self._regenerate_report(tp),
            )
            ops_layout.addWidget(btn_redo)

            btn_report = QPushButton()
            btn_report.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon))
            btn_report.setToolTip("打开分析报告")
            btn_report.setFixedSize(26, 22)
            btn_report.setEnabled(bool(has_report))
            rp = str(report_file) if report_file else ""
            btn_report.clicked.connect(
                lambda checked, p=rp: self._open_report_file(p),
            )
            ops_layout.addWidget(btn_report)

            btn_open = QPushButton()
            btn_open.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
            btn_open.setToolTip("打开报告所在目录")
            btn_open.setFixedSize(26, 22)
            btn_open.setEnabled(report_exists)
            btn_open.clicked.connect(
                lambda checked, rd=report_dir: self._open_report_dir(rd),
            )
            ops_layout.addWidget(btn_open)

            btn_del = QPushButton()
            btn_del.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
            btn_del.setToolTip("删除该分析报告")
            btn_del.setFixedSize(26, 22)
            btn_del.setEnabled(report_exists)
            btn_del.setStyleSheet(
                "QPushButton { color: #e74c3c; }"
                "QPushButton:hover { background-color: #e74c3c; color: white; }"
            )
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
            self._log("服务未初始化")
            return
        self._log(f"重新生成报告: {Path(trace_path).name}")
        result = svc.regenerate_report(
            trace_path,
            on_progress=lambda msg: self._log(msg),
        )
        if result:
            QTimer.singleShot(100, self._refresh_history)
        else:
            self._log("重新生成报告失败（数据库中可能无该 trace 数据）")

    def _open_report_file(self, report_path: str) -> None:
        try:
            if report_path and Path(report_path).exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(report_path))
            else:
                self._log("报告文件不存在")
        except Exception as e:
            self._log(f"打开报告失败: {e}")

    def _open_report_dir(self, report_dir: str) -> None:
        try:
            if report_dir and Path(report_dir).exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(report_dir))
            else:
                self._log("报告目录不存在或未生成")
        except Exception as e:
            self._log(f"打开目录失败: {e}")

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
                self._log(f"删除文件失败: {e}")

        if deleted_files:
            self._log(f"已删除: {dir_name}")
        elif can_delete_dir:
            self._log(f"已删除记录: {dir_name or trace_path}")
        else:
            self._log(f"已删除记录（报告目录保留，其他模式仍在使用）")
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
