"""Pydantic AI Agent 定义 — Main / Sub / Review。"""

from __future__ import annotations

import logging
from typing import Any

from . import AnalysisOutput, AnalysisRouting, SceneMeta

logger = logging.getLogger(__name__)


def create_main_agent(model: Any) -> Any:
    """创建 MainAgent: 意图分析 + 场景路由 (LLM 动态路由)。

    基于用户意图和 trace 概览信息，匹配可用 SOP 场景，
    决定分析场景并输出 AnalysisRouting。
    """
    from pydantic_ai import Agent
    from .prompts import get_scene_registry

    registry = get_scene_registry()
    available_scenes = ", ".join(
        f"{s.scene}({s.display_name})" if s.display_name else s.scene
        for s in registry.values()
    ) if registry else "jank, anr, memory, startup, cpu, general"

    agent = Agent(
        model,
        output_type=AnalysisRouting,
        instructions=(
            "你是 Perfetto trace 分析路由器。根据用户意图和 trace 信息判断分析场景。\n"
            f"可用场景: {available_scenes}\n"
            "如果用户意图不明确，默认路由到 general 场景。\n"
            "输出 scene, sop_name, process_name, reasoning。"
        ),
    )
    return agent


def create_sub_agent(
    model: Any,
    sop_content: str,
    pa_service: Any,
    compressor: Any = None,
    scene_meta: SceneMeta | None = None,
) -> Any:
    """创建 SubAgent: 按推理链模板 + SOP 执行 trace 分析。

    每个 trace 一个独立实例，上下文完全隔离。
    工具返回 ToolReturn，压缩摘要给 LLM，原始数据通过 metadata 保留。
    """
    from pydantic_ai import Agent

    from .tools import build_analysis_tools
    from .prompts import build_reasoning_chain_prompt

    tools = build_analysis_tools(pa_service, compressor)

    instructions = build_reasoning_chain_prompt(
        sop_content=sop_content,
        scene_meta=scene_meta,
    )

    agent = Agent(
        model,
        instructions=instructions,
        tools=tools,
        output_type=AnalysisOutput,
        retries=1,
    )
    return agent


def create_review_agent(model: Any, review_type: str = "cross_compare") -> Any:
    """创建 ReviewAgent，使用 output_type=ReviewResult 实现结构化输出。

    Args:
        model: LLM 模型实例
        review_type: 评审类型 — cross_compare / self_check / individual_review
    """
    from pydantic_ai import Agent
    from . import ReviewResult

    _instructions = {
        "cross_compare": (
            "你是 Perfetto trace 分析评审专家。\n"
            "你的任务是对多个同场景 trace 的分析结论进行交叉评审:\n\n"
            "1. 检查各结论之间的一致性 (cross_consistency)\n"
            "2. 识别共性问题 (common_patterns)\n"
            "3. 指出矛盾之处 (contradictions)\n"
            "4. 对每个 trace 的每个根因给出置信度调整建议 (confidence_adjustments)\n"
            "   - adjustment 范围: [-0.3, +0.3]，正值表示分析可信度高，负值表示存疑\n"
            "   - tag 必须与根因的 tag 字段完全一致\n"
            "5. 综合给出整体评审意见 (overall_assessment)\n"
            "6. 所有输出使用中文"
        ),
        "self_check": (
            "你是 Perfetto trace 分析评审专家。\n"
            "你的任务是对单个 trace 的分析结论进行质量自检:\n\n"
            "1. 验证各根因之间的逻辑一致性\n"
            "2. 检查证据链是否充分\n"
            "3. 对每个根因给出置信度调整建议 (confidence_adjustments)\n"
            "   - adjustment 范围: [-0.3, +0.3]\n"
            "   - tag 必须与根因的 tag 字段完全一致\n"
            "4. 综合给出整体评审意见 (overall_assessment)\n"
            "5. 所有输出使用中文"
        ),
        "individual_review": (
            "你是 Perfetto trace 分析评审专家。\n"
            "你的任务是对低置信度的分析结论进行独立评审:\n\n"
            "1. 验证根因推理的合理性\n"
            "2. 检查证据与结论的关联性\n"
            "3. 对每个根因给出置信度调整建议 (confidence_adjustments)\n"
            "   - adjustment 范围: [-0.3, +0.3]\n"
            "   - tag 必须与根因的 tag 字段完全一致\n"
            "4. 综合给出整体评审意见 (overall_assessment)\n"
            "5. 所有输出使用中文"
        ),
    }

    agent = Agent(
        model,
        instructions=_instructions.get(review_type, _instructions["cross_compare"]),
        output_type=ReviewResult,
    )
    return agent
