# -*- coding: utf-8 -*-
"""MCP 管理层测试 — 配置加载/保存、连接池、工具桥接。"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.agent_chat.src.models import (
    MCPConnection,
    MCPConnectionStatus,
    MCPServerConfig,
)


# ── 配置加载/保存 ────────────────────────────────────────────────────────


class TestMCPConfig:
    """mcp_servers.json 配置加载/保存。"""

    def test_load_config_file_missing(self, tmp_path: Path) -> None:
        from modules.agent_chat.src.mcp import load_mcp_config

        result = load_mcp_config(tmp_path / "nonexistent.json")
        assert result == {}

    def test_load_config_valid(self, tmp_path: Path) -> None:
        from modules.agent_chat.src.mcp import load_mcp_config

        cfg_file = tmp_path / "mcp_servers.json"
        cfg_file.write_text(
            json.dumps(
                {
                    "servers": {
                        "test-mcp": {
                            "command": "npx",
                            "args": ["-y", "test-server"],
                            "transport": "stdio",
                            "enabled": True,
                        },
                        "disabled-mcp": {
                            "command": "node",
                            "args": [],
                            "enabled": False,
                        },
                    }
                }
            ),
            encoding="utf-8",
        )

        result = load_mcp_config(cfg_file)
        assert "test-mcp" in result
        assert "disabled-mcp" not in result
        assert result["test-mcp"].command == "npx"
        assert result["test-mcp"].args == ["-y", "test-server"]

    def test_load_config_invalid_json(self, tmp_path: Path) -> None:
        from modules.agent_chat.src.mcp import load_mcp_config

        cfg_file = tmp_path / "bad.json"
        cfg_file.write_text("{invalid", encoding="utf-8")
        result = load_mcp_config(cfg_file)
        assert result == {}

    def test_save_config(self, tmp_path: Path) -> None:
        from modules.agent_chat.src.mcp import save_mcp_config

        servers = {
            "my-mcp": MCPServerConfig(
                name="my-mcp", command="npx", args=["arg1"]
            )
        }
        out = tmp_path / "out.json"
        save_mcp_config(servers, out)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert "my-mcp" in data["servers"]
        assert data["servers"]["my-mcp"]["command"] == "npx"

    def test_check_mcp_available(self) -> None:
        from modules.agent_chat.src.mcp import check_mcp_available

        avail, msg = check_mcp_available()
        # mcp 应已安装
        assert isinstance(avail, bool)
        assert isinstance(msg, str)


# ── 连接池 ────────────────────────────────────────────────────────────


class TestConnectionPool:
    """ConnectionPool 连接和断开逻辑。"""

    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        from modules.agent_chat.src.mcp.connection import ConnectionPool

        pool = ConnectionPool()
        config = MCPServerConfig(name="mock-srv", command="echo")

        mock_session = MagicMock()
        mock_tools = [MagicMock(name="tool1"), MagicMock(name="tool2")]
        mock_tools[0].name = "tool1"
        mock_tools[1].name = "tool2"

        with patch.object(pool, "_create_session", new_callable=AsyncMock) as m:
            m.return_value = (mock_session, mock_tools)
            conn = await pool.connect(config)

        assert conn.status == MCPConnectionStatus.CONNECTED
        assert conn.available_tools == ["tool1", "tool2"]
        assert pool.is_connected("mock-srv")
        assert pool.get_session("mock-srv") is mock_session

    @pytest.mark.asyncio
    async def test_connect_failure(self) -> None:
        from modules.agent_chat.src.mcp.connection import ConnectionPool

        pool = ConnectionPool()
        config = MCPServerConfig(name="bad-srv", command="nonexistent")

        with patch.object(pool, "_create_session", new_callable=AsyncMock) as m:
            m.side_effect = ConnectionError("模拟连接失败")
            conn = await pool.connect(config)

        assert conn.status == MCPConnectionStatus.ERROR
        assert "模拟连接失败" in (conn.last_error or "")
        assert not pool.is_connected("bad-srv")

    @pytest.mark.asyncio
    async def test_disconnect(self) -> None:
        from modules.agent_chat.src.mcp.connection import ConnectionPool

        pool = ConnectionPool()
        config = MCPServerConfig(name="test-srv", command="echo")

        mock_session = MagicMock()
        with patch.object(pool, "_create_session", new_callable=AsyncMock) as m:
            m.return_value = (mock_session, [])
            await pool.connect(config)

        await pool.disconnect("test-srv")
        assert not pool.is_connected("test-srv")

    @pytest.mark.asyncio
    async def test_disconnect_all(self) -> None:
        from modules.agent_chat.src.mcp.connection import ConnectionPool

        pool = ConnectionPool()
        for name in ("s1", "s2"):
            config = MCPServerConfig(name=name, command="echo")
            with patch.object(pool, "_create_session", new_callable=AsyncMock) as m:
                m.return_value = (MagicMock(), [])
                await pool.connect(config)

        await pool.disconnect_all()
        assert pool.get_all_connections() != []
        for c in pool.get_all_connections():
            assert c.status == MCPConnectionStatus.DISCONNECTED

    def test_get_session_missing(self) -> None:
        from modules.agent_chat.src.mcp.connection import ConnectionPool

        pool = ConnectionPool()
        assert pool.get_session("no-exist") is None


# ── MCPManager ────────────────────────────────────────────────────────


class TestMCPManager:
    """MCPManager 生命周期管理。"""

    def test_load_and_save(self, tmp_path: Path) -> None:
        from modules.agent_chat.src.mcp.manager import MCPManager

        cfg_file = tmp_path / "mcp_servers.json"
        cfg_file.write_text(
            json.dumps(
                {"servers": {"srv1": {"command": "echo", "args": []}}}
            ),
            encoding="utf-8",
        )

        mgr = MCPManager(config_path=cfg_file)
        servers = mgr.load_config()
        assert "srv1" in servers

        mgr.add_server(MCPServerConfig(name="srv2", command="node"))
        reloaded = mgr.load_config()
        assert "srv2" in reloaded

    def test_remove_server(self, tmp_path: Path) -> None:
        from modules.agent_chat.src.mcp.manager import MCPManager

        cfg_file = tmp_path / "mcp_servers.json"
        cfg_file.write_text(
            json.dumps(
                {"servers": {"to_remove": {"command": "echo", "args": []}}}
            ),
            encoding="utf-8",
        )

        mgr = MCPManager(config_path=cfg_file)
        mgr.load_config()
        mgr.remove_server("to_remove")
        assert "to_remove" not in mgr.get_servers()

    @pytest.mark.asyncio
    async def test_connect_missing_server(self, tmp_path: Path) -> None:
        from modules.agent_chat.src.mcp.manager import MCPManager

        mgr = MCPManager(config_path=tmp_path / "empty.json")
        mgr.load_config()

        with pytest.raises(KeyError):
            await mgr.connect("nonexistent")

    @pytest.mark.asyncio
    async def test_status_change_callback(self, tmp_path: Path) -> None:
        from modules.agent_chat.src.mcp.manager import MCPManager

        statuses: list[tuple[str, MCPConnectionStatus]] = []

        def callback(name: str, status: MCPConnectionStatus) -> None:
            statuses.append((name, status))

        cfg_file = tmp_path / "mcp_servers.json"
        cfg_file.write_text(
            json.dumps(
                {"servers": {"cb-srv": {"command": "echo", "args": []}}}
            ),
            encoding="utf-8",
        )

        mgr = MCPManager(config_path=cfg_file, on_status_change=callback)
        mgr.load_config()

        with patch.object(mgr._pool, "connect", new_callable=AsyncMock) as m:
            mock_conn = MCPConnection(
                server_name="cb-srv",
                status=MCPConnectionStatus.CONNECTED,
            )
            m.return_value = mock_conn
            await mgr.connect("cb-srv")

        assert len(statuses) == 2
        assert statuses[0] == ("cb-srv", MCPConnectionStatus.CONNECTING)
        assert statuses[1] == ("cb-srv", MCPConnectionStatus.CONNECTED)


# ── ToolBridge ────────────────────────────────────────────────────────


class TestMCPToolBridge:
    """MCPToolBridge 工具定义生成和远程调用。"""

    @pytest.mark.asyncio
    async def test_call_tool(self) -> None:
        from modules.agent_chat.src.mcp.connection import ConnectionPool
        from modules.agent_chat.src.mcp.tool_bridge import MCPToolBridge

        pool = ConnectionPool()
        bridge = MCPToolBridge(pool)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_content = MagicMock()
        mock_content.text = '{"data": 42}'
        mock_result.content = [mock_content]
        mock_session.call_tool = AsyncMock(return_value=mock_result)
        pool._sessions["test"] = mock_session

        result = await bridge.call_tool("test", "my_tool", {"arg": "val"})
        assert result == {"data": 42}
        mock_session.call_tool.assert_called_once_with("my_tool", {"arg": "val"})

    @pytest.mark.asyncio
    async def test_call_tool_not_connected(self) -> None:
        from modules.agent_chat.src.mcp.connection import ConnectionPool
        from modules.agent_chat.src.mcp.tool_bridge import MCPToolBridge

        pool = ConnectionPool()
        bridge = MCPToolBridge(pool)

        with pytest.raises(ConnectionError, match="未连接"):
            await bridge.call_tool("nope", "tool", {})

    def test_get_tool_definitions_empty(self) -> None:
        from modules.agent_chat.src.mcp.connection import ConnectionPool
        from modules.agent_chat.src.mcp.tool_bridge import MCPToolBridge

        pool = ConnectionPool()
        bridge = MCPToolBridge(pool)
        defs = bridge.get_tool_definitions()
        assert defs == []


# ── ToolRegistry MCP 集成 ─────────────────────────────────────────────


class TestToolRegistryMCP:
    """ToolRegistry 的 MCP 工具注册和清理。"""

    def test_register_mcp_tools(self) -> None:
        from modules.agent_chat.src.models import ToolDefinition
        from modules.agent_chat.src.tools.registry import ToolRegistry

        reg = ToolRegistry()
        tools = [
            ToolDefinition(
                name="mcp__srv__query",
                description="test",
                parameters={},
                method=lambda: None,
            ),
            ToolDefinition(
                name="mcp__srv__exec",
                description="test2",
                parameters={},
                method=lambda: None,
            ),
        ]
        count = reg.register_mcp_tools(tools)
        assert count == 2
        assert reg.get_tool("mcp__srv__query") is not None

    def test_unregister_by_prefix(self) -> None:
        from modules.agent_chat.src.models import ToolDefinition
        from modules.agent_chat.src.tools.registry import ToolRegistry

        reg = ToolRegistry()
        reg.register(
            ToolDefinition(name="mcp__a__t1", description="", parameters={}, method=lambda: None)
        )
        reg.register(
            ToolDefinition(name="mcp__a__t2", description="", parameters={}, method=lambda: None)
        )
        reg.register(
            ToolDefinition(name="local_tool", description="", parameters={}, method=lambda: None)
        )

        removed = reg.unregister_by_prefix("mcp__a__")
        assert removed == 2
        assert reg.get_tool("local_tool") is not None
        assert reg.get_tool("mcp__a__t1") is None
