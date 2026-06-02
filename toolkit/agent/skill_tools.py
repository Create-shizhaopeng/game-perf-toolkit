# -*- coding: utf-8 -*-
"""Skill 工具生成 — build_skill_tools() 统一创建 9 个 Agent 可用的 Skill 工具。"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from toolkit.core.models import ToolDefinition

logger = logging.getLogger(__name__)

_CATEGORY_RULES = [
    ("sop", ["步骤", "流程", "操作指引", "决策树", "step", "procedure", "SOP"]),
    ("patterns", ["原因", "根因", "当.*发生", "方案", "pattern", "root cause"]),
    ("cases", ["分析案例", "设备", "trace", "时间戳", "结论", "case study"]),
]


# ── Curator utility functions ──────────────────────────────────────────

def classify_document(content: str) -> list[dict[str, Any]]:
    sections = _split_sections(content)
    results: list[dict[str, Any]] = []
    for title, body in sections:
        category, confidence = _classify_section(title, body)
        summary = (title or body[:80]).strip()
        results.append({
            "category": category, "confidence": round(confidence, 2),
            "summary": summary[:100],
            "content": f"# {title}\n\n{body}" if title else body,
        })
    if not results:
        category, confidence = _classify_section("", content)
        results.append({
            "category": category, "confidence": round(confidence, 2),
            "summary": content[:100].strip(), "content": content,
        })
    return results


def match_skill(classified_items: list[dict], available_skills: list[dict[str, Any]],
                user_override: str | None = None) -> list[dict[str, Any]]:
    results = []
    for item in classified_items:
        if user_override:
            results.append({"item_summary": item["summary"], "matched_skill": user_override,
                            "score": 1.0, "category": item["category"]})
            continue
        best_skill, best_score = "", 0.0
        item_text = f"{item['summary']} {item['category']}".lower()
        for skill in available_skills:
            skill_text = (
                f"{skill.get('name', '')} {skill.get('description', '')} "
                f"{' '.join(skill.get('tags', []))}"
            ).lower()
            score = SequenceMatcher(None, item_text, skill_text).ratio()
            score += sum(1 for tag in skill.get("tags", []) if tag.lower() in item_text) * 0.15
            if score > best_score:
                best_score, best_skill = score, skill.get("name", "")
        results.append({"item_summary": item["summary"], "matched_skill": best_skill,
                        "score": round(best_score, 2), "category": item["category"]})
    return results


def format_resource(content: str, category: str, source_doc: str = "") -> str:
    lines = content.strip().split("\n")
    title, body = "", content
    if lines and lines[0].startswith("#"):
        title = lines[0].lstrip("#").strip()
        body = "\n".join(lines[1:]).strip()
    name = title or "Untitled"
    header = f"---\ntitle: {name}\ncategory: {category}\n"
    if source_doc:
        header += f"source: {source_doc}\n"
    header += "---\n\n"
    return header + f"# {name}\n\n{body}"


def check_duplicate(new_content: str, existing_files: list[Path],
                    threshold: float = 0.70) -> list[dict[str, Any]]:
    duplicates = []
    new_stripped = re.sub(r"\s+", " ", new_content.strip())
    for f in existing_files:
        if not f.exists() or not f.suffix == ".md":
            continue
        existing = re.sub(r"\s+", " ", f.read_text(encoding="utf-8").strip())
        ratio = SequenceMatcher(None, new_stripped, existing).ratio()
        if ratio >= threshold:
            duplicates.append({"file": f.name, "similarity": round(ratio, 2)})
    return duplicates


def write_resource(content: str, skill_dir: Path, category: str, filename: str) -> str:
    target_dir = skill_dir / category
    target_dir.mkdir(parents=True, exist_ok=True)
    if not filename.endswith(".md"):
        filename += ".md"
    target = target_dir / filename
    target.write_text(content, encoding="utf-8")
    logger.info("知识资源已写入: %s", target)
    return str(target)


# ── Internal helpers ───────────────────────────────────────────────────

def _split_sections(text: str) -> list[tuple[str, str]]:
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


# ── build_skill_tools ──────────────────────────────────────────────────

def build_skill_tools(skill_registry, router=None) -> list[ToolDefinition]:
    """生成全部 Skill Agent 工具（4 base + 5 curator），基于 SkillRegistry。"""
    sr = skill_registry

    # ── Base tools ──

    def skill_list() -> str:
        metas = sr.get_skills()
        if not metas:
            return "当前无可用 Skill"
        lines = []
        for m in metas:
            tags = ", ".join(getattr(m, 'tags', []) or [])
            lines.append(f"- {m.name}: {m.description} [{tags}]")
        return "\n".join(lines)

    def skill_load(name: str) -> str:
        content = sr.get_skill_content(name)
        if content is None:
            return f"Skill '{name}' 不存在或加载失败"
        return content

    def skill_load_resource(skill_name: str, resource_path: str) -> str:
        content = sr.get_resource(skill_name, resource_path)
        if content is None:
            return f"资源不存在: {resource_path}"
        return content

    def skill_list_resources(name: str) -> str:
        resources = sr.list_resources(name)
        if not resources:
            return f"Skill '{name}' 无子资源"
        lines = []
        for cat, files in resources.items():
            lines.append(f"[{cat}]")
            for f in files:
                lines.append(f"  - {f}")
        return "\n".join(lines)

    base = [
        ToolDefinition(name="skill_list", description="列出所有可用 Skill 及其描述、标签",
                       parameters={"type": "object", "properties": {}}, method=skill_list),
        ToolDefinition(name="skill_load", description="加载指定 Skill 的完整内容（SKILL.md），获取分析方法论和工具使用指南",
                       parameters={"type": "object", "properties": {"name": {"type": "string", "description": "Skill 名称"}},
                                   "required": ["name"]}, method=skill_load),
        ToolDefinition(name="skill_load_resource", description="按需加载 Skill 的子资源（SOP、模式库、案例），获取领域知识",
                       parameters={"type": "object",
                                   "properties": {"skill_name": {"type": "string", "description": "Skill 名称"},
                                                  "resource_path": {"type": "string", "description": "子资源路径，如 sop/jank-analysis.md"}},
                                   "required": ["skill_name", "resource_path"]}, method=skill_load_resource),
        ToolDefinition(name="skill_list_resources", description="列出 Skill 的所有子资源文件目录",
                       parameters={"type": "object", "properties": {"name": {"type": "string", "description": "Skill 名称"}},
                                   "required": ["name"]}, method=skill_list_resources),
    ]

    # ── Curator tools ──

    def kc_classify_document(content: str) -> str:
        results = classify_document(content)
        lines = [f"- [{r['category']}] ({r['confidence']:.0%}) {r['summary']}" for r in results]
        return "\n".join(lines) if lines else "无法识别文档类型"

    def kc_match_skill(content: str, skill_name: str = "") -> str:
        items = classify_document(content)
        metas = sr.get_skills()
        skills_info = [{"name": m.name, "description": m.description, "tags": getattr(m, 'tags', []) or []}
                       for m in metas]
        override = skill_name if skill_name else None
        results = match_skill(items, skills_info, user_override=override)
        lines = [f"- {r['item_summary'][:50]} → {r['matched_skill']} (score: {r['score']:.0%}, type: {r['category']})"
                 for r in results]
        return "\n".join(lines) if lines else "无匹配 Skill"

    def kc_format_resource(content: str, category: str, source_doc: str = "") -> str:
        return format_resource(content, category, source_doc)

    def kc_check_duplicate(content: str, skill_name: str, category: str) -> str:
        meta = sr.get_skill(skill_name)
        if not meta:
            return f"Skill '{skill_name}' 不存在"
        cat_dir = meta.skill_dir / category
        if not cat_dir.exists():
            return "目标目录不存在，无需去重"
        existing = list(cat_dir.glob("*.md"))
        dups = check_duplicate(content, existing)
        if not dups:
            return "无重复内容"
        return "发现重复:\n" + "\n".join(f"- {d['file']} (相似度: {d['similarity']:.0%})" for d in dups)

    def kc_write_resource(content: str, skill_name: str, category: str, filename: str) -> str:
        meta = sr.get_skill(skill_name)
        if not meta:
            return f"Skill '{skill_name}' 不存在"
        return write_resource(content, meta.skill_dir, category, filename)

    curator = [
        ToolDefinition(name="kc_classify_document", description="对输入文档进行内容分类（SOP/根因模式/案例）",
                       parameters={"type": "object",
                                   "properties": {"content": {"type": "string", "description": "文档内容"}},
                                   "required": ["content"]}, method=kc_classify_document),
        ToolDefinition(name="kc_match_skill", description="将分类内容匹配到目标 Skill",
                       parameters={"type": "object",
                                   "properties": {"content": {"type": "string", "description": "文档内容"},
                                                  "skill_name": {"type": "string", "description": "指定目标 Skill（可选）"}},
                                   "required": ["content"]}, method=kc_match_skill),
        ToolDefinition(name="kc_format_resource", description="按标准模板格式化子资源内容",
                       parameters={"type": "object",
                                   "properties": {"content": {"type": "string", "description": "待格式化内容"},
                                                  "category": {"type": "string", "description": "类型: sop/patterns/cases"},
                                                  "source_doc": {"type": "string", "description": "原始文档名"}},
                                   "required": ["content", "category"]}, method=kc_format_resource),
        ToolDefinition(name="kc_check_duplicate", description="检查新内容与目标 Skill 已有子资源的重复度",
                       parameters={"type": "object",
                                   "properties": {"content": {"type": "string", "description": "新内容"},
                                                  "skill_name": {"type": "string", "description": "目标 Skill 名称"},
                                                  "category": {"type": "string", "description": "子资源类型"}},
                                   "required": ["content", "skill_name", "category"]}, method=kc_check_duplicate),
        ToolDefinition(name="kc_write_resource", description="将格式化后的子资源写入目标 Skill 目录",
                       parameters={"type": "object",
                                   "properties": {"content": {"type": "string", "description": "格式化后的内容"},
                                                  "skill_name": {"type": "string", "description": "目标 Skill 名称"},
                                                  "category": {"type": "string", "description": "子资源类型"},
                                                  "filename": {"type": "string", "description": "文件名（kebab-case）"}},
                                   "required": ["content", "skill_name", "category", "filename"]}, method=kc_write_resource),
    ]

    return base + curator
