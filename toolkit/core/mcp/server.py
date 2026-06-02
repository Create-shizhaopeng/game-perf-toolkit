# -*- coding: utf-8 -*-
"""MCP Server — 将 ToolRegistry 中的工具通过标准 MCP 协议暴露。

使用 mcp.server.fastmcp.FastMCP，支持 stdio/sse/streamable-http 传输模式。
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def create_mcp_server(tool_registry, tool_executor) -> Any:
    """创建并配置 MCP server 实例。

    Args:
        tool_registry: ToolRegistry 实例，提供已注册的工具定义
        tool_executor: ToolExecutor 实例，负责执行工具调用

    Returns:
        FastMCP 实例
    """
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("lv-game-toolkit")

    for td in tool_registry.get_definitions():
        if not td.method:
            logger.warning("工具 '%s' 无可调用方法，跳过 MCP 注册", td.name)
            continue

        handler = _build_tool_handler(
            executor=tool_executor,
            tool_name=td.name,
            parameters=td.parameters,
        )

        mcp.add_tool(
            fn=handler,
            name=td.name,
            description=td.description,
        )
        logger.debug("MCP 工具已注册: %s", td.name)

    return mcp


def _build_tool_handler(
    executor, tool_name: str, parameters: dict[str, Any]
) -> Callable:
    """动态创建一个异步函数，作为 MCP tool 注册。

    该函数有正确的参数签名（从 JSON Schema 推导），执行时委托给 ToolExecutor。
    """
    props = parameters.get("properties", {})
    required = set(parameters.get("required", []))

    # 构建签名参数
    sig_params: list[inspect.Parameter] = []
    for pname, pschema in props.items():
        ptype = _json_type_to_python(pschema.get("type", "string"))
        default = inspect.Parameter.empty if pname in required else ""
        sig_params.append(
            inspect.Parameter(
                name=pname,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=ptype,
            )
        )

    sig = inspect.Signature(parameters=sig_params, return_annotation=str)

    async def handler(**kwargs: Any) -> str:
        from toolkit.core.models import ToolCall

        # 只传递 schema 中定义的参数
        call_args = {k: v for k, v in kwargs.items() if k in props}
        # 处理空字符串默认值（可选参数的默认值 "" 可能被传进来）
        call_args = {
            k: v for k, v in call_args.items() if v != "" or k in required
        }

        call = ToolCall(id="", name=tool_name)
        call.arguments = call_args
        result = await executor.execute(call)

        if result.is_error:
            raise RuntimeError(result.content)

        return result.content

    handler.__name__ = tool_name
    handler.__qualname__ = tool_name
    handler.__doc__ = f"MCP tool: {tool_name}"
    handler.__signature__ = sig  # type: ignore

    return handler


def _json_type_to_python(json_type: str) -> type:
    """将 JSON Schema 类型映射为 Python 类型。"""
    return _JSON_TYPE_MAP.get(json_type, str)


def run_stdio(tool_registry, tool_executor) -> None:
    """以 stdio 模式启动 MCP server。"""
    mcp = create_mcp_server(tool_registry, tool_executor)
    mcp.run(transport="stdio")


def run_sse(tool_registry, tool_executor, port: int = 8765) -> None:
    """以 SSE 模式启动 MCP server。"""
    mcp = create_mcp_server(tool_registry, tool_executor)
    mcp.run(transport="sse")
