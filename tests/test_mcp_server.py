"""MCP Server 基本测试 — 验证工具注册和动态签名构建。"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch


class TestBuildToolHandler:
    """_build_tool_handler 单元测试。"""

    def test_handler_created_with_proper_signature(self):
        """handler 有正确的参数签名。"""
        from toolkit.core.mcp.server import _build_tool_handler

        executor = MagicMock()
        parameters = {
            "properties": {
                "serial": {"type": "string"},
                "verbose": {"type": "boolean"},
            },
            "required": ["serial"],
        }

        handler = _build_tool_handler(
            executor=executor,
            tool_name="test_tool",
            parameters=parameters,
        )

        sig = inspect.signature(handler)
        param_names = list(sig.parameters.keys())
        assert "serial" in param_names
        assert "verbose" in param_names

    def test_handler_name_is_tool_name(self):
        """handler 函数名等于 tool_name。"""
        from toolkit.core.mcp.server import _build_tool_handler

        handler = _build_tool_handler(
            executor=MagicMock(),
            tool_name="my_device_tool",
            parameters={"properties": {}},
        )

        assert handler.__name__ == "my_device_tool"

    def test_handler_async(self):
        """handler 是协程函数。"""
        from toolkit.core.mcp.server import _build_tool_handler

        handler = _build_tool_handler(
            executor=MagicMock(),
            tool_name="async_tool",
            parameters={"properties": {}},
        )

        assert inspect.iscoroutinefunction(handler)

    def test_handler_with_nested_parameters(self):
        """处理嵌套参数（object/array 类型）。"""
        from toolkit.core.mcp.server import _build_tool_handler

        parameters = {
            "properties": {
                "brand": {"type": "string"},
                "manufacturer": {"type": "string"},
                "model": {"type": "string"},
            },
            "required": ["brand", "manufacturer", "model"],
        }

        handler = _build_tool_handler(
            executor=MagicMock(),
            tool_name="device_disguise",
            parameters=parameters,
        )

        sig = inspect.signature(handler)
        assert len(sig.parameters) == 3
        assert "brand" in sig.parameters
        assert "model" in sig.parameters


class TestJsonTypeToPython:
    """_json_type_to_python 映射测试。"""

    def test_string(self):
        from toolkit.core.mcp.server import _json_type_to_python
        assert _json_type_to_python("string") is str

    def test_integer(self):
        from toolkit.core.mcp.server import _json_type_to_python
        assert _json_type_to_python("integer") is int

    def test_number(self):
        from toolkit.core.mcp.server import _json_type_to_python
        assert _json_type_to_python("number") is float

    def test_boolean(self):
        from toolkit.core.mcp.server import _json_type_to_python
        assert _json_type_to_python("boolean") is bool

    def test_array(self):
        from toolkit.core.mcp.server import _json_type_to_python
        assert _json_type_to_python("array") is list

    def test_object(self):
        from toolkit.core.mcp.server import _json_type_to_python
        assert _json_type_to_python("object") is dict

    def test_unknown_defaults_to_str(self):
        from toolkit.core.mcp.server import _json_type_to_python
        assert _json_type_to_python("unknown_type") is str


class TestCreateMcpServer:
    """create_mcp_server 集成测试。"""

    def test_server_creation(self):
        """FastMCP 实例可以成功创建。"""
        from toolkit.core.mcp.server import create_mcp_server

        tool_registry = MagicMock()
        tool_registry.get_definitions.return_value = []

        tool_executor = MagicMock()

        mcp = create_mcp_server(tool_registry, tool_executor)
        assert mcp is not None

    def test_tools_without_method_are_skipped(self, caplog):
        """没有 method 的 ToolDefinition 被跳过。"""
        import logging
        from toolkit.core.mcp.server import create_mcp_server

        td = MagicMock()
        td.name = "no_method_tool"
        td.method = None
        td.description = "No method"
        td.parameters = {"properties": {}}

        tool_registry = MagicMock()
        tool_registry.get_definitions.return_value = [td]

        mcp = create_mcp_server(tool_registry, MagicMock())
        assert mcp is not None
        # 应该有一条 warning 日志
        assert any("no_method_tool" in rec.message for rec in caplog.records if rec.levelno == logging.WARNING)
