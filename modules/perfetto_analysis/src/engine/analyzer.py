# -*- coding: utf-8 -*-
"""Phase 2 编排器：逐帧分析 + 整体分析的调度中心。"""
from __future__ import annotations

import sys
from typing import Any

from . import app_type as app_type_mod
from . import cpu_topology as cpu_topo_mod
from . import frame_boundary as fb_mod
from . import dimension_registry as dim_reg
from . import report_writer


# 维度 → 分析函数映射
_DIMENSION_ANALYZERS: dict[str, Any] = {}


def _register_builtin_dimensions() -> None:
    """注册所有内置维度分析函数。"""
    try:
        from . import thread_analysis
        _DIMENSION_ANALYZERS["thread"] = _wrap_thread_analyzer(thread_analysis)
    except ImportError:
        pass

    try:
        from . import cpu_analysis
        _DIMENSION_ANALYZERS["cpu"] = _wrap_cpu_analyzer(cpu_analysis)
    except ImportError:
        pass

    try:
        from . import binder_analysis
        _DIMENSION_ANALYZERS["binder"] = _wrap_binder_analyzer(binder_analysis)
    except ImportError:
        pass

    try:
        from . import io_analysis
        _DIMENSION_ANALYZERS["io"] = _wrap_io_analyzer(io_analysis)
    except ImportError:
        pass

    try:
        from . import gc_analysis
        _DIMENSION_ANALYZERS["gc"] = _wrap_optional_analyzer(gc_analysis, "analyze_gc", "gc")
    except ImportError:
        pass

    try:
        from . import gpu_analysis
        _DIMENSION_ANALYZERS["gpu"] = _wrap_optional_analyzer(gpu_analysis, "analyze_gpu", "gpu")
    except ImportError:
        pass

    try:
        from . import sf_analysis
        _DIMENSION_ANALYZERS["sf"] = _wrap_optional_analyzer(sf_analysis, "analyze_sf", "sf")
    except ImportError:
        pass

    try:
        from . import input_analysis
        _DIMENSION_ANALYZERS["input"] = _wrap_optional_analyzer(input_analysis, "analyze_input", "input")
    except ImportError:
        pass

    try:
        from . import lock_analysis
        _DIMENSION_ANALYZERS["lock"] = _wrap_optional_analyzer(lock_analysis, "analyze_lock", "lock")
    except ImportError:
        pass


def _wrap_thread_analyzer(mod: Any) -> Any:
    def _analyze(tp, window_start_ns, window_end_ns, target_utids, **kw):
        return mod.analyze_thread_states(tp, window_start_ns, window_end_ns, target_utids)
    return _analyze


def _wrap_cpu_analyzer(mod: Any) -> Any:
    def _analyze(tp, window_start_ns, window_end_ns, target_utids, topology=None, sched_latency_ms=1.0, **kw):
        return mod.analyze_cpu(tp, window_start_ns, window_end_ns, target_utids, topology, sched_latency_ms)
    return _analyze


def _wrap_binder_analyzer(mod: Any) -> Any:
    def _analyze(tp, window_start_ns, window_end_ns, target_utids, upid=None, slow_binder_ms=2.0, **kw):
        return mod.analyze_binder(tp, window_start_ns, window_end_ns, target_utids, upid, slow_binder_ms)
    return _analyze


def _wrap_io_analyzer(mod: Any) -> Any:
    def _analyze(tp, window_start_ns, window_end_ns, target_utids, **kw):
        return mod.analyze_io(tp, window_start_ns, window_end_ns, target_utids)
    return _analyze


def _wrap_optional_analyzer(mod: Any, func_name: str, dim_name: str) -> Any:
    func = getattr(mod, func_name)
    def _analyze(tp, window_start_ns, window_end_ns, target_utids, upid=None, **kw):
        return func(tp, window_start_ns, window_end_ns, target_utids, upid=upid)
    return _analyze


_register_builtin_dimensions()


def register_dimension(dim_id: str, analyze_func: Any) -> None:
    """注册维度分析函数。"""
    _DIMENSION_ANALYZERS[dim_id] = analyze_func


def analyze_jank(
    tp: Any,
    parse_result: dict[str, Any],
    process_name: str | None = None,
    app_type_override: str = "auto",
    analyze_top: int = 20,
    slow_binder_ms: float = 2.0,
    sched_latency_ms: float = 1.0,
    dimensions: list[str] | None = None,
) -> dict[str, Any]:
    """
    完整分析流程入口（--export 模式）。
    返回分析结果 dict。
    """
    result: dict[str, Any] = {
        "app_type": "app",
        "cpu_topology": {},
        "per_jank_analyses": [],
        "summary_analysis": {},
    }

    if not process_name:
        print(
            "[perfetto_analysis] 提示: 请通过 --process 指定目标 App",
            file=sys.stderr,
        )

    # App 类型检测
    detected_type = app_type_mod.detect_app_type(tp, process_name, app_type_override)
    result["app_type"] = detected_type

    # 目标进程 upid
    upid = None
    if process_name:
        upid = app_type_mod.find_target_upid(tp, process_name)
        if upid is None:
            print(
                f"[perfetto_analysis] 错误: 指定进程在 trace 中未找到: {process_name}",
                file=sys.stderr,
            )
            return result

    # CPU 拓扑
    topology = cpu_topo_mod.init_cpu_topology(tp)
    result["cpu_topology"] = topology

    # 获取关键线程 utids
    target_utids = _get_target_utids(tp, upid) if upid else []

    # jank_records
    jank_records = parse_result.get("jank_records", [])
    if not jank_records:
        print(
            "[perfetto_analysis] 提示: 本 trace 无丢帧，跳过逐帧分析",
            file=sys.stderr,
        )

    # 逐帧分析（Top N）
    stand_vsync_ms = parse_result.get("stand_vsync_ms", 16.67)
    stand_vsync_ns = int(stand_vsync_ms * 1e6)
    sorted_janks = sorted(jank_records, key=lambda j: j.get("jank_num", 0), reverse=True)
    top_janks = sorted_janks[:analyze_top] if analyze_top > 0 else []

    use_dims = dimensions or dim_reg.ALL_DIMENSION_IDS

    for idx, jank in enumerate(top_janks):
        jank_analysis = _analyze_single_jank(
            tp, jank, idx, upid, target_utids, topology,
            stand_vsync_ns, detected_type, use_dims,
            slow_binder_ms=slow_binder_ms,
            sched_latency_ms=sched_latency_ms,
        )
        result["per_jank_analyses"].append(jank_analysis)

    # 整体分析
    if "summary" in use_dims:
        result["summary_analysis"] = _run_summary_analysis(
            tp, parse_result, upid, target_utids, topology,
        )

    return result


def analyze_dimensions(
    tp: Any,
    parse_result: dict[str, Any],
    process_name: str | None,
    dimensions: list[str],
    jank_indices: list[int] | None = None,
    window: tuple[int, int] | None = None,
    app_type_override: str = "auto",
    analyze_top: int = 20,
    slow_binder_ms: float = 2.0,
    sched_latency_ms: float = 1.0,
) -> dict[str, Any]:
    """独立分析模式入口（--analyze）。"""
    result: dict[str, Any] = {}

    # App 类型
    detected_type = app_type_mod.detect_app_type(tp, process_name, app_type_override)
    result["app_type"] = detected_type

    # upid
    upid = None
    if process_name:
        upid = app_type_mod.find_target_upid(tp, process_name)
        if upid is None:
            print(
                f"[perfetto_analysis] 错误: 指定进程在 trace 中未找到: {process_name}",
                file=sys.stderr,
            )
            return result

    # CPU 拓扑（cpu 维度需要）
    topology = {}
    if "cpu" in dimensions or "summary" in dimensions:
        topology = cpu_topo_mod.init_cpu_topology(tp)
    result["cpu_topology"] = topology

    target_utids = _get_target_utids(tp, upid) if upid else []

    # 确定分析的 jank 记录
    jank_records = parse_result.get("jank_records", [])
    sorted_janks = sorted(jank_records, key=lambda j: j.get("jank_num", 0), reverse=True)

    if jank_indices is not None:
        selected_janks = []
        for idx in jank_indices:
            if 0 <= idx < len(sorted_janks):
                selected_janks.append(sorted_janks[idx])
            else:
                print(
                    f"[perfetto_analysis] 错误: 指定的 jank 序号超出范围: {idx}，共 {len(sorted_janks)} 条 jank_record",
                    file=sys.stderr,
                )
                return result
        sorted_janks = selected_janks
    elif analyze_top > 0:
        sorted_janks = sorted_janks[:analyze_top]

    stand_vsync_ms = parse_result.get("stand_vsync_ms", 16.67)
    stand_vsync_ns = int(stand_vsync_ms * 1e6)

    # 逐帧维度分析
    per_frame_dims = [d for d in dimensions if d != "summary"]
    if per_frame_dims and sorted_janks:
        per_jank = []
        for idx, jank in enumerate(sorted_janks):
            jank_analysis = _analyze_single_jank(
                tp, jank, idx, upid, target_utids, topology,
                stand_vsync_ns, detected_type, per_frame_dims,
                slow_binder_ms=slow_binder_ms,
                sched_latency_ms=sched_latency_ms,
            )
            per_jank.append(jank_analysis)
        result["per_jank_analyses"] = per_jank

    # 整体分析
    if "summary" in dimensions:
        result["summary_analysis"] = _run_summary_analysis(
            tp, parse_result, upid, target_utids, topology,
        )

    return result


def _analyze_single_jank(
    tp: Any,
    jank: dict[str, Any],
    index: int,
    upid: int | None,
    target_utids: list[int],
    topology: dict[str, Any],
    stand_vsync_ns: int,
    app_type: str,
    dimensions: list[str],
    slow_binder_ms: float = 2.0,
    sched_latency_ms: float = 1.0,
) -> dict[str, Any]:
    """对单条 jank 执行指定维度的分析。"""
    ajt1 = jank.get("ajt1_ns", 0)
    ajt2 = jank.get("ajt2_ns", 0)
    sjt1 = jank.get("sjt1_ns", 0)
    sjt2 = jank.get("sjt2_ns", 0)

    window_start = max(0, ajt1 - 2 * stand_vsync_ns) if ajt1 else sjt1
    window_end = sjt2 + stand_vsync_ns if sjt2 else ajt2

    jank_num = jank.get("jank_num", 0)
    truncated = jank_num > 20

    jank_data: dict[str, Any] = {
        "jank_index": index,
        "jank_num": jank_num,
        "jank_type": jank.get("jank_type", ""),
        "window_start_ns": window_start,
        "window_end_ns": window_end,
        "app_type": app_type,
        "data_summary": {},
        "truncated": truncated,
    }

    if truncated:
        print(
            f"[perfetto_analysis] 提示: Jank #{index + 1} jank_num={jank_num} > 20，"
            "逐帧分析仅采集关键线程的 Top-20 最长阻塞事件，数据已截断",
            file=sys.stderr,
        )

    for dim_id in dimensions:
        if dim_id == "summary":
            continue
        analyzer = _DIMENSION_ANALYZERS.get(dim_id)
        if analyzer is None:
            continue
        try:
            dim_result = analyzer(
                tp=tp,
                window_start_ns=window_start,
                window_end_ns=window_end,
                target_utids=target_utids,
                topology=topology,
                upid=upid,
                slow_binder_ms=slow_binder_ms,
                sched_latency_ms=sched_latency_ms,
            )
            jank_data[dim_id] = dim_result
        except Exception as e:
            print(
                f"[perfetto_analysis] 警告: 维度 {dim_id} 分析失败: {e}",
                file=sys.stderr,
            )

    return jank_data


def _run_summary_analysis(
    tp: Any,
    parse_result: dict[str, Any],
    upid: int | None,
    target_utids: list[int],
    topology: dict[str, Any],
) -> dict[str, Any]:
    """执行全 trace 整体分析。"""
    try:
        from . import summary_analysis
        return summary_analysis.analyze_summary(
            tp=tp,
            parse_result=parse_result,
            upid=upid,
            target_utids=target_utids,
            topology=topology,
        )
    except ImportError:
        return {}
    except Exception as e:
        print(
            f"[perfetto_analysis] 警告: 整体分析失败: {e}",
            file=sys.stderr,
        )
        return {}


def _get_target_utids(tp: Any, upid: int) -> list[int]:
    """获取目标进程的关键线程 utids。"""
    try:
        rows = list(tp.query(f"""
            SELECT utid, name FROM thread WHERE upid = {upid}
        """))
        utids = [int(row.utid) for row in rows]
        return utids
    except Exception:
        return []
