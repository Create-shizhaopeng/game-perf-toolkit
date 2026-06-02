"""core/mcp/registry 单元测试 — 验证 MCP 注册与工具桥接。

测试文档: tests/doc/test_core_mcp_registry.md
关联 Spec: openspec/changes/agent-wiring-fix/specs/agent-core-refactor/spec.md (FR-003, FR-015 delta)
"""
from __future__ import annotations

import asyncio
from typing import Generator

import pytest

from toolkit.core.tool_registry import ToolRegistry
from toolkit.core.mcp.registry import MCPRegistry


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def tool_registry() -> ToolRegistry:
    """创建空的 ToolRegistry 实例。"""
    return ToolRegistry()


@pytest.fixture
def mcp_registry(tool_registry: ToolRegistry) -> Generator[MCPRegistry, None, None]:
    """创建 MCPRegistry 并注入 ToolRegistry。"""
    yield MCPRegistry(tool_registry=tool_registry)


# ── Mock handler class for register_local ───────────────────────────────

class _MockHandler:
    """测试用 handler — 模拟子模块 MCP 实现。

    有 2 个公开方法（各有 docstring），用于验证内省注册逻辑。
    """

    def list_items(self, query: str = "") -> str:
        """列出所有项目。"""
        return "item1, item2"

    def get_item(self, item_id: str) -> str:
        """获取指定项目详情。"""
        return f"detail of {item_id}"


# ── register_local ──────────────────────────────────────────────────────

class TestRegisterLocal:
    """测试 MCPRegistry.register_local() — 进程内 MCP 能力注册。"""

    def test_registers_tools_with_mcp_prefix(self, mcp_registry: MCPRegistry, tool_registry: ToolRegistry) -> None:
        """工具应以 mcp__{module}__{method} 格式注册到 ToolRegistry。"""
        mcp_registry.register_local("test_module", _MockHandler)

        names = tool_registry.get_tool_names()
        assert "mcp__test_module__list_items" in names, (
            f"Expected mcp__test_module__list_items in {names}"
        )
        assert "mcp__test_module__get_item" in names, (
            f"Expected mcp__test_module__get_item in {names}"
        )

    def test_tools_have_correct_toolset(self, mcp_registry: MCPRegistry, tool_registry: ToolRegistry) -> None:
        """注册的工具应归属 mcp-local toolset。"""
        mcp_registry.register_local("test_module", _MockHandler)

        entry = tool_registry.get_entry("mcp__test_module__list_items")
        assert entry is not None, "Tool entry not found"
        assert entry.toolset == "mcp-local", (
            f"Expected toolset 'mcp-local', got '{entry.toolset}'"
        )

    def test_tool_handler_is_callable(self, mcp_registry: MCPRegistry, tool_registry: ToolRegistry) -> None:
        """生成的 handler 应为合法可调用对象。"""
        mcp_registry.register_local("test_module", _MockHandler)

        entry = tool_registry.get_entry("mcp__test_module__list_items")
        assert entry is not None
        assert callable(entry.handler), f"handler is not callable: {type(entry.handler)}"

    def test_skips_methods_without_docstring(self, mcp_registry: MCPRegistry, tool_registry: ToolRegistry) -> None:
        """无 docstring 的公开方法应被跳过（非工具方法）。"""

        class _NoDocHandler:
            def tool_method(self) -> str:
                return "ok"

            def _private(self) -> None:
                """private doc."""
                pass

        mcp_registry.register_local("nodoc", _NoDocHandler)
        names = tool_registry.get_tool_names()
        assert "mcp__nodoc__tool_method" not in names, (
            f"Method without docstring should not be registered: {names}"
        )


# ── register_remote ─────────────────────────────────────────────────────

class TestRegisterRemote:
    """测试 MCPRegistry.register_remote() — 远程 MCP 服务注册。"""

    def test_stores_remote_config(self, mcp_registry: MCPRegistry) -> None:
        """注册后 get_servers() 应包含远程配置。"""
        mcp_registry.register_remote("https://example.com/mcp", {"token": "abc"})
        servers = mcp_registry.get_servers()
        assert len(servers) > 0, "Expected at least 1 server after register_remote"


# ── No auto-persist on register ─────────────────────────────────────────

class TestNoAutoPersist:
    """验证注册操作不触发意外的自动持久化。"""

    def test_register_remote_does_not_save(self, mcp_registry: MCPRegistry, monkeypatch: pytest.MonkeyPatch) -> None:
        """register_remote 不应触发 save_config。"""
        save_called: list[int] = []

        def fake_save() -> None:
            save_called.append(1)

        monkeypatch.setattr(mcp_registry, "save_config", fake_save)
        mcp_registry.register_remote("https://example.com/mcp")
        assert len(save_called) == 0, (
            f"register_remote should NOT call save_config, called {len(save_called)} times"
        )

    def test_add_server_triggers_save(self, mcp_registry: MCPRegistry, monkeypatch: pytest.MonkeyPatch) -> None:
        """add_server 应触发 save_config（显式管理操作）。"""
        save_called: list[int] = []

        def fake_save() -> None:
            save_called.append(1)

        monkeypatch.setattr(mcp_registry, "save_config", fake_save)

        from toolkit.agent.models import MCPServerConfig
        cfg = MCPServerConfig(name="test", command="echo")
        mcp_registry.add_server(cfg)
        assert len(save_called) == 1, (
            f"add_server should call save_config once, called {len(save_called)} times"
        )


# ── connect_all ─────────────────────────────────────────────────────────

class TestConnectAll:
    """验证 connect_all 的安全空返回行为。"""

    def test_connect_all_empty_returns_empty_list(self, mcp_registry: MCPRegistry) -> None:
        """无配置时 connect_all 应安全返回空列表，不抛异常。"""

        async def run() -> list:
            return await mcp_registry.connect_all()

        result = asyncio.run(run())
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert result == [], f"Expected empty list, got {result}"
