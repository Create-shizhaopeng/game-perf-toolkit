# -*- coding: utf-8 -*-
"""agent_chat 模块 — ToolRegistry + ToolExecutor 测试。"""
from __future__ import annotations

import json

import pytest

from modules.agent_chat.src.models import (
    ToolCall,
    ToolCallStatus,
    ToolDefinition,
    ToolResult,
)
from modules.agent_chat.src.tools.executor import ToolExecutor, _serialize_result
from modules.agent_chat.src.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

class TestToolRegistry:

    def test_register_and_get(self):
        reg = ToolRegistry()
        td = ToolDefinition(name="analyze", description="分析 trace")
        reg.register(td)
        assert reg.get_tool("analyze") is td

    def test_get_nonexistent(self):
        reg = ToolRegistry()
        assert reg.get_tool("nope") is None

    def test_register_many(self):
        reg = ToolRegistry()
        tools = [
            ToolDefinition(name="a", description="A"),
            ToolDefinition(name="b", description="B"),
        ]
        reg.register_many(tools)
        assert len(reg.get_definitions()) == 2

    def test_duplicate_overwrites(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="x", description="old"))
        reg.register(ToolDefinition(name="x", description="new"))
        assert reg.get_tool("x").description == "new"

    def test_get_tool_names(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="a", description="A"))
        reg.register(ToolDefinition(name="b", description="B"))
        assert set(reg.get_tool_names()) == {"a", "b"}

    def test_enhance_schema_from_function(self):
        def my_tool(path: str, count: int = 5) -> str:
            return "ok"

        reg = ToolRegistry()
        td = ToolDefinition(name="my_tool", description="测试", method=my_tool)
        reg._enhance_schema(td)

        assert td.parameters["type"] == "object"
        assert "path" in td.parameters["properties"]
        assert td.parameters["properties"]["path"]["type"] == "string"
        assert td.parameters["properties"]["count"]["type"] == "integer"
        assert "path" in td.parameters["required"]
        assert "count" not in td.parameters["required"]

    def test_no_enhance_if_params_exist(self):
        def my_tool(path: str) -> str:
            return "ok"

        reg = ToolRegistry()
        existing_params = {"type": "object", "properties": {"x": {"type": "string"}}}
        td = ToolDefinition(
            name="my_tool", description="测试",
            parameters=existing_params, method=my_tool,
        )
        reg._enhance_schema(td)
        assert td.parameters is existing_params

    def test_enhance_skips_callable_params(self):
        """Callable 类型参数不应出现在 JSON Schema 中。"""
        import collections.abc
        import types

        func_code = (
            "import collections.abc\n"
            "def my_tool(path: str, callback: collections.abc.Callable | None = None) -> str:\n"
            "    return 'ok'\n"
        )
        ns: dict = {}
        exec(func_code, ns)
        my_tool = ns["my_tool"]

        reg = ToolRegistry()
        td = ToolDefinition(name="cb_tool", description="回调测试", method=my_tool)
        reg._enhance_schema(td)

        assert "path" in td.parameters["properties"]
        assert "callback" not in td.parameters["properties"]

    def test_enhance_skips_pure_callable(self):
        func_code = (
            "import collections.abc\n"
            "def tool_with_cb(name: str, on_done: collections.abc.Callable = None) -> str:\n"
            "    return 'ok'\n"
        )
        ns: dict = {}
        exec(func_code, ns)
        tool_with_cb = ns["tool_with_cb"]

        reg = ToolRegistry()
        td = ToolDefinition(name="cb2", description="test", method=tool_with_cb)
        reg._enhance_schema(td)

        assert "name" in td.parameters["properties"]
        assert "on_done" not in td.parameters["properties"]


class TestIsCallableType:

    def test_plain_callable(self):
        from typing import Callable
        from modules.agent_chat.src.tools.registry import _is_callable_type
        assert _is_callable_type(Callable) is True

    def test_callable_with_args(self):
        from typing import Callable
        from modules.agent_chat.src.tools.registry import _is_callable_type
        assert _is_callable_type(Callable[[int], str]) is True

    def test_optional_callable(self):
        from typing import Callable, Optional
        from modules.agent_chat.src.tools.registry import _is_callable_type
        assert _is_callable_type(Callable | None) is True

    def test_str_is_not_callable(self):
        from modules.agent_chat.src.tools.registry import _is_callable_type
        assert _is_callable_type(str) is False

    def test_none_is_not_callable(self):
        from modules.agent_chat.src.tools.registry import _is_callable_type
        assert _is_callable_type(None) is False

    def test_int_is_not_callable(self):
        from modules.agent_chat.src.tools.registry import _is_callable_type
        assert _is_callable_type(int) is False


# ---------------------------------------------------------------------------
# ToolExecutor
# ---------------------------------------------------------------------------

class TestToolExecutor:

    def _make_registry_with_tool(self, name: str, method):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name=name, description="desc", method=method))
        return reg

    @pytest.mark.asyncio
    async def test_execute_success(self):
        def echo(message: str) -> str:
            return f"echo: {message}"

        reg = self._make_registry_with_tool("echo", echo)
        executor = ToolExecutor(reg)

        tc = ToolCall(id="c1", name="echo", arguments={"message": "hello"})
        result = await executor.execute(tc)

        assert not result.is_error
        assert "echo: hello" in result.content
        assert tc.status == ToolCallStatus.COMPLETE
        assert tc.elapsed_ms > 0

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        reg = ToolRegistry()
        executor = ToolExecutor(reg)

        tc = ToolCall(id="c1", name="unknown", arguments={})
        result = await executor.execute(tc)
        assert result.is_error
        assert "未知工具" in result.content

    @pytest.mark.asyncio
    async def test_execute_exception(self):
        def failing():
            raise ValueError("测试错误")

        reg = self._make_registry_with_tool("fail", failing)
        executor = ToolExecutor(reg)

        tc = ToolCall(id="c1", name="fail", arguments={})
        result = await executor.execute(tc)
        assert result.is_error
        assert "ValueError" in result.content
        assert tc.status == ToolCallStatus.FAILED

    @pytest.mark.asyncio
    async def test_result_truncation(self):
        def big_output() -> str:
            return "X" * 5000

        reg = self._make_registry_with_tool("big", big_output)
        executor = ToolExecutor(reg, max_result_length=100)

        tc = ToolCall(id="c1", name="big", arguments={})
        result = await executor.execute(tc)
        assert len(result.content) < 200
        assert "截断" in result.content

    @pytest.mark.asyncio
    async def test_dict_result(self):
        def dict_tool() -> dict:
            return {"fps": 60, "jank": 3}

        reg = self._make_registry_with_tool("dict_t", dict_tool)
        executor = ToolExecutor(reg)

        tc = ToolCall(id="c1", name="dict_t", arguments={})
        result = await executor.execute(tc)
        parsed = json.loads(result.content)
        assert parsed["fps"] == 60

    @pytest.mark.asyncio
    async def test_none_result(self):
        def void_tool() -> None:
            pass

        reg = self._make_registry_with_tool("void", void_tool)
        executor = ToolExecutor(reg)

        tc = ToolCall(id="c1", name="void", arguments={})
        result = await executor.execute(tc)
        assert not result.is_error
        assert "无返回值" in result.content

    @pytest.mark.asyncio
    async def test_report_paths_extraction(self):
        def report_tool() -> dict:
            return {"report_path": "/out/report.md", "data": "ok"}

        reg = self._make_registry_with_tool("report", report_tool)
        executor = ToolExecutor(reg)

        tc = ToolCall(id="c1", name="report", arguments={})
        result = await executor.execute(tc)
        assert "/out/report.md" in result.report_paths

    @pytest.mark.asyncio
    async def test_execute_async_tool(self):
        """验证 async 工具可以直接 await 而不走 to_thread。"""
        async def async_echo(message: str) -> str:
            return f"async: {message}"

        reg = self._make_registry_with_tool("async_echo", async_echo)
        executor = ToolExecutor(reg)

        tc = ToolCall(id="c1", name="async_echo", arguments={"message": "hi"})
        result = await executor.execute(tc)
        assert not result.is_error
        assert "async: hi" in result.content


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:

    def test_str(self):
        assert _serialize_result("hello") == "hello"

    def test_none(self):
        assert "无返回值" in _serialize_result(None)

    def test_dict(self):
        result = _serialize_result({"a": 1})
        parsed = json.loads(result)
        assert parsed["a"] == 1

    def test_list(self):
        result = _serialize_result([1, 2, 3])
        parsed = json.loads(result)
        assert parsed == [1, 2, 3]
