# -*- coding: utf-8 -*-
"""Java Monitor 锁竞争分析（FR-118）。"""
from __future__ import annotations

import sys
from typing import Any

SEVERE_THRESHOLD_NS = 1_000_000  # 1ms


def analyze_lock(
    tp: Any,
    window_start_ns: int,
    window_end_ns: int,
    target_utids: list[int],
    upid: int | None = None,
) -> dict[str, Any]:
    """
    Java Monitor 锁竞争分析。
    优先 INCLUDE PERFETTO MODULE android.monitor_contention，降级到 slice 表。
    数据不存在时返回空结果（不报错）。
    """
    result: dict[str, Any] = {
        "contentions": [],
        "contention_count": 0,
        "severe_count": 0,
        "total_wait_ns": 0,
    }

    contentions = _try_stdlib_monitor(tp, window_start_ns, window_end_ns, target_utids)
    if contentions is None:
        contentions = _fallback_slice_monitor(tp, window_start_ns, window_end_ns, target_utids)

    result["contentions"] = contentions
    result["contention_count"] = len(contentions)
    result["severe_count"] = sum(1 for c in contentions if c.get("dur_ns", 0) > SEVERE_THRESHOLD_NS)
    result["total_wait_ns"] = sum(c.get("dur_ns", 0) for c in contentions)

    return result


def _try_stdlib_monitor(
    tp: Any,
    start_ns: int,
    end_ns: int,
    utids: list[int],
) -> list[dict[str, Any]] | None:
    """使用 Perfetto stdlib android.monitor_contention 模块。"""
    try:
        tp.query("INCLUDE PERFETTO MODULE android.monitor_contention")
    except Exception:
        return None

    utid_list = ",".join(str(u) for u in utids) if utids else "0"
    try:
        rows = list(tp.query(f"""
            SELECT
                ts, dur, blocked_utid, blocking_utid,
                blocked_thread_name, blocking_thread_name,
                short_blocking_method, waiter_count
            FROM android_monitor_contention
            WHERE blocked_utid IN ({utid_list})
              AND ts >= {start_ns} AND ts <= {end_ns}
            ORDER BY dur DESC
        """))
        contentions = []
        for row in rows:
            dur = int(row.dur) if row.dur else 0
            contentions.append({
                "ts_ns": int(row.ts),
                "dur_ns": dur,
                "dur_ms": round(dur / 1e6, 2),
                "blocked_thread": str(row.blocked_thread_name) if row.blocked_thread_name else "",
                "blocking_thread": str(row.blocking_thread_name) if row.blocking_thread_name else "",
                "blocking_method": str(row.short_blocking_method) if row.short_blocking_method else "",
                "waiter_count": int(row.waiter_count) if row.waiter_count is not None else 0,
                "is_severe": dur > SEVERE_THRESHOLD_NS,
            })
        return contentions
    except Exception:
        return None


def _fallback_slice_monitor(
    tp: Any,
    start_ns: int,
    end_ns: int,
    utids: list[int],
) -> list[dict[str, Any]]:
    """降级方案：查 slice 表的 monitor contention 相关 slice。"""
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
              AND (s.name GLOB '*monitor contention*' OR s.name GLOB '*Lock contention*')
              AND s.ts >= {start_ns} AND s.ts <= {end_ns}
            ORDER BY s.dur DESC
        """))
        contentions = []
        for row in rows:
            dur = int(row.dur) if row.dur else 0
            contentions.append({
                "ts_ns": int(row.ts),
                "dur_ns": dur,
                "dur_ms": round(dur / 1e6, 2),
                "blocked_thread": str(row.thread_name) if row.thread_name else "",
                "blocking_thread": "",
                "name": str(row.name) if row.name else "",
                "is_severe": dur > SEVERE_THRESHOLD_NS,
            })
        return contentions
    except Exception:
        return []
