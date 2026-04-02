# -*- coding: utf-8 -*-
"""Sub-agent 管理层测试。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.agent_chat.src.models import (
    AgentConfig,
    LLMResponse,
    SubAgentConfig,
    SubAgentResult,
    SubAgentStatus,
    ProviderCapabilities,
    ToolDefinition,
)


class TestSubAgentModels:
    def test_subagent_config_defaults(self) -> None:
        cfg = SubAgentConfig(task_description="分析 trace")
        assert cfg.max_turns == 15
        assert cfg.timeout == 120
        assert cfg.skill_names == []

    def test_subagent_result_defaults(self) -> None:
        r = SubAgentResult(task_id="t1")
        assert r.status == SubAgentStatus.PENDING
        assert r.retries == 0

    def test_provider_capabilities(self) -> None:
        cap = ProviderCapabilities(name="glm")
        assert cap.max_context_tokens == 128_000
        assert cap.supports_tools is True


class TestSubAgentManager:
    @pytest.fixture
    def agent_config(self) -> AgentConfig:
        return AgentConfig(
            provider="glm",
            api_key="test-key",
            model_name="glm-4-plus",
        )

    @pytest.mark.asyncio
    async def test_create_and_run_success(self, agent_config: AgentConfig) -> None:
        from modules.agent_chat.src.subagent.manager import SubAgentManager

        mgr = SubAgentManager(parent_config=agent_config)

        mock_response = LLMResponse(text="分析结论: 主线程阻塞", tool_calls=[])
        with patch.object(mgr, "_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"text": "分析结论: 主线程阻塞", "tool_calls_count": 3}
            result = await mgr.create_and_run(
                SubAgentConfig(task_description="分析 trace 卡顿")
            )

        assert result.status == SubAgentStatus.COMPLETED
        assert "主线程阻塞" in result.summary
        assert result.tool_calls_count == 3
        assert result.elapsed_seconds >= 0

    @pytest.mark.asyncio
    async def test_create_and_run_failure_all_retries(self, agent_config: AgentConfig) -> None:
        from modules.agent_chat.src.subagent.manager import SubAgentManager

        mgr = SubAgentManager(parent_config=agent_config)

        with patch.object(mgr, "_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = RuntimeError("Provider 连接超时")
            result = await mgr.create_and_run(
                SubAgentConfig(task_description="失败任务", timeout=5)
            )

        assert result.status == SubAgentStatus.FAILED
        assert result.retries == 2  # 3 attempts = 2 retries
        assert "超时" in (result.error or "")

    @pytest.mark.asyncio
    async def test_create_and_run_retry_then_success(self, agent_config: AgentConfig) -> None:
        from modules.agent_chat.src.subagent.manager import SubAgentManager

        mgr = SubAgentManager(parent_config=agent_config)

        call_count = 0

        async def flaky_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("临时错误")
            return {"text": "第二次成功", "tool_calls_count": 1}

        with patch.object(mgr, "_execute", side_effect=flaky_execute):
            result = await mgr.create_and_run(
                SubAgentConfig(task_description="重试任务")
            )

        assert result.status == SubAgentStatus.COMPLETED
        assert result.retries == 1

    @pytest.mark.asyncio
    async def test_status_callback(self, agent_config: AgentConfig) -> None:
        from modules.agent_chat.src.subagent.manager import SubAgentManager

        updates: list[SubAgentStatus] = []

        def on_update(r: SubAgentResult) -> None:
            updates.append(r.status)

        mgr = SubAgentManager(parent_config=agent_config, on_update=on_update)

        with patch.object(mgr, "_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"text": "ok", "tool_calls_count": 0}
            await mgr.create_and_run(SubAgentConfig(task_description="test"))

        assert SubAgentStatus.RUNNING in updates
        assert SubAgentStatus.COMPLETED in updates

    @pytest.mark.asyncio
    async def test_tool_filter(self, agent_config: AgentConfig) -> None:
        from modules.agent_chat.src.subagent.manager import SubAgentManager

        tools = [
            ToolDefinition(name="t1", description="tool 1", parameters={}, method=lambda: None),
            ToolDefinition(name="t2", description="tool 2", parameters={}, method=lambda: None),
            ToolDefinition(name="t3", description="tool 3", parameters={}, method=lambda: None),
        ]
        mgr = SubAgentManager(parent_config=agent_config, tool_definitions=tools)

        filtered = mgr._filter_tools(["t1", "t3"])
        assert len(filtered) == 2
        names = {t.name for t in filtered}
        assert names == {"t1", "t3"}

    @pytest.mark.asyncio
    async def test_filter_empty_returns_all(self, agent_config: AgentConfig) -> None:
        from modules.agent_chat.src.subagent.manager import SubAgentManager

        tools = [
            ToolDefinition(name="t1", description="", parameters={}, method=lambda: None),
        ]
        mgr = SubAgentManager(parent_config=agent_config, tool_definitions=tools)
        filtered = mgr._filter_tools([])
        assert len(filtered) == 1

    def test_extract_summary_short(self) -> None:
        from modules.agent_chat.src.subagent.manager import SubAgentManager

        s = SubAgentManager._extract_summary({"text": "短结果"})
        assert s == "短结果"

    def test_extract_summary_long_truncated(self) -> None:
        from modules.agent_chat.src.subagent.manager import SubAgentManager

        long_text = "x" * 3000
        s = SubAgentManager._extract_summary({"text": long_text})
        assert len(s) < 2100
        assert "截断" in s

    def test_extract_summary_empty(self) -> None:
        from modules.agent_chat.src.subagent.manager import SubAgentManager

        s = SubAgentManager._extract_summary({"text": ""})
        assert "未返回" in s


class TestSubAgentTool:
    @pytest.mark.asyncio
    async def test_create_sub_agent_tool(self) -> None:
        from modules.agent_chat.src.subagent.manager import (
            SubAgentManager,
            create_subagent_tool,
        )

        config = AgentConfig(provider="glm", api_key="key")
        mgr = SubAgentManager(parent_config=config)

        tool = create_subagent_tool(mgr)
        assert tool.name == "create_sub_agent"
        assert "子代理" in tool.description

        with patch.object(mgr, "create_and_run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = SubAgentResult(
                task_id="t1",
                status=SubAgentStatus.COMPLETED,
                summary="分析完成",
                tool_calls_count=5,
                elapsed_seconds=2.5,
            )
            result = await tool.method(task_description="分析 trace")

        assert "子代理完成" in result
        assert "分析完成" in result

    def test_get_all_tasks(self) -> None:
        from modules.agent_chat.src.subagent.manager import SubAgentManager

        config = AgentConfig(provider="glm", api_key="key")
        mgr = SubAgentManager(parent_config=config)
        assert mgr.get_all_tasks() == []
