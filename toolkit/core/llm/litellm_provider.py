# -*- coding: utf-8 -*-
"""统一 LLM Provider — 基于 LiteLLM 实现多 Provider 统一调用。

替代原先独立的 GLMProvider / ClaudeProvider，通过 LiteLLM 的
统一接口实现对 100+ 模型的支持。
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from .base import LLMProvider, StreamChunk, StreamChunkType, ToolDefinition

logger = logging.getLogger(__name__)

_PROVIDER_MODEL_MAP: dict[str, list[str]] = {
    "glm": ["glm-4-plus", "glm-4-flash", "glm-4-long"],
    "claude": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"],
}

_LITELLM_PREFIX: dict[str, str] = {
    "glm": "zai/",
    "claude": "",
}


def _to_litellm_model(provider: str, model: str) -> str:
    """将内部模型名称转换为 LiteLLM 路由格式。"""
    prefix = _LITELLM_PREFIX.get(provider, "")
    if prefix and not model.startswith(prefix):
        return f"{prefix}{model}"
    return model


def _to_openai_tool(td: ToolDefinition) -> dict[str, Any]:
    params = dict(td.parameters) if td.parameters else {"type": "object", "properties": {}}
    if "required" not in params:
        params["required"] = []
    return {
        "type": "function",
        "function": {
            "name": td.name,
            "description": td.description,
            "parameters": params,
        },
    }


class LiteLLMProvider(LLMProvider):
    """基于 LiteLLM 的统一 Provider 实现。"""

    def __init__(
        self,
        api_key: str,
        model: str = "glm-4-plus",
        provider: str = "glm",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._provider = provider
        self._litellm_model = _to_litellm_model(provider, model)

    @property
    def provider_name(self) -> str:
        return self._provider

    def get_available_models(self) -> list[str]:
        return list(_PROVIDER_MODEL_MAP.get(self._provider, []))

    def count_tokens(self, messages: list[dict]) -> int:
        try:
            import litellm

            return litellm.token_counter(
                model=self._litellm_model, messages=messages
            )
        except Exception:
            return super().count_tokens(messages)

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str = "",
    ) -> AsyncIterator[StreamChunk]:
        import litellm

        api_messages = list(messages)
        if system_prompt:
            api_messages = [
                {"role": "system", "content": system_prompt},
                *api_messages,
            ]

        kwargs: dict[str, Any] = {
            "model": self._litellm_model,
            "messages": api_messages,
            "api_key": self._api_key,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        if tools:
            kwargs["tools"] = [_to_openai_tool(t) for t in tools]

        logger.info(
            "LiteLLM 请求: model=%s, messages=%d, tools=%d",
            self._litellm_model,
            len(api_messages),
            len(kwargs.get("tools", [])),
        )

        tool_calls_acc: dict[int, dict] = {}
        got_usage = False
        full_text_parts: list[str] = []

        try:
            response = await litellm.acompletion(**kwargs)

            async for chunk in response:
                if not chunk.choices:
                    usage = getattr(chunk, "usage", None)
                    if usage:
                        got_usage = True
                        yield StreamChunk(
                            type=StreamChunkType.USAGE,
                            data={
                                "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                                "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                                "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                            },
                        )
                    continue

                delta = chunk.choices[0].delta
                if not delta:
                    continue

                if getattr(delta, "content", None):
                    full_text_parts.append(delta.content)
                    yield StreamChunk(
                        type=StreamChunkType.TEXT,
                        data=delta.content,
                    )

                if getattr(delta, "tool_calls", None):
                    for tc in delta.tool_calls:
                        idx = tc.index if hasattr(tc, "index") else 0
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {
                                "id": getattr(tc, "id", "") or "",
                                "name": "",
                                "arguments": "",
                            }
                        acc = tool_calls_acc[idx]
                        fn = getattr(tc, "function", None)
                        if fn:
                            if getattr(fn, "name", None):
                                acc["name"] = fn.name
                            if getattr(fn, "arguments", None):
                                acc["arguments"] += fn.arguments

                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage and not got_usage:
                    total = getattr(chunk_usage, "total_tokens", 0) or 0
                    if total:
                        got_usage = True
                        yield StreamChunk(
                            type=StreamChunkType.USAGE,
                            data={
                                "prompt_tokens": getattr(chunk_usage, "prompt_tokens", 0) or 0,
                                "completion_tokens": getattr(chunk_usage, "completion_tokens", 0) or 0,
                                "total_tokens": total,
                            },
                        )

            for acc in tool_calls_acc.values():
                try:
                    args = json.loads(acc["arguments"]) if acc["arguments"] else {}
                except json.JSONDecodeError:
                    args = {"_raw": acc["arguments"]}
                yield StreamChunk(
                    type=StreamChunkType.TOOL_START,
                    data={
                        "id": acc["id"],
                        "name": acc["name"],
                        "arguments": args,
                    },
                )

            if not got_usage:
                prompt_tokens = litellm.token_counter(
                    model=self._litellm_model, messages=api_messages
                )
                completion_text = "".join(full_text_parts)
                completion_tokens = litellm.token_counter(
                    model=self._litellm_model,
                    text=completion_text,
                )
                total_tokens = prompt_tokens + completion_tokens
                logger.debug(
                    "流式响应无 usage 数据，使用 token_counter 估算: %d",
                    total_tokens,
                )
                yield StreamChunk(
                    type=StreamChunkType.USAGE,
                    data={
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    },
                )

        except Exception as exc:
            logger.error("LiteLLM API 调用失败: %s", exc)
            yield StreamChunk(
                type=StreamChunkType.ERROR,
                data=f"LLM API 错误: {exc}",
            )
