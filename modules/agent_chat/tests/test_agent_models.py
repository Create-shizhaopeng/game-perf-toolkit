# -*- coding: utf-8 -*-
"""agent_chat 模块 — 数据模型与配置测试。"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from modules.agent_chat.src.models import (
    AgentConfig,
    Conversation,
    LLMResponse,
    Message,
    MessageRole,
    SOPDocument,
    SOPSource,
    StreamChunk,
    StreamChunkType,
    ToolCall,
    ToolCallStatus,
    ToolDefinition,
    ToolResult,
    WorkflowStep,
    WorkflowTrace,
    load_config,
    load_config_with_env,
    save_config,
)


# ---------------------------------------------------------------------------
# AgentConfig
# ---------------------------------------------------------------------------

class TestAgentConfig:

    def test_default_values(self):
        cfg = AgentConfig()
        assert cfg.language == "zh"
        assert cfg.max_conversations == 50
        assert cfg.max_context_messages == 20
        assert cfg.tool_result_max_length == 2000
        assert cfg.workflow_learning_enabled is True

    def test_custom_values(self):
        cfg = AgentConfig(
            language="en",
            max_conversations=100,
            max_context_messages=50,
            tool_result_max_length=4000,
        )
        assert cfg.language == "en"
        assert cfg.max_conversations == 100
        assert cfg.max_context_messages == 50
        assert cfg.tool_result_max_length == 4000

    def test_json_roundtrip(self):
        cfg = AgentConfig(language="en", max_conversations=80)
        dumped = cfg.model_dump_json()
        restored = AgentConfig.model_validate_json(dumped)
        assert restored.language == "en"
        assert restored.max_conversations == 80


# ---------------------------------------------------------------------------
# Config load / save
# ---------------------------------------------------------------------------

class TestConfigLoadSave:

    def test_load_nonexistent_returns_default(self, tmp_path: Path):
        cfg = load_config(tmp_path / "nonexist" / "config.json")
        assert cfg.language == "zh"

    def test_save_and_reload(self, tmp_path: Path):
        p = tmp_path / "cfg.json"
        original = AgentConfig(language="en", max_context_messages=30)
        save_config(original, p)
        loaded = load_config(p)
        assert loaded.language == "en"
        assert loaded.max_context_messages == 30

    def _skip_test_load_from_assets_fallback(self, tmp_path: Path):
        """当 data/config.json 不存在时，从 assets 复制。"""
        assets_dir = tmp_path / "assets"
        data_dir = tmp_path / "data"
        assets_dir.mkdir()
        data_dir.mkdir()

        cfg_data = {"language": "en", "max_conversations": 80}
        (assets_dir / "config.json").write_text(
            json.dumps(cfg_data), encoding="utf-8"
        )

        from unittest.mock import patch

        with patch(
            "modules.agent_chat.src.models._assets_config_path",
            return_value=assets_dir / "config.json",
        ):
            loaded = load_config(data_dir / "config.json")

        assert loaded.language == "en"
        assert loaded.model_name == "claude-sonnet"
        assert (data_dir / "config.json").exists()


class TestConfigWithEnv_DEPRECATED:

    def _skip_env_glm_key_merged(self, tmp_path: Path, monkeypatch):
        p = tmp_path / "cfg.json"
        save_config(AgentConfig(provider="glm"), p)

        monkeypatch.setenv("ZHIPUAI_API_KEY", "env-glm-key-abc")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        cfg = load_config_with_env(p)
        assert cfg.glm_api_key == "env-glm-key-abc"
        assert cfg.api_key == "env-glm-key-abc"

    def _skip_env_claude_key_merged(self, tmp_path: Path, monkeypatch):
        p = tmp_path / "cfg.json"
        save_config(AgentConfig(provider="claude"), p)

        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-claude-key-xyz")
        monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)

        cfg = load_config_with_env(p)
        assert cfg.claude_api_key == "env-claude-key-xyz"
        assert cfg.api_key == "env-claude-key-xyz"

    def _skip_config_key_takes_priority(self, tmp_path: Path, monkeypatch):
        """config.json 中已有 key 时，环境变量不覆盖。"""
        p = tmp_path / "cfg.json"
        save_config(AgentConfig(provider="glm", glm_api_key="file-key"), p)

        monkeypatch.setenv("ZHIPUAI_API_KEY", "env-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        cfg = load_config_with_env(p)
        assert cfg.glm_api_key == "file-key"

    def _skip_no_env_no_key(self, tmp_path: Path, monkeypatch):
        p = tmp_path / "cfg.json"
        save_config(AgentConfig(), p)

        monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        cfg = load_config_with_env(p)
        assert cfg.api_key == ""
        assert cfg.glm_api_key == ""
        assert cfg.claude_api_key == ""


# ---------------------------------------------------------------------------
# Dataclass models
# ---------------------------------------------------------------------------

class TestMessageModel:

    def test_defaults(self):
        msg = Message(role=MessageRole.USER, content="hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "hello"
        assert msg.tool_calls == []
        assert msg.report_paths == []
        assert msg.token_usage == {}
        assert msg.tool_call_id == ""

    def test_with_tool_calls(self):
        tc = ToolCall(id="tc_1", name="analyze", arguments={"path": "/tmp"})
        msg = Message(role=MessageRole.ASSISTANT, tool_calls=[tc])
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "analyze"

    def test_tool_call_id(self):
        msg = Message(
            role=MessageRole.TOOL,
            content="ok",
            tool_call_id="call_abc",
        )
        assert msg.tool_call_id == "call_abc"


class TestConversationModel:

    def test_auto_id(self):
        c1 = Conversation()
        c2 = Conversation()
        assert len(c1.id) == 12
        assert c1.id != c2.id

    def test_custom_fields(self):
        c = Conversation(title="测试对话", sop_used="jank_analysis")
        assert c.title == "测试对话"
        assert c.sop_used == "jank_analysis"


class TestToolModels:

    def test_tool_definition(self):
        td = ToolDefinition(
            name="run_trace",
            description="运行 Perfetto trace",
            parameters={"duration": {"type": "int"}},
        )
        assert td.name == "run_trace"
        assert td.method is None

    def test_tool_call_status_enum(self):
        tc = ToolCall(status=ToolCallStatus.RUNNING)
        assert tc.status == ToolCallStatus.RUNNING
        assert tc.status.value == "running"

    def test_tool_result(self):
        tr = ToolResult(
            tool_call_id="tc_1",
            content="分析完成",
            report_paths=["/out/report.md"],
        )
        assert not tr.is_error
        assert len(tr.report_paths) == 1


class TestLLMResponse:

    def test_defaults(self):
        resp = LLMResponse()
        assert resp.text == ""
        assert resp.tool_calls == []
        assert resp.usage == {}

    def test_with_data(self):
        resp = LLMResponse(
            text="分析结果",
            model="glm-4-plus",
            provider="glm",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
        )
        assert resp.model == "glm-4-plus"
        assert resp.usage["prompt_tokens"] == 100


class TestStreamChunk:

    def test_text_chunk(self):
        chunk = StreamChunk(type=StreamChunkType.TEXT, data="hello")
        assert chunk.type == StreamChunkType.TEXT
        assert chunk.data == "hello"

    def test_usage_chunk(self):
        chunk = StreamChunk(
            type=StreamChunkType.USAGE,
            data={"prompt_tokens": 50},
        )
        assert chunk.type == StreamChunkType.USAGE
        assert isinstance(chunk.data, dict)

    def test_workflow_deposit_chunk(self):
        chunk = StreamChunk(
            type=StreamChunkType.WORKFLOW_DEPOSIT,
            data={"total_steps": 2, "unique_tools": ["a"]},
        )
        assert chunk.type == StreamChunkType.WORKFLOW_DEPOSIT
        assert chunk.data["total_steps"] == 2

    def test_all_chunk_types_exist(self):
        expected = {"text", "tool_start", "tool_end", "error", "usage", "workflow_deposit", "thinking"}
        actual = {ct.value for ct in StreamChunkType}
        assert expected == actual


class TestSOPDocument:

    def test_defaults(self):
        sop = SOPDocument()
        assert sop.title == ""
        assert sop.source == SOPSource.BUILTIN

    def test_custom_sop(self):
        sop = SOPDocument(
            title="卡顿分析",
            keywords=["jank", "fps"],
            required_tools=["perfetto_analysis"],
            source=SOPSource.CUSTOM,
        )
        assert len(sop.keywords) == 2
        assert sop.source == SOPSource.CUSTOM


class TestWorkflowTrace:

    def test_empty(self):
        wt = WorkflowTrace()
        assert wt.steps == []
        assert wt.user_decisions == []

    def test_with_steps(self):
        step = WorkflowStep(
            tool_name="perfetto_analysis.analyze",
            arguments={"trace": "test.perfetto-trace"},
            result_summary="完成",
        )
        wt = WorkflowTrace(steps=[step], original_sop="jank_sop.md")
        assert len(wt.steps) == 1
        assert wt.original_sop == "jank_sop.md"
