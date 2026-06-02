# -*- coding: utf-8 -*-
"""工作流跟踪器 — 记录对话中的工具调用序列并检测沉淀条件。"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ..models import ToolCall, ToolResult, WorkflowStep, WorkflowTrace

logger = logging.getLogger(__name__)

_MIN_TOOL_COUNT_FOR_DEPOSIT = 2


class WorkflowTracker:
    """跟踪单次对话的工具调用序列。

    用于：
    - 记录每个工具调用的名称、参数、结果摘要、耗时
    - 记录用户决策点（如选择了某个分析模式）
    - 检测是否满足 SOP 沉淀条件（FR-150, FR-151）
    """

    def __init__(self, sop_name: str = "") -> None:
        self._trace = WorkflowTrace(original_sop=sop_name)
        self._active_sop_tools: set[str] = set()
        self._used_tool_names: set[str] = set()

    def set_sop_tools(self, required_tools: list[str]) -> None:
        """设置当前 SOP 要求的工具列表。"""
        self._active_sop_tools = set(required_tools)

    def record_tool_call(
        self,
        tool_call: ToolCall,
        result: ToolResult,
        elapsed_ms: float = 0.0,
    ) -> None:
        """记录一次工具调用。"""
        result_summary = result.content[:200] if result.content else ""
        if result.is_error:
            result_summary = f"[ERROR] {result_summary}"

        step = WorkflowStep(
            tool_name=tool_call.name,
            arguments=dict(tool_call.arguments) if isinstance(tool_call.arguments, dict) else {},
            result_summary=result_summary,
            timestamp=datetime.now(),
        )
        self._trace.steps.append(step)
        self._used_tool_names.add(tool_call.name)

        logger.debug("工作流步骤: %s (%.0fms)", tool_call.name, elapsed_ms)

    def record_user_decision(self, decision: str) -> None:
        """记录用户决策点。"""
        self._trace.user_decisions.append(decision)

    @property
    def trace(self) -> WorkflowTrace:
        return self._trace

    @property
    def tool_count(self) -> int:
        return len(self._trace.steps)

    @property
    def unique_tools_used(self) -> set[str]:
        return set(self._used_tool_names)

    def check_deposit_condition(self) -> bool:
        """检测是否满足 SOP 沉淀条件。

        条件 a: 未使用预置 SOP 但调用了 2+ 工具
        条件 b: 使用了 SOP 但步骤有偏差
        """
        if not self._trace.steps:
            return False

        unique_count = len(self._used_tool_names)

        if not self._trace.original_sop:
            return unique_count >= _MIN_TOOL_COUNT_FOR_DEPOSIT

        deviation = self._detect_deviation()
        if deviation:
            self._trace.sop_deviation = deviation
            return True

        return False

    def _detect_deviation(self) -> str:
        """检测工作流与 SOP 的偏差。"""
        if not self._active_sop_tools:
            return ""

        extra_tools = self._used_tool_names - self._active_sop_tools
        missing_tools = self._active_sop_tools - self._used_tool_names

        parts: list[str] = []
        if extra_tools:
            parts.append(f"额外工具: {', '.join(sorted(extra_tools))}")
        if missing_tools:
            parts.append(f"跳过工具: {', '.join(sorted(missing_tools))}")

        return "; ".join(parts) if parts else ""

    def get_workflow_summary(self) -> dict[str, Any]:
        """返回工作流摘要（供 SOP 生成使用）。"""
        return {
            "original_sop": self._trace.original_sop,
            "total_steps": len(self._trace.steps),
            "unique_tools": sorted(self._used_tool_names),
            "tool_sequence": [s.tool_name for s in self._trace.steps],
            "user_decisions": self._trace.user_decisions,
            "sop_deviation": self._trace.sop_deviation,
            "steps": [
                {
                    "tool": s.tool_name,
                    "args_keys": list(s.arguments.keys()),
                    "result_preview": s.result_summary[:100],
                }
                for s in self._trace.steps
            ],
        }
