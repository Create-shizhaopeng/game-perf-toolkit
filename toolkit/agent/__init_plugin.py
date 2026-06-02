# -*- coding: utf-8 -*-
"""Agent — 插件注册入口。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

_logger = logging.getLogger("agent")

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin


class AgentPlugin(BasePlugin):

    _service: Any = None

    @hookimpl
    def get_plugin_info(self) -> dict:
        return {
            "name": "agent_chat",
            "display_name": "Agent 智能助手",
            "version": "0.1.0",
        }

    @hookimpl
    def register_gui_tab(self):
        from .gui_tab import AgentTab

        return AgentTab(context=self.context)

    @hookimpl
    def register_agent_tools(self) -> list:
        from .tools.builtin import create_workspace, list_workspace_files

        return [
            {
                "name": "create_workspace",
                "description": "创建分析工作目录，用于存放综合分析的中间文件和报告。返回工作目录绝对路径。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "工作目录名称前缀（如 'jank_analysis'），留空默认 'analysis'",
                        },
                    },
                    "required": [],
                },
                "method": create_workspace,
            },
            {
                "name": "list_workspace_files",
                "description": "列出分析工作目录下的所有文件及大小。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace_path": {
                            "type": "string",
                            "description": "工作目录绝对路径",
                        },
                    },
                    "required": ["workspace_path"],
                },
                "method": list_workspace_files,
            },
        ]

    @hookimpl
    def on_startup(self, context: dict) -> None:
        self.context = context

        from toolkit.core.app_paths import get_exe_dir

        from .models import load_config_with_env

        data_dir = get_exe_dir() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "sops").mkdir(exist_ok=True)
        (data_dir / "agent_workspace").mkdir(exist_ok=True)

        config = load_config_with_env()

        context["ac_config"] = config
        context["ac_data_dir"] = str(data_dir)

        has_api_key = bool(config.api_key or config.glm_api_key or config.claude_api_key)
        if not has_api_key:
            _logger.warning(
                "未配置 API Key，请在设置中配置后使用 Agent 功能",
            )

    @hookimpl
    def on_shutdown(self) -> None:
        pass
