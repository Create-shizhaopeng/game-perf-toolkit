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

_DEFAULT_SOP = """\
## 通用分析 SOP

1. 使用 pa_trace_overview 获取 trace 概览
2. 根据概览信息判断关键进程和时间范围
3. 使用 pa_detect_jank 检测卡顿帧
4. 根据卡顿帧选择分析维度（cpu/thread/binder/io 等）
5. 使用 pa_analyze_dimension 逐维度分析
6. 综合各维度结果推理根因
7. 输出结论和建议
"""


def load_sop(scene: str) -> str:
    """加载指定场景的 SOP 文档。

    Args:
        scene: 分析场景名称

    Returns:
        SOP 文档内容
    """
    sop_file = _SCENE_SOP_MAP.get(scene, _SCENE_SOP_MAP.get("general", ""))
    if not sop_file:
        logger.info("场景 '%s' 无 SOP 映射，使用默认 SOP", scene)
        return _DEFAULT_SOP

    sop_path = _SOP_DIR / sop_file
    if not sop_path.exists():
        logger.info("SOP 文件不存在: %s，使用默认 SOP", sop_path)
        return _DEFAULT_SOP

    try:
        content = sop_path.read_text(encoding="utf-8")
        if len(content) > 3000:
            content = content[:3000] + "\n\n... (SOP 内容已截断，请按核心步骤执行)"
        logger.debug("已加载 SOP: %s (%d 字符)", sop_path.name, len(content))
        return content
    except Exception as exc:
        logger.warning("SOP 加载失败: %s — %s", sop_path, exc)
        return _DEFAULT_SOP
