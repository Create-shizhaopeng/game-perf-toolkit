"""LLM Manager 模块插件入口。"""

from __future__ import annotations

import logging

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin
from . import strings_gui as s

LOGGER = logging.getLogger("llm_manager.plugin")


class LLMManagerPlugin(BasePlugin):
    """LLM Manager 模块插件 — 注册配置管理服务。"""

    def get_plugin_info(self) -> dict:
        return {
            "name": "llm_manager",
            "display_name": s.PLUGIN_DISPLAY_NAME,
            "version": "0.1.0",
            "description": s.PLUGIN_DESCRIPTION,
        }

    @hookimpl
    def register_gui_tab(self):
        """不注册独立 Tab，Provider 管理通过设置面板入口。"""
        return None

    @hookimpl
    def register_agent_tools(self) -> list:
        return []

    @hookimpl
    def register_skills(self) -> list:
        return []

    @hookimpl
    def on_startup(self, context: dict) -> None:
        try:
            db_manager = context.get("db_manager")
            from .service import LLMManagerService

            service = LLMManagerService(db_manager=db_manager)
            service.load()
            context["llm_manager_service"] = service

            llm_manager = context.get("llm_manager")
            if llm_manager and hasattr(llm_manager, "set_llm_service"):
                llm_manager.set_llm_service(service)

            registry = context.get("service_registry")
            if registry:
                registry.register("llm_manager_service", service)
            LOGGER.info("LLMManagerService 已注册")
        except Exception as e:
            LOGGER.error("LLMManagerService 初始化失败: %s", e, exc_info=True)

    @hookimpl
    def on_shutdown(self) -> None:
        LOGGER.info("LLMManagerService 已关闭")
