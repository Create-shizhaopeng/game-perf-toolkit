"""接口协议定义 — 使用 typing.Protocol 定义跨模块的接口契约"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class ServiceProtocol(Protocol):
    """模块服务协议 — 每个模块的 service.py 应满足此接口"""

    def get_service_info(self) -> dict[str, Any]: ...


@runtime_checkable
class AnalyzableService(Protocol):
    """可分析服务 — 提供分析功能的模块应满足此接口"""

    def analyze(self, input_data: BaseModel) -> BaseModel: ...


@runtime_checkable
class ComparableService(Protocol):
    """可对比服务 — 提供对比功能的模块应满足此接口"""

    def compare(self, result_a: BaseModel, result_b: BaseModel) -> dict: ...


@runtime_checkable
class LLMProviderProtocol(Protocol):
    """LLM Provider 协议 — 模块通过此协议使用 LLM 能力"""

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list | None = None,
        system_prompt: str = "",
    ) -> AsyncIterator: ...

    def count_tokens(self, messages: list[dict]) -> int: ...

    def get_available_models(self) -> list[str]: ...

    @property
    def provider_name(self) -> str: ...
