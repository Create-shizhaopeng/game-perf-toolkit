# -*- coding: utf-8 -*-
"""GC 阻塞分析（FR-114）。"""
from __future__ import annotations

import sys
from typing import Any


def analyze_gc(
    tp: Any,
    window_start_ns: int,
    window_end_ns: int,
    target_utids: list[int],
    upid: int | None = None,
) -> dict[str, Any]:
    """
    GC 阻塞分析：查 slice 表匹配 GC / concurrent copying 事件。
    数据不存在时返回空结果（不报错）。
    """
    result: dict[str, Any] = {
        "gc_events": [],
        "gc_count": 0,
        "gc_total_dur_ns": 0,
        "stw_dur_ns": 0,
    }

    if not target_utids and upid is None:
        return result

    where_clause = ""
    if target_utids:
        utid_list = ",".join(str(u) for u in target_utids)
        where_clause = f"t.utid IN ({utid_list})"
    elif upid is not None:
        where_clause = f"t.upid = {upid}"

    try:
        rows = list(tp.query(f"""
            SELECT s.ts, s.dur, s.name, t.name as thread_name
            FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE {where_clause}
              AND (s.name GLOB '*GC*' OR s.name GLOB '*concurrent copying*'
                   OR s.name GLOB '*concurrent mark*' OR s.name GLOB '*SuspendAll*')
              AND s.ts >= {window_start_ns} AND s.ts <= {window_end_ns}
            ORDER BY s.ts
        """))

        events = []
        total_dur = 0
        stw_dur = 0
        for row in rows:
            dur = int(row.dur) if row.dur else 0
            name = str(row.name) if row.name else ""
            is_stw = "SuspendAll" in name or "pause" in name.lower()
            events.append({
                "ts_ns": int(row.ts),
                "dur_ns": dur,
                "dur_ms": round(dur / 1e6, 2),
                "name": name,
                "thread_name": str(row.thread_name) if row.thread_name else "",
                "is_stw": is_stw,
            })
            total_dur += dur
            if is_stw:
                stw_dur += dur

        result["gc_events"] = events
        result["gc_count"] = len(events)
        result["gc_total_dur_ns"] = total_dur
        result["stw_dur_ns"] = stw_dur

    except Exception:
        pass

    return result
