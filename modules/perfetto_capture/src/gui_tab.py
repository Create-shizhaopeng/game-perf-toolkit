"""Perfetto 抓取模块 — GUI 页面（方案 A：左右分栏）"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSize, QThread, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QTextCharFormat
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


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
        "warning": "#fab387",
        "btn_primary_bg": "#a6e3a1",
        "btn_primary_fg": "#1e1e2e",
        "btn_save_bg": "#f9e2af",
        "btn_save_fg": "#1e1e2e",
        "btn_stop_bg": "#f38ba8",
        "btn_stop_fg": "#1e1e2e",
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
        "warning": "#df8e1d",
        "btn_primary_bg": "#40a02b",
        "btn_primary_fg": "#ffffff",
        "btn_save_bg": "#df8e1d",
        "btn_save_fg": "#ffffff",
        "btn_stop_bg": "#d20f39",
        "btn_stop_fg": "#ffffff",
        "btn_secondary_bg": "#ccd0da",
        "btn_secondary_fg": "#333333",
        "input_bg": "#dce0e8",
        "input_border": "#bcc0cc",
    },
}


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
                self.progress.emit("▶ 抓取已开始")
                self.started_ok.emit()

            elif self._action == "save":
                device_info = self._kwargs["device_info"]
                device_dir = self._kwargs["device_dir"]
                self._svc.session_save_trace(self._serial, device_dir, device_info)
                count = len(self._svc.session.saved_traces) if self._svc.session else 0
                self.progress.emit(f"💾 已保存第 {count} 段 trace")
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
                self.progress.emit(f"■ 会话结束，已导出 {len(exported)} 个文件")
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
                self.progress.emit("▶ 抓取已恢复")
                self.started_ok.emit()

        except Exception as e:
            self.error.emit(str(e))


class PerfettoCaptureTab(BaseTab):
    tab_title = "Perfetto 抓取"
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
        config_group = QGroupBox("⚙ 抓取配置")
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
        config_row.addWidget(QLabel("秒"))
        config_row.addSpacing(12)
        config_row.addWidget(QLabel("Buffer"))
        self._spin_buffer = QSpinBox()
        self._spin_buffer.setRange(91136, 512000)
        self._spin_buffer.setValue(91136)
        self._spin_buffer.setFixedSize(spin_width, ctrl_height)
        self._spin_buffer.setEnabled(False)
        self._spin_buffer.setReadOnly(True)
        config_row.addWidget(self._spin_buffer)
        config_row.addWidget(QLabel("KB"))
        config_row.addSpacing(12)
        self._btn_import_config = QPushButton("📂 导入配置")
        self._btn_import_config.setFixedSize(btn_width, ctrl_height)
        self._btn_import_config.setToolTip("选择 JSON 配置文件导入")
        self._btn_import_config.clicked.connect(self._on_import_config)
        config_row.addWidget(self._btn_import_config)
        config_row.addStretch()
        config_vbox.addLayout(config_row)

        self._spin_duration.valueChanged.connect(self._update_auto_buffer)

        chk_row = QHBoxLayout()
        self._chk_manual_buffer = QCheckBox("手动设置 Buffer")
        self._chk_manual_buffer.toggled.connect(self._on_manual_buffer_toggled)
        self._chk_ftrace = QCheckBox("启用 Ftrace 自定义")
        self._chk_jank = QCheckBox("启用 Jank 检测")
        self._chk_jank.toggled.connect(self._on_jank_toggled)
        chk_row.addWidget(self._chk_manual_buffer)
        chk_row.addWidget(self._chk_ftrace)
        chk_row.addWidget(self._chk_jank)
        chk_row.addStretch()
        config_vbox.addLayout(chk_row)

        config_group.setLayout(config_vbox)
        scroll_layout.addWidget(config_group)

        # ── Categories 面板（FlowWidget 自适应列数） ──
        cat_group = QGroupBox("📦 Atrace Categories")
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
        self._ftrace_group = QGroupBox("🔧 Ftrace Events")
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
        self._jank_group = QGroupBox("📊 Jank 监控")
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

        scroll_layout.addStretch()
        top_scroll.setWidget(scroll_widget)
        root.addWidget(top_scroll, 1)

        # ── 底部固定区：状态 + 按钮 + 日志 ──
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)

        status_group = QGroupBox("📊 会话状态")
        status_row = QHBoxLayout()
        status_row.setSpacing(16)
        self._lbl_status = QLabel("🟢 就绪")
        self._lbl_saved = QLabel("已保存: 0 段")
        self._lbl_timer = QLabel("时长: --:--")
        self._lbl_device = QLabel("设备: --")
        status_row.addWidget(self._lbl_status)
        status_row.addWidget(self._lbl_saved)
        status_row.addWidget(self._lbl_timer)
        status_row.addWidget(self._lbl_device, 1)
        status_group.setLayout(status_row)
        bottom_layout.addWidget(status_group)

        btn_layout = QHBoxLayout()
        action_btn_w = 100
        self._btn_start = QPushButton("▶ 开始")
        self._btn_start.setFixedWidth(action_btn_w)
        self._btn_save = QPushButton("💾 保存")
        self._btn_save.setFixedWidth(action_btn_w)
        self._btn_stop = QPushButton("⏹ 停止")
        self._btn_stop.setFixedWidth(action_btn_w)
        self._btn_stop.setObjectName("stopBtn")
        self._btn_abandon = QPushButton("❌ 放弃会话")
        self._btn_abandon.setFixedWidth(action_btn_w)
        self._btn_abandon.setObjectName("stopBtn")
        self._btn_abandon.setVisible(False)
        self._btn_save.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_save.clicked.connect(self._on_save)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_abandon.clicked.connect(self._on_abandon)
        self._btn_history = QPushButton("📂 历史")
        self._btn_history.setFixedWidth(action_btn_w)
        self._btn_history.clicked.connect(self._toggle_history_panel)
        btn_layout.addWidget(self._btn_start)
        btn_layout.addWidget(self._btn_save)
        btn_layout.addWidget(self._btn_stop)
        btn_layout.addWidget(self._btn_abandon)
        btn_layout.addWidget(self._btn_history)
        btn_layout.addStretch()
        bottom_layout.addLayout(btn_layout)

        log_label = QLabel("📋 操作日志")
        bottom_layout.addWidget(log_label)
        self._log_area = QTextEdit()
        self._log_area.setReadOnly(True)
        self._log_area.setFixedHeight(160)
        bottom_layout.addWidget(self._log_area)

        root.addWidget(bottom_widget)

        # 历史记录面板（延迟初始化）
        self._history_panel = None
        self._history_mask = None
        self._history_service = None

    def _ensure_history_panel(self) -> None:
        """确保历史面板已初始化。"""
        if self._history_panel is not None:
            return

        from .history_panel import HistoryPanel, OverlayMask
        from .history_service import HistoryService
        from .history_storage import HistoryStorage

        # 初始化遮罩
        self._history_mask = OverlayMask(self)
        self._history_mask.clicked.connect(self._close_history_panel)

        # 初始化面板
        self._history_panel = HistoryPanel(self)
        self._history_panel.close_requested.connect(self._close_history_panel)
        self._history_panel.refresh_requested.connect(self._refresh_history)
        self._history_panel.cleanup_requested.connect(self._cleanup_history)
        self._history_panel.open_directory_requested.connect(self._open_history_directory)
        self._history_panel.analyze_trace_requested.connect(self._analyze_history_trace)
        self._history_panel.delete_session_requested.connect(self._delete_history_session)
        self._history_panel.delete_trace_requested.connect(self._delete_history_trace)

        # 初始化历史服务
        output_dir = self._get_output_dir()
        db_path = output_dir / "history.db"
        storage = HistoryStorage(db_path)
        self._history_service = HistoryService(storage, output_dir, self._cfg.history)

        # 检测 analysis 模块是否可用
        analysis_available = self._is_analysis_module_available()
        self._history_panel.set_analysis_available(bool(analysis_available))

    def _get_output_dir(self) -> Path:
        """获取输出目录。"""
        import sys
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).parent / "output"
        else:
            base = Path(__file__).parent.parent / "data" / self._cfg.output_dir
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _is_analysis_module_available(self) -> bool:
        """检测 perfetto_analysis 模块是否可用。"""
        try:
            import importlib
            return importlib.util.find_spec("modules.perfetto_analysis") is not None
        except Exception:
            return False

    def _toggle_history_panel(self) -> None:
        """切换历史面板显示状态。"""
        try:
            self._ensure_history_panel()
        except Exception as e:
            self._log(f"✗ 历史面板初始化失败: {e}", "error")
            return

        if self._history_panel.isVisible():
            self._close_history_panel()
        else:
            self._open_history_panel()

    def _open_history_panel(self) -> None:
        """打开历史面板。"""
        self._ensure_history_panel()
        self._history_mask.show_mask()
        self._history_panel.show_animated()
        self._refresh_history()

    def _close_history_panel(self) -> None:
        """关闭历史面板。"""
        if self._history_panel:
            self._history_panel.hide_animated()
        if self._history_mask:
            self._history_mask.hide_mask()

    def _refresh_history(self) -> None:
        """刷新历史记录。"""
        if not self._history_service:
            return

        sessions = self._history_service.scan_sessions()
        self._history_panel.refresh(sessions)

        stats = self._history_service.get_stats()
        self._history_panel.update_stats(stats)

    def _cleanup_history(self) -> None:
        """清理过期历史。"""
        if not self._history_service:
            return

        deleted = self._history_service.cleanup_expired()
        if deleted > 0:
            self._log(f"已清理 {deleted} 个过期会话", "success")
            self._refresh_history()
        else:
            self._log("没有需要清理的过期会话", "info")

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
            self._log(f"路径不存在: {path}", "error")

    def _analyze_history_trace(self, trace_path: Path) -> None:
        """分析历史 trace。"""
        if not trace_path.exists():
            self._log(f"文件不存在: {trace_path}", "error")
            self._refresh_history()
            return

        # 通过 EventBus 发布分析请求
        try:
            from toolkit.core.event_bus import get_event_bus
            bus = get_event_bus()
            bus.emit("perfetto_capture.open_trace_for_analysis", {"trace_path": str(trace_path)})
            self._log(f"已请求分析: {trace_path.name}", "info")
            self._close_history_panel()
        except Exception as e:
            self._log(f"发送分析请求失败: {e}", "error")

    def _delete_history_session(self, session_id: str) -> None:
        """删除历史会话。"""
        if not self._history_service:
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除会话 {session_id} 及其所有 trace 文件吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self._history_service.delete_session(session_id):
                self._log(f"已删除会话: {session_id}", "success")
                self._refresh_history()
            else:
                self._log(f"删除会话失败: {session_id}", "error")

    def _delete_history_trace(self, trace_path: Path) -> None:
        """删除历史 trace。"""
        if not self._history_service:
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除 trace 文件吗？\n{trace_path.name}\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self._history_service.delete_trace(trace_path):
                self._log(f"已删除: {trace_path.name}", "success")
                self._refresh_history()
            else:
                self._log(f"删除失败: {trace_path.name}", "error")

    def keyPressEvent(self, event) -> None:
        """键盘事件处理。"""
        if event.key() == Qt.Key.Key_Escape:
            if self._history_panel and self._history_panel.isVisible():
                self._close_history_panel()
                return
        super().keyPressEvent(event)

    def _log(self, message: str, level: str = "info") -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        fmt = QTextCharFormat()
        colors = _THEME_COLORS.get("dark", _THEME_COLORS["dark"])
        if level == "success":
            fmt.setForeground(QColor(colors["success"]))
        elif level == "error":
            fmt.setForeground(QColor(colors["error"]))
        elif level == "warning":
            fmt.setForeground(QColor(colors["warning"]))
        else:
            fmt.setForeground(QColor(colors["fg"]))
        cursor = self._log_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(f"[{ts}] {message}\n", fmt)
        self._log_area.setTextCursor(cursor)
        self._log_area.ensureCursorVisible()

    def on_activated(self) -> None:
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
                self._lbl_status.setText("🟢 就绪")
        else:
            old_serial = self._serial
            self._serial = None
            self._device_info = None
            self._lbl_device.setText("设备: --")

            if self._capturing and not self._waiting_reconnect:
                self._on_device_disconnected()
            elif not self._capturing:
                self._btn_start.setEnabled(False)
                self._lbl_status.setText("🔴 设备断开")

    def _try_fetch_device_info(self) -> None:
        """尝试获取设备信息；service 未就绪或 ADB 失败时使用 fallback。"""
        from .models import DeviceInfo

        if not self._serial:
            return
        if self._service:
            try:
                info = self._service.get_device_info(self._serial)
                self._lbl_device.setText(f"设备: {info.model} ({self._serial})")
                self._device_info = info
                return
            except Exception:
                self._log("⚠ 无法读取设备详细信息，已使用默认值", "warning")

        self._device_info = DeviceInfo(
            serial=self._serial, model="unknown", soc="unknown",
        )
        self._lbl_device.setText(f"设备: {self._serial}")

    def _on_import_config(self) -> None:
        """弹出文件选择对话框，默认指向当前模块配置目录，导入用户选择的 JSON 配置。"""
        if not self._service:
            self._log("✗ 服务未初始化", "error")
            return
        default_dir = str(self._service._data_dir)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择配置文件",
            default_dir,
            "JSON 配置 (*.json);;所有文件 (*)",
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
            self._log(f"✓ 已导入配置: {src}", "success")
        except Exception as e:
            self._log(f"✗ 加载配置失败: {e}", "error")

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
        self._apply_config_from_ui()
        self._log("正在启动 Perfetto 抓取...")
        cfg = self._service.config
        cats = ", ".join(cfg.atrace_categories)
        self._log(f"  Atrace: {cats}")
        if cfg.advanced.ftrace_events:
            evts = ", ".join(cfg.advanced.ftrace_events)
            self._log(f"  Ftrace: {evts}")
        effective_buf = self._service.get_effective_buffer_size()
        buf_label = "手动" if cfg.buffer_manual_override else "自动"
        self._log(f"  Buffer: {effective_buf} KB ({buf_label}) | Duration: {cfg.duration_sec}s")
        self._btn_start.setEnabled(False)
        self._saved_count = 0
        self._lbl_saved.setText("已保存: 0 段")

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
                mode_label = " [快照模式]"
            else:
                mode_label = " [自动缓冲模式]"
        self._log(f"✓ Perfetto 后台抓取已启动{mode_label}", "success")
        self._set_capturing(True)
        self._capture_start_time = datetime.datetime.now()
        self._timer.start(1000)
        self._lbl_status.setText("⏺ 抓取中")
        if self._service and self._serial:
            try:
                self._device_dir = self._service.ensure_device_trace_dir(self._serial)
            except Exception as e:
                self._log(f"✗ 获取设备目录失败: {e}", "error")

        if self._jank_enabled:
            self._start_jank_monitor()

    def _on_save(self) -> None:
        if not self._service:
            self._log("✗ 服务未初始化，无法保存", "error")
            return
        if not self._serial:
            self._log("✗ 未检测到设备，无法保存", "error")
            return
        if not self._device_info:
            self._log("✗ 设备信息未获取，无法保存", "error")
            return
        self._log("保存当前 trace 段...")
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
        self._lbl_saved.setText(f"已保存: {count} 段")
        self._log(f"✓ 第 {count} 段已保存", "success")

    def _on_stop(self) -> None:
        self._set_capturing(False)
        self._timer.stop()

        if self._jank_worker:
            self._stop_jank_monitor()

        if not self._service or not self._serial:
            return
        self._log("停止抓取，导出 trace...")

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
            self._log(f"✓ 已导出 {len(paths)} 个文件:", "success")
            for p in paths:
                self._log(f"  {p}")
            export_dir = Path(paths[0]).parent
            if export_dir.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(export_dir)))
                self._log(f"📂 已打开导出目录: {export_dir}")
        else:
            self._log("本次抓取未保存有效 trace", "warning")
        self._lbl_status.setText("🟢 就绪")
        self._lbl_timer.setText("时长: --:--")
        self._saved_count = 0
        self._lbl_saved.setText("已保存: 0 段")

    def _on_error(self, msg: str) -> None:
        if self._capturing and ("设备不可用" in msg or "device" in msg.lower()):
            self._on_device_disconnected()
            self._log(f"✗ {msg}", "error")
            return
        self._log(f"✗ {msg}", "error")
        self._set_capturing(False)
        self._timer.stop()
        self._lbl_status.setText("🟢 就绪")

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
        self._lbl_timer.setText("时长: --:--")
        self._saved_count = 0
        self._lbl_saved.setText("已保存: 0 段")
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
        except Exception as e:
            self._log(f"✗ Jank 监控启动失败: {e}", "error")

    def _stop_jank_monitor(self) -> None:
        """停止 Jank 监控。"""
        if self._jank_worker:
            self._jank_worker.stop_monitor()
            self._jank_worker = None
            self._jank_config_panel.set_enabled(True)
            self._log("■ Jank 监控已停止", "info")

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
