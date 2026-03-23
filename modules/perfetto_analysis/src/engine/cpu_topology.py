# -*- coding: utf-8 -*-
"""CPU 拓扑初始化（FR-101）：从 trace 中推断 CPU 集群结构。"""
from __future__ import annotations

import json
import sys
from typing import Any


def init_cpu_topology(tp: Any) -> dict[str, Any]:
    """
    从 trace 推断 CPU 拓扑结构。
    优先尝试 INCLUDE PERFETTO MODULE android.cpu.cluster_type，
    失败时回退到从 cpu_freq counter 推断。
    返回: {"clusters": [{"type": str, "cpus": [int], "max_freq_khz": int}], ...}
    """
    topology = _try_stdlib_topology(tp)
    if topology is None:
        topology = _infer_from_freq(tp)
    return topology


def _try_stdlib_topology(tp: Any) -> dict[str, Any] | None:
    """尝试使用 Perfetto stdlib 获取 CPU 集群信息。"""
    try:
        tp.query("INCLUDE PERFETTO MODULE android.cpu.cluster_type")
        rows = list(tp.query("""
            SELECT cpu, cluster_type
            FROM android_cpu_cluster_type
            ORDER BY cpu
        """))
        if not rows:
            return None

        clusters_map: dict[str, list[int]] = {}
        for row in rows:
            ctype = str(row.cluster_type).lower()
            cpu = int(row.cpu)
            clusters_map.setdefault(ctype, []).append(cpu)

        freq_map = _get_max_freq_per_cpu(tp)
        clusters = []
        for ctype in ("little", "mid", "big"):
            if ctype in clusters_map:
                cpus = sorted(clusters_map[ctype])
                max_freq = max(freq_map.get(c, 0) for c in cpus) if cpus else 0
                clusters.append({
                    "type": ctype,
                    "cpus": cpus,
                    "max_freq_khz": max_freq,
                })

        for ctype, cpus in clusters_map.items():
            if ctype not in ("little", "mid", "big"):
                max_freq = max(freq_map.get(c, 0) for c in cpus) if cpus else 0
                clusters.append({
                    "type": ctype,
                    "cpus": sorted(cpus),
                    "max_freq_khz": max_freq,
                })

        total = sum(len(c["cpus"]) for c in clusters)
        return {"clusters": clusters, "total_cpu_count": total}
    except Exception:
        return None


def _infer_from_freq(tp: Any) -> dict[str, Any]:
    """从 cpu_freq counter 的最大频率推断集群分组。"""
    freq_map = _get_max_freq_per_cpu(tp)
    if not freq_map:
        return {"clusters": [], "total_cpu_count": 0}

    freq_groups: dict[int, list[int]] = {}
    for cpu, freq in freq_map.items():
        freq_groups.setdefault(freq, []).append(cpu)

    sorted_freqs = sorted(freq_groups.keys())
    type_labels = _assign_cluster_types(len(sorted_freqs))

    clusters = []
    for i, freq in enumerate(sorted_freqs):
        cpus = sorted(freq_groups[freq])
        clusters.append({
            "type": type_labels[i],
            "cpus": cpus,
            "max_freq_khz": freq,
        })

    total = sum(len(c["cpus"]) for c in clusters)
    return {"clusters": clusters, "total_cpu_count": total}


def _get_max_freq_per_cpu(tp: Any) -> dict[int, int]:
    """查询每个 CPU 的最大频率 (KHz)。"""
    freq_map: dict[int, int] = {}
    # 优先使用 cpu_counter_track.cpu 列（准确），而非从 track 名称解析
    try:
        rows = list(tp.query("""
            SELECT
                ct.cpu,
                CAST(MAX(c.value) AS INTEGER) as max_freq
            FROM counter c
            JOIN cpu_counter_track ct ON c.track_id = ct.id
            WHERE ct.name GLOB '*freq*' AND ct.name NOT GLOB '*gpu*'
            GROUP BY ct.cpu
            ORDER BY ct.cpu
        """))
        for row in rows:
            freq_map[int(row.cpu)] = int(row.max_freq)
    except Exception:
        pass

    if not freq_map:
        try:
            rows = list(tp.query("""
                SELECT
                    ct.cpu,
                    CAST(MAX(c.value) AS INTEGER) as max_freq
                FROM counter c
                JOIN cpu_counter_track ct ON c.track_id = ct.id
                WHERE ct.name IN ('cpufreq', 'cpu_freq')
                GROUP BY ct.cpu
                ORDER BY ct.cpu
            """))
            for row in rows:
                freq_map[int(row.cpu)] = int(row.max_freq)
        except Exception:
            pass

    return freq_map


def _assign_cluster_types(count: int) -> list[str]:
    """按集群数量分配类型标签。"""
    if count == 1:
        return ["big"]
    elif count == 2:
        return ["little", "big"]
    elif count == 3:
        return ["little", "mid", "big"]
    else:
        labels = ["little"]
        for i in range(1, count - 1):
            labels.append(f"mid_{i}" if count > 4 else "mid")
        labels.append("big")
        return labels


def topology_to_json(topology: dict[str, Any]) -> str:
    """将拓扑结构序列化为 JSON 字符串。"""
    return json.dumps(topology, ensure_ascii=False)
