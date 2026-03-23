# -*- coding: utf-8 -*-
"""Binder 调用分析 + 线程池饱和度（FR-109/FR-110）。"""
from __future__ import annotations

import sys
from typing import Any


def analyze_binder(
    tp: Any,
    window_start_ns: int,
    window_end_ns: int,
    target_utids: list[int],
    upid: int | None = None,
    slow_binder_ms: float = 2.0,
) -> dict[str, Any]:
    """
    Binder 综合分析。
    优先使用 INCLUDE PERFETTO MODULE android.binder，降级到 slice 表查询。
    """
    result: dict[str, Any] = {
        "binder_calls": [],
        "slow_binder_count": 0,
        "pool_saturation": {},
        "degraded": False,
    }

    # 尝试 stdlib 模块
    calls = _try_stdlib_binder(tp, window_start_ns, window_end_ns, target_utids, slow_binder_ms)
    if calls is None:
        result["degraded"] = True
        result["degraded_reason"] = "Binder stdlib 模块不可用，降级到 slice 表查询"
        calls = _fallback_slice_binder(tp, window_start_ns, window_end_ns, target_utids, slow_binder_ms)

    result["binder_calls"] = calls
    result["slow_binder_count"] = sum(1 for c in calls if c.get("is_slow"))

    # 线程池饱和度
    if upid is not None:
        result["pool_saturation"] = _analyze_pool_saturation(
            tp, window_start_ns, window_end_ns, upid,
        )

    return result


def _try_stdlib_binder(
    tp: Any,
    start_ns: int,
    end_ns: int,
    utids: list[int],
    threshold_ms: float,
) -> list[dict[str, Any]] | None:
    """使用 Perfetto stdlib android.binder 模块。"""
    try:
        tp.query("INCLUDE PERFETTO MODULE android.binder")
    except Exception:
        return None

    threshold_ns = int(threshold_ms * 1e6)
    utid_list = ",".join(str(u) for u in utids) if utids else "0"

    try:
        rows = list(tp.query(f"""
            SELECT
                client_ts as ts,
                client_dur as dur,
                client_utid,
                server_utid,
                client_tid,
                server_tid,
                client_process as client_proc,
                server_process as server_proc,
                client_thread,
                server_thread,
                server_pid
            FROM android_binder_txns
            WHERE client_utid IN ({utid_list})
              AND client_ts >= {start_ns} AND client_ts <= {end_ns}
            ORDER BY client_ts
        """))
        calls = []
        for row in rows:
            dur = int(row.dur) if row.dur else 0
            callee_proc = str(row.server_proc) if row.server_proc else ""
            if not callee_proc:
                server_pid = int(row.server_pid) if hasattr(row, "server_pid") and row.server_pid is not None else None
                if server_pid:
                    callee_proc = f"PID:{server_pid}"
            calls.append({
                "ts_ns": int(row.ts),
                "dur_ns": dur,
                "dur_ms": round(dur / 1e6, 2),
                "caller_thread": str(row.client_thread) if row.client_thread else "",
                "callee_thread": str(row.server_thread) if row.server_thread else "",
                "callee_process": callee_proc,
                "server_tid": int(row.server_tid) if row.server_tid is not None else None,
                "is_slow": dur > threshold_ns,
            })
        return calls
    except Exception:
        return None


def _fallback_slice_binder(
    tp: Any,
    start_ns: int,
    end_ns: int,
    utids: list[int],
    threshold_ms: float,
) -> list[dict[str, Any]]:
    """降级方案：直接查 slice 表的 binder* slice。"""
    threshold_ns = int(threshold_ms * 1e6)
    utid_list = ",".join(str(u) for u in utids) if utids else "0"

    try:
        rows = list(tp.query(f"""
            SELECT s.ts, s.dur, s.name, t.name as thread_name
            FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE t.utid IN ({utid_list})
              AND s.name GLOB 'binder*'
              AND s.ts >= {start_ns} AND s.ts <= {end_ns}
            ORDER BY s.ts
        """))
        calls = []
        for row in rows:
            dur = int(row.dur) if row.dur else 0
            calls.append({
                "ts_ns": int(row.ts),
                "dur_ns": dur,
                "dur_ms": round(dur / 1e6, 2),
                "caller_thread": str(row.thread_name) if row.thread_name else "",
                "callee_thread": "",
                "callee_process": "",
                "slice_name": str(row.name),
                "is_slow": dur > threshold_ns,
            })
        return calls
    except Exception as e:
        print(f"[perfetto_analysis] 警告: Binder slice 查询失败: {e}", file=sys.stderr)
        return []


def _analyze_pool_saturation(
    tp: Any,
    start_ns: int,
    end_ns: int,
    upid: int,
) -> dict[str, Any]:
    """Binder 线程池饱和度（FR-110）。"""
    try:
        # 统计目标进程的 Binder 线程数
        binder_threads = list(tp.query(f"""
            SELECT utid, name FROM thread
            WHERE upid = {upid} AND name GLOB 'Binder:*'
        """))
        total_binder_threads = len(binder_threads)

        if total_binder_threads == 0:
            return {"total_threads": 0, "peak_concurrent": 0, "saturation_pct": 0}

        binder_utids = [int(r.utid) for r in binder_threads]
        utid_list = ",".join(str(u) for u in binder_utids)

        # 窗口内同时 Running 的 Binder 线程峰值
        rows = list(tp.query(f"""
            SELECT ts, dur, utid
            FROM thread_state
            WHERE utid IN ({utid_list})
              AND state = 'Running'
              AND ts + dur > {start_ns}
              AND ts < {end_ns}
            ORDER BY ts
        """))

        if not rows:
            return {
                "total_threads": total_binder_threads,
                "peak_concurrent": 0,
                "saturation_pct": 0,
            }

        events: list[tuple[int, int]] = []
        for row in rows:
            ts = int(row.ts)
            dur = int(row.dur) if row.dur else 0
            events.append((ts, 1))
            events.append((ts + dur, -1))
        events.sort()

        current = 0
        peak = 0
        for _, delta in events:
            current += delta
            peak = max(peak, current)

        saturation_pct = round(peak / total_binder_threads * 100, 1)

        return {
            "total_threads": total_binder_threads,
            "peak_concurrent": peak,
            "saturation_pct": saturation_pct,
        }
    except Exception as e:
        print(f"[perfetto_analysis] 警告: Binder 线程池饱和度分析失败: {e}", file=sys.stderr)
        return {}
