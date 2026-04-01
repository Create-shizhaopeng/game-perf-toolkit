# -*- coding: utf-8 -*-
"""Perfetto 分析原子工具集。

暴露独立可调用的原子分析工具，每个工具支持 MCP/引擎路由和可选 time_range。
Agent 可按需组合调用这些工具，而非依赖固定流水线。
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from .analysis_mode import FeatureFlagManager, get_route
from .mcp_client import McpAnalysisClient
from .models import (
    AnalysisChainResult,
    AnalysisChainStep,
    AnalysisConfig,
    AnalysisMode,
    CpuCoreEntry,
    CpuFreqAnalysis,
    DimensionResult,
    ThreadStateEntry,
    ThreadStateSummary,
    TraceOverview,
)

logger = logging.getLogger(__name__)

_MS_TO_NS = 1_000_000


class AnalysisToolkit:
    """原子分析工具集，统一处理 MCP/引擎路由。"""

    def __init__(
        self,
        config: AnalysisConfig,
        mcp_client: McpAnalysisClient | None = None,
        flag_manager: FeatureFlagManager | None = None,
    ) -> None:
        self._cfg = config
        self._mcp = mcp_client or McpAnalysisClient(
            timeout_ms=config.mcp_timeout_ms,
        )
        self._flags = flag_manager or FeatureFlagManager(config)
        self._chain_steps: list[AnalysisChainStep] = []

    def _record_step(
        self,
        tool_name: str,
        input_params: dict[str, Any],
        output_summary: str,
        duration_ms: float,
        source: str = "",
    ) -> None:
        """记录分析链路步骤。"""
        self._chain_steps.append(AnalysisChainStep(
            tool_name=tool_name,
            input_params=input_params,
            output_summary=output_summary,
            duration_ms=duration_ms,
            source=source,
        ))

    def get_chain_result(self, conclusion: str = "", confidence: float = 1.0) -> AnalysisChainResult:
        """返回当前分析会话的完整链路结果。"""
        return AnalysisChainResult(
            steps=list(self._chain_steps),
            conclusion=conclusion,
            confidence=confidence,
        )

    def reset_chain(self) -> None:
        """重置分析链路。"""
        self._chain_steps.clear()

    # ------------------------------------------------------------------
    # 原子工具：Trace 元数据
    # ------------------------------------------------------------------

    def get_trace_overview(
        self,
        trace_path: str | Path,
        process: str | None = None,
    ) -> TraceOverview:
        """获取 trace 元数据概览。"""
        t0 = time.perf_counter()
        trace_path = str(Path(trace_path).resolve())

        from .engine import parser

        parse_result, tp = parser.parse_trace_with_tp(
            trace_path,
            self._cfg.refresh_rate_preset,
            process_filter=process or None,
        )

        processes: list[str] = []
        try:
            rows = list(tp.query(
                "SELECT DISTINCT name FROM process WHERE name IS NOT NULL AND name != ''"
            ))
            processes = sorted({str(r.name) for r in rows if r.name})
        except Exception:
            logger.warning("无法从 trace 中查询进程列表")

        start_ns = parse_result.get("trace_start_ns") or 0
        end_ns = parse_result.get("trace_end_ns") or 0
        duration_s = (end_ns - start_ns) / 1e9 if end_ns > start_ns else 0.0

        overview = TraceOverview(
            file=trace_path,
            duration_s=round(duration_s, 3),
            processes=processes,
            frame_count=parse_result.get("frame_num", 0),
            refresh_rate_hz=parse_result.get("inferred_refresh_rate_hz", 60.0),
            scenario_phases=[],
        )

        self._safe_close_tp(tp)
        self._record_step(
            "get_trace_overview",
            {"trace_path": trace_path, "process": process},
            f"duration={overview.duration_s}s, frames={overview.frame_count}, processes={len(overview.processes)}",
            _elapsed_ms(t0),
            source="engine",
        )
        return overview

    # ------------------------------------------------------------------
    # 原子工具：卡顿帧检测
    # ------------------------------------------------------------------

    def detect_jank_frames(
        self,
        trace_path: str | Path,
        process: str,
        time_range: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """检测卡顿帧，返回帧列表（含时间窗口信息）。

        time_range 格式: {"start_ms": float, "end_ms": float}
        当多个 jank 帧时间窗口重叠时合并为一个窗口。
        """
        t0 = time.perf_counter()
        trace_path = str(Path(trace_path).resolve())

        from .engine import parser

        parse_result = parser.parse_trace(
            trace_path,
            self._cfg.refresh_rate_preset,
            process_filter=process or None,
        )

        jank_records = parse_result.get("jank_records", [])
        stand_vsync_ms = parse_result.get("stand_vsync_ms", 16.67)
        stand_vsync_ns = int(stand_vsync_ms * 1e6)

        frames: list[dict[str, Any]] = []
        for i, jank in enumerate(jank_records):
            ajt1 = jank.get("ajt1_ns", 0)
            ajt2 = jank.get("ajt2_ns", 0)
            sjt1 = jank.get("sjt1_ns", 0)
            sjt2 = jank.get("sjt2_ns", 0)

            window_start = max(0, ajt1 - 2 * stand_vsync_ns) if ajt1 else sjt1
            window_end = sjt2 + stand_vsync_ns if sjt2 else ajt2

            frames.append({
                "index": i,
                "jank_num": jank.get("jank_num", 0),
                "jank_type": jank.get("jank_type", ""),
                "window_start_ns": window_start,
                "window_end_ns": window_end,
                "window_start_ms": round(window_start / _MS_TO_NS, 3),
                "window_end_ms": round(window_end / _MS_TO_NS, 3),
            })

        if time_range:
            start_ns = int(time_range.get("start_ms", 0) * _MS_TO_NS)
            end_ns = int(time_range.get("end_ms", 0) * _MS_TO_NS)
            frames = [
                f for f in frames
                if f["window_end_ns"] > start_ns and f["window_start_ns"] < end_ns
            ]

        frames = self._merge_overlapping_frames(frames)
        self._record_step(
            "detect_jank_frames",
            {"trace_path": trace_path, "process": process, "time_range": time_range},
            f"检测到 {len(frames)} 个卡顿帧",
            _elapsed_ms(t0),
            source="engine",
        )
        return frames

    # ------------------------------------------------------------------
    # 原子工具：单维度分析
    # ------------------------------------------------------------------

    def analyze_dimension(
        self,
        trace_path: str | Path,
        process: str,
        dimension: str,
        time_range: dict[str, float] | None = None,
    ) -> DimensionResult:
        """对指定维度执行分析（MCP/引擎路由）。

        time_range 格式: {"start_ms": float, "end_ms": float}
        超出 trace 时间范围时返回错误。
        """
        trace_path = str(Path(trace_path).resolve())
        t0 = time.perf_counter()

        mode = self._flags.get_mode_for_dimension(dimension)

        if mode == AnalysisMode.ENGINE_ONLY:
            result = self._engine_analyze(trace_path, process, dimension, time_range)
        elif mode == AnalysisMode.MCP_ONLY:
            mcp_data = self._mcp_analyze(trace_path, process, dimension, time_range)
            if mcp_data is not None:
                result = DimensionResult(
                    dimension=dimension,
                    source="mcp",
                    data=mcp_data,
                    duration_ms=_elapsed_ms(t0),
                )
            else:
                result = DimensionResult(
                    dimension=dimension,
                    source="unavailable",
                    error="MCP 工具未返回数据",
                    duration_ms=_elapsed_ms(t0),
                )
        else:  # mcp_preferred
            mcp_data = self._mcp_analyze(trace_path, process, dimension, time_range)
            if mcp_data is not None:
                result = DimensionResult(
                    dimension=dimension,
                    source="mcp",
                    data=mcp_data,
                    duration_ms=_elapsed_ms(t0),
                )
            else:
                result = self._engine_analyze(
                    trace_path, process, dimension, time_range,
                )
                if result.source == "engine":
                    result.source = "degraded"

        result.duration_ms = _elapsed_ms(t0)
        self._record_step(
            "analyze_dimension",
            {"trace_path": trace_path, "process": process, "dimension": dimension, "time_range": time_range},
            f"source={result.source}, has_data={bool(result.data)}",
            result.duration_ms,
            source=result.source,
        )
        return result

    # ------------------------------------------------------------------
    # 原子工具：CPU 全局概览（MCP only）
    # ------------------------------------------------------------------

    def get_cpu_overview(
        self,
        trace_path: str | Path,
        process: str,
    ) -> dict[str, Any] | None:
        """调用 MCP cpu_utilization_profiler 返回全 trace CPU 概览。"""
        t0 = time.perf_counter()
        result = self._mcp.get_cpu_utilization(
            str(Path(trace_path).resolve()), process,
        )
        self._record_step(
            "get_cpu_overview",
            {"trace_path": str(trace_path), "process": process},
            f"has_data={result is not None}",
            _elapsed_ms(t0),
            source="mcp" if result else "unavailable",
        )
        return result

    # ------------------------------------------------------------------
    # 原子工具：主线程状态分布
    # ------------------------------------------------------------------

    def thread_state_summary(
        self,
        trace_path: str | Path,
        process: str,
        time_range: dict[str, float] | None = None,
        compact: bool = False,
    ) -> ThreadStateSummary | dict[str, Any]:
        """查询主线程各状态（Running/S/R/D/R+）的耗时和占比。"""
        t0 = time.perf_counter()
        trace_path_str = str(Path(trace_path).resolve())

        time_filter = ""
        if time_range:
            start_ns = int(time_range["start_ms"] * _MS_TO_NS)
            end_ns = int(time_range["end_ms"] * _MS_TO_NS)
            time_filter = f"AND ts.ts >= {start_ns} AND ts.ts + ts.dur <= {end_ns}"

        sql = f"""
        SELECT
          ts.state,
          SUM(ts.dur) as total_dur,
          COUNT(*) as cnt
        FROM thread_state ts
        JOIN thread t ON ts.utid = t.utid
        JOIN process p ON t.upid = p.upid
        WHERE p.name LIKE '%{process}%' AND t.is_main_thread = 1
          AND ts.dur > 0
          {time_filter}
        GROUP BY ts.state
        ORDER BY total_dur DESC
        """

        result = self._mcp.execute_sql(trace_path_str, sql)
        states: list[ThreadStateEntry] = []
        total_ns = 0

        if result and result.get("rows"):
            for row in result["rows"]:
                dur_ns = row.get("total_dur", 0)
                total_ns += dur_ns
                states.append(ThreadStateEntry(
                    state=row.get("state", ""),
                    duration_ms=round(dur_ns / _MS_TO_NS, 3),
                    count=row.get("cnt", 0),
                ))

        if total_ns > 0:
            for s in states:
                s.percentage = round(s.duration_ms / (total_ns / _MS_TO_NS) * 100, 1)

        dominant = states[0].state if states else ""
        summary = ThreadStateSummary(
            process=process,
            total_duration_ms=round(total_ns / _MS_TO_NS, 3),
            states=states,
            dominant_state=dominant,
            time_range=time_range,
        )

        self._record_step(
            "thread_state_summary",
            {"trace_path": trace_path_str, "process": process, "time_range": time_range},
            f"states={len(states)}, dominant={dominant}",
            _elapsed_ms(t0),
            source="mcp",
        )
        return summary.to_compact_dict() if compact else summary

    # ------------------------------------------------------------------
    # 原子工具：CPU 核心与频率分析
    # ------------------------------------------------------------------

    def cpu_freq_analysis(
        self,
        trace_path: str | Path,
        process: str,
        time_range: dict[str, float] | None = None,
        compact: bool = False,
    ) -> CpuFreqAnalysis | dict[str, Any]:
        """查询主线程运行的 CPU 核心分布和各核心频率统计。"""
        t0 = time.perf_counter()
        trace_path_str = str(Path(trace_path).resolve())

        time_filter = ""
        if time_range:
            start_ns = int(time_range["start_ms"] * _MS_TO_NS)
            end_ns = int(time_range["end_ms"] * _MS_TO_NS)
            time_filter = f"AND ts.ts >= {start_ns} AND ts.ts + ts.dur <= {end_ns}"

        core_sql = f"""
        SELECT
          ts.cpu,
          COUNT(*) as running_segments,
          SUM(ts.dur) as total_running_ns
        FROM thread_state ts
        JOIN thread t ON ts.utid = t.utid
        JOIN process p ON t.upid = p.upid
        WHERE p.name LIKE '%{process}%' AND t.is_main_thread = 1
          AND ts.state = 'Running'
          {time_filter}
        GROUP BY ts.cpu
        ORDER BY total_running_ns DESC
        """

        core_result = self._mcp.execute_sql(trace_path_str, core_sql)
        cores: list[CpuCoreEntry] = []
        total_running_ns = 0

        if core_result and core_result.get("rows"):
            for row in core_result["rows"]:
                running_ns = row.get("total_running_ns", 0)
                total_running_ns += running_ns
                cores.append(CpuCoreEntry(
                    cpu_id=row.get("cpu", -1),
                    running_ms=round(running_ns / _MS_TO_NS, 3),
                    segment_count=row.get("running_segments", 0),
                ))

        if total_running_ns > 0:
            for c in cores:
                c.running_percentage = round(
                    c.running_ms / (total_running_ns / _MS_TO_NS) * 100, 1,
                )

        for core in cores:
            freq_sql = f"""
            SELECT
              MIN(c.value) as freq_min,
              MAX(c.value) as freq_max,
              CAST(AVG(c.value) AS INT) as freq_avg
            FROM counter c
            JOIN cpu_counter_track ct ON c.track_id = ct.id
            WHERE ct.name = 'cpufreq' AND ct.cpu = {core.cpu_id}
            """
            if time_range:
                start_ns = int(time_range["start_ms"] * _MS_TO_NS)
                end_ns = int(time_range["end_ms"] * _MS_TO_NS)
                freq_sql += f" AND c.ts >= {start_ns} AND c.ts <= {end_ns}"

            freq_result = self._mcp.execute_sql(trace_path_str, freq_sql)
            if freq_result and freq_result.get("rows"):
                row = freq_result["rows"][0]
                core.freq_min_khz = row.get("freq_min", 0) or 0
                core.freq_max_khz = row.get("freq_max", 0) or 0
                core.freq_avg_khz = row.get("freq_avg", 0) or 0

        primary = cores[0].cpu_id if cores else -1
        analysis = CpuFreqAnalysis(
            process=process,
            total_running_ms=round(total_running_ns / _MS_TO_NS, 3),
            cores=cores,
            primary_core=primary,
            time_range=time_range,
        )

        self._record_step(
            "cpu_freq_analysis",
            {"trace_path": trace_path_str, "process": process, "time_range": time_range},
            f"cores={len(cores)}, primary=cpu{primary}",
            _elapsed_ms(t0),
            source="mcp",
        )
        return analysis.to_compact_dict() if compact else analysis

    # ------------------------------------------------------------------
    # 原子工具：灵活查询（MCP 透传）
    # ------------------------------------------------------------------

    def find_slices(
        self,
        trace_path: str | Path,
        pattern: str,
        process: str | None = None,
        compact: bool = False,
    ) -> dict[str, Any] | None:
        """按名称模式搜索 slice。"""
        result = self._mcp.find_slices(
            str(Path(trace_path).resolve()), pattern, process,
        )
        if compact and result and "rows" in result:
            return _compact_rows(result)
        return result

    def execute_sql(
        self,
        trace_path: str | Path,
        sql: str,
        compact: bool = False,
    ) -> dict[str, Any] | None:
        """执行任意 Perfetto SQL 查询。"""
        result = self._mcp.execute_sql(
            str(Path(trace_path).resolve()), sql,
        )
        if compact and result and "rows" in result:
            return _compact_rows(result)
        return result

    # ------------------------------------------------------------------
    # 原子工具：多场景分析
    # ------------------------------------------------------------------

    def analyze_anr(
        self,
        trace_path: str | Path,
        process: str,
    ) -> dict[str, Any]:
        """ANR 检测与根因分析。"""
        t0 = time.perf_counter()
        trace_path = str(Path(trace_path).resolve())

        anr_detected = self._mcp.detect_anrs(trace_path, process)
        root_cause = None
        if anr_detected:
            root_cause = self._mcp.analyze_anr_root_cause(trace_path, process)

        result = {
            "anr_detected": anr_detected,
            "root_cause": root_cause,
            "available": anr_detected is not None,
        }
        self._record_step(
            "analyze_anr",
            {"trace_path": trace_path, "process": process},
            f"anr_detected={anr_detected is not None}",
            _elapsed_ms(t0),
            source="mcp",
        )
        return result

    def analyze_memory(
        self,
        trace_path: str | Path,
        process: str,
    ) -> dict[str, Any]:
        """内存泄漏检测与堆分析。"""
        t0 = time.perf_counter()
        trace_path = str(Path(trace_path).resolve())

        leaks = self._mcp.detect_memory_leaks(trace_path, process)
        dominator = None
        if leaks:
            dominator = self._mcp.analyze_heap_dominator(trace_path, process)

        result = {
            "memory_leaks": leaks,
            "heap_dominator": dominator,
            "available": leaks is not None,
        }
        self._record_step(
            "analyze_memory",
            {"trace_path": trace_path, "process": process},
            f"leaks_detected={leaks is not None}",
            _elapsed_ms(t0),
            source="mcp",
        )
        return result

    def check_scenario_availability(
        self,
        trace_path: str | Path,
        scenario: str,
    ) -> dict[str, Any]:
        """检查分析场景在当前 trace 中是否可用。"""
        from .models import AnalysisScenario

        scenarios = {
            "jank": AnalysisScenario(
                name="jank",
                description="卡顿分析",
                mcp_tools=["thread_contention_analyzer", "binder_transaction_profiler"],
                engine_dimensions=["cpu", "thread", "binder", "gpu", "sf"],
                required_trace_data=["vsync_cycles", "jank_records"],
            ),
            "anr": AnalysisScenario(
                name="anr",
                description="ANR 分析",
                mcp_tools=["detect_anrs", "anr_root_cause_analyzer"],
                engine_dimensions=[],
                required_trace_data=[],
            ),
            "memory": AnalysisScenario(
                name="memory",
                description="内存分析",
                mcp_tools=["memory_leak_detector", "heap_dominator_tree_analyzer"],
                engine_dimensions=[],
                required_trace_data=[],
            ),
        }

        sc = scenarios.get(scenario)
        if sc is None:
            return {"available": False, "reason": f"未知场景: {scenario}"}

        if scenario == "jank":
            overview = self.get_trace_overview(trace_path)
            if overview.frame_count == 0:
                return {"available": False, "reason": "trace 中未检测到帧数据"}
            return {"available": True, "scenario": sc.name, "description": sc.description}

        return {"available": True, "scenario": sc.name, "description": sc.description}

    # ------------------------------------------------------------------
    # 内部方法：MCP 通道
    # ------------------------------------------------------------------

    def _mcp_analyze(
        self,
        trace_path: str,
        process: str,
        dimension: str,
        time_range: dict[str, float] | None,
    ) -> dict[str, Any] | None:
        """通过 MCP 执行维度分析。"""
        route = get_route(dimension)
        if route is None or route.mcp_tool is None:
            return None

        mcp_time_range = None
        if time_range and route.supports_time_range:
            mcp_time_range = {
                "start_ms": time_range["start_ms"],
                "end_ms": time_range["end_ms"],
            }

        tool_map = {
            "thread_contention_analyzer": self._mcp.analyze_thread_contention,
            "binder_transaction_profiler": self._mcp.analyze_binder,
            "main_thread_hotspot_slices": self._mcp.get_main_thread_hotspots,
            "cpu_utilization_profiler": self._mcp.get_cpu_utilization,
        }

        method = tool_map.get(route.mcp_tool)
        if method is None:
            return None

        if route.mcp_tool == "cpu_utilization_profiler":
            return method(trace_path, process)
        return method(trace_path, process, mcp_time_range)

    # ------------------------------------------------------------------
    # 内部方法：引擎通道
    # ------------------------------------------------------------------

    def _engine_analyze(
        self,
        trace_path: str,
        process: str,
        dimension: str,
        time_range: dict[str, float] | None,
    ) -> DimensionResult:
        """通过引擎执行维度分析。"""
        from .engine import parser, analyzer, app_type as app_type_mod
        from .engine import cpu_topology as cpu_topo_mod

        try:
            parse_result, tp = parser.parse_trace_with_tp(
                trace_path,
                self._cfg.refresh_rate_preset,
                process_filter=process or None,
            )

            if time_range:
                tr_start = parse_result.get("trace_start_ns") or 0
                tr_end = parse_result.get("trace_end_ns") or 0
                req_start_ns = int(time_range["start_ms"] * _MS_TO_NS)
                req_end_ns = int(time_range["end_ms"] * _MS_TO_NS)
                if tr_end > 0 and (req_start_ns > tr_end or req_end_ns < tr_start):
                    self._safe_close_tp(tp)
                    return DimensionResult(
                        dimension=dimension,
                        source="unavailable",
                        error=(
                            f"time_range [{time_range['start_ms']}ms, {time_range['end_ms']}ms] "
                            f"超出 trace 范围 [{tr_start / _MS_TO_NS:.1f}ms, {tr_end / _MS_TO_NS:.1f}ms]"
                        ),
                    )

            if dimension == "summary":
                analysis = analyzer.analyze_jank(
                    tp, parse_result,
                    process_name=process or None,
                    app_type_override=self._cfg.app_type,
                    dimensions=["summary"],
                )
                self._safe_close_tp(tp)
                return DimensionResult(
                    dimension=dimension,
                    source="engine",
                    data=analysis.get("summary_analysis", {}),
                )

            if time_range:
                window_start_ns = int(time_range["start_ms"] * _MS_TO_NS)
                window_end_ns = int(time_range["end_ms"] * _MS_TO_NS)
                data = self._engine_analyze_window(
                    tp, parse_result, process, dimension,
                    window_start_ns, window_end_ns,
                )
            else:
                analysis = analyzer.analyze_jank(
                    tp, parse_result,
                    process_name=process or None,
                    app_type_override=self._cfg.app_type,
                    analyze_top=self._cfg.analyze_top,
                    slow_binder_ms=self._cfg.slow_binder_threshold_ms,
                    sched_latency_ms=self._cfg.sched_latency_threshold_ms,
                    dimensions=[dimension],
                )
                per_jank = analysis.get("per_jank_analyses", [])
                data = {
                    "per_jank_count": len(per_jank),
                    "per_jank_results": [
                        j.get(dimension, {}) for j in per_jank if dimension in j
                    ],
                }

            self._safe_close_tp(tp)
            return DimensionResult(
                dimension=dimension,
                source="engine",
                data=data,
            )

        except Exception as e:
            logger.error("引擎分析维度 %s 失败: %s", dimension, e)
            return DimensionResult(
                dimension=dimension,
                source="unavailable",
                error=str(e),
            )

    def _engine_analyze_window(
        self,
        tp: Any,
        parse_result: dict[str, Any],
        process: str,
        dimension: str,
        window_start_ns: int,
        window_end_ns: int,
    ) -> dict[str, Any]:
        """引擎对指定时间窗口的单维度分析。"""
        from .engine import app_type as app_type_mod
        from .engine import cpu_topology as cpu_topo_mod
        from .engine.analyzer import _DIMENSION_ANALYZERS, _register_builtin_dimensions

        if not _DIMENSION_ANALYZERS:
            _register_builtin_dimensions()

        analyzer_fn = _DIMENSION_ANALYZERS.get(dimension)
        if analyzer_fn is None:
            return {"error": f"未注册的引擎维度: {dimension}"}

        upid = None
        if process:
            upid = app_type_mod.find_target_upid(tp, process)

        target_utids: list[int] = []
        if upid is not None:
            try:
                rows = list(tp.query(
                    f"SELECT utid FROM thread WHERE upid = {upid}"
                ))
                target_utids = [int(r.utid) for r in rows]
            except Exception:
                pass

        topology = cpu_topo_mod.init_cpu_topology(tp)

        try:
            return analyzer_fn(
                tp=tp,
                window_start_ns=window_start_ns,
                window_end_ns=window_end_ns,
                target_utids=target_utids,
                topology=topology,
                upid=upid,
                slow_binder_ms=self._cfg.slow_binder_threshold_ms,
                sched_latency_ms=self._cfg.sched_latency_threshold_ms,
            )
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_overlapping_frames(
        frames: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """合并重叠的 jank 帧时间窗口。"""
        if len(frames) <= 1:
            return frames

        sorted_frames = sorted(frames, key=lambda f: f["window_start_ns"])
        merged: list[dict[str, Any]] = [sorted_frames[0].copy()]

        for frame in sorted_frames[1:]:
            last = merged[-1]
            if frame["window_start_ns"] <= last["window_end_ns"]:
                last["window_end_ns"] = max(
                    last["window_end_ns"], frame["window_end_ns"],
                )
                last["window_end_ms"] = round(
                    last["window_end_ns"] / _MS_TO_NS, 3,
                )
                last["jank_num"] = last.get("jank_num", 0) + frame.get("jank_num", 0)
            else:
                merged.append(frame.copy())

        return merged

    @staticmethod
    def _safe_close_tp(tp: Any) -> None:
        """安全关闭 TraceProcessor。"""
        if tp is None:
            return
        try:
            if hasattr(tp, "close"):
                tp.close()
        except Exception:
            pass


def _elapsed_ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 2)


_COMPACT_SAMPLE_SIZE = 5


def _compact_rows(result: dict[str, Any]) -> dict[str, Any]:
    """将含 rows 的 MCP 结果压缩为 total_rows + 前 N 条样本。"""
    rows = result.get("rows", [])
    return {
        "total_rows": len(rows),
        "sample_count": min(_COMPACT_SAMPLE_SIZE, len(rows)),
        "sample": rows[:_COMPACT_SAMPLE_SIZE],
        "columns": result.get("columns", []),
    }
