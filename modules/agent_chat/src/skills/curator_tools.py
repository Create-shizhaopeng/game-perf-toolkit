# -*- coding: utf-8 -*-
"""knowledge-curator Skill 辅助工具 — 文档分类、匹配、格式化、去重、写入。"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from ..models import ToolDefinition

logger = logging.getLogger(__name__)

_CATEGORY_RULES = [
    ("sop", ["步骤", "流程", "操作指引", "决策树", "step", "procedure", "SOP"]),
    ("patterns", ["原因", "根因", "当.*发生", "方案", "pattern", "root cause"]),
    ("cases", ["分析案例", "设备", "trace", "时间戳", "结论", "case study"]),
]


def classify_document(content: str) -> list[dict[str, Any]]:
    """对输入文档进行内容分类。

    Returns:
        分类结果列表: [{"category": "sop"|"patterns"|"cases", "confidence": float,
                        "summary": str, "content": str}]
    """
    sections = _split_sections(content)
    results: list[dict[str, Any]] = []

    for title, body in sections:
        category, confidence = _classify_section(title, body)
        summary = (title or body[:80]).strip()
        results.append({
            "category": category,
            "confidence": round(confidence, 2),
            "summary": summary[:100],
            "content": f"# {title}\n\n{body}" if title else body,
        })

    if not results:
        category, confidence = _classify_section("", content)
        results.append({
            "category": category,
            "confidence": round(confidence, 2),
            "summary": content[:100].strip(),
            "content": content,
        })

    return results


def match_skill(
    classified_items: list[dict],
    available_skills: list[dict[str, Any]],
    user_override: str | None = None,
) -> list[dict[str, Any]]:
    """将分类内容匹配到目标 Skill。

    Args:
        classified_items: classify_document 的输出
        available_skills: [{"name": ..., "description": ..., "tags": [...]}]
        user_override: 用户指定的 Skill 名称

    Returns:
        匹配结果: [{"item_summary": ..., "matched_skill": ..., "score": float}]
    """
    results = []

    for item in classified_items:
        if user_override:
            results.append({
                "item_summary": item["summary"],
                "matched_skill": user_override,
                "score": 1.0,
                "category": item["category"],
            })
            continue

        best_skill = ""
        best_score = 0.0
        item_text = f"{item['summary']} {item['category']}".lower()

        for skill in available_skills:
            skill_text = (
                f"{skill.get('name', '')} {skill.get('description', '')} "
                f"{' '.join(skill.get('tags', []))}"
            ).lower()

            score = SequenceMatcher(None, item_text, skill_text).ratio()
            keyword_overlap = sum(
                1 for tag in skill.get("tags", []) if tag.lower() in item_text
            )
            score += keyword_overlap * 0.15

            if score > best_score:
                best_score = score
                best_skill = skill.get("name", "")

        results.append({
            "item_summary": item["summary"],
            "matched_skill": best_skill,
            "score": round(best_score, 2),
            "category": item["category"],
        })

    return results


def format_resource(
    content: str,
    category: str,
    source_doc: str = "",
) -> str:
    """按标准模板格式化子资源内容。"""
    lines = content.strip().split("\n")
    title = ""
    body = content
    if lines and lines[0].startswith("#"):
        title = lines[0].lstrip("#").strip()
        body = "\n".join(lines[1:]).strip()

    if category == "sop":
        return _format_sop(title or "Untitled SOP", body, source_doc)
    elif category == "patterns":
        return _format_pattern(title or "Untitled Pattern", body, source_doc)
    elif category == "cases":
        return _format_case(title or "Untitled Case", body, source_doc)
    else:
        return content


def check_duplicate(
    new_content: str,
    existing_files: list[Path],
    threshold: float = 0.70,
) -> list[dict[str, Any]]:
    """检查新内容与已有子资源的重复度。

    Returns:
        重复项列表: [{"file": str, "similarity": float}]
    """
    duplicates = []
    new_stripped = re.sub(r"\s+", " ", new_content.strip())

    for f in existing_files:
        if not f.exists() or not f.suffix == ".md":
            continue
        existing = re.sub(r"\s+", " ", f.read_text(encoding="utf-8").strip())
        ratio = SequenceMatcher(None, new_stripped, existing).ratio()
        if ratio >= threshold:
            duplicates.append({
                "file": f.name,
                "similarity": round(ratio, 2),
            })

    return duplicates


def write_resource(
    content: str,
    skill_dir: Path,
    category: str,
    filename: str,
) -> str:
    """将格式化后的子资源写入目标 Skill 目录。

    Returns:
        写入的文件路径
    """
    target_dir = skill_dir / category
    target_dir.mkdir(parents=True, exist_ok=True)

    if not filename.endswith(".md"):
        filename += ".md"

    target = target_dir / filename
    target.write_text(content, encoding="utf-8")
    logger.info("知识资源已写入: %s", target)
    return str(target)


# ── 内部辅助函数 ───────────────────────────────────────────────────────


def _split_sections(text: str) -> list[tuple[str, str]]:
    """将文档按 H2/H1 标题拆分为 (title, body) 段落。"""
    pattern = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))

    if not matches:
        return [("", text)]

    sections = []
    for i, m in enumerate(matches):
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((title, body))

    return sections or [("", text)]


def _classify_section(title: str, body: str) -> tuple[str, float]:
    """基于关键词规则对单个段落分类。"""
    combined = f"{title} {body}".lower()
    scores: dict[str, float] = {}

    for cat, keywords in _CATEGORY_RULES:
        hits = sum(1 for kw in keywords if kw.lower() in combined)
        scores[cat] = hits / len(keywords) if keywords else 0

    if not scores or max(scores.values()) == 0:
        if re.search(r"SELECT\s|FROM\s|WHERE\s", body, re.IGNORECASE):
            return "sop", 0.6
        return "cases", 0.3

    best = max(scores, key=lambda k: scores[k])
    return best, scores[best]


def _format_sop(title: str, body: str, source: str) -> str:
    """SOP 格式化模板。"""
    parts = [
        "---",
        f"title: {title}",
        f"category: sop",
        f"source: {source}" if source else "",
        "---",
        "",
        f"# {title}",
        "",
        body,
    ]
    return "\n".join(p for p in parts if p is not None)


def _format_pattern(title: str, body: str, source: str) -> str:
    """根因模式格式化模板。"""
    parts = [
        "---",
        f"title: {title}",
        f"category: pattern",
        f"source: {source}" if source else "",
        "---",
        "",
        f"# {title}",
        "",
        body,
    ]
    return "\n".join(p for p in parts if p is not None)


def _format_case(title: str, body: str, source: str) -> str:
    """案例格式化模板。"""
    parts = [
        "---",
        f"title: {title}",
        f"category: case",
        f"source: {source}" if source else "",
        "---",
        "",
        f"# {title}",
        "",
        body,
    ]
    return "\n".join(p for p in parts if p is not None)


def create_curator_tools(skills_manager: Any) -> list[ToolDefinition]:
    """创建 knowledge-curator 的 Agent 工具。"""
    mgr = skills_manager

    def kc_classify_document(content: str) -> str:
        """对输入文档进行内容分类，返回分类结果。"""
        results = classify_document(content)
        lines = []
        for r in results:
            lines.append(
                f"- [{r['category']}] ({r['confidence']:.0%}) {r['summary']}"
            )
        return "\n".join(lines) if lines else "无法识别文档类型"

    def kc_match_skill(content: str, skill_name: str = "") -> str:
        """将分类内容匹配到目标 Skill。"""
        items = classify_document(content)
        all_meta = mgr.get_all_metadata() if mgr else []
        skills_info = [
            {"name": m.name, "description": m.description, "tags": m.tags}
            for m in all_meta
        ]
        override = skill_name if skill_name else None
        results = match_skill(items, skills_info, user_override=override)
        lines = []
        for r in results:
            lines.append(
                f"- {r['item_summary'][:50]} → {r['matched_skill']} "
                f"(score: {r['score']:.0%}, type: {r['category']})"
            )
        return "\n".join(lines) if lines else "无匹配 Skill"

    def kc_format_resource(
        content: str, category: str, source_doc: str = ""
    ) -> str:
        """按标准模板格式化子资源内容。"""
        return format_resource(content, category, source_doc)

    def kc_check_duplicate(
        content: str, skill_name: str, category: str
    ) -> str:
        """检查新内容与目标 Skill 已有子资源的重复度。"""
        skill_path = mgr.get_all_metadata() if mgr else []
        path = None
        if mgr:
            from .discovery import SkillDiscovery
            path_result = mgr._discovery.get_skill_path(skill_name)
            if path_result:
                path = path_result

        if not path:
            return f"Skill '{skill_name}' 不存在"

        cat_dir = path / category
        if not cat_dir.exists():
            return "目标目录不存在，无需去重"

        existing = list(cat_dir.glob("*.md"))
        dups = check_duplicate(content, existing)
        if not dups:
            return "无重复内容"
        lines = [f"- {d['file']} (相似度: {d['similarity']:.0%})" for d in dups]
        return "发现重复:\n" + "\n".join(lines)

    def kc_write_resource(
        content: str, skill_name: str, category: str, filename: str
    ) -> str:
        """将格式化后的子资源写入目标 Skill 目录（需用户确认后调用）。"""
        if not mgr:
            return "SkillsManager 未初始化"

        path = mgr._discovery.get_skill_path(skill_name)
        if not path:
            return f"Skill '{skill_name}' 不存在"

        return write_resource(content, path, category, filename)

    return [
        ToolDefinition(
            name="kc_classify_document",
            description="对输入文档进行内容分类（SOP/根因模式/案例）",
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "文档内容"},
                },
                "required": ["content"],
            },
            method=kc_classify_document,
        ),
        ToolDefinition(
            name="kc_match_skill",
            description="将分类内容匹配到目标 Skill",
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "文档内容"},
                    "skill_name": {"type": "string", "description": "指定目标 Skill（可选）"},
                },
                "required": ["content"],
            },
            method=kc_match_skill,
        ),
        ToolDefinition(
            name="kc_format_resource",
            description="按标准模板格式化子资源内容",
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "待格式化内容"},
                    "category": {"type": "string", "description": "类型: sop/patterns/cases"},
                    "source_doc": {"type": "string", "description": "原始文档名"},
                },
                "required": ["content", "category"],
            },
            method=kc_format_resource,
        ),
        ToolDefinition(
            name="kc_check_duplicate",
            description="检查新内容与目标 Skill 已有子资源的重复度",
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "新内容"},
                    "skill_name": {"type": "string", "description": "目标 Skill 名称"},
                    "category": {"type": "string", "description": "子资源类型"},
                },
                "required": ["content", "skill_name", "category"],
            },
            method=kc_check_duplicate,
        ),
        ToolDefinition(
            name="kc_write_resource",
            description="将格式化后的子资源写入目标 Skill 目录",
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "格式化后的内容"},
                    "skill_name": {"type": "string", "description": "目标 Skill 名称"},
                    "category": {"type": "string", "description": "子资源类型"},
                    "filename": {"type": "string", "description": "文件名（kebab-case）"},
                },
                "required": ["content", "skill_name", "category", "filename"],
            },
            method=kc_write_resource,
        ),
    ]
