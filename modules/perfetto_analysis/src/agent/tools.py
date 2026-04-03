"""将 PerfettoAnalysisService 的 pa_* 方法封装为 Pydantic AI 工具函数。"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


_stream_callback: Callable | None = None


def set_tool_stream_callback(callback: Callable | None) -> None:
    """设置工具调用流式输出回调。"""
    global _stream_callback
    _stream_callback = callback


def _notify_tool_call(tool_name: str, args: dict) -> None:
    """通知工具被调用。"""
    if _stream_callback:
        args_brief = ", ".join(f"{k}={v!r}" for k, v in args.items() if v)
        _stream_callback("tool", f"🔧 调用 {tool_name}({args_brief})")


def _notify_tool_result(tool_name: str, result: Any) -> None:
    """通知工具返回结果。"""
    if _stream_callback:
        if isinstance(result, dict):
            if "error" in result:
                _stream_callback("tool", f"❌ {tool_name} 返回错误: {result['error']}")
            else:
                keys = list(result.keys())[:5]
                _stream_callback("tool", f"✅ {tool_name} 返回: {keys}")
        elif isinstance(result, list):
            _stream_callback("tool", f"✅ {tool_name} 返回 {len(result)} 项")
        else:
            _stream_callback("tool", f"✅ {tool_name} 完成")


def build_analysis_tools(pa_service: Any) -> list[Callable]:
    """构建 Pydantic AI 工具列表，封装 pa_service 的分析方法。"""

    def pa_trace_overview(trace_path: str, process_name: str = "") -> dict:
        """获取trace元数据概览(时长/帧数/进程/刷新率)"""
        _notify_tool_call("pa_trace_overview", {"trace_path": trace_path, "process_name": process_name})
        try:
            result = pa_service.get_trace_overview(trace_path, process_name)
            _notify_tool_result("pa_trace_overview", result)
            return result
        except Exception as e:
            _notify_tool_result("pa_trace_overview", {"error": str(e)})
            return {"error": str(e)}

    def pa_detect_jank(trace_path: str, process_name: str = "") -> dict:
        """检测卡顿帧(Jank/BigJank),返回丢帧列表和统计"""
        _notify_tool_call("pa_detect_jank", {"trace_path": trace_path, "process_name": process_name})
        try:
            result = pa_service.parse_only(trace_path, process_name)
            result = result if isinstance(result, dict) else {"data": str(result)}
            _notify_tool_result("pa_detect_jank", result)
            return result
        except Exception as e:
            _notify_tool_result("pa_detect_jank", {"error": str(e)})
            return {"error": str(e)}

    def pa_analyze_dimension(
        trace_path: str,
        dimension: str,
        process_name: str = "",
        compact: bool = True,
    ) -> dict:
        """按维度(cpu/thread/binder/io/gc/gpu/sf/input/lock/summary)分析trace"""
        _notify_tool_call("pa_analyze_dimension", {"dimension": dimension, "process_name": process_name})
        try:
            result = pa_service.analyze_dimensions(
                trace_path, process_name, [dimension], compact
            )
            _notify_tool_result("pa_analyze_dimension", result)
            return result
        except Exception as e:
            _notify_tool_result("pa_analyze_dimension", {"error": str(e)})
            return {"error": str(e)}

    def pa_analyze_full(trace_path: str, process_name: str = "") -> dict:
        """执行完整 Phase 1 + Phase 2 分析并生成报告。

        Args:
            trace_path: Perfetto trace 文件路径
            process_name: 目标进程名

        Returns:
            完整分析结果
        """
        try:
            return pa_service.analyze(trace_path, process_name)
        except Exception as e:
            return {"error": str(e)}

    def pa_list_dimensions() -> list[str]:
        """列出所有可用的分析维度。

        Returns:
            维度名称列表
        """
        return [
            "cpu", "thread", "binder", "io", "gc",
            "gpu", "sf", "input", "lock", "summary",
        ]

    def pa_get_history(limit: int = 20) -> list[dict]:
        """查询分析历史记录。

        Args:
            limit: 返回记录数上限

        Returns:
            分析历史记录列表
        """
        try:
            return pa_service.get_analysis_history(limit)
        except Exception as e:
            return [{"error": str(e)}]

    def pa_cpu_overview(trace_path: str) -> dict:
        """获取全 trace CPU 概览（线程分布、频率统计）。

        Args:
            trace_path: Perfetto trace 文件路径

        Returns:
            CPU 概览数据
        """
        try:
            return pa_service.analyze_dimensions(
                trace_path, "", ["cpu"], compact=True
            )
        except Exception as e:
            return {"error": str(e)}

    def pa_find_slices(trace_path: str, slice_name: str, process_name: str = "") -> dict:
        """按名称搜索 trace 中的 slice。

        Args:
            trace_path: Perfetto trace 文件路径
            slice_name: 要搜索的 slice 名称
            process_name: 目标进程名

        Returns:
            匹配的 slice 列表
        """
        try:
            if hasattr(pa_service, "find_slices"):
                return pa_service.find_slices(trace_path, slice_name, process_name)
            return {"error": "find_slices 方法不可用"}
        except Exception as e:
            return {"error": str(e)}

    def pa_execute_sql(trace_path: str, sql: str) -> dict:
        """在 trace 上执行任意 Perfetto SQL 查询。

        Args:
            trace_path: Perfetto trace 文件路径
            sql: SQL 查询语句

        Returns:
            查询结果
        """
        try:
            if hasattr(pa_service, "execute_sql"):
                return pa_service.execute_sql(trace_path, sql)
            return {"error": "execute_sql 方法不可用"}
        except Exception as e:
            return {"error": str(e)}

    def pa_analyze_anr(trace_path: str, process_name: str = "") -> dict:
        """检测 ANR 并分析根因。

        Args:
            trace_path: Perfetto trace 文件路径
            process_name: 目标进程名

        Returns:
            ANR 分析结果
        """
        try:
            if hasattr(pa_service, "analyze_anr"):
                return pa_service.analyze_anr(trace_path, process_name)
            return pa_service.analyze_dimensions(
                trace_path, process_name, ["thread", "binder", "lock"], True
            )
        except Exception as e:
            return {"error": str(e)}

    def pa_analyze_memory(trace_path: str, process_name: str = "") -> dict:
        """分析内存使用和泄漏情况。

        Args:
            trace_path: Perfetto trace 文件路径
            process_name: 目标进程名

        Returns:
            内存分析结果
        """
        try:
            if hasattr(pa_service, "analyze_memory"):
                return pa_service.analyze_memory(trace_path, process_name)
            return pa_service.analyze_dimensions(
                trace_path, process_name, ["gc"], True
            )
        except Exception as e:
            return {"error": str(e)}

    return [
        pa_trace_overview,
        pa_detect_jank,
        pa_analyze_dimension,
        pa_analyze_full,
        pa_list_dimensions,
        pa_get_history,
        pa_cpu_overview,
        pa_find_slices,
        pa_execute_sql,
        pa_analyze_anr,
        pa_analyze_memory,
    ]
