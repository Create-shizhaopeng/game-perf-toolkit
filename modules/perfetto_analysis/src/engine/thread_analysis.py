# -*- coding: utf-8 -*-
"""线程状态时间线 + Block/Waker 链（FR-104/FR-105）。"""
from __future__ import annotations

import logging
import sys
from typing import Any

_log = logging.getLogger("perfetto_analysis.engine")

MAX_WAKER_DEPTH = 10
BLOCK_THRESHOLD_NS = 1_000_000  # 1ms


def analyze_thread_states(
    tp: Any,
    window_start_ns: int,
    window_end_ns: int,
    target_utids: list[int],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    线程状态时间线 + Block/Waker 链分析。
    返回: {"thread_states": [...], "waker_chains": [...], "degraded": bool}
    """
    result: dict[str, Any] = {
        "thread_states": [],
        "waker_chains": [],
        "degraded": False,
    }

    if not target_utids:
        return result

    # 检查 sched_switch/sched_waking 数据可用性
    has_sched = _check_sched_data(tp)
    if not has_sched:
        result["degraded"] = True
        result["degraded_reason"] = "调度数据不完整"
        _log.warning("缺少 sched_switch/sched_waking，线程分析降级")

    # 查询线程状态
    thread_states = _query_thread_states(tp, window_start_ns, window_end_ns, target_utids)
    result["thread_states"] = thread_states

    # Block/Waker 链追溯（对阻塞 > 1ms 的状态）
    if has_sched:
        waker_chains = []
        for ts in thread_states:
            if ts.get("state") in ("S", "D", "I") and ts.get("dur_ns", 0) > BLOCK_THRESHOLD_NS:
                chain = _trace_waker_chain(tp, ts)
                if chain:
                    waker_chains.append(chain)
        result["waker_chains"] = waker_chains

    return result


def _check_sched_data(tp: Any) -> bool:
    """检查 thread_state 表是否有数据。"""
    try:
        rows = list(tp.query("SELECT 1 FROM thread_state LIMIT 1"))
        return len(rows) > 0
    except Exception:
        return False


def _query_thread_states(
    tp: Any,
    start_ns: int,
    end_ns: int,
    utids: list[int],
) -> list[dict[str, Any]]:
    """查询指定 utids 在窗口内的线程状态。"""
    if not utids:
        return []

    utid_list = ",".join(str(u) for u in utids)
    try:
        rows = list(tp.query(f"""
            SELECT
                ts.ts,
                ts.dur,
                ts.state,
                ts.cpu,
                ts.utid,
                ts.blocked_function,
                ts.waker_utid,
                t.name as thread_name,
                t.tid,
                p.pid,
                p.name as process_name,
                ts.io_wait
            FROM thread_state ts
            JOIN thread t ON ts.utid = t.utid
            LEFT JOIN process p ON t.upid = p.upid
            WHERE ts.utid IN ({utid_list})
              AND ts.ts + ts.dur > {start_ns}
              AND ts.ts < {end_ns}
            ORDER BY ts.ts
        """))
        return [
            {
                "thread_name": str(row.thread_name) if row.thread_name else "",
                "state": str(row.state) if row.state else "",
                "ts_ns": int(row.ts),
                "dur_ns": int(row.dur) if row.dur else 0,
                "cpu": int(row.cpu) if row.cpu is not None else None,
                "utid": int(row.utid),
                "tid": int(row.tid) if row.tid is not None else None,
                "pid": int(row.pid) if row.pid is not None else None,
                "process_name": str(row.process_name) if row.process_name else "",
                "blocked_function": str(row.blocked_function) if row.blocked_function else None,
                "waker_utid": int(row.waker_utid) if row.waker_utid is not None else None,
                "io_wait": bool(row.io_wait) if hasattr(row, "io_wait") and row.io_wait is not None else None,
            }
            for row in rows
        ]
    except Exception as e:
        _log.warning("线程状态查询失败: %s", e)
        return []


def _trace_waker_chain(tp: Any, blocked_state: dict[str, Any]) -> dict[str, Any] | None:
    """对单个阻塞状态追溯 waker 链，最多 MAX_WAKER_DEPTH 层。"""
    waker_utid = blocked_state.get("waker_utid")
    if waker_utid is None:
        return None

    chain: list[dict[str, Any]] = []
    visited: set[int] = set()
    current_utid = waker_utid

    for _ in range(MAX_WAKER_DEPTH):
        if current_utid in visited:
            break
        visited.add(current_utid)

        info = _get_thread_info(tp, current_utid)
        if not info:
            break

        chain.append(info)

        next_waker = _find_waker_at_time(tp, current_utid, blocked_state["ts_ns"])
        if next_waker is None:
            break
        current_utid = next_waker

    if not chain:
        return None

    return {
        "blocked_thread": blocked_state.get("thread_name", ""),
        "blocked_ts_ns": blocked_state.get("ts_ns", 0),
        "blocked_dur_ns": blocked_state.get("dur_ns", 0),
        "blocked_function": blocked_state.get("blocked_function"),
        "chain": chain,
    }


def _get_thread_info(tp: Any, utid: int) -> dict[str, Any] | None:
    """获取线程基本信息。"""
    try:
        rows = list(tp.query(f"""
            SELECT t.name as thread_name, p.name as process_name, p.pid
            FROM thread t
            LEFT JOIN process p ON t.upid = p.upid
            WHERE t.utid = {utid}
            LIMIT 1
        """))
        if not rows:
            return None
        row = rows[0]
        return {
            "utid": utid,
            "thread": str(row.thread_name) if row.thread_name else f"utid={utid}",
            "process": str(row.process_name) if row.process_name else "",
            "pid": int(row.pid) if row.pid is not None else None,
        }
    except Exception:
        return None


def _find_waker_at_time(tp: Any, utid: int, ts_ns: int) -> int | None:
    """查找在指定时间点附近唤醒当前线程的 waker_utid。"""
    try:
        rows = list(tp.query(f"""
            SELECT waker_utid
            FROM thread_state
            WHERE utid = {utid}
              AND ts <= {ts_ns}
              AND waker_utid IS NOT NULL
            ORDER BY ts DESC
            LIMIT 1
        """))
        if rows and rows[0].waker_utid is not None:
            return int(rows[0].waker_utid)
    except Exception:
        pass
    return None
