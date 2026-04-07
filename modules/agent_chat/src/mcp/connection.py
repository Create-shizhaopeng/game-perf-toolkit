# -*- coding: utf-8 -*-
"""MCP 连接管理 — stdio/SSE 传输层封装。"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ..models import MCPConnection, MCPConnectionStatus, MCPServerConfig

logger = logging.getLogger(__name__)


class ConnectionPool:
    """管理活跃的 MCP 连接。"""

    def __init__(self) -> None:
        self._connections: dict[str, MCPConnection] = {}
        self._sessions: dict[str, Any] = {}
        self._exit_stacks: dict[str, Any] = {}

    async def connect(self, config: MCPServerConfig) -> MCPConnection:
        """连接到 MCP 服务器。"""
        conn = MCPConnection(
            server_name=config.name,
            status=MCPConnectionStatus.CONNECTING,
        )
        self._connections[config.name] = conn

        try:
            session, tools = await self._create_session(config)
            self._sessions[config.name] = session
            conn.status = MCPConnectionStatus.CONNECTED
            conn.available_tools = [t.name for t in tools]
            conn.connected_at = datetime.now()
            logger.info(
                "MCP '%s' 已连接，发现 %d 个工具", config.name, len(tools)
            )
            return conn

        except Exception as exc:
            conn.status = MCPConnectionStatus.ERROR
            conn.last_error = str(exc)
            logger.error("MCP '%s' 连接失败: %s", config.name, exc)
            return conn

    async def _create_session(self, config: MCPServerConfig) -> tuple[Any, list]:
        """通过 MCP SDK 创建会话，返回 (session, tools)。"""
        from contextlib import AsyncExitStack

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        if config.transport == "stdio":
            server_params = StdioServerParameters(
                command=config.command,
                args=config.args,
                env=config.env or None,
            )

            exit_stack = AsyncExitStack()
            self._exit_stacks[config.name] = exit_stack

            read_stream, write_stream = await exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()

            tools_resp = await session.list_tools()
            return session, tools_resp.tools

        else:
            raise ValueError(f"不支持的传输类型: {config.transport}")

    async def disconnect(self, server_name: str) -> None:
        """断开指定服务器连接。"""
        exit_stack = self._exit_stacks.pop(server_name, None)
        if exit_stack:
            try:
                await exit_stack.aclose()
            except Exception as exc:
                logger.warning("MCP '%s' 断开连接时异常: %s", server_name, exc)

        self._sessions.pop(server_name, None)
        conn = self._connections.get(server_name)
        if conn:
            conn.status = MCPConnectionStatus.DISCONNECTED
        logger.info("MCP '%s' 已断开", server_name)

    async def disconnect_all(self) -> None:
        """断开所有连接。"""
        names = list(self._sessions.keys())
        for name in names:
            await self.disconnect(name)

    def get_session(self, server_name: str) -> Any | None:
        """获取指定服务器的活跃 session。"""
        return self._sessions.get(server_name)

    def get_connection(self, server_name: str) -> MCPConnection | None:
        return self._connections.get(server_name)

    def get_all_connections(self) -> list[MCPConnection]:
        return list(self._connections.values())

    def is_connected(self, server_name: str) -> bool:
        conn = self._connections.get(server_name)
        return conn is not None and conn.status == MCPConnectionStatus.CONNECTED
