"""Pydantic AI Agent 定义 — Main / Sub / Review。"""

from __future__ import annotations

import logging
from typing import Any

from . import AnalysisRouting

logger = logging.getLogger(__name__)


def create_main_agent(model: Any) -> Any:
    """创建 MainAgent: 意图分析 + 场景路由。

    基于用户意图和 trace 概览信息（由 orchestrator 预注入 prompt），
    决定分析场景并输出 AnalysisRouting。
    """
    from pydantic_ai import Agent

    agent = Agent(
        model,
        output_type=AnalysisRouting,
        instructions=(
            "根据用户意图判断分析场景。场景: jank/anr/memory/startup/cpu/general。"
            "输出 scene, sop_name, process_name, reasoning。"
        ),
    )
    return agent


def create_sub_agent(model: Any, sop_content: str, pa_service: Any, compressor: Any = None) -> Any:
    """创建 SubAgent: 按 SOP 执行 trace 分析。

    每个 trace 一个独立实例，上下文完全隔离。
    工具返回 ToolReturn，压缩摘要给 LLM，原始数据通过 metadata 保留。
    """
    from pydantic_ai import Agent

    from .tools import build_analysis_tools

    tools = build_analysis_tools(pa_service, compressor)

    instructions = "你是 Perfetto trace 分析专家。中文输出。"
    if sop_content:
        instructions += f"\n\n{sop_content}"
    else:
        instructions += "\n\n请根据 trace 数据自主判断分析路径。"

    agent = Agent(
        model,
        instructions=instructions,
        tools=tools,
    )
    return agent


def create_review_agent(model: Any) -> Any:
    """创建 ReviewAgent: 交叉评审多个分析结论。"""
    from pydantic_ai import Agent

    agent = Agent(
        model,
        instructions=(
            "你是 Perfetto trace 分析评审专家。\n"
            "你的任务是对多个独立 trace 的分析结论进行交叉评审:\n\n"
            "1. 检查各结论之间的一致性\n"
            "2. 识别共性问题和差异\n"
            "3. 验证根因推理的合理性\n"
            "4. 如有矛盾，指出并提供判断\n"
            "5. 综合所有信息给出整体评审意见\n"
            "6. 所有输出使用中文"
        ),
    )
    return agent
