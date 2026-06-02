# -*- coding: utf-8 -*-
"""Skill 注册表 — 发现和管理模块 Skill 文件（SKILL.md）。

Core 层面负责：扫描搜索路径、解析 YAML frontmatter、内容读取。
Agent 层面负责：意图匹配路由、生成 skill_* 工具、运行时加载决策。
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_SUB_RESOURCE_DIRS = ("sop", "patterns", "cases", "ref")


def parse_yaml_frontmatter(text: str) -> dict[str, Any]:
    """解析 Markdown 文件的 YAML frontmatter。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception as exc:
        logger.debug("YAML frontmatter 解析失败: %s", exc)
        return {}


class SkillMetadata:
    """Skill 元数据（从 SKILL.md 的 YAML frontmatter 解析）。"""

    def __init__(
        self, name: str, description: str, file_path: Path,
        skill_dir: Path | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.file_path = file_path
        self.skill_dir = skill_dir or file_path.parent
        self.version: str = "1.0.0"
        self.tags: list[str] = []
        self.triggers: list[str] = []
        self.category: str = ""
        self.icon: str = ""
        self.platforms: list[str] = []
        self.prerequisites: dict[str, Any] = {}
        self.enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "tags": self.tags,
            "triggers": self.triggers,
            "category": self.category,
            "icon": self.icon,
            "platforms": self.platforms,
            "file_path": str(self.file_path),
        }


class SkillRegistry:
    """Skill 发现 + 元数据索引 + 内容读取。"""

    def __init__(self) -> None:
        self._skills: dict[str, SkillMetadata] = {}
        self._search_paths: list[Path] = []

    # ── 发现与扫描 ──

    def add_search_path(self, path: Path) -> None:
        """添加 Skill 搜索路径（支持递归扫描子目录）。"""
        if path not in self._search_paths:
            self._search_paths.append(path)
            logger.debug("Skill 搜索路径已添加: %s", path)

    def scan(self) -> list[SkillMetadata]:
        """扫描所有搜索路径，刷新 Skill 索引。

        T027: data/sops/ 作为默认搜索路径加入。
        """
        from toolkit.core.app_paths import get_exe_dir

        # Ensure default search paths
        default_sops = get_exe_dir() / "data" / "sops"
        if default_sops.exists() and default_sops not in self._search_paths:
            self._search_paths.append(default_sops)

        new_skills: dict[str, SkillMetadata] = {}
        for base in self._search_paths:
            if not base.exists():
                continue
            for skill_dir in sorted(base.iterdir()):
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue
                try:
                    meta = self._parse_skill(skill_md, skill_dir)
                    if meta.name in new_skills:
                        logger.info("Skill '%s' 被后发现的路径覆盖: %s", meta.name, skill_dir)
                    new_skills[meta.name] = meta
                except Exception as exc:
                    logger.warning("Skill 加载失败 %s: %s", skill_dir, exc)

        self._skills = new_skills
        logger.info("SkillRegistry.scan: 发现 %d 个 Skill", len(self._skills))
        return self.get_skills()

    def load_skills(self, skill_paths: list[str]) -> None:
        """从路径列表加载所有 SKILL.md 文件（pluggy hook 收集的路径）。"""
        for raw_path in skill_paths:
            path = Path(raw_path)
            if not path.exists():
                logger.warning("Skill 文件不存在: %s", raw_path)
                continue
            try:
                meta = self._parse_skill(path, path.parent)
                self._skills[meta.name] = meta
                logger.debug("已加载 Skill: %s (%s)", meta.name, path)
            except Exception as e:
                logger.error("Skill 加载失败 %s: %s", raw_path, e)

    # ── 索引查询 ──

    def get_skills(self) -> list[SkillMetadata]:
        return list(self._skills.values())

    def get_skill(self, name: str) -> SkillMetadata | None:
        return self._skills.get(name)

    def search(self, keyword: str) -> list[SkillMetadata]:
        """按关键词搜索 Skill（匹配 name/description/tags/triggers）。"""
        kw = keyword.lower()
        results = []
        for meta in self._skills.values():
            if kw in meta.name.lower() or kw in meta.description.lower():
                results.append(meta)
                continue
            if any(kw in t.lower() for t in (meta.tags or [])):
                results.append(meta)
                continue
            if any(kw in t.lower() for t in (meta.triggers or [])):
                results.append(meta)
        return results

    def get_content(self, name: str) -> str | None:
        """get_skill_content 的别名。"""
        return self.get_skill_content(name)

    # ── 内容读取 ──

    def get_skill_content(self, name: str) -> str | None:
        meta = self._skills.get(name)
        if not meta:
            return None
        try:
            return meta.file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("读取 Skill 内容失败 %s: %s", name, e)
            return None

    def get_resource(self, name: str, rel_path: str) -> str | None:
        """读取 Skill 的子资源文件。"""
        meta = self._skills.get(name)
        if not meta:
            return None
        full = meta.skill_dir / rel_path
        if not full.exists():
            return None
        # Path traversal guard
        try:
            full.resolve().relative_to(meta.skill_dir.resolve())
        except ValueError:
            return None
        try:
            return full.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("读取 Skill 子资源失败 %s/%s: %s", name, rel_path, e)
            return None

    def list_resources(self, name: str) -> dict[str, list[str]]:
        """列出 Skill 的子资源目录结构。"""
        meta = self._skills.get(name)
        if not meta:
            return {}
        result: dict[str, list[str]] = {}
        for sub in _SUB_RESOURCE_DIRS:
            sub_dir = meta.skill_dir / sub
            if sub_dir.is_dir():
                files = sorted(
                    f.name for f in sub_dir.iterdir()
                    if f.is_file() and f.suffix == ".md"
                )
                if files:
                    result[sub] = files
        extra_md = [
            f.name for f in meta.skill_dir.iterdir()
            if f.is_file() and f.suffix == ".md" and f.name != "SKILL.md"
        ]
        if extra_md:
            result["root"] = sorted(extra_md)
        return result

    # ── 平台过滤 ──
    def get_platform_skills(self, platform: str | None = None) -> list[SkillMetadata]:
        import sys
        plat = platform or sys.platform
        return [
            m for m in self._skills.values()
            if not m.platforms or plat in m.platforms
        ]

    # ── Internal ──

    @staticmethod
    def _parse_skill(path: Path, skill_dir: Path | None = None) -> SkillMetadata:
        """解析单个 SKILL.md 文件，提取 frontmatter。"""
        content = path.read_text(encoding="utf-8")
        fm_data = parse_yaml_frontmatter(content)

        name = fm_data.get("name", path.stem if skill_dir is None else (skill_dir.name if skill_dir else path.stem))
        description = fm_data.get("description", "")

        meta = SkillMetadata(
            name=name,
            description=description,
            file_path=path,
            skill_dir=skill_dir or path.parent,
        )
        meta.version = fm_data.get("version", "1.0.0")
        meta.tags = fm_data.get("tags", [])
        triggers_raw = fm_data.get("triggers", [])
        if isinstance(triggers_raw, dict):
            triggers_raw = list(triggers_raw.keys())
        meta.triggers = triggers_raw if isinstance(triggers_raw, list) else [str(triggers_raw)]
        meta.category = fm_data.get("category", "")
        meta.icon = fm_data.get("icon", "")
        meta.platforms = fm_data.get("platforms", [])
        meta.prerequisites = fm_data.get("prerequisites", {})
        meta.enabled = fm_data.get("enabled", True)
        return meta
