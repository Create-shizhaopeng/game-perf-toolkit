# -*- coding: utf-8 -*-
"""输入事件延迟分析（FR-117）。"""
from __future__ import annotations

import sys
from typing import Any


def analyze_input(
    tp: Any,
    window_start_ns: int,
    window_end_ns: int,
    target_utids: list[int],
    upid: int | None = None,
) -> dict[str, Any]:
    """
    输入事件延迟分析。
    优先 INCLUDE PERFETTO MODULE android.input，降级到 slice 表查询。
    数据不存在时返回空结果（不报错）。
    """
    result: dict[str, Any] = {
        "input_events": [],
        "slow_input_count": 0,
        "input_stats": {},
    }

    events = _try_stdlib_input(tp, window_start_ns, window_end_ns, upid)
    if events is None:
        events = _fallback_slice_input(tp, window_start_ns, window_end_ns, target_utids)

    result["input_events"] = events
    result["slow_input_count"] = sum(1 for e in events if e.get("is_slow"))

    if events:
        latencies = [e.get("latency_ns", 0) for e in events if e.get("latency_ns")]
        if latencies:
            lat_sorted = sorted(latencies)
            n = len(lat_sorted)
            result["input_stats"] = {
                "count": n,
                "avg_ms": round(sum(latencies) / n / 1e6, 2),
                "p99_ms": round(lat_sorted[min(n * 99 // 100, n - 1)] / 1e6, 2),
                "max_ms": round(lat_sorted[-1] / 1e6, 2),
            }

    return result


def _try_stdlib_input(
    tp: Any,
    start_ns: int,
    end_ns: int,
    upid: int | None,
) -> list[dict[str, Any]] | None:
    """使用 Perfetto stdlib android.input 模块。"""
    try:
        tp.query("INCLUDE PERFETTO MODULE android.input")
    except Exception:
        return None

    try:
        rows = list(tp.query(f"""
            SELECT ts, dur, event_type
            FROM android_input_events
            WHERE ts >= {start_ns} AND ts <= {end_ns}
            ORDER BY ts
        """))
        events = []
        for row in rows:
            dur = int(row.dur) if row.dur else 0
            is_slow = dur > 16_000_000  # > 16ms
            events.append({
                "ts_ns": int(row.ts),
                "dur_ns": dur,
                "latency_ns": dur,
                "event_type": str(row.event_type) if hasattr(row, "event_type") and row.event_type else "",
                "is_slow": is_slow,
            })
        return events
    except Exception:
        return None


def _fallback_slice_input(
    tp: Any,
    start_ns: int,
    end_ns: int,
    utids: list[int],
) -> list[dict[str, Any]]:
    """降级方案：查 slice 表的 deliverInputEvent / input 相关 slice。"""
    if not utids:
        return []

    utid_list = ",".join(str(u) for u in utids)
    try:
        rows = list(tp.query(f"""
            SELECT s.ts, s.dur, s.name, t.name as thread_name
            FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE t.utid IN ({utid_list})
              AND (s.name GLOB '*deliverInputEvent*' OR s.name GLOB '*input*')
              AND s.ts >= {start_ns} AND s.ts <= {end_ns}
            ORDER BY s.ts
        """))
        events = []
        for row in rows:
            dur = int(row.dur) if row.dur else 0
            is_slow = dur > 16_000_000
            events.append({
                "ts_ns": int(row.ts),
                "dur_ns": dur,
                "latency_ns": dur,
                "name": str(row.name) if row.name else "",
                "is_slow": is_slow,
            })
        return events
    except Exception:
        return []
