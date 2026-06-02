# -*- coding: utf-8 -*-
"""SkillsManager — 统一管理 Skill 的发现、路由、加载和 Agent 工具注册。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..models import SkillContext, SkillMetadata, ToolDefinition
from .discovery import SkillDiscovery
from .loader import SkillLoader
from .router import SkillRouter

# Compat: delegate skill tools to toolkit.agent.skill_tools
def _compat_create_agent_tools(mgr) -> list:
    """Delegate to toolkit.agent.skill_tools.build_skill_tools()."""
    sr = mgr._discovery._core
    sr.scan()
    from toolkit.agent.skill_tools import build_skill_tools
    return build_skill_tools(sr)

logger = logging.getLogger(__name__)


class SkillsManager:
    """Skill 全生命周期管理，暴露 Agent 可调用的工具。"""

    def __init__(self, search_paths: list[Path] | None = None) -> None:
        self._discovery = SkillDiscovery(search_paths or [])
        self._router = SkillRouter()
        self._loader = SkillLoader()
        self._active_contexts: dict[str, SkillContext] = {}

    def add_search_path(self, path: Path) -> None:
        self._discovery.add_search_path(path)

    def scan(self) -> list[SkillMetadata]:
        """扫描所有搜索路径，刷新索引。"""
        entries = self._discovery.scan()
        all_meta = [meta for meta, _ in entries.values()]
        self._router.update_index(all_meta)
        return all_meta

    def match_skills(self, query: str, top_k: int = 3) -> list[tuple[SkillMetadata, float]]:
        """根据用户意图匹配 Skill。"""
        return self._router.match(query, top_k=top_k)

    def load_skill(self, name: str, level: int = 1) -> SkillContext | None:
        """加载指定 Skill 到运行时上下文。"""
        skill_path = self._discovery.get_skill_path(name)
        if not skill_path:
            return None

        ctx = self._loader.load_metadata(skill_path)
        if not ctx:
            return None

        if level >= 1:
            self._loader.load_skill_content(ctx)

        self._active_contexts[name] = ctx
        return ctx

    def load_resource(self, name: str, resource_path: str) -> str:
        """Level 2: 加载 Skill 子资源。"""
        ctx = self._active_contexts.get(name)
        if not ctx:
            ctx = self.load_skill(name, level=0)
            if not ctx:
                return f"Skill '{name}' 不存在"

        return self._loader.load_resource(ctx, resource_path)

    def list_resources(self, name: str) -> dict[str, list[str]]:
        """列出 Skill 的子资源。"""
        ctx = self._active_contexts.get(name)
        if not ctx:
            ctx = self.load_skill(name, level=0)
            if not ctx:
                return {}
        return self._loader.list_resources(ctx)

    def get_active_skills(self) -> list[SkillContext]:
        return list(self._active_contexts.values())

    def get_all_metadata(self) -> list[SkillMetadata]:
        return self._discovery.get_all_metadata()

    # ── Agent 工具 ──────────────────────────────────────────────────────

    def create_agent_tools(self) -> list[ToolDefinition]:
        """委托到 toolkit.agent.skill_tools.build_skill_tools()。"""
        self._discovery._core.scan()  # refresh Skill index
        from toolkit.agent.skill_tools import build_skill_tools
        return build_skill_tools(self._discovery._core)
