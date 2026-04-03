# -*- coding: utf-8 -*-
"""LLM Manager — Provider 生命周期管理、配置持久化、信号通知。"""
from __future__ import annotations

import logging
import threading
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal

from toolkit.sdk.models import LLMConfig

from .base import LLMProvider
from .models import get_context_window

logger = logging.getLogger(__name__)


class LLMState(str, Enum):
    UNCONFIGURED = "unconfigured"
    READY = "ready"
    DEGRADED = "degraded"
    ERROR = "error"
    BUDGET_PAUSED = "budget_paused"


class LLMManager(QObject):
    """框架层 LLM 能力管理中心。"""

    config_changed = pyqtSignal(object)
    provider_changed = pyqtSignal(str)
    token_updated = pyqtSignal(int, int)  # used, budget
    budget_alert = pyqtSignal(float)  # current_ratio
    error_occurred = pyqtSignal(str, str)  # error_type, message
    degradation_occurred = pyqtSignal(str, str)  # from_provider, to_provider

    def __init__(self, config_manager: object, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config_manager = config_manager
        self._lock = threading.Lock()
        self._try_migrate(config_manager)
        self._config = self._load_config()
        self._provider: LLMProvider | None = None
        self._session_tokens = 0
        self._context_tokens = 0
        self._budget_alerted = False
        self._budget_paused = False
        self._state = LLMState.UNCONFIGURED
        self._init_provider()

    @staticmethod
    def _try_migrate(config_manager: object) -> None:
        try:
            from .migration import migrate_agent_chat_llm

            migrate_agent_chat_llm(config_manager)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 配置迁移失败: %s", exc)

    def _load_config(self) -> LLMConfig:
        raw = {}
        if hasattr(self._config_manager, "get_llm_config"):
            raw = self._config_manager.get_llm_config()  # type: ignore[union-attr]
        try:
            return LLMConfig(**raw) if raw else LLMConfig()
        except Exception:
            logger.warning("LLM 配置解析失败，使用默认值")
            return LLMConfig()

    def _save_config(self) -> None:
        if hasattr(self._config_manager, "set_llm_config"):
            self._config_manager.set_llm_config(  # type: ignore[union-attr]
                self._config.model_dump()
            )

    def _init_provider(self) -> None:
        api_key = self._config.get_api_key()
        if not api_key:
            self._provider = None
            self._state = LLMState.UNCONFIGURED
            logger.info("LLM 未配置 API Key")
            return

        provider = self._config.provider
        try:
            from .litellm_provider import LiteLLMProvider

            self._provider = LiteLLMProvider(
                api_key=api_key,
                model=self._config.model_name,
                provider=provider,
            )
            self._state = LLMState.READY
            logger.info("LLM Provider 已初始化: %s (%s)", provider, self._config.model_name)
        except Exception as exc:
            logger.error("LLM Provider 初始化失败: %s", exc)
            self._provider = None
            self._state = LLMState.ERROR
            self.error_occurred.emit(type(exc).__name__, str(exc))

    def get_provider(self) -> LLMProvider | None:
        with self._lock:
            return self._provider

    def get_config(self) -> LLMConfig:
        return self._config.model_copy()

    @property
    def state(self) -> LLMState:
        return self._state

    def update_config(self, config: LLMConfig) -> None:
        self._config = config
        self._save_config()
        self._init_provider()
        self.config_changed.emit(config)
        if self._provider:
            self.provider_changed.emit(self._provider.provider_name)

    def switch_model(self, model_name: str) -> None:
        if model_name == self._config.model_name:
            return
        new_config = self._config.model_copy(update={"model_name": model_name})
        self.update_config(new_config)

    def record_tokens(self, count: int) -> None:
        with self._lock:
            self._session_tokens += count
            self._context_tokens = count

        used = self._session_tokens
        budget = self._config.token_budget
        self.token_updated.emit(used, budget)

        if budget > 0 and not self._budget_alerted:
            ratio = used / budget
            if ratio >= self._config.budget_alert_threshold:
                self._budget_alerted = True
                self.budget_alert.emit(ratio)

    def reset_session(self) -> None:
        with self._lock:
            self._session_tokens = 0
            self._context_tokens = 0
            self._budget_alerted = False
            self._budget_paused = False
        self.token_updated.emit(0, self._config.token_budget)

    def get_context_window_size(self) -> int:
        return get_context_window(self._config.model_name)

    def get_context_usage_ratio(self) -> float:
        window = self.get_context_window_size()
        if window <= 0:
            return 0.0
        return min(1.0, self._context_tokens / window)

    @property
    def session_tokens(self) -> int:
        return self._session_tokens

    @property
    def is_budget_paused(self) -> bool:
        return self._budget_paused

    def set_budget_paused(self, paused: bool) -> None:
        self._budget_paused = paused

    async def smart_stream_chat(
        self,
        messages: list[dict],
        tools: list | None = None,
        system_prompt: str = "",
    ):
        """带失败降级的流式对话。主 Provider 异常时自动切换到备用 Provider。"""
        from .base import StreamChunk as _SC

        provider = self.get_provider()
        if not provider:
            yield _SC(type="error", data="LLM Provider 未配置")
            return

        try:
            async for chunk in provider.stream_chat(messages, tools, system_prompt):
                yield chunk
        except Exception as primary_exc:
            if not self._config.smart_switch:
                yield _SC(type="error", data=str(primary_exc))
                return

            backup = "claude" if self._config.provider == "glm" else "glm"
            backup_key = self._config.get_api_key(backup)
            if not backup_key:
                yield _SC(type="error", data=str(primary_exc))
                return

            logger.warning(
                "主 Provider %s 失败，降级至 %s: %s",
                self._config.provider, backup, primary_exc,
            )
            self.degradation_occurred.emit(self._config.provider, backup)

            try:
                from .litellm_provider import LiteLLMProvider

                default_model = "glm-4-plus" if backup == "glm" else "claude-sonnet-4-20250514"
                fallback = LiteLLMProvider(
                    api_key=backup_key, model=default_model, provider=backup
                )

                async for chunk in fallback.stream_chat(
                    messages, tools, system_prompt
                ):
                    yield chunk
            except Exception as fallback_exc:
                logger.error("备用 Provider %s 也失败: %s", backup, fallback_exc)
                self._state = LLMState.ERROR
                self.error_occurred.emit(type(fallback_exc).__name__, str(fallback_exc))
                yield _SC(type="error", data=str(fallback_exc))
