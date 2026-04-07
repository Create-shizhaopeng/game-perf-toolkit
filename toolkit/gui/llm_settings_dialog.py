# -*- coding: utf-8 -*-
"""LLM 模型设置对话框 — Provider / API Key / 模型 / 参数配置。"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from toolkit.sdk.models import LLMConfig

_GLM_MODELS = ["glm-4-plus", "glm-4-flash", "glm-4-long"]
_CLAUDE_MODELS = ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"]


class _ApiKeyRow(QWidget):
    """API Key 输入行 — 密码框 + 显示/隐藏按钮。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._edit = QLineEdit()
        self._edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._edit.setPlaceholderText("输入 API Key")
        self._edit.setObjectName("apiKeyEdit")
        layout.addWidget(self._edit, 1)

        self._toggle_btn = QPushButton("显示")
        self._toggle_btn.setFixedWidth(48)
        self._toggle_btn.setObjectName("apiKeyToggle")
        self._toggle_btn.clicked.connect(self._toggle_echo)
        layout.addWidget(self._toggle_btn)

    def _toggle_echo(self) -> None:
        if self._edit.echoMode() == QLineEdit.EchoMode.Password:
            self._edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle_btn.setText("隐藏")
        else:
            self._edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle_btn.setText("显示")

    def text(self) -> str:
        return self._edit.text()

    def setText(self, text: str) -> None:
        self._edit.setText(text)


class LLMSettingsDialog(QDialog):
    """LLM 模型配置对话框。"""

    def __init__(
        self,
        llm_manager: object,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._llm_manager = llm_manager
        self._config: LLMConfig = llm_manager.get_config()  # type: ignore[union-attr]
        self.setWindowTitle("LLM 模型设置")
        self.setObjectName("llmSettingsDialog")
        self.setMinimumWidth(440)
        self.setModal(True)
        self._setup_ui()
        self._load_config()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(24, 20, 24, 20)

        # --- Provider 选择 ---
        provider_row = QHBoxLayout()
        provider_label = QLabel("Provider:")
        provider_label.setFixedWidth(90)
        provider_row.addWidget(provider_label)

        self._glm_btn = QPushButton("GLM")
        self._glm_btn.setCheckable(True)
        self._glm_btn.setObjectName("providerBtn")
        self._glm_btn.clicked.connect(lambda: self._select_provider("glm"))

        self._claude_btn = QPushButton("Claude")
        self._claude_btn.setCheckable(True)
        self._claude_btn.setObjectName("providerBtn")
        self._claude_btn.clicked.connect(lambda: self._select_provider("claude"))

        provider_row.addWidget(self._glm_btn)
        provider_row.addWidget(self._claude_btn)
        provider_row.addStretch()
        root.addLayout(provider_row)

        # --- API Key (stacked per provider) ---
        self._key_stack = QStackedWidget()
        self._glm_key = _ApiKeyRow()
        self._claude_key = _ApiKeyRow()
        self._key_stack.addWidget(self._glm_key)   # index 0
        self._key_stack.addWidget(self._claude_key)  # index 1

        key_row = QHBoxLayout()
        key_label = QLabel("API Key:")
        key_label.setFixedWidth(90)
        key_row.addWidget(key_label)
        key_row.addWidget(self._key_stack, 1)
        root.addLayout(key_row)

        # --- 模型选择 ---
        model_row = QHBoxLayout()
        model_label = QLabel("模型:")
        model_label.setFixedWidth(90)
        model_row.addWidget(model_label)

        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.setObjectName("modelCombo")
        model_row.addWidget(self._model_combo, 1)
        root.addLayout(model_row)

        # --- Temperature ---
        temp_row = QHBoxLayout()
        temp_label = QLabel("Temperature:")
        temp_label.setFixedWidth(90)
        temp_row.addWidget(temp_label)

        self._temp_slider = QSlider(Qt.Orientation.Horizontal)
        self._temp_slider.setRange(0, 100)
        self._temp_slider.setTickInterval(10)
        self._temp_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._temp_slider.valueChanged.connect(self._on_temp_changed)
        temp_row.addWidget(self._temp_slider, 1)

        self._temp_value = QLabel("0.7")
        self._temp_value.setFixedWidth(32)
        self._temp_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_row.addWidget(self._temp_value)
        root.addLayout(temp_row)

        # --- Form: smart switch / token budget / alert threshold ---
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(12)

        self._smart_switch = QCheckBox("启用失败自动降级")
        form.addRow("智能切换:", self._smart_switch)

        self._budget_spin = QSpinBox()
        self._budget_spin.setRange(1000, 10_000_000)
        self._budget_spin.setSingleStep(10000)
        self._budget_spin.setSuffix(" tokens")
        form.addRow("Token 预算:", self._budget_spin)

        self._alert_spin = QSpinBox()
        self._alert_spin.setRange(10, 100)
        self._alert_spin.setSingleStep(10)
        self._alert_spin.setSuffix(" %")
        form.addRow("告警阈值:", self._alert_spin)

        root.addLayout(form)

        # --- Max tokens ---
        max_tokens_row = QHBoxLayout()
        mt_label = QLabel("Max Tokens:")
        mt_label.setFixedWidth(90)
        max_tokens_row.addWidget(mt_label)

        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(256, 1_000_000)
        self._max_tokens_spin.setSingleStep(1024)
        max_tokens_row.addWidget(self._max_tokens_spin, 1)
        root.addLayout(max_tokens_row)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._save_btn = QPushButton("保存")
        self._save_btn.setObjectName("llmSaveBtn")
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setObjectName("llmCancelBtn")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        root.addLayout(btn_row)

    def _load_config(self) -> None:
        c = self._config
        self._select_provider(c.provider)
        self._glm_key.setText(c.glm_api_key)
        self._claude_key.setText(c.claude_api_key)
        self._model_combo.setCurrentText(c.model_name)
        self._temp_slider.setValue(int(c.temperature * 100))
        self._smart_switch.setChecked(c.smart_switch)
        self._budget_spin.setValue(c.token_budget)
        self._alert_spin.setValue(int(c.budget_alert_threshold * 100))
        self._max_tokens_spin.setValue(c.max_tokens)

    def _select_provider(self, provider: str) -> None:
        is_glm = provider == "glm"
        self._glm_btn.setChecked(is_glm)
        self._claude_btn.setChecked(not is_glm)
        self._key_stack.setCurrentIndex(0 if is_glm else 1)

        models = _GLM_MODELS if is_glm else _CLAUDE_MODELS
        current_text = self._model_combo.currentText()
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        self._model_combo.addItems(models)
        if current_text in models:
            self._model_combo.setCurrentText(current_text)
        self._model_combo.blockSignals(False)

        self._current_provider = provider

    def _on_temp_changed(self, value: int) -> None:
        self._temp_value.setText(f"{value / 100:.1f}")

    def _on_save(self) -> None:
        new_config = LLMConfig(
            provider=self._current_provider,
            glm_api_key=self._glm_key.text(),
            claude_api_key=self._claude_key.text(),
            model_name=self._model_combo.currentText(),
            temperature=self._temp_slider.value() / 100.0,
            max_tokens=self._max_tokens_spin.value(),
            smart_switch=self._smart_switch.isChecked(),
            token_budget=self._budget_spin.value(),
            budget_alert_threshold=self._alert_spin.value() / 100.0,
        )
        self._llm_manager.update_config(new_config)  # type: ignore[union-attr]
        self.accept()
