# -*- coding: utf-8 -*-
"""全 trace 整体分析（FR-119）。"""
from __future__ import annotations

import sys
from typing import Any


def analyze_summary(
    tp: Any,
    parse_result: dict[str, Any],
    upid: int | None = None,
    target_utids: list[int] | None = None,
    topology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    全 trace 整体分析。
    涵盖 CPU/GPU 整体状态、帧率匹配、Binder/IO/GC/锁竞争健康度、
    CPU 频率 vs 帧率相关性、大小核利用率失衡检测。
    """
    result: dict[str, Any] = {}

    trace_start = parse_result.get("trace_start_ns", 0) or 0
    trace_end = parse_result.get("trace_end_ns", 0) or 0

    # CPU 整体状态
    result["cpu"] = _cpu_overall(tp, trace_start, trace_end, target_utids or [], topology or {})

    # GPU 整体状态
    result["gpu"] = _gpu_overall(tp, trace_start, trace_end, upid)

    # 帧率匹配分析
    result["frame_rate_matching"] = _frame_rate_matching(parse_result)

    # Binder 健康度
    result["binder_health"] = _binder_health(tp, trace_start, trace_end, target_utids or [], upid)

    # IO 健康度
    result["io_health"] = _io_health(tp, trace_start, trace_end, target_utids or [])

    # GC 健康度
    result["gc_health"] = _gc_health(tp, trace_start, trace_end, upid)

    # 锁竞争健康度
    result["lock_health"] = _lock_health(tp, trace_start, trace_end, target_utids or [])

    # CPU 频率 vs 帧率相关性
    result["cpu_freq_vs_framerate"] = _cpu_freq_correlation(
        tp, parse_result, trace_start, trace_end, topology or {},
    )

    # 大小核利用率失衡
    result["big_little_imbalance"] = _big_little_imbalance(
        tp, trace_start, trace_end, target_utids or [], topology or {},
    )

    return result


def _cpu_overall(
    tp: Any,
    start_ns: int,
    end_ns: int,
    utids: list[int],
    topology: dict[str, Any],
) -> dict[str, Any]:
    """CPU 整体状态：集群利用率、频率分布、Thermal 限频、调度延迟分布。"""
    cpu_data: dict[str, Any] = {
        "cluster_utilization": {},
        "sched_latency": {},
        "thermal_throttling": {"detected": False, "segments": []},
    }

    # 集群利用率
    cpu_to_cluster: dict[int, str] = {}
    for cl in topology.get("clusters", []):
        for c in cl.get("cpus", []):
            cpu_to_cluster[c] = cl.get("type", "unknown")

    if utids:
        utid_list = ",".join(str(u) for u in utids)
        try:
            rows = list(tp.query(f"""
                SELECT cpu, SUM(dur) as total_dur
                FROM thread_state
                WHERE utid IN ({utid_list})
                  AND state = 'Running'
                  AND ts >= {start_ns} AND ts < {end_ns}
                GROUP BY cpu
            """))
            cluster_running: dict[str, int] = {}
            for row in rows:
                cpu = int(row.cpu) if row.cpu is not None else -1
                cluster = cpu_to_cluster.get(cpu, "unknown")
                dur = int(row.total_dur) if row.total_dur else 0
                cluster_running[cluster] = cluster_running.get(cluster, 0) + dur

            total_dur = end_ns - start_ns if end_ns > start_ns else 1
            for cluster, running in cluster_running.items():
                cpu_data["cluster_utilization"][cluster] = {
                    "running_time_ns": running,
                    "avg_pct": round(running / total_dur * 100, 1),
                }
        except Exception:
            pass

    # 调度延迟分布
    if utids:
        utid_list = ",".join(str(u) for u in utids)
        try:
            rows = list(tp.query(f"""
                SELECT dur FROM thread_state
                WHERE utid IN ({utid_list})
                  AND state IN ('R', 'R+')
                  AND ts >= {start_ns} AND ts < {end_ns}
                ORDER BY dur
            """))
            latencies = [int(r.dur) for r in rows if r.dur]
            if latencies:
                n = len(latencies)
                cpu_data["sched_latency"] = {
                    "p50_us": round(latencies[n * 50 // 100] / 1000, 1),
                    "p90_us": round(latencies[n * 90 // 100] / 1000, 1),
                    "p99_us": round(latencies[min(n * 99 // 100, n - 1)] / 1000, 1),
                    "max_us": round(latencies[-1] / 1000, 1),
                }
        except Exception:
            pass

    return cpu_data


def _gpu_overall(
    tp: Any, start_ns: int, end_ns: int, upid: int | None,
) -> dict[str, Any]:
    """GPU 整体状态。"""
    gpu_data: dict[str, Any] = {"render_stage_available": False}
    if upid is None:
        return gpu_data

    try:
        rows = list(tp.query(f"""
            SELECT s.dur FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE t.upid = {upid}
              AND s.name GLOB '*DrawFrame*'
              AND s.ts >= {start_ns} AND s.ts < {end_ns}
        """))
        durs = [int(r.dur) for r in rows if r.dur]
        if durs:
            durs_sorted = sorted(durs)
            n = len(durs_sorted)
            gpu_data["draw_frame_avg_us"] = round(sum(durs) / n / 1000, 1)
            gpu_data["draw_frame_p99_us"] = round(durs_sorted[min(n * 99 // 100, n - 1)] / 1000, 1)
    except Exception:
        pass

    return gpu_data


def _frame_rate_matching(parse_result: dict[str, Any]) -> dict[str, Any]:
    """帧率匹配分析。"""
    hz = parse_result.get("inferred_refresh_rate_hz", 60) or 60
    frame_num = parse_result.get("frame_num", 0)
    start_ns = parse_result.get("trace_start_ns", 0) or 0
    end_ns = parse_result.get("trace_end_ns", 0) or 0
    dur_sec = (end_ns - start_ns) / 1e9 if end_ns > start_ns else 1

    actual_fps = frame_num / dur_sec if dur_sec > 0 else 0
    match_pct = round(min(actual_fps / hz, 1.0) * 100, 1)

    # 帧间隔分布直方图
    cycles = parse_result.get("vsync_cycles", [])
    stand_ms = parse_result.get("stand_vsync_ms", 1000 / hz)
    histogram = {
        "0_to_0.5T": 0, "0.5T_to_T": 0, "T_to_1.5T": 0,
        "1.5T_to_2T": 0, "2T_to_3T": 0, "3T_plus": 0,
    }
    intervals: list[float] = []
    for cy in cycles:
        interval_ms = (cy["vt_ns"] - cy["pre_vt_ns"]) / 1e6
        intervals.append(interval_ms)
        ratio = interval_ms / stand_ms if stand_ms > 0 else 1
        if ratio < 0.5:
            histogram["0_to_0.5T"] += 1
        elif ratio < 1.0:
            histogram["0.5T_to_T"] += 1
        elif ratio < 1.5:
            histogram["T_to_1.5T"] += 1
        elif ratio < 2.0:
            histogram["1.5T_to_2T"] += 1
        elif ratio < 3.0:
            histogram["2T_to_3T"] += 1
        else:
            histogram["3T_plus"] += 1

    # 变异系数
    import statistics
    cv_pct = 0.0
    if len(intervals) > 1:
        mean = statistics.mean(intervals)
        stdev = statistics.stdev(intervals)
        cv_pct = round((stdev / mean) * 100, 1) if mean > 0 else 0

    return {
        "device_refresh_hz": hz,
        "actual_fps": round(actual_fps, 2),
        "match_pct": match_pct,
        "interval_cv_pct": cv_pct,
        "unstable": cv_pct > 30,
        "histogram": histogram,
    }


def _binder_health(
    tp: Any, start_ns: int, end_ns: int, utids: list[int], upid: int | None,
) -> dict[str, Any]:
    """Binder 健康度。"""
    data: dict[str, Any] = {"total_txn": 0, "slow_txn_count": 0, "slow_txn_pct": 0}
    if not utids:
        return data
    utid_list = ",".join(str(u) for u in utids)
    try:
        rows = list(tp.query(f"""
            SELECT s.dur FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE t.utid IN ({utid_list})
              AND s.name GLOB 'binder*'
              AND s.ts >= {start_ns} AND s.ts < {end_ns}
        """))
        total = len(rows)
        slow = sum(1 for r in rows if r.dur and int(r.dur) > 2_000_000)
        data["total_txn"] = total
        data["slow_txn_count"] = slow
        data["slow_txn_pct"] = round(slow / total * 100, 1) if total > 0 else 0
    except Exception:
        pass
    return data


def _io_health(
    tp: Any, start_ns: int, end_ns: int, utids: list[int],
) -> dict[str, Any]:
    """IO 健康度。"""
    data: dict[str, Any] = {"d_state_total_ms": 0, "critical_thread_io_blocks": 0}
    if not utids:
        return data
    utid_list = ",".join(str(u) for u in utids)
    try:
        rows = list(tp.query(f"""
            SELECT SUM(dur) as total, COUNT(*) as cnt
            FROM thread_state
            WHERE utid IN ({utid_list})
              AND state = 'D'
              AND ts >= {start_ns} AND ts < {end_ns}
        """))
        if rows:
            total = int(rows[0].total) if rows[0].total else 0
            data["d_state_total_ms"] = round(total / 1e6, 1)
            data["critical_thread_io_blocks"] = int(rows[0].cnt) if rows[0].cnt else 0
    except Exception:
        pass
    return data


def _gc_health(
    tp: Any, start_ns: int, end_ns: int, upid: int | None,
) -> dict[str, Any]:
    """GC 健康度。"""
    data: dict[str, Any] = {"total_count": 0, "total_dur_ms": 0}
    if upid is None:
        return data
    try:
        rows = list(tp.query(f"""
            SELECT SUM(s.dur) as total, COUNT(*) as cnt
            FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE t.upid = {upid}
              AND (s.name GLOB '*GC*' OR s.name GLOB '*concurrent copying*')
              AND s.ts >= {start_ns} AND s.ts < {end_ns}
        """))
        if rows:
            total = int(rows[0].total) if rows[0].total else 0
            data["total_count"] = int(rows[0].cnt) if rows[0].cnt else 0
            data["total_dur_ms"] = round(total / 1e6, 1)
    except Exception:
        pass
    return data


def _lock_health(
    tp: Any, start_ns: int, end_ns: int, utids: list[int],
) -> dict[str, Any]:
    """锁竞争健康度。"""
    data: dict[str, Any] = {"total_count": 0, "total_wait_ms": 0}
    if not utids:
        return data
    utid_list = ",".join(str(u) for u in utids)
    try:
        rows = list(tp.query(f"""
            SELECT SUM(s.dur) as total, COUNT(*) as cnt
            FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE t.utid IN ({utid_list})
              AND (s.name GLOB '*monitor contention*' OR s.name GLOB '*Lock contention*')
              AND s.ts >= {start_ns} AND s.ts < {end_ns}
        """))
        if rows:
            total = int(rows[0].total) if rows[0].total else 0
            data["total_count"] = int(rows[0].cnt) if rows[0].cnt else 0
            data["total_wait_ms"] = round(total / 1e6, 1)
    except Exception:
        pass
    return data


def _cpu_freq_correlation(
    tp: Any,
    parse_result: dict[str, Any],
    start_ns: int,
    end_ns: int,
    topology: dict[str, Any],
) -> dict[str, Any]:
    """CPU 频率 vs 帧率相关性。"""
    data: dict[str, Any] = {"freq_insufficient": False}

    jank_records = parse_result.get("jank_records", [])
    if not jank_records:
        return data

    jank_windows = [(j.get("ajt1_ns", 0), j.get("sjt2_ns", 0)) for j in jank_records]
    normal_freq = _avg_freq_in_windows(tp, [(start_ns, end_ns)])
    jank_freq = _avg_freq_in_windows(tp, jank_windows) if jank_windows else normal_freq

    if normal_freq > 0:
        diff_pct = round((jank_freq - normal_freq) / normal_freq * 100, 1)
        data["jank_window_avg_freq_khz"] = jank_freq
        data["normal_window_avg_freq_khz"] = normal_freq
        data["diff_pct"] = diff_pct
        data["freq_insufficient"] = diff_pct < -20

    return data


def _avg_freq_in_windows(
    tp: Any,
    windows: list[tuple[int, int]],
) -> int:
    """计算窗口内平均 CPU 频率。"""
    all_freqs: list[int] = []
    _freq_queries_tpl = [
        """SELECT CAST(AVG(c.value) AS INTEGER) as avg_freq
           FROM counter c
           JOIN cpu_counter_track ct ON c.track_id = ct.id
           WHERE ct.name GLOB '*freq*' AND ct.name NOT GLOB '*gpu*'
             AND c.ts >= {start} AND c.ts < {end}""",
        """SELECT CAST(AVG(c.value) AS INTEGER) as avg_freq
           FROM counter c
           JOIN counter_track t ON c.track_id = t.id
           WHERE (t.name GLOB '*cpufreq*' OR t.name GLOB '*cpu_frequency*'
                  OR t.name GLOB '*cpu*freq*')
             AND t.name NOT GLOB '*gpu*'
             AND c.ts >= {start} AND c.ts < {end}""",
    ]
    for start, end in windows:
        if not start or not end:
            continue
        for q_tpl in _freq_queries_tpl:
            try:
                q = q_tpl.format(start=start, end=end)
                rows = list(tp.query(q))
                if rows and rows[0].avg_freq:
                    all_freqs.append(int(rows[0].avg_freq))
                    break
            except Exception:
                continue
    return int(sum(all_freqs) / len(all_freqs)) if all_freqs else 0


def _big_little_imbalance(
    tp: Any,
    start_ns: int,
    end_ns: int,
    utids: list[int],
    topology: dict[str, Any],
) -> dict[str, Any]:
    """大小核利用率失衡检测。"""
    data: dict[str, Any] = {"imbalanced": False}
    if not utids or not topology.get("clusters"):
        return data

    cpu_to_cluster: dict[int, str] = {}
    for cl in topology.get("clusters", []):
        for c in cl.get("cpus", []):
            cpu_to_cluster[c] = cl.get("type", "unknown")

    utid_list = ",".join(str(u) for u in utids)
    try:
        rows = list(tp.query(f"""
            SELECT cpu, SUM(dur) as total
            FROM thread_state
            WHERE utid IN ({utid_list})
              AND state = 'Running'
              AND ts >= {start_ns} AND ts < {end_ns}
            GROUP BY cpu
        """))
        cluster_dur: dict[str, int] = {}
        for row in rows:
            cpu = int(row.cpu) if row.cpu is not None else -1
            cl = cpu_to_cluster.get(cpu, "unknown")
            dur = int(row.total) if row.total else 0
            cluster_dur[cl] = cluster_dur.get(cl, 0) + dur

        total = sum(cluster_dur.values()) or 1
        little_pct = round(cluster_dur.get("little", 0) / total * 100, 1)
        data["critical_thread_little_pct"] = little_pct
        data["imbalanced"] = little_pct > 50
    except Exception:
        pass

    return data
