"""Perfetto 抓取模块 — GUI 页面（方案 A：左右分栏）"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSize, QThread, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.toolkit_dialog import warning_dialog

from .strings_gui import *


class _FlowWidget(QWidget):
    """自动换行的流式容器，根据自身宽度动态调整子控件列数和高度。"""

    def __init__(self, parent: QWidget | None = None, h_spacing: int = 8, v_spacing: int = 4) -> None:
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._children: list[QWidget] = []

    def add_widget(self, w: QWidget) -> None:
        w.setParent(self)
        self._children.append(w)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        if not self._children:
            return
        width = self.width()
        if width <= 0:
            return
        x, y, line_height = 0, 0, 0
        for w in self._children:
            hint = w.sizeHint()
            iw, ih = hint.width(), hint.height()
            if x + iw > width and line_height > 0:
                x = 0
                y += line_height + self._v_spacing
                line_height = 0
            w.setGeometry(x, y, iw, ih)
            x += iw + self._h_spacing
            line_height = max(line_height, ih)
        total_h = y + line_height
        if total_h != self.minimumHeight():
            self.setMinimumHeight(total_h)
            self.setMaximumHeight(total_h)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(200, self.minimumHeight() or 20)

from toolkit.gui.base_tab import BaseTab
from toolkit.gui.theme_colors import THEMES as _THEME_COLORS

logger = logging.getLogger(__name__)
HISTORY_SEND_TO_AGENT_EVENT = "history.send_to_agent"


class _CaptureWorker(QThread):
    """后台抓取控制线程。"""

    progress = pyqtSignal(str)
    started_ok = pyqtSignal()
    save_ok = pyqtSignal(int)
    export_ok = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, action: str, service: Any, serial: str, **kwargs: Any) -> None:
        super().__init__()
        self._action = action
        self._svc = service
        self._serial = serial
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            if self._action == "start":
                device_dir = self._svc.ensure_device_trace_dir(self._serial)
                self._svc.create_session(self._serial)
                self._svc.session_start_capture(self._serial, device_dir)
                self.progress.emit(WORKER_CAPTURE_STARTED)
                self.started_ok.emit()

            elif self._action == "save":
                device_info = self._kwargs["device_info"]
                device_dir = self._kwargs["device_dir"]
                self._svc.session_save_trace(self._serial, device_dir, device_info)
                count = len(self._svc.session.saved_traces) if self._svc.session else 0
                self.progress.emit(WORKER_SAVED_FMT.format(count))
                self.save_ok.emit(count)

            elif self._action == "stop":
                device_info = self._kwargs.get("device_info")
                device_dir = self._kwargs.get("device_dir")
                auto_save = self._kwargs.get("auto_save", False)

                if auto_save and device_info and device_dir:
                    exported = self._svc.session_stop_with_auto_save(
                        self._serial,
                        device_info,
                        device_dir,
                        on_progress=lambda msg: self.progress.emit(msg),
                    )
                else:
                    exported = self._svc.session_stop_and_export(
                        self._serial,
                        on_progress=lambda msg: self.progress.emit(msg),
                    )
                self.progress.emit(WORKER_EXPORTED_FMT.format(len(exported)))
                self.export_ok.emit([str(p) for p in exported])

            elif self._action == "reconnect":
                session = self._svc.session
                if session and session.running:
                    try:
                        self._svc.stop_tracing(self._serial, session.running)
                    except Exception:
                        pass
                    session.running = None
                device_dir = self._svc.ensure_device_trace_dir(self._serial)
                self._svc.session_start_capture(self._serial, device_dir)
                self.progress.emit(WORKER_CAPTURE_RESUMED)
                self.started_ok.emit()

        except Exception as e:
            self.error.emit(str(e))


class PerfettoCaptureTab(BaseTab):
    tab_title = TAB_TITLE
    tab_icon = "🔍"

    def __init__(self, context: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._service = None
        self._adb = None
        self._serial: str | None = None
        self._device_info = None
        self._device_dir: str | None = None
        self._worker: _CaptureWorker | None = None
        self._capturing = False
        self._waiting_reconnect = False
        self._saved_count = 0
        self._capture_start_time: datetime.datetime | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_timer)
        from .config_manager import load_config
        self._cfg = load_config()
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        ctrl_height = 26
        spin_width = 100
        btn_width = 100

        # ── 上部滚动区：配置 + Categories + Ftrace ──
        top_scroll = QScrollArea()
        top_scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(8)

        # ── 配置面板：Duration | Buffer | 导入  同一行 ──
        config_group = QGroupBox(GROUP_CAPTURE_CONFIG)
        config_vbox = QVBoxLayout()
        config_vbox.setSpacing(6)

        config_row = QHBoxLayout()
        config_row.setSpacing(8)
        config_row.addWidget(QLabel("Duration"))
        self._spin_duration = QSpinBox()
        self._spin_duration.setRange(1, 3600)
        self._spin_duration.setValue(15)
        self._spin_duration.setFixedSize(spin_width, ctrl_height)
        config_row.addWidget(self._spin_duration)
        config_row.addWidget(QLabel(LABEL_SECONDS))
        config_row.addSpacing(12)
        config_row.addWidget(QLabel("Buffer"))
        self._spin_buffer = QSpinBox()
        self._spin_buffer.setRange(91136, 512000)
        self._spin_buffer.setValue(91136)
        self._spin_buffer.setFixedSize(spin_width, ctrl_height)
        self._spin_buffer.setEnabled(False)
        self._spin_buffer.setReadOnly(True)
        config_row.addWidget(self._spin_buffer)
        config_row.addWidget(QLabel(LABEL_KB))
        config_row.addSpacing(12)
        self._btn_import_config = QPushButton(BTN_IMPORT_CONFIG)
        self._btn_import_config.setFixedSize(btn_width, ctrl_height)
        self._btn_import_config.setToolTip(TOOLTIP_IMPORT_CONFIG)
        self._btn_import_config.clicked.connect(self._on_import_config)
        config_row.addWidget(self._btn_import_config)
        config_row.addStretch()
        config_vbox.addLayout(config_row)

        self._spin_duration.valueChanged.connect(self._update_auto_buffer)

        chk_row = QHBoxLayout()
        self._chk_manual_buffer = QCheckBox(CHECK_MANUAL_BUFFER)
        self._chk_manual_buffer.toggled.connect(self._on_manual_buffer_toggled)
        self._chk_ftrace = QCheckBox(CHECK_FTRACE_CUSTOM)
        self._chk_jank = QCheckBox(CHECK_JANK_MONITOR)
        self._chk_jank.toggled.connect(self._on_jank_toggled)
        chk_row.addWidget(self._chk_manual_buffer)
        chk_row.addWidget(self._chk_ftrace)
        chk_row.addWidget(self._chk_jank)
        chk_row.addStretch()
        config_vbox.addLayout(chk_row)

        config_group.setLayout(config_vbox)
        scroll_layout.addWidget(config_group)

        # ── Categories 面板（FlowWidget 自适应列数） ──
        cat_group = QGroupBox(GROUP_ATRACE_CATEGORIES)
        cat_group_layout = QVBoxLayout(cat_group)
        cat_group_layout.setContentsMargins(8, 4, 8, 4)
        cat_inner = _FlowWidget(h_spacing=8, v_spacing=4)
        self._cat_checks: dict[str, QCheckBox] = {}
        all_cats = [
            "sched", "freq", "idle", "am", "wm", "gfx", "view",
            "input", "irq", "sync", "binder_driver", "webview",
            "workq", "thermal", "pagecache", "dalvik", "pm", "ss", "memreclaim",
        ]
        recommended_cats = {"sched", "gfx", "view", "input", "am", "wm", "freq"}
        for cat in all_cats:
            cb = QCheckBox(cat)
            cb.setChecked(cat in recommended_cats)
            cb.toggled.connect(self._update_auto_buffer)
            self._cat_checks[cat] = cb
            cat_inner.add_widget(cb)
        cat_group_layout.addWidget(cat_inner)
        scroll_layout.addWidget(cat_group)

        # ── Ftrace Events 面板（默认隐藏） ──
        self._ftrace_group = QGroupBox(GROUP_FTRACE_EVENTS)
        ftrace_group_layout = QVBoxLayout(self._ftrace_group)
        ftrace_group_layout.setContentsMargins(8, 4, 8, 4)
        self._ftrace_inner = _FlowWidget(h_spacing=8, v_spacing=4)
        self._ftrace_checks: dict[str, QCheckBox] = {}
        for evt in self._cfg.advanced.available_ftrace_events:
            short = evt.split("/")[-1] if "/" in evt else evt
            cb = QCheckBox(short)
            cb.setToolTip(evt)
            cb.toggled.connect(self._update_auto_buffer)
            self._ftrace_checks[evt] = cb
            self._ftrace_inner.add_widget(cb)
        ftrace_group_layout.addWidget(self._ftrace_inner)
        self._ftrace_group.setVisible(False)
        self._chk_ftrace.toggled.connect(self._ftrace_group.setVisible)
        self._chk_ftrace.toggled.connect(lambda _: self._update_auto_buffer())
        scroll_layout.addWidget(self._ftrace_group)

        # ── Jank 监控面板（默认隐藏）：左配置 + 右曲线 ──
        self._jank_group = QGroupBox(GROUP_JANK_MONITOR)
        jank_outer = QHBoxLayout(self._jank_group)
        jank_outer.setContentsMargins(4, 4, 4, 4)
        jank_outer.setSpacing(4)

        from .jank_panel import JankConfigPanel
        from .fps_chart import FpsChartWidget

        self._jank_config_panel = JankConfigPanel()
        self._jank_config_panel.config_changed.connect(self._on_jank_config_changed)
        self._jank_config_panel.app_selector.refresh_requested.connect(self._refresh_jank_apps)
        self._jank_config_panel.pause_clicked.connect(self._on_jank_pause_clicked)
        self._jank_config_panel.export_clicked.connect(self._on_jank_export_clicked)
        jank_outer.addWidget(self._jank_config_panel)

        self._fps_chart = FpsChartWidget()
        self._fps_chart.setMinimumHeight(180)
        jank_outer.addWidget(self._fps_chart, 1)

        self._jank_group.setVisible(False)
        scroll_layout.addWidget(self._jank_group)

        # Jank Worker
        self._jank_worker = None
        self._jank_enabled = False
        self._jank_duration_timer: QTimer | None = None

        scroll_layout.addStretch()
        top_scroll.setWidget(scroll_widget)
        root.addWidget(top_scroll, 1)

        # ── 底部固定区：状态 + 按钮 + 日志 ──
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)

        status_group = QGroupBox(GROUP_SESSION_STATUS)
        status_row = QHBoxLayout()
        status_row.setSpacing(16)
        self._lbl_status = QLabel(LABEL_STATUS_READY_EMOJI)
        self._lbl_saved = QLabel(LABEL_SAVED_DEFAULT_FMT)
        self._lbl_timer = QLabel(LABEL_TIMER_DEFAULT_FMT)
        self._lbl_device = QLabel(LABEL_DEVICE_DEFAULT)
        status_row.addWidget(self._lbl_status)
        status_row.addWidget(self._lbl_saved)
        status_row.addWidget(self._lbl_timer)
        status_row.addWidget(self._lbl_device, 1)
        status_group.setLayout(status_row)
        bottom_layout.addWidget(status_group)

        btn_layout = QHBoxLayout()
        action_btn_w = 100
        self._btn_start = QPushButton(BTN_START)
        self._btn_start.setFixedWidth(action_btn_w)
        self._btn_save = QPushButton(BTN_SAVE)
        self._btn_save.setFixedWidth(action_btn_w)
        self._btn_stop = QPushButton(BTN_STOP)
        self._btn_stop.setFixedWidth(action_btn_w)
        self._btn_stop.setObjectName("stopBtn")
        self._btn_abandon = QPushButton(BTN_ABANDON)
        self._btn_abandon.setFixedWidth(action_btn_w)
        self._btn_abandon.setObjectName("stopBtn")
        self._btn_abandon.setVisible(False)
        self._btn_save.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_save.clicked.connect(self._on_save)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_abandon.clicked.connect(self._on_abandon)
        btn_layout.addWidget(self._btn_start)
        btn_layout.addWidget(self._btn_save)
        btn_layout.addWidget(self._btn_stop)
        btn_layout.addWidget(self._btn_abandon)
        btn_layout.addStretch()
        bottom_layout.addLayout(btn_layout)

        root.addWidget(bottom_widget)

        self._history_container = QWidget()
        self._history_container_layout = QVBoxLayout(self._history_container)
        self._history_container_layout.setContentsMargins(0, 0, 0, 0)

        self._analysis_container = QWidget()
        self._analysis_container_layout = QVBoxLayout(self._analysis_container)
        self._analysis_container_layout.setContentsMargins(0, 0, 0, 0)

        self._history_panel = None
        self._history_service = None
        self._ensure_history_panel()

    def history_widget(self) -> QWidget | None:
        return self._history_container

    def history_widgets(self) -> list[tuple[str, QWidget]]:
        """返回抓取历史和分析历史两个 Tab。"""
        return [
            (TAB_HISTORY_CAPTURE, self._history_container),
            (TAB_HISTORY_ANALYSIS, self._analysis_container),
        ]

    def _ensure_history_panel(self) -> None:
        """确保历史面板已初始化。"""
        if self._history_panel is not None:
            return

        from .analysis_chat import AnalysisChatWidget
        from .history_panel import HistoryPanel
        from .history_service import HistoryService
        from .history_storage import HistoryStorage

        self._history_panel = HistoryPanel()
        self._history_panel.close_requested.connect(self._on_history_close)
        self._history_panel.refresh_requested.connect(self._refresh_history)
        self._history_panel.cleanup_requested.connect(self._cleanup_history)
        self._history_panel.open_directory_requested.connect(self._open_history_directory)
        self._history_panel.analyze_trace_requested.connect(self._analyze_history_trace)
        self._history_panel.delete_session_requested.connect(self._delete_history_session)
        self._history_panel.delete_trace_requested.connect(self._delete_history_trace)
        self._history_panel.send_to_agent_requested.connect(self._on_send_to_agent)
        self._history_panel.file_dropped.connect(self._on_trace_file_dropped)
        self._history_panel._analysis_history_tree.open_report_requested.connect(
            self._open_analysis_report
        )
        self._history_panel._analysis_history_tree.delete_analysis_requested.connect(
            self._delete_analysis_task
        )

        # AI 对话组件
        self._analysis_chat = AnalysisChatWidget()
        self._analysis_chat.send_message.connect(self._on_analysis_chat_send)
        self._history_panel.set_chat_widget(self._analysis_chat)

        # trace 选中时自动更新对话区域
        self._history_panel._session_tree.itemSelectionChanged.connect(
            self._on_trace_selection_changed
        )

        from toolkit.core.app_paths import get_db_path, get_exe_dir, is_frozen

        # 初始化历史服务
        output_dir = self._get_output_dir()
        db_path = get_db_path("perfetto_capture", "history")
        storage = HistoryStorage(db_path)
        self._history_service = HistoryService(storage, output_dir, self._cfg.history)

        # 检测 analysis 模块是否可用
        analysis_available = self._is_analysis_module_available()
        self._history_panel.set_analysis_available(bool(analysis_available))

        # 抓取历史：只保留 session tree
        session_tree = self._history_panel._session_tree
        session_tree.setParent(None)
        self._history_container_layout.addWidget(session_tree)

        # 分析历史：只保留 analysis history tree
        analysis_tree = self._history_panel._analysis_history_tree
        analysis_tree.setParent(None)
        self._analysis_container_layout.addWidget(analysis_tree)

        self._refresh_history()

    def _get_output_dir(self) -> Path:
        from toolkit.core.app_paths import get_exe_dir, is_frozen

        if is_frozen():
            base = get_exe_dir() / "output"
        else:
            base = get_exe_dir() / "modules" / "perfetto_capture" / "data" / self._cfg.output_dir
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _is_analysis_module_available(self) -> bool:
        """检测 perfetto_analysis 模块是否可用。"""
        try:
            import importlib
            return importlib.util.find_spec("modules.perfetto_analysis") is not None
        except Exception:
            return False

    def _on_history_close(self) -> None:
        """历史面板关闭按钮 — 保留兼容，当前无操作。"""

    def _on_send_to_agent(self, payload: dict) -> None:
        """将历史文件上下文发送给 Agent Chat。"""
        if not self.context:
            return
        bus = self.context.get("event_bus")
        if not bus:
            return
        try:
            show_right = self.context.get("show_right_panel")
            if callable(show_right):
                show_right()
            bus.emit(HISTORY_SEND_TO_AGENT_EVENT, **payload)
            self._log(
                LOG_SENT_TO_AGENT_FMT.format(payload.get('file_name', '')),
                "success",
            )
        except Exception as exc:
            self._log(LOG_SEND_AGENT_FAIL_FMT.format(exc), "error")

    def _refresh_history(self) -> None:
        """刷新历史记录和分析历史。"""
        if not self._history_service:
            logger.warning("_refresh_history: " + LOG_SVC_NOT_INIT_HISTORY_2)
            return

        sessions = self._history_service.scan_sessions()
        self._history_panel.refresh(sessions)

        stats = self._history_service.get_stats()
        self._history_panel.update_stats(stats)

        try:
            storage = self._history_service.storage
            tasks = storage.get_all_analysis_tasks(limit=50)
            self._history_panel.refresh_analysis_history(tasks)
        except Exception:
            pass

    def _cleanup_history(self) -> None:
        """清理过期历史。"""
        if not self._history_service:
            return

        deleted = self._history_service.cleanup_expired()
        if deleted > 0:
            self._log(LOG_CLEANUP_FMT.format(deleted), "success")
            self._refresh_history()
        else:
            self._log(LOG_NO_EXPIRED_SESSIONS, "info")

    def _open_history_directory(self, path: Path) -> None:
        """打开历史目录。"""
        if path.is_file():
            # 打开文件所在目录并选中文件
            import subprocess
            import sys
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", str(path)], check=False)
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
        elif path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            self._log(LOG_PATH_NOT_FOUND_FMT.format(path), "error")

    def _on_trace_file_dropped(self, file_path: Path) -> None:
        """处理拖入的 trace 文件——移动到 user_traces 并刷新。"""
        if not self._history_service:
            self._log(LOG_SVC_NOT_INIT_HISTORY, "error")
            return

        try:
            output_dir = self._get_output_dir()
            user_dir = output_dir / "user_traces"
            user_dir.mkdir(parents=True, exist_ok=True)

            import shutil

            dest = user_dir / file_path.name
            if dest.exists():
                self._log(LOG_FILE_EXISTS_FMT.format(dest.name), "warning")
                return

            shutil.copy2(str(file_path), str(dest))
            self._log(LOG_IMPORTED_FMT.format(dest.name), "success")
            self._refresh_history()
        except Exception as e:
            self._log(LOG_IMPORT_FAIL_FMT.format(e), "error")

    def _on_trace_selection_changed(self) -> None:
        """trace 选中变化时更新 AI 对话区域。"""
        if not hasattr(self, "_analysis_chat"):
            return
        selected = self._history_panel._get_selected_items_data()
        self._analysis_chat.set_selected_traces(selected)

    def _on_analysis_chat_send(self, message: str, traces: list) -> None:
        """AI 对话发送消息，启动 AnalysisWorker。"""
        if message == "__cancel__":
            if hasattr(self, "_analysis_worker") and self._analysis_worker:
                self._analysis_worker.request_abort()
                self._analysis_chat.set_analyzing(False)
            self._log(CANCEL_ANALYSIS_REQUEST, "info")
            return

        trace_paths = [t.get("path") for t in traces if t.get("type") == "trace"]
        if not trace_paths:
            self._analysis_chat.append_message("system", CHAT_SELECT_TRACE_FIRST)
            return

        orchestrator = self.context.get("pa_orchestrator") if self.context else None
        if not orchestrator:
            self._analysis_chat.append_message("system", CHAT_ENGINE_NOT_READY)
            return

        from .analysis_chat import AnalysisWorker

        process_name = ""
        for t in traces:
            if t.get("target_package"):
                process_name = t["target_package"]
                break

        self._analysis_worker = AnalysisWorker(
            orchestrator=orchestrator,
            trace_path=trace_paths[0],
            user_intent=message,
            process_name=process_name,
        )
        self._analysis_worker.message_received.connect(self._on_analysis_message)
        self._analysis_worker.status_changed.connect(self._on_analysis_status)
        self._analysis_worker.finished_with_report.connect(self._on_analysis_finished)
        self._analysis_worker.analysis_error.connect(self._on_analysis_error)
        self._analysis_worker.finished.connect(lambda: self._analysis_chat.set_analyzing(False))

        self._analysis_chat.set_analyzing(True)
        self._analysis_worker.start()

    def _on_analysis_message(self, role: str, content: str) -> None:
        self._analysis_chat.append_message(role, content)

    def _on_analysis_status(self, task_id: str, status: str, detail: str) -> None:
        self._log(LOG_ANALYSIS_STATUS_FMT.format(status, detail), "info")

    def _on_analysis_finished(self, html_path: str) -> None:
        if html_path:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl.fromLocalFile(html_path))
            self._analysis_chat.append_message("system", CHAT_REPORT_OPENED_FMT.format(Path(html_path).name))

            self._save_analysis_record(html_path, "COMPLETED")
        else:
            self._analysis_chat.append_message("system", CHAT_ANALYSIS_COMPLETE)
        self._refresh_history()

    def _save_analysis_record(self, html_path: str, status: str) -> None:
        """保存分析记录到数据库。"""
        if not self._history_service:
            return
        try:
            import uuid

            storage = self._history_service.storage
            task_id = str(uuid.uuid4())

            trace_path = ""
            process_name = ""
            user_intent = ""
            if hasattr(self, "_analysis_worker") and self._analysis_worker:
                trace_path = str(self._analysis_worker._trace_path)
                process_name = str(self._analysis_worker._process_name or "")
                user_intent = str(self._analysis_worker._user_intent or "")

            storage.create_analysis_task(
                task_id=task_id,
                trace_path=trace_path,
                process_name=process_name,
                user_intent=user_intent,
            )

            result_dir = str(Path(html_path).parent) if html_path else ""
            storage.update_task_status(
                task_id=task_id,
                status=status,
                result_dir=result_dir,
            )

            if trace_path:
                storage.update_trace_analysis_status(trace_path, status, task_id)
        except Exception as e:
            logger.warning(LOG_SAVE_RECORD_FAIL_FMT.format(e))

    def _on_analysis_error(self, error: str) -> None:
        self._analysis_chat.append_message("system", CHAT_ANALYSIS_FAILED_FMT.format(error))

    def _open_analysis_report(self, html_path: str) -> None:
        """打开分析报告 HTML。"""
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        if Path(html_path).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(html_path))
        else:
            self._log(LOG_FILE_NOT_EXISTS_FMT.format(html_path), "error")

    def _analyze_history_trace(self, trace_path: Path) -> None:
        """分析历史 trace。"""
        if not trace_path.exists():
            self._log(LOG_FILE_NOT_FOUND_FMT.format(trace_path), "error")
            self._refresh_history()
            return

        # 通过 EventBus 发布分析请求
        try:
            from toolkit.core.event_bus import get_event_bus
            bus = get_event_bus()
            bus.emit("perfetto_capture.open_trace_for_analysis", {"trace_path": str(trace_path)})
            self._log(LOG_REQUEST_ANALYSIS_FMT.format(trace_path.name), "info")
            self._on_history_close()
        except Exception as e:
            self._log(LOG_SEND_ANALYSIS_FAIL_FMT.format(e), "error")

    def _delete_history_session(self, session_id: str) -> None:
        """删除历史会话（确认已在 history_panel 中完成）。"""
        if not self._history_service:
            return
        if self._history_service.delete_session(session_id):
            self._log(LOG_SESSION_DELETED_FMT.format(session_id), "success")
        else:
            self._log(LOG_SESSION_DELETE_FAIL_FMT.format(session_id), "error")
        self._refresh_history()

    def _delete_history_trace(self, trace_path: Path) -> None:
        """删除历史 trace（确认已在 history_panel 中完成）。"""
        if not self._history_service:
            return
        if self._history_service.delete_trace(trace_path):
            self._log(LOG_TRACE_DELETED_FMT.format(trace_path.name), "success")
        else:
            self._log(LOG_TRACE_DELETE_FAIL_FMT.format(trace_path.name), "error")
        self._refresh_history()

    def _delete_analysis_task(self, task_id: str) -> None:
        """删除分析任务记录。"""
        if not self._history_service:
            return
        try:
            storage = self._history_service.storage
            if storage.delete_analysis_task(task_id):
                self._log(LOG_ANALYSIS_RECORD_DELETED, "success")
            else:
                self._log(LOG_ANALYSIS_RECORD_DELETE_FAIL, "error")
            self._refresh_history()
        except Exception as e:
            self._log(LOG_ANALYSIS_RECORD_DELETE_FAIL_FMT.format(e), "error")

    def _log(self, msg: str, level: str = "info") -> None:
        """兼容旧接口的位置参数 level 调用。"""
        super()._log(msg, level=level)

    def on_activated(self) -> None:
        self._ensure_history_panel()
        if self.context:
            self._service = self.context.get("pe_service")
            self._adb = self.context.get("pe_adb")
            if self._service:
                cfg = self._service.config
                self._spin_duration.setValue(cfg.duration_sec)
                for cat, cb in self._cat_checks.items():
                    cb.setChecked(cat in cfg.atrace_categories)
                self._chk_manual_buffer.setChecked(cfg.buffer_manual_override)
                if cfg.buffer_manual_override and cfg.buffer_size_kb is not None:
                    self._spin_buffer.setValue(cfg.buffer_size_kb)
                else:
                    self._update_auto_buffer()
                if cfg.advanced.ftrace_events:
                    self._chk_ftrace.setChecked(True)
                    for evt, cb in self._ftrace_checks.items():
                        cb.setChecked(evt in cfg.advanced.ftrace_events)
            if self._serial and (
                not self._device_info or self._device_info.model == "unknown"
            ):
                self._try_fetch_device_info()

    def on_devices_changed(self, devices: list[str]) -> None:
        super().on_devices_changed(devices)
        if devices:
            self._serial = devices[0]
            self._try_fetch_device_info()
            if self._waiting_reconnect:
                self._on_device_reconnected()
            elif not self._capturing:
                self._btn_start.setEnabled(True)
                self._lbl_status.setText(LABEL_STATUS_READY_EMOJI)
        else:
            old_serial = self._serial
            self._serial = None
            self._device_info = None
            self._lbl_device.setText(LABEL_DEVICE_DEFAULT)

            if self._capturing and not self._waiting_reconnect:
                self._on_device_disconnected()
            elif not self._capturing:
                self._btn_start.setEnabled(False)
                self._lbl_status.setText(LABEL_STATUS_DEVICE_DISCONNECTED)

    def _try_fetch_device_info(self) -> None:
        """尝试获取设备信息；service 未就绪或 ADB 失败时使用 fallback。"""
        from .models import DeviceInfo

        if not self._serial:
            return
        if self._service:
            try:
                info = self._service.get_device_info(self._serial)
                self._lbl_device.setText(LABEL_DEVICE + ": " + f"{info.model} ({self._serial})")
                self._device_info = info
                return
            except Exception:
                self._log(LOG_CANNOT_READ_DEVICE, "warning")

        self._device_info = DeviceInfo(
            serial=self._serial, model="unknown", soc="unknown",
        )
        self._lbl_device.setText(f"{LABEL_DEVICE}: {self._serial}")

    def _on_import_config(self) -> None:
        """弹出文件选择对话框，默认指向当前模块配置目录，导入用户选择的 JSON 配置。"""
        if not self._service:
            self._log(LOG_SVC_NOT_INIT, "error")
            return
        default_dir = str(self._service._data_dir)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            DLG_TITLE_SELECT_CONFIG,
            default_dir,
            FILE_FILTER_JSON,
        )
        if not file_path:
            return
        self._load_config_from_file(Path(file_path))

    def _load_config_from_file(self, file_path: Path | None = None) -> None:
        """从指定文件（或默认路径）加载配置并刷新 GUI。"""
        if not self._service:
            return
        try:
            cfg = self._service.reload_config(file_path)
            self._spin_duration.setValue(cfg.duration_sec)
            for cat, cb in self._cat_checks.items():
                cb.setChecked(cat in cfg.atrace_categories)
            self._chk_manual_buffer.setChecked(cfg.buffer_manual_override)
            if cfg.buffer_manual_override and cfg.buffer_size_kb is not None:
                self._spin_buffer.setValue(cfg.buffer_size_kb)
            else:
                self._update_auto_buffer()

            self._rebuild_ftrace_panel(cfg)
            if cfg.advanced.ftrace_events:
                self._chk_ftrace.setChecked(True)
                for evt, cb in self._ftrace_checks.items():
                    cb.setChecked(evt in cfg.advanced.ftrace_events)
            src = file_path.name if file_path else "默认配置"
            self._log(LOG_CONFIG_IMPORTED_FMT.format(src), "success")
        except Exception as e:
            self._log(LOG_CONFIG_LOAD_FAIL_FMT.format(e), "error")

    def _rebuild_ftrace_panel(self, cfg: Any) -> None:
        """根据配置重建 Ftrace Events 选项列表。"""
        for cb in list(self._ftrace_checks.values()):
            cb.setParent(None)
            cb.deleteLater()
        self._ftrace_checks.clear()
        self._ftrace_inner._children.clear()

        for evt in cfg.advanced.available_ftrace_events:
            short = evt.split("/")[-1] if "/" in evt else evt
            cb = QCheckBox(short)
            cb.setToolTip(evt)
            cb.toggled.connect(self._update_auto_buffer)
            self._ftrace_checks[evt] = cb
            self._ftrace_inner.add_widget(cb)
            cb.show()
        self._ftrace_inner._relayout()

    def _on_manual_buffer_toggled(self, checked: bool) -> None:
        self._spin_buffer.setEnabled(checked)
        self._spin_buffer.setReadOnly(not checked)
        if not checked:
            self._update_auto_buffer()

    def _update_auto_buffer(self) -> None:
        """根据 duration、atrace categories 和 ftrace events 自动计算 buffer。"""
        if self._chk_manual_buffer.isChecked():
            return
        if not self._service:
            return
        cat_count = sum(1 for cb in self._cat_checks.values() if cb.isChecked())
        ftrace_count = 0
        if self._chk_ftrace.isChecked():
            ftrace_count = sum(1 for cb in self._ftrace_checks.values() if cb.isChecked())
        buf = self._service.calculate_buffer_size(
            duration_sec=self._spin_duration.value(),
            category_count=cat_count,
            ftrace_count=ftrace_count,
        )
        self._spin_buffer.blockSignals(True)
        self._spin_buffer.setValue(buf)
        self._spin_buffer.blockSignals(False)

    def _apply_config_from_ui(self) -> None:
        if not self._service:
            return
        cats = [cat for cat, cb in self._cat_checks.items() if cb.isChecked()]
        manual = self._chk_manual_buffer.isChecked()

        ftrace_events: list[str] = []
        if self._chk_ftrace.isChecked():
            ftrace_events = [evt for evt, cb in self._ftrace_checks.items() if cb.isChecked()]

        from .models import AdvancedConfig
        adv = self._service.config.advanced.model_copy(update={
            "ftrace_events": ftrace_events,
        })
        cfg = self._service.config.model_copy(update={
            "duration_sec": self._spin_duration.value(),
            "buffer_size_kb": self._spin_buffer.value() if manual else None,
            "buffer_manual_override": manual,
            "atrace_categories": cats,
            "advanced": adv,
        })
        self._service.config = cfg
        try:
            self._service.save_current_config()
        except Exception:
            pass

    def _on_start(self) -> None:
        if not self.require_device() or not self._service:
            return
        if self._jank_enabled:
            config = self._jank_config_panel.get_config()
            if not config.target_package:
                warning_dialog(self, "提示", "已启用 Jank 检测，请先选择监控应用")
                return
        self._apply_config_from_ui()
        self._log("正在启动 Perfetto 抓取...")
        cfg = self._service.config
        cats = ", ".join(cfg.atrace_categories)
        self._log(f"  Atrace: {cats}")
        if cfg.advanced.ftrace_events:
            evts = ", ".join(cfg.advanced.ftrace_events)
            self._log(f"  Ftrace: {evts}")
        effective_buf = self._service.get_effective_buffer_size()
        buf_label = LOG_BUFF_LABEL_MANUAL if cfg.buffer_manual_override else LOG_BUFF_LABEL_AUTO
        self._log(f"  Buffer: {effective_buf} KB ({buf_label}) | Duration: {cfg.duration_sec}s")
        self._btn_start.setEnabled(False)
        self._saved_count = 0
        self._lbl_saved.setText(LABEL_SAVED_DEFAULT_FMT)

        worker = _CaptureWorker("start", self._service, self._serial)
        worker.progress.connect(lambda msg: self._log(msg))
        worker.started_ok.connect(self._on_started)
        worker.error.connect(self._on_error)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_started(self) -> None:
        mode_label = ""
        if self._service and self._service.session and self._service.session.running:
            from .models import CaptureMode
            mode = self._service.session.running.mode
            if mode == CaptureMode.SNAPSHOT:
                mode_label = LOG_CAPTURE_MODE_SNAPSHOT
            else:
                mode_label = LOG_CAPTURE_MODE_AUTO_BUFFER
        self._log(LOG_CAPTURE_STARTED_FMT.format(mode_label), "success")
        self._set_capturing(True)
        self._capture_start_time = datetime.datetime.now()
        self._timer.start(1000)
        self._lbl_status.setText("⏺ 抓取中")
        if self._service and self._serial:
            try:
                self._device_dir = self._service.ensure_device_trace_dir(self._serial)
            except Exception as e:
                self._log(LOG_GET_DEVICE_DIR_FAIL_FMT.format(e), "error")

        if self._jank_enabled:
            self._start_jank_monitor()

    def _on_save(self) -> None:
        if not self._service:
            self._log(LOG_SVC_NOT_INIT, "error")
            return
        if not self._serial:
            self._log(LOG_NO_DEVICE, "error")
            return
        if not self._device_info:
            self._log(LOG_NO_DEVICE_INFO, "error")
            return
        self._log(LOG_SAVE_TRACE_SEGMENT)
        self._btn_save.setEnabled(False)

        worker = _CaptureWorker(
            "save", self._service, self._serial,
            device_info=self._device_info,
            device_dir=self._device_dir or self._service.config.device_trace_dir,
        )
        worker.progress.connect(lambda msg: self._log(msg))
        worker.save_ok.connect(self._on_saved)
        worker.error.connect(self._on_error)
        worker.finished.connect(lambda: self._btn_save.setEnabled(self._capturing))
        self._worker = worker
        worker.start()

    def _on_saved(self, count: int) -> None:
        self._saved_count = count
        self._lbl_saved.setText(f"{LABEL_SAVED_COUNT}: {count} {LABEL_SEGMENTS}")
        self._log(LOG_SAVED_FMT.format(count), "success")

    def _on_stop(self) -> None:
        self._set_capturing(False)
        self._timer.stop()

        if self._jank_worker:
            self._stop_jank_monitor()

        if not self._service or not self._serial:
            return
        self._log(LOG_STOP_AND_EXPORT)

        worker = _CaptureWorker(
            "stop",
            self._service,
            self._serial,
            device_info=self._device_info,
            device_dir=self._device_dir or self._service.config.device_trace_dir,
            auto_save=True,
        )
        worker.progress.connect(lambda msg: self._log(msg))
        worker.export_ok.connect(self._on_exported)
        worker.error.connect(self._on_error)
        self._worker = worker
        worker.start()

    def _on_exported(self, paths: list[str]) -> None:
        if paths:
            self._log(LOG_EXPORTED_FMT.format(len(paths)), "success")
            for p in paths:
                self._log(f"  {p}")
            export_dir = Path(paths[0]).parent
            if export_dir.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(export_dir)))
                self._log(LOG_OPEN_EXPORT_DIR_FMT.format(export_dir))
        else:
            self._log(LOG_NO_VALID_TRACE, "warning")
        self._lbl_status.setText(LABEL_STATUS_READY_EMOJI)
        self._lbl_timer.setText(LABEL_TIMER_DEFAULT_FMT)
        self._saved_count = 0
        self._lbl_saved.setText(LABEL_SAVED_DEFAULT_FMT)

    def _on_error(self, msg: str) -> None:
        if self._capturing and (LOG_DEVICE_UNAVAILABLE in msg or "device" in msg.lower()):
            self._on_device_disconnected()
            self._log(f"✗ {msg}", "error")
            return
        self._log(f"✗ {msg}", "error")
        self._set_capturing(False)
        self._timer.stop()
        self._lbl_status.setText(LABEL_STATUS_READY_EMOJI)

    def _on_device_disconnected(self) -> None:
        """抓取中设备断开。保持会话但暂停操作，等待自动重连。"""
        if self._waiting_reconnect:
            return
        self._waiting_reconnect = True
        self._lbl_status.setText("🟡 等待重连")
        self._btn_save.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._btn_start.setEnabled(False)
        self._btn_abandon.setVisible(True)
        self._log("⚠ 设备断开！已保存的 trace 保留在设备上，等待自动重连...", "warning")

    def _on_device_reconnected(self) -> None:
        """设备重连成功，在现有会话中重启 perfetto。"""
        self._waiting_reconnect = False
        self._btn_abandon.setVisible(False)
        self._log("✓ 设备已重连，正在恢复抓取...", "success")

        if not self._service or not self._serial:
            self._log("✗ 服务或设备不可用，无法恢复", "error")
            self._set_capturing(False)
            return

        worker = _CaptureWorker("reconnect", self._service, self._serial)
        worker.progress.connect(lambda msg: self._log(msg))
        worker.started_ok.connect(self._on_reconnect_ok)
        worker.error.connect(self._on_reconnect_fail)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _on_reconnect_ok(self) -> None:
        mode_label = ""
        if self._service and self._service.session and self._service.session.running:
            from .models import CaptureMode
            mode = self._service.session.running.mode
            mode_label = " [快照]" if mode == CaptureMode.SNAPSHOT else " [自动缓冲]"
        self._log(f"✓ 抓取已恢复{mode_label}", "success")
        self._set_capturing(True)
        self._lbl_status.setText("⏺ 抓取中")
        if self._service and self._serial:
            try:
                self._device_dir = self._service.ensure_device_trace_dir(self._serial)
            except Exception:
                pass

    def _on_reconnect_fail(self, msg: str) -> None:
        self._log(f"✗ 恢复抓取失败: {msg}", "error")
        self._log("请点击「放弃会话」后重新开始", "warning")
        self._btn_abandon.setVisible(True)

    def _on_abandon(self) -> None:
        """放弃当前会话，不导出任何 trace。"""
        if self._service:
            self._service.session_abandon()
        self._waiting_reconnect = False
        self._set_capturing(False)
        self._timer.stop()
        self._btn_abandon.setVisible(False)
        self._lbl_timer.setText(LABEL_TIMER_DEFAULT_FMT)
        self._saved_count = 0
        self._lbl_saved.setText(LABEL_SAVED_DEFAULT_FMT)
        if self._serial:
            self._lbl_status.setText("🟢 就绪")
            self._btn_start.setEnabled(True)
        else:
            self._lbl_status.setText("🔴 设备断开")
            self._btn_start.setEnabled(False)
        self._log("会话已放弃", "warning")

    def _set_capturing(self, capturing: bool) -> None:
        self._capturing = capturing
        self._btn_start.setEnabled(not capturing and self._device_connected)
        self._btn_start.setText("⏸ 抓取中" if capturing else "▶ 开始")
        self._btn_save.setEnabled(capturing)
        self._btn_stop.setEnabled(capturing)
        self._spin_duration.setEnabled(not capturing)
        manual = self._chk_manual_buffer.isChecked()
        self._spin_buffer.setEnabled(not capturing and manual)
        for cb in self._cat_checks.values():
            cb.setEnabled(not capturing)
        self._chk_jank.setEnabled(not capturing)
        self._chk_ftrace.setEnabled(not capturing)

    def _update_timer(self) -> None:
        if self._capture_start_time:
            elapsed = datetime.datetime.now() - self._capture_start_time
            mins, secs = divmod(int(elapsed.total_seconds()), 60)
            self._lbl_timer.setText(f"时长: {mins:02d}:{secs:02d}")

    # ── Jank 监控相关方法 ──────────────────────────────────────────

    def _on_jank_toggled(self, checked: bool) -> None:
        """Jank 检测复选框状态变化。"""
        self._jank_group.setVisible(checked)
        self._jank_enabled = checked
        if checked and self._adb and self._serial:
            self._refresh_jank_apps()

    def _refresh_jank_apps(self) -> None:
        """刷新应用列表。"""
        if not self._adb or not self._serial:
            self._log("⚠ 请先连接设备", "warning")
            return

        try:
            from .jank_service import JankMonitorService
            svc = JankMonitorService(self._adb, self._serial)
            apps = svc.get_running_apps()
            self._jank_config_panel.app_selector.set_apps(apps)

            threshold = svc.get_default_threshold()
            self._jank_config_panel.set_default_threshold(threshold)
        except Exception as e:
            self._log(f"⚠ 获取应用列表失败: {e}", "warning")

    def _on_jank_config_changed(self, config) -> None:
        """Jank 配置变化。"""
        pass

    def _on_jank_pause_clicked(self) -> None:
        """Jank 暂停/恢复按钮点击。"""
        if self._jank_worker:
            if self._jank_config_panel._paused:
                self._jank_worker.pause_capture_detection()
                self._log("⏸ 已暂停 Jank 判定", "info")
            else:
                self._jank_worker.resume_capture_detection()
                self._log("▶ 已恢复 Jank 判定", "info")

    def _on_jank_export_clicked(self) -> None:
        """导出帧率数据。"""
        if not self._jank_worker:
            self._log("⚠ 监控未运行，无数据可导出", "warning")
            return

        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出帧率数据",
            f"fps_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel 文件 (*.xlsx)",
        )
        if not file_path:
            return

        try:
            from .frame_exporter import export_to_xlsx
            regions = self._jank_worker.capture_regions
            config = self._jank_config_panel.get_config()
            export_to_xlsx(
                data=self._fps_chart._data,
                regions=regions,
                output_path=Path(file_path),
            )
            self._log(f"✓ 已导出: {file_path}", "success")
        except ImportError:
            self._log("⚠ 导出功能尚未实现", "warning")
        except Exception as e:
            self._log(f"✗ 导出失败: {e}", "error")

    def _start_jank_monitor(self) -> None:
        """启动 Jank 监控。不阻塞 Perfetto 抓取。"""
        if not self._adb or not self._jank_enabled:
            return

        config = self._jank_config_panel.get_config()
        if not config.target_package:
            self._log("⚠ Jank 监控未启动：请先选择监控应用", "warning")
            return

        self._fps_chart.clear()

        try:
            from .jank_worker import JankMonitorWorker
            self._jank_worker = JankMonitorWorker(self._adb, self._serial, self)
            self._jank_worker.configure(config, config.target_package)

            self._jank_worker.frame_stats_ready.connect(self._on_jank_frame_stats)
            self._jank_worker.jank_triggered.connect(self._on_jank_triggered)
            self._jank_worker.app_state_changed.connect(self._on_jank_app_state)
            self._jank_worker.state_changed.connect(self._on_jank_state_changed)
            self._jank_worker.monitor_stats_updated.connect(self._on_jank_stats_updated)
            self._jank_worker.capture_requested.connect(self._on_jank_capture_requested)
            self._jank_worker.capture_region_changed.connect(self._on_capture_region_changed)

            self._jank_worker.start_monitor()
            self._jank_config_panel.set_enabled(False)
            self._log(f"▶ 开始监控: {config.target_package}", "info")

            duration_ms = config.max_duration_hours * 3600 * 1000
            self._jank_duration_timer = QTimer(self)
            self._jank_duration_timer.setSingleShot(True)
            self._jank_duration_timer.timeout.connect(self._on_duration_exceeded)
            self._jank_duration_timer.start(duration_ms)
            self._log(
                f"⏱ 监控时长上限: {config.max_duration_hours} 小时", "info"
            )
        except Exception as e:
            self._log(f"✗ Jank 监控启动失败: {e}", "error")

    def _stop_jank_monitor(self) -> None:
        """停止 Jank 监控。"""
        if self._jank_duration_timer:
            self._jank_duration_timer.stop()
            self._jank_duration_timer = None
        if self._jank_worker:
            self._jank_worker.stop_monitor()
            self._jank_worker = None
            self._jank_config_panel.set_enabled(True)
            self._log("■ Jank 监控已停止", "info")

    def _on_duration_exceeded(self) -> None:
        """监控时长到达上限，自动停止。"""
        self._log("⏱ 已达到最大监控时长，自动停止", "warning")
        self._on_stop()

    def _on_jank_frame_stats(self, stats) -> None:
        """帧数据更新。"""
        logger.debug("帧数据: fps=%.1f, jank=%d, big_jank=%d, frames=%d",
                      stats.fps, stats.jank_count, stats.big_jank_count, len(stats.frames))
        self._fps_chart.update_stats(stats)

    def _on_jank_triggered(self, event) -> None:
        """Jank 触发事件。"""
        self._log(
            f"⚠ Jank 触发: {event.jank_count} 帧, "
            f"平均帧耗时 {event.avg_frame_time_ms:.1f}ms",
            "warning",
        )

    def _on_jank_app_state(self, is_foreground: bool) -> None:
        """应用前后台状态变化。"""
        if is_foreground:
            self._log("📱 应用回到前台", "info")
        else:
            self._log("📱 应用切到后台", "info")

    def _on_jank_state_changed(self, state) -> None:
        """监控状态变化。"""
        from .models import MonitorState
        state_labels = {
            MonitorState.IDLE: "就绪",
            MonitorState.MONITORING: "监控中",
            MonitorState.TRIGGERED: "已触发",
            MonitorState.STABILIZING: "稳定中",
            MonitorState.SAVING: "保存中",
            MonitorState.PAUSED: "已暂停",
            MonitorState.COMPLETED: "已完成",
            MonitorState.ERROR: "错误",
        }
        label = state_labels.get(state, str(state))
        self._log(f"📊 Jank 状态: {label}", "info")

    def _on_jank_stats_updated(self, stats) -> None:
        """监控统计更新。"""
        config = self._jank_config_panel.get_config()
        self._jank_config_panel.update_capture_count(
            stats.capture_count, config.max_captures
        )

    def _on_jank_capture_requested(self) -> None:
        """Jank 请求保存 trace。"""
        self._log("📦 Jank 检测触发，自动保存 trace...", "info")
        self._on_save()

    def _on_capture_region_changed(self, regions: list) -> None:
        """抓取选区变化。"""
        self._fps_chart.set_regions(regions)
