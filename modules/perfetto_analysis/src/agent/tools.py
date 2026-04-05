"""将 PerfettoAnalysisService 的 pa_* 方法封装为 Pydantic AI 工具函数。

所有工具返回 ToolReturn: return_value 为压缩摘要给 LLM，metadata 保留原始数据。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from pydantic_ai.tools import ToolReturn

logger = logging.getLogger(__name__)


_stream_callback: Callable | None = None


def set_tool_stream_callback(callback: Callable | None) -> None:
    """设置工具调用流式输出回调。"""
    global _stream_callback
    _stream_callback = callback


def _notify_tool_call(tool_name: str, args: dict) -> None:
    if _stream_callback:
        args_brief = ", ".join(f"{k}={v!r}" for k, v in args.items() if v)
        _stream_callback("tool", f"🔧 调用 {tool_name}({args_brief})")


def _notify_tool_result(tool_name: str, result: Any) -> None:
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


def _make_tool_return(
    tool_name: str, raw: Any, compressor: Any
) -> ToolReturn:
    """统一构建 ToolReturn: 压缩 return_value，保留 raw 到 metadata。"""
    if raw is None or (isinstance(raw, dict) and not raw):
        return ToolReturn(
            return_value="工具未返回数据",
            metadata={"raw": raw, "tool_name": tool_name},
        )
    compressed = compressor.compress_tool_output(tool_name, raw, 300)
    return ToolReturn(
        return_value=compressed,
        metadata={"raw": raw, "tool_name": tool_name},
    )


def _make_error_return(tool_name: str, error: str) -> ToolReturn:
    return ToolReturn(
        return_value=f"错误: {error}",
        metadata={"error": error, "tool_name": tool_name},
    )


def build_analysis_tools(pa_service: Any, compressor: Any = None) -> list[Callable]:
    """构建 Pydantic AI 工具列表。

    Args:
        pa_service: PerfettoAnalysisService 实例
        compressor: ResultCompressor 实例（用于工具返回值压缩）
    """
    if compressor is None:
        from ..result_compressor import ResultCompressor
        compressor = ResultCompressor()

    def pa_trace_overview(trace_path: str, process_name: str = "") -> ToolReturn:
        """获取trace元数据概览"""
        _notify_tool_call("pa_trace_overview", {"trace_path": trace_path, "process_name": process_name})
        try:
            result = pa_service.get_trace_overview(trace_path, process_name)
            _notify_tool_result("pa_trace_overview", result)
            return _make_tool_return("pa_trace_overview", result, compressor)
        except Exception as e:
            _notify_tool_result("pa_trace_overview", {"error": str(e)})
            return _make_error_return("pa_trace_overview", str(e))

    def pa_detect_jank(trace_path: str, process_name: str = "") -> ToolReturn:
        """检测卡顿帧,返回丢帧统计和Top-5"""
        _notify_tool_call("pa_detect_jank", {"trace_path": trace_path, "process_name": process_name})
        try:
            result = pa_service.parse_only(trace_path, process_name)
            result = result if isinstance(result, dict) else {"data": str(result)}
            _notify_tool_result("pa_detect_jank", result)
            return _make_tool_return("pa_detect_jank", result, compressor)
        except Exception as e:
            _notify_tool_result("pa_detect_jank", {"error": str(e)})
            return _make_error_return("pa_detect_jank", str(e))

    def pa_analyze_dimension(
        trace_path: str,
        dimension: str,
        process_name: str = "",
        compact: bool = True,
    ) -> ToolReturn:
        """按维度(cpu/thread/binder/io/gc/gpu/sf/input/lock/summary)分析trace"""
        _notify_tool_call("pa_analyze_dimension", {"dimension": dimension, "process_name": process_name})
        try:
            result = pa_service.analyze_dimensions(
                trace_path, process_name, [dimension], compact
            )
            _notify_tool_result("pa_analyze_dimension", result)
            return _make_tool_return("pa_analyze_dimension", result, compressor)
        except Exception as e:
            _notify_tool_result("pa_analyze_dimension", {"error": str(e)})
            return _make_error_return("pa_analyze_dimension", str(e))

    def pa_list_dimensions() -> ToolReturn:
        """列出所有可用分析维度"""
        dims = [
            "cpu", "thread", "binder", "io", "gc",
            "gpu", "sf", "input", "lock", "summary",
        ]
        return ToolReturn(
            return_value=", ".join(dims),
            metadata={"raw": dims, "tool_name": "pa_list_dimensions"},
        )

    def pa_get_history(limit: int = 20) -> ToolReturn:
        """查询分析历史记录"""
        _notify_tool_call("pa_get_history", {"limit": limit})
        try:
            result = pa_service.get_analysis_history()
            if isinstance(result, list) and limit:
                result = result[:limit]
            _notify_tool_result("pa_get_history", result)
            return _make_tool_return("pa_get_history", result, compressor)
        except Exception as e:
            _notify_tool_result("pa_get_history", {"error": str(e)})
            return _make_error_return("pa_get_history", str(e))

    def pa_find_slices(trace_path: str, slice_name: str, process_name: str = "") -> ToolReturn:
        """按名称搜索trace中的slice"""
        _notify_tool_call("pa_find_slices", {"slice_name": slice_name, "process_name": process_name})
        try:
            if hasattr(pa_service, "find_slices_tool"):
                result = pa_service.find_slices_tool(trace_path, slice_name, process_name)
            elif hasattr(pa_service, "find_slices"):
                result = pa_service.find_slices(trace_path, slice_name, process_name)
            else:
                result = {"error": "find_slices 方法不可用"}
            _notify_tool_result("pa_find_slices", result)
            return _make_tool_return("pa_find_slices", result, compressor)
        except Exception as e:
            _notify_tool_result("pa_find_slices", {"error": str(e)})
            return _make_error_return("pa_find_slices", str(e))

    def pa_execute_sql(trace_path: str, sql: str) -> ToolReturn:
        """在trace上执行Perfetto SQL查询"""
        _notify_tool_call("pa_execute_sql", {"sql": sql[:80]})
        try:
            if hasattr(pa_service, "execute_sql_tool"):
                result = pa_service.execute_sql_tool(trace_path, sql)
            elif hasattr(pa_service, "execute_sql"):
                result = pa_service.execute_sql(trace_path, sql)
            else:
                result = {"error": "execute_sql 方法不可用"}
            _notify_tool_result("pa_execute_sql", result)
            return _make_tool_return("pa_execute_sql", result, compressor)
        except Exception as e:
            _notify_tool_result("pa_execute_sql", {"error": str(e)})
            return _make_error_return("pa_execute_sql", str(e))

    def pa_analyze_anr(trace_path: str, process_name: str = "") -> ToolReturn:
        """检测ANR并分析根因"""
        _notify_tool_call("pa_analyze_anr", {"trace_path": trace_path, "process_name": process_name})
        try:
            if hasattr(pa_service, "analyze_anr"):
                result = pa_service.analyze_anr(trace_path, process_name)
            else:
                result = pa_service.analyze_dimensions(
                    trace_path, process_name, ["thread", "binder", "lock"], True
                )
            _notify_tool_result("pa_analyze_anr", result)
            return _make_tool_return("pa_analyze_anr", result, compressor)
        except Exception as e:
            _notify_tool_result("pa_analyze_anr", {"error": str(e)})
            return _make_error_return("pa_analyze_anr", str(e))

    def pa_analyze_memory(trace_path: str, process_name: str = "") -> ToolReturn:
        """分析内存使用和泄漏"""
        _notify_tool_call("pa_analyze_memory", {"trace_path": trace_path, "process_name": process_name})
        try:
            if hasattr(pa_service, "analyze_memory"):
                result = pa_service.analyze_memory(trace_path, process_name)
            else:
                result = pa_service.analyze_dimensions(
                    trace_path, process_name, ["gc"], True
                )
            _notify_tool_result("pa_analyze_memory", result)
            return _make_tool_return("pa_analyze_memory", result, compressor)
        except Exception as e:
            _notify_tool_result("pa_analyze_memory", {"error": str(e)})
            return _make_error_return("pa_analyze_memory", str(e))

    return [
        pa_trace_overview,
        pa_detect_jank,
        pa_analyze_dimension,
        pa_list_dimensions,
        pa_get_history,
        pa_find_slices,
        pa_execute_sql,
        pa_analyze_anr,
        pa_analyze_memory,
    ]
