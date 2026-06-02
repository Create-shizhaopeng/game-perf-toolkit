# -*- coding: utf-8 -*-
"""MCPRegistry — MCP 服务器全生命周期管理 (local/external/remote)。"""
from __future__ import annotations

import asyncio
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from toolkit.core.app_paths import get_config_path

logger = logging.getLogger(__name__)

OnStatusChange = Callable[[str, str], None]


class MCPSource(str, Enum):
    LOCAL = "local"
    EXTERNAL = "external"
    REMOTE = "remote"


def load_mcp_config(config_path: Path) -> dict:
    """加载 MCP 服务器配置 JSON。"""
    import json
    from pydantic import BaseModel

    if not config_path.exists():
        return {}
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    return raw


def save_mcp_config(servers: dict, config_path: Path) -> None:
    """保存 MCP 服务器配置到 JSON。"""
    import json
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    for name, cfg in servers.items():
        if hasattr(cfg, "model_dump"):
            data[name] = cfg.model_dump()
        else:
            data[name] = cfg
    config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class MCPRegistry:
    """MCP 统一注册中心。

    管理 local/external/remote 三种 MCP 服务来源。
    """

    def __init__(
        self,
        tool_registry=None,
        config_path: Path | None = None,
        on_status_change: OnStatusChange | None = None,
    ) -> None:
        from toolkit.core.mcp.client import ConnectionPool
        from toolkit.core.mcp.tool_bridge import MCPToolBridge

        self._tool_registry = tool_registry
        self._config_path = config_path or get_config_path("agent_chat", "mcp_servers.json")
        self._servers: dict[str, Any] = {}
        self._pool = ConnectionPool()
        self._bridge = MCPToolBridge(self._pool)
        self._on_status_change = on_status_change

    def register_local(self, module: str, handler_class) -> None:
        """注册子模块实现的 MCP 能力（进程内调用），内省 handler 公开方法。"""
        import inspect
        from toolkit.core.models import ToolDefinition

        handler = handler_class()
        count = 0
        for name in dir(handler):
            if name.startswith("_"):
                continue
            method = getattr(handler, name)
            if not callable(method) or not method.__doc__:
                continue
            sig = inspect.signature(method)
            properties = {}
            required = []
            for pname, param in sig.parameters.items():
                if pname == "self":
                    continue
                properties[pname] = {"type": "string"}
                if param.default is inspect.Parameter.empty:
                    required.append(pname)
            full_name = f"mcp__{module}__{name}"
            td = ToolDefinition(
                name=full_name,
                description=f"[MCP:{module}] {method.__doc__[:100]}",
                parameters={"type": "object", "properties": properties,
                            "required": required} if properties else {"type": "object", "properties": {}},
                method=method,
            )
            if self._tool_registry:
                self._tool_registry.register(
                    name=td.name, toolset="mcp-local",
                    schema=td.parameters, handler=td.method,
                    description=td.description,
                )
            count += 1
        logger.info("MCP Local 注册: %s → %d tools", module, count)

    def register_external(self, config) -> None:
        """注册外部 MCP Server 配置（不自动持久化）。"""
        self._servers[config.name] = config

    def register_remote(self, url: str, auth: dict | None = None) -> None:
        """注册远程 HTTP MCP 服务配置。"""
        import uuid
        from toolkit.agent.models import MCPServerConfig

        name = f"remote_{uuid.uuid4().hex[:8]}"
        config = MCPServerConfig(name=name, command=url, transport="sse",
                                 timeout=30, enabled=True)
        self._servers[name] = config
        logger.info("MCP Remote 注册: %s (%s)", name, url)

    def load_config(self) -> dict:
        self._servers = load_mcp_config(self._config_path)
        return self._servers

    def save_config(self) -> None:
        save_mcp_config(self._servers, self._config_path)

    def add_server(self, config) -> None:
        self._servers[config.name] = config
        self.save_config()

    def remove_server(self, name: str) -> None:
        self._servers.pop(name, None)
        self.save_config()

    def update_server(self, name: str, **kwargs) -> None:
        if name not in self._servers:
            raise KeyError(f"MCP 服务器 '{name}' 不存在")
        updated = self._servers[name].model_copy(update=kwargs)
        self._servers[name] = updated
        self.save_config()

    async def connect(self, name: str):
        from toolkit.core.mcp.client import MCPConnectionStatus
        if name not in self._servers:
            raise KeyError(f"MCP 服务器 '{name}' 未配置")
        self._notify(name, MCPConnectionStatus.CONNECTING)
        conn = await self._pool.connect(self._servers[name])
        self._notify(name, conn.status)
        return conn

    async def connect_all(self) -> list:
        if not self._servers:
            self.load_config()
        tasks = [self.connect(name) for name in self._servers
                 if getattr(self._servers[name], "enabled", True)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        connections = []
        for r in results:
            if isinstance(r, Exception):
                logger.error("MCP 连接异常: %s", r)
            else:
                connections.append(r)
        # Inject MCP tools into ToolRegistry
        if self._tool_registry:
            mcp_tools = self._bridge.get_tool_definitions()
            self._tool_registry.register_mcp_tools(mcp_tools)
        return connections

    async def disconnect(self, name: str) -> None:
        from toolkit.core.mcp.client import MCPConnectionStatus
        await self._pool.disconnect(name)
        self._notify(name, MCPConnectionStatus.DISCONNECTED)

    async def disconnect_all(self) -> None:
        await self._pool.disconnect_all()

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> Any:
        return await self._bridge.call_tool(server_name, tool_name, arguments)

    def get_tool_definitions(self) -> list:
        return self._bridge.get_tool_definitions()

    def get_connections(self) -> list:
        return self._pool.get_all_connections()

    def get_servers(self) -> dict:
        return dict(self._servers)

    def _notify(self, name: str, status: str) -> None:
        if self._on_status_change:
            try:
                self._on_status_change(name, status)
            except Exception:
                logger.debug("状态回调异常", exc_info=True)
