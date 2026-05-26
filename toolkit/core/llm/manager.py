"""LLM Manager — Provider 生命周期管理、配置持久化、信号通知。"""
from __future__ import annotations

import logging
import threading
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal

from toolkit.sdk.models import LLMConfig

from .base import LLMProvider

logger = logging.getLogger(__name__)


class LLMState(str, Enum):
    UNCONFIGURED = "unconfigured"
    READY = "ready"
    ERROR = "error"


class LLMManager(QObject):
    """框架层 LLM 能力管理中心。

    从 LLMManagerService 读取 Provider 配置来初始化 LiteLLMProvider。
    """

    config_changed = pyqtSignal(object)
    provider_changed = pyqtSignal(str)
    token_updated = pyqtSignal(int, int)  # used, context_window
    error_occurred = pyqtSignal(str, str)

    def __init__(self, config_manager: object, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config_manager = config_manager
        self._service_registry = None
        self._lock = threading.Lock()
        self._try_migrate(config_manager)
        self._config = self._load_config()
        self._provider: LLMProvider | None = None
        self._session_tokens = 0
        self._context_tokens = 0
        self._context_window = 128000
        self._state = LLMState.UNCONFIGURED
        self._init_provider()

    def set_service_registry(self, registry: object) -> None:
        self._service_registry = registry

    def set_llm_service(self, service: object) -> None:
        self._llm_service = service

    def get_service(self, name: str):
        if name == "llm_manager_service" and hasattr(self, "_llm_service") and self._llm_service:
            return self._llm_service
        if self._service_registry and hasattr(self._service_registry, "get"):
            try:
                return self._service_registry.get(name)
            except KeyError:
                return None
        return None

    @staticmethod
    def _try_migrate(config_manager: object) -> None:
        try:
            from .migration import migrate_agent_chat_llm
            migrate_agent_chat_llm(config_manager)
        except Exception as exc:
            logger.warning("LLM 配置迁移失败: %s", exc)

    def _load_config(self) -> LLMConfig:
        raw = {}
        if hasattr(self._config_manager, "get_llm_config"):
            raw = self._config_manager.get_llm_config()
        try:
            return LLMConfig(**raw) if raw else LLMConfig()
        except Exception:
            logger.warning("LLM 配置解析失败，使用默认值")
            return LLMConfig()

    def _save_config(self) -> None:
        if hasattr(self._config_manager, "set_llm_config"):
            self._config_manager.set_llm_config(
                self._config.model_dump()
            )

    def _get_provider_config(self) -> tuple:
        """从 LLMManagerService 获取活跃 Provider 配置。"""
        svc = None
        if hasattr(self, "_llm_service") and self._llm_service:
            svc = self._llm_service
        else:
            svc = self.get_service("llm_manager_service")
        if svc:
            try:
                return svc.get_active_provider_config()
            except Exception:
                pass
        return None, None

    def _init_provider(self) -> None:
        prov_cfg, model_cfg = self._get_provider_config()

        if prov_cfg is None or not prov_cfg.api_key:
            self._provider = None
            self._state = LLMState.UNCONFIGURED
            logger.info("LLM 未配置 API Key")
            return

        try:
            from .litellm_provider import LiteLLMProvider

            thinking = None
            if prov_cfg.thinking:
                thinking = {
                    "type": "enabled",
                    "budget_tokens": prov_cfg.thinking_budget,
                }

            self._provider = LiteLLMProvider(
                api_key=prov_cfg.api_key,
                model=prov_cfg.default_model if model_cfg else self._config.model_name,
                provider=prov_cfg.id,
                litellm_prefix=prov_cfg.litellm_prefix,
                api_base=prov_cfg.base_url or None,
                thinking=thinking,
            )
            self._context_window = model_cfg.context_window if model_cfg else 128000
            self._config.model_name = prov_cfg.default_model
            self._config.provider = prov_cfg.id
            self._state = LLMState.READY
            logger.info(
                "LLM Provider 已初始化: %s (%s), api_base=%s, thinking=%s",
                prov_cfg.id, self._config.model_name,
                "custom" if prov_cfg.base_url else "default",
                "enabled" if thinking else "disabled",
            )
        except Exception as exc:
            logger.error("LLM Provider 初始化失败: %s", exc)
            self._provider = None
            self._state = LLMState.ERROR
            self.error_occurred.emit(type(exc).__name__, str(exc))

    def refresh_provider(self) -> None:
        """重新从 Service 加载 Provider 配置并初始化。"""
        self._init_provider()
        if self._provider:
            self.config_changed.emit(self._config)
            self.provider_changed.emit(self._provider.provider_name)

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

        self.token_updated.emit(self._session_tokens, self._context_window)

    def record_token_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        conversation_id: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        """供 Agent Chat 在收到 USAGE chunk 时调用。"""
        svc = self.get_service("llm_manager_service")
        if svc:
            try:
                tracker = svc.get_token_tracker()
                prov = self._provider.provider_name if self._provider else ""
                model = self._config.model_name
                tracker.record(
                    provider=prov,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    conversation_id=conversation_id,
                    trace_id=trace_id,
                )
            except Exception:
                logger.debug("Token record skipped (service not ready)")

    def reset_session(self) -> None:
        with self._lock:
            self._session_tokens = 0
            self._context_tokens = 0
        self.token_updated.emit(0, self._context_window)

    def get_context_window_size(self) -> int:
        return self._context_window

    def get_context_usage_ratio(self) -> float:
        if self._context_window <= 0:
            return 0.0
        return min(1.0, self._session_tokens / self._context_window)

    @property
    def session_tokens(self) -> int:
        return self._session_tokens

    async def smart_stream_chat(
        self,
        messages: list[dict],
        tools: list | None = None,
        system_prompt: str = "",
    ):
        """流式对话。异常时直接返回错误，不再有降级逻辑。"""
        from .base import StreamChunk as _SC

        provider = self.get_provider()
        if not provider:
            yield _SC(type="error", data="LLM Provider 未配置")
            return

        try:
            async for chunk in provider.stream_chat(messages, tools, system_prompt):
                yield chunk
        except Exception as exc:
            logger.error("LLM 请求失败: %s", exc)
            self._state = LLMState.ERROR
            self.error_occurred.emit(type(exc).__name__, str(exc))
            yield _SC(type="error", data=str(exc))
