# -*- coding: utf-8 -*-
"""三段式 System Prompt 组装。

借鉴 Hermes Agent 设计:
  Stable   — 身份 + 工具摘要 + Skill 索引 + 使用指导（会话期间不变）
  Context  — 用户上下文文件 + 额外 system_message
  Volatile — Memory 快照 + 时间戳 / 会话 ID
"""
from __future__ import annotations

from typing import Any

_IDENTITY_ZH = """你是 LV Game Toolkit 的智能助手，专注于游戏性能分析与测试工具。
你可以访问已注册的工具和 Skill 来帮助用户完成分析任务。"""

_USAGE_GUIDANCE_ZH = """## 使用指导
- 复杂任务 (5+ 工具调用) 完成后，考虑沉淀为新的 Skill
- 遇到新的分析模式时，使用 skill_manage 保存经验
- 不确定使用哪个工具时，先用 skill_list 查看可用 Skill"""


def build_system_prompt(
    *,
    tools: list | None = None,
    skills: list | None = None,
    language: str = "zh",
    extra: str = "",
    report_index: Any = None,
    conv_id: str = "",
) -> str:
    """组装三段式 System Prompt。"""
    stable = _build_stable_prompt(tools or [], skills or [], language, report_index)
    context = _build_context_prompt(extra)
    volatile = _build_volatile_prompt(conv_id)
    return "\n\n".join([stable, context, volatile])


def _build_stable_prompt(
    tools: list, skills: list, language: str, report_index: Any = None
) -> str:
    """Stable 层：身份 + 工具摘要 + Skill 索引 + 使用指导（≤3000 chars）。"""
    parts = []

    # 身份
    parts.append(_IDENTITY_ZH)

    # 工具摘要
    if tools:
        tool_lines = ["## 可用工具"]
        for t in tools:
            tool_lines.append(f"- {t.name}: {t.description[:80]}")
        parts.append("\n".join(tool_lines))

    # Skill 索引
    if skills:
        skill_lines = ["## 可用 Skill"]
        for s in skills:
            name = getattr(s, 'name', str(s))
            desc = getattr(s, 'description', '')
            skill_lines.append(f"- {name}: {desc[:100]}")
        parts.append("\n".join(skill_lines))

    # Report context (if available)
    if report_index:
        try:
            ctx = report_index.get_context_text(top_n=3)
            if ctx:
                parts.append(ctx[:500])
        except Exception:
            pass

    parts.append(_USAGE_GUIDANCE_ZH)

    result = "\n\n".join(parts)
    # Length control: trim skill index if needed
    if len(result) > 3000:
        # Simplify to name-only skill list
        parts.pop()
        if skills:
            short = ", ".join(getattr(s, 'name', str(s)) for s in skills)
            parts.insert(-1, f"可用 Skill: {short}")
        parts.append(_USAGE_GUIDANCE_ZH)
        result = "\n\n".join(parts)
    return result


def _build_context_prompt(extra: str) -> str:
    """Context 层：用户提供的上下文文件 + 额外 system_message。"""
    parts = []
    if extra:
        parts.append(extra)
    return "\n".join(parts)


def _build_volatile_prompt(conv_id: str = "") -> str:
    """Volatile 层：会话 ID + 时间戳。"""
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts = []
    if conv_id:
        parts.append(f"[Session: {conv_id}]")
    parts.append(f"[System Time: {ts}]")
    return " ".join(parts)
