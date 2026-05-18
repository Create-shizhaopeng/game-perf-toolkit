"""Perfetto 分析对话组件

右栏 AI 对话区域，支持流式消息展示、输入交互和分析任务管理。
包含 AnalysisWorker（QThread）驱动异步分析。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.theme_colors import THEMES as _THEMES

logger = logging.getLogger(__name__)

_THEME = _THEMES["dark"]


class AnalysisChatWidget(QWidget):
    """AI 分析对话组件（嵌入历史面板右栏）。"""

    send_message = pyqtSignal(str, list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_traces: list[dict] = []
        self._is_analyzing = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 8)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header = QLabel("💬 AI 分析对话")
        header.setObjectName("analysisChatHeader")
        header_row.addWidget(header)
        header_row.addStretch()

        self._btn_clear = QPushButton("🗑")
        self._btn_clear.setObjectName("ghostBtn")
        self._btn_clear.setFixedSize(24, 24)
        self._btn_clear.setToolTip("清空对话")
        self._btn_clear.clicked.connect(self.clear_chat)
        header_row.addWidget(self._btn_clear)
        layout.addLayout(header_row)

        self._trace_hint = QLabel()
        self._trace_hint.setObjectName("fieldHint")
        self._trace_hint.setWordWrap(True)
        self._trace_hint.hide()
        layout.addWidget(self._trace_hint)

        self._chat_display = QTextBrowser()
        self._chat_display.setObjectName("analysisChatDisplay")
        self._chat_display.setOpenExternalLinks(True)
        layout.addWidget(self._chat_display, 1)

        input_row = QHBoxLayout()
        input_row.setSpacing(4)

        self._input = QLineEdit()
        self._input.setObjectName("analysisChatInput")
        self._input.setPlaceholderText("描述分析需求，如：分析卡顿原因...")
        self._input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._input, 1)

        self._btn_send = QPushButton("发送")
        self._btn_send.setObjectName("primaryBtn")
        self._btn_send.setFixedWidth(64)
        self._btn_send.clicked.connect(self._on_send)
        input_row.addWidget(self._btn_send)

        layout.addLayout(input_row)

    def set_selected_traces(self, traces: list[dict]) -> None:
        """更新当前选中的 trace 列表。"""
        self._selected_traces = traces
        if not traces:
            self._trace_hint.hide()
            return

        names = [Path(t.get("path", "")).name for t in traces if t.get("type") == "trace"]
        if not names:
            self._trace_hint.hide()
            return

        has_package = any(t.get("target_package") for t in traces)
        hint = f"📎 已选择 {len(names)} 个 trace: {', '.join(names[:3])}"
        if len(names) > 3:
            hint += f" 等 {len(names)} 个"
        if not has_package:
            hint += "\n⚠ 未检测到目标进程，请在下方描述分析场景"
        self._trace_hint.setText(hint)
        self._trace_hint.show()

    def append_message(self, role: str, content: str) -> None:
        """追加对话消息到显示区域。"""
        if role == "user":
            bg = _THEME["msg_user"]
            label = "👤 你"
        elif role == "assistant":
            bg = _THEME["msg_ai"]
            label = "🤖 AI"
        else:
            bg = _THEME["msg_ai"]
            label = f"🔧 {role}"

        html = (
            f'<div style="background:{bg}; border-radius:6px; padding:8px; '
            f'margin:4px 0;">'
            f'<b style="color:{_THEME["accent"]};">{label}</b><br/>'
            f'<span style="color:{_THEME["fg"]};">{content}</span>'
            f"</div>"
        )
        self._chat_display.append(html)

    def append_stream_chunk(self, content: str) -> None:
        """追加流式输出内容（追加到最后一条消息）。"""
        cursor = self._chat_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertHtml(f'<span style="color:{_THEME["fg"]};">{content}</span>')
        self._chat_display.setTextCursor(cursor)
        self._chat_display.ensureCursorVisible()

    def set_analyzing(self, analyzing: bool) -> None:
        """切换分析状态（发送/取消按钮切换）。"""
        self._is_analyzing = analyzing
        self._input.setEnabled(not analyzing)
        if analyzing:
            self._btn_send.setText("取消")
            self._btn_send.setObjectName("stopBtn")
        else:
            self._btn_send.setText("发送")
            self._btn_send.setObjectName("primaryBtn")
        self._btn_send.style().unpolish(self._btn_send)
        self._btn_send.style().polish(self._btn_send)

    def show_batch_progress(self, current: int, total: int, trace_name: str, status: str) -> None:
        """显示批量分析进度。"""
        status_icons = {
            "PENDING": "⏳",
            "ROUTING": "🔀",
            "ANALYZING": "🔬",
            "REVIEWING": "📋",
            "COMPLETED": "✅",
            "FAILED": "❌",
            "TIMEOUT": "⏰",
            "CANCELLED": "🚫",
        }
        icon = status_icons.get(status, "⏳")
        html = (
            f'<div style="background:{_THEME["msg_ai"]}; border-radius:4px; '
            f'padding:4px 8px; margin:2px 0; font-size:12px;">'
            f'{icon} [{current}/{total}] {trace_name}: {status}'
            f'</div>'
        )
        self._chat_display.append(html)

    def clear_chat(self) -> None:
        """清空对话历史。"""
        self._chat_display.clear()

    def _on_send(self) -> None:
        if self._is_analyzing:
            self.send_message.emit("__cancel__", [])
            return

        text = self._input.text().strip()
        if not text:
            return

        self._input.clear()
        self.append_message("user", text)
        self.send_message.emit(text, self._selected_traces)


class AnalysisWorker(QThread):
    """后台线程运行 AnalysisOrchestrator 异步流程。"""

    message_received = pyqtSignal(str, str)
    status_changed = pyqtSignal(str, str, str)
    finished_with_report = pyqtSignal(str)
    analysis_error = pyqtSignal(str)

    def __init__(
        self,
        orchestrator: Any,
        trace_path: str,
        user_intent: str,
        process_name: str = "",
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._orchestrator = orchestrator
        self._trace_path = trace_path
        self._user_intent = user_intent
        self._process_name = process_name

    def request_abort(self) -> None:
        self._orchestrator.request_abort()

    def run(self) -> None:
        try:
            def on_status(task_id: str, status: Any, detail: str = "") -> None:
                self.status_changed.emit(task_id, str(status), detail)

            def on_stream(task_id: str, role: str, content: str) -> None:
                self.message_received.emit(role, content)

            report = asyncio.run(
                self._orchestrator.analyze_single(
                    self._trace_path,
                    self._user_intent,
                    self._process_name,
                    on_status=on_status,
                    on_stream=on_stream,
                )
            )
            if report and report.html_path:
                self.finished_with_report.emit(report.html_path)
            else:
                self.finished_with_report.emit("")

        except Exception as exc:
            logger.exception("AnalysisWorker 运行失败: %s", exc)
            self.analysis_error.emit(str(exc))
