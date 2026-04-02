# -*- coding: utf-8 -*-
"""MCPToolBridge — 将 MCP 工具转换为 ToolDefinition 注入 ToolRegistry。"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..models import ToolDefinition
from .connection import ConnectionPool

logger = logging.getLogger(__name__)

MCP_TOOL_PREFIX = "mcp__"


class MCPToolBridge:
    """将已连接的 MCP 工具映射为标准 ToolDefinition。"""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict
    ) -> Any:
        """通过 MCP session 调用远程工具。"""
        session = self._pool.get_session(server_name)
        if session is None:
            raise ConnectionError(f"MCP '{server_name}' 未连接")

        result = await session.call_tool(tool_name, arguments)

        if hasattr(result, "content") and result.content:
            texts = []
            for item in result.content:
                if hasattr(item, "text"):
                    texts.append(item.text)
            combined = "\n".join(texts)
            try:
                return json.loads(combined)
            except (json.JSONDecodeError, ValueError):
                return combined

        return str(result)

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """为所有已连接服务器的工具生成 ToolDefinition。"""
        definitions: list[ToolDefinition] = []

        for conn in self._pool.get_all_connections():
            if not self._pool.is_connected(conn.server_name):
                continue

            session = self._pool.get_session(conn.server_name)
            if session is None:
                continue

            for tool_name in conn.available_tools:
                full_name = f"{MCP_TOOL_PREFIX}{conn.server_name}__{tool_name}"

                server_name = conn.server_name
                bridge = self

                async def _invoke(
                    _sn: str = server_name,
                    _tn: str = tool_name,
                    _br: MCPToolBridge = bridge,
                    **kwargs: Any,
                ) -> Any:
                    return await _br.call_tool(_sn, _tn, kwargs)

                td = ToolDefinition(
                    name=full_name,
                    description=f"[MCP:{conn.server_name}] {tool_name}",
                    parameters=self._get_tool_schema(session, tool_name),
                    method=_invoke,
                )
                definitions.append(td)

        return definitions

    def _get_tool_schema(self, session: Any, tool_name: str) -> dict:
        """尝试从 session 缓存中获取工具 schema。"""
        try:
            cache = getattr(session, "_tools_cache", None)
            if cache:
                for t in cache:
                    if t.name == tool_name and hasattr(t, "inputSchema"):
                        return t.inputSchema
        except Exception:
            pass
        return {"type": "object", "properties": {}}
