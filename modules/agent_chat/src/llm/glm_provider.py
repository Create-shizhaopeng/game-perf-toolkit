# -*- coding: utf-8 -*-
"""GLM (智谱) LLM Provider 实现。

直接使用 httpx + JWT 认证调用 GLM API，绕过 zhipuai SDK
以规避其 Pydantic V1 兼容层在 Python 3.14 上的 native crash。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator

from ..models import (
    StreamChunk,
    StreamChunkType,
    ToolCall,
    ToolCallStatus,
    ToolDefinition,
)
from .base import LLMProvider

logger = logging.getLogger(__name__)

_PRESET_MODELS = ["glm-4-plus", "glm-4-flash", "glm-4-long"]
_API_BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
_TOKEN_TTL_SEC = 3600
_REQUEST_TIMEOUT = 120


def _generate_jwt(api_key: str, exp_seconds: int = _TOKEN_TTL_SEC) -> str:
    """从 API Key 生成 JWT Token。"""
    import jwt as pyjwt

    try:
        key_id, secret = api_key.split(".")
    except ValueError as exc:
        raise ValueError("API Key 格式无效，应为 'id.secret'") from exc

    now_ms = int(round(time.time() * 1000))
    payload = {
        "api_key": key_id,
        "exp": now_ms + exp_seconds * 1000,
        "timestamp": now_ms,
    }
    return pyjwt.encode(
        payload,
        secret,
        algorithm="HS256",
        headers={"alg": "HS256", "sign_type": "SIGN"},
    )


class GLMProvider(LLMProvider):
    """智谱 GLM Provider — 直接 httpx 调用，不依赖 zhipuai SDK。"""

    def __init__(self, api_key: str, model: str = "glm-4-plus") -> None:
        import httpx

        self._api_key = api_key
        self._model = model
        self._async_client = httpx.AsyncClient(timeout=_REQUEST_TIMEOUT)
        self._token: str = ""
        self._token_exp: float = 0

    def _get_token(self) -> str:
        now = time.time()
        if not self._token or now >= self._token_exp:
            self._token = _generate_jwt(self._api_key)
            self._token_exp = now + _TOKEN_TTL_SEC - 60
        return self._token

    @property
    def provider_name(self) -> str:
        return "glm"

    def get_available_models(self) -> list[str]:
        return list(_PRESET_MODELS)

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str = "",
    ) -> AsyncIterator[StreamChunk]:
        body: dict[str, Any] = {
            "model": self._model,
            "stream": False,
        }

        api_messages = list(messages)
        if system_prompt:
            api_messages = [
                {"role": "system", "content": system_prompt},
                *api_messages,
            ]
        api_messages = _sanitize_messages(api_messages)
        body["messages"] = api_messages

        if tools:
            body["tools"] = [_to_openai_tool(t) for t in tools]

        logger.info(
            "GLM API 请求: model=%s, messages=%d, tools=%d",
            self._model,
            len(api_messages),
            len(body.get("tools", [])),
        )
        for i, m in enumerate(api_messages):
            logger.debug(
                "  msg[%d] role=%s keys=%s content_len=%d",
                i, m.get("role"), sorted(m.keys()), len(str(m.get("content", "") or "")),
            )

        try:
            token = self._get_token()
            logger.debug("[DIAG] GLM: 发送请求...")
            resp = await self._async_client.post(
                _API_BASE,
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            logger.debug("[DIAG] GLM: 响应状态=%d", resp.status_code)
            resp.raise_for_status()
            data = resp.json()
            logger.debug("[DIAG] GLM: JSON 解析完成, keys=%s", list(data.keys()))
        except Exception as exc:
            logger.error("GLM API 调用失败: %s", exc)
            yield StreamChunk(
                type=StreamChunkType.ERROR,
                data=f"GLM API 错误: {exc}",
            )
            return

        logger.debug("[DIAG] GLM: 开始 _parse_json_response")
        for chunk in _parse_json_response(data):
            yield chunk
        logger.debug("[DIAG] GLM: _parse_json_response 完成")


def _parse_json_response(data: dict[str, Any]) -> Iterator[StreamChunk]:
    """解析 GLM API JSON 响应，转换为 StreamChunk 序列。"""
    usage_raw = data.get("usage", {})
    usage_data: dict[str, int] = {}
    if usage_raw:
        usage_data = {
            "prompt_tokens": usage_raw.get("prompt_tokens", 0),
            "completion_tokens": usage_raw.get("completion_tokens", 0),
            "total_tokens": usage_raw.get("total_tokens", 0),
        }

    choices = data.get("choices", [])
    if not choices:
        if usage_data:
            yield StreamChunk(type=StreamChunkType.USAGE, data=usage_data)
        return

    message = choices[0].get("message", {})
    content = message.get("content", "") or ""

    if content:
        _CHUNK_SIZE = 20
        for i in range(0, len(content), _CHUNK_SIZE):
            yield StreamChunk(
                type=StreamChunkType.TEXT,
                data=content[i : i + _CHUNK_SIZE],
            )

    tool_calls_raw = message.get("tool_calls", []) or []
    for tc in tool_calls_raw:
        tc_id = tc.get("id", "")
        fn = tc.get("function", {})
        name = fn.get("name", "")
        args_str = fn.get("arguments", "")
        try:
            args = json.loads(args_str) if args_str else {}
        except json.JSONDecodeError:
            args = {"_raw": args_str}

        yield StreamChunk(
            type=StreamChunkType.TOOL_START,
            data={"id": tc_id, "name": name, "arguments": args},
        )

    if usage_data:
        yield StreamChunk(type=StreamChunkType.USAGE, data=usage_data)


def _sanitize_messages(messages: list[dict]) -> list[dict]:
    """清洗消息列表以确保符合 GLM (OpenAI) API 要求。

    规则：
    - assistant + tool_calls: arguments 必须是 JSON string
    - assistant + tool_calls + 无 content: content 设为 None
    - tool 消息必须有 tool_call_id
    - 移除未知字段
    """
    _VALID_KEYS = {
        "system": {"role", "content"},
        "user": {"role", "content"},
        "assistant": {"role", "content", "tool_calls"},
        "tool": {"role", "content", "tool_call_id"},
    }
    cleaned: list[dict] = []
    for msg in messages:
        role = msg.get("role", "")
        valid = _VALID_KEYS.get(role, set())
        out: dict[str, Any] = {k: v for k, v in msg.items() if k in valid}
        out["role"] = role

        if role == "assistant":
            if "tool_calls" in out and out["tool_calls"]:
                for tc in out["tool_calls"]:
                    fn = tc.get("function", {})
                    args = fn.get("arguments")
                    if args is not None and not isinstance(args, str):
                        fn["arguments"] = json.dumps(args, ensure_ascii=False)
                if not out.get("content"):
                    out["content"] = None
            else:
                out.pop("tool_calls", None)
                out.setdefault("content", "")

        elif role == "tool":
            if "tool_call_id" not in out:
                logger.warning("tool 消息缺少 tool_call_id，跳过")
                continue
            out.setdefault("content", "")

        elif role in ("system", "user"):
            out.setdefault("content", "")

        cleaned.append(out)
    return cleaned


def _to_openai_tool(td: ToolDefinition) -> dict[str, Any]:
    """将中间格式 ToolDefinition 转换为 OpenAI 兼容的 tools 参数。"""
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
