"""pluggy 钩子规范定义 — 所有模块必须实现的接口"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pluggy

if TYPE_CHECKING:
    from toolkit.gui.base_tab import BaseTab

hookspec = pluggy.HookspecMarker("lv_toolkit")
hookimpl = pluggy.HookimplMarker("lv_toolkit")

PROJECT_NAME = "lv_toolkit"


class ToolkitHookSpec:
    """模块插件必须实现的钩子接口。

    所有被 @hookspec 标记的方法都是模块可以实现的扩展点。
    模块通过 @hookimpl 标记来提供具体实现。
    """

    @hookspec
    def get_plugin_info(self) -> dict:
        """返回模块基本信息。

        Returns:
            包含 name, display_name, version, description 等字段的字典。
        """

    @hookspec
    def register_cli_commands(self, cli_app: Any) -> None:
        """注册模块的 CLI 子命令。

        Args:
            cli_app: typer.Typer 实例，模块通过 add_typer 挂载子命令组。
        """

    @hookspec
    def register_gui_tab(self) -> BaseTab | None:
        """返回模块的 GUI Tab 实例。

        无 GUI 界面的模块返回 None。
        """

    @hookspec
    def register_agent_tools(self) -> list[dict]:
        """返回模块向 Agent 暴露的工具列表。

        每个工具是一个字典，包含 name, description, parameters, handler 字段，
        格式与 LLM Function Calling 对齐。
        """

    @hookspec
    def on_startup(self, context: dict) -> None:
        """应用启动时的初始化回调。

        Args:
            context: 包含核心服务实例的字典（adb_manager, config_manager 等）。
        """

    @hookspec
    def on_shutdown(self) -> None:
        """应用关闭时的清理回调。"""
