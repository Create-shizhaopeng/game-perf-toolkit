# -*- coding: utf-8 -*-
"""agent_chat 模块 — AgentService 测试（mock LLM）。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.agent_chat.src.memory.conversation import ConversationStore
from modules.agent_chat.src.models import (
    AgentConfig,
    StreamChunk,
    StreamChunkType,
    ToolCall,
    ToolCallStatus,
    ToolDefinition,
    ToolResult,
)
from modules.agent_chat.src.service import AgentService


def _make_text_chunks(text: str) -> list[StreamChunk]:
    """模拟 LLM 返回纯文本。"""
    return [
        StreamChunk(type=StreamChunkType.TEXT, data=text),
        StreamChunk(type=StreamChunkType.USAGE, data={
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }),
    ]


def _make_tool_call_chunks(name: str, args: dict) -> list[StreamChunk]:
    """模拟 LLM 返回工具调用。"""
    import json
    return [
        StreamChunk(type=StreamChunkType.TOOL_START, data={
            "id": "call_001",
            "name": name,
            "arguments": args,
        }),
        StreamChunk(type=StreamChunkType.USAGE, data={
            "prompt_tokens": 15,
            "completion_tokens": 10,
            "total_tokens": 25,
        }),
    ]


@pytest.fixture
def store(tmp_path: Path):
    db = tmp_path / "test_svc.db"
    s = ConversationStore(db)
    yield s
    s.close()


@pytest.fixture
def config():
    return AgentConfig(
        provider="glm",
        api_key="test-key",
        model_name="glm-4-plus",
    )


class TestServiceInit:

    def test_is_ready_with_key(self, config: AgentConfig):
        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            svc = AgentService(config=config)
        assert svc.is_ready

    def test_not_ready_without_key(self):
        cfg = AgentConfig(provider="glm")
        svc = AgentService(config=cfg)
        assert not svc.is_ready

    def test_unsupported_provider(self):
        cfg = AgentConfig(provider="unknown", api_key="key")
        svc = AgentService(config=cfg)
        assert not svc.is_ready


class TestServiceChat:

    def test_simple_text_response(self, config, store):
        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = MagicMock()
            MockProv.return_value = mock_provider
            mock_provider.stream_chat.return_value = iter(
                _make_text_chunks("你好！我是 Agent。")
            )

            svc = AgentService(config=config, conversation_store=store)

        chunks_received = []
        response = svc.chat(
            user_message="你好",
            on_chunk=lambda c: chunks_received.append(c),
        )

        assert response.text == "你好！我是 Agent。"
        assert response.usage["total_tokens"] == 30
        assert any(c.type == StreamChunkType.TEXT for c in chunks_received)

    def test_chat_without_store(self, config):
        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = MagicMock()
            MockProv.return_value = mock_provider
            mock_provider.stream_chat.return_value = iter(
                _make_text_chunks("回复")
            )

            svc = AgentService(config=config)

        response = svc.chat(user_message="test")
        assert response.text == "回复"

    def test_chat_provider_not_ready(self):
        cfg = AgentConfig(provider="glm")
        svc = AgentService(config=cfg)

        chunks = []
        response = svc.chat(
            user_message="test",
            on_chunk=lambda c: chunks.append(c),
        )
        assert "未初始化" in response.text
        assert any(c.type == StreamChunkType.ERROR for c in chunks)

    def test_cancel_during_chat(self, config):
        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = MagicMock()
            MockProv.return_value = mock_provider

            def slow_stream(*args, **kwargs):
                svc.cancel()
                yield StreamChunk(type=StreamChunkType.TEXT, data="开始")
                yield StreamChunk(type=StreamChunkType.TEXT, data="继续")

            mock_provider.stream_chat.side_effect = slow_stream

            svc = AgentService(config=config)

        response = svc.chat(user_message="test")
        assert "[已取消]" in response.text


class TestServiceToolCalls:

    def test_tool_call_and_response(self, config, store):
        call_count = 0

        def mock_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return iter(_make_tool_call_chunks(
                    "analyze", {"path": "/tmp/trace"}
                ))
            else:
                return iter(_make_text_chunks("分析完成，发现 3 个卡顿。"))

        def mock_executor(tc: ToolCall) -> ToolResult:
            return ToolResult(
                tool_call_id=tc.id,
                content="分析结果: 3 jank events",
                report_paths=["/out/report.md"],
            )

        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = MagicMock()
            MockProv.return_value = mock_provider
            mock_provider.stream_chat.side_effect = mock_stream

            svc = AgentService(
                config=config,
                conversation_store=store,
                tool_definitions=[
                    ToolDefinition(name="analyze", description="分析"),
                ],
                tool_executor=mock_executor,
            )

        response = svc.chat(user_message="分析这个 trace")
        assert "分析完成" in response.text
        assert call_count == 2

    def test_tool_failure_retry(self, config):
        attempt = 0

        def mock_stream(*args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt <= 2:
                return iter(_make_tool_call_chunks("broken_tool", {}))
            return iter(_make_text_chunks("工具失败了"))

        fail_count = 0

        def failing_executor(tc: ToolCall) -> ToolResult:
            nonlocal fail_count
            fail_count += 1
            return ToolResult(
                tool_call_id=tc.id,
                content="执行失败",
                is_error=True,
            )

        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = MagicMock()
            MockProv.return_value = mock_provider
            mock_provider.stream_chat.side_effect = mock_stream

            svc = AgentService(
                config=config,
                tool_definitions=[
                    ToolDefinition(name="broken_tool", description="坏的"),
                ],
                tool_executor=failing_executor,
            )

        svc.chat(user_message="test")
        assert fail_count >= 2

    def test_tool_result_truncation(self, config):
        cfg = AgentConfig(
            provider="glm",
            api_key="key",
            tool_result_max_length=50,
        )

        def mock_stream(*args, **kwargs):
            return iter(_make_tool_call_chunks("big_tool", {}))

        call_count = [0]

        def executor(tc: ToolCall) -> ToolResult:
            call_count[0] += 1
            if call_count[0] <= 2:
                return ToolResult(
                    tool_call_id=tc.id,
                    content="X" * 200,
                )
            return ToolResult(
                tool_call_id=tc.id,
                content="done",
            )

        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = MagicMock()
            MockProv.return_value = mock_provider

            def side_effect(*a, **k):
                if call_count[0] < 2:
                    return iter(_make_tool_call_chunks("big_tool", {}))
                return iter(_make_text_chunks("ok"))

            mock_provider.stream_chat.side_effect = side_effect

            svc = AgentService(
                config=cfg,
                tool_definitions=[
                    ToolDefinition(name="big_tool", description="大结果"),
                ],
                tool_executor=executor,
            )

        chunks = []
        svc.chat(user_message="test", on_chunk=lambda c: chunks.append(c))

        tool_end_chunks = [
            c for c in chunks if c.type == StreamChunkType.TOOL_END
        ]
        assert len(tool_end_chunks) >= 1

    def test_no_executor_returns_error(self, config):
        def mock_stream(*args, **kwargs):
            return iter(_make_tool_call_chunks("some_tool", {}))

        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = MagicMock()
            MockProv.return_value = mock_provider

            call_count = [0]

            def side_effect(*a, **k):
                call_count[0] += 1
                if call_count[0] == 1:
                    return iter(_make_tool_call_chunks("some_tool", {}))
                return iter(_make_text_chunks("ok"))

            mock_provider.stream_chat.side_effect = side_effect

            svc = AgentService(config=config)

        response = svc.chat(user_message="test")
        assert response.text is not None


class TestServiceSystemPrompt:

    def test_default_chinese(self, config):
        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = MagicMock()
            MockProv.return_value = mock_provider
            mock_provider.stream_chat.return_value = iter(
                _make_text_chunks("ok")
            )

            svc = AgentService(config=config)

        svc.chat(user_message="test")

        call_args = mock_provider.stream_chat.call_args
        system_prompt = call_args.kwargs.get("system_prompt", "")
        assert "中文" in system_prompt or "Agent" in system_prompt

    def test_english_prompt(self):
        cfg = AgentConfig(
            provider="glm", api_key="key", language="en"
        )
        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = MagicMock()
            MockProv.return_value = mock_provider
            mock_provider.stream_chat.return_value = iter(
                _make_text_chunks("ok")
            )

            svc = AgentService(config=cfg)

        svc.chat(user_message="test")

        call_args = mock_provider.stream_chat.call_args
        system_prompt = call_args.kwargs.get("system_prompt", "")
        assert "English" in system_prompt or "Agent" in system_prompt

    def test_trim_system_prompt_short(self, config):
        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            MockProv.return_value = MagicMock()
            svc = AgentService(config=config)

        short = "短文本"
        assert svc._trim_system_prompt(short) == short

    def test_trim_system_prompt_long(self, config):
        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            MockProv.return_value = MagicMock()
            svc = AgentService(config=config)

        sections = ["核心指令" * 100, "工具列表" * 100, "最近分析报告:\n  1. r1\n  2. r2\n  3. r3\n  4. r4"]
        long_prompt = "\n\n".join(sections)

        trimmed = svc._trim_system_prompt(long_prompt, max_chars=500)
        assert len(trimmed) < len(long_prompt)


class TestServiceWorkflowDeposit:

    def test_deposit_triggered_with_2_tools(self, config, store):
        call_count = 0

        def mock_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return iter(_make_tool_call_chunks("tool_a", {}))
            elif call_count == 2:
                return iter(_make_tool_call_chunks("tool_b", {}))
            else:
                return iter(_make_text_chunks("完成"))

        def executor(tc: ToolCall) -> ToolResult:
            return ToolResult(tool_call_id=tc.id, content="ok")

        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = MagicMock()
            MockProv.return_value = mock_provider
            mock_provider.stream_chat.side_effect = mock_stream

            svc = AgentService(
                config=config,
                conversation_store=store,
                tool_definitions=[
                    ToolDefinition(name="tool_a", description="A"),
                    ToolDefinition(name="tool_b", description="B"),
                ],
                tool_executor=executor,
            )

        chunks = []
        response = svc.chat(
            user_message="test",
            on_chunk=lambda c: chunks.append(c),
        )

        assert response.workflow_deposit_ready is True
        assert len(response.workflow_summary["unique_tools"]) == 2
        deposit_chunks = [
            c for c in chunks if c.type == StreamChunkType.WORKFLOW_DEPOSIT
        ]
        assert len(deposit_chunks) == 1
