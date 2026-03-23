# -*- coding: utf-8 -*-
"""SurfaceFlinger 合成耗时分析（FR-116）。"""
from __future__ import annotations

import sys
from typing import Any


def analyze_sf(
    tp: Any,
    window_start_ns: int,
    window_end_ns: int,
    target_utids: list[int],
    upid: int | None = None,
) -> dict[str, Any]:
    """
    SF 合成耗时分析：SurfaceFlinger 进程的 onMessageReceived/commit/composite slice。
    数据不存在时返回空结果（不报错）。
    """
    result: dict[str, Any] = {
        "sf_slices": [],
        "sf_stats": {},
        "re_composer_detected": False,
    }

    # 查找 SurfaceFlinger 进程 upid
    sf_upid = _find_sf_upid(tp)
    if sf_upid is None:
        return result

    try:
        rows = list(tp.query(f"""
            SELECT s.ts, s.dur, s.name, t.name as thread_name
            FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE t.upid = {sf_upid}
              AND (s.name GLOB '*onMessageReceived*'
                   OR s.name GLOB '*commit*'
                   OR s.name GLOB '*composite*'
                   OR s.name GLOB '*onComposerHalRefresh*')
              AND s.ts >= {window_start_ns} AND s.ts <= {window_end_ns}
            ORDER BY s.ts
        """))

        slices = []
        for row in rows:
            dur = int(row.dur) if row.dur else 0
            slices.append({
                "ts_ns": int(row.ts),
                "dur_ns": dur,
                "dur_ms": round(dur / 1e6, 2),
                "name": str(row.name) if row.name else "",
                "thread_name": str(row.thread_name) if row.thread_name else "",
            })
        result["sf_slices"] = slices

        if slices:
            durs = [s["dur_ns"] for s in slices]
            durs_sorted = sorted(durs)
            n = len(durs_sorted)
            result["sf_stats"] = {
                "count": n,
                "avg_us": round(sum(durs) / n / 1000, 1),
                "max_us": round(durs_sorted[-1] / 1000, 1),
            }
    except Exception:
        pass

    # REComposer 检测
    try:
        rows = list(tp.query(f"""
            SELECT 1 FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE t.upid = {sf_upid} AND s.name GLOB '*REComposer*'
            LIMIT 1
        """))
        result["re_composer_detected"] = len(rows) > 0
    except Exception:
        pass

    return result


def _find_sf_upid(tp: Any) -> int | None:
    """查找 SurfaceFlinger 进程的 upid。"""
    try:
        rows = list(tp.query(
            "SELECT upid FROM process WHERE name = 'surfaceflinger' OR name = '/system/bin/surfaceflinger' LIMIT 1"
        ))
        if rows:
            return int(rows[0].upid)
    except Exception:
        pass
    return None
