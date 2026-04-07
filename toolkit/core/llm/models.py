# -*- coding: utf-8 -*-
"""LLM 模型元数据 — 上下文窗口大小映射表。"""

MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "glm-4-plus": 128_000,
    "glm-4-flash": 128_000,
    "glm-4-long": 1_000_000,
    "claude-sonnet-4-20250514": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
}

DEFAULT_CONTEXT_WINDOW = 128_000


def get_context_window(model_name: str) -> int:
    """获取模型的上下文窗口大小（token 数）。"""
    return MODEL_CONTEXT_WINDOWS.get(model_name, DEFAULT_CONTEXT_WINDOW)
