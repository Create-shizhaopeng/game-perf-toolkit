# -*- coding: utf-8 -*-
"""Perfetto 分析模式 — Feature Flag 管理和维度级路由。"""
from __future__ import annotations

from dataclasses import dataclass

from .models import AnalysisConfig, AnalysisMode


def _parse_mode(value: str) -> AnalysisMode:
    """将配置中的模式字符串解析为枚举。"""
    return AnalysisMode(value)


@dataclass(frozen=True, slots=True)
class DimensionRoute:
    """单维度的 MCP 工具与默认分析策略。"""

    dimension: str
    mcp_tool: str | None
    supports_time_range: bool
    default_mode: AnalysisMode


DIMENSION_ROUTING: dict[str, DimensionRoute] = {
    "cpu": DimensionRoute(
        dimension="cpu",
        mcp_tool=None,
        supports_time_range=False,
        default_mode=AnalysisMode.ENGINE_ONLY,
    ),
    "thread": DimensionRoute(
        dimension="thread",
        mcp_tool="thread_contention_analyzer",
        supports_time_range=True,
        default_mode=AnalysisMode.MCP_PREFERRED,
    ),
    "binder": DimensionRoute(
        dimension="binder",
        mcp_tool="binder_transaction_profiler",
        supports_time_range=True,
        default_mode=AnalysisMode.MCP_PREFERRED,
    ),
    "hotspot": DimensionRoute(
        dimension="hotspot",
        mcp_tool="main_thread_hotspot_slices",
        supports_time_range=True,
        default_mode=AnalysisMode.MCP_ONLY,
    ),
    "io": DimensionRoute(
        dimension="io",
        mcp_tool=None,
        supports_time_range=False,
        default_mode=AnalysisMode.ENGINE_ONLY,
    ),
    "gc": DimensionRoute(
        dimension="gc",
        mcp_tool=None,
        supports_time_range=False,
        default_mode=AnalysisMode.ENGINE_ONLY,
    ),
    "gpu": DimensionRoute(
        dimension="gpu",
        mcp_tool=None,
        supports_time_range=False,
        default_mode=AnalysisMode.ENGINE_ONLY,
    ),
    "sf": DimensionRoute(
        dimension="sf",
        mcp_tool=None,
        supports_time_range=False,
        default_mode=AnalysisMode.ENGINE_ONLY,
    ),
    "input": DimensionRoute(
        dimension="input",
        mcp_tool=None,
        supports_time_range=False,
        default_mode=AnalysisMode.ENGINE_ONLY,
    ),
    "lock": DimensionRoute(
        dimension="lock",
        mcp_tool=None,
        supports_time_range=False,
        default_mode=AnalysisMode.ENGINE_ONLY,
    ),
    "summary": DimensionRoute(
        dimension="summary",
        mcp_tool=None,
        supports_time_range=False,
        default_mode=AnalysisMode.ENGINE_ONLY,
    ),
    "cpu_global": DimensionRoute(
        dimension="cpu_global",
        mcp_tool="cpu_utilization_profiler",
        supports_time_range=True,
        default_mode=AnalysisMode.MCP_ONLY,
    ),
}


def get_route(dimension: str) -> DimensionRoute | None:
    """返回指定维度的路由信息；未知维度返回 None。"""
    return DIMENSION_ROUTING.get(dimension)


class FeatureFlagManager:
    """基于 AnalysisConfig 的维度级分析模式解析。"""

    def __init__(self, config: AnalysisConfig) -> None:
        self._config = config

    def get_global_mode(self) -> AnalysisMode:
        """返回全局 analysis_mode。"""
        return _parse_mode(self._config.analysis_mode)

    def get_mcp_timeout_ms(self) -> int:
        """返回 MCP 调用超时（毫秒）。"""
        return self._config.mcp_timeout_ms

    def get_mode_for_dimension(self, dimension: str) -> AnalysisMode:
        """解析某维度最终使用的 AnalysisMode（覆盖 > 路由默认策略 > 全局）。"""
        overrides = self._config.dimension_overrides
        if dimension in overrides:
            return _parse_mode(overrides[dimension])

        route = DIMENSION_ROUTING.get(dimension)
        if route is None:
            return self.get_global_mode()

        if route.default_mode in (
            AnalysisMode.ENGINE_ONLY,
            AnalysisMode.MCP_ONLY,
        ):
            return route.default_mode

        return self.get_global_mode()
