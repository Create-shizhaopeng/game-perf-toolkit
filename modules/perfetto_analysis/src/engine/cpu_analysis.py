# -*- coding: utf-8 -*-
"""CPU 频率/爬升/大小核调度/调度延迟分析（FR-106/FR-107/FR-108）。"""
from __future__ import annotations

import logging
import sys
from typing import Any

_log = logging.getLogger("perfetto_analysis.engine")

FREQ_RAMP_MIN_STEPS = 3  # 连续递增步数判定为频率爬升


def _build_ramp_entry(cpu: int, events: list[dict], start_idx: int, end_idx: int, steps: int) -> dict:
    """构建频率爬升条目，包含每步详情。"""
    step_details = []
    for j in range(start_idx, end_idx):
        step_details.append({
            "from_khz": events[j]["freq_khz"],
            "to_khz": events[j + 1]["freq_khz"],
            "ts_ns": events[j + 1]["ts_ns"],
            "step_dur_us": round((events[j + 1]["ts_ns"] - events[j]["ts_ns"]) / 1000, 1),
        })
    total_dur_us = round((events[end_idx]["ts_ns"] - events[start_idx]["ts_ns"]) / 1000, 1)
    return {
        "cpu": cpu,
        "start_ts_ns": events[start_idx]["ts_ns"],
        "end_ts_ns": events[end_idx]["ts_ns"],
        "start_freq_khz": events[start_idx]["freq_khz"],
        "end_freq_khz": events[end_idx]["freq_khz"],
        "steps": steps,
        "total_dur_us": total_dur_us,
        "step_details": step_details,
    }


def analyze_cpu(
    tp: Any,
    window_start_ns: int,
    window_end_ns: int,
    target_utids: list[int],
    topology: dict[str, Any] | None = None,
    sched_latency_ms: float = 1.0,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    CPU 综合分析（频率 + 大小核 + 调度延迟）。
    """
    result: dict[str, Any] = {
        "freq_analysis": {},
        "cluster_analysis": {},
        "sched_latency": {},
        "degraded": False,
    }

    # CPU 频率分析
    freq_data = _analyze_cpu_freq(tp, window_start_ns, window_end_ns, topology)
    result["freq_analysis"] = freq_data

    if not freq_data.get("freq_events"):
        result["degraded"] = True
        result["degraded_reason"] = "缺少 CPU 频率数据"
        _log.warning("缺少 CPU 频率数据，CPU 频率分析跳过")

    # 大小核调度分析
    if target_utids and topology:
        cluster_data = _analyze_cluster_scheduling(
            tp, window_start_ns, window_end_ns, target_utids, topology,
        )
        result["cluster_analysis"] = cluster_data

    # 调度延迟分析
    if target_utids:
        sched_data = _analyze_sched_latency(
            tp, window_start_ns, window_end_ns, target_utids, sched_latency_ms,
        )
        result["sched_latency"] = sched_data

    return result


def _analyze_cpu_freq(
    tp: Any,
    start_ns: int,
    end_ns: int,
    topology: dict[str, Any] | None,
) -> dict[str, Any]:
    """CPU 频率与爬升状态分析（FR-106）。"""
    freq_events: list[dict[str, Any]] = []

    _freq_queries = [
        f"""SELECT ct.cpu, c.ts, CAST(c.value AS INTEGER) as freq_khz
            FROM counter c
            JOIN cpu_counter_track ct ON c.track_id = ct.id
            WHERE ct.name GLOB '*freq*' AND ct.name NOT GLOB '*gpu*'
              AND c.ts >= {start_ns} AND c.ts <= {end_ns}
            ORDER BY ct.cpu, c.ts""",
        f"""SELECT ct.cpu, c.ts, CAST(c.value AS INTEGER) as freq_khz
            FROM counter c
            JOIN cpu_counter_track ct ON c.track_id = ct.id
            WHERE ct.name IN ('cpufreq', 'cpu_freq', 'cpu_frequency')
              AND c.ts >= {start_ns} AND c.ts <= {end_ns}
            ORDER BY ct.cpu, c.ts""",
        f"""SELECT
                CAST(SUBSTR(t.name, INSTR(t.name, 'cpu') + 3) AS INTEGER) as cpu,
                c.ts,
                CAST(c.value AS INTEGER) as freq_khz
            FROM counter c
            JOIN counter_track t ON c.track_id = t.id
            WHERE (t.name GLOB '*cpufreq*' OR t.name GLOB '*cpu_frequency*'
                   OR t.name GLOB '*cpu*freq*')
              AND t.name NOT GLOB '*gpu*'
              AND c.ts >= {start_ns} AND c.ts <= {end_ns}
            ORDER BY cpu, c.ts""",
    ]

    for q in _freq_queries:
        try:
            rows = list(tp.query(q))
            if rows:
                freq_events = [
                    {"cpu": int(row.cpu), "ts_ns": int(row.ts), "freq_khz": int(row.freq_khz)}
                    for row in rows
                ]
                break
        except Exception as e:
            _log.warning("CPU 频率查询降级: %s", e)
            continue

    if not freq_events:
        return {"freq_events": [], "ramp_ups": [], "stats": {}}

    # 按 CPU 分组检测频率爬升
    cpu_events: dict[int, list[dict]] = {}
    for ev in freq_events:
        cpu_events.setdefault(ev["cpu"], []).append(ev)

    ramp_ups: list[dict[str, Any]] = []
    stats_per_cpu: dict[int, dict] = {}

    for cpu, events in cpu_events.items():
        freqs = [e["freq_khz"] for e in events]
        stats_per_cpu[cpu] = {
            "min_freq_khz": min(freqs),
            "max_freq_khz": max(freqs),
            "sample_count": len(freqs),
        }

        # 频率爬升检测：连续 N 次递增，并记录每步详情
        inc_count = 0
        ramp_start = 0
        for i in range(1, len(events)):
            if events[i]["freq_khz"] > events[i - 1]["freq_khz"]:
                if inc_count == 0:
                    ramp_start = i - 1
                inc_count += 1
            else:
                if inc_count >= FREQ_RAMP_MIN_STEPS:
                    ramp_ups.append(_build_ramp_entry(cpu, events, ramp_start, i - 1, inc_count))
                inc_count = 0

        if inc_count >= FREQ_RAMP_MIN_STEPS:
            ramp_ups.append(_build_ramp_entry(cpu, events, ramp_start, len(events) - 1, inc_count))

    # 整体统计
    all_freqs = [e["freq_khz"] for e in freq_events]
    overall_stats = {
        "min_freq_khz": min(all_freqs),
        "max_freq_khz": max(all_freqs),
        "per_cpu": stats_per_cpu,
    }

    # 集群标注
    if topology:
        cpu_to_cluster: dict[int, str] = {}
        for cl in topology.get("clusters", []):
            for c in cl.get("cpus", []):
                cpu_to_cluster[c] = cl.get("type", "unknown")
        for ev in freq_events:
            ev["cluster"] = cpu_to_cluster.get(ev["cpu"], "unknown")
        for ru in ramp_ups:
            ru["cluster"] = cpu_to_cluster.get(ru["cpu"], "unknown")

    return {
        "freq_events": freq_events,
        "ramp_ups": ramp_ups,
        "stats": overall_stats,
    }


def _analyze_cluster_scheduling(
    tp: Any,
    start_ns: int,
    end_ns: int,
    utids: list[int],
    topology: dict[str, Any],
) -> dict[str, Any]:
    """大小核调度分析（FR-107）。"""
    cpu_to_cluster: dict[int, str] = {}
    for cl in topology.get("clusters", []):
        for c in cl.get("cpus", []):
            cpu_to_cluster[c] = cl.get("type", "unknown")

    utid_list = ",".join(str(u) for u in utids)
    cluster_time: dict[str, int] = {}
    migrations_same = 0
    migrations_cross = 0
    migration_details: list[dict[str, Any]] = []

    try:
        rows = list(tp.query(f"""
            SELECT ts.ts, ts.dur, ts.cpu, ts.utid, t.name as thread_name
            FROM thread_state ts
            JOIN thread t ON ts.utid = t.utid
            WHERE ts.utid IN ({utid_list})
              AND ts.state = 'Running'
              AND ts.ts + ts.dur > {start_ns}
              AND ts.ts < {end_ns}
            ORDER BY ts.utid, ts.ts
        """))

        prev_cpu: dict[int, int] = {}
        for row in rows:
            cpu = int(row.cpu) if row.cpu is not None else -1
            dur = int(row.dur) if row.dur else 0
            utid = int(row.utid)
            cluster = cpu_to_cluster.get(cpu, "unknown")
            cluster_time[cluster] = cluster_time.get(cluster, 0) + dur

            if utid in prev_cpu:
                if prev_cpu[utid] != cpu and cpu >= 0:
                    prev_cluster = cpu_to_cluster.get(prev_cpu[utid], "unknown")
                    if prev_cluster == cluster:
                        migrations_same += 1
                    else:
                        migrations_cross += 1
                        migration_details.append({
                            "utid": utid,
                            "thread_name": str(row.thread_name),
                            "ts_ns": int(row.ts),
                            "from_cpu": prev_cpu[utid],
                            "to_cpu": cpu,
                            "from_cluster": prev_cluster,
                            "to_cluster": cluster,
                        })
            prev_cpu[utid] = cpu

    except Exception as e:
        _log.warning("大小核调度分析失败: %s", e)

    total_running = sum(cluster_time.values()) or 1
    cluster_pct = {k: round(v / total_running * 100, 1) for k, v in cluster_time.items()}

    return {
        "cluster_time_ns": cluster_time,
        "cluster_pct": cluster_pct,
        "migrations_same_cluster": migrations_same,
        "migrations_cross_cluster": migrations_cross,
        "migration_details": migration_details[:50],
    }


def _analyze_sched_latency(
    tp: Any,
    start_ns: int,
    end_ns: int,
    utids: list[int],
    threshold_ms: float,
) -> dict[str, Any]:
    """调度延迟分析（FR-108）。"""
    utid_list = ",".join(str(u) for u in utids)
    threshold_ns = int(threshold_ms * 1e6)

    latencies: list[int] = []
    anomalies: list[dict[str, Any]] = []

    try:
        rows = list(tp.query(f"""
            SELECT ts.ts, ts.dur, ts.cpu, ts.utid, t.name as thread_name
            FROM thread_state ts
            JOIN thread t ON ts.utid = t.utid
            WHERE ts.utid IN ({utid_list})
              AND ts.state IN ('R', 'R+')
              AND ts.ts + ts.dur > {start_ns}
              AND ts.ts < {end_ns}
            ORDER BY ts.dur DESC
        """))
        for row in rows:
            dur = int(row.dur) if row.dur else 0
            latencies.append(dur)
            if dur > threshold_ns:
                anomalies.append({
                    "utid": int(row.utid),
                    "thread_name": str(row.thread_name),
                    "ts_ns": int(row.ts),
                    "dur_ns": dur,
                    "dur_us": round(dur / 1000, 1),
                    "cpu": int(row.cpu) if row.cpu is not None else None,
                })
    except Exception as e:
        _log.warning("调度延迟分析失败: %s", e)

    stats: dict[str, Any] = {}
    if latencies:
        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)
        stats = {
            "count": n,
            "p50_us": round(latencies_sorted[n * 50 // 100] / 1000, 1),
            "p90_us": round(latencies_sorted[n * 90 // 100] / 1000, 1),
            "p99_us": round(latencies_sorted[min(n * 99 // 100, n - 1)] / 1000, 1),
            "max_us": round(latencies_sorted[-1] / 1000, 1),
        }

    return {
        "stats": stats,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies[:20],
    }
