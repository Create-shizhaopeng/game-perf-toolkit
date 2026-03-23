# -*- coding: utf-8 -*-
"""GPU 渲染耗时分析（FR-115）。"""
from __future__ import annotations

import sys
from typing import Any


def analyze_gpu(
    tp: Any,
    window_start_ns: int,
    window_end_ns: int,
    target_utids: list[int],
    upid: int | None = None,
) -> dict[str, Any]:
    """
    GPU 渲染耗时分析：DrawFrame + dequeueBuffer slice dur。
    数据不存在时返回空结果（不报错）。
    """
    result: dict[str, Any] = {
        "draw_frames": [],
        "dequeue_buffers": [],
        "draw_frame_stats": {},
        "dequeue_stats": {},
        "render_stage_available": False,
    }

    if not target_utids and upid is None:
        return result

    where_clause = ""
    if target_utids:
        utid_list = ",".join(str(u) for u in target_utids)
        where_clause = f"t.utid IN ({utid_list})"
    elif upid is not None:
        where_clause = f"t.upid = {upid}"

    # DrawFrame slice
    try:
        rows = list(tp.query(f"""
            SELECT s.ts, s.dur, s.name
            FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE {where_clause}
              AND s.name GLOB '*DrawFrame*'
              AND s.ts >= {window_start_ns} AND s.ts <= {window_end_ns}
            ORDER BY s.ts
        """))
        draw_frames = [
            {"ts_ns": int(r.ts), "dur_ns": int(r.dur) if r.dur else 0}
            for r in rows
        ]
        result["draw_frames"] = draw_frames
        if draw_frames:
            durs = [d["dur_ns"] for d in draw_frames]
            durs_sorted = sorted(durs)
            n = len(durs_sorted)
            result["draw_frame_stats"] = {
                "count": n,
                "avg_us": round(sum(durs) / n / 1000, 1),
                "p99_us": round(durs_sorted[min(n * 99 // 100, n - 1)] / 1000, 1),
                "max_us": round(durs_sorted[-1] / 1000, 1),
            }
    except Exception:
        pass

    # dequeueBuffer slice
    try:
        rows = list(tp.query(f"""
            SELECT s.ts, s.dur
            FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE {where_clause}
              AND s.name GLOB '*dequeueBuffer*'
              AND s.ts >= {window_start_ns} AND s.ts <= {window_end_ns}
            ORDER BY s.ts
        """))
        dequeues = [
            {"ts_ns": int(r.ts), "dur_ns": int(r.dur) if r.dur else 0}
            for r in rows
        ]
        result["dequeue_buffers"] = dequeues
        if dequeues:
            durs = [d["dur_ns"] for d in dequeues]
            durs_sorted = sorted(durs)
            n = len(durs_sorted)
            result["dequeue_stats"] = {
                "count": n,
                "avg_us": round(sum(durs) / n / 1000, 1),
                "p99_us": round(durs_sorted[min(n * 99 // 100, n - 1)] / 1000, 1),
                "max_us": round(durs_sorted[-1] / 1000, 1),
            }
    except Exception:
        pass

    # gpu_render_stage_event（可选）
    try:
        rows = list(tp.query("SELECT 1 FROM gpu_slice LIMIT 1"))
        result["render_stage_available"] = len(rows) > 0
    except Exception:
        pass

    return result
