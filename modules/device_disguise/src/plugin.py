"""设备伪装工具 — 插件注册入口"""

from __future__ import annotations

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin


class DeviceDisguisePlugin(BasePlugin):

    def __init__(self) -> None:
        super().__init__()
        self._service = None
        self._profile_mgr = None

    @hookimpl
    def get_plugin_info(self) -> dict:
        return {
            "name": "device_disguise",
            "display_name": "设备伪装工具",
            "version": "1.0.0",
        }

    @hookimpl
    def register_gui_tab(self):
        from .gui_tab import DeviceDisguiseTab

        tab = DeviceDisguiseTab(context=self.context)
        return tab

    @hookimpl
    def register_agent_tools(self) -> list:
        if not self._service:
            return []
        tools = [
            {
                "name": "device_status",
                "description": "获取设备连接状态和伪装信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "serial": {
                            "type": "string",
                            "description": "设备序列号（留空则自动选择第一个已连接设备）",
                        },
                    },
                    "required": [],
                },
                "method": self._service.get_device_state,
            },
            {
                "name": "device_disguise",
                "description": "执行设备信息伪装，将 ODM 属性修改为目标品牌/厂商/型号",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "serial": {
                            "type": "string",
                            "description": "设备序列号（留空则自动选择第一个已连接设备）",
                        },
                        "brand": {
                            "type": "string",
                            "description": "目标品牌（如 华为、小米、OPPO）",
                        },
                        "manufacturer": {
                            "type": "string",
                            "description": "目标厂商（如 Huawei、Xiaomi、OPPO）",
                        },
                        "model": {
                            "type": "string",
                            "description": "目标型号（如 ANA-AN00、M2007J3SC）",
                        },
                    },
                    "required": ["brand", "manufacturer", "model"],
                },
                "method": self._service.disguise,
            },
            {
                "name": "device_reset",
                "description": "还原设备信息到 vendor 原始状态",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "serial": {
                            "type": "string",
                            "description": "设备序列号（留空则自动选择第一个已连接设备）",
                        },
                    },
                    "required": [],
                },
                "method": self._service.reset,
            },
        ]
        # Profile 相关工具
        if self._profile_mgr:
            tools.extend([
                {
                    "name": "profile_list",
                    "description": "列出所有设备档案",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                    "method": self._profile_mgr.get_all,
                },
                {
                    "name": "profile_add",
                    "description": "添加设备档案",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "brand": {
                                "type": "string",
                                "description": "品牌",
                            },
                            "manufacturer": {
                                "type": "string",
                                "description": "厂商",
                            },
                            "model": {
                                "type": "string",
                                "description": "型号",
                            },
                            "notes": {
                                "type": "string",
                                "description": "备注",
                            },
                        },
                        "required": ["brand", "manufacturer", "model"],
                    },
                    "method": self._profile_mgr.add,
                },
                {
                    "name": "profile_import",
                    "description": "从 JSON 文件批量导入设备档案",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file": {
                                "type": "string",
                                "description": "JSON 文件路径",
                            },
                        },
                        "required": ["file"],
                    },
                    "method": self._profile_mgr.import_from,
                },
            ])
        return tools

    @hookimpl
    def register_skills(self) -> list[str]:
        from pathlib import Path

        skill_path = Path(__file__).parent.parent / "skills" / "device-disguise" / "SKILL.md"
        if skill_path.exists():
            return [str(skill_path)]
        return []

    @hookimpl
    def on_startup(self, context: dict):
        self.context = context

        from toolkit.core.adb_manager import AdbManager

        from .models import ProfileManager
        from .service import DeviceDisguiseService

        adb: AdbManager = context.get("adb")
        if adb is None:
            adb = AdbManager()

        self._service = DeviceDisguiseService(adb)
        self._profile_mgr = ProfileManager()

        self.context["dd_adb"] = adb
        self.context["dd_service"] = self._service
        self.context["dd_profile_mgr"] = self._profile_mgr

    @hookimpl
    def on_shutdown(self):
        pass
