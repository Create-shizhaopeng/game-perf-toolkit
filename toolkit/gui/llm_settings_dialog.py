"""LLM 模型设置对话框 — 精简版：Provider + Model + Thinking。"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.toolkit_dialog import ToolkitDialog, DialogCloseButton
from toolkit.gui import strings as s


def _format_model_label(name: str, context_window: int) -> str:
    """生成带上下文窗口标签的模型显示名，如 `[1M] claude-opus-4-7`。"""
    if context_window >= 1_000_000:
        label = f"[{context_window // 1_000_000}M]"
    elif context_window >= 1_000:
        label = f"[{context_window // 1_000}K]"
    else:
        return name
    return f"{label} {name}"


class LLMSettingsDialog(ToolkitDialog):
    """精简版 LLM 模型设置对话框。"""

    def __init__(
        self,
        llm_manager: object,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(s.LLM_SETTINGS_TITLE, parent)
        self.resize(440, 320)
        self._llm_manager = llm_manager
        self._config = llm_manager.get_config()

        body = QVBoxLayout()
        body.setSpacing(12)

        LABEL_W = 72

        def _label(text: str) -> QLabel:
            lb = QLabel(text)
            lb.setFixedWidth(LABEL_W)
            lb.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return lb

        # Provider
        row1 = QHBoxLayout()
        row1.addWidget(_label(s.LLM_SETTINGS_PROVIDER_LABEL))
        self._provider_combo = QComboBox()
        self._provider_combo.setObjectName("llmProviderCombo")
        self._provider_combo.setFixedHeight(28)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        row1.addWidget(self._provider_combo, 1)
        body.addLayout(row1)

        # Model
        row2 = QHBoxLayout()
        row2.addWidget(_label(s.LLM_SETTINGS_MODEL_LABEL))
        self._model_combo = QComboBox()
        self._model_combo.setObjectName("llmModelCombo")
        self._model_combo.setFixedHeight(28)
        row2.addWidget(self._model_combo, 1)
        body.addLayout(row2)

        # Base URL
        row_url = QHBoxLayout()
        row_url.addWidget(_label("Base URL:"))
        self._url_edit = QLineEdit()
        self._url_edit.setObjectName("llmUrlEdit")
        self._url_edit.setFixedHeight(28)
        self._url_edit.setPlaceholderText("留空使用默认地址")
        row_url.addWidget(self._url_edit, 1)
        body.addLayout(row_url)

        # API Key
        row_key = QHBoxLayout()
        row_key.addWidget(_label("API Key:"))
        self._apikey_edit = QLineEdit()
        self._apikey_edit.setObjectName("llmApiKeyEdit")
        self._apikey_edit.setFixedHeight(28)
        self._apikey_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._apikey_edit.setPlaceholderText("输入 API Key")
        row_key.addWidget(self._apikey_edit, 1)
        body.addLayout(row_key)

        # Thinking 开关
        self._thinking_check = QCheckBox(s.LLM_SETTINGS_THINKING)
        self._thinking_check.setObjectName("thinkingCheck")
        body.addWidget(self._thinking_check)

        # 按钮
        btn_row = QHBoxLayout()
        manage_btn = QPushButton(s.LLM_SETTINGS_MANAGE_PROVIDER)
        manage_btn.setObjectName("manageProviderBtn")
        manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        manage_btn.clicked.connect(self._on_manage_clicked)
        btn_row.addWidget(manage_btn)
        btn_row.addStretch()

        cancel_btn = QPushButton(s.LLM_SETTINGS_BTN_CANCEL)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton(s.LLM_SETTINGS_BTN_SAVE)
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        body.addLayout(btn_row)
        self.content_layout.addLayout(body)

        self._load_providers()
        self._load_config()

    # ------------------------------------------------------------------
    # Provider 列表
    # ------------------------------------------------------------------

    def _load_providers(self) -> None:
        """从 LLMManagerService 动态加载 Provider 列表。"""
        self._provider_combo.blockSignals(True)
        self._provider_combo.clear()
        self._providers: list = []

        try:
            svc = self._llm_manager.get_service("llm_manager_service")
            if svc:
                self._providers = svc.list_providers(enabled_only=True)
        except Exception:
            pass

        for prov in self._providers:
            self._provider_combo.addItem(prov.name, prov.id)

        self._provider_combo.blockSignals(False)

    def _on_provider_changed(self, idx: int) -> None:
        if idx < 0:
            return
        self._refresh_models(idx)

    # ------------------------------------------------------------------
    # 加载 / 保存
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        cfg = self._llm_manager.get_config()
        # 找到匹配的 provider
        idx = 0
        for i in range(self._provider_combo.count()):
            if self._provider_combo.itemData(i) == cfg.provider:
                idx = i
                break
        if self._provider_combo.count() > 0:
            self._provider_combo.setCurrentIndex(idx)
            # 显式刷新 model 列表（确保即使信号未触发也能填充）
            self._refresh_models(idx)

    def _refresh_models(self, idx: int) -> None:
        """显式根据 provider index 刷新 model 下拉。"""
        if idx < 0 or idx >= len(self._providers):
            self._model_combo.clear()
            return
        prov = self._providers[idx]
        self._model_combo.clear()
        for m in prov.models:
            label = _format_model_label(m.name, m.context_window)
            self._model_combo.addItem(label, m.name)
        if self._model_combo.count() > 0:
            self._model_combo.setCurrentIndex(0)

        self._thinking_check.setVisible(prov.thinking)
        if not prov.thinking:
            self._thinking_check.setChecked(False)
        self._url_edit.setText(prov.base_url)
        self._apikey_edit.setText(prov.api_key)

    def _on_save(self) -> None:
        from toolkit.sdk.models import LLMConfig

        prov_idx = self._provider_combo.currentIndex()
        model_idx = self._model_combo.currentIndex()

        model_name = self._model_combo.itemData(model_idx) if model_idx >= 0 else (
            self._model_combo.currentText() or "glm-4-plus"
        )
        provider_id = self._provider_combo.itemData(prov_idx) if prov_idx >= 0 else "glm"

        new_config = LLMConfig(provider=provider_id, model_name=model_name)
        self._llm_manager.update_config(new_config)

        # 同步 active provider/model 到 Service
        svc = self._llm_manager.get_service("llm_manager_service")
        if svc:
            try:
                svc.reload()
                svc.set_active_provider(provider_id)
                svc.set_active_model(model_name)
                self._llm_manager.refresh_provider()
            except Exception:
                pass

        self.accept()

    def _on_manage_clicked(self) -> None:
        import os
        from pathlib import Path
        config_path = Path.cwd() / "data" / "config" / "llm_providers.json"
        if config_path.exists():
            os.startfile(str(config_path))
        else:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("{}", encoding="utf-8")
            os.startfile(str(config_path))
