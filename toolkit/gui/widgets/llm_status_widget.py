# -*- coding: utf-8 -*-
"""状态栏 LLM 指示器 — 上下文圆环 + Token 用量 + 模型快捷切换。"""
from __future__ import annotations

import math

from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QWidget,
)


def _format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


class ContextRingWidget(QWidget):
    """上下文窗口占用空心圆环。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ratio = 0.0
        self.setFixedSize(18, 18)

    def set_ratio(self, ratio: float) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(2, 2, 14, 14)
        line_w = 2.0

        bg_pen = QPen(QColor("#45475a"), line_w)
        painter.setPen(bg_pen)
        painter.drawEllipse(rect)

        if self._ratio > 0:
            if self._ratio >= 0.95:
                color = QColor("#f38ba8")  # red
            elif self._ratio >= 0.80:
                color = QColor("#f9e2af")  # yellow
            else:
                color = QColor("#a6e3a1")  # green

            fg_pen = QPen(color, line_w)
            fg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(fg_pen)
            start = 90 * 16  # 12 o'clock
            span = -int(self._ratio * 360 * 16)
            painter.drawArc(rect, start, span)

        painter.end()


class LLMStatusWidget(QWidget):
    """状态栏 LLM 信息组件 — ContextRing + Token + Model。"""

    model_switch_requested = pyqtSignal(str)

    def __init__(self, llm_manager: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._llm_manager = llm_manager
        self.setObjectName("llmStatusWidget")
        self._setup_ui()
        self._connect_signals()
        self._refresh()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._ring = ContextRingWidget(self)
        layout.addWidget(self._ring)

        self._token_label = QLabel("0 / 100k")
        self._token_label.setObjectName("llmTokenLabel")
        layout.addWidget(self._token_label)

        self._model_label = QLabel("未配置")
        self._model_label.setObjectName("llmModelLabel")
        self._model_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._model_label.mousePressEvent = self._on_model_clicked
        layout.addWidget(self._model_label)

    def _connect_signals(self) -> None:
        mgr = self._llm_manager
        if hasattr(mgr, "token_updated"):
            mgr.token_updated.connect(self._on_token_updated)  # type: ignore[union-attr]
        if hasattr(mgr, "provider_changed"):
            mgr.provider_changed.connect(self._on_provider_changed)  # type: ignore[union-attr]
        if hasattr(mgr, "config_changed"):
            mgr.config_changed.connect(self._on_config_changed)  # type: ignore[union-attr]

    def _refresh(self) -> None:
        mgr = self._llm_manager
        if hasattr(mgr, "get_config"):
            cfg = mgr.get_config()  # type: ignore[union-attr]
            self._model_label.setText(cfg.model_name if cfg.is_configured() else "未配置")
            budget_str = _format_tokens(cfg.token_budget)
            self._token_label.setText(f"0 / {budget_str}")

        if hasattr(mgr, "get_context_usage_ratio"):
            self._ring.set_ratio(mgr.get_context_usage_ratio())  # type: ignore[union-attr]

    def _on_token_updated(self, used: int, budget: int) -> None:
        self._token_label.setText(f"{_format_tokens(used)} / {_format_tokens(budget)}")
        if hasattr(self._llm_manager, "get_context_usage_ratio"):
            self._ring.set_ratio(
                self._llm_manager.get_context_usage_ratio()  # type: ignore[union-attr]
            )

    def _on_provider_changed(self, provider_name: str) -> None:
        if hasattr(self._llm_manager, "get_config"):
            cfg = self._llm_manager.get_config()  # type: ignore[union-attr]
            self._model_label.setText(cfg.model_name)

    def _on_config_changed(self, config: object) -> None:
        self._refresh()

    def _on_model_clicked(self, event) -> None:
        provider = self._llm_manager.get_provider()  # type: ignore[union-attr]
        if not provider:
            return

        models = provider.get_available_models()
        if not models:
            return

        menu = QMenu(self)
        menu.setObjectName("modelSwitchMenu")
        current = self._llm_manager.get_config().model_name  # type: ignore[union-attr]

        for m in models:
            action = menu.addAction(m)
            action.setCheckable(True)
            action.setChecked(m == current)
            action.triggered.connect(lambda checked, model=m: self._switch_model(model))

        menu.exec(event.globalPosition().toPoint() if hasattr(event, "globalPosition") else self._model_label.mapToGlobal(self._model_label.rect().bottomLeft()))

    def _switch_model(self, model_name: str) -> None:
        if hasattr(self._llm_manager, "switch_model"):
            self._llm_manager.switch_model(model_name)  # type: ignore[union-attr]
            self._model_label.setText(model_name)
