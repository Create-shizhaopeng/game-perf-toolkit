# -*- coding: utf-8 -*-
"""SkillsManager — 统一管理 Skill 的发现、路由、加载和 Agent 工具注册。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..models import SkillContext, SkillMetadata, ToolDefinition
from .curator_tools import create_curator_tools
from .discovery import SkillDiscovery
from .loader import SkillLoader
from .router import SkillRouter

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
        """创建注册到 ToolRegistry 的 Skill 管理 + knowledge-curator 工具。"""
        mgr = self

        def skill_list() -> str:
            """列出所有可用的 Skill 及其描述。"""
            all_meta = mgr.get_all_metadata()
            if not all_meta:
                return "当前无可用 Skill"
            lines = []
            for m in all_meta:
                tags = ", ".join(m.tags) if m.tags else ""
                lines.append(f"- {m.name} (v{m.version}): {m.description} [{tags}]")
            return "\n".join(lines)

        def skill_load(name: str) -> str:
            """加载指定 Skill 的完整内容 (SKILL.md)。"""
            ctx = mgr.load_skill(name, level=1)
            if not ctx:
                return f"Skill '{name}' 不存在或加载失败"
            return ctx.loaded_content or "Skill 内容为空"

        def skill_load_resource(skill_name: str, resource_path: str) -> str:
            """加载 Skill 的子资源 (如 sop/jank-analysis.md)。"""
            return mgr.load_resource(skill_name, resource_path)

        def skill_list_resources(name: str) -> str:
            """列出 Skill 的所有子资源文件。"""
            resources = mgr.list_resources(name)
            if not resources:
                return f"Skill '{name}' 无子资源"
            lines = []
            for category, files in resources.items():
                lines.append(f"[{category}]")
                for f in files:
                    lines.append(f"  - {f}")
            return "\n".join(lines)

        base_tools = [
            ToolDefinition(
                name="skill_list",
                description="列出所有可用 Skill 及其描述、标签",
                parameters={"type": "object", "properties": {}},
                method=skill_list,
            ),
            ToolDefinition(
                name="skill_load",
                description="加载指定 Skill 的完整内容（SKILL.md），获取分析方法论和工具使用指南",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Skill 名称"},
                    },
                    "required": ["name"],
                },
                method=skill_load,
            ),
            ToolDefinition(
                name="skill_load_resource",
                description="按需加载 Skill 的子资源（SOP、模式库、案例），获取领域知识",
                parameters={
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string", "description": "Skill 名称"},
                        "resource_path": {
                            "type": "string",
                            "description": "子资源路径，如 sop/jank-analysis.md",
                        },
                    },
                    "required": ["skill_name", "resource_path"],
                },
                method=skill_load_resource,
            ),
            ToolDefinition(
                name="skill_list_resources",
                description="列出 Skill 的所有子资源文件目录",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Skill 名称"},
                    },
                    "required": ["name"],
                },
                method=skill_list_resources,
            ),
        ]

        curator_tools = create_curator_tools(self)
        return base_tools + curator_tools
