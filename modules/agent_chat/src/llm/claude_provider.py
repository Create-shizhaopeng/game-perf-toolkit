# -*- coding: utf-8 -*-
"""Claude (Anthropic) LLM Provider 实现。"""
from __future__ import annotations

import json
import logging
from typing import Any, Iterator

from ..models import (
    StreamChunk,
    StreamChunkType,
    ToolCall,
    ToolCallStatus,
    ToolDefinition,
)
from .base import LLMProvider

logger = logging.getLogger(__name__)

_PRESET_MODELS = ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"]


class ClaudeProvider(LLMProvider):
    """Anthropic Claude Provider。"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic SDK 未安装，请执行: pip install anthropic"
            ) from exc

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    @property
    def provider_name(self) -> str:
        return "claude"

    def get_available_models(self) -> list[str]:
        return list(_PRESET_MODELS)

    def stream_chat(
        self,
        messages: list[dict],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str = "",
    ) -> Iterator[StreamChunk]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = [_to_claude_tool(t) for t in tools]

        try:
            with self._client.messages.stream(**kwargs) as stream:
                current_tool: dict | None = None
                usage_data: dict[str, int] = {}

                for event in stream:
                    event_type = getattr(event, "type", "")

                    if event_type == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if block and getattr(block, "type", "") == "tool_use":
                            current_tool = {
                                "id": getattr(block, "id", ""),
                                "name": getattr(block, "name", ""),
                                "input_json": "",
                            }

                    elif event_type == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if not delta:
                            continue
                        delta_type = getattr(delta, "type", "")

                        if delta_type == "text_delta":
                            text = getattr(delta, "text", "")
                            if text:
                                yield StreamChunk(
                                    type=StreamChunkType.TEXT, data=text
                                )

                        elif delta_type == "input_json_delta":
                            partial = getattr(delta, "partial_json", "")
                            if current_tool and partial:
                                current_tool["input_json"] += partial

                    elif event_type == "content_block_stop":
                        if current_tool:
                            try:
                                args = (
                                    json.loads(current_tool["input_json"])
                                    if current_tool["input_json"]
                                    else {}
                                )
                            except json.JSONDecodeError:
                                args = {"_raw": current_tool["input_json"]}

                            yield StreamChunk(
                                type=StreamChunkType.TOOL_START,
                                data={
                                    "id": current_tool["id"],
                                    "name": current_tool["name"],
                                    "arguments": args,
                                },
                            )
                            current_tool = None

                    elif event_type == "message_delta":
                        msg_usage = getattr(event, "usage", None)
                        if msg_usage:
                            usage_data["completion_tokens"] = getattr(
                                msg_usage, "output_tokens", 0
                            )

                    elif event_type == "message_start":
                        msg = getattr(event, "message", None)
                        if msg:
                            msg_usage = getattr(msg, "usage", None)
                            if msg_usage:
                                usage_data["prompt_tokens"] = getattr(
                                    msg_usage, "input_tokens", 0
                                )

                if usage_data:
                    usage_data.setdefault("prompt_tokens", 0)
                    usage_data.setdefault("completion_tokens", 0)
                    usage_data["total_tokens"] = (
                        usage_data["prompt_tokens"]
                        + usage_data["completion_tokens"]
                    )
                    yield StreamChunk(type=StreamChunkType.USAGE, data=usage_data)

        except Exception as exc:
            logger.error("Claude API 调用失败: %s", exc)
            yield StreamChunk(
                type=StreamChunkType.ERROR,
                data=f"Claude API 错误: {exc}",
            )


def _to_claude_tool(td: ToolDefinition) -> dict[str, Any]:
    """将中间格式 ToolDefinition 转换为 Claude tools 参数。"""
    return {
        "name": td.name,
        "description": td.description,
        "input_schema": td.parameters or {"type": "object", "properties": {}},
    }
