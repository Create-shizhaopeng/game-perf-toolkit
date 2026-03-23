# -*- coding: utf-8 -*-
"""从 DB 导出 Markdown 报告；纳秒 BOOTTIME 时间戳通过 realtime_offset 转为北京时间 24h 制、年月日、精确到 1ms；UTF-8。"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

BEIJING = timezone(timedelta(hours=8))

JANK_TYPE_LABELS: dict[str, str] = {
    "jank_1": "App Deadline Missed（App 提交超时）",
    "jank_2": "Buffer Unavailable（Buffer 不可用）",
    "jank_3": "SF Composition Missed（SF 合成未消费）",
}


def _format_jank_type(jtype: str) -> str:
    """将 jank_type 编码转为可读术语。"""
    if not jtype:
        return ""
    parts = [JANK_TYPE_LABELS.get(t.strip(), t.strip()) for t in jtype.split(",")]
    return ", ".join(parts)


def _us_to_ms(us_val: float | int) -> str:
    """将 μs 值转为 ms 字符串，保留 3 位小数。"""
    return str(round(us_val / 1000, 3))


def ns_to_beijing_ms(ns: int | None, offset_ns: int = 0) -> str:
    """BOOTTIME 纳秒时间戳 -> 北京时间 24h，含年月日，精确到 1ms。
    offset_ns: REALTIME - BOOTTIME 偏移量，从 clock_snapshot 获取。
    """
    if ns is None:
        return ""
    realtime_ns = ns + offset_ns
    sec = realtime_ns / 1e9
    dt = datetime.fromtimestamp(sec, tz=timezone.utc).astimezone(BEIJING)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _trace_stem(trace_path: str) -> str:
    """从 trace 完整路径提取不含扩展名的文件名。"""
    p = Path(trace_path)
    stem = p.stem
    if stem.endswith(".perfetto"):
        stem = Path(stem).stem
    return stem


def _build_trace_report(run: dict, summary: dict | None, jank_records: list[dict], offset_ns: int) -> list[str]:
    """为单个 trace 构建报告内容行。"""
    path = run["trace_path"]
    lines = [f"# Perfetto 解析报告（丢帧拆解）", ""]
    lines.append(f"## Trace: {path}")
    lines.append("")
    if summary:
        lines.append(f"- 丢帧次数 (jank_times): {summary['jank_times']}")
        lines.append(f"- 游戏帧数 (frame_num): {summary['frame_num']}")
        hz = summary.get("inferred_refresh_rate_hz")
        if hz is not None:
            lines.append(f"- 本次识别的刷新率: {hz} Hz")
        switches = summary.get("refresh_rate_switches") or []
        if isinstance(switches, str):
            try:
                switches = json.loads(switches)
            except (ValueError, TypeError):
                switches = []
        if not switches:
            lines.append("- 是否有刷新率切换: 否")
        else:
            lines.append("- 是否有刷新率切换: 是")
            lines.append("- 刷新率切换时间点:")
            for sw in switches:
                at_ns = sw.get("at_ns")
                from_hz = sw.get("from_hz", "?")
                to_hz = sw.get("to_hz", "?")
                ts_str = ns_to_beijing_ms(at_ns, offset_ns) if at_ns is not None else "—"
                lines.append(f"  - {ts_str}  {from_hz} Hz → {to_hz} Hz")
        max_buf = summary.get("max_buffer_count", 0)
        lines.append(f"- 最大 Buffer 数量: {max_buf}")
        start_ns = run.get("trace_start_ns")
        end_ns = run.get("trace_end_ns")
        if start_ns is not None and end_ns is not None and end_ns > start_ns:
            duration_sec = (end_ns - start_ns) / 1e9
            frame_num = summary["frame_num"]
            avg_fps = frame_num / duration_sec if duration_sec > 0 else 0.0
            lines.append(
                f"- Trace 时间范围 (北京): "
                f"{ns_to_beijing_ms(start_ns, offset_ns)} ~ "
                f"{ns_to_beijing_ms(end_ns, offset_ns)}"
            )
            lines.append(f"- Trace 时长: {duration_sec:.2f} 秒")
            lines.append(f"- 平均帧率: {avg_fps:.2f} FPS（总帧数 / 时长）")
        lines.append("")
    for jr in jank_records:
        jtype = jr.get("jank_type") or ""
        type_str = f" [{jtype}]" if jtype else ""
        lines.append(
            f"- 丢帧数 {jr['jank_num']}{type_str} | "
            f"App 起 {ns_to_beijing_ms(jr.get('ajt1_ns'), offset_ns)} ~ "
            f"止 {ns_to_beijing_ms(jr.get('ajt2_ns'), offset_ns)} | "
            f"SF 起 {ns_to_beijing_ms(jr.get('sjt1_ns'), offset_ns)} ~ "
            f"止 {ns_to_beijing_ms(jr.get('sjt2_ns'), offset_ns)}"
        )
    lines.append("")
    return lines


def build_base_info_section(
    trace_path: str,
    process_name: str | None,
    app_type: str,
    topology: dict,
    parse_result: dict,
) -> str:
    """生成 Phase 2 基础环境信息段落（FR-102）。"""
    lines = ["## 基础信息", ""]
    lines.append(f"- **Trace 文件**: `{trace_path}`")
    lines.append(f"- **目标进程**: {process_name or '(全局分析)'}")
    lines.append(f"- **App 类型**: {app_type}")

    clusters = topology.get("clusters", [])
    total_cpus = topology.get("total_cpu_count", 0)
    if clusters:
        lines.append(f"- **CPU 拓扑**: {total_cpus} 核")
        for cl in clusters:
            cpus_str = ", ".join(str(c) for c in cl.get("cpus", []))
            freq_ghz = cl.get("max_freq_khz", 0) / 1e6
            lines.append(f"  - {cl.get('type', '?')}: CPU [{cpus_str}], 最大频率 {freq_ghz:.2f} GHz")
    else:
        lines.append("- **CPU 拓扑**: 未知")

    hz = parse_result.get("inferred_refresh_rate_hz")
    if hz:
        lines.append(f"- **刷新率**: {hz} Hz")
    switches = parse_result.get("refresh_rate_switches", [])
    if switches:
        lines.append(f"- **刷新率切换**: {len(switches)} 次")

    jank_records = parse_result.get("jank_records", [])
    jank_times = parse_result.get("jank_times", len(jank_records))
    total_jank_num = sum(j.get("jank_num", 0) for j in jank_records)
    frame_num = parse_result.get("frame_num", 0)
    lines.append(f"- **丢帧次数**: {jank_times}")
    lines.append(f"- **总丢帧数**: {total_jank_num}")
    lines.append(f"- **游戏帧数**: {frame_num}")

    offset_ns = parse_result.get("realtime_offset_ns", 0)
    start_ns = parse_result.get("trace_start_ns")
    end_ns = parse_result.get("trace_end_ns")
    if start_ns and end_ns and end_ns > start_ns:
        dur_sec = (end_ns - start_ns) / 1e9
        avg_fps = frame_num / dur_sec if dur_sec > 0 else 0
        lines.append(
            f"- **Trace 时间范围**: "
            f"{ns_to_beijing_ms(start_ns, offset_ns)} ~ "
            f"{ns_to_beijing_ms(end_ns, offset_ns)} (北京时间)"
        )
        lines.append(f"- **Trace 时长**: {dur_sec:.2f} 秒")
        lines.append(f"- **平均帧率**: {avg_fps:.2f} FPS")

    max_buf = parse_result.get("max_buffer_count", 0)
    lines.append(f"- **最大 Buffer 数量**: {max_buf}")
    lines.append("")
    return "\n".join(lines)


def build_jank_overview_section(
    parse_result: dict,
    offset_ns: int = 0,
) -> str:
    """生成丢帧概览 + 丢帧列表段落。"""
    lines = ["## 丢帧概览", ""]
    jank_records = parse_result.get("jank_records", [])
    jank_times = parse_result.get("jank_times", len(jank_records))
    frame_num = parse_result.get("frame_num", 0)
    lines.append(f"- 丢帧次数: {jank_times}")
    lines.append(f"- 游戏帧数: {frame_num}")
    lines.append("")

    if jank_records:
        lines.append("## 丢帧列表")
        lines.append("")
        lines.append("| 序号 | 丢帧数 | 类型 | App 起始 | App 结束 | SF 起始 | SF 结束 |")
        lines.append("|------|--------|------|----------|----------|---------|---------|")
        for i, jr in enumerate(jank_records):
            jtype = _format_jank_type(jr.get("jank_type", ""))
            lines.append(
                f"| {i+1} | {jr.get('jank_num', 0)} | {jtype} | "
                f"{ns_to_beijing_ms(jr.get('ajt1_ns'), offset_ns)} | "
                f"{ns_to_beijing_ms(jr.get('ajt2_ns'), offset_ns)} | "
                f"{ns_to_beijing_ms(jr.get('sjt1_ns'), offset_ns)} | "
                f"{ns_to_beijing_ms(jr.get('sjt2_ns'), offset_ns)} |"
            )
        lines.append("")
    return "\n".join(lines)


def build_full_report(
    trace_path: str,
    process_name: str | None,
    app_type: str,
    topology: dict,
    parse_result: dict,
    analysis_result: dict,
    offset_ns: int = 0,
) -> str:
    """构建完整合并报告（--export 产出）。"""
    sections = []
    sections.append("# Perfetto 丢帧分析报告\n")

    sections.append(build_base_info_section(
        trace_path, process_name, app_type, topology, parse_result,
    ))

    sections.append(build_jank_overview_section(parse_result, offset_ns))

    # 整体分析段落
    summary = analysis_result.get("summary_analysis", {})
    if summary:
        sections.append(_build_summary_section(summary))

    # 逐帧分析段落
    per_jank = analysis_result.get("per_jank_analyses", [])
    if per_jank:
        sections.append(_build_per_jank_sections(per_jank, offset_ns))

    # 统计摘要
    if per_jank:
        sections.append(_build_statistics_summary(per_jank))

    return "\n".join(sections)


def _build_summary_section(summary: dict) -> str:
    """构建全 Trace 整体分析段落（FR-119）。"""
    lines = ["## 全 Trace 整体分析", ""]

    # CPU 整体状态
    cpu = summary.get("cpu", {})
    if cpu.get("cluster_utilization"):
        lines.append("### CPU 集群利用率")
        lines.append("")
        lines.append("| 集群 | 运行时间 (ms) | 利用率 |")
        lines.append("|------|--------------|--------|")
        for cluster, info in cpu["cluster_utilization"].items():
            running_ms = round(info.get("running_time_ns", 0) / 1e6, 1)
            pct = info.get("avg_pct", 0)
            lines.append(f"| {cluster} | {running_ms} | {pct}% |")
        lines.append("")

    sched = cpu.get("sched_latency", {})
    if sched:
        lines.append("### 调度延迟分布")
        lines.append("")
        lines.append("> 调度延迟：线程从「可运行」到「实际获得 CPU 执行」的等待时间。")
        lines.append("> Pxx 表示百分位数，例如 P50 = 50% 的调度延迟 ≤ 该值，P99 = 99% ≤ 该值。")
        lines.append("")
        lines.append(f"- P50（中位数）: {_us_to_ms(sched.get('p50_us', 0))} ms")
        lines.append(f"- P90（90% 分位）: {_us_to_ms(sched.get('p90_us', 0))} ms")
        lines.append(f"- P99（99% 分位）: {_us_to_ms(sched.get('p99_us', 0))} ms")
        lines.append(f"- MAX（最大值）: {_us_to_ms(sched.get('max_us', 0))} ms")
        lines.append("")

    frm = summary.get("frame_rate_matching", {})
    if frm:
        lines.append("### 帧率匹配")
        lines.append("")
        hz = frm.get('device_refresh_hz', 0)
        lines.append(f"- 设备刷新率: {hz} Hz")
        lines.append(f"- 实际帧率: {frm.get('actual_fps', 0)} FPS")
        lines.append(f"- 匹配度: {frm.get('match_pct', 0)}%")
        lines.append(f"- 帧间隔变异系数: {frm.get('interval_cv_pct', 0)}%")
        t_ms = round(1000 / hz, 2) if hz else 0
        hist = frm.get("histogram", {})
        if hist:
            lines.append(f"- 帧间隔分布（T = 1 个 VSync 周期 ≈ {t_ms} ms）:")
            bucket_names = {
                "0_to_0.5T": f"< 0.5T（{round(t_ms * 0.5, 1)} ms 以下，提前完成）",
                "0.5T_to_T": f"0.5T ~ T（正常范围）",
                "T_to_1.5T": f"T ~ 1.5T（轻微超时，掉 1 帧）",
                "1.5T_to_2T": f"1.5T ~ 2T（掉 1~2 帧）",
                "2T_to_3T": f"2T ~ 3T（掉 2~3 帧，明显卡顿）",
                "3T_plus": f"> 3T（严重卡顿，掉 3+ 帧）",
            }
            for bucket, count in hist.items():
                label = bucket_names.get(bucket, bucket)
                lines.append(f"  - {label}: {count} 帧")
        lines.append("")

    binder_h = summary.get("binder_health", {})
    if binder_h:
        lines.append("### Binder 健康度")
        lines.append("")
        lines.append("> Binder：Android 进程间通信机制。慢 Binder 会阻塞渲染线程导致丢帧。")
        lines.append("")
        lines.append(f"- Binder 事务总数: {binder_h.get('total_txn', 0)}")
        lines.append(f"- 慢事务数量（> 阈值）: {binder_h.get('slow_txn_count', 0)}")
        lines.append(f"- 慢事务占比: {binder_h.get('slow_txn_pct', 0)}%")
        lines.append("")

    io_h = summary.get("io_health", {})
    if io_h:
        lines.append("### IO 健康度")
        lines.append("")
        lines.append("> D-State 阻塞：线程因等待磁盘 IO 完成而被内核挂起，无法被中断。")
        lines.append("")
        lines.append(f"- D-State 总阻塞时长: {io_h.get('d_state_total_ms', 0)} ms")
        lines.append(f"- 关键线程 IO 阻塞次数: {io_h.get('critical_thread_io_blocks', 0)}")
        lines.append("")

    gc_h = summary.get("gc_health", {})
    if gc_h:
        lines.append("### GC 健康度")
        lines.append("")
        lines.append("> GC（垃圾回收）：Java/ART 运行时的自动内存回收，可能造成短暂停顿（STW）。")
        lines.append("")
        lines.append(f"- GC 事件数: {gc_h.get('total_count', 0)}")
        lines.append(f"- GC 总耗时: {gc_h.get('total_dur_ms', 0)} ms")
        lines.append("")

    lock_h = summary.get("lock_health", {})
    if lock_h:
        lines.append("### 锁竞争健康度")
        lines.append("")
        lines.append("> Java Monitor 锁竞争：线程等待获取另一个线程持有的锁，造成阻塞。")
        lines.append("")
        lines.append(f"- 锁竞争次数: {lock_h.get('total_count', 0)}")
        lines.append(f"- 总等待时长: {lock_h.get('total_wait_ms', 0)} ms")
        lines.append("")

    # CPU 频率 vs 帧率
    corr = summary.get("cpu_freq_vs_framerate", {})
    if corr.get("normal_window_avg_freq_khz"):
        lines.append("### CPU 频率 vs 帧率相关性")
        lines.append("")
        lines.append(f"- 正常窗口平均频率: {corr.get('normal_window_avg_freq_khz', 0)} KHz")
        lines.append(f"- 丢帧窗口平均频率: {corr.get('jank_window_avg_freq_khz', 0)} KHz")
        lines.append(f"- 差异: {corr.get('diff_pct', 0)}%")
        lines.append(f"- 频率不足: {'是' if corr.get('freq_insufficient') else '否'}")
        lines.append("")

    # 大小核失衡
    imb = summary.get("big_little_imbalance", {})
    if "critical_thread_little_pct" in imb:
        lines.append("### 大小核利用率失衡")
        lines.append("")
        lines.append(f"- 关键线程在小核运行占比: {imb.get('critical_thread_little_pct', 0)}%")
        lines.append(f"- 失衡: {'是' if imb.get('imbalanced') else '否'}")
        lines.append("")

    return "\n".join(lines)


def _aggregate_thread_states(states: list[dict]) -> list[dict]:
    """按 tid 聚合线程状态，返回汇总列表（按 Running 时间降序）。"""
    threads: dict[int, dict] = {}
    for ts in states:
        utid = ts.get("utid", 0)
        if utid not in threads:
            threads[utid] = {
                "utid": utid,
                "tid": ts.get("tid", ""),
                "pid": ts.get("pid", ""),
                "thread_name": ts.get("thread_name", ""),
                "process_name": ts.get("process_name", ""),
                "running_ns": 0,
                "runnable_ns": 0,
                "sleep_ns": 0,
                "d_state_ns": 0,
                "idle_ns": 0,
                "cpu_time": {},  # cpu_id -> ns
                "blocked_funcs": set(),
            }
        t = threads[utid]
        dur = ts.get("dur_ns", 0)
        state = ts.get("state", "")
        if state == "Running":
            t["running_ns"] += dur
            cpu = ts.get("cpu")
            if cpu is not None:
                t["cpu_time"][cpu] = t["cpu_time"].get(cpu, 0) + dur
        elif state in ("R", "R+"):
            t["runnable_ns"] += dur
        elif state == "S":
            t["sleep_ns"] += dur
        elif state == "D":
            t["d_state_ns"] += dur
            bf = ts.get("blocked_function")
            if bf:
                t["blocked_funcs"].add(bf)
        elif state == "I":
            t["idle_ns"] += dur

    result = []
    for t in threads.values():
        # CPU 核分布：按时间降序排列
        cpu_sorted = sorted(t["cpu_time"].items(), key=lambda x: x[1], reverse=True)
        if cpu_sorted:
            cpu_parts = []
            for cpu, ns in cpu_sorted:
                cpu_parts.append(f"CPU{cpu}({round(ns / 1e6, 2)}ms)")
            cpu_dist = " ".join(cpu_parts)
        else:
            cpu_dist = "-"

        bf_list = sorted(t["blocked_funcs"])
        result.append({
            "pid": t["pid"] or "-",
            "process_name": t["process_name"] or "-",
            "tid": t["tid"] or "-",
            "thread_name": t["thread_name"] or "-",
            "running_ms": round(t["running_ns"] / 1e6, 3),
            "cpu_dist": cpu_dist,
            "runnable_ms": round(t["runnable_ns"] / 1e6, 3),
            "sleep_ms": round(t["sleep_ns"] / 1e6, 3),
            "d_state_ms": round(t["d_state_ns"] / 1e6, 3),
            "blocked_funcs": ", ".join(bf_list) if bf_list else "-",
        })

    result.sort(key=lambda x: x["running_ms"], reverse=True)
    return result


def _build_per_jank_sections(per_jank: list[dict], offset_ns: int = 0) -> str:
    """构建逐帧归因分析段落（FR-112）。"""
    lines = [f"## 逐帧归因分析（Top {len(per_jank)}）", ""]

    for jd in per_jank:
        idx = jd.get("jank_index", 0)
        jnum = jd.get("jank_num", 0)
        jtype = jd.get("jank_type", "")
        ws = jd.get("window_start_ns", 0)
        we = jd.get("window_end_ns", 0)

        jtype_label = _format_jank_type(jtype)
        lines.append(f"### Jank #{idx + 1}（丢帧数: {jnum}, 类型: {jtype_label}）")
        lines.append("")
        jank_dur_ms = round((we - ws) / 1e6, 3) if we > ws else 0
        lines.append(f"- 分析窗口: {ns_to_beijing_ms(ws, offset_ns)} ~ {ns_to_beijing_ms(we, offset_ns)}")
        lines.append(f"- 丢帧时长: {jank_dur_ms} ms")
        lines.append(f"- 窗口范围: {ws} ~ {we} ns")
        lines.append("")

        # 线程状态
        thread_data = jd.get("thread", {})
        if thread_data and thread_data.get("thread_states"):
            lines.append("#### 线程状态汇总（按线程聚合）")
            lines.append("")
            lines.append("> Running=执行中, R/R+=等待调度, S=睡眠, D=不可中断（IO 等待）, I=空闲")
            lines.append("> CPU 核分布按该线程在各核上的运行时间排序")
            lines.append("")
            agg = _aggregate_thread_states(thread_data["thread_states"])
            lines.append("| PID | 进程名 | TID | 线程名 | Running (ms) | CPU 核分布 | R/R+ (ms) | S (ms) | D (ms) | 阻塞函数 |")
            lines.append("|-----|--------|-----|--------|-------------|-----------|----------|--------|--------|---------|")
            for t in agg[:30]:
                lines.append(
                    f"| {t['pid']} | {t['process_name']} | {t['tid']} | {t['thread_name']} | "
                    f"{t['running_ms']} | {t['cpu_dist']} | {t['runnable_ms']} | "
                    f"{t['sleep_ms']} | {t['d_state_ms']} | {t['blocked_funcs']} |"
                )
            if len(agg) > 30:
                lines.append(f"| ... | ... | ... | 共 {len(agg)} 个线程 | ... | ... | ... | ... | ... | ... |")
            lines.append("")

            # Waker 链
            chains = thread_data.get("waker_chains", [])
            if chains:
                lines.append("#### Block/Waker 链")
                lines.append("")
                for chain_data in chains[:10]:
                    bt = chain_data.get("blocked_thread", "")
                    dur = round(chain_data.get("blocked_dur_ns", 0) / 1e6, 3)
                    lines.append(f"- **{bt}** 阻塞 {dur} ms")
                    for ci in chain_data.get("chain", []):
                        lines.append(f"  → {ci.get('thread', '')} ({ci.get('process', '')})")
                lines.append("")

        # CPU 分析
        cpu_data = jd.get("cpu", {})
        if cpu_data:
            freq = cpu_data.get("freq_analysis", {})
            if freq.get("ramp_ups"):
                lines.append("#### CPU 频率爬升")
                lines.append("")
                lines.append("> 频率爬升：CPU 从低频逐步提升到高频的过程，每步之间有响应延迟。")
                lines.append("")
                for ru in freq["ramp_ups"]:
                    total_dur = ru.get("total_dur_us", 0)
                    dur_ms = round(total_dur / 1000, 3) if total_dur else 0
                    lines.append(
                        f"- **CPU{ru.get('cpu', '?')}** ({ru.get('cluster', '?')}): "
                        f"{ru.get('start_freq_khz', 0)} → {ru.get('end_freq_khz', 0)} KHz, "
                        f"{ru.get('steps', 0)} 步, 总耗时 {dur_ms} ms"
                    )
                    for sd in ru.get("step_details", []):
                        lines.append(
                            f"  - {sd.get('from_khz', 0)} → {sd.get('to_khz', 0)} KHz "
                            f"（{_us_to_ms(sd.get('step_dur_us', 0))} ms）"
                        )
                lines.append("")

            cluster = cpu_data.get("cluster_analysis", {})
            if cluster.get("cluster_pct"):
                lines.append("#### 大小核调度")
                lines.append("")
                lines.append("")
                for cl, pct in cluster["cluster_pct"].items():
                    lines.append(f"- {cl}: {pct}%")
                cross = cluster.get("migrations_cross_cluster", 0)
                same = cluster.get("migrations_same_cluster", 0)
                if cross or same:
                    lines.append(f"- 跨集群迁移: {cross} 次, 同集群迁移: {same} 次")
                details = cluster.get("migration_details", [])
                if details:
                    # 按线程聚合迁移方向统计
                    thread_mig: dict[str, dict] = {}
                    for d in details:
                        tn = d.get("thread_name", "?")
                        utid = d.get("utid", 0)
                        key = f"{utid}:{tn}"
                        if key not in thread_mig:
                            thread_mig[key] = {"thread_name": tn, "utid": utid, "dirs": {}, "total": 0}
                        fc = d.get("from_cluster", "?")
                        tc = d.get("to_cluster", "?")
                        d_key = f"{fc} → {tc}"
                        thread_mig[key]["dirs"][d_key] = thread_mig[key]["dirs"].get(d_key, 0) + 1
                        thread_mig[key]["total"] += 1

                    # 按 thread 聚合表的 running 时间排序
                    thread_data_for_sort = jd.get("thread", {})
                    running_by_utid: dict[int, float] = {}
                    if thread_data_for_sort and thread_data_for_sort.get("thread_states"):
                        for ts in thread_data_for_sort["thread_states"]:
                            if ts.get("state") == "Running":
                                u = ts.get("utid", 0)
                                running_by_utid[u] = running_by_utid.get(u, 0) + ts.get("dur_ns", 0)

                    mig_list = sorted(
                        thread_mig.values(),
                        key=lambda x: running_by_utid.get(x["utid"], 0),
                        reverse=True,
                    )

                    lines.append("")
                    lines.append("**跨集群迁移详情：**")
                    lines.append("")
                    lines.append("| 线程名 | Running (ms) | 迁移方向 | 次数 |")
                    lines.append("|--------|-------------|---------|------|")
                    for m in mig_list[:15]:
                        utid = m["utid"]
                        running_ms = round(running_by_utid.get(utid, 0) / 1e6, 3)
                        for d_key, cnt in sorted(m["dirs"].items(), key=lambda x: x[1], reverse=True):
                            lines.append(f"| {m['thread_name']} | {running_ms} | {d_key} | {cnt} |")
                lines.append("")

            sched = cpu_data.get("sched_latency", {})
            if sched.get("stats"):
                s = sched["stats"]
                lines.append("#### 调度延迟")
                lines.append("")
                lines.append(f"- P50（中位数）: {_us_to_ms(s.get('p50_us', 0))} ms, P90: {_us_to_ms(s.get('p90_us', 0))} ms, MAX: {_us_to_ms(s.get('max_us', 0))} ms")
                if sched.get("anomalies"):
                    lines.append(f"- 异常延迟（> 阈值）: {sched.get('anomaly_count', 0)} 次")
                lines.append("")

        # Binder
        binder_data = jd.get("binder", {})
        if binder_data and binder_data.get("binder_calls"):
            slow_count = binder_data.get("slow_binder_count", 0)
            lines.append(f"#### Binder 调用（慢调用: {slow_count}）")
            lines.append("")
            for bc in binder_data["binder_calls"][:10]:
                slow_mark = " ⚠" if bc.get("is_slow") else ""
                lines.append(
                    f"- {bc.get('caller_thread', '')} → {bc.get('callee_process', '')}: "
                    f"{bc.get('dur_ms', 0)} ms{slow_mark}"
                )
            lines.append("")

        # IO
        io_data = jd.get("io", {})
        if io_data and io_data.get("io_blocks"):
            total_ms = round(io_data.get("io_block_total_ns", 0) / 1e6, 3)
            lines.append(f"#### IO 阻塞（总时长: {total_ms} ms）")
            lines.append("")
            for iob in io_data["io_blocks"][:10]:
                dur_ms = round(iob.get("dur_ns", iob.get("dur_us", 0) * 1000) / 1e6, 3)
                lines.append(
                    f"- {iob.get('thread_name', '')}: {dur_ms} ms "
                    f"({iob.get('category', '')}) [{iob.get('blocked_function', '')}]"
                )
            lines.append("")

        # GC
        gc_data = jd.get("gc", {})
        if gc_data and gc_data.get("gc_events"):
            lines.append(f"#### GC 事件（{gc_data.get('gc_count', 0)} 次）")
            lines.append("")
            for gc in gc_data["gc_events"][:5]:
                stw = " [STW]" if gc.get("is_stw") else ""
                lines.append(f"- {gc.get('name', '')}: {gc.get('dur_ms', 0)} ms{stw}")
            lines.append("")

        # GPU
        gpu_data = jd.get("gpu", {})
        if gpu_data and gpu_data.get("draw_frame_stats"):
            s = gpu_data["draw_frame_stats"]
            lines.append(f"#### GPU 渲染")
            lines.append("")
            lines.append(f"- DrawFrame 平均: {_us_to_ms(s.get('avg_us', 0))} ms, P99: {_us_to_ms(s.get('p99_us', 0))} ms")
            lines.append("")

        # 锁竞争
        lock_data = jd.get("lock", {})
        if lock_data and lock_data.get("contentions"):
            severe = lock_data.get("severe_count", 0)
            lines.append(f"#### 锁竞争（严重: {severe}）")
            lines.append("")
            for lc in lock_data["contentions"][:5]:
                lines.append(
                    f"- {lc.get('blocked_thread', '')} 等待 {lc.get('blocking_thread', '')}: "
                    f"{lc.get('dur_ms', 0)} ms"
                )
            lines.append("")

    return "\n".join(lines)


def _build_statistics_summary(per_jank: list[dict]) -> str:
    """构建逐帧分析统计摘要（FR-113）。"""
    lines = ["## 统计摘要", ""]

    # 调度延迟汇总
    all_latencies: list[float] = []
    slow_binders: list[dict] = []
    io_blocks: list[dict] = []
    gc_total = 0
    gc_count = 0
    lock_total = 0
    lock_count = 0

    for jd in per_jank:
        cpu_data = jd.get("cpu", {})
        sched = cpu_data.get("sched_latency", {}).get("stats", {})
        if sched.get("max_us"):
            all_latencies.append(sched["max_us"])

        binder_data = jd.get("binder", {})
        for bc in binder_data.get("binder_calls", []):
            if bc.get("is_slow"):
                slow_binders.append(bc)

        io_data = jd.get("io", {})
        for iob in io_data.get("io_blocks", []):
            io_blocks.append(iob)

        gc_data = jd.get("gc", {})
        gc_count += gc_data.get("gc_count", 0)
        gc_total += gc_data.get("gc_total_dur_ns", 0)

        lock_data = jd.get("lock", {})
        lock_count += lock_data.get("contention_count", 0)
        lock_total += lock_data.get("total_wait_ns", 0)

    if all_latencies:
        lines.append("### 调度延迟分布")
        lines.append(f"- 最大值: {_us_to_ms(max(all_latencies))} ms")
        lines.append(f"- 平均值: {_us_to_ms(round(sum(all_latencies) / len(all_latencies), 1))} ms")
        lines.append("")

    if slow_binders:
        lines.append("### 慢 Binder Top-5")
        lines.append("")
        sorted_binders = sorted(slow_binders, key=lambda x: x.get("dur_ns", 0), reverse=True)
        for bc in sorted_binders[:5]:
            lines.append(
                f"- {bc.get('caller_thread', '')} → {bc.get('callee_process', '')}: "
                f"{bc.get('dur_ms', 0)} ms"
            )
        lines.append("")

    if io_blocks:
        lines.append("### IO 阻塞 Top-5")
        lines.append("")
        sorted_io = sorted(io_blocks, key=lambda x: x.get("dur_ns", 0), reverse=True)
        for iob in sorted_io[:5]:
            lines.append(
                f"- {iob.get('thread_name', '')}: {_us_to_ms(iob.get('dur_us', 0))} ms "
                f"[{iob.get('blocked_function', '')}]"
            )
        lines.append("")

    if gc_count:
        lines.append(f"### GC 汇总")
        lines.append(f"- 事件数: {gc_count}")
        lines.append(f"- 总时长: {round(gc_total / 1e6, 2)} ms")
        lines.append("")

    if lock_count:
        lines.append(f"### 锁竞争汇总")
        lines.append(f"- 竞争次数: {lock_count}")
        lines.append(f"- 总等待: {round(lock_total / 1e6, 2)} ms")
        lines.append("")

    return "\n".join(lines)


def export_to_markdown(db_path: str, output_dir: str) -> bool:
    """将 DB 中每个 trace_run 导出为独立的 Markdown 文件（按 trace 文件名命名）。"""
    import os

    from . import storage

    conn = storage.get_connection(db_path)
    runs = storage.list_trace_runs(conn)
    if not runs:
        conn.close()
        return True

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for run in runs:
        tid = run["trace_id"]
        offset_ns = run.get("realtime_offset_ns") or 0
        summary = storage.get_trace_summary(conn, tid)
        jank_records = storage.get_jank_records(conn, tid)
        lines = _build_trace_report(run, summary, jank_records, offset_ns)

        stem = _trace_stem(run["trace_path"])
        report_path = out / f"{stem}_jank_report.md"
        report_path.write_text("\n".join(lines), encoding="utf-8")

    conn.close()
    return True
