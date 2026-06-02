# -*- coding: utf-8 -*-
"""工具注册表 — 收集和管理 Agent 可用工具。

Framework core — 线程安全单例，收集 pluggy hooks、Skill 工具、MCP 桥接工具。
"""
from __future__ import annotations

import inspect
import logging
import threading
import time
from typing import Any, Callable, get_type_hints

from toolkit.core.models import ToolDefinition

logger = logging.getLogger(__name__)

_CHECK_FN_TTL_SECONDS = 30.0
_check_fn_cache: dict[Callable, tuple[float, bool]] = {}
_check_fn_cache_lock = threading.Lock()


def _check_fn_cached(fn: Callable) -> bool:
    """Return bool(fn()), TTL-cached. Swallows exceptions as False."""
    now = time.monotonic()
    with _check_fn_cache_lock:
        cached = _check_fn_cache.get(fn)
        if cached is not None:
            ts, value = cached
            if now - ts < _CHECK_FN_TTL_SECONDS:
                return value
    try:
        value = bool(fn())
    except Exception:
        value = False
    with _check_fn_cache_lock:
        _check_fn_cache[fn] = (now, value)
    return value


def invalidate_check_fn_cache() -> None:
    with _check_fn_cache_lock:
        _check_fn_cache.clear()


class ToolEntry:
    """单个工具的元数据 + 处理器。"""

    __slots__ = (
        "name", "toolset", "schema", "handler",
        "check_fn", "is_async", "description",
        "max_result_size_chars", "dynamic_schema_overrides",
    )

    def __init__(self, name, toolset, schema, handler, check_fn=None,
                 is_async=False, description="", max_result_size_chars=None,
                 dynamic_schema_overrides=None):
        self.name = name
        self.toolset = toolset
        self.schema = schema
        self.handler = handler
        self.check_fn = check_fn
        self.is_async = is_async
        self.description = description or schema.get("description", "")
        self.max_result_size_chars = max_result_size_chars
        self.dynamic_schema_overrides = dynamic_schema_overrides


class ToolRegistry:
    """线程安全单例工具注册中心。

    收集三种来源的工具：
    1. 模块通过 register_agent_tools() hook 注册
    2. Skill 系统生成的 skill_* 工具
    3. MCP 框架桥接的外部工具
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}
        self._toolset_checks: dict[str, Callable] = {}
        self._lock = threading.RLock()
        self._generation: int = 0

    def register(self, name_or_tool=None, *, name=None, toolset="module",
                 schema=None, handler=None, check_fn=None, is_async=False,
                 description="", max_result_size_chars=None,
                 dynamic_schema_overrides=None, override=False) -> None:
        # Resolve: accept old-style register(tool) or new register(name="x", ...)
        if name is not None:
            pass  # keyword-argument path: name already set
        elif name_or_tool is None:
            raise TypeError("register() requires name= or a ToolDefinition/dict/str")
        elif isinstance(name_or_tool, ToolDefinition):
            tool = name_or_tool
            name, toolset, schema, handler = (
                tool.name, "module", tool.parameters, tool.method
            )
            description = tool.description
        elif isinstance(name_or_tool, dict):
            d = name_or_tool
            name, toolset, schema, handler = (
                d.get("name", ""), "module", d.get("parameters", {}), d.get("method")
            )
            description = d.get("description", "")
        elif isinstance(name_or_tool, str):
            name = name_or_tool
            schema = schema or {}
            handler = handler
        else:
            raise TypeError(f"register() expects ToolDefinition, dict, or str, got {type(name_or_tool)}")

        with self._lock:
            existing = self._tools.get(name)
            if existing and existing.toolset != toolset:
                both_mcp = (
                    existing.toolset.startswith("mcp")
                    and toolset.startswith("mcp")
                )
                if not both_mcp and not override:
                    logger.error(
                        "Tool registration REJECTED: '%s' (toolset '%s') would "
                        "shadow existing tool from toolset '%s'.",
                        name, toolset, existing.toolset,
                    )
                    return
            self._tools[name] = ToolEntry(
                name=name, toolset=toolset, schema=schema,
                handler=handler, check_fn=check_fn, is_async=is_async,
                description=description, max_result_size_chars=max_result_size_chars,
                dynamic_schema_overrides=dynamic_schema_overrides,
            )
            if check_fn and toolset not in self._toolset_checks:
                self._toolset_checks[toolset] = check_fn
            self._generation += 1
        logger.debug("已注册工具: %s (toolset=%s)", name, toolset)

    def deregister(self, name: str) -> None:
        with self._lock:
            entry = self._tools.pop(name, None)
            if entry is None:
                return
            still_exists = any(
                e.toolset == entry.toolset for e in self._tools.values()
            )
            if not still_exists:
                self._toolset_checks.pop(entry.toolset, None)
            self._generation += 1
        logger.debug("Deregistered tool: %s", name)

    def register_many(self, tools: list[ToolDefinition]) -> None:
        for tool in tools:
            self._enhance_schema(tool)
            self.register(
                name=tool.name, toolset="module",
                schema=tool.parameters, handler=tool.method,
                description=tool.description,
            )

    def collect_from_plugins(self, plugin_manager) -> int:
        count = 0
        results = plugin_manager.pm.hook.register_agent_tools()
        for tool_list in results:
            if not tool_list:
                continue
            for item in tool_list:
                if isinstance(item, ToolDefinition):
                    self._enhance_schema(item)
                    self.register(
                        name=item.name, toolset="module",
                        schema=item.parameters, handler=item.method,
                        description=item.description,
                    )
                    count += 1
                elif isinstance(item, dict):
                    td = ToolDefinition(
                        name=item.get("name", ""),
                        description=item.get("description", ""),
                        parameters=item.get("parameters", {}),
                        method=item.get("method"),
                    )
                    self._enhance_schema(td)
                    self.register(
                        name=td.name, toolset="module",
                        schema=td.parameters, handler=td.method,
                        description=td.description,
                    )
                    count += 1
        return count

    def get_entry(self, name: str) -> ToolEntry | None:
        with self._lock:
            return self._tools.get(name)

    def get_tool(self, name: str) -> ToolEntry | None:
        """Backward-compat alias for get_entry()."""
        return self.get_entry(name)

    def get_definitions(self) -> list[ToolDefinition]:
        result = []
        for entry in list(self._tools.values()):
            if entry.check_fn and not _check_fn_cached(entry.check_fn):
                continue
            result.append(ToolDefinition(
                name=entry.name,
                description=entry.description,
                parameters=entry.schema,
                method=entry.handler,
            ))
        return result

    def get_tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def register_mcp_tools(self, definitions: list[ToolDefinition]) -> int:
        count = 0
        for td in definitions:
            self.register(
                name=td.name, toolset="mcp-external",
                schema=td.parameters, handler=td.method,
                description=td.description,
            )
            count += 1
        return count

    def unregister_by_prefix(self, prefix: str) -> int:
        to_remove = [n for n in self._tools if n.startswith(prefix)]
        for n in to_remove:
            del self._tools[n]
        return len(to_remove)

    def dispatch(self, name: str, args: dict) -> str:
        """执行工具，返回 JSON string。async handler 自动桥接。"""
        import asyncio, json
        entry = self.get_entry(name)
        if not entry:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            if entry.is_async:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, entry.handler(args))
                        return str(future.result())
                return asyncio.run(entry.handler(args))
            return entry.handler(args)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def get_tool_names_for_toolset(self, toolset: str) -> list[str]:
        return sorted(
            e.name for e in self._tools.values() if e.toolset == toolset
        )

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
        tool.parameters = {"type": "object", "properties": properties}
        if required:
            tool.parameters["required"] = required


def _is_callable_type(hint: Any) -> bool:
    if hint is None:
        return False
    import collections.abc
    origin = getattr(hint, "__origin__", None)
    if origin is collections.abc.Callable:
        return True
    import types
    if isinstance(hint, types.UnionType):
        for arg in hint.__args__:
            if _is_callable_type(arg):
                return True
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


# Module-level singleton
tool_registry = ToolRegistry()
