# -*- coding: utf-8 -*-
"""ResultCompressor 单元测试。"""
from __future__ import annotations

import pytest

from modules.perfetto_analysis.src.result_compressor import ResultCompressor
from modules.perfetto_analysis.src.models import (
    DimensionResult,
    TraceOverview,
    CompressedSummary,
)


def _jank_n(n: int, jank_num: int = 1) -> list[dict]:
    return [{"jank_num": jank_num} for _ in range(n)]


@pytest.fixture
def overview():
    return TraceOverview(
        file="test.trace",
        duration_s=10.0,
        processes=["com.test.app"],
        frame_count=600,
        refresh_rate_hz=60.0,
    )


@pytest.fixture
def dimension_results():
    return [
        DimensionResult(dimension="cpu", source="engine", data={"issues": []}),
        DimensionResult(
            dimension="thread",
            source="mcp",
            data={"issues": [{"description": "线程竞争", "severity": "HIGH"}]},
        ),
        DimensionResult(
            dimension="binder",
            source="degraded",
            data={"issues": [{"description": "慢 Binder", "severity": "MEDIUM"}]},
        ),
        DimensionResult(
            dimension="hotspot",
            source="unavailable",
            error="MCP 不可用",
        ),
    ]


def test_severity_critical(overview):
    c = ResultCompressor()
    s = c.compress(overview, [], jank_frames=_jank_n(10))
    assert s.severity == "CRITICAL"


def test_severity_high(overview):
    c = ResultCompressor()
    s = c.compress(overview, [], jank_frames=_jank_n(5))
    assert s.severity == "HIGH"


def test_severity_medium(overview):
    c = ResultCompressor()
    s = c.compress(overview, [], jank_frames=_jank_n(2))
    assert s.severity == "MEDIUM"


def test_severity_low(overview):
    c = ResultCompressor()
    s = c.compress(overview, [], jank_frames=_jank_n(1))
    assert s.severity == "LOW"


def test_severity_by_max_jank_num(overview):
    c = ResultCompressor()
    s = c.compress(overview, [], jank_frames=[{"jank_num": 20}])
    assert s.severity == "CRITICAL"


def test_root_cause_extraction(overview, dimension_results):
    c = ResultCompressor()
    s = c.compress(overview, dimension_results, jank_frames=None)
    texts = {rc.cause for rc in s.root_causes}
    assert "线程竞争" in texts
    assert "慢 Binder" in texts


def test_root_cause_ranking(overview):
    c = ResultCompressor(top_n=10)
    results = [
        DimensionResult(
            dimension="cpu",
            source="engine",
            data={
                "issues": [
                    {"description": "low", "severity": "LOW"},
                    {"description": "crit", "severity": "CRITICAL"},
                ]
            },
        ),
    ]
    s = c.compress(overview, results, [])
    assert [rc.cause for rc in s.root_causes] == ["crit", "low"]


def test_root_cause_top_n(overview):
    c = ResultCompressor(top_n=2)
    results = [
        DimensionResult(
            dimension="cpu",
            source="engine",
            data={
                "issues": [
                    {"description": "M", "severity": "MEDIUM"},
                    {"description": "L", "severity": "LOW"},
                    {"description": "H", "severity": "HIGH"},
                ]
            },
        ),
    ]
    s = c.compress(overview, results, [])
    assert len(s.root_causes) == 2
    assert [rc.rank for rc in s.root_causes] == [1, 2]
    assert s.root_causes[0].cause == "H"
    assert s.root_causes[1].cause == "M"


def test_health_summary_ok(overview):
    c = ResultCompressor()
    results = [
        DimensionResult(dimension="cpu", source="engine", data={"issues": []}),
    ]
    s = c.compress(overview, results, [])
    assert s.health_summary["cpu"].status == "OK"


def test_health_summary_warning(overview):
    c = ResultCompressor()
    results = [
        DimensionResult(
            dimension="thread",
            source="mcp",
            data={"issues": [{"description": "a", "severity": "LOW"}]},
        ),
        DimensionResult(
            dimension="many",
            source="engine",
            data={
                "issues": [
                    {"description": "1", "severity": "LOW"},
                    {"description": "2", "severity": "LOW"},
                    {"description": "3", "severity": "LOW"},
                ]
            },
        ),
    ]
    s = c.compress(overview, results, [])
    assert s.health_summary["thread"].status == "WARNING"
    assert s.health_summary["many"].status == "CRITICAL"


def test_health_summary_unavailable(overview, dimension_results):
    c = ResultCompressor()
    s = c.compress(overview, dimension_results, [])
    assert s.health_summary["hotspot"].status == "UNAVAILABLE"


def test_data_completeness(overview, dimension_results):
    c = ResultCompressor()
    s = c.compress(overview, dimension_results, [])
    dc = s.data_completeness
    assert set(dc.mcp_source) == {"thread"}
    assert set(dc.engine_source) == {"cpu", "binder"}
    assert dc.degraded_dimensions == ["binder"]


def test_compress_empty_results(overview):
    c = ResultCompressor()
    s = c.compress(overview, [], [])
    assert isinstance(s, CompressedSummary)
    assert s.root_causes == []
    assert s.severity == "LOW"


def test_trace_info_extraction(overview, dimension_results):
    c = ResultCompressor()
    s = c.compress(overview, dimension_results, _jank_n(3))
    ti = s.trace_info
    assert ti.file == "test.trace"
    assert ti.process == "com.test.app"
    assert ti.duration_s == 10.0
    assert ti.refresh_rate_hz == 60.0
    assert ti.frame_count == 600
    assert ti.jank_count == 3


def test_avg_fps_calculation(overview):
    c = ResultCompressor()
    s = c.compress(overview, [], [])
    assert s.trace_info.avg_fps == 60.0
