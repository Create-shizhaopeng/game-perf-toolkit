# -*- coding: utf-8 -*-
"""Perfetto 解析分析 — 插件注册入口。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from toolkit.core.app_paths import get_db_path, get_exe_dir, get_user_data_dir
from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

_SKILL_DIR = Path(__file__).parent.parent / "skills" / "perfetto-analysis"

_PA_EXECUTE_SQL_DESCRIPTION = (
    "对 Perfetto trace 文件执行 PerfettoSQL 查询。\n\n"
    "## 使用方式\n\n"
    "1. SQL 来源：读取 Skill YAML 技能文件（atomic/composite/*.skill.yaml）中 steps[].sql 字段\n"
    "2. 变量替换：将 SQL 中的 ${variable} 替换为实际参数值后再调用本工具\n"
    "   例：SQL 中的 ${package} → 实际包名 com.game.xxx\n"
    "3. 返回结构：{\"success\": bool, \"rows\": [{col: val, ...}, ...], \"row_count\": int, \"error\": str}\n"
    "4. SQL 片段：fragments/ 目录下的 .sql CTE 需要手动拼接到 SQL 的 WITH 子句中\n\n"
    "## 可选参数\n\n"
    "- bin_path: trace_processor_shell 二进制路径，不传则自动下载\n"
    "  （国内网络无法访问 Google Cloud Storage 时建议传入本地路径）\n"
    "- load_timeout: 启动超时秒数，默认 30\n\n"
    "## 技能索引\n\n"
    "查看 SKILL.md 中的场景索引表，了解针对不同问题应执行哪些 SQL。"
)


class PerfettoAnalysisPlugin(BasePlugin):

    _service: Any = None

    @hookimpl
    def get_plugin_info(self) -> dict:
        return {
            "name": "perfetto_analysis",
            "display_name": "Perfetto 解析分析",
            "version": "0.2.0",
        }

    @hookimpl
    def register_gui_tab(self):
        return None

    @hookimpl
    def register_agent_tools(self) -> list:
        return [
            {
                "name": "pa_execute_sql",
                "description": _PA_EXECUTE_SQL_DESCRIPTION,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {
                            "type": "string",
                            "description": "Perfetto trace 文件路径（.perfetto-trace）",
                        },
                        "sql": {
                            "type": "string",
                            "description": "PerfettoSQL 查询语句（先将 ${variable} 替换为实际值）",
                        },
                        "bin_path": {
                            "type": "string",
                            "description": "trace_processor_shell 二进制路径，不传则自动下载",
                        },
                        "load_timeout": {
                            "type": "integer",
                            "description": "启动超时秒数，默认 30",
                        },
                    },
                    "required": ["trace_path", "sql"],
                },
                "method": self._execute_sql,
            },
        ]

    @hookimpl
    def register_skills(self) -> list[str]:
        skill_md = _SKILL_DIR / "SKILL.md"
        if skill_md.exists():
            return [str(skill_md)]
        return []

    @staticmethod
    def _execute_sql(
        trace_path: str,
        sql: str,
        bin_path: str | None = None,
        load_timeout: int = 30,
    ) -> dict[str, Any]:
        """执行 PerfettoSQL — 从 Skill scripts/ 目录导入，确保 Skill 可独立迁移。"""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "sql_executor", _SKILL_DIR / "scripts" / "sql_executor.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.execute_sql(
            trace_path, sql,
            bin_path=bin_path,
            load_timeout=load_timeout,
        )

    @hookimpl
    def on_startup(self, context: dict) -> None:
        self.context = context

        from .service import PerfettoAnalysisService

        data_dir = get_user_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)

        db_manager = context.get("db_manager")
        root_dir = context.get("root_dir")

        self._service = PerfettoAnalysisService(
            data_dir=data_dir,
            db_manager=db_manager,
            root_dir=root_dir,
        )

        context["pa_service"] = self._service

        self._event_bus = context.get("event_bus")
        if self._event_bus:
            self._event_bus.on(
                "perfetto_capture.trace_ready", self._on_trace_ready,
            )

        if not self._service.perfetto_available:
            logger.warning(
                "perfetto 包未安装，请执行: pip install perfetto>=0.16.0",
            )

    @hookimpl
    def on_shutdown(self) -> None:
        if self._event_bus:
            self._event_bus.off(
                "perfetto_capture.trace_ready", self._on_trace_ready,
            )

    def _on_trace_ready(self, trace_path: str = "", **kwargs: Any) -> None:
        """响应 perfetto_capture.trace_ready 事件 — 通知 Agent 有新 trace 可用。"""
        if not trace_path:
            return

        logger.info("收到 trace_ready 事件: %s", trace_path)

        if self._event_bus:
            self._event_bus.emit(
                "perfetto_analysis.trace_ready",
                trace_path=trace_path,
            )
