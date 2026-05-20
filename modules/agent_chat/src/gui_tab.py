# -*- coding: utf-8 -*-
"""Agent 智能助手 — GUI Tab（Phase 3）。

实现 T018-T023：完整的聊天界面、消息渲染、异步 Worker、
会话历史管理、SOP 管理面板、设置弹窗。
"""
from __future__ import annotations

import datetime
import logging
import os
import platform
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.base_tab import BaseTab
from toolkit.gui.codicons import codicon_font, icon_char
from toolkit.gui.theme_colors import THEMES as _THEMES
from toolkit.gui.toolkit_dialog import (
    ToolkitDialog,
    confirm_dialog,
    info_dialog,
    input_dialog,
    warning_dialog,
)

from .strings_gui import *

logger = logging.getLogger(__name__)
HISTORY_SEND_TO_AGENT_EVENT = "history.send_to_agent"

_DARK = _THEMES["dark"]


def compose_message_with_context(text: str, contexts: list[dict[str, Any]]) -> str:
    if not contexts:
        return text
    unique_paths: list[str] = []
    seen = set()
    for ctx in contexts:
        p = str(ctx.get("file_path") or "").strip()
        if p and p not in seen:
            seen.add(p)
            unique_paths.append(p)
    if not unique_paths:
        return text
    extra = "\n".join(f"- {p}" for p in unique_paths)
    return f"{text}\n\n{CONTEXT_FILE_CONTEXT}\n{extra}"


# ---------------------------------------------------------------------------
# T019: 消息渲染 Widgets
# ---------------------------------------------------------------------------


class _UserMessageWidget(QFrame):
    """用户消息气泡（右对齐蓝色气泡）。"""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(30, 4, 8, 4)
        layout.addStretch()

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble.setStyleSheet(
            f"background-color: {_DARK['user_bubble']};"
            "border-radius: 10px;"
            "padding: 10px 14px;"
            f"color: {_DARK['fg']};"
        )
        layout.addWidget(bubble)


class _AgentTextWidget(QFrame):
    """Agent 文本回复（左对齐，支持流式追加）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 30, 4)

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self._label.setOpenExternalLinks(False)
        self._label.linkActivated.connect(self._on_link)
        self._label.setStyleSheet(
            "padding: 8px 12px;"
            f"color: {_DARK['fg']};"
        )
        self._text_parts: list[str] = []
        layout.addWidget(self._label, 1)
        layout.addStretch()

    def set_thinking(self, hint: str) -> None:
        """显示思考状态（带动画点）。"""
        if not self._text_parts:
            self._label.setText(f"💭 {hint}")
            self._label.setStyleSheet(
                "padding: 8px 12px;"
                f"color: {_DARK['fg_dim']};"
                "font-style: italic;"
            )

    def clear_thinking(self) -> None:
        """清除思考状态，恢复正常样式。"""
        self._label.setStyleSheet(
            "padding: 8px 12px;"
            f"color: {_DARK['fg']};"
        )

    def append_text(self, text: str) -> None:
        self._text_parts.append(text)
        self._label.setText("".join(self._text_parts))

    def set_full_text(self, text: str) -> None:
        self._text_parts = [text]
        self._label.setText(text)

    def get_text(self) -> str:
        return "".join(self._text_parts)

    def _on_link(self, url: str) -> None:
        if url.startswith("file://"):
            _open_path(url.replace("file://", ""))


class _ToolCallCard(QFrame):
    """工具调用可折叠卡片。"""

    def __init__(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tool_name = tool_name
        self._collapsed = True
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"background-color: {_DARK['tool_card_bg']};"
            f"border: 1px solid {_DARK['border']};"
            "border-radius: 6px;"
            "margin: 4px 8px 4px 24px;"
        )

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 8, 10, 8)
        self._layout.setSpacing(4)

        header = QHBoxLayout()
        self._icon_label = QLabel("⏳")
        self._title_label = QLabel(f"📎 {tool_name}")
        self._title_label.setStyleSheet(f"color: {_DARK['accent']}; font-weight: bold; border: none;")
        self._status_label = QLabel(STATE_TOOL_RUNNING)
        self._status_label.setStyleSheet(f"color: {_DARK['fg_dim']}; border: none;")
        self._toggle_btn = QPushButton(STATE_TOOL_EXPAND)
        self._toggle_btn.setFixedWidth(60)
        self._toggle_btn.setStyleSheet(
            f"color: {_DARK['accent']}; border: none; font-size: 11px;"
        )
        self._toggle_btn.clicked.connect(self._toggle_detail)
        self._toggle_btn.setVisible(False)
        header.addWidget(self._icon_label)
        header.addWidget(self._title_label)
        header.addStretch()
        header.addWidget(self._status_label)
        header.addWidget(self._toggle_btn)
        self._layout.addLayout(header)

        args_text = ""
        if arguments:
            for k, v in arguments.items():
                val_str = str(v)
                if len(val_str) > 80:
                    val_str = val_str[:77] + "..."
                args_text += f"{k}: {val_str}\n"
        if args_text:
            args_label = QLabel(args_text.strip())
            args_label.setWordWrap(True)
            args_label.setStyleSheet(f"color: {_DARK['fg_dim']}; font-size: 11px; border: none;")
            self._layout.addWidget(args_label)

        self._detail_frame = QFrame()
        self._detail_frame.setVisible(False)
        self._detail_layout = QVBoxLayout(self._detail_frame)
        self._detail_layout.setContentsMargins(0, 4, 0, 0)
        self._detail_layout.setSpacing(2)
        self._layout.addWidget(self._detail_frame)

        self._report_layout = QHBoxLayout()
        self._report_layout.setContentsMargins(0, 4, 0, 0)
        self._layout.addLayout(self._report_layout)

    def set_running(self, elapsed_sec: float = 0) -> None:
        self._icon_label.setText("⏳")
        if elapsed_sec > 0:
            self._status_label.setText(STATE_TOOL_RUNNING_FMT.format(elapsed_sec))
        else:
            self._status_label.setText(STATE_TOOL_RUNNING)

    def set_complete(self, elapsed_ms: float, content_preview: str = "") -> None:
        secs = elapsed_ms / 1000
        self._icon_label.setText("✅")
        self._status_label.setText(STATE_TOOL_COMPLETE_FMT.format(secs))
        self._status_label.setStyleSheet(f"color: {_DARK['success']}; border: none;")
        if content_preview:
            detail_label = QLabel(content_preview)
            detail_label.setWordWrap(True)
            detail_label.setStyleSheet(f"color: {_DARK['fg_dim']}; font-size: 11px; border: none;")
            self._detail_layout.addWidget(detail_label)
            self._toggle_btn.setVisible(True)

    def set_failed(self, error_msg: str = "") -> None:
        self._icon_label.setText("❌")
        self._status_label.setText(STATE_TOOL_FAILED)
        self._status_label.setStyleSheet(f"color: {_DARK['error']}; border: none;")
        if error_msg:
            err_label = QLabel(error_msg)
            err_label.setWordWrap(True)
            err_label.setStyleSheet(f"color: {_DARK['error']}; font-size: 11px; border: none;")
            self._detail_layout.addWidget(err_label)
            self._toggle_btn.setVisible(True)

    def set_cancelled(self) -> None:
        self._icon_label.setText("⛔")
        self._status_label.setText(STATE_TOOL_CANCELLED)
        self._status_label.setStyleSheet(f"color: {_DARK['warning']}; border: none;")

    def add_report_button(self, report_path: str) -> None:
        btn = QPushButton(BTN_OPEN_REPORT_DIR)
        btn.setFixedHeight(24)
        btn.setStyleSheet(
            f"color: {_DARK['accent']}; border: 1px solid {_DARK['border']}; "
            "border-radius: 4px; padding: 2px 8px; font-size: 11px;"
        )
        btn.clicked.connect(lambda: _open_path(str(Path(report_path).parent)))
        self._report_layout.addWidget(btn)

        btn2 = QPushButton(BTN_VIEW_REPORT)
        btn2.setFixedHeight(24)
        btn2.setStyleSheet(
            f"color: {_DARK['accent']}; border: 1px solid {_DARK['border']}; "
            "border-radius: 4px; padding: 2px 8px; font-size: 11px;"
        )
        btn2.clicked.connect(lambda: _open_path(report_path))
        self._report_layout.addWidget(btn2)
        self._report_layout.addStretch()

    def _toggle_detail(self) -> None:
        self._collapsed = not self._collapsed
        self._detail_frame.setVisible(not self._collapsed)
        self._toggle_btn.setText(STATE_TOOL_COLLAPSE if not self._collapsed else STATE_TOOL_EXPAND)


class _TokenUsageLabel(QLabel):
    """Token 用量显示（灰色小字）。"""

    def __init__(self, usage: dict[str, int], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        inp = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        out = usage.get("completion_tokens", usage.get("output_tokens", 0))
        text = TOKEN_USAGE_FMT.format(inp, out)
        self.setText(text)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setStyleSheet(f"color: {_DARK['fg_dim']}; font-size: 10px; padding: 2px 12px;")


class _SystemNotice(QLabel):
    """系统提示（居中灰色小字）。"""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"color: {_DARK['fg_dim']}; font-size: 11px; padding: 6px;")


class _WorkflowOverview(QFrame):
    """工作流概览卡片（紫色左边框）。"""

    def __init__(self, sop_title: str, steps: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"background-color: {_DARK['card_bg']};"
            f"border-left: 3px solid {_DARK['workflow_border']};"
            "border-radius: 6px;"
            "margin: 4px 8px;"
            "padding: 10px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        title = QLabel(WORKFLOW_TITLE_FMT.format(sop_title))
        title.setStyleSheet(f"color: {_DARK['accent']}; font-weight: bold; border: none;")
        layout.addWidget(title)
        for i, step in enumerate(steps, 1):
            lbl = QLabel(WORKFLOW_STEP_FMT.format(i, step))
            lbl.setStyleSheet(f"color: {_DARK['fg']}; font-size: 11px; border: none;")
            layout.addWidget(lbl)


class _WorkflowDepositCard(QFrame):
    """工作流沉淀卡片（黄色左边框）。"""

    save_new = pyqtSignal(dict)
    skipped = pyqtSignal()

    def __init__(self, summary: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._summary = summary
        self.setStyleSheet(
            f"background-color: {_DARK['card_bg']};"
            "border-left: 3px solid #F59E0B;"
            "border-radius: 6px;"
            "margin: 4px 8px;"
            "padding: 10px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        header = QLabel(WORKFLOW_DEPOSIT_HEADER)
        header.setStyleSheet(
            f"color: #F59E0B; font-weight: bold; font-size: 13px; border: none;"
        )
        layout.addWidget(header)

        tools = summary.get("unique_tools", [])
        steps = summary.get("total_steps", 0)
        desc = QLabel(WORKFLOW_DEPOSIT_DESC_FMT.format(len(tools), steps))
        desc.setStyleSheet(f"color: {_DARK['fg']}; font-size: 11px; border: none;")
        layout.addWidget(desc)

        if tools:
            tool_text = QLabel(f"工具: {', '.join(tools)}")
            tool_text.setStyleSheet(f"color: {_DARK['fg_dim']}; font-size: 10px; border: none;")
            tool_text.setWordWrap(True)
            layout.addWidget(tool_text)

        deviation = summary.get("sop_deviation", "")
        if deviation:
            dev_text = QLabel(WORKFLOW_DEVIATION_FMT.format(deviation))
            dev_text.setStyleSheet("color: #FB923C; font-size: 10px; border: none;")
            dev_text.setWordWrap(True)
            layout.addWidget(dev_text)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_save = QPushButton(BTN_SAVE_NEW_SOP)
        btn_save.setStyleSheet(
            "QPushButton { background-color: #F59E0B; color: #1E1E2E; "
            "border: none; border-radius: 4px; padding: 5px 12px; font-size: 11px; }"
            "QPushButton:hover { background-color: #D97706; }"
        )
        btn_save.clicked.connect(self._on_save_new)
        btn_row.addWidget(btn_save)

        btn_skip = QPushButton(BTN_SKIP)
        btn_skip.setStyleSheet(
            f"QPushButton {{ background-color: {_DARK['card_bg']}; color: {_DARK['fg_dim']}; "
            "border: 1px solid #555; border-radius: 4px; padding: 5px 12px; font-size: 11px; }"
            f"QPushButton:hover {{ background-color: {_DARK['hover']}; }}"
        )
        btn_skip.clicked.connect(self._on_skip)
        btn_row.addWidget(btn_skip)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _on_save_new(self) -> None:
        self.save_new.emit(self._summary)
        self._show_done(STATE_SAVING)

    def _on_skip(self) -> None:
        self.skipped.emit()
        self._show_done(STATE_SKIPPED)

    def _show_done(self, msg: str) -> None:
        for child in self.findChildren(QPushButton):
            child.setEnabled(False)
        done_label = QLabel(STATE_DONE_FMT.format(msg))
        done_label.setStyleSheet(f"color: {_DARK['fg_dim']}; font-size: 10px; border: none;")
        self.layout().addWidget(done_label)


# ---------------------------------------------------------------------------
# T020: 异步 Worker (QThread)
# ---------------------------------------------------------------------------


class _AgentWorker(QThread):
    """后台执行 AgentService.chat() 的线程。

    在 QThread 内部启动 asyncio event loop 来运行异步 chat()。
    """

    text_chunk = pyqtSignal(str)
    tool_start = pyqtSignal(dict)
    tool_end = pyqtSignal(dict)
    usage_received = pyqtSignal(dict)
    workflow_deposit = pyqtSignal(dict)
    thinking = pyqtSignal(str)
    finished_ok = pyqtSignal(str, str)  # full_text, conversation_id
    error = pyqtSignal(str)

    def __init__(
        self,
        service: Any,
        message: str,
        conversation_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._message = message
        self._conv_id = conversation_id

    def run(self) -> None:
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_async())
        finally:
            loop.close()

    async def _run_async(self) -> None:
        from .models import StreamChunkType

        try:
            logger.debug("[DIAG] AgentWorker._run_async: 调用 chat()")
            response = await self._service.chat(
                user_message=self._message,
                conversation_id=self._conv_id,
                on_chunk=self._on_chunk,
            )
            logger.debug("[DIAG] AgentWorker._run_async: chat() 返回, text_len=%d", len(response.text))
            self.finished_ok.emit(response.text, self._conv_id or "")
        except Exception as exc:
            logger.error(LOG_WORKER_EXCEPTION, exc, exc_info=True)
            try:
                self.error.emit(str(exc))
            except RuntimeError:
                pass

    def _on_chunk(self, chunk: Any) -> None:
        from .models import StreamChunkType

        try:
            if chunk.type == StreamChunkType.TEXT:
                self.text_chunk.emit(str(chunk.data))
            elif chunk.type == StreamChunkType.TOOL_START:
                data = chunk.data if isinstance(chunk.data, dict) else {}
                self.tool_start.emit(data)
            elif chunk.type == StreamChunkType.TOOL_END:
                data = chunk.data if isinstance(chunk.data, dict) else {}
                self.tool_end.emit(data)
            elif chunk.type == StreamChunkType.USAGE:
                if isinstance(chunk.data, dict):
                    self.usage_received.emit(chunk.data)
            elif chunk.type == StreamChunkType.WORKFLOW_DEPOSIT:
                data = chunk.data if isinstance(chunk.data, dict) else {}
                self.workflow_deposit.emit(data)
            elif chunk.type == StreamChunkType.THINKING:
                self.thinking.emit(str(chunk.data))
            elif chunk.type == StreamChunkType.ERROR:
                self.error.emit(str(chunk.data))
        except RuntimeError:
            logger.debug(LOG_ON_CHUNK_FAILED)

    def cancel(self) -> None:
        if self._service:
            self._service.cancel()


# ---------------------------------------------------------------------------
# T020: 自适应高度输入框
# ---------------------------------------------------------------------------


class _ScrollableTabBar(QTabBar):
    """支持滚轮切换 Tab 的 QTabBar。"""

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta > 0:
            new_idx = self.currentIndex() - 1
        elif delta < 0:
            new_idx = self.currentIndex() + 1
        else:
            return
        if 0 <= new_idx < self.count():
            self.setCurrentIndex(new_idx)
            self.tabBarClicked.emit(new_idx)
        event.accept()


class _ChatInput(QTextEdit):
    """自适应高度（1-5 行）输入框，Enter 发送，Shift+Enter 换行。"""

    send_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("agentChatInput")
        self.setAcceptDrops(True)
        self.setPlaceholderText(PLACEHOLDER_CHAT_INPUT)
        self._min_lines = 1
        self._max_lines = 5
        self.textChanged.connect(self._adjust_height)
        self.setFixedHeight(36)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.send_requested.emit()
            return
        super().keyPressEvent(event)

    def _adjust_height(self) -> None:
        doc = self.document()
        line_count = max(1, min(doc.blockCount(), self._max_lines))
        line_height = self.fontMetrics().lineSpacing()
        new_height = line_count * line_height + 16
        self.setFixedHeight(max(36, min(new_height, self._max_lines * line_height + 16)))

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            current = self.toPlainText()
            sep = "\n" if current else ""
            self.setPlainText(current + sep + "\n".join(paths))
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


# ---------------------------------------------------------------------------
# T023: 设置弹窗
# ---------------------------------------------------------------------------


class _SettingsDialog(ToolkitDialog):
    """Agent 设置弹窗 — 继承 ToolkitDialog 统一框架。"""

    config_changed = pyqtSignal(object)  # AgentConfig

    def __init__(
        self,
        config: Any,
        sop_manager: Any | None = None,
        mcp_manager: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(DLG_TITLE_AGENT_SETTINGS, parent, min_width=560)
        self.setMinimumHeight(460)
        self._config = config
        self._sop_manager = sop_manager
        self._mcp_manager = mcp_manager
        self._init_ui()

    def _init_ui(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._build_sop_tab(), GROUP_SOP_MANAGEMENT)
        tabs.addTab(self._build_mcp_tab(), GROUP_MCP_MANAGEMENT)
        tabs.addTab(self._build_advanced_tab(), GROUP_ADVANCED_SETTINGS)
        self.content_layout.addWidget(tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_save = QPushButton(BTN_SAVE)
        btn_save.setObjectName("primaryBtn")
        btn_save.setFixedWidth(80)
        btn_save.clicked.connect(self._on_save)
        btn_cancel = QPushButton(BTN_CANCEL)
        btn_cancel.setObjectName("secondaryBtn")
        btn_cancel.setFixedWidth(80)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        self.content_layout.addLayout(btn_layout)

    def _build_model_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        grp = QGroupBox(GROUP_LLM_PROVIDER)
        grp_layout = QHBoxLayout(grp)
        self._rb_glm = QPushButton(BTN_GLM)
        self._rb_glm.setCheckable(True)
        self._rb_claude = QPushButton(BTN_CLAUDE)
        self._rb_claude.setCheckable(True)
        if self._config.provider == "claude":
            self._rb_claude.setChecked(True)
        else:
            self._rb_glm.setChecked(True)
        self._rb_glm.clicked.connect(lambda: self._rb_claude.setChecked(False))
        self._rb_claude.clicked.connect(lambda: self._rb_glm.setChecked(False))
        grp_layout.addWidget(self._rb_glm)
        grp_layout.addWidget(self._rb_claude)
        layout.addWidget(grp)

        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel(LABEL_API_KEY))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        current_key = self._config.api_key
        if not current_key:
            if self._config.provider == "glm":
                current_key = self._config.glm_api_key
            else:
                current_key = self._config.claude_api_key
        self._key_input.setText(current_key)
        key_layout.addWidget(self._key_input, 1)
        self._btn_toggle_key = QPushButton(BTN_TOGGLE_KEY_SHOW)
        self._btn_toggle_key.setFixedWidth(30)
        self._btn_toggle_key.clicked.connect(self._toggle_key_visibility)
        key_layout.addWidget(self._btn_toggle_key)
        layout.addLayout(key_layout)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel(LABEL_MODEL))
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        glm_models = ["glm-4-plus", "glm-4-flash", "glm-4-long", "glm-4"]
        claude_models = ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]
        self._model_combo.addItems(glm_models + claude_models)
        self._model_combo.setCurrentText(self._config.model_name)
        model_layout.addWidget(self._model_combo, 1)
        layout.addLayout(model_layout)

        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel(LABEL_REPLY_LANGUAGE))
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["中文", "English"])
        self._lang_combo.setCurrentIndex(0 if self._config.language == "zh" else 1)
        lang_layout.addWidget(self._lang_combo)
        lang_layout.addStretch()
        layout.addLayout(lang_layout)

        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel(LABEL_TEMPERATURE))
        self._temp_slider = QSlider(Qt.Orientation.Horizontal)
        self._temp_slider.setRange(0, 100)
        self._temp_slider.setValue(int(self._config.temperature * 100))
        self._temp_value = QLabel(f"{self._config.temperature:.2f}")
        self._temp_slider.valueChanged.connect(
            lambda v: self._temp_value.setText(f"{v / 100:.2f}")
        )
        temp_layout.addWidget(self._temp_slider, 1)
        temp_layout.addWidget(self._temp_value)
        layout.addLayout(temp_layout)

        self._chk_smart = QCheckBox(CHECK_SMART_SWITCH)
        self._chk_smart.setChecked(self._config.smart_switch)
        layout.addWidget(self._chk_smart)

        layout.addStretch()
        return w

    def _build_sop_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self._sop_tree = QTreeWidget()
        self._sop_tree.setHeaderLabels([LABEL_SOP_NAME, LABEL_SOP_SOURCE, LABEL_SOP_ACTION])
        self._sop_tree.setColumnWidth(0, 200)
        self._sop_tree.setColumnWidth(1, 60)
        self._refresh_sop_tree()
        layout.addWidget(self._sop_tree, 1)

        btn_row = QHBoxLayout()
        btn_import = QPushButton(BTN_IMPORT_SOP)
        btn_import.clicked.connect(self._on_import_sop)
        btn_row.addWidget(btn_import)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    def _build_mcp_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        desc = QLabel(MCP_DESC)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {_DARK['fg_dim']}; font-size: 11px; padding: 4px;")
        layout.addWidget(desc)

        self._mcp_tree = QTreeWidget()
        self._mcp_tree.setHeaderLabels([LABEL_MCP_SERVER, LABEL_MCP_STATUS, LABEL_MCP_TOOL_COUNT])
        self._mcp_tree.setColumnWidth(0, 200)
        self._mcp_tree.setColumnWidth(1, 80)
        self._refresh_mcp_tree()
        layout.addWidget(self._mcp_tree, 1)

        btn_row = QHBoxLayout()
        btn_add = QPushButton(BTN_ADD_MCP_SERVER)
        btn_add.clicked.connect(self._on_add_mcp_server)
        btn_remove = QPushButton(BTN_REMOVE_MCP_SERVER)
        btn_remove.clicked.connect(self._on_remove_mcp_server)
        btn_toggle = QPushButton(BTN_TOGGLE_MCP_SERVER)
        btn_toggle.clicked.connect(self._on_toggle_mcp_server)
        for btn in (btn_add, btn_remove, btn_toggle):
            btn.setFixedHeight(24)
            btn.setStyleSheet(
                f"color: {_DARK['fg_dim']}; border: 1px solid {_DARK['border']}; "
                "border-radius: 4px; font-size: 11px; padding: 2px 8px;"
            )
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addWidget(btn_toggle)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    def _refresh_mcp_tree(self) -> None:
        self._mcp_tree.clear()
        if not self._mcp_manager:
            item = QTreeWidgetItem(self._mcp_tree, [LABEL_MCP_SDK_NOT_INSTALLED, "--", "0"])
            return

        servers = self._mcp_manager.get_servers()
        connections = self._mcp_manager.get_connections()
        conn_map = {c.server_name: c for c in connections}

        for name, cfg in servers.items():
            conn = conn_map.get(name)
            if conn:
                status_text = conn.status.value
                tools_count = str(len(conn.available_tools))
            else:
                status_text = STATE_CONNECTING if cfg.enabled else STATE_DISABLED
                tools_count = "0"
            item = QTreeWidgetItem(self._mcp_tree, [name, status_text, tools_count])
            if conn and conn.available_tools:
                for t in conn.available_tools:
                    QTreeWidgetItem(item, [MCP_TOOL_PREFIX.format(t), "", ""])

    def _on_add_mcp_server(self) -> None:
        if not self._mcp_manager:
            warning_dialog(self, DLG_TITLE_MCP, MSG_MCP_NOT_INSTALLED)
            return
        name, ok = input_dialog(self, DLG_TITLE_ADD_MCP_SERVER, MSG_SOP_SERVER_NAME)
        if not ok or not name.strip():
            return
        cmd, ok = input_dialog(self, DLG_TITLE_ADD_MCP_SERVER, MSG_SOP_START_CMD)
        if not ok or not cmd.strip():
            return
        args_str, ok = input_dialog(self, DLG_TITLE_ADD_MCP_SERVER, MSG_SOP_ARGS)
        args = args_str.strip().split() if args_str.strip() else []

        from .models import MCPServerConfig
        config = MCPServerConfig(name=name.strip(), command=cmd.strip(), args=args)
        self._mcp_manager.add_server(config)
        self._refresh_mcp_tree()

    def _on_remove_mcp_server(self) -> None:
        if not self._mcp_manager:
            return
        item = self._mcp_tree.currentItem()
        if item and item.parent() is None:
            name = item.text(0)
            self._mcp_manager.remove_server(name)
            self._refresh_mcp_tree()

    def _on_toggle_mcp_server(self) -> None:
        if not self._mcp_manager:
            return
        item = self._mcp_tree.currentItem()
        if item and item.parent() is None:
            name = item.text(0)
            servers = self._mcp_manager.get_servers()
            if name in servers:
                current = servers[name].enabled
                self._mcp_manager.update_server(name, enabled=not current)
                self._refresh_mcp_tree()

    def _build_advanced_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        grp_hist = QGroupBox(GROUP_CONVERSATION_HISTORY)
        hist_layout = QVBoxLayout(grp_hist)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel(LABEL_MAX_CONVERSATIONS))
        self._spin_max_conv = QSpinBox()
        self._spin_max_conv.setRange(5, 200)
        self._spin_max_conv.setValue(self._config.max_conversations)
        row1.addWidget(self._spin_max_conv)
        row1.addStretch()
        hist_layout.addLayout(row1)
        layout.addWidget(grp_hist)

        grp_ctx = QGroupBox(GROUP_CONTEXT_MANAGEMENT)
        ctx_layout = QVBoxLayout(grp_ctx)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel(LABEL_MAX_CONTEXT_MESSAGES))
        self._spin_max_ctx = QSpinBox()
        self._spin_max_ctx.setRange(5, 100)
        self._spin_max_ctx.setValue(self._config.max_context_messages)
        row2.addWidget(self._spin_max_ctx)
        row2.addStretch()
        ctx_layout.addLayout(row2)
        row3 = QHBoxLayout()
        row3.addWidget(QLabel(LABEL_TOOL_RESULT_MAX_LENGTH))
        self._spin_tool_len = QSpinBox()
        self._spin_tool_len.setRange(500, 10000)
        self._spin_tool_len.setSingleStep(500)
        self._spin_tool_len.setValue(self._config.tool_result_max_length)
        row3.addWidget(self._spin_tool_len)
        row3.addWidget(QLabel(LABEL_CHARACTERS))
        row3.addStretch()
        ctx_layout.addLayout(row3)
        layout.addWidget(grp_ctx)

        grp_wf = QGroupBox(GROUP_WORKFLOW_LEARNING)
        wf_layout = QVBoxLayout(grp_wf)
        self._chk_wf_learn = QCheckBox(CHECK_WORKFLOW_LEARNING)
        self._chk_wf_learn.setChecked(self._config.workflow_learning_enabled)
        wf_layout.addWidget(self._chk_wf_learn)
        layout.addWidget(grp_wf)

        grp_lang = QGroupBox(GROUP_LANGUAGE)
        lang_layout = QHBoxLayout(grp_lang)
        lang_layout.addWidget(QLabel(LABEL_REPLY_LANGUAGE))
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["中文", "English"])
        self._lang_combo.setCurrentIndex(0 if self._config.language == "zh" else 1)
        lang_layout.addWidget(self._lang_combo)
        lang_layout.addStretch()
        layout.addWidget(grp_lang)

        layout.addStretch()
        return w

    def _toggle_key_visibility(self) -> None:
        if self._key_input.echoMode() == QLineEdit.EchoMode.Password:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._btn_toggle_key.setText(BTN_TOGGLE_KEY_HIDE)
        else:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._btn_toggle_key.setText(BTN_TOGGLE_KEY_SHOW)

    def _refresh_sop_tree(self) -> None:
        self._sop_tree.clear()
        if not self._sop_manager:
            return
        from .models import SOPSource
        sops = self._sop_manager.load_all()
        builtin_root = QTreeWidgetItem(self._sop_tree, [SOP_BUILTIN_FOLDER, "", ""])
        custom_root = QTreeWidgetItem(self._sop_tree, [SOP_CUSTOM_FOLDER, "", ""])
        for doc in sops:
            source_text = SOP_BUILT_IN if doc.source == SOPSource.BUILTIN else SOP_CUSTOM
            parent = builtin_root if doc.source == SOPSource.BUILTIN else custom_root
            item = QTreeWidgetItem(parent, [f"📄 {doc.title}", source_text, ""])
            item.setData(0, Qt.ItemDataRole.UserRole, doc)
        builtin_root.setExpanded(True)
        custom_root.setExpanded(True)

    def _on_import_sop(self) -> None:
        if not self._sop_manager:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, DLG_TITLE_IMPORT_SOP, "", FILE_FILTER_MARKDOWN
        )
        if path:
            self._sop_manager.import_sop(Path(path))
            self._refresh_sop_tree()

    def _on_save(self) -> None:
        from .models import save_config

        language = "en" if self._lang_combo.currentIndex() == 1 else "zh"

        updates: dict = {
            "language": language,
            "max_conversations": self._spin_max_conv.value(),
            "max_context_messages": self._spin_max_ctx.value(),
            "tool_result_max_length": self._spin_tool_len.value(),
            "workflow_learning_enabled": self._chk_wf_learn.isChecked(),
        }

        new_config = self._config.model_copy(update=updates)
        save_config(new_config)
        self._config = new_config
        self.config_changed.emit(new_config)
        self.accept()


# ---------------------------------------------------------------------------
# T018 + T019 + T020 + T021 + T022: AgentTab 主体
# ---------------------------------------------------------------------------


class AgentTab(BaseTab):
    """Agent 智能助手 Tab — 完整聊天界面。"""

    tab_title = TAB_TITLE
    tab_icon = TAB_ICON

    def __init__(self, context: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._service: Any = None
        self._store: Any = None
        self._sop_manager: Any = None
        self._skills_manager: Any = None
        self._mcp_manager: Any = None
        self._config: Any = None
        self._worker: _AgentWorker | None = None
        self._current_conv_id: str | None = None
        self._current_agent_widget: _AgentTextWidget | None = None
        self._current_tool_cards: dict[str, _ToolCallCard] = {}
        self._last_usage: dict[str, int] = {}
        self._is_running = False
        self._scroll_pending = False
        self._history_event_bound = False
        self._pending_history_payloads: list[dict[str, Any]] = []
        self._conv_contexts: dict[str, list[dict[str, Any]]] = {}
        self._draft_contexts: list[dict[str, Any]] = []

        self._init_ui()
        self._bind_history_event()

    # ── UI 初始化 ──────────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        conv_bar = self._build_conv_bar()
        root.addWidget(conv_bar)

        chat_panel = self._build_chat_panel()
        root.addWidget(chat_panel, 1)

    def _build_conv_bar(self) -> QWidget:
        """构建顶部会话 Tab 栏。"""
        bar_widget = QWidget()
        bar_widget.setObjectName("agentConvBar")
        bar_widget.setFixedHeight(32)
        bar_layout = QHBoxLayout(bar_widget)
        bar_layout.setContentsMargins(4, 0, 4, 0)
        bar_layout.setSpacing(0)

        self._conv_tab_bar = _ScrollableTabBar()
        self._conv_tab_bar.setObjectName("agentConvTabBar")
        self._conv_tab_bar.setDrawBase(False)
        self._conv_tab_bar.setExpanding(False)
        self._conv_tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        self._conv_tab_bar.setTabsClosable(False)
        self._conv_tab_bar.setUsesScrollButtons(False)
        self._conv_tab_bar.tabBarClicked.connect(self._on_conv_tab_changed)
        self._conv_tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._conv_tab_bar.customContextMenuRequested.connect(self._on_conv_context_menu)
        bar_layout.addWidget(self._conv_tab_bar, 1)

        self._btn_new_conv = QPushButton(BTN_NEW_CONVERSATION)
        self._btn_new_conv.setObjectName("agentBtnNewConv")
        self._btn_new_conv.setFixedSize(28, 24)
        self._btn_new_conv.setToolTip(TOOLTIP_NEW_CONVERSATION)
        self._btn_new_conv.clicked.connect(self._on_new_conversation)
        bar_layout.addWidget(self._btn_new_conv)

        self._conv_ids: list[str] = []
        self._refreshing_tabs = False
        self._new_conv_mode = False

        return bar_widget

    def _build_chat_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部工具栏
        self._toolbar = QWidget()
        self._toolbar.setObjectName("agentToolbar")
        self._toolbar.setFixedHeight(36)
        tb_layout = QHBoxLayout(self._toolbar)
        tb_layout.setContentsMargins(12, 0, 12, 0)
        self._lbl_title = QLabel(LABEL_TITLE)
        self._lbl_title.setObjectName("agentLblTitle")
        tb_layout.addWidget(self._lbl_title)
        tb_layout.addStretch()
        layout.addWidget(self._toolbar)

        # 消息区域（QStackedWidget: 欢迎页 / 聊天页）
        self._content_stack = QStackedWidget()

        self._welcome_page = self._build_welcome_page()
        self._content_stack.addWidget(self._welcome_page)

        self._chat_page = self._build_chat_page()
        self._content_stack.addWidget(self._chat_page)

        layout.addWidget(self._content_stack, 1)

        self._context_bar = self._build_context_bar()
        layout.addWidget(self._context_bar)

        # 输入区域
        self._input_bar = QWidget()
        self._input_bar.setObjectName("agentInputBar")
        ib_layout = QHBoxLayout(self._input_bar)
        ib_layout.setContentsMargins(12, 8, 12, 8)

        self._chat_input = _ChatInput()
        ib_layout.addWidget(self._chat_input, 1)

        self._btn_send = QPushButton(BTN_SEND)
        self._btn_send.setObjectName("agentBtnSend")
        self._btn_send.setFixedSize(60, 36)
        self._btn_send.clicked.connect(self._on_send)
        self._chat_input.send_requested.connect(self._on_send)
        ib_layout.addWidget(self._btn_send)

        layout.addWidget(self._input_bar)
        return panel

    def _build_context_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("agentContextBar")
        bar.setVisible(False)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(4)

        title = QLabel(LABEL_CONTEXT_AREA)
        title.setObjectName("agentContextTitle")
        layout.addWidget(title)

        self._context_list = QListWidget()
        self._context_list.setObjectName("agentContextList")
        self._context_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._context_list.setMaximumHeight(90)
        self._context_list.setToolTip(TOOLTIP_CONTEXT_LIST)
        self._context_list.installEventFilter(self)
        self._context_list.itemSelectionChanged.connect(self._on_context_selection_changed)
        layout.addWidget(self._context_list)
        return bar

    def _build_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(2)

        center = QVBoxLayout()
        center.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._welcome_title = QLabel(WELCOME_TITLE)
        self._welcome_title.setObjectName("agentWelcomeTitle")
        self._welcome_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self._welcome_title)

        self._welcome_subtitle = QLabel(WELCOME_SUBTITLE)
        self._welcome_subtitle.setObjectName("agentWelcomeSubtitle")
        self._welcome_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self._welcome_subtitle)

        btn_grid = QVBoxLayout()
        btn_grid.setSpacing(8)
        btn_grid.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        shortcuts = [
            (WELCOME_SHORTCUT_TRACE, "帮我分析 Perfetto trace 文件中的卡顿问题"),
            (WELCOME_SHORTCUT_PERFDog, "帮我分析 PerfDog 导出的性能数据"),
            (WELCOME_SHORTCUT_POLICY, "帮我审查当前的游戏性能策略配置"),
            (WELCOME_SHORTCUT_JANK, "帮我做一次完整的游戏卡顿综合分析"),
        ]
        self._shortcut_btns: list[QPushButton] = []
        for label, prompt in shortcuts:
            btn = QPushButton(label)
            btn.setObjectName("agentShortcutBtn")
            btn.setFixedHeight(36)
            btn.setMinimumWidth(180)
            btn.setMaximumWidth(240)
            btn.clicked.connect(lambda checked, p=prompt: self._quick_send(p))
            btn_grid.addWidget(btn)
            self._shortcut_btns.append(btn)
        center.addLayout(btn_grid)

        self._welcome_hint = QLabel(WELCOME_HINT)
        self._welcome_hint.setObjectName("agentWelcomeHint")
        self._welcome_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self._welcome_hint)

        layout.addLayout(center)
        layout.addStretch(3)
        return page

    def _build_chat_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self._msg_scroll = QScrollArea()
        self._msg_scroll.setObjectName("agentMsgScroll")
        self._msg_scroll.setWidgetResizable(True)
        self._msg_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._msg_container = QWidget()
        self._msg_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(4, 8, 4, 8)
        self._msg_layout.setSpacing(2)
        self._msg_layout.addStretch()

        self._msg_scroll.setWidget(self._msg_container)
        layout.addWidget(self._msg_scroll)
        return page

    # ── Tab 生命周期 ─────────────────────────────────────────────────────

    def on_activated(self) -> None:
        if self.context:
            self._config = self.context.get("ac_config")
        self._bind_history_event()
        self._ensure_service()
        self._refresh_conv_list()
        self._refresh_skill_tree()
        self._flush_pending_history_payloads()

        has_key = False
        if self._config:
            has_key = bool(
                self._config.api_key
                or self._config.glm_api_key
                or self._config.claude_api_key
            )
        if not has_key and self._content_stack.currentIndex() == 0:
            self._show_setup_guide()

    def set_theme(self, theme: str) -> None:
        """切换主题 — 全局 QSS 自动处理大部分样式，此处只更新动态引用。"""
        c = _THEMES.get(theme, _THEMES["dark"])
        global _DARK
        _DARK = c
        self._refresh_conv_list()


    # ── 服务初始化 ────────────────────────────────────────────────────────

    def _ensure_service(self) -> None:
        """确保 AgentService 已初始化。"""
        if self._service:
            return

        if not self._config:
            return

        from .memory.conversation import ConversationStore
        from .service import AgentService
        from .skills.manager import SkillsManager
        from .sop.manager import SOPManager
        from .tools.registry import ToolRegistry

        from toolkit.core.app_paths import get_db_path, get_exe_dir

        module_dir = Path(__file__).resolve().parent.parent
        data_dir = get_exe_dir() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        self._store = ConversationStore(get_db_path("agent_chat", "conversation"))

        self._sop_manager = SOPManager(
            builtin_dir=module_dir / "assets" / "sops",
            custom_dir=data_dir / "sops",
        )
        self._sop_manager.load_all()

        # Skills 管理器（搜索本模块 + perfetto_analysis 的 skills 目录）
        skill_search_paths = [
            module_dir / "skills",
            module_dir.parent / "perfetto_analysis" / "skills",
        ]
        self._skills_manager = SkillsManager(skill_search_paths)
        self._skills_manager.scan()

        tool_registry = ToolRegistry()
        pm = self.context.get("plugin_manager") if self.context else None
        if pm:
            tool_registry.collect_from_plugins(pm)

        # 注册 Skill Agent 工具
        skill_tools = self._skills_manager.create_agent_tools()
        tool_registry.register_many(skill_tools)

        llm_manager = self.context.get("llm_manager") if self.context else None
        self._service = AgentService(
            config=self._config,
            conversation_store=self._store,
            tool_registry=tool_registry,
            sop_manager=self._sop_manager,
            skills_manager=self._skills_manager,
            llm_manager=llm_manager,
        )
        self._flush_pending_history_payloads()

    def _bind_history_event(self) -> None:
        if self._history_event_bound or not self.context:
            return
        bus = self.context.get("event_bus")
        if not bus:
            return
        bus.on(HISTORY_SEND_TO_AGENT_EVENT, self._on_history_send_to_agent)
        self._history_event_bound = True

    def _flush_pending_history_payloads(self) -> None:
        if not self._store or not self._pending_history_payloads:
            return
        payloads = list(self._pending_history_payloads)
        self._pending_history_payloads.clear()
        for payload in payloads:
            self._apply_history_payload(payload)

    def _reinit_service(self) -> None:
        """配置变更后重新初始化 service。"""
        if self._store:
            self._store.close()
        self._service = None
        self._store = None
        self._sop_manager = None
        self._skills_manager = None
        self._ensure_service()

    # ── 首次使用引导 ──────────────────────────────────────────────────────

    def _show_setup_guide(self) -> None:
        """在欢迎页显示 API Key 配置引导。"""
        pass  # 由 _on_open_settings 替代，点击设置直接弹出

    # ── 会话历史管理 (T021) ──────────────────────────────────────────────

    def _refresh_conv_list(self) -> None:
        self._refreshing_tabs = True
        try:
            while self._conv_tab_bar.count() > 0:
                self._conv_tab_bar.removeTab(0)
            self._conv_ids.clear()

            if not self._store:
                logger.debug("_refresh_conv_list: store 未初始化")
                return

            convs = self._store.list_conversations()
            active_idx = -1
            logger.debug("_refresh_conv_list: %d 个会话, current=%s", len(convs), self._current_conv_id)

            for c in convs:
                title = c.get("title") or CONVERSATION_NEW
                if len(title) > 16:
                    title = title[:16] + "…"
                idx = self._conv_tab_bar.addTab(title)
                self._conv_tab_bar.setTabToolTip(idx, c.get("title") or CONVERSATION_NEW)
                self._conv_ids.append(c["id"])
                self._add_tab_close_btn(idx)
                if c["id"] == self._current_conv_id:
                    active_idx = idx

            if active_idx >= 0 and not self._new_conv_mode:
                self._conv_tab_bar.setCurrentIndex(active_idx)
            else:
                new_idx = self._conv_tab_bar.insertTab(0, CONVERSATION_NEW_TAB)
                self._conv_ids.insert(0, "__new__")
                self._add_tab_close_btn(0)
                self._conv_tab_bar.setCurrentIndex(0)
                self._new_conv_mode = True
            logger.debug("_refresh_conv_list: active_idx=%d, tab_count=%d", active_idx, self._conv_tab_bar.count())
        finally:
            self._refreshing_tabs = False

    def _add_tab_close_btn(self, tab_idx: int) -> None:
        """为指定 Tab 添加自定义 Codicon 关闭按钮。"""
        btn = QPushButton()
        btn.setFixedSize(16, 16)
        cf = codicon_font(10)
        if cf:
            btn.setFont(cf)
            btn.setText(icon_char("close"))
        else:
            btn.setText("×")
        hover_bg = _DARK.get("hover", "rgba(255,255,255,0.1)")
        fg = _DARK.get("fg", "#cdd6f4")
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; padding: 0; margin: 0; color: {fg}; }}"
            f"QPushButton:hover {{ background-color: {hover_bg}; border-radius: 3px; }}"
        )

        def _find_and_close():
            for i in range(self._conv_tab_bar.count()):
                if self._conv_tab_bar.tabButton(i, QTabBar.ButtonPosition.RightSide) is btn:
                    self._on_conv_tab_close(i)
                    return

        btn.clicked.connect(_find_and_close)
        self._conv_tab_bar.setTabButton(
            tab_idx, QTabBar.ButtonPosition.RightSide, btn
        )

    def _on_conv_tab_changed(self, index: int) -> None:
        """用户点击 Tab 时加载对应会话。"""
        logger.debug("_on_conv_tab_changed: index=%d", index)
        if index < 0 or index >= len(self._conv_ids):
            return

        conv_id = self._conv_ids[index]
        if conv_id == "__new__":
            self._new_conv_mode = True
            self._current_conv_id = None
            self._clear_messages()
            self._content_stack.setCurrentIndex(0)
            self._refresh_context_ui()
            return
        if conv_id == self._current_conv_id:
            return

        if self._is_running:
            ok = confirm_dialog(
                self, DLG_TITLE_SWITCH_CONVERSATION,
                MSG_SWITCH_STOP_TASK,
            )
            if not ok:
                old_idx = self._conv_ids.index(self._current_conv_id) if self._current_conv_id in self._conv_ids else -1
                if old_idx >= 0:
                    self._conv_tab_bar.setCurrentIndex(old_idx)
                return
            self._on_stop()

        self._new_conv_mode = False
        self._current_conv_id = conv_id
        self._load_conversation_messages(conv_id)
        self._refresh_context_ui()

    def _on_conv_tab_close(self, index: int) -> None:
        """Tab 关闭按钮 — 删除会话。"""
        if index < 0 or index >= len(self._conv_ids):
            return
        conv_id = self._conv_ids[index]
        if conv_id == "__new__":
            self._new_conv_mode = False
            self._refresh_conv_list()
            return
        ok = confirm_dialog(
            self, DLG_TITLE_DELETE_CONVERSATION, MSG_CONFIRM_DELETE_CONVERSATION,
            confirm_text=BTN_DELETE, danger=True,
        )
        if ok and self._store:
            self._store.delete_conversation(conv_id)
            self._conv_contexts.pop(conv_id, None)
            if self._current_conv_id == conv_id:
                self._current_conv_id = None
                self._clear_messages()
                self._content_stack.setCurrentIndex(0)
                self._refresh_context_ui()
            self._refresh_conv_list()

    def _on_conv_context_menu(self, pos) -> None:
        index = self._conv_tab_bar.tabAt(pos)
        if index < 0 or index >= len(self._conv_ids):
            return
        conv_id = self._conv_ids[index]

        menu = QMenu(self)
        action_rename = menu.addAction(BTN_RENAME)
        action_delete = menu.addAction(BTN_DELETE)

        action = menu.exec(self._conv_tab_bar.mapToGlobal(pos))
        if action == action_rename:
            new_name, ok = input_dialog(self, DLG_TITLE_RENAME_CONVERSATION, MSG_RENAME_PLACEHOLDER)
            if ok and new_name.strip() and self._store:
                self._store.rename_conversation(conv_id, new_name.strip())
                self._refresh_conv_list()
        elif action == action_delete:
            ok = confirm_dialog(
                self, DLG_TITLE_DELETE_CONVERSATION, MSG_CONFIRM_DELETE_CONVERSATION,
                confirm_text=BTN_DELETE, danger=True,
            )
            if ok and self._store:
                self._store.delete_conversation(conv_id)
                self._conv_contexts.pop(conv_id, None)
                if self._current_conv_id == conv_id:
                    self._current_conv_id = None
                    self._clear_messages()
                    self._content_stack.setCurrentIndex(0)
                    self._refresh_context_ui()
                self._refresh_conv_list()

    def _on_new_conversation(self) -> None:
        logger.debug("_on_new_conversation")
        self._new_conv_mode = True
        if self._is_running:
            ok = confirm_dialog(
                self, DLG_TITLE_NEW_CONVERSATION,
                MSG_NEW_CONV_STOP_TASK,
            )
            if not ok:
                return
            self._on_stop()

        self._current_conv_id = None
        self._draft_contexts = []
        self._clear_messages()
        self._content_stack.setCurrentIndex(0)
        self._refresh_context_ui()
        self._refresh_conv_list()

    def _load_conversation_messages(self, conv_id: str) -> None:
        """加载历史对话消息到聊天区。"""
        self._clear_messages()
        self._content_stack.setCurrentIndex(1)

        if not self._store:
            return

        from .models import MessageRole

        messages = self._store.load_messages(conv_id)
        for msg in messages:
            if msg.role == MessageRole.USER:
                self._add_user_bubble(msg.content)
            elif msg.role == MessageRole.ASSISTANT:
                widget = _AgentTextWidget()
                widget.set_full_text(msg.content)
                self._insert_message_widget(widget)
                if msg.tool_calls:
                    from .models import ToolCallStatus
                    for tc in msg.tool_calls:
                        card = _ToolCallCard(tc.name, tc.arguments)
                        if tc.status == ToolCallStatus.COMPLETE:
                            card.set_complete(tc.elapsed_ms)
                        elif tc.status == ToolCallStatus.FAILED:
                            card.set_failed()
                        elif tc.status == ToolCallStatus.RUNNING:
                            card.set_cancelled()
                        self._insert_message_widget(card)
                if msg.token_usage:
                    self._insert_message_widget(_TokenUsageLabel(msg.token_usage))
            elif msg.role == MessageRole.TOOL:
                if msg.report_paths:
                    for rp in msg.report_paths:
                        if self._current_tool_cards:
                            last_card = list(self._current_tool_cards.values())[-1]
                            last_card.add_report_button(rp)

        self._scroll_to_bottom()

    # ── 知识管理 (Skills) ──────────────────────────────────────────────

    def _refresh_skill_tree(self) -> None:
        if not hasattr(self, "_skill_tree"):
            return
        self._skill_tree.clear()
        if not self._skills_manager:
            return

        all_meta = self._skills_manager.get_all_metadata()
        if not all_meta:
            QTreeWidgetItem(self._skill_tree, [SOP_NO_SKILLS])
            return

        for meta in all_meta:
            root = QTreeWidgetItem(self._skill_tree, [f"📦 {meta.name}"])
            root.setData(0, Qt.ItemDataRole.UserRole, meta.name)
            desc_item = QTreeWidgetItem(root, [f"  {meta.description[:40]}"])
            desc_item.setDisabled(True)

            resources = self._skills_manager.list_resources(meta.name)
            for category, files in resources.items():
                cat_item = QTreeWidgetItem(root, [f"  📁 {category} ({len(files)})"])
                for f in files:
                    QTreeWidgetItem(cat_item, [f"    📄 {f}"])

            root.setExpanded(True)

    # ── 设置 (T023) ──────────────────────────────────────────────────────

    def _on_open_settings(self) -> None:
        if not self._config:
            return
        dlg = _SettingsDialog(
            self._config,
            sop_manager=self._sop_manager,
            mcp_manager=self._mcp_manager,
            parent=self,
        )
        dlg.config_changed.connect(self._on_config_changed)
        dlg.exec()

    def _on_config_changed(self, new_config: Any) -> None:
        self._config = new_config
        if self.context:
            self.context["ac_config"] = new_config
        self._reinit_service()
        self._refresh_skill_tree()

    # ── 消息发送与接收 (T020) ─────────────────────────────────────────────

    def _quick_send(self, prompt: str) -> None:
        self._chat_input.setPlainText(prompt)
        self._on_send()

    def _on_send(self) -> None:
        text = self._chat_input.toPlainText().strip()
        if not text:
            return

        if self._is_running:
            return

        self._ensure_service()
        if not self._service:
            warning_dialog(self, DLG_TITLE_AGENT_NOT_READY, MSG_AGENT_NOT_READY_NO_KEY)
            return

        if not self._service.is_ready:
            warning_dialog(self, DLG_TITLE_AGENT_NOT_READY, MSG_AGENT_NOT_READY_INVALID_KEY)
            return

        self._new_conv_mode = False
        self._content_stack.setCurrentIndex(1)
        self._chat_input.clear()

        self._add_user_bubble(text)
        self._current_agent_widget = _AgentTextWidget()
        self._insert_message_widget(self._current_agent_widget)
        self._current_tool_cards.clear()
        self._last_usage = {}

        self._set_running(True)

        message_with_context = self._compose_message_with_context(text)
        self._worker = _AgentWorker(
            service=self._service,
            message=message_with_context,
            conversation_id=self._current_conv_id,
            parent=self,
        )
        self._worker.text_chunk.connect(self._on_text_chunk)
        self._worker.tool_start.connect(self._on_tool_start)
        self._worker.tool_end.connect(self._on_tool_end)
        self._worker.usage_received.connect(self._on_usage)
        self._worker.workflow_deposit.connect(self._on_workflow_deposit)
        self._worker.thinking.connect(self._on_thinking)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.start()

    def _on_stop(self) -> None:
        if self._worker:
            self._worker.cancel()
        self._set_running(False)
        for card in self._current_tool_cards.values():
            card.set_cancelled()
        self._insert_message_widget(
            _SystemNotice(MSG_STOPPED_HINT)
        )
        self._scroll_to_bottom()

    def _on_thinking(self, hint: str) -> None:
        """显示思考状态提示 — 当 LLM 等待响应时给用户反馈。"""
        try:
            w = self._current_agent_widget
            if w is not None:
                w.set_thinking(hint)
            self._scroll_to_bottom()
        except RuntimeError:
            pass

    def _on_text_chunk(self, text: str) -> None:
        w = self._current_agent_widget
        if w is not None:
            try:
                w.clear_thinking()
                w.append_text(text)
            except RuntimeError:
                self._current_agent_widget = None
                return
        self._scroll_to_bottom()

    def _on_tool_start(self, data: dict) -> None:
        tool_name = data.get("name", "unknown")
        args = data.get("arguments", {})
        if isinstance(args, str):
            import json as _json
            try:
                args = _json.loads(args)
            except (ValueError, TypeError):
                args = {}
        try:
            if self._current_agent_widget:
                self._current_agent_widget.clear_thinking()

            card = _ToolCallCard(tool_name, args)
            tool_id = data.get("id", tool_name)
            self._current_tool_cards[tool_id] = card
            self._insert_message_widget(card)
            self._scroll_to_bottom()

            self._current_agent_widget = _AgentTextWidget()
            self._insert_message_widget(self._current_agent_widget)
        except RuntimeError:
            logger.warning(LOG_ON_TOOL_START_DESTROYED)

    def _on_tool_end(self, data: dict) -> None:
        tool_id = data.get("id", data.get("name", ""))
        card = self._current_tool_cards.get(tool_id)
        if not card:
            return
        try:
            is_error = data.get("is_error", False)
            elapsed_ms = data.get("elapsed_ms", 0)
            content_preview = data.get("content_preview", "")
            if is_error:
                card.set_failed(content_preview)
            else:
                card.set_complete(elapsed_ms, content_preview)
        except RuntimeError:
            logger.warning(LOG_ON_TOOL_END_DESTROYED)

    def _on_usage(self, usage: dict) -> None:
        self._last_usage = usage

    def _on_finished(self, full_text: str, conv_id: str) -> None:
        logger.debug("[DIAG] _on_finished: 开始处理")
        try:
            self._set_running(False)
            if conv_id:
                self._current_conv_id = conv_id
                if self._draft_contexts:
                    self._conv_contexts.setdefault(conv_id, [])
                    existing = {str(it.get("file_path")) for it in self._conv_contexts[conv_id]}
                    for item in self._draft_contexts:
                        p = str(item.get("file_path") or "")
                        if p and p not in existing:
                            self._conv_contexts[conv_id].append(item)
                            existing.add(p)
                    self._draft_contexts = []
                    self._refresh_context_ui()

            if self._last_usage:
                self._insert_message_widget(_TokenUsageLabel(self._last_usage))

            self._refresh_conv_list()
            self._scroll_to_bottom()

            if not self._current_conv_id and self._store:
                convs = self._store.list_conversations()
                if convs:
                    self._current_conv_id = convs[0]["id"]
                    first_msg = full_text[:20] if full_text else CONVERSATION_NEW
                    self._store.rename_conversation(self._current_conv_id, first_msg)
                    self._refresh_conv_list()
        except RuntimeError:
            logger.warning(LOG_ON_FINISHED_DESTROYED)

    def _on_error(self, msg: str) -> None:
        try:
            self._set_running(False)
            err_label = _SystemNotice(MSG_ERROR_FMT.format(msg))
            err_label.setStyleSheet(f"color: {_DARK['error']}; font-size: 12px; padding: 8px;")
            self._insert_message_widget(err_label)
            self._scroll_to_bottom()
        except RuntimeError:
            logger.warning(LOG_ON_ERROR_DESTROYED)

    def _on_workflow_deposit(self, summary: dict) -> None:
        """工作流满足沉淀条件时显示沉淀卡片。"""
        card = _WorkflowDepositCard(summary, parent=self)
        card.save_new.connect(self._on_deposit_save_new)
        card.skipped.connect(lambda: logger.debug(LOG_SKIP_WORKFLOW_DEPOSIT))
        self._insert_message_widget(card)
        self._scroll_to_bottom()

    def _on_deposit_save_new(self, summary: dict) -> None:
        """保存工作流为新 SOP。"""
        from .workflow.generator import generate_sop_from_trace, open_sop_file, save_sop

        content = generate_sop_from_trace(summary)

        if not self._sop_manager:
            return

        from toolkit.core.app_paths import get_exe_dir

        save_dir = get_exe_dir() / "data" / "sops"
        saved_path = save_sop(content, save_dir)

        if self._sop_manager:
            self._sop_manager.load_all()
        self._refresh_skill_tree()

        ok = confirm_dialog(
            self, DLG_TITLE_SOP_SAVED,
            MSG_SOP_SAVED_FMT.format(saved_path),
            confirm_text=BTN_OPEN,
        )
        if ok:
            open_sop_file(saved_path)

    # ── UI 辅助方法 ──────────────────────────────────────────────────────

    def _add_user_bubble(self, text: str) -> None:
        widget = _UserMessageWidget(text)
        self._insert_message_widget(widget)

    def _insert_message_widget(self, widget: QWidget) -> None:
        count = self._msg_layout.count()
        self._msg_layout.insertWidget(count - 1, widget)

    def _clear_messages(self) -> None:
        while self._msg_layout.count() > 1:
            item = self._msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._current_agent_widget = None
        self._current_tool_cards.clear()

    def _on_history_send_to_agent(self, **payload: Any) -> None:
        """接收历史模块发送的文件上下文。"""
        data = self._parse_history_payload(payload)
        if not data["file_path"] or not data["file_name"] or not data["context_type"]:
            return
        if not self._store:
            self._pending_history_payloads.append(data)
            return
        self._apply_history_payload(data)

    def _parse_history_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """统一解析 history.send_to_agent payload。"""
        return {
            "file_path": str(payload.get("file_path") or "").strip(),
            "file_name": str(payload.get("file_name") or "").strip(),
            "context_type": str(payload.get("context_type") or "").strip(),
            "missing": bool(payload.get("missing", False)),
        }

    def _apply_history_payload(self, data: dict[str, Any]) -> None:
        """将历史 payload 写入当前会话上下文。"""
        show_right = self.context.get("show_right_panel") if self.context else None
        if callable(show_right):
            show_right()

        if self._current_conv_id is None and self._new_conv_mode:
            exists = {str(it.get("file_path")) for it in self._draft_contexts}
            if data["file_path"] not in exists:
                data["context_id"] = f"ctx_draft_{len(self._draft_contexts)+1}_{int(time.time()*1000)}"
                self._draft_contexts.append(data)
            self._refresh_context_ui()
            self._chat_input.setFocus()
            return
        if not self._current_conv_id:
            return

        items = self._conv_contexts.setdefault(self._current_conv_id, [])
        existing = {str(it.get("file_path")): it for it in items}
        if data["file_path"] not in existing:
            data["context_id"] = f"ctx_{len(items)+1}_{int(time.time()*1000)}"
            items.append(data)
        self._refresh_context_ui()
        self._chat_input.setFocus()

    def _refresh_context_ui(self) -> None:
        """刷新当前会话上下文区域。"""
        self._context_list.clear()
        if not self._current_conv_id:
            contexts = self._draft_contexts if self._new_conv_mode else []
        else:
            contexts = self._conv_contexts.get(self._current_conv_id, [])
        if not contexts:
            self._context_bar.setVisible(False)
            return
        for ctx in contexts:
            suffix = CONTEXT_FILE_MISSING if ctx.get("missing") else ""
            text = f"{ctx.get('file_name')} — {ctx.get('file_path')}{suffix}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, ctx.get("file_path"))
            self._context_list.addItem(item)
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            lbl = QLabel(text)
            lbl.setObjectName("agentContextItemLabel")
            lbl.setWordWrap(False)
            row_layout.addWidget(lbl, 1)
            btn = QPushButton("×")
            btn.setObjectName("agentContextRemoveBtn")
            btn.setFixedSize(18, 18)
            btn.clicked.connect(lambda checked=False, p=str(ctx.get("file_path") or ""): self._remove_context_by_path(p))
            row_layout.addWidget(btn)
            self._context_list.setItemWidget(item, row)
        self._context_bar.setVisible(True)

    def _on_context_selection_changed(self) -> None:
        self._context_list.setFocus()

    def _remove_selected_context(self) -> None:
        item = self._context_list.currentItem()
        if not item:
            return
        path = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not path:
            return
        self._remove_context_by_path(path)

    def _remove_context_by_path(self, path: str) -> None:
        if not path:
            return
        if self._current_conv_id:
            items = self._conv_contexts.get(self._current_conv_id, [])
            self._conv_contexts[self._current_conv_id] = [
                it for it in items if str(it.get("file_path")) != path
            ]
        elif self._new_conv_mode:
            self._draft_contexts = [
                it for it in self._draft_contexts if str(it.get("file_path")) != path
            ]
        self._refresh_context_ui()

    def _compose_message_with_context(self, text: str) -> str:
        contexts = (
            self._conv_contexts.get(self._current_conv_id, [])
            if self._current_conv_id
            else (self._draft_contexts if self._new_conv_mode else [])
        )
        return compose_message_with_context(text, contexts)

    def _scroll_to_bottom(self) -> None:
        if self._scroll_pending:
            return
        self._scroll_pending = True
        QTimer.singleShot(80, self._do_scroll)

    def _do_scroll(self) -> None:
        self._scroll_pending = False
        try:
            sb = self._msg_scroll.verticalScrollBar()
            sb.setValue(sb.maximum())
        except RuntimeError:
            pass

    def _set_running(self, running: bool) -> None:
        self._is_running = running
        self._chat_input.setEnabled(not running)
        if running:
            self._btn_send.setText(BTN_STOP)
            self._btn_send.setStyleSheet(
                f"background-color: {_DARK['btn_stop_bg']};"
                "color: #1e1e2e;"
                "border-radius: 8px;"
                "font-weight: bold;"
            )
            self._btn_send.clicked.disconnect()
            self._btn_send.clicked.connect(self._on_stop)
        else:
            self._btn_send.setText(BTN_SEND)
            self._btn_send.setStyleSheet(
                f"background-color: {_DARK['btn_send_bg']};"
                "color: #1e1e2e;"
                "border-radius: 8px;"
                "font-weight: bold;"
            )
            self._btn_send.clicked.disconnect()
            self._btn_send.clicked.connect(self._on_send)

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is getattr(self, "_context_list", None) and hasattr(event, "key"):
            if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                self._remove_selected_context()
                return True
        return super().eventFilter(obj, event)

    def _cleanup_worker(self) -> None:
        """QThread.finished 信号回调 — 线程已完全退出后安全清理。"""
        logger.debug("[DIAG] _cleanup_worker: 开始")
        worker = self._worker
        if worker is None:
            logger.debug("[DIAG] _cleanup_worker: worker 已为 None")
            return
        self._worker = None
        logger.debug("[DIAG] _cleanup_worker: 调用 wait()")
        worker.wait(2000)
        logger.debug("[DIAG] _cleanup_worker: wait() 完成, 调用 deleteLater()")
        worker.deleteLater()
        logger.debug("[DIAG] _cleanup_worker: 完成")

    def closeEvent(self, event) -> None:
        if self.context:
            bus = self.context.get("event_bus")
            if bus and self._history_event_bound:
                bus.off(HISTORY_SEND_TO_AGENT_EVENT, self._on_history_send_to_agent)
                self._history_event_bound = False
        worker = self._worker
        if worker is not None:
            worker.cancel()
            worker.wait(5000)
            self._worker = None
        if self._store:
            self._store.close()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _open_path(path: str) -> None:
    """跨平台打开文件/目录。"""
    p = Path(path)
    if not p.exists():
        logger.warning("路径不存在: %s", path)
        return
    try:
        if platform.system() == "Windows":
            os.startfile(str(p))  # noqa: S606
        elif platform.system() == "Darwin":
            os.system(f'open "{p}"')  # noqa: S605
        else:
            os.system(f'xdg-open "{p}"')  # noqa: S605
    except Exception as exc:
        logger.error(LOG_OPEN_PATH_FAILED_FMT, path, exc)
