# -*- coding: utf-8 -*-
"""Perfetto 解析分析 — 插件注册入口。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin


class PerfettoAnalysisPlugin(BasePlugin):

    _service: Any = None

    def _pa_trace_overview(
        self,
        trace_path: str,
        process_name: str | None = None,
    ) -> Any:
        return self._service.get_trace_overview(trace_path, process_name)

    def _pa_detect_jank(
        self,
        trace_path: str,
        process_name: str = "",
        time_range: dict | None = None,
    ) -> Any:
        return self._service.detect_jank_frames(
            trace_path, process_name, time_range,
        )

    def _pa_analyze_dimension(
        self,
        trace_path: str,
        dimension: str,
        process_name: str = "",
        time_range: dict | None = None,
    ) -> Any:
        return self._service.analyze_dimension(
            trace_path, process_name, dimension, time_range,
        )

    def _pa_cpu_overview(self, trace_path: str, process_name: str = "") -> Any:
        return self._service.get_cpu_overview(trace_path, process_name)

    def _pa_find_slices(
        self,
        trace_path: str,
        pattern: str,
        process_name: str | None = None,
    ) -> Any:
        return self._service.find_slices_tool(
            trace_path, pattern, process_name,
        )

    def _pa_thread_state_summary(
        self,
        trace_path: str,
        process_name: str = "",
        time_range: dict | None = None,
        compact: bool = False,
    ) -> Any:
        return self._service.thread_state_summary(
            trace_path, process_name, time_range, compact,
        )

    def _pa_cpu_freq_analysis(
        self,
        trace_path: str,
        process_name: str = "",
        time_range: dict | None = None,
        compact: bool = False,
    ) -> Any:
        return self._service.cpu_freq_analysis(
            trace_path, process_name, time_range, compact,
        )

    def _pa_analyze_anr(self, trace_path: str, process_name: str = "") -> dict:
        return self._service.analyze_anr(trace_path, process_name)

    def _pa_analyze_memory(self, trace_path: str, process_name: str = "") -> dict:
        return self._service.analyze_memory(trace_path, process_name)

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
        return None

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
                "name": "pa_trace_overview",
                "description": "获取 Perfetto trace 元数据概览。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {"type": "string", "description": "Perfetto trace 文件路径"},
                        "process_name": {"type": "string", "description": "目标进程名（可选）"},
                    },
                    "required": ["trace_path"],
                },
                "method": self._pa_trace_overview,
            },
            {
                "name": "pa_detect_jank",
                "description": "检测卡顿帧，可选时间范围过滤。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {"type": "string", "description": "Perfetto trace 文件路径"},
                        "process_name": {"type": "string", "description": "目标进程名（可选）"},
                        "time_range": {
                            "type": "object",
                            "properties": {
                                "start_ms": {"type": "number"},
                                "end_ms": {"type": "number"},
                            },
                            "description": "可选时间范围（毫秒）",
                        },
                    },
                    "required": ["trace_path"],
                },
                "method": self._pa_detect_jank,
            },
            {
                "name": "pa_analyze_dimension",
                "description": "单维度分析（MCP/引擎路由）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {"type": "string", "description": "Perfetto trace 文件路径"},
                        "process_name": {"type": "string", "description": "目标进程名（可选）"},
                        "dimension": {
                            "type": "string",
                            "enum": [
                                "cpu", "thread", "binder", "hotspot", "io",
                                "gc", "gpu", "sf", "input", "lock", "summary",
                            ],
                            "description": "分析维度",
                        },
                        "time_range": {
                            "type": "object",
                            "properties": {
                                "start_ms": {"type": "number"},
                                "end_ms": {"type": "number"},
                            },
                            "description": "可选时间范围（毫秒）",
                        },
                    },
                    "required": ["trace_path", "dimension"],
                },
                "method": self._pa_analyze_dimension,
            },
            {
                "name": "pa_cpu_overview",
                "description": "获取全 trace CPU 全局概览。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {"type": "string", "description": "Perfetto trace 文件路径"},
                        "process_name": {"type": "string", "description": "目标进程名（可选）"},
                    },
                    "required": ["trace_path"],
                },
                "method": self._pa_cpu_overview,
            },
            {
                "name": "pa_find_slices",
                "description": "按名称模式搜索 slice。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {"type": "string", "description": "Perfetto trace 文件路径"},
                        "pattern": {"type": "string", "description": "名称匹配模式"},
                        "process_name": {"type": "string", "description": "目标进程名（可选）"},
                    },
                    "required": ["trace_path", "pattern"],
                },
                "method": self._pa_find_slices,
            },
            {
                "name": "pa_execute_sql",
                "description": "对 trace 执行任意 Perfetto SQL 查询。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {"type": "string", "description": "Perfetto trace 文件路径"},
                        "sql": {"type": "string", "description": "SQL 语句"},
                    },
                    "required": ["trace_path", "sql"],
                },
                "method": self._service.execute_sql_tool,
            },
            {
                "name": "pa_thread_state_summary",
                "description": "查询主线程各状态（Running/Sleeping/Runnable/D-State）的耗时和占比。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {"type": "string", "description": "Perfetto trace 文件路径"},
                        "process_name": {"type": "string", "description": "目标进程名"},
                        "time_range": {
                            "type": "object",
                            "properties": {
                                "start_ms": {"type": "number"},
                                "end_ms": {"type": "number"},
                            },
                            "description": "可选时间范围（毫秒）",
                        },
                        "compact": {"type": "boolean", "description": "compact 模式仅返回摘要", "default": False},
                    },
                    "required": ["trace_path"],
                },
                "method": self._pa_thread_state_summary,
            },
            {
                "name": "pa_cpu_freq_analysis",
                "description": "查询主线程运行的 CPU 核心分布和各核心频率统计（min/max/avg）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {"type": "string", "description": "Perfetto trace 文件路径"},
                        "process_name": {"type": "string", "description": "目标进程名"},
                        "time_range": {
                            "type": "object",
                            "properties": {
                                "start_ms": {"type": "number"},
                                "end_ms": {"type": "number"},
                            },
                            "description": "可选时间范围（毫秒）",
                        },
                        "compact": {"type": "boolean", "description": "compact 模式仅返回摘要", "default": False},
                    },
                    "required": ["trace_path"],
                },
                "method": self._pa_cpu_freq_analysis,
            },
            {
                "name": "pa_analyze_anr",
                "description": "检测 Perfetto trace 中的 ANR 事件并分析根因。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {"type": "string", "description": "Perfetto trace 文件路径"},
                        "process_name": {"type": "string", "description": "目标进程名"},
                    },
                    "required": ["trace_path"],
                },
                "method": self._pa_analyze_anr,
            },
            {
                "name": "pa_analyze_memory",
                "description": "检测 Perfetto trace 中的内存泄漏并分析堆支配树。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "trace_path": {"type": "string", "description": "Perfetto trace 文件路径"},
                        "process_name": {"type": "string", "description": "目标进程名"},
                    },
                    "required": ["trace_path"],
                },
                "method": self._pa_analyze_memory,
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

        llm_manager = context.get("llm_manager")
        if llm_manager:
            try:
                from .agent.orchestrator import AnalysisOrchestrator
                from .agent.package_db import PackageMappingDB

                package_db = PackageMappingDB(data_dir / "package_mappings.db")
                orchestrator = AnalysisOrchestrator(
                    llm_manager=llm_manager,
                    pa_service=self._service,
                    package_db=package_db,
                )
                context["pa_orchestrator"] = orchestrator
                context["pa_package_db"] = package_db
            except Exception as exc:
                import sys
                print(
                    f"[perfetto_analysis] AnalysisOrchestrator 初始化失败: {exc}",
                    file=sys.stderr,
                )

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
