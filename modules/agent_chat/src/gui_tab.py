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
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.base_tab import BaseTab

logger = logging.getLogger(__name__)

_DARK = {
    "bg": "#1e1e2e",
    "card_bg": "#313244",
    "border": "#45475a",
    "fg": "#cdd6f4",
    "fg_dim": "#a6adc8",
    "accent": "#cba6f7",
    "success": "#a6e3a1",
    "error": "#f38ba8",
    "warning": "#fab387",
    "user_bubble": "#313244",
    "tool_card_bg": "#181825",
    "workflow_border": "#cba6f7",
    "learn_border": "#f9e2af",
    "btn_send_bg": "#cba6f7",
    "btn_stop_bg": "#f38ba8",
}


# ---------------------------------------------------------------------------
# T019: 消息渲染 Widgets
# ---------------------------------------------------------------------------


class _UserMessageWidget(QFrame):
    """用户消息气泡（右对齐蓝色气泡）。"""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(60, 4, 8, 4)
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
        layout.setContentsMargins(8, 4, 60, 4)

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
        self._status_label = QLabel("执行中...")
        self._status_label.setStyleSheet(f"color: {_DARK['fg_dim']}; border: none;")
        self._toggle_btn = QPushButton("▶ 展开")
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
            self._status_label.setText(f"执行中... ({elapsed_sec:.1f}s)")
        else:
            self._status_label.setText("执行中...")

    def set_complete(self, elapsed_ms: float, content_preview: str = "") -> None:
        secs = elapsed_ms / 1000
        self._icon_label.setText("✅")
        self._status_label.setText(f"完成 ({secs:.1f}s)")
        self._status_label.setStyleSheet(f"color: {_DARK['success']}; border: none;")
        if content_preview:
            detail_label = QLabel(content_preview)
            detail_label.setWordWrap(True)
            detail_label.setStyleSheet(f"color: {_DARK['fg_dim']}; font-size: 11px; border: none;")
            self._detail_layout.addWidget(detail_label)
            self._toggle_btn.setVisible(True)

    def set_failed(self, error_msg: str = "") -> None:
        self._icon_label.setText("❌")
        self._status_label.setText("失败")
        self._status_label.setStyleSheet(f"color: {_DARK['error']}; border: none;")
        if error_msg:
            err_label = QLabel(error_msg)
            err_label.setWordWrap(True)
            err_label.setStyleSheet(f"color: {_DARK['error']}; font-size: 11px; border: none;")
            self._detail_layout.addWidget(err_label)
            self._toggle_btn.setVisible(True)

    def set_cancelled(self) -> None:
        self._icon_label.setText("⛔")
        self._status_label.setText("已取消")
        self._status_label.setStyleSheet(f"color: {_DARK['warning']}; border: none;")

    def add_report_button(self, report_path: str) -> None:
        btn = QPushButton("📂 打开报告目录")
        btn.setFixedHeight(24)
        btn.setStyleSheet(
            f"color: {_DARK['accent']}; border: 1px solid {_DARK['border']}; "
            "border-radius: 4px; padding: 2px 8px; font-size: 11px;"
        )
        btn.clicked.connect(lambda: _open_path(str(Path(report_path).parent)))
        self._report_layout.addWidget(btn)

        btn2 = QPushButton("📋 查看报告")
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
        self._toggle_btn.setText("▼ 收起" if not self._collapsed else "▶ 展开")


class _TokenUsageLabel(QLabel):
    """Token 用量显示（灰色小字）。"""

    def __init__(self, usage: dict[str, int], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        inp = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        out = usage.get("completion_tokens", usage.get("output_tokens", 0))
        text = f"↑{inp:,} ↓{out:,} tokens"
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
        title = QLabel(f"📋 工作流: {sop_title}")
        title.setStyleSheet(f"color: {_DARK['accent']}; font-weight: bold; border: none;")
        layout.addWidget(title)
        for i, step in enumerate(steps, 1):
            lbl = QLabel(f"  Step {i}: {step}")
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

        header = QLabel("💡 工作流沉淀")
        header.setStyleSheet(
            f"color: #F59E0B; font-weight: bold; font-size: 13px; border: none;"
        )
        layout.addWidget(header)

        tools = summary.get("unique_tools", [])
        steps = summary.get("total_steps", 0)
        desc = QLabel(f"本次对话使用了 {len(tools)} 个工具、{steps} 个步骤")
        desc.setStyleSheet(f"color: {_DARK['fg']}; font-size: 11px; border: none;")
        layout.addWidget(desc)

        if tools:
            tool_text = QLabel(f"工具: {', '.join(tools)}")
            tool_text.setStyleSheet(f"color: {_DARK['fg_dim']}; font-size: 10px; border: none;")
            tool_text.setWordWrap(True)
            layout.addWidget(tool_text)

        deviation = summary.get("sop_deviation", "")
        if deviation:
            dev_text = QLabel(f"偏差: {deviation}")
            dev_text.setStyleSheet("color: #FB923C; font-size: 10px; border: none;")
            dev_text.setWordWrap(True)
            layout.addWidget(dev_text)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_save = QPushButton("保存为新 SOP")
        btn_save.setStyleSheet(
            "QPushButton { background-color: #F59E0B; color: #1E1E2E; "
            "border: none; border-radius: 4px; padding: 5px 12px; font-size: 11px; }"
            "QPushButton:hover { background-color: #D97706; }"
        )
        btn_save.clicked.connect(self._on_save_new)
        btn_row.addWidget(btn_save)

        btn_skip = QPushButton("跳过")
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
        self._show_done("SOP 保存中...")

    def _on_skip(self) -> None:
        self.skipped.emit()
        self._show_done("已跳过")

    def _show_done(self, msg: str) -> None:
        for child in self.findChildren(QPushButton):
            child.setEnabled(False)
        done_label = QLabel(f"✓ {msg}")
        done_label.setStyleSheet(f"color: {_DARK['fg_dim']}; font-size: 10px; border: none;")
        self.layout().addWidget(done_label)


# ---------------------------------------------------------------------------
# T020: 异步 Worker (QThread)
# ---------------------------------------------------------------------------


class _AgentWorker(QThread):
    """后台执行 AgentService.chat() 的线程。"""

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
        from .models import StreamChunkType

        try:
            logger.debug("[DIAG] AgentWorker.run: 调用 chat()")
            response = self._service.chat(
                user_message=self._message,
                conversation_id=self._conv_id,
                on_chunk=self._on_chunk,
            )
            logger.debug("[DIAG] AgentWorker.run: chat() 返回, text_len=%d", len(response.text))
            logger.debug("[DIAG] AgentWorker.run: 准备 emit finished_ok")
            self.finished_ok.emit(response.text, self._conv_id or "")
            logger.debug("[DIAG] AgentWorker.run: finished_ok 已 emit, run() 即将返回")
        except Exception as exc:
            logger.error("AgentWorker 异常: %s", exc, exc_info=True)
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
            logger.debug("_on_chunk: 信号发射失败 (对象可能已销毁)")

    def cancel(self) -> None:
        if self._service:
            self._service.cancel()


# ---------------------------------------------------------------------------
# T020: 自适应高度输入框
# ---------------------------------------------------------------------------


class _ChatInput(QTextEdit):
    """自适应高度（1-5 行）输入框，Enter 发送，Shift+Enter 换行。"""

    send_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("描述你的任务...")
        self.setStyleSheet(
            f"background-color: {_DARK['card_bg']};"
            f"border: 1px solid {_DARK['border']};"
            "border-radius: 8px;"
            "padding: 8px 10px;"
            f"color: {_DARK['fg']};"
            "font-size: 13px;"
        )
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


class _SettingsDialog(QDialog):
    """Agent 设置弹窗（模型配置 + SOP 管理 + 高级设置）。"""

    config_changed = pyqtSignal(object)  # AgentConfig

    def __init__(
        self,
        config: Any,
        sop_manager: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Agent 设置")
        self.setMinimumSize(520, 420)
        self._config = config
        self._sop_manager = sop_manager
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        tabs.addTab(self._build_model_tab(), "模型配置")
        tabs.addTab(self._build_sop_tab(), "SOP 管理")
        tabs.addTab(self._build_advanced_tab(), "高级设置")

        layout.addWidget(tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_save = QPushButton("保存")
        btn_save.setFixedWidth(80)
        btn_save.clicked.connect(self._on_save)
        btn_cancel = QPushButton("取消")
        btn_cancel.setFixedWidth(80)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _build_model_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        grp = QGroupBox("LLM Provider")
        grp_layout = QHBoxLayout(grp)
        self._rb_glm = QPushButton("GLM (智谱)")
        self._rb_glm.setCheckable(True)
        self._rb_claude = QPushButton("Claude (Anthropic)")
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
        key_layout.addWidget(QLabel("API Key"))
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
        self._btn_toggle_key = QPushButton("👁")
        self._btn_toggle_key.setFixedWidth(30)
        self._btn_toggle_key.clicked.connect(self._toggle_key_visibility)
        key_layout.addWidget(self._btn_toggle_key)
        layout.addLayout(key_layout)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("模型"))
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        glm_models = ["glm-4-plus", "glm-4-flash", "glm-4-long", "glm-4"]
        claude_models = ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]
        self._model_combo.addItems(glm_models + claude_models)
        self._model_combo.setCurrentText(self._config.model_name)
        model_layout.addWidget(self._model_combo, 1)
        layout.addLayout(model_layout)

        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("回复语言"))
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["中文", "English"])
        self._lang_combo.setCurrentIndex(0 if self._config.language == "zh" else 1)
        lang_layout.addWidget(self._lang_combo)
        lang_layout.addStretch()
        layout.addLayout(lang_layout)

        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Temperature"))
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

        self._chk_smart = QCheckBox("智能切换: 复杂任务自动使用 Claude（需双 Key）")
        self._chk_smart.setChecked(self._config.smart_switch)
        layout.addWidget(self._chk_smart)

        layout.addStretch()
        return w

    def _build_sop_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self._sop_tree = QTreeWidget()
        self._sop_tree.setHeaderLabels(["名称", "来源", "操作"])
        self._sop_tree.setColumnWidth(0, 200)
        self._sop_tree.setColumnWidth(1, 60)
        self._refresh_sop_tree()
        layout.addWidget(self._sop_tree, 1)

        btn_row = QHBoxLayout()
        btn_import = QPushButton("📥 导入 SOP")
        btn_import.clicked.connect(self._on_import_sop)
        btn_row.addWidget(btn_import)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    def _build_advanced_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        grp_hist = QGroupBox("对话历史")
        hist_layout = QVBoxLayout(grp_hist)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("最大保存会话数:"))
        self._spin_max_conv = QSpinBox()
        self._spin_max_conv.setRange(5, 200)
        self._spin_max_conv.setValue(self._config.max_conversations)
        row1.addWidget(self._spin_max_conv)
        row1.addStretch()
        hist_layout.addLayout(row1)
        layout.addWidget(grp_hist)

        grp_ctx = QGroupBox("上下文管理")
        ctx_layout = QVBoxLayout(grp_ctx)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("最大上下文消息数:"))
        self._spin_max_ctx = QSpinBox()
        self._spin_max_ctx.setRange(5, 100)
        self._spin_max_ctx.setValue(self._config.max_context_messages)
        row2.addWidget(self._spin_max_ctx)
        row2.addStretch()
        ctx_layout.addLayout(row2)
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("工具结果最大长度:"))
        self._spin_tool_len = QSpinBox()
        self._spin_tool_len.setRange(500, 10000)
        self._spin_tool_len.setSingleStep(500)
        self._spin_tool_len.setValue(self._config.tool_result_max_length)
        row3.addWidget(self._spin_tool_len)
        row3.addWidget(QLabel("字符"))
        row3.addStretch()
        ctx_layout.addLayout(row3)
        layout.addWidget(grp_ctx)

        grp_wf = QGroupBox("工作流学习")
        wf_layout = QVBoxLayout(grp_wf)
        self._chk_wf_learn = QCheckBox("对话结束时检测可沉淀工作流")
        self._chk_wf_learn.setChecked(self._config.workflow_learning_enabled)
        wf_layout.addWidget(self._chk_wf_learn)
        layout.addWidget(grp_wf)

        layout.addStretch()
        return w

    def _toggle_key_visibility(self) -> None:
        if self._key_input.echoMode() == QLineEdit.EchoMode.Password:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._btn_toggle_key.setText("🔒")
        else:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._btn_toggle_key.setText("👁")

    def _refresh_sop_tree(self) -> None:
        self._sop_tree.clear()
        if not self._sop_manager:
            return
        from .models import SOPSource
        sops = self._sop_manager.load_all()
        builtin_root = QTreeWidgetItem(self._sop_tree, ["📁 内置", "", ""])
        custom_root = QTreeWidgetItem(self._sop_tree, ["📁 自定义", "", ""])
        for doc in sops:
            source_text = "内置" if doc.source == SOPSource.BUILTIN else "自定义"
            parent = builtin_root if doc.source == SOPSource.BUILTIN else custom_root
            item = QTreeWidgetItem(parent, [f"📄 {doc.title}", source_text, ""])
            item.setData(0, Qt.ItemDataRole.UserRole, doc)
        builtin_root.setExpanded(True)
        custom_root.setExpanded(True)

    def _on_import_sop(self) -> None:
        if not self._sop_manager:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "导入 SOP", "", "Markdown (*.md);;所有文件 (*)"
        )
        if path:
            self._sop_manager.import_sop(Path(path))
            self._refresh_sop_tree()

    def _on_save(self) -> None:
        from .models import AgentConfig, save_config

        provider = "claude" if self._rb_claude.isChecked() else "glm"
        api_key = self._key_input.text().strip()
        model_name = self._model_combo.currentText().strip()
        language = "en" if self._lang_combo.currentIndex() == 1 else "zh"
        temperature = self._temp_slider.value() / 100.0

        updates = {
            "provider": provider,
            "model_name": model_name or self._config.model_name,
            "temperature": temperature,
            "language": language,
            "smart_switch": self._chk_smart.isChecked(),
            "max_conversations": self._spin_max_conv.value(),
            "max_context_messages": self._spin_max_ctx.value(),
            "tool_result_max_length": self._spin_tool_len.value(),
            "workflow_learning_enabled": self._chk_wf_learn.isChecked(),
        }

        if api_key:
            if provider == "glm":
                updates["glm_api_key"] = api_key
                updates["api_key"] = api_key
            else:
                updates["claude_api_key"] = api_key
                updates["api_key"] = api_key

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

    tab_title = "Agent 智能助手"
    tab_icon = "🤖"

    def __init__(self, context: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._service: Any = None
        self._store: Any = None
        self._sop_manager: Any = None
        self._config: Any = None
        self._worker: _AgentWorker | None = None
        self._current_conv_id: str | None = None
        self._current_agent_widget: _AgentTextWidget | None = None
        self._current_tool_cards: dict[str, _ToolCallCard] = {}
        self._last_usage: dict[str, int] = {}
        self._is_running = False
        self._scroll_pending = False

        self._init_ui()

    # ── UI 初始化 ──────────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_panel = self._build_left_panel()
        left_panel.setFixedWidth(220)
        splitter.addWidget(left_panel)

        right_panel = self._build_right_panel()
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(
            f"background-color: {_DARK['bg']};"
            f"border-right: 1px solid {_DARK['border']};"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # T021: 会话历史
        hist_header = QHBoxLayout()
        hist_label = QLabel("会话历史")
        hist_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        self._btn_new_conv = QPushButton("+ 新建")
        self._btn_new_conv.setFixedHeight(22)
        self._btn_new_conv.setFixedWidth(50)
        self._btn_new_conv.setStyleSheet(
            f"color: {_DARK['accent']}; border: 1px solid {_DARK['border']}; "
            "border-radius: 4px; font-size: 11px;"
        )
        self._btn_new_conv.clicked.connect(self._on_new_conversation)
        hist_header.addWidget(hist_label)
        hist_header.addStretch()
        hist_header.addWidget(self._btn_new_conv)
        layout.addLayout(hist_header)

        self._conv_list = QListWidget()
        self._conv_list.setStyleSheet(
            f"QListWidget {{ background-color: transparent; border: none; }}"
            f"QListWidget::item {{ padding: 6px 8px; border-radius: 4px; }}"
            f"QListWidget::item:selected {{ background-color: {_DARK['card_bg']}; }}"
            f"QListWidget::item:hover {{ background-color: {_DARK['border']}; }}"
        )
        self._conv_list.itemClicked.connect(self._on_conv_selected)
        self._conv_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._conv_list.customContextMenuRequested.connect(self._on_conv_context_menu)
        layout.addWidget(self._conv_list, 1)

        # T022: SOP 管理
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {_DARK['border']};")
        layout.addWidget(sep)

        sop_header = QHBoxLayout()
        sop_label = QLabel("SOP 管理")
        sop_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        sop_header.addWidget(sop_label)
        sop_header.addStretch()
        layout.addLayout(sop_header)

        self._sop_tree = QTreeWidget()
        self._sop_tree.setHeaderHidden(True)
        self._sop_tree.setStyleSheet(
            f"QTreeWidget {{ background-color: transparent; border: none; }}"
            f"QTreeWidget::item {{ padding: 3px 4px; }}"
            f"QTreeWidget::item:hover {{ background-color: {_DARK['border']}; }}"
        )
        self._sop_tree.setMaximumHeight(180)
        self._sop_tree.itemDoubleClicked.connect(self._on_sop_double_click)
        self._sop_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._sop_tree.customContextMenuRequested.connect(self._on_sop_context_menu)
        layout.addWidget(self._sop_tree)

        sop_btn_row = QHBoxLayout()
        btn_import = QPushButton("📥 导入")
        btn_import.setFixedHeight(22)
        btn_import.setStyleSheet(
            f"color: {_DARK['fg_dim']}; border: 1px solid {_DARK['border']}; "
            "border-radius: 4px; font-size: 11px; padding: 2px 6px;"
        )
        btn_import.clicked.connect(self._on_import_sop)
        btn_manage = QPushButton("📋 管理")
        btn_manage.setFixedHeight(22)
        btn_manage.setStyleSheet(
            f"color: {_DARK['fg_dim']}; border: 1px solid {_DARK['border']}; "
            "border-radius: 4px; font-size: 11px; padding: 2px 6px;"
        )
        btn_manage.clicked.connect(self._on_open_settings)
        sop_btn_row.addWidget(btn_import)
        sop_btn_row.addWidget(btn_manage)
        sop_btn_row.addStretch()
        layout.addLayout(sop_btn_row)

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部工具栏
        toolbar = QWidget()
        toolbar.setFixedHeight(36)
        toolbar.setStyleSheet(
            f"background-color: {_DARK['bg']};"
            f"border-bottom: 1px solid {_DARK['border']};"
        )
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 0, 12, 0)
        lbl_title = QLabel("🤖 Agent 智能助手")
        lbl_title.setStyleSheet(f"color: {_DARK['accent']}; font-weight: bold; font-size: 13px;")
        tb_layout.addWidget(lbl_title)
        tb_layout.addStretch()
        self._lbl_model = QLabel("模型: --")
        self._lbl_model.setStyleSheet(f"color: {_DARK['fg_dim']}; font-size: 11px;")
        tb_layout.addWidget(self._lbl_model)
        self._btn_settings = QPushButton("⚙ 设置")
        self._btn_settings.setFixedHeight(24)
        self._btn_settings.setStyleSheet(
            f"color: {_DARK['fg_dim']}; border: 1px solid {_DARK['border']}; "
            "border-radius: 4px; padding: 2px 8px; font-size: 11px;"
        )
        self._btn_settings.clicked.connect(self._on_open_settings)
        tb_layout.addWidget(self._btn_settings)
        layout.addWidget(toolbar)

        # 消息区域（QStackedWidget: 欢迎页 / 聊天页）
        self._content_stack = QStackedWidget()

        self._welcome_page = self._build_welcome_page()
        self._content_stack.addWidget(self._welcome_page)

        self._chat_page = self._build_chat_page()
        self._content_stack.addWidget(self._chat_page)

        layout.addWidget(self._content_stack, 1)

        # 输入区域
        input_bar = QWidget()
        input_bar.setStyleSheet(f"border-top: 1px solid {_DARK['border']};")
        ib_layout = QHBoxLayout(input_bar)
        ib_layout.setContentsMargins(12, 8, 12, 8)

        self._chat_input = _ChatInput()
        ib_layout.addWidget(self._chat_input, 1)

        self._btn_send = QPushButton("发送")
        self._btn_send.setFixedSize(60, 36)
        self._btn_send.setStyleSheet(
            f"background-color: {_DARK['btn_send_bg']};"
            "color: #1e1e2e;"
            "border-radius: 8px;"
            "font-weight: bold;"
        )
        self._btn_send.clicked.connect(self._on_send)
        self._chat_input.send_requested.connect(self._on_send)
        ib_layout.addWidget(self._btn_send)

        layout.addWidget(input_bar)
        return panel

    def _build_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(2)

        center = QVBoxLayout()
        center.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("🤖 Agent 智能助手")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {_DARK['accent']}; font-size: 20px; font-weight: bold;")
        center.addWidget(title)

        subtitle = QLabel("描述你的任务，我将自动匹配工作流完成分析。")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"color: {_DARK['fg_dim']}; font-size: 13px; padding: 8px;")
        center.addWidget(subtitle)

        btn_grid = QHBoxLayout()
        btn_grid.setSpacing(12)
        btn_grid.addStretch()
        shortcuts = [
            ("🔍 Trace 分析", "帮我分析 Perfetto trace 文件中的卡顿问题"),
            ("📊 PerfDog 分析", "帮我分析 PerfDog 导出的性能数据"),
            ("⚙ 策略审查", "帮我审查当前的游戏性能策略配置"),
            ("🔬 综合卡顿分析", "帮我做一次完整的游戏卡顿综合分析"),
        ]
        for label, prompt in shortcuts:
            btn = QPushButton(label)
            btn.setFixedSize(140, 36)
            btn.setStyleSheet(
                f"background-color: {_DARK['card_bg']};"
                f"color: {_DARK['fg']};"
                f"border: 1px solid {_DARK['border']};"
                "border-radius: 8px;"
                "font-size: 12px;"
            )
            btn.clicked.connect(lambda checked, p=prompt: self._quick_send(p))
            btn_grid.addWidget(btn)
        btn_grid.addStretch()
        center.addLayout(btn_grid)

        hint = QLabel("💡 提示: 你也可以直接描述需求，无需选择具体分析类型")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"color: {_DARK['fg_dim']}; font-size: 11px; padding: 12px;")
        center.addWidget(hint)

        layout.addLayout(center)
        layout.addStretch(3)
        return page

    def _build_chat_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self._msg_scroll = QScrollArea()
        self._msg_scroll.setWidgetResizable(True)
        self._msg_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._msg_scroll.setStyleSheet("border: none;")

        self._msg_container = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(8, 8, 8, 8)
        self._msg_layout.setSpacing(2)
        self._msg_layout.addStretch()

        self._msg_scroll.setWidget(self._msg_container)
        layout.addWidget(self._msg_scroll)
        return page

    # ── Tab 生命周期 ─────────────────────────────────────────────────────

    def on_activated(self) -> None:
        if self.context:
            self._config = self.context.get("ac_config")
            if self._config:
                self._lbl_model.setText(
                    f"模型: {self._config.model_name} ({self._config.provider.upper()})"
                )
        self._ensure_service()
        self._refresh_conv_list()
        self._refresh_sop_tree()

        has_key = False
        if self._config:
            has_key = bool(
                self._config.api_key
                or self._config.glm_api_key
                or self._config.claude_api_key
            )
        if not has_key and self._content_stack.currentIndex() == 0:
            self._show_setup_guide()

    # ── 服务初始化 ────────────────────────────────────────────────────────

    def _ensure_service(self) -> None:
        """确保 AgentService 已初始化。"""
        if self._service:
            return

        if not self._config:
            return

        from .memory.conversation import ConversationStore
        from .service import AgentService
        from .sop.manager import SOPManager
        from .tools.registry import ToolRegistry

        module_dir = Path(__file__).resolve().parent.parent
        data_dir = module_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        self._store = ConversationStore(data_dir / "agent_chat.db")

        self._sop_manager = SOPManager(
            builtin_dir=module_dir / "assets" / "sops",
            custom_dir=data_dir / "sops",
        )
        self._sop_manager.load_all()

        tool_registry = ToolRegistry()
        pm = self.context.get("plugin_manager") if self.context else None
        if pm:
            tool_registry.collect_from_plugins(pm)

        self._service = AgentService(
            config=self._config,
            conversation_store=self._store,
            tool_registry=tool_registry,
            sop_manager=self._sop_manager,
        )

    def _reinit_service(self) -> None:
        """配置变更后重新初始化 service。"""
        if self._store:
            self._store.close()
        self._service = None
        self._store = None
        self._sop_manager = None
        self._ensure_service()

    # ── 首次使用引导 ──────────────────────────────────────────────────────

    def _show_setup_guide(self) -> None:
        """在欢迎页显示 API Key 配置引导。"""
        pass  # 由 _on_open_settings 替代，点击设置直接弹出

    # ── 会话历史管理 (T021) ──────────────────────────────────────────────

    def _refresh_conv_list(self) -> None:
        self._conv_list.clear()
        if not self._store:
            return

        convs = self._store.list_conversations()
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        groups: dict[str, list[dict]] = {}
        for c in convs:
            try:
                dt = datetime.datetime.strptime(c["updated_at"], "%Y-%m-%dT%H:%M:%S")
                d = dt.date()
            except (ValueError, KeyError):
                d = today
            if d == today:
                key = "● 今天"
            elif d == yesterday:
                key = "● 昨天"
            else:
                key = f"● {d.strftime('%m月%d日')}"
            groups.setdefault(key, []).append(c)

        for group_name, items in groups.items():
            header = QListWidgetItem(group_name)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header.setForeground(QColor(_DARK["fg_dim"]))
            font = header.font()
            font.setBold(True)
            font.setPointSize(9)
            header.setFont(font)
            self._conv_list.addItem(header)

            for c in items:
                title = c.get("title") or "新对话"
                if len(title) > 20:
                    title = title[:20] + "..."
                prefix = "🔵" if c["id"] == self._current_conv_id else "⚪"
                item = QListWidgetItem(f"  {prefix} {title}")
                item.setData(Qt.ItemDataRole.UserRole, c["id"])
                self._conv_list.addItem(item)

    def _on_conv_selected(self, item: QListWidgetItem) -> None:
        conv_id = item.data(Qt.ItemDataRole.UserRole)
        if not conv_id:
            return

        if self._is_running:
            reply = QMessageBox.question(
                self,
                "切换会话",
                "当前有任务在执行中，切换会话将停止当前任务。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
            self._on_stop()

        self._current_conv_id = conv_id
        self._load_conversation_messages(conv_id)
        self._refresh_conv_list()

    def _on_conv_context_menu(self, pos) -> None:
        item = self._conv_list.itemAt(pos)
        if not item:
            return
        conv_id = item.data(Qt.ItemDataRole.UserRole)
        if not conv_id:
            return

        menu = QMenu(self)
        action_rename = menu.addAction("重命名")
        action_delete = menu.addAction("删除")

        action = menu.exec(self._conv_list.mapToGlobal(pos))
        if action == action_rename:
            new_name, ok = QInputDialog.getText(self, "重命名对话", "新名称:")
            if ok and new_name.strip() and self._store:
                self._store.rename_conversation(conv_id, new_name.strip())
                self._refresh_conv_list()
        elif action == action_delete:
            reply = QMessageBox.question(
                self, "删除对话", "确认删除该对话？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes and self._store:
                self._store.delete_conversation(conv_id)
                if self._current_conv_id == conv_id:
                    self._current_conv_id = None
                    self._clear_messages()
                    self._content_stack.setCurrentIndex(0)
                self._refresh_conv_list()

    def _on_new_conversation(self) -> None:
        if self._is_running:
            reply = QMessageBox.question(
                self,
                "新建对话",
                "当前有任务在执行中，新建对话将停止当前任务。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
            self._on_stop()

        self._current_conv_id = None
        self._clear_messages()
        self._content_stack.setCurrentIndex(0)
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

    # ── SOP 管理 (T022) ──────────────────────────────────────────────────

    def _refresh_sop_tree(self) -> None:
        self._sop_tree.clear()
        if not self._sop_manager:
            return

        from .models import SOPSource

        sops = self._sop_manager.load_all()
        builtin_items = [s for s in sops if s.source == SOPSource.BUILTIN]
        custom_items = [s for s in sops if s.source == SOPSource.CUSTOM]

        if builtin_items:
            root_b = QTreeWidgetItem(self._sop_tree, [f"📁 内置 ({len(builtin_items)})"])
            for doc in builtin_items:
                item = QTreeWidgetItem(root_b, [f"📄 {doc.title}"])
                item.setData(0, Qt.ItemDataRole.UserRole, doc)
            root_b.setExpanded(True)

        if custom_items:
            root_c = QTreeWidgetItem(self._sop_tree, [f"📁 自定义 ({len(custom_items)})"])
            for doc in custom_items:
                item = QTreeWidgetItem(root_c, [f"📄 {doc.title}"])
                item.setData(0, Qt.ItemDataRole.UserRole, doc)
            root_c.setExpanded(True)

    def _on_sop_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        doc = item.data(0, Qt.ItemDataRole.UserRole)
        if not doc:
            return
        _open_path(str(doc.path))

    def _on_sop_context_menu(self, pos) -> None:
        item = self._sop_tree.itemAt(pos)
        if not item:
            return
        doc = item.data(0, Qt.ItemDataRole.UserRole)
        if not doc:
            return

        from .models import SOPSource

        menu = QMenu(self)
        if doc.source == SOPSource.CUSTOM:
            action_edit = menu.addAction("编辑")
            action_delete = menu.addAction("删除")
            action_export = menu.addAction("导出")
        else:
            action_edit = menu.addAction("查看")
            action_delete = None
            action_export = menu.addAction("导出")

        action = menu.exec(self._sop_tree.mapToGlobal(pos))
        if action == action_edit:
            _open_path(str(doc.path))
        elif action_delete and action == action_delete:
            reply = QMessageBox.question(
                self, "删除 SOP", f"确认删除 SOP「{doc.title}」？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes and self._sop_manager:
                self._sop_manager.delete_sop(doc.title)
                self._refresh_sop_tree()
        elif action == action_export:
            target, _ = QFileDialog.getSaveFileName(
                self, "导出 SOP", doc.title + ".md", "Markdown (*.md)"
            )
            if target and self._sop_manager:
                self._sop_manager.export_sop(doc.title, Path(target))

    def _on_import_sop(self) -> None:
        if not self._sop_manager:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "导入 SOP", "", "Markdown (*.md);;所有文件 (*)"
        )
        if path:
            self._sop_manager.import_sop(Path(path))
            self._refresh_sop_tree()

    # ── 设置 (T023) ──────────────────────────────────────────────────────

    def _on_open_settings(self) -> None:
        if not self._config:
            return
        dlg = _SettingsDialog(self._config, self._sop_manager, self)
        dlg.config_changed.connect(self._on_config_changed)
        dlg.exec()

    def _on_config_changed(self, new_config: Any) -> None:
        self._config = new_config
        if self.context:
            self.context["ac_config"] = new_config
        self._lbl_model.setText(
            f"模型: {new_config.model_name} ({new_config.provider.upper()})"
        )
        self._reinit_service()
        self._refresh_sop_tree()

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
            QMessageBox.warning(self, "Agent 未就绪", "请先在设置中配置 API Key。")
            return

        if not self._service.is_ready:
            QMessageBox.warning(self, "Agent 未就绪", "API Key 未配置或无效，请在设置中检查。")
            return

        self._content_stack.setCurrentIndex(1)
        self._chat_input.clear()

        self._add_user_bubble(text)
        self._current_agent_widget = _AgentTextWidget()
        self._insert_message_widget(self._current_agent_widget)
        self._current_tool_cards.clear()
        self._last_usage = {}

        self._set_running(True)

        self._worker = _AgentWorker(
            service=self._service,
            message=text,
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
            _SystemNotice("⚠️ 工作已中断。你可以继续发送消息。")
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
            logger.warning("_on_tool_start: widget 已销毁, 忽略")

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
            logger.warning("_on_tool_end: widget 已销毁, 忽略")

    def _on_usage(self, usage: dict) -> None:
        self._last_usage = usage

    def _on_finished(self, full_text: str, conv_id: str) -> None:
        logger.debug("[DIAG] _on_finished: 开始处理")
        try:
            self._set_running(False)
            if conv_id:
                self._current_conv_id = conv_id

            if self._last_usage:
                self._insert_message_widget(_TokenUsageLabel(self._last_usage))

            self._refresh_conv_list()
            self._scroll_to_bottom()

            if not self._current_conv_id and self._store:
                convs = self._store.list_conversations()
                if convs:
                    self._current_conv_id = convs[0]["id"]
                    first_msg = full_text[:20] if full_text else "新对话"
                    self._store.rename_conversation(self._current_conv_id, first_msg)
                    self._refresh_conv_list()
        except RuntimeError:
            logger.warning("_on_finished: widget 已销毁, 忽略")

    def _on_error(self, msg: str) -> None:
        try:
            self._set_running(False)
            err_label = _SystemNotice(f"❌ 错误: {msg}")
            err_label.setStyleSheet(f"color: {_DARK['error']}; font-size: 12px; padding: 8px;")
            self._insert_message_widget(err_label)
            self._scroll_to_bottom()
        except RuntimeError:
            logger.warning("_on_error: widget 已销毁, 忽略")

    def _on_workflow_deposit(self, summary: dict) -> None:
        """工作流满足沉淀条件时显示沉淀卡片。"""
        card = _WorkflowDepositCard(summary, parent=self)
        card.save_new.connect(self._on_deposit_save_new)
        card.skipped.connect(lambda: logger.debug("用户跳过工作流沉淀"))
        self._insert_message_widget(card)
        self._scroll_to_bottom()

    def _on_deposit_save_new(self, summary: dict) -> None:
        """保存工作流为新 SOP。"""
        from .workflow.generator import generate_sop_from_trace, open_sop_file, save_sop

        content = generate_sop_from_trace(summary)

        if not self._sop_manager:
            return

        module_dir = Path(__file__).resolve().parent.parent
        save_dir = module_dir / "data" / "sops"
        saved_path = save_sop(content, save_dir)

        self._sop_manager.load_all()
        self._refresh_sop_tree()

        reply = QMessageBox.question(
            self,
            "SOP 已保存",
            f"SOP 已保存到:\n{saved_path}\n\n是否打开编辑？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
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
            self._btn_send.setText("停止")
            self._btn_send.setStyleSheet(
                f"background-color: {_DARK['btn_stop_bg']};"
                "color: #1e1e2e;"
                "border-radius: 8px;"
                "font-weight: bold;"
            )
            self._btn_send.clicked.disconnect()
            self._btn_send.clicked.connect(self._on_stop)
        else:
            self._btn_send.setText("发送")
            self._btn_send.setStyleSheet(
                f"background-color: {_DARK['btn_send_bg']};"
                "color: #1e1e2e;"
                "border-radius: 8px;"
                "font-weight: bold;"
            )
            self._btn_send.clicked.disconnect()
            self._btn_send.clicked.connect(self._on_send)

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
        logger.error("打开路径失败 '%s': %s", path, exc)
