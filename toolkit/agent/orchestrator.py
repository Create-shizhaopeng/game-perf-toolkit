# -*- coding: utf-8 -*-
"""AgentOrchestrator — Agent 生命周期管理 + 统一工具视图。"""
from __future__ import annotations

import logging
from typing import Any

from toolkit.core.models import ToolDefinition
from toolkit.core.skill_registry import SkillRegistry
from toolkit.core.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Agent 生命周期管理 + 工具发现。

    职责：
    - 从 Core 获取 Skill/Tool/MCP 统一视图
    - 构建 System Prompt (三段式)
    - 管理 AgentService 实例
    - 处理配置变更 (Provider 切换等)
    """

    def __init__(self, context: dict) -> None:
        self._tool_registry: ToolRegistry = context.get("tool_registry")
        self._skill_registry: SkillRegistry = context.get("skill_registry")
        self._mcp_registry: Any = context.get("mcp_registry")
        self._llm_manager = context.get("llm_manager")
        self._service: Any = None

    # ── 初始化 ──

    def _register_skill_tools(self) -> int:
        """从 SkillRegistry 生成 skill_* + kc_* 工具并注入 ToolRegistry。"""
        if not self._skill_registry or not self._tool_registry:
            return 0
        from toolkit.agent.skill_tools import build_skill_tools
        from toolkit.agent.skill_router import SkillRouter

        router = SkillRouter()
        router.update_index(self._skill_registry.get_skills())
        tools = build_skill_tools(self._skill_registry, router)
        for t in tools:
            self._tool_registry.register(
                name=t.name, toolset="skill",
                schema=t.parameters, handler=t.method,
                description=t.description,
            )
        return len(tools)

    def _register_builtin_tools(self) -> int:
        """注册 Agent 内置工具：create_workspace, list_workspace_files。"""
        if not self._tool_registry:
            return 0
        from toolkit.agent.builtin import create_workspace, list_workspace_files

        builtins = [
            ToolDefinition(name="create_workspace", description="创建分析工作目录，返回绝对路径",
                           parameters={"type": "object", "properties": {"name": {"type": "string"}}},
                           method=create_workspace),
            ToolDefinition(name="list_workspace_files", description="列出工作目录下所有文件",
                           parameters={"type": "object", "properties": {"workspace_path": {"type": "string"}},
                                       "required": ["workspace_path"]},
                           method=list_workspace_files),
        ]
        for t in builtins:
            self._tool_registry.register(
                name=t.name, toolset="agent",
                schema=t.parameters, handler=t.method,
                description=t.description,
            )
        return len(builtins)

    def init(self) -> None:
        """同步初始化：注册 Skill 工具 + 内置工具。"""
        self._register_skill_tools()
        self._register_builtin_tools()
        logger.info("Orchestrator.init: tools initialized")

    async def init_async(self) -> None:
        """异步初始化：连接 MCP servers，刷新工具视图。"""
        if self._mcp_registry:
            try:
                await self._mcp_registry.connect_all()
            except Exception:
                logger.warning("MCP connect_all failed", exc_info=True)
        self.init_tools()

    def init_tools(self) -> list[ToolDefinition]:
        """构建统一工具视图（模块 tools + Skill tools + MCP tools）。"""
        tools: list[ToolDefinition] = []
        if self._tool_registry:
            tools.extend(self._tool_registry.get_definitions())
        if self._mcp_registry:
            try:
                mcp_tools = self._mcp_registry.get_tool_definitions()
                if mcp_tools and self._tool_registry:
                    self._tool_registry.register_mcp_tools(mcp_tools)
                    tools = self._tool_registry.get_definitions()
            except Exception:
                logger.debug("MCP 工具获取失败", exc_info=True)
        return tools

    def build_system_prompt(self, *, extra: str = "", conv_id: str = "") -> str:
        """三段式 System Prompt 组装。"""
        from toolkit.agent.system_prompt import build_system_prompt

        skills = []
        if self._skill_registry:
            skills = self._skill_registry.get_skills()
        tools = self.init_tools()

        return build_system_prompt(
            tools=tools,
            skills=skills,
            extra=extra,
        )

    # ── 对话 ──

    def create_service(self, conversation_store=None) -> Any:
        """创建/返回 AgentService 实例。"""
        if self._service is not None:
            return self._service
        self.init_tools()
        from toolkit.agent.service import AgentService
        from toolkit.agent.models import AgentConfig
        from toolkit.agent.memory.conversation import ConversationStore
        from toolkit.core.app_paths import get_db_path

        config = AgentConfig()
        store = conversation_store or ConversationStore(get_db_path("agent_chat", "conversation"))
        self._service = AgentService(
            config=config,
            conversation_store=store,
            tool_registry=self._tool_registry,
            llm_manager=self._llm_manager,
        )
        return self._service

    @property
    def is_ready(self) -> bool:
        """Provider 是否可用。"""
        if self._llm_manager:
            provider = self._llm_manager.get_provider()
            return provider is not None
        return False

    # ── 配置变更回调 ──

    def on_provider_changed(self, provider_name: str) -> None:
        logger.info("Provider 已切换: %s", provider_name)
        if self._service and hasattr(self._service, "_provider"):
            self._service._provider = self._llm_manager.get_provider()

    def on_skills_changed(self) -> None:
        logger.info("Skills 已变更")

    def on_mcp_changed(self) -> None:
        logger.info("MCP 配置已变更")

    # ── 预留 ──

    def spawn_subagent(self, config: Any) -> Any:
        """预留：创建子 Agent 执行独立任务。"""
        raise NotImplementedError("SubAgent not implemented yet")
