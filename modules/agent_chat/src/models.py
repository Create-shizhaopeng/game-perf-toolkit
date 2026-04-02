# -*- coding: utf-8 -*-
"""Agent 智能助手模块 — 数据模型定义。

公共 API 使用 Pydantic 模型，内部流转使用 dataclass。
"""
from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic 配置模型（公共 API / 三端共享）
# ---------------------------------------------------------------------------

class AgentConfig(BaseModel):
    """Agent 模块配置。"""

    provider: str = Field(
        default="glm",
        description="LLM Provider: glm / claude",
    )
    api_key: str = Field(
        default="",
        description="当前 Provider 的 API Key",
    )
    model_name: str = Field(
        default="glm-4-plus",
        description="模型名称",
    )
    max_tokens: int = Field(
        default=4096,
        description="LLM 最大输出 token 数",
    )
    temperature: float = Field(
        default=0.3,
        description="采样温度",
    )
    sop_dir: str = Field(
        default="",
        description="自定义 SOP 目录（空则使用默认 data/sops/）",
    )
    language: str = Field(
        default="zh",
        description="Agent 回复语言: zh / en",
    )
    smart_switch: bool = Field(
        default=True,
        description="智能 Provider 切换（复杂任务自动使用 Claude）",
    )
    max_conversations: int = Field(
        default=50,
        description="最大保留会话数",
    )
    max_context_messages: int = Field(
        default=20,
        description="发送给 LLM 的最大上下文消息数",
    )
    tool_result_max_length: int = Field(
        default=2000,
        description="工具结果最大长度（字符），超过截断",
    )
    workflow_learning_enabled: bool = Field(
        default=True,
        description="是否启用工作流学习与沉淀",
    )
    claude_api_key: str = Field(
        default="",
        description="Claude 的 API Key（支持双 Key 智能切换）",
    )
    glm_api_key: str = Field(
        default="",
        description="GLM 的 API Key",
    )


# ---------------------------------------------------------------------------
# 配置加载/保存
# ---------------------------------------------------------------------------

def _module_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _assets_config_path() -> Path:
    return _module_dir() / "assets" / "config.json"


def _data_config_path() -> Path:
    return _module_dir() / "data" / "config.json"


def load_config(path: Path | None = None) -> AgentConfig:
    """加载配置。优先使用 data/config.json，不存在时从 assets 复制。"""
    target = path or _data_config_path()
    if not target.exists():
        assets = _assets_config_path()
        if assets.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(assets, target)
        else:
            return AgentConfig()
    raw = json.loads(target.read_text(encoding="utf-8"))
    return AgentConfig(**raw)


def save_config(cfg: AgentConfig, path: Path | None = None) -> None:
    """保存配置到 data/config.json。"""
    target = path or _data_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        cfg.model_dump_json(indent=2),
        encoding="utf-8",
    )


def load_config_with_env(path: Path | None = None) -> AgentConfig:
    """加载配置并合并环境变量（三级策略 C-001）。

    优先级：环境变量 > data/config.json > 默认值
    """
    import os
    cfg = load_config(path)
    env_anthropic = os.environ.get("ANTHROPIC_API_KEY", "")
    env_glm = os.environ.get("ZHIPUAI_API_KEY", "")
    if env_anthropic and not cfg.claude_api_key:
        cfg.claude_api_key = env_anthropic
    if env_glm and not cfg.glm_api_key:
        cfg.glm_api_key = env_glm
    if cfg.provider == "glm" and not cfg.api_key and cfg.glm_api_key:
        cfg.api_key = cfg.glm_api_key
    elif cfg.provider == "claude" and not cfg.api_key and cfg.claude_api_key:
        cfg.api_key = cfg.claude_api_key
    return cfg


# ---------------------------------------------------------------------------
# 消息与对话
# ---------------------------------------------------------------------------

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


@dataclass
class Message:
    """对话消息。"""

    role: MessageRole
    content: str = ""
    tool_call_id: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    report_paths: list[str] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Conversation:
    """对话会话。"""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    sop_used: str = ""
    workflow_trace: WorkflowTrace | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# 工具定义与调用
# ---------------------------------------------------------------------------

@dataclass
class ToolDefinition:
    """工具定义（用于 ToolRegistry）。"""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    method: Callable | None = None


class ToolCallStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class ToolCall:
    """工具调用请求。"""

    id: str = ""
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    status: ToolCallStatus = ToolCallStatus.PENDING
    elapsed_ms: float = 0.0


@dataclass
class ToolResult:
    """工具执行结果。"""

    tool_call_id: str = ""
    content: str = ""
    is_error: bool = False
    report_paths: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM 响应
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    """LLM 完整响应。"""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""
    provider: str = ""
    workflow_deposit_ready: bool = False
    workflow_summary: dict[str, Any] = field(default_factory=dict)


class StreamChunkType(str, Enum):
    TEXT = "text"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    ERROR = "error"
    USAGE = "usage"
    WORKFLOW_DEPOSIT = "workflow_deposit"
    THINKING = "thinking"


@dataclass
class StreamChunk:
    """流式输出块。"""

    type: StreamChunkType
    data: str | dict[str, Any] = ""


# ---------------------------------------------------------------------------
# MCP 管理
# ---------------------------------------------------------------------------

class MCPServerConfig(BaseModel):
    """MCP 服务器配置。"""

    name: str
    command: str
    args: list[str] = []
    env: dict[str, str] = {}
    transport: str = Field(default="stdio", description="stdio | sse")
    timeout: int = 30
    enabled: bool = True


class MCPConnectionStatus(str, Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class MCPConnection:
    """MCP 服务器连接状态。"""

    server_name: str = ""
    status: MCPConnectionStatus = MCPConnectionStatus.DISCONNECTED
    available_tools: list[str] = field(default_factory=list)
    last_error: str | None = None
    connected_at: datetime | None = None


# ---------------------------------------------------------------------------
# Sub-agent 编排
# ---------------------------------------------------------------------------


class SubAgentConfig(BaseModel):
    """Sub-agent 创建配置。"""

    task_description: str
    skill_names: list[str] = []
    tool_filter: list[str] = []
    provider: str = ""  # 空 = 继承主 Agent
    model: str = ""
    max_turns: int = 15
    timeout: int = 120


class SubAgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class SubAgentResult:
    """Sub-agent 执行结果。"""

    task_id: str = ""
    status: SubAgentStatus = SubAgentStatus.PENDING
    summary: str = ""
    tool_calls_count: int = 0
    error: str | None = None
    retries: int = 0
    elapsed_seconds: float = 0.0
    raw_response: str = ""


class ProviderCapabilities(BaseModel):
    """LLM Provider 能力边界定义。"""

    name: str
    max_context_tokens: int = 128_000
    supports_tools: bool = True
    supports_vision: bool = False
    max_output_tokens: int = 4096
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0


# ---------------------------------------------------------------------------
# Skill 管理
# ---------------------------------------------------------------------------


class SkillMetadata(BaseModel):
    """Skill YAML frontmatter 元数据。"""

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    tags: list[str] = []
    triggers: list[str] = []
    tools: list[str] = []
    priority: int = 0
    enabled: bool = True


@dataclass
class SkillContext:
    """Skill 的运行时上下文。"""

    metadata: SkillMetadata | None = None
    skill_path: Path = field(default_factory=Path)
    loaded_content: str = ""
    loaded_resources: dict[str, str] = field(default_factory=dict)
    load_level: int = 0  # 0=metadata, 1=SKILL.md, 2=sub-resources


# ---------------------------------------------------------------------------
# SOP 文档
# ---------------------------------------------------------------------------

class SOPSource(str, Enum):
    BUILTIN = "builtin"
    CUSTOM = "custom"


@dataclass
class SOPDocument:
    """SOP 文档（解析后的结构化表示）。"""

    path: Path = field(default_factory=Path)
    title: str = ""
    keywords: list[str] = field(default_factory=list)
    description: str = ""
    recommended_provider: str = ""
    required_tools: list[str] = field(default_factory=list)
    content: str = ""
    source: SOPSource = SOPSource.BUILTIN


# ---------------------------------------------------------------------------
# 工作流追踪
# ---------------------------------------------------------------------------

@dataclass
class WorkflowStep:
    """工作流中的单个步骤。"""

    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WorkflowTrace:
    """工作流记录（用于沉淀检测）。"""

    steps: list[WorkflowStep] = field(default_factory=list)
    user_decisions: list[str] = field(default_factory=list)
    sop_deviation: str = ""
    original_sop: str = ""
