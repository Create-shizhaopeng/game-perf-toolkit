"""将 PerfettoAnalysisService 的 pa_* 方法封装为 Pydantic AI 工具函数。

所有工具返回 ToolReturn: return_value 为压缩摘要给 LLM，metadata 保留原始数据。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable

from pydantic_ai.tools import ToolReturn

from . import CompressionProfile

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills" / "perfetto-analysis"

COMPRESSION_PROFILES: dict[str, CompressionProfile] = {
    "pa_trace_overview": CompressionProfile(strategy="keep_all"),
    "pa_detect_jank": CompressionProfile(strategy="jank_records"),
    "pa_analyze_dimension": CompressionProfile(strategy="degraded_aware"),
    "pa_list_dimensions": CompressionProfile(strategy="keep_all"),
    "pa_get_history": CompressionProfile(strategy="truncate", max_tokens=300),
    "pa_find_slices": CompressionProfile(strategy="truncate", max_tokens=400),
    "pa_execute_sql": CompressionProfile(strategy="truncate", max_tokens=500),
    "pa_analyze_anr": CompressionProfile(strategy="degraded_aware"),
    "pa_analyze_memory": CompressionProfile(strategy="degraded_aware"),
    "pa_read_knowledge": CompressionProfile(strategy="keep_all"),
}


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
    """统一构建 ToolReturn: 查找注册表压缩策略，保留 raw 到 metadata。"""
    if raw is None or (isinstance(raw, dict) and not raw):
        return ToolReturn(
            return_value="工具未返回数据",
            metadata={"raw": raw, "tool_name": tool_name},
        )
    profile = COMPRESSION_PROFILES.get(tool_name)
    if profile and profile.strategy == "keep_all":
        compressed = compressor.compress_tool_output(tool_name, raw, 2000)
    elif profile:
        compressed = compressor.compress_tool_output(
            tool_name, raw, profile.max_tokens, profile.strategy,
        )
    else:
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


# ---------------------------------------------------------------------------
# G5: Skill 知识层级 — 辅助函数
# ---------------------------------------------------------------------------


def _heading_to_anchor(heading: str) -> str:
    """Markdown 标题 → 锚点（小写、去中文标点、空格/破折号转连字符）。"""
    anchor = heading.lstrip("#").strip().lower()
    anchor = re.sub(r"[，。、；：！？（）【】]", "", anchor)
    anchor = anchor.replace("—", "-").replace("–", "-")
    anchor = re.sub(r"\s+", "-", anchor)
    return anchor


def _normalize_anchor(anchor: str) -> str:
    """规范化锚点：合并连续连字符、去首尾连字符，用于模糊匹配。"""
    return re.sub(r"-{2,}", "-", anchor).strip("-")


def _build_toc_summary(content: str) -> str:
    """从 Markdown 内容提取 H2/H3 目录 + 每章节首句摘要。"""
    lines = content.split("\n")
    toc_parts: list[str] = []
    current_heading: str | None = None
    first_line_after: str | None = None

    for line in lines:
        if line.startswith("## ") or line.startswith("### "):
            if current_heading and first_line_after:
                toc_parts.append(f"{current_heading} — {first_line_after}")
            elif current_heading:
                toc_parts.append(current_heading)
            current_heading = line.strip()
            first_line_after = None
        elif current_heading and not first_line_after and line.strip():
            first_line_after = line.strip()[:80]

    if current_heading:
        if first_line_after:
            toc_parts.append(f"{current_heading} — {first_line_after}")
        else:
            toc_parts.append(current_heading)

    return "\n".join(toc_parts)


def _extract_section_by_anchor(content: str, anchor: str) -> str:
    """根据锚点提取 Markdown 章节内容（含标题行，到下一同级/父级标题结束）。"""
    lines = content.split("\n")
    target = _normalize_anchor(anchor.lower().strip())
    start_idx: int | None = None
    start_level: int = 0

    for i, line in enumerate(lines):
        if line.startswith("#"):
            heading_anchor = _normalize_anchor(_heading_to_anchor(line))
            if heading_anchor == target:
                start_idx = i
                start_level = len(line) - len(line.lstrip("#"))
                continue
            if start_idx is not None:
                current_level = len(line) - len(line.lstrip("#"))
                if current_level <= start_level:
                    return "\n".join(lines[start_idx:i]).strip()

    if start_idx is not None:
        return "\n".join(lines[start_idx:]).strip()
    return ""


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
            cache_key = pa_service.cache_key(trace_path, "trace_overview", process_name=process_name)
            cached = pa_service.get_cached(cache_key)
            if cached is not None:
                logger.debug("pa_trace_overview 命中缓存")
                return _make_tool_return("pa_trace_overview", cached, compressor)
            result = pa_service.get_trace_overview(trace_path, process_name)
            pa_service.set_cached(cache_key, result)
            _notify_tool_result("pa_trace_overview", result)
            return _make_tool_return("pa_trace_overview", result, compressor)
        except Exception as e:
            _notify_tool_result("pa_trace_overview", {"error": str(e)})
            return _make_error_return("pa_trace_overview", str(e))

    def pa_detect_jank(trace_path: str, process_name: str = "") -> ToolReturn:
        """检测卡顿帧,返回丢帧统计和Top-5"""
        _notify_tool_call("pa_detect_jank", {"trace_path": trace_path, "process_name": process_name})
        try:
            cache_key = pa_service.cache_key(trace_path, "detect_jank", process_name=process_name)
            cached = pa_service.get_cached(cache_key)
            if cached is not None:
                logger.debug("pa_detect_jank 命中缓存")
                return _make_tool_return("pa_detect_jank", cached, compressor)
            raw_result = pa_service.parse_only(trace_path, process_name)
            if isinstance(raw_result, dict):
                result = raw_result
            elif hasattr(raw_result, "parse_result"):
                result = {
                    "jank_times": getattr(raw_result, "jank_times", 0),
                    "frame_count": getattr(raw_result, "frame_count", 0),
                    "detected_process": getattr(raw_result, "detected_process", ""),
                    "parse_result": raw_result.parse_result,
                }
            else:
                result = {"data": str(raw_result)}
            pa_service.set_cached(cache_key, result)
            _notify_tool_result("pa_detect_jank", result)
            return _make_tool_return("pa_detect_jank", result, compressor)
        except Exception as e:
            _notify_tool_result("pa_detect_jank", {"error": str(e)})
            return _make_error_return("pa_detect_jank", str(e))

    def pa_analyze_dimension(
        trace_path: str,
        dimension: str,
        process_name: str = "",
    ) -> ToolReturn:
        """按维度(cpu/thread/binder/io/gc/gpu/sf/input/lock/summary)分析trace"""
        _notify_tool_call("pa_analyze_dimension", {"dimension": dimension, "process_name": process_name})
        try:
            cache_key = pa_service.cache_key(trace_path, "analyze_dimension", dimension=dimension, process_name=process_name)
            cached = pa_service.get_cached(cache_key)
            if cached is not None:
                logger.debug("pa_analyze_dimension(%s) 命中缓存", dimension)
                return _make_tool_return("pa_analyze_dimension", cached, compressor)
            result = pa_service.analyze_dimensions(
                trace_path, process_name, [dimension]
            )
            pa_service.set_cached(cache_key, result)
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
            result = pa_service.get_analysis_history(limit=limit)
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
                    trace_path, process_name, ["thread", "binder", "lock"]
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
                    trace_path, process_name, ["gc"]
                )
            _notify_tool_result("pa_analyze_memory", result)
            return _make_tool_return("pa_analyze_memory", result, compressor)
        except Exception as e:
            _notify_tool_result("pa_analyze_memory", {"error": str(e)})
            return _make_error_return("pa_analyze_memory", str(e))

    def pa_read_knowledge(resource_path: str) -> ToolReturn:
        """两级加载Perfetto分析知识库资源。

        Level 1（无锚点）: 返回文件章节目录+摘要，用于浏览可用知识
        Level 2（带#锚点）: 返回指定章节完整内容

        Args:
            resource_path: 相对于skills/perfetto-analysis/的路径
                Level 1: "patterns/root-cause-patterns.md"
                Level 2: "patterns/root-cause-patterns.md#cpu-调度抢占"
        """
        _notify_tool_call("pa_read_knowledge", {"resource_path": resource_path})

        path_part, _, anchor = resource_path.partition("#")
        full_path = (_SKILLS_DIR / path_part).resolve()

        if not full_path.exists():
            _notify_tool_result("pa_read_knowledge", {"error": f"资源不存在: {path_part}"})
            return _make_error_return("pa_read_knowledge", f"资源不存在: {path_part}")

        try:
            if not full_path.is_relative_to(_SKILLS_DIR.resolve()):
                return _make_error_return("pa_read_knowledge", "路径越界")
        except (ValueError, TypeError):
            return _make_error_return("pa_read_knowledge", "路径越界")

        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception as e:
            return _make_error_return("pa_read_knowledge", f"读取失败: {e}")

        if anchor:
            section = _extract_section_by_anchor(content, anchor)
            if not section:
                _notify_tool_result("pa_read_knowledge", {"error": f"锚点不存在: #{anchor}"})
                return _make_error_return("pa_read_knowledge", f"锚点不存在: #{anchor}")
            _notify_tool_result("pa_read_knowledge", f"Level 2: {len(section)} chars")
            return ToolReturn(
                return_value=section[:2000],
                metadata={
                    "resource_path": resource_path, "level": 2,
                    "tool_name": "pa_read_knowledge",
                },
            )
        else:
            toc = _build_toc_summary(content)
            _notify_tool_result("pa_read_knowledge", f"Level 1: {len(toc)} chars")
            return ToolReturn(
                return_value=toc if toc else content[:500],
                metadata={
                    "resource_path": resource_path, "level": 1,
                    "tool_name": "pa_read_knowledge",
                    "hint": "使用 #锚点 获取具体章节详情",
                },
            )

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
        pa_read_knowledge,
    ]
