# -*- coding: utf-8 -*-
"""核心数据模型 — ToolRegistry 使用的公共类型。

所有模块和框架层共享这些模型，避免循环依赖。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


# ── ToolDefinition ──────────────────────────────────────────────────────

@dataclass
class ToolDefinition:
    """工具定义（用于 LLM Function Calling）。"""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    method: Callable | None = None


# ── ToolCall / ToolResult ──────────────────────────────────────────────

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
