# -*- coding: utf-8 -*-
"""统一对话框组件 — 无边框风格，替换原生 QMessageBox / QInputDialog。

所有对话框复用 llmSettingsDialog 相关的 QSS 选择器实现暗色/亮色主题自适应。
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class DialogCloseButton(QPushButton):
    """对话框关闭按钮 — Codicons 或 fallback 矢量 X。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setObjectName("llmDialogCloseBtn")

    def paintEvent(self, event) -> None:
        from toolkit.gui.codicons import codicon_font, icon_char

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.underMouse():
            p.fillRect(self.rect(), QColor("#f38ba8"))
            icon_color = QColor("#1e1e2e")
        else:
            icon_color = QColor("#a6adc8")

        font = codicon_font(14)
        if font:
            p.setPen(icon_color)
            p.setFont(font)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, icon_char("close"))
        else:
            cx = self.width() / 2
            cy = self.height() / 2
            p.setPen(QPen(icon_color, 1.2))
            p.drawLine(QPointF(cx - 4, cy - 4), QPointF(cx + 4, cy + 4))
            p.drawLine(QPointF(cx + 4, cy - 4), QPointF(cx - 4, cy + 4))
        p.end()


class ToolkitDialog(QDialog):
    """统一无边框对话框基类，自动提供标题栏和可拖动。

    子类或直接使用者在 content_layout 中添加内容即可。
    """

    def __init__(
        self,
        title: str = "",
        parent: QWidget | None = None,
        min_width: int = 360,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("llmSettingsDialog")
        self.setMinimumWidth(min_width)
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        )
        self._drag_pos: QPoint | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        title_bar = QWidget()
        title_bar.setObjectName("llmDialogTitleBar")
        title_bar.setFixedHeight(36)
        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(16, 0, 4, 0)

        lbl = QLabel(title)
        lbl.setObjectName("llmDialogTitle")
        tb.addWidget(lbl)
        tb.addStretch()

        close_btn = DialogCloseButton()
        close_btn.clicked.connect(self.reject)
        tb.addWidget(close_btn)
        outer.addWidget(title_bar)

        sep = QWidget()
        sep.setObjectName("llmDialogSeparator")
        sep.setFixedHeight(1)
        outer.addWidget(sep)

        content_wrapper = QWidget()
        self.content_layout = QVBoxLayout(content_wrapper)
        self.content_layout.setContentsMargins(24, 16, 24, 20)
        self.content_layout.setSpacing(12)
        outer.addWidget(content_wrapper)

    # ── 拖动支持 ──

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.pos().y() < 36:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


def confirm_dialog(
    parent: QWidget,
    title: str,
    message: str,
    confirm_text: str = "确认",
    cancel_text: str = "取消",
    danger: bool = False,
) -> bool:
    """显示统一风格的确认对话框。返回 True 表示用户点击了确认。"""
    dlg = ToolkitDialog(title, parent, min_width=340)

    msg_label = QLabel(message)
    msg_label.setWordWrap(True)
    msg_label.setObjectName("dlgMsgLabel")
    dlg.content_layout.addWidget(msg_label)

    btn_row = QHBoxLayout()
    btn_row.addStretch()

    btn_cancel = QPushButton(cancel_text)
    btn_cancel.setObjectName("secondaryBtn")
    btn_cancel.setFixedWidth(80)
    btn_cancel.clicked.connect(dlg.reject)
    btn_row.addWidget(btn_cancel)

    btn_ok = QPushButton(confirm_text)
    btn_ok.setObjectName("dangerBtn" if danger else "primaryBtn")
    btn_ok.setFixedWidth(80)
    btn_ok.clicked.connect(dlg.accept)
    btn_row.addWidget(btn_ok)

    dlg.content_layout.addLayout(btn_row)

    return dlg.exec() == QDialog.DialogCode.Accepted


def input_dialog(
    parent: QWidget,
    title: str,
    label: str,
    default_text: str = "",
) -> tuple[str, bool]:
    """显示统一风格的文本输入对话框。返回 (text, accepted)。"""
    dlg = ToolkitDialog(title, parent, min_width=380)

    lbl = QLabel(label)
    lbl.setObjectName("dlgMsgLabel")
    dlg.content_layout.addWidget(lbl)

    edit = QLineEdit()
    edit.setText(default_text)
    dlg.content_layout.addWidget(edit)

    btn_row = QHBoxLayout()
    btn_row.addStretch()

    btn_cancel = QPushButton("取消")
    btn_cancel.setObjectName("secondaryBtn")
    btn_cancel.setFixedWidth(80)
    btn_cancel.clicked.connect(dlg.reject)
    btn_row.addWidget(btn_cancel)

    btn_ok = QPushButton("确定")
    btn_ok.setObjectName("primaryBtn")
    btn_ok.setFixedWidth(80)
    btn_ok.clicked.connect(dlg.accept)
    btn_row.addWidget(btn_ok)

    dlg.content_layout.addLayout(btn_row)

    accepted = dlg.exec() == QDialog.DialogCode.Accepted
    return edit.text(), accepted


def warning_dialog(parent: QWidget, title: str, message: str) -> None:
    """显示统一风格的警告提示对话框（仅一个"确定"按钮）。"""
    dlg = ToolkitDialog(title, parent, min_width=340)

    msg_label = QLabel(message)
    msg_label.setWordWrap(True)
    msg_label.setObjectName("dlgMsgLabel")
    dlg.content_layout.addWidget(msg_label)

    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_ok = QPushButton("确定")
    btn_ok.setObjectName("primaryBtn")
    btn_ok.setFixedWidth(80)
    btn_ok.clicked.connect(dlg.accept)
    btn_row.addWidget(btn_ok)
    dlg.content_layout.addLayout(btn_row)

    dlg.exec()


def info_dialog(parent: QWidget, title: str, message: str) -> None:
    """显示统一风格的信息提示对话框（仅一个"确定"按钮）。"""
    warning_dialog(parent, title, message)


def three_button_dialog(
    parent: QWidget,
    title: str,
    message: str,
    btn1_text: str,
    btn2_text: str,
    btn3_text: str,
) -> int:
    """三按钮对话框。返回 0/1/2 分别对应 btn1/btn2/btn3。"""
    dlg = ToolkitDialog(title, parent, min_width=400)
    result = [0]

    msg_label = QLabel(message)
    msg_label.setWordWrap(True)
    msg_label.setObjectName("dlgMsgLabel")
    dlg.content_layout.addWidget(msg_label)

    btn_row = QHBoxLayout()
    btn_row.addStretch()

    def _make_handler(idx):
        def _h():
            result[0] = idx
            dlg.accept()
        return _h

    b1 = QPushButton(btn1_text)
    b1.setObjectName("dangerBtn")
    b1.clicked.connect(_make_handler(0))
    btn_row.addWidget(b1)

    b2 = QPushButton(btn2_text)
    b2.setObjectName("secondaryBtn")
    b2.clicked.connect(_make_handler(1))
    btn_row.addWidget(b2)

    b3 = QPushButton(btn3_text)
    b3.setObjectName("primaryBtn")
    b3.clicked.connect(_make_handler(2))
    btn_row.addWidget(b3)

    dlg.content_layout.addLayout(btn_row)

    if dlg.exec() == QDialog.DialogCode.Rejected:
        return 2
    return result[0]
