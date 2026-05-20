# -*- coding: utf-8 -*-
"""Agent 对话循环核心服务。"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

from .llm.base import LLMProvider
from .memory.conversation import ConversationStore
from .models import (
    AgentConfig,
    Conversation,
    LLMResponse,
    Message,
    MessageRole,
    StreamChunk,
    StreamChunkType,
    ToolCall,
    ToolCallStatus,
    ToolDefinition,
    ToolResult,
)
from .sop.manager import SOPManager
from .skills.manager import SkillsManager
from .tools.executor import ToolExecutor
from .tools.registry import ToolRegistry
from .knowledge.report_index import ReportIndex
from .workflow.tracker import WorkflowTracker
from .strings_service import *

logger = logging.getLogger(__name__)

_MAX_TOOL_LOOP = 10
_TOOL_RETRY_COUNT = 1


class AgentService:
    """Agent 对话循环服务。

    负责：
    - 管理 LLM Provider 实例
    - 执行对话循环（用户消息 → LLM → 工具调用 → LLM → ...）
    - 流式输出
    - Token 统计
    """

    def __init__(
        self,
        config: AgentConfig,
        conversation_store: ConversationStore | None = None,
        tool_definitions: list[ToolDefinition] | None = None,
        tool_executor: ToolExecutor | None = None,
        tool_registry: ToolRegistry | None = None,
        sop_manager: SOPManager | None = None,
        skills_manager: SkillsManager | None = None,
        llm_manager: object | None = None,
    ) -> None:
        self._config = config
        self._store = conversation_store
        self._sop_manager = sop_manager
        self._skills_manager = skills_manager
        self._report_index = ReportIndex()
        self._provider: LLMProvider | None = None
        self._cancelled = False
        self._tracker: WorkflowTracker | None = None
        self._llm_manager = llm_manager

        if tool_registry:
            self._tools = tool_registry.get_definitions()
            self._tool_executor = ToolExecutor(
                tool_registry,
                max_result_length=config.tool_result_max_length,
            )
        elif tool_executor:
            self._tools = tool_definitions or []
            self._tool_executor = tool_executor
        else:
            self._tools = tool_definitions or []
            self._tool_executor = None

        self._init_provider()

        if self._llm_manager and hasattr(self._llm_manager, "provider_changed"):
            self._llm_manager.provider_changed.connect(  # type: ignore[union-attr]
                self._on_provider_changed
            )

    def _init_provider(self) -> None:
        """根据配置初始化 LLM Provider。优先从全局 LLMManager 获取。"""
        if self._llm_manager and hasattr(self._llm_manager, "get_provider"):
            self._provider = self._llm_manager.get_provider()  # type: ignore[union-attr]
            if self._provider:
                return
            logger.info(ERR_LLM_MANAGER_NO_PROVIDER)

        provider = self._config.provider
        api_key = self._resolve_api_key(provider)

        if not api_key:
            logger.warning(ERR_PROVIDER_NO_API_KEY_FMT, provider)
            return

        try:
            from toolkit.core.llm.litellm_provider import LiteLLMProvider

            self._provider = LiteLLMProvider(
                api_key=api_key,
                model=self._config.model_name,
                provider=provider,
            )
        except Exception as exc:
            logger.error(ERR_PROVIDER_INIT_FAILED_FMT, exc)

    def _resolve_api_key(self, provider: str) -> str:
        """解析 API Key（优先 api_key → 分 provider 的 key）。"""
        if self._config.api_key:
            return self._config.api_key
        if provider == "glm":
            return self._config.glm_api_key
        if provider == "claude":
            return self._config.claude_api_key
        return ""

    def _on_provider_changed(self, provider_name: str) -> None:
        """全局 Provider 切换后刷新内部引用。"""
        if self._llm_manager and hasattr(self._llm_manager, "get_provider"):
            new_provider = self._llm_manager.get_provider()  # type: ignore[union-attr]
            if new_provider:
                self._provider = new_provider
                logger.info(LOG_AGENT_PROVIDER_SWITCHED_FMT, provider_name)

    @property
    def is_ready(self) -> bool:
        return self._provider is not None

    def cancel(self) -> None:
        """取消当前对话。"""
        self._cancelled = True

    async def chat(
        self,
        user_message: str,
        conversation_id: str | None = None,
        on_chunk: Callable[[StreamChunk], None] | None = None,
        system_prompt: str = "",
    ) -> LLMResponse:
        """执行一次完整对话循环。

        Args:
            user_message: 用户消息
            conversation_id: 对话 ID（None 则创建新对话）
            on_chunk: 流式回调
            system_prompt: 额外 system prompt（可选）

        Returns:
            LLMResponse 完整响应
        """
        self._cancelled = False
        self._tracker = WorkflowTracker()

        if not self._provider:
            error_msg = ERR_PROVIDER_NOT_INIT
            if on_chunk:
                on_chunk(StreamChunk(type=StreamChunkType.ERROR, data=error_msg))
            return LLMResponse(text=error_msg)

        conv = self._get_or_create_conversation(conversation_id)
        messages = self._load_context_messages(conv.id)

        user_msg = Message(role=MessageRole.USER, content=user_message)
        if self._store:
            self._store.save_message(conv.id, user_msg)
        messages.append({"role": "user", "content": user_message})

        final_system = self._build_system_prompt(system_prompt)

        logger.debug("[DIAG] chat: 进入 _run_loop")
        response = await self._run_loop(
            messages=messages,
            conv_id=conv.id,
            system_prompt=final_system,
            on_chunk=on_chunk,
        )
        logger.debug("[DIAG] chat: _run_loop 返回, text_len=%d", len(response.text))

        if self._tracker and self._tracker.check_deposit_condition():
            response.workflow_deposit_ready = True
            response.workflow_summary = self._tracker.get_workflow_summary()
            if on_chunk:
                on_chunk(StreamChunk(
                    type=StreamChunkType.WORKFLOW_DEPOSIT,
                    data=response.workflow_summary,
                ))

        logger.debug("[DIAG] chat: 返回 response")
        return response

    def _get_or_create_conversation(self, conv_id: str | None) -> Conversation:
        if conv_id and self._store:
            existing = self._store.load_conversation(conv_id)
            if existing:
                return existing

        conv = Conversation()
        if self._store:
            self._store.create_conversation(conv)
        return conv

    def _load_context_messages(self, conv_id: str) -> list[dict]:
        """从存储加载最近的上下文消息。"""
        if not self._store:
            return []

        stored = self._store.load_messages(conv_id)
        max_ctx = self._config.max_context_messages

        if len(stored) > max_ctx:
            stored = self._smart_truncate(stored, max_ctx)

        result: list[dict] = []
        for msg in stored:
            entry: dict[str, Any] = {
                "role": msg.role.value,
                "content": msg.content,
            }
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": (
                                tc.arguments
                                if isinstance(tc.arguments, str)
                                else json.dumps(tc.arguments, ensure_ascii=False)
                            ),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            if msg.role == MessageRole.TOOL and msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            result.append(entry)
        return result

    @staticmethod
    def _smart_truncate(messages: list, max_count: int) -> list:
        """智能截断消息列表，优先保留 Skill 相关的工具调用结果。"""
        if len(messages) <= max_count:
            return messages

        skill_keywords = {"skill_load", "skill_list", "skill_load_resource"}

        priority_indices: set[int] = set()
        for i, msg in enumerate(messages):
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.name in skill_keywords:
                        priority_indices.add(i)
                        if i + 1 < len(messages):
                            priority_indices.add(i + 1)

        priority_msgs = [messages[i] for i in sorted(priority_indices)]
        remaining_count = max_count - len(priority_msgs)

        if remaining_count <= 0:
            return priority_msgs[-max_count:]

        recent = [m for i, m in enumerate(messages) if i not in priority_indices]
        recent = recent[-remaining_count:]

        return priority_msgs + recent

    def _build_system_prompt(self, extra: str = "") -> str:
        """构建系统提示词。"""
        parts = []

        parts.append(SYS_PROMPT_IDENTITY_ZH)

        if self._config.language == "en":
            parts[0] = SYS_PROMPT_IDENTITY_EN

        if self._tools:
            tool_list = ", ".join(t.name for t in self._tools)
            parts.append(SYS_PROMPT_TOOLS_FMT.format(tool_list))

        if self._skills_manager:
            all_meta = self._skills_manager.get_all_metadata()
            if all_meta:
                skill_summary = "\n".join(
                    SYS_PROMPT_SOP_SKILL_FMT.format(m.name, m.description, ", ".join(m.tags))
                    for m in all_meta
                )
                parts.append(
                    SYS_PROMPT_SKILLS_HEADER + skill_summary + "\n"
                    + SYS_PROMPT_SKILLS_FOOTER
                )
        elif self._sop_manager:
            sop_meta = self._sop_manager.get_all_metadata()
            if sop_meta:
                sop_summary = "\n".join(
                    SYS_PROMPT_SOP_ENTRY_FMT.format(
                        s["name"], s["description"], ", ".join(s["keywords"])
                    )
                    for s in sop_meta
                )
                parts.append(
                    SYS_PROMPT_SOP_HEADER + sop_summary + "\n"
                    + SYS_PROMPT_SOP_FOOTER
                )

        report_ctx = self._report_index.get_context_text(top_n=5)
        if report_ctx:
            parts.append(report_ctx)

        if extra:
            parts.append(extra)

        full = "\n\n".join(parts)
        return self._trim_system_prompt(full)

    def _trim_system_prompt(self, prompt: str, max_chars: int = 4000) -> str:
        """控制 system prompt 长度，避免占用过多上下文窗口。"""
        if len(prompt) <= max_chars:
            return prompt

        sections = prompt.split("\n\n")
        trimmed: list[str] = []
        used = 0

        for sec in sections:
            if used + len(sec) > max_chars:
                if sec.startswith("最近分析报告"):
                    lines = sec.split("\n")
                    remaining = max_chars - used - 50
                    if remaining > 100:
                        partial = "\n".join(lines[:3])
                        trimmed.append(partial + "\n  ...(更多历史报告已省略)")
                    continue
                elif len(trimmed) >= 2:
                    continue
            trimmed.append(sec)
            used += len(sec) + 2

        return "\n\n".join(trimmed)

    async def _run_loop(
        self,
        messages: list[dict],
        conv_id: str,
        system_prompt: str,
        on_chunk: Callable[[StreamChunk], None] | None,
        loop_count: int = 0,
    ) -> LLMResponse:
        """核心对话循环：调用 LLM → 处理工具 → 递归。"""
        if loop_count >= _MAX_TOOL_LOOP:
            logger.warning("工具调用循环达到上限 (%d)", _MAX_TOOL_LOOP)
            text = ERR_TOOL_LOOP_LIMIT_FMT
            if on_chunk:
                on_chunk(StreamChunk(type=StreamChunkType.TEXT, data=text))
            return LLMResponse(text=text)

        if self._cancelled:
            return LLMResponse(text=CANCELLED_MARK)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        usage: dict[str, int] = {}
        error_text = ""

        assert self._provider is not None

        if on_chunk:
            hint = PROGRESS_THINKING_FIRST if loop_count == 0 else PROGRESS_THINKING_LOOP
            on_chunk(StreamChunk(type=StreamChunkType.THINKING, data=hint))

        async for chunk in self._provider.stream_chat(
            messages=messages,
            tools=self._tools if self._tools else None,
            system_prompt=system_prompt if loop_count == 0 else "",
        ):
            if self._cancelled:
                return LLMResponse(text="".join(text_parts) + CANCELLED_APPEND)

            if chunk.type == StreamChunkType.TEXT:
                text_parts.append(str(chunk.data))
                if on_chunk:
                    on_chunk(chunk)

            elif chunk.type == StreamChunkType.TOOL_START:
                data = chunk.data if isinstance(chunk.data, dict) else {}
                tc = ToolCall(
                    id=data.get("id", ""),
                    name=data.get("name", ""),
                    arguments=data.get("arguments", {}),
                    status=ToolCallStatus.PENDING,
                )
                tool_calls.append(tc)
                if on_chunk:
                    on_chunk(chunk)

            elif chunk.type == StreamChunkType.USAGE:
                if isinstance(chunk.data, dict):
                    usage = chunk.data
                    total = usage.get("total_tokens", 0)
                    if total and self._llm_manager and hasattr(self._llm_manager, "record_tokens"):
                        self._llm_manager.record_tokens(total)  # type: ignore[union-attr]

            elif chunk.type == StreamChunkType.ERROR:
                error_text = str(chunk.data)
                if on_chunk:
                    on_chunk(chunk)

        if error_text and not text_parts and not tool_calls:
            return LLMResponse(text=error_text, usage=usage)

        full_text = "".join(text_parts)

        if not tool_calls:
            logger.debug("[DIAG] _run_loop[%d]: 无 tool_calls, 返回文本响应 len=%d", loop_count, len(full_text))
            assistant_msg = Message(
                role=MessageRole.ASSISTANT,
                content=full_text,
                token_usage=usage,
            )
            if self._store:
                self._store.save_message(conv_id, assistant_msg)

            return LLMResponse(
                text=full_text,
                usage=usage,
                model=self._config.model_name,
                provider=self._config.provider,
            )

        assistant_msg = Message(
            role=MessageRole.ASSISTANT,
            content=full_text,
            tool_calls=tool_calls,
            token_usage=usage,
        )
        if self._store:
            self._store.save_message(conv_id, assistant_msg)

        messages.append(self._build_assistant_message(full_text, tool_calls))

        logger.debug("[DIAG] _run_loop[%d]: 有 %d 个 tool_calls, 开始执行", loop_count, len(tool_calls))
        tool_results = await self._handle_tool_calls(tool_calls, on_chunk)
        logger.debug("[DIAG] _run_loop[%d]: tool_calls 执行完成", loop_count)

        for tc, tr in zip(tool_calls, tool_results):
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tr.content,
            })

            tool_msg = Message(
                role=MessageRole.TOOL,
                content=tr.content,
                tool_call_id=tc.id,
                report_paths=tr.report_paths,
            )
            if self._store:
                self._store.save_message(conv_id, tool_msg)

        logger.debug("[DIAG] _run_loop[%d]: 递归调用 _run_loop[%d]", loop_count, loop_count + 1)
        result = await self._run_loop(
            messages=messages,
            conv_id=conv_id,
            system_prompt=system_prompt,
            on_chunk=on_chunk,
            loop_count=loop_count + 1,
        )
        logger.debug("[DIAG] _run_loop[%d]: 递归返回", loop_count)
        return result

    def _build_assistant_message(
        self, text: str, tool_calls: list[ToolCall]
    ) -> dict[str, Any]:
        """构建 assistant 消息（含工具调用）用于回传 LLM。"""
        msg: dict[str, Any] = {"role": "assistant"}
        if text:
            msg["content"] = text
        if tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": (
                            tc.arguments
                            if isinstance(tc.arguments, str)
                            else __import__("json").dumps(tc.arguments, ensure_ascii=False)
                        ),
                    },
                }
                for tc in tool_calls
            ]
        return msg

    async def _handle_tool_calls(
        self,
        tool_calls: list[ToolCall],
        on_chunk: Callable[[StreamChunk], None] | None,
    ) -> list[ToolResult]:
        """执行工具调用列表，含重试逻辑。"""
        results: list[ToolResult] = []

        for tc in tool_calls:
            if self._cancelled:
                results.append(ToolResult(
                    tool_call_id=tc.id,
                    content=CANCELLED_MARK,
                    is_error=True,
                ))
                continue

            result = await self._execute_single_tool(tc, on_chunk)

            if result.is_error and _TOOL_RETRY_COUNT > 0:
                logger.info(LOG_TOOL_RETRY_FMT, tc.name)
                result = await self._execute_single_tool(tc, on_chunk)

            if self._tracker:
                self._tracker.record_tool_call(
                    tc, result, elapsed_ms=tc.elapsed_ms,
                )

            results.append(result)

        return results

    async def _execute_single_tool(
        self,
        tc: ToolCall,
        on_chunk: Callable[[StreamChunk], None] | None,
    ) -> ToolResult:
        """执行单个工具调用。"""
        if not self._tool_executor:
            return ToolResult(
                tool_call_id=tc.id,
                content=ERR_TOOL_NO_EXECUTOR_FMT.format(tc.name),
                is_error=True,
            )

        tc.status = ToolCallStatus.RUNNING
        start = time.time()

        try:
            result = await self._tool_executor.execute(tc)
        except Exception as exc:
            logger.error(LOG_TOOL_EXEC_ERROR_FMT, tc.name, exc)
            result = ToolResult(
                tool_call_id=tc.id,
                content=ERR_TOOL_EXEC_EXCEPTION_FMT.format(exc),
                is_error=True,
            )

        elapsed = (time.time() - start) * 1000
        tc.elapsed_ms = elapsed
        tc.status = (
            ToolCallStatus.COMPLETE if not result.is_error
            else ToolCallStatus.FAILED
        )

        if len(result.content) > self._config.tool_result_max_length:
            result.content = (
                result.content[: self._config.tool_result_max_length]
                + TOOL_RESULT_TRUNCATED
            )

        if on_chunk:
            on_chunk(StreamChunk(
                type=StreamChunkType.TOOL_END,
                data={
                    "id": tc.id,
                    "name": tc.name,
                    "is_error": result.is_error,
                    "elapsed_ms": elapsed,
                    "content_preview": result.content[:200],
                },
            ))

        return result
