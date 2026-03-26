# -*- coding: utf-8 -*-
"""agent_chat 模块 — LLM Provider 测试（mock SDK）。"""
from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from modules.agent_chat.src.llm.base import LLMProvider
from modules.agent_chat.src.models import (
    StreamChunk,
    StreamChunkType,
    ToolDefinition,
)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class TestLLMProviderBase:

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            LLMProvider()

    def test_default_count_tokens(self):
        class DummyProvider(LLMProvider):
            def stream_chat(self, messages, tools=None, system_prompt=""):
                yield from []
            def get_available_models(self):
                return []
            @property
            def provider_name(self):
                return "dummy"

        p = DummyProvider()
        count = p.count_tokens([
            {"role": "user", "content": "hello world"},
        ])
        assert count == len("hello world")


# ---------------------------------------------------------------------------
# GLM Provider
# ---------------------------------------------------------------------------

class TestGLMProvider:

    def _make_api_json(self, content="", tool_calls=None, prompt=10, completion=20, total=30):
        """构造 GLM API 原始 JSON 响应。"""
        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        return {
            "choices": [{"message": msg, "index": 0, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": total,
            },
        }

    def _make_provider(self, response_json=None, side_effect=None):
        """创建带 mock httpx 的 GLMProvider 实例。"""
        from modules.agent_chat.src.llm.glm_provider import GLMProvider

        provider = GLMProvider.__new__(GLMProvider)
        provider._api_key = "test_id.test_secret"
        provider._model = "glm-4-plus"
        provider._token = "mock_token"
        provider._token_exp = time.time() + 3600

        mock_client = MagicMock()
        if side_effect:
            mock_client.post.side_effect = side_effect
        else:
            mock_resp = MagicMock()
            mock_resp.json.return_value = response_json or {}
            mock_resp.raise_for_status.return_value = None
            mock_client.post.return_value = mock_resp
        provider._client = mock_client
        return provider

    def test_stream_text(self):
        resp = self._make_api_json(content="你好世界")
        provider = self._make_provider(response_json=resp)

        results = list(provider.stream_chat([{"role": "user", "content": "hi"}]))

        text_chunks = [r for r in results if r.type == StreamChunkType.TEXT]
        assert len(text_chunks) >= 1
        full_text = "".join(c.data for c in text_chunks)
        assert full_text == "你好世界"

        usage_chunks = [r for r in results if r.type == StreamChunkType.USAGE]
        assert len(usage_chunks) == 1
        assert usage_chunks[0].data["total_tokens"] == 30

    def test_stream_error(self):
        provider = self._make_provider(side_effect=Exception("网络超时"))

        results = list(provider.stream_chat([{"role": "user", "content": "hi"}]))
        assert len(results) == 1
        assert results[0].type == StreamChunkType.ERROR
        assert "网络超时" in str(results[0].data)

    def test_stream_tool_call(self):
        tc_data = {
            "id": "call_abc",
            "type": "function",
            "function": {
                "name": "analyze",
                "arguments": '{"path": "/tmp/trace"}',
            },
        }
        resp = self._make_api_json(content="", tool_calls=[tc_data])
        provider = self._make_provider(response_json=resp)

        results = list(provider.stream_chat(
            [{"role": "user", "content": "分析"}],
            tools=[ToolDefinition(name="analyze", description="分析 trace")],
        ))

        tool_chunks = [r for r in results if r.type == StreamChunkType.TOOL_START]
        assert len(tool_chunks) == 1
        assert tool_chunks[0].data["name"] == "analyze"

    def test_available_models(self):
        provider = self._make_provider(response_json={})
        models = provider.get_available_models()
        assert "glm-4-plus" in models
        assert "glm-4-flash" in models

    def test_provider_name(self):
        provider = self._make_provider(response_json={})
        assert provider.provider_name == "glm"


# ---------------------------------------------------------------------------
# Claude Provider
# ---------------------------------------------------------------------------

class TestClaudeProvider:

    @patch("modules.agent_chat.src.llm.claude_provider.anthropic", create=True)
    def test_provider_name(self, mock_mod):
        from modules.agent_chat.src.llm.claude_provider import ClaudeProvider

        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            provider = ClaudeProvider.__new__(ClaudeProvider)

        assert provider.provider_name == "claude"

    @patch("modules.agent_chat.src.llm.claude_provider.anthropic", create=True)
    def test_available_models(self, mock_mod):
        from modules.agent_chat.src.llm.claude_provider import ClaudeProvider

        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            provider = ClaudeProvider.__new__(ClaudeProvider)

        models = provider.get_available_models()
        assert "claude-sonnet-4-20250514" in models

    @patch("modules.agent_chat.src.llm.claude_provider.anthropic", create=True)
    def test_stream_error(self, mock_mod):
        from modules.agent_chat.src.llm.claude_provider import ClaudeProvider

        client = MagicMock()
        mock_mod.Anthropic.return_value = client
        client.messages.stream.side_effect = Exception("API 限流")

        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            provider = ClaudeProvider.__new__(ClaudeProvider)
            provider._client = client
            provider._model = "claude-sonnet-4-20250514"

        results = list(provider.stream_chat([{"role": "user", "content": "hi"}]))
        assert len(results) == 1
        assert results[0].type == StreamChunkType.ERROR

    @patch("modules.agent_chat.src.llm.claude_provider.anthropic", create=True)
    def test_stream_text_success(self, mock_mod):
        """Claude streaming 文本成功路径。"""
        from modules.agent_chat.src.llm.claude_provider import ClaudeProvider

        client = MagicMock()
        mock_mod.Anthropic.return_value = client

        msg_start_event = MagicMock()
        msg_start_event.type = "message_start"
        msg_start_msg = MagicMock()
        msg_start_usage = MagicMock()
        msg_start_usage.input_tokens = 15
        msg_start_msg.usage = msg_start_usage
        msg_start_event.message = msg_start_msg

        text_delta_event = MagicMock()
        text_delta_event.type = "content_block_delta"
        text_delta = MagicMock()
        text_delta.type = "text_delta"
        text_delta.text = "你好世界"
        text_delta_event.delta = text_delta

        msg_delta_event = MagicMock()
        msg_delta_event.type = "message_delta"
        msg_delta_usage = MagicMock()
        msg_delta_usage.output_tokens = 10
        msg_delta_event.usage = msg_delta_usage

        stream_ctx = MagicMock()
        stream_ctx.__enter__ = MagicMock(return_value=stream_ctx)
        stream_ctx.__exit__ = MagicMock(return_value=False)
        stream_ctx.__iter__ = MagicMock(
            return_value=iter([msg_start_event, text_delta_event, msg_delta_event])
        )
        client.messages.stream.return_value = stream_ctx

        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            provider = ClaudeProvider.__new__(ClaudeProvider)
            provider._client = client
            provider._model = "claude-sonnet-4-20250514"

        results = list(provider.stream_chat([{"role": "user", "content": "hi"}]))
        text_chunks = [r for r in results if r.type == StreamChunkType.TEXT]
        assert len(text_chunks) == 1
        assert text_chunks[0].data == "你好世界"

        usage_chunks = [r for r in results if r.type == StreamChunkType.USAGE]
        assert len(usage_chunks) == 1
        assert usage_chunks[0].data["prompt_tokens"] == 15

    @patch("modules.agent_chat.src.llm.claude_provider.anthropic", create=True)
    def test_stream_tool_call(self, mock_mod):
        """Claude streaming 工具调用路径。"""
        from modules.agent_chat.src.llm.claude_provider import ClaudeProvider

        client = MagicMock()
        mock_mod.Anthropic.return_value = client

        block_start = MagicMock()
        block_start.type = "content_block_start"
        block = MagicMock()
        block.type = "tool_use"
        block.id = "toolu_abc"
        block.name = "pa_analyze"
        block_start.content_block = block

        input_delta = MagicMock()
        input_delta.type = "content_block_delta"
        delta = MagicMock()
        delta.type = "input_json_delta"
        delta.partial_json = '{"path": "/tmp"}'
        input_delta.delta = delta

        block_stop = MagicMock()
        block_stop.type = "content_block_stop"

        stream_ctx = MagicMock()
        stream_ctx.__enter__ = MagicMock(return_value=stream_ctx)
        stream_ctx.__exit__ = MagicMock(return_value=False)
        stream_ctx.__iter__ = MagicMock(
            return_value=iter([block_start, input_delta, block_stop])
        )
        client.messages.stream.return_value = stream_ctx

        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            provider = ClaudeProvider.__new__(ClaudeProvider)
            provider._client = client
            provider._model = "claude-sonnet-4-20250514"

        results = list(provider.stream_chat(
            [{"role": "user", "content": "分析"}],
            tools=[ToolDefinition(name="pa_analyze", description="分析")],
        ))
        tool_chunks = [r for r in results if r.type == StreamChunkType.TOOL_START]
        assert len(tool_chunks) == 1
        assert tool_chunks[0].data["name"] == "pa_analyze"
        assert tool_chunks[0].data["arguments"]["path"] == "/tmp"


# ---------------------------------------------------------------------------
# GLM _sanitize_messages
# ---------------------------------------------------------------------------

class TestGLMSanitizeMessages:

    def test_basic_user_message(self):
        from modules.agent_chat.src.llm.glm_provider import _sanitize_messages
        msgs = [{"role": "user", "content": "hello"}]
        result = _sanitize_messages(msgs)
        assert result == [{"role": "user", "content": "hello"}]

    def test_strips_unknown_fields(self):
        from modules.agent_chat.src.llm.glm_provider import _sanitize_messages
        msgs = [{"role": "user", "content": "hi", "extra_field": "drop_me"}]
        result = _sanitize_messages(msgs)
        assert "extra_field" not in result[0]

    def test_assistant_tool_calls_args_serialized(self):
        from modules.agent_chat.src.llm.glm_provider import _sanitize_messages
        msgs = [{
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "c1",
                "function": {"name": "test", "arguments": {"a": 1}},
            }],
        }]
        result = _sanitize_messages(msgs)
        args = result[0]["tool_calls"][0]["function"]["arguments"]
        assert isinstance(args, str)
        assert result[0]["content"] is None

    def test_tool_message_without_id_skipped(self):
        from modules.agent_chat.src.llm.glm_provider import _sanitize_messages
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "tool", "content": "result"},
        ]
        result = _sanitize_messages(msgs)
        assert len(result) == 1

    def test_tool_message_with_id_kept(self):
        from modules.agent_chat.src.llm.glm_provider import _sanitize_messages
        msgs = [{"role": "tool", "content": "ok", "tool_call_id": "c1"}]
        result = _sanitize_messages(msgs)
        assert len(result) == 1
        assert result[0]["tool_call_id"] == "c1"

    def test_system_message_default_content(self):
        from modules.agent_chat.src.llm.glm_provider import _sanitize_messages
        msgs = [{"role": "system"}]
        result = _sanitize_messages(msgs)
        assert result[0]["content"] == ""

    def test_assistant_without_tool_calls_strips_empty(self):
        from modules.agent_chat.src.llm.glm_provider import _sanitize_messages
        msgs = [{"role": "assistant", "content": "ok", "tool_calls": []}]
        result = _sanitize_messages(msgs)
        assert "tool_calls" not in result[0]


class TestGLMToOpenAITool:

    def test_basic_conversion(self):
        from modules.agent_chat.src.llm.glm_provider import _to_openai_tool
        td = ToolDefinition(
            name="test",
            description="测试",
            parameters={"type": "object", "properties": {"a": {"type": "string"}}},
        )
        result = _to_openai_tool(td)
        assert result["type"] == "function"
        assert result["function"]["name"] == "test"
        assert "required" in result["function"]["parameters"]

    def test_empty_params_generates_defaults(self):
        from modules.agent_chat.src.llm.glm_provider import _to_openai_tool
        td = ToolDefinition(name="t", description="d")
        result = _to_openai_tool(td)
        params = result["function"]["parameters"]
        assert params["type"] == "object"
        assert params["properties"] == {}
        assert params["required"] == []
