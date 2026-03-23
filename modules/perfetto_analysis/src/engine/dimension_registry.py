# -*- coding: utf-8 -*-
"""维度注册表：维度 ID → 依赖/描述映射，拓扑排序依赖解析，维度列表输出。"""
from __future__ import annotations

DIMENSIONS: dict[str, dict] = {
    "cpu": {
        "frs": ["FR-101", "FR-106", "FR-107", "FR-108"],
        "deps": [],
        "desc": "CPU 拓扑 + 频率/爬升 + 大小核调度 + 调度延迟",
    },
    "thread": {
        "frs": ["FR-104", "FR-105"],
        "deps": [],
        "desc": "线程状态时间线 + Block/Waker 链",
    },
    "binder": {
        "frs": ["FR-109", "FR-110"],
        "deps": [],
        "desc": "Binder 调用 + 线程池饱和度",
    },
    "io": {
        "frs": ["FR-111"],
        "deps": [],
        "desc": "文件 IO 阻塞",
    },
    "gc": {
        "frs": ["FR-114"],
        "deps": [],
        "desc": "GC 阻塞",
    },
    "gpu": {
        "frs": ["FR-115"],
        "deps": [],
        "desc": "GPU 渲染耗时",
    },
    "sf": {
        "frs": ["FR-116"],
        "deps": [],
        "desc": "SurfaceFlinger 合成耗时",
    },
    "input": {
        "frs": ["FR-117"],
        "deps": [],
        "desc": "输入事件延迟",
    },
    "lock": {
        "frs": ["FR-118"],
        "deps": [],
        "desc": "Java Monitor 锁竞争",
    },
    "summary": {
        "frs": ["FR-119"],
        "deps": ["cpu"],
        "desc": "全 trace 整体分析",
    },
}

ALL_DIMENSION_IDS = list(DIMENSIONS.keys())


def resolve_dependencies(requested: list[str]) -> list[str]:
    """
    拓扑排序：自动补全依赖维度，返回执行顺序。
    无效维度 ID 会被忽略（由调用方校验）。
    返回列表中依赖项排在被依赖项之前。
    """
    valid = [d for d in requested if d in DIMENSIONS]
    needed: set[str] = set()

    def _collect(dim_id: str) -> None:
        if dim_id in needed:
            return
        needed.add(dim_id)
        for dep in DIMENSIONS[dim_id]["deps"]:
            _collect(dep)

    for d in valid:
        _collect(d)

    ordered: list[str] = []
    visited: set[str] = set()

    def _visit(dim_id: str) -> None:
        if dim_id in visited:
            return
        visited.add(dim_id)
        for dep in DIMENSIONS[dim_id]["deps"]:
            if dep in needed:
                _visit(dep)
        ordered.append(dim_id)

    for d in sorted(needed):
        _visit(d)

    return ordered


def list_dimensions() -> str:
    """返回维度列表的格式化字符串（用于 --analyze 无参数输出）。"""
    lines = ["可用分析维度：", ""]
    max_id_len = max(len(d) for d in DIMENSIONS)
    for dim_id, info in DIMENSIONS.items():
        deps_str = f" (依赖: {', '.join(info['deps'])})" if info["deps"] else ""
        lines.append(f"  {dim_id:<{max_id_len}}  {info['desc']}{deps_str}")
    lines.append("")
    lines.append("用法: --analyze <维度1> [<维度2> ...]")
    return "\n".join(lines)


def get_auto_completed(requested: list[str], resolved: list[str]) -> list[str]:
    """返回自动补全添加的维度列表（resolved 中有但 requested 中没有的）。"""
    req_set = set(requested)
    return [d for d in resolved if d not in req_set]
