# -*- coding: utf-8 -*-
"""向后兼容层 — 从 toolkit.core.llm 重新导出。

新代码应直接使用 toolkit.core.llm。
"""
from toolkit.core.llm.base import LLMProvider, StreamChunk, ToolDefinition
from toolkit.core.llm.litellm_provider import LiteLLMProvider

# 向后兼容别名
GLMProvider = LiteLLMProvider
ClaudeProvider = LiteLLMProvider

__all__ = [
    "ClaudeProvider",
    "GLMProvider",
    "LLMProvider",
    "LiteLLMProvider",
    "StreamChunk",
    "ToolDefinition",
]
