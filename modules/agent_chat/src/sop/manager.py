# -*- coding: utf-8 -*-
"""SOP 文档管理器。"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import yaml

from ..models import SOPDocument, SOPSource

logger = logging.getLogger(__name__)


class SOPManager:
    """管理内置和自定义 SOP 文档。

    加载顺序：assets/sops/（内置）+ data/sops/（自定义）。
    同名文件时 data/sops/ 优先（FR-155）。
    """

    def __init__(self, builtin_dir: Path, custom_dir: Path) -> None:
        self._builtin_dir = builtin_dir
        self._custom_dir = custom_dir
        self._custom_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, SOPDocument] = {}

    def load_all(self) -> list[SOPDocument]:
        """加载所有 SOP 文档（custom 优先于 builtin 同名文件）。"""
        self._cache.clear()
        seen_names: set[str] = set()

        for path in sorted(self._custom_dir.glob("*.md")):
            doc = self._parse_file(path, SOPSource.CUSTOM)
            if doc:
                self._cache[doc.title or path.stem] = doc
                seen_names.add(path.stem)

        for path in sorted(self._builtin_dir.glob("*.md")):
            if path.stem in seen_names:
                logger.debug("SOP '%s' 被自定义版本覆盖", path.stem)
                continue
            doc = self._parse_file(path, SOPSource.BUILTIN)
            if doc:
                self._cache[doc.title or path.stem] = doc

        logger.info("已加载 %d 个 SOP 文档", len(self._cache))
        return list(self._cache.values())

    def get_all_metadata(self) -> list[dict[str, Any]]:
        """返回所有 SOP 的摘要元数据（供 system prompt 注入）。"""
        if not self._cache:
            self.load_all()

        return [
            {
                "name": name,
                "title": doc.title,
                "keywords": doc.keywords,
                "description": doc.description,
                "recommended_provider": doc.recommended_provider,
                "required_tools": doc.required_tools,
                "source": doc.source.value,
            }
            for name, doc in self._cache.items()
        ]

    def get_sop_content(self, name: str) -> str | None:
        """返回指定 SOP 的完整正文。"""
        if not self._cache:
            self.load_all()

        doc = self._cache.get(name)
        if doc:
            return doc.content

        for key, doc in self._cache.items():
            if doc.path.stem == name:
                return doc.content

        return None

    def get_sop(self, name: str) -> SOPDocument | None:
        """按名称获取 SOPDocument。"""
        if not self._cache:
            self.load_all()

        doc = self._cache.get(name)
        if doc:
            return doc

        for key, d in self._cache.items():
            if d.path.stem == name:
                return d

        return None

    def import_sop(self, source_path: Path) -> SOPDocument | None:
        """导入外部 SOP 文件到 data/sops/。"""
        if not source_path.exists():
            logger.error("SOP 文件不存在: %s", source_path)
            return None

        target = self._custom_dir / source_path.name
        if target.exists():
            stem = source_path.stem
            suffix = source_path.suffix
            counter = 2
            while target.exists():
                target = self._custom_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        shutil.copy2(source_path, target)
        doc = self._parse_file(target, SOPSource.CUSTOM)
        if doc:
            self._cache[doc.title or target.stem] = doc
            logger.info("已导入 SOP: %s", target.name)
        return doc

    def delete_sop(self, name: str) -> bool:
        """删除自定义 SOP（仅 custom 可删除）。"""
        doc = self.get_sop(name)
        if not doc:
            logger.warning("SOP '%s' 未找到", name)
            return False

        if doc.source != SOPSource.CUSTOM:
            logger.warning("内置 SOP '%s' 不可删除", name)
            return False

        try:
            doc.path.unlink()
        except OSError as exc:
            logger.error("删除 SOP 失败: %s", exc)
            return False

        self._cache = {k: v for k, v in self._cache.items() if v is not doc}
        logger.info("已删除 SOP: %s", name)
        return True

    def export_sop(self, name: str, target_path: Path) -> bool:
        """导出 SOP 到指定路径。"""
        doc = self.get_sop(name)
        if not doc:
            return False

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(doc.path, target_path)
        return True

    def _parse_file(self, path: Path, source: SOPSource) -> SOPDocument | None:
        """解析 SOP Markdown 文件（含 YAML frontmatter）。"""
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error("读取 SOP 文件失败 '%s': %s", path, exc)
            return None

        frontmatter, body = _split_frontmatter(raw)

        return SOPDocument(
            path=path,
            title=frontmatter.get("title", path.stem),
            keywords=frontmatter.get("keywords", []),
            description=frontmatter.get("description", ""),
            recommended_provider=frontmatter.get("recommended_provider", ""),
            required_tools=frontmatter.get("required_tools", []),
            content=body,
            source=source,
        )


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """拆分 YAML frontmatter 和正文。

    格式：
    ```
    ---
    title: ...
    keywords: [...]
    ---
    正文内容...
    ```
    """
    text = text.strip()
    if not text.startswith("---"):
        return {}, text

    end_marker = text.find("---", 3)
    if end_marker == -1:
        return {}, text

    yaml_str = text[3:end_marker].strip()
    body = text[end_marker + 3:].strip()

    try:
        meta = yaml.safe_load(yaml_str)
        if not isinstance(meta, dict):
            meta = {}
    except yaml.YAMLError as exc:
        logger.warning("YAML frontmatter 解析失败: %s", exc)
        meta = {}

    return meta, body
