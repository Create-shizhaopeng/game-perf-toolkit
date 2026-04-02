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
from modules.agent_chat.src.tools.executor import ToolExecutor
from modules.agent_chat.src.tools.registry import ToolRegistry


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


async def _async_iter(items):
    """将同步列表转为异步迭代器，供 mock stream_chat 使用。"""
    for item in items:
        yield item


def _make_mock_provider(return_chunks=None, side_effect=None):
    """创建 mock LLM provider，返回异步迭代器。"""
    mock_provider = MagicMock()
    if side_effect:
        mock_provider.stream_chat = side_effect
    elif return_chunks is not None:
        mock_provider.stream_chat = lambda *a, **k: _async_iter(return_chunks)
    return mock_provider


def _make_tool_registry(*tools: tuple[str, str]) -> tuple[ToolRegistry, ToolExecutor]:
    """创建含指定工具的 Registry + Executor。"""
    reg = ToolRegistry()
    for name, desc in tools:
        reg.register(ToolDefinition(name=name, description=desc))
    return reg, ToolExecutor(reg)


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

    @pytest.mark.asyncio
    async def test_simple_text_response(self, config, store):
        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = _make_mock_provider(
                return_chunks=_make_text_chunks("你好！我是 Agent。")
            )
            MockProv.return_value = mock_provider
            svc = AgentService(config=config, conversation_store=store)

        chunks_received = []
        response = await svc.chat(
            user_message="你好",
            on_chunk=lambda c: chunks_received.append(c),
        )

        assert response.text == "你好！我是 Agent。"
        assert response.usage["total_tokens"] == 30
        assert any(c.type == StreamChunkType.TEXT for c in chunks_received)

    @pytest.mark.asyncio
    async def test_chat_without_store(self, config):
        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = _make_mock_provider(
                return_chunks=_make_text_chunks("回复")
            )
            MockProv.return_value = mock_provider
            svc = AgentService(config=config)

        response = await svc.chat(user_message="test")
        assert response.text == "回复"

    @pytest.mark.asyncio
    async def test_chat_provider_not_ready(self):
        cfg = AgentConfig(provider="glm")
        svc = AgentService(config=cfg)

        chunks = []
        response = await svc.chat(
            user_message="test",
            on_chunk=lambda c: chunks.append(c),
        )
        assert "未初始化" in response.text
        assert any(c.type == StreamChunkType.ERROR for c in chunks)

    @pytest.mark.asyncio
    async def test_cancel_during_chat(self, config):
        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            async def slow_stream(*args, **kwargs):
                svc.cancel()
                yield StreamChunk(type=StreamChunkType.TEXT, data="开始")
                yield StreamChunk(type=StreamChunkType.TEXT, data="继续")

            mock_provider = _make_mock_provider(side_effect=slow_stream)
            MockProv.return_value = mock_provider
            svc = AgentService(config=config)

        response = await svc.chat(user_message="test")
        assert "[已取消]" in response.text


class TestServiceToolCalls:

    @pytest.mark.asyncio
    async def test_tool_call_and_response(self, config, store):
        call_count = 0

        async def mock_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                for c in _make_tool_call_chunks("analyze", {"path": "/tmp/trace"}):
                    yield c
            else:
                for c in _make_text_chunks("分析完成，发现 3 个卡顿。"):
                    yield c

        def analyze_fn(path: str) -> str:
            return "分析结果: 3 jank events"

        reg = ToolRegistry()
        reg.register(ToolDefinition(
            name="analyze", description="分析", method=analyze_fn,
        ))

        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = _make_mock_provider(side_effect=mock_stream)
            MockProv.return_value = mock_provider

            svc = AgentService(
                config=config,
                conversation_store=store,
                tool_registry=reg,
            )

        response = await svc.chat(user_message="分析这个 trace")
        assert "分析完成" in response.text
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_tool_failure_retry(self, config):
        attempt = 0

        async def mock_stream(*args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt <= 2:
                for c in _make_tool_call_chunks("broken_tool", {}):
                    yield c
            else:
                for c in _make_text_chunks("工具失败了"):
                    yield c

        def failing_fn():
            raise ValueError("工具出错")

        reg = ToolRegistry()
        reg.register(ToolDefinition(
            name="broken_tool", description="坏的", method=failing_fn,
        ))

        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = _make_mock_provider(side_effect=mock_stream)
            MockProv.return_value = mock_provider

            svc = AgentService(config=config, tool_registry=reg)

        await svc.chat(user_message="test")

    @pytest.mark.asyncio
    async def test_tool_result_truncation(self, config):
        cfg = AgentConfig(
            provider="glm",
            api_key="key",
            tool_result_max_length=50,
        )

        call_count = [0]

        def big_fn() -> str:
            call_count[0] += 1
            if call_count[0] <= 2:
                return "X" * 200
            return "done"

        reg = ToolRegistry()
        reg.register(ToolDefinition(
            name="big_tool", description="大结果", method=big_fn,
        ))

        async def mock_stream(*args, **kwargs):
            if call_count[0] < 2:
                for c in _make_tool_call_chunks("big_tool", {}):
                    yield c
            else:
                for c in _make_text_chunks("ok"):
                    yield c

        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = _make_mock_provider(side_effect=mock_stream)
            MockProv.return_value = mock_provider

            svc = AgentService(config=cfg, tool_registry=reg)

        chunks = []
        await svc.chat(user_message="test", on_chunk=lambda c: chunks.append(c))

        tool_end_chunks = [
            c for c in chunks if c.type == StreamChunkType.TOOL_END
        ]
        assert len(tool_end_chunks) >= 1

    @pytest.mark.asyncio
    async def test_no_executor_returns_error(self, config):
        call_count = [0]

        async def mock_stream(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                for c in _make_tool_call_chunks("some_tool", {}):
                    yield c
            else:
                for c in _make_text_chunks("ok"):
                    yield c

        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = _make_mock_provider(side_effect=mock_stream)
            MockProv.return_value = mock_provider
            svc = AgentService(config=config)

        response = await svc.chat(user_message="test")
        assert response.text is not None


class TestServiceSystemPrompt:

    @pytest.mark.asyncio
    async def test_default_chinese(self, config):
        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = MagicMock()
            MockProv.return_value = mock_provider
            mock_provider.stream_chat = lambda *a, **k: _async_iter(
                _make_text_chunks("ok")
            )
            svc = AgentService(config=config)

        await svc.chat(user_message="test")

        call_args = None
        original_stream = mock_provider.stream_chat
        captured_kwargs = {}

        async def capturing_stream(*args, **kwargs):
            captured_kwargs.update(kwargs)
            for c in _make_text_chunks("ok"):
                yield c

        mock_provider.stream_chat = capturing_stream
        await svc.chat(user_message="test2")

        system_prompt = captured_kwargs.get("system_prompt", "")
        assert "中文" in system_prompt or "Agent" in system_prompt

    @pytest.mark.asyncio
    async def test_english_prompt(self):
        cfg = AgentConfig(
            provider="glm", api_key="key", language="en"
        )
        captured_kwargs = {}

        async def capturing_stream(*args, **kwargs):
            captured_kwargs.update(kwargs)
            for c in _make_text_chunks("ok"):
                yield c

        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = MagicMock()
            MockProv.return_value = mock_provider
            mock_provider.stream_chat = capturing_stream
            svc = AgentService(config=cfg)

        await svc.chat(user_message="test")

        system_prompt = captured_kwargs.get("system_prompt", "")
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

    @pytest.mark.asyncio
    async def test_deposit_triggered_with_2_tools(self, config, store):
        call_count = 0

        async def mock_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                for c in _make_tool_call_chunks("tool_a", {}):
                    yield c
            elif call_count == 2:
                for c in _make_tool_call_chunks("tool_b", {}):
                    yield c
            else:
                for c in _make_text_chunks("完成"):
                    yield c

        def tool_fn() -> str:
            return "ok"

        reg = ToolRegistry()
        reg.register(ToolDefinition(name="tool_a", description="A", method=tool_fn))
        reg.register(ToolDefinition(name="tool_b", description="B", method=tool_fn))

        with patch(
            "modules.agent_chat.src.service.GLMProvider"
        ) as MockProv:
            mock_provider = _make_mock_provider(side_effect=mock_stream)
            MockProv.return_value = mock_provider

            svc = AgentService(
                config=config,
                conversation_store=store,
                tool_registry=reg,
            )

        chunks = []
        response = await svc.chat(
            user_message="test",
            on_chunk=lambda c: chunks.append(c),
        )

        assert response.workflow_deposit_ready is True
        assert len(response.workflow_summary["unique_tools"]) == 2
        deposit_chunks = [
            c for c in chunks if c.type == StreamChunkType.WORKFLOW_DEPOSIT
        ]
        assert len(deposit_chunks) == 1
