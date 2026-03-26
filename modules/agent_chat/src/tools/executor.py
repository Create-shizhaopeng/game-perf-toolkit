# -*- coding: utf-8 -*-
"""工具执行器 — 安全调用工具并序列化结果。"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, is_dataclass
from typing import Any

from ..models import ToolCall, ToolCallStatus, ToolResult
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """安全执行工具调用，处理序列化和截断。"""

    def __init__(
        self,
        registry: ToolRegistry,
        max_result_length: int = 2000,
    ) -> None:
        self._registry = registry
        self._max_length = max_result_length

    def execute(self, tool_call: ToolCall) -> ToolResult:
        """执行单个工具调用。

        - 按 name 查找工具方法
        - try/except 全捕获
        - 结果序列化 + 截断
        - 提取 report_paths
        """
        tool_def = self._registry.get_tool(tool_call.name)
        if not tool_def:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"未知工具: {tool_call.name}",
                is_error=True,
            )

        if not tool_def.method:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"工具 '{tool_call.name}' 无可调用方法",
                is_error=True,
            )

        tool_call.status = ToolCallStatus.RUNNING
        start = time.time()

        try:
            raw_result = tool_def.method(**tool_call.arguments)
        except Exception as exc:
            logger.error(
                "工具 '%s' 执行异常: %s", tool_call.name, exc, exc_info=True
            )
            elapsed = (time.time() - start) * 1000
            tool_call.elapsed_ms = elapsed
            tool_call.status = ToolCallStatus.FAILED
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"工具执行异常: {type(exc).__name__}: {exc}",
                is_error=True,
            )

        elapsed = (time.time() - start) * 1000
        tool_call.elapsed_ms = elapsed
        tool_call.status = ToolCallStatus.COMPLETE

        content = _serialize_result(raw_result)
        report_paths = _extract_report_paths(raw_result)

        if len(content) > self._max_length:
            truncated = content[: self._max_length]
            if report_paths:
                truncated += f"\n... [结果已截断，完整内容见: {report_paths[0]}]"
            else:
                truncated += "\n... [结果已截断]"
            content = truncated

        return ToolResult(
            tool_call_id=tool_call.id,
            content=content,
            report_paths=report_paths,
        )


def _serialize_result(result: Any) -> str:
    """将工具返回值序列化为字符串。"""
    if result is None:
        return "执行完成（无返回值）"

    if isinstance(result, str):
        return result

    try:
        from pydantic import BaseModel
        if isinstance(result, BaseModel):
            return result.model_dump_json(indent=2)
    except ImportError:
        pass

    if is_dataclass(result) and not isinstance(result, type):
        try:
            return json.dumps(asdict(result), ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            pass

    if isinstance(result, (dict, list)):
        try:
            return json.dumps(result, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            pass

    return str(result)


def _extract_report_paths(result: Any) -> list[str]:
    """从工具结果中提取报告路径。"""
    paths: list[str] = []

    if isinstance(result, dict):
        for key in ("report_path", "report_paths", "output_path", "output_dir"):
            val = result.get(key)
            if val:
                if isinstance(val, list):
                    paths.extend(str(p) for p in val)
                else:
                    paths.append(str(val))

    try:
        from pydantic import BaseModel
        if isinstance(result, BaseModel):
            data = result.model_dump()
            for key in ("report_path", "report_paths", "output_path", "output_dir"):
                val = data.get(key)
                if val:
                    if isinstance(val, list):
                        paths.extend(str(p) for p in val)
                    else:
                        paths.append(str(val))
    except ImportError:
        pass

    return paths
