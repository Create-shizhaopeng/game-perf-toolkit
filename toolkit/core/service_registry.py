"""服务注册表 — Agent 和框架通过此发现和调用模块服务"""

from __future__ import annotations

import inspect
import logging
from typing import Any, get_type_hints

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """模块服务的注册与发现中心。

    每个模块在启动时将自己的 Service 实例注册到这里，
    Agent 和其他消费者通过名称查找并调用服务。
    """

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        """注册模块服务。"""
        if name in self._services:
            logger.warning("服务覆盖注册: %s", name)
        self._services[name] = service
        logger.info("服务已注册: %s (%s)", name, type(service).__name__)

    def get(self, name: str) -> Any:
        """获取已注册的服务。

        Raises:
            KeyError: 服务未注册时。
        """
        if name not in self._services:
            raise KeyError(f"服务未注册: {name}")
        return self._services[name]

    def has(self, name: str) -> bool:
        """检查服务是否已注册。"""
        return name in self._services

    def list_services(self) -> list[str]:
        """返回所有已注册的服务名列表。"""
        return list(self._services.keys())

    def get_service_schema(self, name: str) -> dict:
        """获取服务的输入/输出 JSON Schema。

        要求服务类包含 Pydantic 模型标注，自动生成 schema。
        Agent 可用此了解如何调用服务。
        """
        service = self.get(name)
        schema: dict[str, Any] = {"name": name, "methods": {}}
        for method_name in dir(service):
            if method_name.startswith("_"):
                continue
            method = getattr(service, method_name)
            if not callable(method):
                continue
            try:
                hints = get_type_hints(method)
            except Exception:
                hints = getattr(method, "__annotations__", {})
            method_info: dict[str, Any] = {"doc": method.__doc__ or ""}
            if "return" in hints:
                ret_type = hints["return"]
                if hasattr(ret_type, "model_json_schema"):
                    method_info["output_schema"] = ret_type.model_json_schema()
            param_types = {k: v for k, v in hints.items() if k != "return"}
            for param_name, param_type in param_types.items():
                if hasattr(param_type, "model_json_schema"):
                    method_info.setdefault("input_schema", {})
                    method_info["input_schema"][param_name] = param_type.model_json_schema()
            schema["methods"][method_name] = method_info
        return schema
