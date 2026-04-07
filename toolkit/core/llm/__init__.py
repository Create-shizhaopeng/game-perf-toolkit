"""toolkit.core.llm — LLM 核心基础设施（基于 LiteLLM）"""

from .base import LLMProvider, StreamChunk, StreamChunkType, ToolDefinition
from .litellm_provider import LiteLLMProvider
from .manager import LLMManager

# 向后兼容：旧代码可能直接导入 GLMProvider / ClaudeProvider
# 现在统一使用 LiteLLMProvider
GLMProvider = LiteLLMProvider
ClaudeProvider = LiteLLMProvider

__all__ = [
    "ClaudeProvider",
    "GLMProvider",
    "LiteLLMProvider",
    "LLMManager",
    "LLMProvider",
    "StreamChunk",
    "StreamChunkType",
    "ToolDefinition",
]
