# -*- coding: utf-8 -*-
"""SkillDiscovery — 搜索路径扫描 + YAML frontmatter 解析。"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from ..models import SkillMetadata

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def parse_yaml_frontmatter(text: str) -> dict[str, Any]:
    """解析 Markdown 文件的 YAML frontmatter。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        import yaml
        return yaml.safe_load(m.group(1)) or {}
    except Exception as exc:
        logger.debug("YAML frontmatter 解析失败: %s", exc)
        return {}


class SkillDiscovery:
    """扫描搜索路径，发现可用 Skill。"""

    def __init__(self, search_paths: list[Path] | None = None) -> None:
        self._search_paths: list[Path] = search_paths or []
        self._cache: dict[str, tuple[SkillMetadata, Path]] = {}

    def add_search_path(self, path: Path) -> None:
        if path not in self._search_paths:
            self._search_paths.append(path)

    def scan(self) -> dict[str, tuple[SkillMetadata, Path]]:
        """扫描所有搜索路径，返回 name → (metadata, skill_dir) 映射。"""
        self._cache.clear()

        for base in self._search_paths:
            if not base.exists():
                continue
            for skill_dir in sorted(base.iterdir()):
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue
                self._load_skill(skill_md, skill_dir)

        logger.info("发现 %d 个 Skill", len(self._cache))
        return dict(self._cache)

    def _load_skill(self, skill_md: Path, skill_dir: Path) -> None:
        try:
            text = skill_md.read_text(encoding="utf-8")
            fm = parse_yaml_frontmatter(text)
            if not fm:
                name = skill_dir.name
                fm = {"name": name, "description": f"Skill: {name}"}
            else:
                name = fm.get("name", skill_dir.name)

            metadata = SkillMetadata(
                name=name,
                version=fm.get("version", "1.0.0"),
                description=fm.get("description", ""),
                author=fm.get("author", ""),
                tags=fm.get("tags", []),
                triggers=fm.get("triggers", []),
                tools=fm.get("tools", []),
                priority=fm.get("priority", 0),
                enabled=fm.get("enabled", True),
            )

            if metadata.enabled:
                self._cache[name] = (metadata, skill_dir)
            else:
                logger.debug("Skill '%s' 已禁用", name)

        except Exception as exc:
            logger.warning("Skill '%s' 加载失败: %s", skill_dir.name, exc)

    def get_all_metadata(self) -> list[SkillMetadata]:
        """返回所有已发现 Skill 的元数据列表。"""
        return [meta for meta, _ in self._cache.values()]

    def get_skill_path(self, name: str) -> Path | None:
        """根据 Skill 名称获取其目录路径。"""
        entry = self._cache.get(name)
        return entry[1] if entry else None

    def get_metadata(self, name: str) -> SkillMetadata | None:
        entry = self._cache.get(name)
        return entry[0] if entry else None
