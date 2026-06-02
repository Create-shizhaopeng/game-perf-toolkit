# -*- coding: utf-8 -*-
"""AgentPanel — 右侧 Agent 对话面板（含完整聊天+历史上下文功能）。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from toolkit.gui.codicons import icon_char
from toolkit.gui.theme_colors import get_colors

logger = logging.getLogger(__name__)

HISTORY_SEND_EVENT = "history.send_to_agent"


# ── Message widgets ────────────────────────────────────────────────────

class _UserBubble(QFrame):
    def __init__(self, text: str, colors: dict, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(30, 4, 8, 4)
        layout.addStretch()
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setStyleSheet(
            f"background-color: {colors.get('user_bubble','#45475a')};"
            "border-radius: 10px; padding: 10px 14px;"
            f"color: {colors.get('fg','#cdd6f4')};"
        )
        layout.addWidget(lbl)


class _AgentBubble(QFrame):
    def __init__(self, colors: dict, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 30, 4)
        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self._label.setStyleSheet(f"padding: 8px 12px; color: {colors.get('fg','#cdd6f4')};")
        self._text: list[str] = []
        layout.addWidget(self._label, 1)
        layout.addStretch()

    def append(self, text: str):
        self._text.append(text)
        self._label.setText("".join(self._text))


class _SystemNotice(QLabel):
    def __init__(self, text: str, colors: dict, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"color: {colors.get('fg_dim','#6c7086')}; font-size: 11px; padding: 6px;")


# ── Worker thread ──────────────────────────────────────────────────────

class _AgentWorker(QThread):
    text_chunk = pyqtSignal(str)
    tool_start = pyqtSignal(dict)
    tool_end = pyqtSignal(dict)
    thinking = pyqtSignal(str)
    finished_ok = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, service, message: str, conv_id: str | None = None, parent=None):
        super().__init__(parent)
        self._service = service
        self._message = message
        self._conv_id = conv_id

    def run(self):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run())
        finally:
            loop.close()

    async def _run(self):
        from toolkit.agent.models import StreamChunkType
        try:
            resp = await self._service.chat(
                user_message=self._message,
                conversation_id=self._conv_id,
                on_chunk=self._on_chunk,
            )
            self.finished_ok.emit(resp.text, self._conv_id or "")
        except Exception as e:
            self.error.emit(str(e))

    def _on_chunk(self, chunk):
        from toolkit.agent.models import StreamChunkType
        try:
            if chunk.type == StreamChunkType.TEXT:
                self.text_chunk.emit(str(chunk.data))
            elif chunk.type == StreamChunkType.TOOL_START:
                self.tool_start.emit(chunk.data if isinstance(chunk.data, dict) else {})
            elif chunk.type == StreamChunkType.TOOL_END:
                self.tool_end.emit(chunk.data if isinstance(chunk.data, dict) else {})
            elif chunk.type == StreamChunkType.THINKING:
                self.thinking.emit(str(chunk.data))
            elif chunk.type == StreamChunkType.ERROR:
                self.error.emit(str(chunk.data))
        except RuntimeError:
            pass

    def cancel(self):
        if self._service:
            self._service.cancel()


# ── Input ──────────────────────────────────────────────────────────────

class _ChatInput(QTextEdit):
    send_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("agentPanelInput")
        self.setPlaceholderText("输入消息... (Enter 发送, Shift+Enter 换行)")
        self.setFixedHeight(36)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.send_requested.emit()
            return
        super().keyPressEvent(event)


# ── AgentPanel ─────────────────────────────────────────────────────────

class AgentPanel(QWidget):
    """Agent 右侧可展开面板。"""

    panel_expanded = pyqtSignal()
    panel_collapsed = pyqtSignal()
    message_sent = pyqtSignal(str)

    def __init__(self, orchestrator=None, parent=None):
        super().__init__(parent)
        self.setObjectName("agentPanel")
        self._orch = orchestrator
        self._theme = "dark"
        self._colors = get_colors(self._theme)
        self._collapsed = True
        self._expanded_width = 360
        self._service = None
        self._store = None
        self._worker = None
        self._current_agent_bubble = None
        self._conv_id = None
        self._history_bound = False
        self._pending_contexts: list[dict] = []
        self._conv_contexts: dict[str, list[dict]] = {}
        self._draft_contexts: list[dict] = []
        self._is_running = False

        self._init_ui()
        # event_bus is wired externally via set_event_bus() after construction

    # ── UI ─────────────────────────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Collapsed bar
        self._collapsed_bar = QWidget()
        cl = QVBoxLayout(self._collapsed_bar)
        cl.setContentsMargins(0, 8, 0, 8)
        btn = QPushButton(icon_char("robot") or "A")
        btn.setObjectName("agentPanelToggleBtn")
        btn.setFixedSize(24, 24)
        btn.clicked.connect(self._expand)
        cl.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
        cl.addStretch()
        root.addWidget(self._collapsed_bar)

        # Expanded widget
        self._expanded = QWidget()
        self._expanded.setVisible(False)
        el = QVBoxLayout(self._expanded)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setObjectName("agentPanelHeader")
        hdr.setFixedHeight(36)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 8, 0)
        hl.addWidget(QLabel("Agent 智能助手"))
        hl.addStretch()
        cb = QPushButton(icon_char("close") or "×")
        cb.setFixedSize(24, 24)
        cb.clicked.connect(self._collapse)
        hl.addWidget(cb)
        el.addWidget(hdr)

        # Session selector
        self._session_bar = QWidget()
        self._session_bar.setObjectName("agentPanelSessionBar")
        sl = QHBoxLayout(self._session_bar)
        sl.setContentsMargins(8, 4, 8, 4)
        sl.setSpacing(4)
        self._session_combo = QComboBox()
        self._session_combo.setObjectName("agentPanelSessionCombo")
        self._session_combo.setToolTip("选择历史会话")
        self._session_combo.currentIndexChanged.connect(self._on_session_changed)
        sl.addWidget(self._session_combo, 1)
        new_btn = QPushButton(icon_char("add") or "+")
        new_btn.setObjectName("agentPanelNewSessionBtn")
        new_btn.setFixedSize(28, 28)
        new_btn.setToolTip("新建会话")
        new_btn.clicked.connect(self._on_new_session)
        sl.addWidget(new_btn)
        el.addWidget(self._session_bar)

        # Context bar
        self._context_bar = QWidget()
        self._context_bar.setVisible(False)
        cbl = QVBoxLayout(self._context_bar)
        cbl.setContentsMargins(12, 4, 12, 4)
        cbl.addWidget(QLabel("已引用的文件:"))
        self._context_list = QListWidget()
        self._context_list.setMaximumHeight(72)
        cbl.addWidget(self._context_list)
        el.addWidget(self._context_bar)

        # Messages
        self._msg_scroll = QScrollArea()
        self._msg_scroll.setObjectName("agentPanelMsgScroll")
        self._msg_scroll.setWidgetResizable(True)
        self._msg_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._msg_container = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(4, 8, 4, 8)
        self._msg_layout.setSpacing(2)
        self._msg_layout.addStretch()
        self._msg_scroll.setWidget(self._msg_container)
        el.addWidget(self._msg_scroll, 1)

        # Input
        ib = QWidget()
        ib.setObjectName("agentPanelInputBar")
        il = QHBoxLayout(ib)
        il.setContentsMargins(8, 6, 8, 6)
        self._input = _ChatInput()
        il.addWidget(self._input, 1)
        self._send_btn = QPushButton("发送")
        self._send_btn.setObjectName("agentPanelSendBtn")
        self._send_btn.setFixedSize(56, 32)
        self._send_btn.clicked.connect(self._on_send)
        self._input.send_requested.connect(self._on_send)
        il.addWidget(self._send_btn)
        el.addWidget(ib)

        root.addWidget(self._expanded, 1)

    # ── Expand / Collapse ──────────────────────────────────────────────

    def _expand(self):
        self._collapsed = False
        self._collapsed_bar.setVisible(False)
        self._expanded.setVisible(True)
        self.setMinimumWidth(240)
        self.setMaximumWidth(16777215)  # QWIDGETSIZE_MAX — allow parent resize
        self._ensure_service()
        self._flush_pending()
        self.panel_expanded.emit()

    def _collapse(self):
        self._collapsed = True
        self._expanded.setVisible(False)
        self._collapsed_bar.setVisible(True)
        self.setMinimumWidth(30)
        self.setMaximumWidth(30)
        self.panel_collapsed.emit()

    # ── Service ────────────────────────────────────────────────────────

    def _ensure_service(self):
        if self._service:
            return
        if not self._orch:
            return
        from toolkit.core.app_paths import get_db_path
        from toolkit.agent.memory.conversation import ConversationStore

        self._store = ConversationStore(get_db_path("agent_chat", "conversation"))
        self._service = self._orch.create_service(conversation_store=self._store)
        self._refresh_sessions()
        self._flush_pending()

    # ── Session management ───────────────────────────────────────────────

    def _refresh_sessions(self):
        """从 ConversationStore 加载历史会话列表到下拉框。"""
        self._session_combo.blockSignals(True)
        self._session_combo.clear()
        current_items = set()
        if self._store:
            try:
                sessions = self._store.list_conversations()
                for s in sessions:
                    title = s.get("title") or s.get("id", "?")[:20]
                    display = f"{title} ({s.get('id','')[:8]}...)"
                    self._session_combo.addItem(display, s.get("id"))
                    current_items.add(s.get("id"))
            except Exception:
                logger.debug("加载会话列表失败", exc_info=True)
        # Always have a "新建会话" placeholder
        self._session_combo.insertItem(0, "— 新建会话 —", "")
        self._session_combo.setCurrentIndex(0)
        self._session_combo.blockSignals(False)

    def _on_session_changed(self, index: int):
        """切换到选中的历史会话。"""
        if index <= 0:
            return  # placeholder
        conv_id = self._session_combo.currentData()
        if not conv_id or conv_id == self._conv_id:
            return
        self._switch_to_session(conv_id)

    def _switch_to_session(self, conv_id: str):
        """切换会话：保存当前上下文 → 加载目标会话。"""
        if conv_id == self._conv_id:
            return
        # Save pending contexts to current conversation
        if self._conv_id and self._draft_contexts:
            self._conv_contexts.setdefault(self._conv_id, []).extend(self._draft_contexts)
            self._draft_contexts.clear()
        self._conv_id = conv_id
        self._clear_messages()
        self._refresh_context_ui()
        # Load past messages if service is ready
        if self._store:
            try:
                past = self._store.load_messages(conv_id)
                for msg in past:
                    if msg.role.value == "user":
                        self._add_user_bubble(msg.content)
                    elif msg.role.value == "assistant":
                        bubble = _AgentBubble(self._colors)
                        bubble.append(msg.content)
                        self._insert_widget(bubble)
            except Exception:
                logger.debug("加载历史消息失败", exc_info=True)

    def _on_new_session(self):
        """创建新会话。"""
        if self._draft_contexts and self._conv_id:
            self._conv_contexts.setdefault(self._conv_id, []).extend(self._draft_contexts)
        self._draft_contexts.clear()
        self._conv_id = None
        self._clear_messages()
        self._refresh_context_ui()
        self._session_combo.setCurrentIndex(0)

    def _clear_messages(self):
        """清空消息区域（保留 stretch）。"""
        while self._msg_layout.count() > 1:
            item = self._msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._current_agent_bubble = None

    def set_event_bus(self, bus):
        """Connect to EventBus for history.send_to_agent events."""
        if bus is None or self._history_bound:
            return
        bus.on(HISTORY_SEND_EVENT, self._on_history_event)
        self._history_bound = True

    def _on_history_event(self, **payload):
        """Handle history.send_to_agent event from history panels."""
        data = {
            "file_path": str(payload.get("file_path", "")).strip(),
            "file_name": str(payload.get("file_name", "")).strip(),
            "context_type": str(payload.get("context_type", "")).strip(),
            "missing": bool(payload.get("missing", False)),
        }
        if not data["file_path"] or not data["file_name"]:
            return
        if not self._store:
            self._pending_contexts.append(data)
            return
        self._apply_context(data)

    def _apply_context(self, data: dict):
        if self._conv_id:
            items = self._conv_contexts.setdefault(self._conv_id, [])
            exists = {str(i.get("file_path")) for i in items}
            if data["file_path"] not in exists:
                items.append(data)
        else:
            exists = {str(i.get("file_path")) for i in self._draft_contexts}
            if data["file_path"] not in exists:
                self._draft_contexts.append(data)
        self._refresh_context_ui()

    def _flush_pending(self):
        if not self._store or not self._pending_contexts:
            return
        items = list(self._pending_contexts)
        self._pending_contexts.clear()
        for d in items:
            self._apply_context(d)

    def _refresh_context_ui(self):
        self._context_list.clear()
        contexts = self._conv_contexts.get(self._conv_id, []) if self._conv_id else self._draft_contexts
        if not contexts:
            self._context_bar.setVisible(False)
            return
        for ctx in contexts:
            suffix = " (缺失)" if ctx.get("missing") else ""
            text = f"{ctx.get('file_name','')} — {ctx.get('file_path','')}{suffix}"
            self._context_list.addItem(QListWidgetItem(text))
        self._context_bar.setVisible(True)

    # ── Send / Receive ─────────────────────────────────────────────────

    def _on_send(self):
        text = self._input.toPlainText().strip()
        if not text or self._is_running:
            return
        self._ensure_service()
        if not self._service or not self._service.is_ready:
            self._add_notice("Agent 未就绪 — 请检查 LLM Provider 配置")
            return
        self._input.clear()
        self._is_running = True
        self._send_btn.setText("停止")
        self._send_btn.clicked.disconnect()
        self._send_btn.clicked.connect(self._on_stop)

        # Build message with context
        contexts = self._conv_contexts.get(self._conv_id, []) if self._conv_id else self._draft_contexts
        msg = text
        if contexts:
            paths = []
            seen = set()
            for c in contexts:
                p = str(c.get("file_path", ""))
                if p and p not in seen:
                    seen.add(p)
                    paths.append(p)
            if paths:
                msg = text + "\n\n已引用的上下文文件:\n" + "\n".join(f"- {p}" for p in paths)

        self._add_user_bubble(text)
        self._current_agent_bubble = _AgentBubble(self._colors)
        self._insert_widget(self._current_agent_bubble)

        self._status_notice = _SystemNotice("思考中...", self._colors)
        self._insert_widget(self._status_notice)

        self._worker = _AgentWorker(self._service, msg, self._conv_id, self)
        self._worker.text_chunk.connect(self._on_text)
        self._worker.tool_start.connect(self._on_tool_start)
        self._worker.tool_end.connect(self._on_tool_end)
        self._worker.thinking.connect(self._on_status)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.start()

    def _on_stop(self):
        if self._worker:
            self._worker.cancel()
        self._set_idle()

    def _on_text(self, text: str):
        if self._current_agent_bubble:
            self._current_agent_bubble.append(text)
        if self._status_notice:
            self._status_notice.setText("")
        self._scroll_bottom()

    def _on_status(self, msg: str):
        if self._status_notice:
            self._status_notice.setText(msg)

    def _on_tool_start(self, data: dict):
        name = data.get("name", "tool")
        if self._status_notice:
            self._status_notice.setText(f"执行中: {name}...")

    def _on_tool_end(self, data: dict):
        name = data.get("name", "tool")
        elapsed = data.get("elapsed_ms", 0)
        is_err = data.get("is_error", False)
        remaining = data.get("remaining", "?")
        if is_err:
            msg = f"工具失败: {name} (剩余 {remaining} 轮)"
        else:
            msg = f"工具完成: {name} ({elapsed:.0f}ms, 剩余 {remaining} 轮)"
        if self._status_notice:
            self._status_notice.setText(msg)

    def _on_finished(self, full_text: str, conv_id: str):
        self._set_idle()
        if self._status_notice:
            self._status_notice.setText("")
        if conv_id:
            self._conv_id = conv_id
            if self._draft_contexts:
                self._conv_contexts.setdefault(conv_id, [])
                existing = {str(i.get("file_path")) for i in self._conv_contexts[conv_id]}
                for item in self._draft_contexts:
                    if item["file_path"] not in existing:
                        self._conv_contexts[conv_id].append(item)
                        existing.add(item["file_path"])
                self._draft_contexts.clear()
                self._refresh_context_ui()
            self._refresh_sessions()  # new session appears in list
        self._scroll_bottom()

    def _on_error(self, msg: str):
        self._set_idle()
        if self._status_notice:
            self._status_notice.setText(f"错误: {msg}")

    def _set_idle(self):
        self._is_running = False
        self._send_btn.setText("发送")
        try:
            self._send_btn.clicked.disconnect()
        except Exception:
            pass
        self._send_btn.clicked.connect(self._on_send)

    def _cleanup_worker(self):
        if self._worker:
            self._worker.wait(2000)
            self._worker.deleteLater()
            self._worker = None

    # ── UI helpers ─────────────────────────────────────────────────────

    def _add_user_bubble(self, text: str):
        self._insert_widget(_UserBubble(text, self._colors))

    def _add_notice(self, text: str):
        self._insert_widget(_SystemNotice(text, self._colors))

    def _insert_widget(self, w: QWidget):
        n = self._msg_layout.count()
        self._msg_layout.insertWidget(n - 1, w)

    def _scroll_bottom(self):
        QTimer.singleShot(50, lambda: self._msg_scroll.verticalScrollBar().setValue(
            self._msg_scroll.verticalScrollBar().maximum()))

    def set_theme(self, theme: str):
        self._theme = theme
        self._colors = get_colors(theme)

    def on_devices_changed(self, devices): pass
    def on_deactivated(self): pass
