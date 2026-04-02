# -*- coding: utf-8 -*-
"""SkillLoader — 三级渐进式加载。

Level 0: 仅元数据 (SkillMetadata)
Level 1: SKILL.md 全文
Level 2: 子资源按需加载 (sop/, patterns/, cases/, ref/)
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..models import SkillContext, SkillMetadata
from .discovery import parse_yaml_frontmatter

logger = logging.getLogger(__name__)

_FRONTMATTER_END = re.compile(r"^---\s*$") if False else None  # noqa: F841

_SUB_RESOURCE_DIRS = ("sop", "patterns", "cases", "ref")


class SkillLoader:
    """三级渐进式加载 Skill 内容。"""

    def load_metadata(self, skill_dir: Path) -> SkillContext | None:
        """Level 0: 仅加载元数据。"""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        text = skill_md.read_text(encoding="utf-8")
        fm = parse_yaml_frontmatter(text)
        if not fm:
            name = skill_dir.name
            meta = SkillMetadata(name=name)
        else:
            meta = SkillMetadata(**{
                k: v for k, v in fm.items()
                if k in SkillMetadata.model_fields
            })

        ctx = SkillContext(
            metadata=meta,
            skill_path=skill_dir,
            load_level=0,
        )
        return ctx

    def load_skill_content(self, ctx: SkillContext) -> SkillContext:
        """Level 1: 加载 SKILL.md 全文。"""
        skill_md = ctx.skill_path / "SKILL.md"
        if skill_md.exists():
            ctx.loaded_content = skill_md.read_text(encoding="utf-8")
        ctx.load_level = 1
        return ctx

    def load_resource(self, ctx: SkillContext, resource_path: str) -> str:
        """Level 2: 按需加载指定子资源。

        Args:
            resource_path: 相对于 skill 目录的路径，如 "sop/jank-analysis.md"

        Returns:
            资源内容文本
        """
        full = ctx.skill_path / resource_path
        if not full.exists():
            return f"资源不存在: {resource_path}"

        if not self._is_safe_path(ctx.skill_path, full):
            return f"路径越界: {resource_path}"

        content = full.read_text(encoding="utf-8")
        ctx.loaded_resources[resource_path] = content
        ctx.load_level = 2
        return content

    def list_resources(self, ctx: SkillContext) -> dict[str, list[str]]:
        """列出 Skill 的所有子资源。"""
        result: dict[str, list[str]] = {}

        for sub in _SUB_RESOURCE_DIRS:
            sub_dir = ctx.skill_path / sub
            if sub_dir.is_dir():
                files = sorted(
                    f.name for f in sub_dir.iterdir()
                    if f.is_file() and f.suffix == ".md"
                )
                if files:
                    result[sub] = files

        extra_md = [
            f.name for f in ctx.skill_path.iterdir()
            if f.is_file() and f.suffix == ".md" and f.name != "SKILL.md"
        ]
        if extra_md:
            result["root"] = sorted(extra_md)

        return result

    @staticmethod
    def _is_safe_path(base: Path, target: Path) -> bool:
        """防止路径遍历攻击。"""
        try:
            target.resolve().relative_to(base.resolve())
            return True
        except ValueError:
            return False
