"""Agent system prompt 管理 — SOP 文件加载 + 场景元数据解析。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from . import PrefetchSpec, SceneMeta

logger = logging.getLogger(__name__)

_SOP_DIR = Path(__file__).resolve().parents[2] / "skills" / "perfetto-analysis" / "sop"

_SCENE_SOP_MAP: dict[str, str] = {
    "jank": "jank-analysis.md",
    "anr": "anr-analysis.md",
    "memory": "memory-analysis.md",
    "startup": "startup-analysis.md",
    "cpu": "jank-analysis.md",
    "io": "io-block-analysis.md",
    "general": "general-analysis.md",
    "input-latency": "input-latency.md",
    "response-latency": "response-latency.md",
    "rotation": "rotation-analysis.md",
}

_scene_registry: dict[str, SceneMeta] | None = None


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """从 Markdown 内容中提取 YAML frontmatter 和正文。"""
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    try:
        meta = yaml.safe_load(content[3:end]) or {}
    except yaml.YAMLError:
        meta = {}
    body = content[end + 3:].lstrip("\n")
    return meta, body


def _build_scene_registry() -> dict[str, SceneMeta]:
    """扫描所有 SOP 文件，解析 frontmatter 构建场景元数据注册表。"""
    registry: dict[str, SceneMeta] = {}
    if not _SOP_DIR.exists():
        logger.warning("SOP 目录不存在: %s", _SOP_DIR)
        return registry

    for sop_file in _SOP_DIR.glob("*.md"):
        try:
            content = sop_file.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("读取 SOP 失败: %s — %s", sop_file, exc)
            continue

        meta, _ = _parse_frontmatter(content)
        scene = meta.get("scene")
        if not scene:
            continue

        prefetch_specs = []
        for pf in meta.get("prefetch", []):
            if isinstance(pf, dict) and "tool" in pf and "inject_as" in pf:
                prefetch_specs.append(PrefetchSpec(
                    tool=pf["tool"],
                    inject_as=pf["inject_as"],
                    args=pf.get("args", {}),
                ))

        registry[scene] = SceneMeta(
            scene=scene,
            display_name=meta.get("display_name", scene),
            priority_dims=meta.get("priority_dims", []),
            secondary_dims=meta.get("secondary_dims", []),
            optional_dims=meta.get("optional_dims", []),
            prefetch=prefetch_specs,
        )
        logger.debug("注册场景 '%s' (from %s)", scene, sop_file.name)

    return registry


def get_scene_registry() -> dict[str, SceneMeta]:
    """获取场景元数据注册表（懒加载，首次调用时扫描 SOP 文件）。"""
    global _scene_registry
    if _scene_registry is None:
        _scene_registry = _build_scene_registry()
    return _scene_registry


def get_scene_meta(scene: str) -> SceneMeta | None:
    """获取指定场景的元数据。"""
    return get_scene_registry().get(scene)


def build_reasoning_chain_prompt(
    sop_content: str = "",
    scene_meta: SceneMeta | None = None,
    known_info: str = "",
) -> str:
    """构建 SubAgent 推理链 prompt 模板（5 部分）。

    1. 角色定义
    2. 已知信息占位（由编排器注入预取结果）
    3. 场景 SOP 规则占位
    4. 维度优先级占位
    5. 行为约束（Phase A/B/C 推理链）
    """
    parts: list[str] = []

    parts.append(
        "你是 Perfetto trace 分析专家。所有输出使用中文。\n"
        "你的职责是通过调用工具系统性分析 trace 数据，定位性能问题根因。"
    )

    if known_info:
        parts.append(f"\n{known_info}")

    if sop_content:
        parts.append(f"\n## 分析 SOP\n\n{sop_content}")
    else:
        parts.append("\n未找到匹配的分析 SOP，请根据 trace 数据自主判断分析路径。")

    if scene_meta:
        dim_lines = []
        if scene_meta.priority_dims:
            dim_lines.append(f"- 必查维度（优先调用）: {', '.join(scene_meta.priority_dims)}")
        if scene_meta.secondary_dims:
            dim_lines.append(f"- 推荐维度（按需调用）: {', '.join(scene_meta.secondary_dims)}")
        if scene_meta.optional_dims:
            dim_lines.append(f"- 辅助维度（仅在需要时调用）: {', '.join(scene_meta.optional_dims)}")
        if dim_lines:
            parts.append("\n## 维度优先级\n\n" + "\n".join(dim_lines))

    parts.append(
        "\n## 推理链约束\n\n"
        "请严格按照以下三阶段执行分析：\n\n"
        "### Phase A: 排查\n"
        "按维度优先级依次调用工具，收集各维度数据。"
        "优先排查必查维度，发现异常后再展开推荐维度验证。\n\n"
        "### Phase B: 验证与交叉分析\n"
        "对 Phase A 发现的异常进行交叉验证：\n"
        "- 同一时间窗口内是否有多维度异常关联\n"
        "- 因果链是否成立（例如 CPU 限频 → 线程等待 → 帧耗时增加）\n"
        "- 如果已发现 ≥2 个强根因，可跳过低优先级维度\n\n"
        "### Phase C: 结论输出\n"
        "将分析结果组织为结构化报告，包含问题概述、根因分析、关键数据和优化建议。"
    )

    return "\n".join(parts)


def load_sop(scene: str, sop_name: str = "") -> str:
    """加载指定场景的 SOP 文档（完整加载，不截断）。

    优先使用 MainAgent 指定的 sop_name（如果文件存在），
    否则通过 scene → _SCENE_SOP_MAP 匹配。
    未匹配时返回空字符串，由 LLM 自主决定分析路径。
    """
    if sop_name:
        sop_path = _SOP_DIR / sop_name
        if sop_path.exists():
            try:
                content = sop_path.read_text(encoding="utf-8")
                logger.debug("已加载 SOP (sop_name): %s (%d 字符)", sop_path.name, len(content))
                return content
            except Exception as exc:
                logger.warning("SOP 加载失败 (sop_name): %s — %s", sop_path, exc)
        else:
            logger.debug("sop_name '%s' 文件不存在，回退到 scene 映射", sop_name)

    sop_file = _SCENE_SOP_MAP.get(scene)
    if not sop_file:
        logger.warning("场景 '%s' 无 SOP 映射，LLM 将自主分析", scene)
        return ""

    sop_path = _SOP_DIR / sop_file
    if not sop_path.exists():
        logger.warning("SOP 文件不存在: %s，LLM 将自主分析", sop_path)
        return ""

    try:
        content = sop_path.read_text(encoding="utf-8")
        logger.debug("已加载 SOP (scene): %s (%d 字符)", sop_path.name, len(content))
        return content
    except Exception as exc:
        logger.warning("SOP 加载失败: %s — %s", sop_path, exc)
        return ""
