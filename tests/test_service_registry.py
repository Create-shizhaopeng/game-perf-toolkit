"""ServiceRegistry 单元测试（含 JSON Schema 生成验证）"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from toolkit.core.service_registry import ServiceRegistry


class SampleInput(BaseModel):
    name: str
    value: int


class SampleOutput(BaseModel):
    result: str
    code: int


class SampleService:
    """测试用服务"""

    def process(self, data: SampleInput) -> SampleOutput:
        """处理数据"""
        return SampleOutput(result=data.name, code=data.value)

    def simple_method(self) -> None:
        """无参数方法"""

    def _private(self) -> None:
        """私有方法不应出现在 schema 中"""


class TestServiceRegistry:
    def test_register_and_get(self) -> None:
        reg = ServiceRegistry()
        svc = SampleService()
        reg.register("sample", svc)
        assert reg.get("sample") is svc

    def test_get_nonexistent_raises(self) -> None:
        reg = ServiceRegistry()
        with pytest.raises(KeyError, match="服务未注册"):
            reg.get("missing")

    def test_has(self) -> None:
        reg = ServiceRegistry()
        reg.register("x", object())
        assert reg.has("x")
        assert not reg.has("y")

    def test_list_services(self) -> None:
        reg = ServiceRegistry()
        reg.register("a", object())
        reg.register("b", object())
        assert sorted(reg.list_services()) == ["a", "b"]

    def test_duplicate_register_overwrites(self) -> None:
        reg = ServiceRegistry()
        svc1 = object()
        svc2 = object()
        reg.register("dup", svc1)
        reg.register("dup", svc2)
        assert reg.get("dup") is svc2

    def test_get_service_schema_includes_methods(self) -> None:
        reg = ServiceRegistry()
        reg.register("sample", SampleService())
        schema = reg.get_service_schema("sample")
        assert schema["name"] == "sample"
        assert "process" in schema["methods"]
        assert "simple_method" in schema["methods"]
        assert "_private" not in schema["methods"]

    def test_get_service_schema_pydantic_models(self) -> None:
        reg = ServiceRegistry()
        reg.register("sample", SampleService())
        schema = reg.get_service_schema("sample")
        process = schema["methods"]["process"]
        assert "input_schema" in process
        assert "data" in process["input_schema"]
        assert "output_schema" in process
        assert process["output_schema"]["title"] == "SampleOutput"

    def test_get_service_schema_no_pydantic(self) -> None:
        reg = ServiceRegistry()
        reg.register("simple", SampleService())
        schema = reg.get_service_schema("simple")
        simple = schema["methods"]["simple_method"]
        assert "input_schema" not in simple
