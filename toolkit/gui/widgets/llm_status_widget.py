"""状态栏 LLM 指示器 — 上下文圆环 + 模型名（精简版）。"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QWidget,
)

from toolkit.gui.theme_colors import get_colors
from toolkit.gui import strings as s


class ContextRingWidget(QWidget):
    """上下文窗口占用圆环 — 统一蓝色填充，无颜色区分。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self._ratio = 0.0
        self._fg_color = QColor("#89b4fa")
        self._bg_color = QColor("#45475a")
        self._used_tokens = 0
        self._total_tokens = 0

    def set_ratio(self, ratio: float, used: int = 0, total: int = 0) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self._used_tokens = used
        self._total_tokens = total
        pct = self._ratio * 100
        actual_used = self._used_tokens if self._used_tokens > 0 else int(self._ratio * max(self._total_tokens, 1))
        self.setToolTip(
            s.LLM_CONTEXT_TOOLTIP_FMT.format(
                used=actual_used,
                total=self._total_tokens,
                pct=pct,
            )
        )
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen_bg = QPen(self._bg_color, 2.0)
        p.setPen(pen_bg)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(2, 2, 14, 14), 0, 360 * 16)

        if self._ratio > 0:
            pen_fg = QPen(self._fg_color, 2.0)
            p.setPen(pen_fg)
            span = int(self._ratio * 360 * 16)
            p.drawArc(QRectF(2, 2, 14, 14), 90 * 16, -span)

        p.end()


class LLMStatusWidget(QWidget):
    """状态栏 LLM 状态指示器 — 圆环 + 模型名。"""

    model_switch_requested = pyqtSignal(str)

    def __init__(self, llm_manager: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._llm_manager = llm_manager
        self._theme = "dark"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._ring = ContextRingWidget()
        layout.addWidget(self._ring)

        self._model_label = QLabel(s.LLM_STATUS_NOT_CONFIGURED)
        self._model_label.setObjectName("llmModelLabel")
        self._model_label.mousePressEvent = self._on_model_clicked
        layout.addWidget(self._model_label)

        llm_manager.token_updated.connect(self._on_token_updated)
        llm_manager.provider_changed.connect(self._on_provider_changed)
        llm_manager.config_changed.connect(self._on_config_changed)

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        colors = get_colors(theme)
        self._ring._bg_color = QColor(colors.get("border", "#45475a"))
        self.update()

    def _on_token_updated(self, used: int, total: int) -> None:
        ratio = used / total if total > 0 else 0.0
        self._ring.set_ratio(ratio, used=used, total=total)

    def _on_provider_changed(self, provider_name: str) -> None:
        cfg = self._llm_manager.get_config()
        self._model_label.setText(cfg.model_name)

    def _on_config_changed(self, config: object) -> None:
        self._model_label.setText(config.model_name)

    def _on_model_clicked(self, event) -> None:
        menu = QMenu(self)
        menu.setObjectName("modelSwitchMenu")
        try:
            svc = self._llm_manager.get_service("llm_manager_service")
            if svc:
                prov, _ = svc.get_active_provider_config()
                for m in prov.models:
                    action = menu.addAction(m.name)
                    action.setCheckable(True)
                    action.setChecked(m.name == self._llm_manager.get_config().model_name)
                    action.triggered.connect(
                        lambda checked, n=m.name: self._switch_model(n)
                    )
        except Exception:
            pass
        if menu.actions():
            menu.exec(self._model_label.mapToGlobal(
                self._model_label.rect().bottomLeft()
            ))

    def _switch_model(self, model_name: str) -> None:
        self._llm_manager.switch_model(model_name)
        self.model_switch_requested.emit(model_name)
