"""LLM Manager 数据模型 — Pydantic 验证。"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ModelConfig(BaseModel):
    """Provider 下的单个模型定义。"""

    name: str
    context_window: int = Field(default=128000, ge=1024)

    @property
    def context_label(self) -> str:
        """生成上下文窗口标签，如 [1M]、[200K]、[128K]。"""
        w = self.context_window
        if w >= 1_000_000:
            return f"[{w // 1_000_000}M]"
        if w >= 1_000:
            return f"[{w // 1_000}K]"
        return ""


class ProviderConfig(BaseModel):
    """单个 LLM Provider 的完整定义。"""

    id: str
    name: str
    base_url: str = ""
    litellm_prefix: str = ""
    api_key: str = ""
    enabled: bool = True
    thinking: bool = False
    thinking_budget: int = Field(default=4000, ge=1024)
    models: list[ModelConfig] = []
    default_model: str = ""

    @model_validator(mode="after")
    def _check_default_model(self) -> "ProviderConfig":
        models = [m.name for m in self.models]
        if self.default_model and self.default_model not in models:
            if models:
                self.default_model = models[0]
            else:
                self.default_model = ""
        elif not self.default_model and models:
            self.default_model = models[0]
        return self

    def get_model(self, name: str | None = None) -> ModelConfig | None:
        target = name or self.default_model
        for m in self.models:
            if m.name == target:
                return m
        return None


class LLMProvidersConfig(BaseModel):
    """llm_providers.json 根对象。"""

    providers: list[ProviderConfig] = []
    active_provider: str = ""

    @model_validator(mode="after")
    def _check_active(self) -> "LLMProvidersConfig":
        ids = {p.id for p in self.providers}
        if self.active_provider not in ids:
            if self.providers:
                self.active_provider = self.providers[0].id
            else:
                self.active_provider = ""
        return self

    def get_active(self) -> ProviderConfig | None:
        for p in self.providers:
            if p.id == self.active_provider:
                return p
        return None

    def get_provider(self, provider_id: str) -> ProviderConfig | None:
        for p in self.providers:
            if p.id == provider_id:
                return p
        return None
