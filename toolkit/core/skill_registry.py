# -*- coding: utf-8 -*-
"""Skill 注册表 — 发现和管理模块 Skill 文件（SKILL.md）。

Skill 本质是给 LLM Agent 的操作指南文档（markdown + YAML frontmatter）。
框架仅做文件扫描和元数据提取；Agent 直接读取文件内容并按其指引工作。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n", re.MULTILINE)


class SkillMetadata:
    """Skill 元数据（从 SKILL.md 的 YAML frontmatter 解析）。"""

    def __init__(
        self, name: str, description: str, file_path: Path
    ) -> None:
        self.name = name
        self.description = description
        self.file_path = file_path
        self.triggers: dict[str, Any] = {}
        self.category: str = ""
        self.icon: str = ""
        self.tags: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "triggers": self.triggers,
            "category": self.category,
            "icon": self.icon,
            "tags": self.tags,
            "file_path": str(self.file_path),
        }


class SkillRegistry:
    """收集各模块通过 pluggy hook 注册的 Skill 文件。"""

    def __init__(self) -> None:
        self._skills: dict[str, SkillMetadata] = {}

    def load_skills(self, skill_paths: list[str]) -> None:
        """从路径列表加载所有 SKILL.md 文件。"""
        for raw_path in skill_paths:
            path = Path(raw_path)
            if not path.exists():
                logger.warning("Skill 文件不存在: %s", raw_path)
                continue
            try:
                meta = self._parse_skill(path)
                self._skills[meta.name] = meta
                logger.debug("已加载 Skill: %s (%s)", meta.name, path)
            except Exception as e:
                logger.error("Skill 加载失败 %s: %s", raw_path, e)

    def get_skills(self) -> list[SkillMetadata]:
        """返回所有已注册的 Skill 元数据。"""
        return list(self._skills.values())

    def get_skill(self, name: str) -> SkillMetadata | None:
        """按名称获取 Skill 元数据。"""
        return self._skills.get(name)

    def get_skill_content(self, name: str) -> str | None:
        """按名称获取 Skill 完整文件内容。"""
        meta = self._skills.get(name)
        if not meta:
            return None
        try:
            return meta.file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("读取 Skill 内容失败 %s: %s", name, e)
            return None

    @staticmethod
    def _parse_skill(path: Path) -> SkillMetadata:
        """解析单个 SKILL.md 文件，提取 frontmatter。"""
        content = path.read_text(encoding="utf-8")

        fm_data: dict[str, Any] = {}
        if content.startswith("---"):
            parts = _FRONTMATTER_PATTERN.split(content, maxsplit=2)
            if len(parts) >= 3:
                try:
                    fm_data = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError as e:
                    logger.warning(
                        "SKILL.md frontmatter 解析失败 %s: %s", path, e
                    )

        name = fm_data.get("name", path.stem)
        description = fm_data.get("description", "")

        meta = SkillMetadata(name=name, description=description, file_path=path)
        meta.triggers = fm_data.get("triggers", {})
        meta.category = fm_data.get("category", "")
        meta.icon = fm_data.get("icon", "")
        meta.tags = fm_data.get("tags", [])
        return meta
