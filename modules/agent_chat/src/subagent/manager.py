# -*- coding: utf-8 -*-
"""SubAgentManager — 子 Agent 创建、执行、重试和结果收集。"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Callable

from ..models import (
    AgentConfig,
    SubAgentConfig,
    SubAgentResult,
    SubAgentStatus,
    ToolDefinition,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
OnSubAgentUpdate = Callable[[SubAgentResult], None]


class SubAgentManager:
    """管理子 Agent 的生命周期。"""

    def __init__(
        self,
        parent_config: AgentConfig,
        tool_definitions: list[ToolDefinition] | None = None,
        on_update: OnSubAgentUpdate | None = None,
    ) -> None:
        self._parent_config = parent_config
        self._tool_definitions = tool_definitions or []
        self._on_update = on_update
        self._tasks: dict[str, SubAgentResult] = {}

    async def create_and_run(
        self, config: SubAgentConfig
    ) -> SubAgentResult:
        """创建子 Agent 并执行任务。"""
        task_id = f"sub_{uuid.uuid4().hex[:8]}"
        result = SubAgentResult(
            task_id=task_id,
            status=SubAgentStatus.RUNNING,
        )
        self._tasks[task_id] = result
        self._notify(result)

        start = time.monotonic()

        for attempt in range(1, MAX_RETRIES + 1):
            result.retries = attempt - 1
            try:
                response = await self._execute(config, task_id)
                result.status = SubAgentStatus.COMPLETED
                result.summary = self._extract_summary(response)
                result.raw_response = response.get("text", "")
                result.tool_calls_count = response.get("tool_calls_count", 0)
                break
            except Exception as exc:
                result.error = str(exc)
                logger.warning(
                    "Sub-agent '%s' 第 %d 次执行失败: %s",
                    task_id, attempt, exc,
                )
                if attempt < MAX_RETRIES:
                    result.status = SubAgentStatus.RETRYING
                    self._notify(result)
                    await asyncio.sleep(1.0 * attempt)
                else:
                    result.status = SubAgentStatus.FAILED

        result.elapsed_seconds = round(time.monotonic() - start, 2)
        self._notify(result)
        return result

    async def _execute(
        self, config: SubAgentConfig, task_id: str
    ) -> dict[str, Any]:
        """在隔离上下文中执行子 Agent 对话循环。"""
        from ..service import AgentService
        from ..tools.executor import ToolExecutor
        from ..tools.registry import ToolRegistry

        sub_config = self._parent_config.model_copy(update={
            "provider": config.provider or self._parent_config.provider,
            "model_name": config.model or self._parent_config.model_name,
            "max_context_messages": config.max_turns,
        })

        registry = ToolRegistry()
        tools = self._filter_tools(config.tool_filter)
        registry.register_many(tools)

        service = AgentService(
            config=sub_config,
            tool_registry=registry,
        )

        if not service.is_ready:
            raise RuntimeError("Sub-agent Provider 初始化失败")

        response = await asyncio.wait_for(
            service.chat(
                user_message=config.task_description,
                system_prompt=(
                    "你是一个专注的分析子代理。请简洁准确地完成分析任务，"
                    "输出结构化的分析结论。避免冗长的解释。"
                ),
            ),
            timeout=config.timeout,
        )

        return {
            "text": response.text,
            "tool_calls_count": len(response.tool_calls),
        }

    def _filter_tools(self, filter_names: list[str]) -> list[ToolDefinition]:
        """按名称过滤工具。"""
        if not filter_names:
            return list(self._tool_definitions)
        return [t for t in self._tool_definitions if t.name in filter_names]

    @staticmethod
    def _extract_summary(response: dict[str, Any]) -> str:
        """从子 Agent 响应中提取结构化摘要。"""
        text = response.get("text", "")
        if not text:
            return "子代理未返回有效结果"

        if len(text) > 2000:
            return text[:1800] + "\n\n...(结果已截断)"
        return text

    def get_task(self, task_id: str) -> SubAgentResult | None:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[SubAgentResult]:
        return list(self._tasks.values())

    def _notify(self, result: SubAgentResult) -> None:
        if self._on_update:
            try:
                self._on_update(result)
            except Exception:
                logger.debug("Sub-agent 回调异常", exc_info=True)


def create_subagent_tool(manager: SubAgentManager) -> ToolDefinition:
    """创建 create_sub_agent 工具供主 Agent 调用。"""

    async def create_sub_agent(
        task_description: str,
        skill_names: str = "",
        tool_filter: str = "",
    ) -> str:
        """创建子代理执行独立分析任务，返回结果摘要。"""
        config = SubAgentConfig(
            task_description=task_description,
            skill_names=skill_names.split(",") if skill_names else [],
            tool_filter=tool_filter.split(",") if tool_filter else [],
        )
        result = await manager.create_and_run(config)
        if result.status == SubAgentStatus.COMPLETED:
            return (
                f"[子代理完成] 耗时: {result.elapsed_seconds}s, "
                f"工具调用: {result.tool_calls_count}\n\n"
                f"{result.summary}"
            )
        return (
            f"[子代理失败] 重试 {result.retries} 次后仍失败\n"
            f"错误: {result.error}"
        )

    return ToolDefinition(
        name="create_sub_agent",
        description="创建独立子代理执行分析任务，上下文隔离，返回结构化摘要",
        parameters={
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "子代理需要完成的任务描述",
                },
                "skill_names": {
                    "type": "string",
                    "description": "子代理需要加载的 Skill，逗号分隔",
                },
                "tool_filter": {
                    "type": "string",
                    "description": "子代理可用的工具名称，逗号分隔（空=全部）",
                },
            },
            "required": ["task_description"],
        },
        method=create_sub_agent,
    )
