"""Agent system prompt 管理 — SOP 文件加载。"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SOP_DIR = Path(__file__).resolve().parents[2] / "skills" / "perfetto-analysis" / "sop"

_SCENE_SOP_MAP: dict[str, str] = {
    "jank": "jank-analysis.md",
    "anr": "anr-analysis.md",
    "memory": "memory-analysis.md",
    "startup": "startup-analysis.md",
    "cpu": "jank-analysis.md",
    "io": "io-blocking-analysis.md",
    "general": "general-analysis.md",
}


def load_sop(scene: str) -> str:
    """加载指定场景的 SOP 文档（完整加载，不截断）。

    通过 SKILL 路由匹配场景 SOP 文件。未匹配时返回空字符串，
    由 LLM 自主决定分析路径。
    """
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
        logger.debug("已加载 SOP: %s (%d 字符)", sop_path.name, len(content))
        return content
    except Exception as exc:
        logger.warning("SOP 加载失败: %s — %s", sop_path, exc)
        return ""
