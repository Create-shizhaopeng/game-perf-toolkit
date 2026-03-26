# -*- coding: utf-8 -*-
"""Perfetto 解析分析 — 插件注册入口。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin


class PerfettoAnalysisPlugin(BasePlugin):

    _service: Any = None

    @hookimpl
    def get_plugin_info(self) -> dict:
        return {
            "name": "perfetto_analysis",
            "display_name": "Perfetto 解析分析",
            "version": "0.1.0",
        }

    @hookimpl
    def register_cli_commands(self, cli_app) -> None:
        from .cli_commands import analysis_app

        analysis_app._pa_context = self.context
        cli_app.add_typer(analysis_app, name="analysis")

    @hookimpl
    def register_gui_tab(self):
        from .gui_tab import PerfettoAnalysisTab

        return PerfettoAnalysisTab(context=self.context)

    @hookimpl
    def register_agent_tools(self) -> list:
        if not self._service:
            return []
        return [
            {
                "name": "pa_analyze",
                "description": "完整分析 Perfetto trace 文件（丢帧检测 + 全维度分析 + 导出报告）。返回分析摘要和报告路径。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {"type": "string", "description": "Perfetto trace 文件路径（.perfetto-trace）"},
                        "process_name": {"type": "string", "description": "目标进程名（留空则自动检测）"},
                    },
                    "required": ["trace_path"],
                },
                "method": self._service.analyze,
            },
            {
                "name": "pa_parse",
                "description": "仅解析 Perfetto trace（Phase 1 丢帧定位），不进行维度分析。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {"type": "string", "description": "Perfetto trace 文件路径"},
                        "process_name": {"type": "string", "description": "目标进程名（留空则自动检测）"},
                    },
                    "required": ["trace_path"],
                },
                "method": self._service.parse_only,
            },
            {
                "name": "pa_analyze_dims",
                "description": "按指定维度分析 Perfetto trace（如 cpu_freq, binder, sched 等）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {"type": "string", "description": "Perfetto trace 文件路径"},
                        "process_name": {"type": "string", "description": "目标进程名（留空则自动检测）"},
                        "dimensions": {"type": "array", "items": {"type": "string"}, "description": "要分析的维度列表（留空则全部）"},
                    },
                    "required": ["trace_path"],
                },
                "method": self._service.analyze_dimensions,
            },
            {
                "name": "pa_list_dims",
                "description": "列出所有可用的 Perfetto 分析维度及其说明。",
                "parameters": {"type": "object", "properties": {}},
                "method": self._service.list_dimensions,
            },
            {
                "name": "pa_history",
                "description": "查询 Perfetto 分析历史记录，返回已完成分析的列表。",
                "parameters": {"type": "object", "properties": {}},
                "method": self._service.get_analysis_history,
            },
        ]

    @hookimpl
    def on_startup(self, context: dict) -> None:
        self.context = context

        from .service import PerfettoAnalysisService

        data_dir = Path(__file__).resolve().parent.parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        adb = context.get("adb")
        db_manager = context.get("db_manager")
        root_dir = context.get("root_dir")

        self._service = PerfettoAnalysisService(
            data_dir=data_dir,
            db_manager=db_manager,
            root_dir=root_dir,
        )

        context["pa_service"] = self._service
        context["pa_adb"] = adb
        context["pa_data_dir"] = str(data_dir)

        self._event_bus = context.get("event_bus")
        if self._event_bus:
            self._event_bus.on(
                "perfetto_capture.trace_ready", self._on_trace_ready,
            )

        if not self._service.perfetto_available:
            import sys
            print(
                "[perfetto_analysis] 警告: perfetto 包未安装, "
                "请执行: pip install perfetto>=0.16.0",
                file=sys.stderr,
            )

    @hookimpl
    def on_shutdown(self) -> None:
        if self._event_bus:
            self._event_bus.off(
                "perfetto_capture.trace_ready", self._on_trace_ready,
            )

    def _on_trace_ready(self, trace_path: str = "", **kwargs: Any) -> None:
        """响应 perfetto_capture.trace_ready 事件（配置开关控制）。"""
        if not self._service or not trace_path:
            return
        cfg = self._service.get_config()
        if not cfg.auto_analyze_on_capture:
            return

        import logging
        logger = logging.getLogger(__name__)
        logger.info("收到 trace_ready 事件, 自动分析: %s", trace_path)

        try:
            self._service.analyze(trace_path, on_progress=lambda msg: logger.info(msg))
            if self._event_bus:
                self._event_bus.emit(
                    "perfetto_analysis.analysis_complete",
                    trace_path=trace_path,
                )
        except Exception:
            logger.exception("自动分析失败: %s", trace_path)
