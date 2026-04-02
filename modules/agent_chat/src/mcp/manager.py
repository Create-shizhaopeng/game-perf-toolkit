# -*- coding: utf-8 -*-
"""MCPManager — MCP 服务器全生命周期管理。"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable

from ..models import MCPConnection, MCPConnectionStatus, MCPServerConfig
from . import load_mcp_config, save_mcp_config
from .connection import ConnectionPool
from .tool_bridge import MCPToolBridge

logger = logging.getLogger(__name__)

OnStatusChange = Callable[[str, MCPConnectionStatus], None]


class MCPManager:
    """管理所有 MCP 服务器的发现、连接和工具桥接。"""

    def __init__(
        self,
        config_path: Path | None = None,
        on_status_change: OnStatusChange | None = None,
    ) -> None:
        self._config_path = config_path or (
            Path(__file__).parent.parent.parent / "data" / "mcp_servers.json"
        )
        self._servers: dict[str, MCPServerConfig] = {}
        self._pool = ConnectionPool()
        self._bridge = MCPToolBridge(self._pool)
        self._on_status_change = on_status_change

    def load_config(self) -> dict[str, MCPServerConfig]:
        """加载 MCP 服务器配置。"""
        self._servers = load_mcp_config(self._config_path)
        return self._servers

    def save_config(self) -> None:
        """保存当前配置到文件。"""
        save_mcp_config(self._servers, self._config_path)

    def add_server(self, config: MCPServerConfig) -> None:
        """添加一个 MCP 服务器配置。"""
        self._servers[config.name] = config
        self.save_config()

    def remove_server(self, name: str) -> None:
        """移除一个 MCP 服务器配置。"""
        self._servers.pop(name, None)
        self.save_config()

    def update_server(self, name: str, **kwargs: Any) -> None:
        """更新指定服务器的配置字段。"""
        if name not in self._servers:
            raise KeyError(f"MCP 服务器 '{name}' 不存在")
        updated = self._servers[name].model_copy(update=kwargs)
        self._servers[name] = updated
        self.save_config()

    async def connect(self, name: str) -> MCPConnection:
        """连接到指定 MCP 服务器。"""
        if name not in self._servers:
            raise KeyError(f"MCP 服务器 '{name}' 未配置")

        self._notify(name, MCPConnectionStatus.CONNECTING)
        conn = await self._pool.connect(self._servers[name])
        self._notify(name, conn.status)
        return conn

    async def connect_all(self) -> list[MCPConnection]:
        """并行连接所有已启用的服务器。"""
        if not self._servers:
            self.load_config()

        tasks = [self.connect(name) for name in self._servers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        connections: list[MCPConnection] = []
        for r in results:
            if isinstance(r, MCPConnection):
                connections.append(r)
            else:
                logger.error("MCP 连接异常: %s", r)
        return connections

    async def disconnect(self, name: str) -> None:
        """断开指定服务器。"""
        await self._pool.disconnect(name)
        self._notify(name, MCPConnectionStatus.DISCONNECTED)

    async def disconnect_all(self) -> None:
        """断开所有连接。"""
        await self._pool.disconnect_all()

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> Any:
        """调用指定 MCP 服务器上的工具。"""
        return await self._bridge.call_tool(server_name, tool_name, arguments)

    def get_tool_definitions(self) -> list:
        """获取所有已连接的 MCP 工具定义（可注入 ToolRegistry）。"""
        return self._bridge.get_tool_definitions()

    def get_connections(self) -> list[MCPConnection]:
        return self._pool.get_all_connections()

    def get_servers(self) -> dict[str, MCPServerConfig]:
        return dict(self._servers)

    def _notify(self, name: str, status: MCPConnectionStatus) -> None:
        if self._on_status_change:
            try:
                self._on_status_change(name, status)
            except Exception:
                logger.debug("状态回调异常", exc_info=True)
