# -*- coding: utf-8 -*-
"""LLM Provider 抽象基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from ..models import StreamChunk, ToolDefinition


class LLMProvider(ABC):
    """LLM Provider 接口。所有 Provider 实现此基类。"""

    @abstractmethod
    def stream_chat(
        self,
        messages: list[dict],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str = "",
    ) -> Iterator[StreamChunk]:
        """流式对话。

        Args:
            messages: 对话消息列表，格式 [{"role": "user", "content": "..."}]
            tools: 可用工具定义列表
            system_prompt: 系统提示词

        Yields:
            StreamChunk 流式输出块
        """
        ...

    def count_tokens(self, messages: list[dict]) -> int:
        """估算 token 数量（可选实现）。

        默认按字符数粗略估算：中文 1 字 ≈ 2 token，英文 1 词 ≈ 1 token。
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += len(content)
        return total

    @abstractmethod
    def get_available_models(self) -> list[str]:
        """返回预设模型列表。"""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 标识名称。"""
        ...
