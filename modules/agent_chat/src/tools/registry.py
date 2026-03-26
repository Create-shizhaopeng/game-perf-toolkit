# -*- coding: utf-8 -*-
"""工具注册表 — 收集和管理 Agent 可用工具。"""
from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, get_type_hints

from ..models import ToolDefinition

logger = logging.getLogger(__name__)


class ToolRegistry:
    """收集各模块通过 pluggy hook 注册的工具。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """注册单个工具。"""
        if tool.name in self._tools:
            logger.warning("工具 '%s' 已存在，将被覆盖", tool.name)
        self._tools[tool.name] = tool
        logger.debug("已注册工具: %s", tool.name)

    def register_many(self, tools: list[ToolDefinition]) -> None:
        for tool in tools:
            self.register(tool)

    def collect_from_plugins(self, plugin_manager) -> None:
        """从 PluginManager 的 register_agent_tools hook 收集工具。"""
        results = plugin_manager.pm.hook.register_agent_tools()
        for tool_list in results:
            if not tool_list:
                continue
            for item in tool_list:
                if isinstance(item, ToolDefinition):
                    self._enhance_schema(item)
                    self.register(item)
                elif isinstance(item, dict):
                    td = ToolDefinition(
                        name=item.get("name", ""),
                        description=item.get("description", ""),
                        parameters=item.get("parameters", {}),
                        method=item.get("method"),
                    )
                    self._enhance_schema(td)
                    self.register(td)

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_definitions(self) -> list[ToolDefinition]:
        """返回所有工具定义列表。"""
        return list(self._tools.values())

    def get_tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def _enhance_schema(self, tool: ToolDefinition) -> None:
        """对缺少 parameters 的工具自动生成 JSON Schema。"""
        if tool.parameters or not tool.method:
            return

        try:
            sig = inspect.signature(tool.method)
            hints = get_type_hints(tool.method)
        except (ValueError, TypeError):
            return

        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            hint = hints.get(param_name)
            if _is_callable_type(hint):
                continue

            prop = _type_to_json_schema(hint)
            properties[param_name] = prop

            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        tool.parameters = {
            "type": "object",
            "properties": properties,
        }
        if required:
            tool.parameters["required"] = required


def _is_callable_type(hint: Any) -> bool:
    """判断类型是否为 Callable 类型（Agent 无法传递回调函数）。"""
    if hint is None:
        return False
    import collections.abc
    origin = getattr(hint, "__origin__", None)
    if origin is collections.abc.Callable:
        return True
    # Union 类型（如 Callable | None）
    import types
    if isinstance(hint, types.UnionType):
        for arg in hint.__args__:
            if _is_callable_type(arg):
                return True
    # typing.Optional[Callable]
    if origin is type(None):
        return False
    try:
        import typing
        if origin is typing.Union:
            for arg in hint.__args__:
                if _is_callable_type(arg):
                    return True
    except Exception:
        pass
    if isinstance(hint, type) and issubclass(hint, collections.abc.Callable):
        return True
    return False


def _type_to_json_schema(hint: Any) -> dict[str, Any]:
    """将 Python 类型提示转换为 JSON Schema 片段。"""
    if hint is None:
        return {"type": "string"}

    origin = getattr(hint, "__origin__", None)

    if hint is str:
        return {"type": "string"}
    elif hint is int:
        return {"type": "integer"}
    elif hint is float:
        return {"type": "number"}
    elif hint is bool:
        return {"type": "boolean"}
    elif origin is list:
        args = getattr(hint, "__args__", ())
        if args:
            return {"type": "array", "items": _type_to_json_schema(args[0])}
        return {"type": "array"}
    elif origin is dict:
        return {"type": "object"}

    try:
        from pydantic import BaseModel
        if isinstance(hint, type) and issubclass(hint, BaseModel):
            return hint.model_json_schema()
    except ImportError:
        pass

    return {"type": "string"}
