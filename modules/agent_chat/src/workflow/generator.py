# -*- coding: utf-8 -*-
"""SOP 自动生成器 — 从工作流记录生成 Markdown SOP 文件。"""
from __future__ import annotations

import logging
import os
import platform
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def generate_sop_from_trace(
    workflow_summary: dict[str, Any],
    title: str = "",
    description: str = "",
) -> str:
    """从工作流摘要生成 SOP Markdown 内容。

    Args:
        workflow_summary: WorkflowTracker.get_workflow_summary() 的输出
        title: SOP 标题（留空则自动生成）
        description: SOP 描述（留空则自动生成）

    Returns:
        完整的 Markdown 字符串（含 YAML frontmatter）
    """
    tools = workflow_summary.get("unique_tools", [])
    steps = workflow_summary.get("steps", [])
    tool_sequence = workflow_summary.get("tool_sequence", [])

    if not title:
        title = _generate_title(tools)
    if not description:
        description = _generate_description(tools, steps)

    keywords = _extract_keywords(tools)

    lines: list[str] = [
        "---",
        f"title: {title}",
        f"keywords: [{', '.join(keywords)}]",
        f"description: {description}",
        "recommended_provider: glm",
        f"required_tools: [{', '.join(tools)}]",
        f"generated_at: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "source: auto_generated",
        "---",
        "",
        f"# {title}",
        "",
        "## 目录",
        "",
        "- [概述](#概述)",
        "- [前置条件](#前置条件)",
        "- [分析步骤](#分析步骤)",
        "- [注意事项](#注意事项)",
        "",
        "## 概述",
        "",
        description,
        "",
        "## 前置条件",
        "",
    ]

    for tool in tools:
        lines.append(f"- 工具 `{tool}` 可用")
    lines.append("")

    lines.append("## 分析步骤")
    lines.append("")

    seen_tools: set[str] = set()
    step_num = 0
    for step in steps:
        tool_name = step.get("tool", "")
        args_keys = step.get("args_keys", [])

        if tool_name in seen_tools and tool_name == (tool_sequence[step_num - 1] if step_num > 0 else ""):
            continue

        step_num += 1
        seen_tools.add(tool_name)

        step_desc = _tool_step_description(tool_name, args_keys)
        lines.append(f"### 步骤 {step_num}: {step_desc}")
        lines.append("")
        lines.append(f"调用工具 `{tool_name}`")
        if args_keys:
            lines.append(f"- 参数: {', '.join(f'`{k}`' for k in args_keys)}")
        lines.append("")

    lines.extend([
        "## 注意事项",
        "",
        "- 本 SOP 由工作流自动生成，建议根据实际场景调整步骤",
        "- 文件路径参数需要替换为实际路径",
        "",
    ])

    return "\n".join(lines)


def save_sop(
    content: str,
    save_dir: Path,
    filename: str = "",
) -> Path:
    """保存 SOP 到指定目录。

    Args:
        content: SOP Markdown 内容
        save_dir: 保存目录
        filename: 文件名（留空则从 title 生成）

    Returns:
        保存后的文件路径
    """
    save_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        match = re.search(r"^title:\s*(.+)$", content, re.MULTILINE)
        title = match.group(1).strip() if match else "custom_workflow"
        filename = _title_to_filename(title)

    if not filename.endswith(".md"):
        filename += ".md"

    target = save_dir / filename
    if target.exists():
        stem = target.stem
        for i in range(2, 100):
            candidate = save_dir / f"{stem}_{i}.md"
            if not candidate.exists():
                target = candidate
                break

    target.write_text(content, encoding="utf-8")
    logger.info("SOP 已保存: %s", target)
    return target


def open_sop_file(path: Path) -> None:
    """用系统默认编辑器打开 SOP 文件。"""
    try:
        if platform.system() == "Windows":
            os.startfile(str(path))
        elif platform.system() == "Darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception as exc:
        logger.warning("无法打开 SOP 文件 %s: %s", path, exc)


def _generate_title(tools: list[str]) -> str:
    """根据工具列表生成标题。"""
    tool_labels = {
        "pa_analyze": "Trace分析",
        "pa_parse": "Trace解析",
        "pdi_load_report": "PerfDog分析",
        "pdi_summarize": "PerfDog汇总",
        "gp_analyze_config": "策略审查",
        "device_status": "设备状态",
        "device_disguise": "设备伪装",
    }
    labels = []
    for t in tools:
        if t in tool_labels:
            label = tool_labels[t]
            if label not in labels:
                labels.append(label)
        else:
            labels.append(t)

    if labels:
        return " + ".join(labels[:3]) + " 工作流"
    return "自定义分析工作流"


def _generate_description(tools: list[str], steps: list[dict]) -> str:
    return f"使用 {len(tools)} 个工具、{len(steps)} 个步骤完成的分析工作流。"


def _extract_keywords(tools: list[str]) -> list[str]:
    """从工具名提取关键词。"""
    keyword_map = {
        "pa_": ["trace", "perfetto", "丢帧"],
        "pdi_": ["perfdog", "fps", "性能"],
        "gp_": ["策略", "配置", "gameperfconfig"],
        "device_": ["设备", "伪装"],
        "perf_": ["性能配置", "推送"],
    }
    kws: list[str] = []
    for tool in tools:
        for prefix, keywords in keyword_map.items():
            if tool.startswith(prefix):
                for kw in keywords:
                    if kw not in kws:
                        kws.append(kw)
                break
    return kws or ["自定义"]


def _tool_step_description(tool_name: str, args_keys: list[str]) -> str:
    """为工具调用生成步骤描述。"""
    desc_map = {
        "pa_analyze": "执行 Perfetto Trace 完整分析",
        "pa_parse": "解析 Perfetto Trace 文件",
        "pa_analyze_dims": "按维度分析 Trace",
        "pa_list_dims": "列出可用分析维度",
        "pa_history": "查询分析历史",
        "pdi_load_report": "加载 PerfDog 报告",
        "pdi_summarize": "汇总 PerfDog 性能指标",
        "gp_analyze_config": "解析性能策略配置",
        "device_status": "检查设备状态",
        "device_disguise": "执行设备伪装",
        "device_reset": "还原设备信息",
        "perf_push": "推送性能配置",
        "perf_reset": "还原性能配置",
        "perf_info": "查询性能配置信息",
    }
    return desc_map.get(tool_name, f"调用 {tool_name}")


def _title_to_filename(title: str) -> str:
    """将标题转换为文件名。"""
    name = title.lower()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s]+", "_", name)
    name = name.strip("_")
    return name[:50] if name else "custom_workflow"
