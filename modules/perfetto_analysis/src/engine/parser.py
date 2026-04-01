# -*- coding: utf-8 -*-
"""
解析 Perfetto trace：使用 TraceProcessor 查询 vsync/buffer，按 SOP 计算丢帧并产出可写入 storage 的结构。
当 trace 中缺少 vsync 或 buffer 相关数据时，在结果中标记缺失范围，不伪造数据。

刷新率识别规则（按 spec 澄清）：
- 取 vsync-sf 间隔中的最短常见间隔作为基准周期（如 6.9ms→144Hz，8.3ms→120Hz，16.6ms→60Hz）。
- 出现约 2x 的间隔视为丢帧（该帧 stand_vsync 仍为 1x 周期），不是刷新率切换。
- 仅当连续、均匀（中位数接近目标周期）的不同间隔持续 >1 秒时，才判定为刷新率切换。
"""
from __future__ import annotations

import bisect
import statistics
import sys
from pathlib import Path
from typing import Any

# 标准刷新率 (Hz) -> 周期(ms)，SOP
VSYNC_MS = {
    30: 1000 / 30,
    60: 1000 / 60,
    90: 1000 / 90,
    120: 1000 / 120,
    144: 1000 / 144,
    165: 1000 / 165,
    185: 1000 / 185,
}
STANDARD_HZ = sorted(VSYNC_MS.keys())

RATE_SWITCH_MIN_DURATION_NS = 1_000_000_000  # 刷新率切换最短持续时长：1 秒

_popen_patched = False


def _patch_popen_no_window() -> None:
    """PyInstaller --noconsole 模式下 monkey-patch subprocess.Popen。

    perfetto 的 load_shell 使用 CREATE_NEW_PROCESS_GROUP 但不带
    CREATE_NO_WINDOW，导致子进程弹出黑色控制台并可能因无效句柄崩溃。
    此补丁在 frozen 环境中自动追加 CREATE_NO_WINDOW 标志。
    """
    global _popen_patched
    if _popen_patched or not getattr(sys, "frozen", False) or sys.platform != "win32":
        return
    _popen_patched = True

    import subprocess
    _OrigPopen = subprocess.Popen

    class _NWPopen(_OrigPopen):  # type: ignore[misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            flags = kwargs.get("creationflags", 0)
            flags |= subprocess.CREATE_NO_WINDOW
            kwargs["creationflags"] = flags
            super().__init__(*args, **kwargs)

    subprocess.Popen = _NWPopen  # type: ignore[misc]


def _get_stand_vsync_ms(refresh_rate_hz: int | float) -> float:
    if refresh_rate_hz in VSYNC_MS:
        return VSYNC_MS[int(refresh_rate_hz)]
    return 1000.0 / float(refresh_rate_hz)


def _nearest_standard_hz(period_ms: float) -> int:
    """将一个周期(ms)匹配到最近的标准刷新率 Hz。"""
    best_hz = 60
    best_diff = abs(period_ms - VSYNC_MS[60])
    for hz in STANDARD_HZ:
        d = abs(period_ms - VSYNC_MS[hz])
        if d < best_diff:
            best_diff = d
            best_hz = hz
    return best_hz


def _base_period_of_window(intervals_ms: list[float]) -> float:
    """
    从一段间隔(ms)中提取基准周期。
    对每个标准周期 T，将间隔中落在 [T*0.85, T*1.15] 内的视为 1x 匹配，
    落在 [T*1.85, T*2.15] 内的视为 2x（丢帧）匹配。
    取 (1x+2x) 最多且 1x>0 的 Hz 为基准；同分时取 1x 更多者。
    若都无有效匹配，回退到全量中位数匹配最近标准刷新率。
    """
    if not intervals_ms:
        return VSYNC_MS[60]
    best_hz = -1
    best_total = 0
    best_1x = 0
    for hz in STANDARD_HZ:
        t = VSYNC_MS[hz]
        count_1x = sum(1 for x in intervals_ms if t * 0.85 <= x <= t * 1.15)
        count_2x = sum(1 for x in intervals_ms if t * 1.85 <= x <= t * 2.15)
        total = count_1x + count_2x
        if count_1x > 0 and (total > best_total or (total == best_total and count_1x > best_1x)):
            best_total = total
            best_1x = count_1x
            best_hz = hz
    if best_hz > 0:
        return VSYNC_MS[best_hz]
    med = statistics.median(intervals_ms)
    return VSYNC_MS[_nearest_standard_hz(med)]


def _classify_window_to_hz(intervals_ms: list[float]) -> int:
    """
    对一段间隔(ms)判断刷新率。
    取最短常见间隔作为基准周期（如 6.9ms→144Hz，8.3ms→120Hz）。
    出现约 2x 的间隔是丢帧，不是刷新率切换。
    使用中位数判定：中位数接近目标周期即视为均匀。
    """
    if not intervals_ms:
        return 60
    base_ms = _base_period_of_window(intervals_ms)
    return _nearest_standard_hz(base_ms)


def _segment_and_switches(
    vt_list: list[int],
) -> tuple[list[tuple[int, int, int]], list[dict[str, Any]]]:
    """
    按间隔分段并得到刷新率切换点。
    规则：仅当连续、均匀（中位数接近目标周期）的不同间隔持续 >1 秒时，才判定为刷新率切换。
    返回 (segments, switches)：
      segments = [(start_interval_idx, end_interval_idx, hz)]
      switches = [{"at_ns": int, "from_hz": int, "to_hz": int}]
    """
    if len(vt_list) < 2:
        return ([(0, 0, 60)], [])
    n = len(vt_list) - 1
    intervals_ms = [(vt_list[i + 1] - vt_list[i]) / 1e6 for i in range(n)]

    # 阶段 1：为每个间隔分配初步 Hz（基于局部窗口的基准周期）
    WINDOW = 20
    rate_per_idx: list[int] = []
    for i in range(n):
        lo = max(0, i - WINDOW // 2)
        hi = min(n, i + WINDOW // 2 + 1)
        rate_per_idx.append(_classify_window_to_hz(intervals_ms[lo:hi]))

    # 阶段 2：合并连续同 rate 为候选段
    raw_segments: list[tuple[int, int, int]] = []
    i = 0
    while i < n:
        hz = rate_per_idx[i]
        j = i + 1
        while j < n and rate_per_idx[j] == hz:
            j += 1
        raw_segments.append((i, j, hz))
        i = j

    # 阶段 3：过滤——段持续时长 <1s 的非首段回退到前一段的 Hz（不视为真正切换）
    segments: list[tuple[int, int, int]] = []
    for seg_idx, (start, end, hz) in enumerate(raw_segments):
        duration_ns = vt_list[end] - vt_list[start]
        if seg_idx == 0:
            segments.append((start, end, hz))
        elif duration_ns < RATE_SWITCH_MIN_DURATION_NS:
            prev_start, prev_end, prev_hz = segments[-1]
            segments[-1] = (prev_start, end, prev_hz)
        else:
            segments.append((start, end, hz))

    # 阶段 4：再次合并可能因回退而相邻且同 Hz 的段
    merged: list[tuple[int, int, int]] = [segments[0]]
    for seg in segments[1:]:
        if seg[2] == merged[-1][2]:
            merged[-1] = (merged[-1][0], seg[1], seg[2])
        else:
            merged.append(seg)
    segments = merged

    # 阶段 5：提取切换点
    switches: list[dict[str, Any]] = []
    for seg_idx in range(1, len(segments)):
        start_idx, _end_idx, to_hz = segments[seg_idx]
        _s, _e, from_hz = segments[seg_idx - 1]
        at_ns = vt_list[start_idx]
        switches.append({"at_ns": at_ns, "from_hz": from_hz, "to_hz": to_hz})
    return segments, switches


def _stand_vsync_ms_per_cycle(
    vt_list: list[int],
    segments: list[tuple[int, int, int]],
) -> list[float]:
    """每个 vsync 周期（间隔）对应的 stand_vsync_ms。"""
    n = len(vt_list) - 1
    out: list[float] = [VSYNC_MS[60]] * n
    for start, end, hz in segments:
        ms = VSYNC_MS[hz]
        for i in range(start, min(end, n)):
            out[i] = ms
    return out


def _dominant_hz_by_duration(
    vt_list: list[int],
    segments: list[tuple[int, int, int]],
) -> int:
    """按持续时间取占比最大的刷新率。"""
    duration_by_hz: dict[int, int] = {}
    for start, end, hz in segments:
        dur = vt_list[min(end, len(vt_list) - 1)] - vt_list[start]
        duration_by_hz[hz] = duration_by_hz.get(hz, 0) + dur
    if not duration_by_hz:
        return 60
    return max(duration_by_hz, key=lambda h: duration_by_hz[h])


def parse_trace_with_tp(
    trace_path: str | Path,
    refresh_rate_preset: int | float = 60,
    process_filter: str | None = None,
) -> tuple[dict[str, Any], Any]:
    """
    解析单个 trace 文件，返回 (result_dict, tp)。
    调用方负责 tp.close()，以便 Phase 2 复用同一 TraceProcessor 实例。
    """
    trace_path = Path(trace_path)
    if not trace_path.is_file():
        raise FileNotFoundError(f"trace 文件不存在: {trace_path}")

    try:
        from perfetto.trace_processor import TraceProcessor
    except ImportError as e:
        raise RuntimeError("请安装 perfetto: pip install perfetto") from e

    _patch_popen_no_window()

    result = {
        "trace_path": str(trace_path.resolve()),
        "parsed_at_ns": None,
        "stand_vsync_ms": _get_stand_vsync_ms(refresh_rate_preset),
        "inferred_refresh_rate_hz": None,
        "refresh_rate_switches": [],
        "mixed_refresh_rates": False,
        "refresh_rate_segments": [],
        "trace_start_ns": None,
        "trace_end_ns": None,
        "realtime_offset_ns": 0,
        "vsync_cycles": [],
        "jank_records": [],
        "jank_times": 0,
        "frame_num": 0,
        "max_buffer_count": 0,
        "missing_ranges": [],
    }

    try:
        tp = TraceProcessor(trace=str(trace_path))
    except Exception as e:
        raise RuntimeError(f"无法打开 trace 或格式非 Perfetto: {e}") from e

    try:
        # BOOTTIME→REALTIME 偏移量：通过 clock_snapshot 获取
        try:
            rt_rows = list(tp.query(
                "SELECT clock_value FROM clock_snapshot "
                "WHERE clock_id = 1 AND snapshot_id = 0 LIMIT 1"
            ))
            bt_rows = list(tp.query(
                "SELECT clock_value FROM clock_snapshot "
                "WHERE clock_id = 6 AND snapshot_id = 0 LIMIT 1"
            ))
            if rt_rows and bt_rows:
                result["realtime_offset_ns"] = int(rt_rows[0].clock_value) - int(bt_rows[0].clock_value)
        except Exception:
            pass

        # 尝试获取 vsync 相关时间戳：先查 slice+track，若无则查 counter（Android VSYNC-app/VSYNC-sf 常在 counter_track）
        vt_list = []
        q_vsync_slice = """
        SELECT s.ts as ts
        FROM slice s
        JOIN track t ON s.track_id = t.id
        WHERE (t.name GLOB '*[Vv]sync*' OR t.name GLOB '*VSYNC*' OR t.name GLOB '*Choreographer*' OR t.name GLOB '*Display*')
        ORDER BY s.ts
        """
        try:
            for row in tp.query(q_vsync_slice):
                vt_list.append(row.ts)
        except Exception:
            pass
        if not vt_list:
            try:
                # 仅使用 VSYNC-sf（SurfaceFlinger vsync），不使用 VSYNC-app
                q_vsync_counter = """
                SELECT ts FROM counter
                WHERE track_id IN (SELECT id FROM counter_track WHERE name = 'VSYNC-sf')
                ORDER BY ts
                """
                for row in tp.query(q_vsync_counter):
                    vt_list.append(row.ts)
                if vt_list:
                    vt_list = sorted(set(vt_list))
            except Exception:
                pass

        # BufferTX counter 查询：选择单一 BufferTX 轨道（避免多轨道 delta 混淆）
        # 优先选含 SurfaceView 的轨道（游戏 layer），否则取事件最多的轨道
        buffer_raw: list[tuple[int, int]] = []
        _track_queries = [
            # 优先：process_counter_track（有 upid）+ SurfaceFlinger 进程过滤
            """SELECT pct.id, pct.name FROM process_counter_track pct
               JOIN process p ON pct.upid = p.upid
               WHERE pct.name GLOB '*BufferTX*' AND p.name = 'surfaceflinger'""",
            # 降级 1：process_counter_track 不过滤进程名
            """SELECT id, name FROM process_counter_track
               WHERE name GLOB '*BufferTX*'""",
            # 降级 2：counter_track
            """SELECT id, name FROM counter_track
               WHERE name GLOB '*BufferTX*'""",
        ]
        buffer_track_id: int | None = None
        buffer_track_name: str = ""
        for q_trk in _track_queries:
            try:
                tracks = [(row.id, row.name) for row in tp.query(q_trk)]
                if not tracks:
                    continue
                # 若指定了 process_filter，优先匹配轨道名中包含该进程/包名的轨道
                if process_filter:
                    pf = [t for t in tracks if process_filter in t[1]]
                    if pf:
                        buffer_track_id = pf[0][0]
                        buffer_track_name = pf[0][1]
                        break
                # 其次选含 SurfaceView 的轨道（游戏 layer）
                sv = [t for t in tracks if "SurfaceView" in t[1]]
                if sv:
                    buffer_track_id = sv[0][0]
                    buffer_track_name = sv[0][1]
                else:
                    buffer_track_id = tracks[0][0]
                    buffer_track_name = tracks[0][1]
                break
            except Exception:
                continue

        if buffer_track_id is not None:
            q_buf_data = f"""SELECT c.ts, c.value FROM counter c
                             WHERE c.track_id = {buffer_track_id}
                             ORDER BY c.ts"""
            try:
                buffer_raw = [(row.ts, int(row.value)) for row in tp.query(q_buf_data)]
            except Exception:
                buffer_raw = []

        # 构建 delta 事件列表与二分查找索引
        buffer_events: list[dict[str, Any]] = []
        for i, (ts, val) in enumerate(buffer_raw):
            prev_val = buffer_raw[i - 1][1] if i > 0 else val
            delta = val - prev_val
            if delta != 0:
                buffer_events.append({"ts": ts, "value": val, "delta": delta})
        buffer_raw_ts = [e[0] for e in buffer_raw]
        buffer_raw_vals = [e[1] for e in buffer_raw]
        buffer_ev_ts = [e["ts"] for e in buffer_events]
        result["max_buffer_count"] = max(buffer_raw_vals) if buffer_raw_vals else 0
        result["buffer_track_name"] = buffer_track_name

        # 若完全没有 vsync 或 buffer 数据，记录缺失范围（用 trace 时间范围近似）
        try:
            bounds = list(tp.query("SELECT MIN(ts) as mn, MAX(ts) as mx FROM slice"))
            if bounds and bounds[0].mn is not None:
                start_ns, end_ns = int(bounds[0].mn), int(bounds[0].mx)
            else:
                start_ns, end_ns = 0, 0
        except Exception:
            start_ns, end_ns = 0, 0

        if not vt_list:
            result["missing_ranges"].append({
                "start_ns": start_ns,
                "end_ns": end_ns,
                "reason": "trace 中缺少 vsync 相关数据（无匹配 slice/track）",
            })
        if not buffer_raw and vt_list:
            result["missing_ranges"].append({
                "start_ns": start_ns,
                "end_ns": end_ns,
                "reason": "trace 中缺少 BufferTX counter 数据（SurfaceFlinger 进程下无匹配 counter_track）",
            })

        # 若有 vsync 时间戳，按 SOP 生成周期与丢帧；stand_vsync 取最短常见间隔对应的标准刷新率，2x 视为丢帧
        if vt_list:
            result["trace_start_ns"] = vt_list[0]
            result["trace_end_ns"] = vt_list[-1]
            segments, switches = _segment_and_switches(vt_list)
            stand_ms_per_cycle = _stand_vsync_ms_per_cycle(vt_list, segments)
            result["inferred_refresh_rate_hz"] = _dominant_hz_by_duration(
                vt_list, segments
            )
            result["refresh_rate_switches"] = switches
            result["mixed_refresh_rates"] = len(switches) > 0
            result["refresh_rate_segments"] = [
                {
                    "hz": hz,
                    "start_ns": vt_list[start],
                    "end_ns": vt_list[min(end, len(vt_list) - 1)],
                    "duration_s": round(
                        (vt_list[min(end, len(vt_list) - 1)] - vt_list[start]) / 1e9,
                        3,
                    ),
                }
                for start, end, hz in segments
            ]
            result["stand_vsync_ms"] = VSYNC_MS.get(
                result["inferred_refresh_rate_hz"], 1000 / 60
            )
            pre_vt = vt_list[0]
            pre_bt1 = pre_bt2 = bt1 = bt2 = pre_vt
            jank_num = 0
            jank_times = 0
            ajt1 = ajt2 = sjt1 = sjt2 = 0
            frame_num = 0
            jank_records: list[dict[str, Any]] = []
            jank_types_in_seq: set[str] = set()
            cycle_idx = 0
            prev_cycle_ns = 0

            for vt in vt_list[1:]:
                stand_ms = (
                    stand_ms_per_cycle[cycle_idx]
                    if cycle_idx < len(stand_ms_per_cycle)
                    else result["stand_vsync_ms"]
                )
                pre_vsync_ns = vt - pre_vt

                # buffer_count_at_vt: 取 ts <= vt 的最后一条 counter 值
                buf_idx = bisect.bisect_right(buffer_raw_ts, vt) - 1
                buffer_count_at_vt = buffer_raw_vals[buf_idx] if buf_idx >= 0 else 0

                # 本周期内 buffer 事件：[pre_vt, vt] 区间，按 delta 区分 bt1/bt2
                ev_lo = bisect.bisect_left(buffer_ev_ts, pre_vt)
                ev_hi = bisect.bisect_right(buffer_ev_ts, vt)
                cycle_bt1 = None
                cycle_bt2 = None
                for i in range(ev_lo, ev_hi):
                    ev = buffer_events[i]
                    if ev["delta"] > 0:
                        cycle_bt1 = ev["ts"]  # 多次增加取最后一次
                    elif ev["delta"] < 0:
                        cycle_bt2 = ev["ts"]
                if cycle_bt1 is not None:
                    bt1 = cycle_bt1
                if cycle_bt2 is not None:
                    bt2 = cycle_bt2

                cycle = {
                    "pre_vt_ns": pre_vt,
                    "vt_ns": vt,
                    "stand_vsync_ms": stand_ms,
                    "pre_bt1_ns": pre_bt1,
                    "pre_bt2_ns": pre_bt2,
                    "bt1_ns": bt1,
                    "bt2_ns": bt2,
                    "buffer_count_at_vt": buffer_count_at_vt,
                }
                result["vsync_cycles"].append(cycle)

                # 首周期守卫：第一个周期缺乏前置上下文，跳过 jank 判定
                skip_jank = prev_cycle_ns == 0
                # 双周期校验（通用前置守卫）：
                # 当前周期+上一周期 < 2×stand_vsync 则跳过所有丢帧判定
                if not skip_jank and prev_cycle_ns > 0:
                    two_cycle_ns = pre_vsync_ns + prev_cycle_ns
                    if two_cycle_ns < 2 * stand_ms * 1e6:
                        skip_jank = True

                if skip_jank:
                    jank_1 = jank_2 = jank_3 = False
                else:
                    # 丢帧判定 1: vt - bt2 > 1.5× stand_vsync
                    jank_1 = (vt - bt2) / 1e6 > stand_ms * 1.5 if bt2 else False
                    # 丢帧判定 2: buffer 数量 = 0
                    jank_2 = buffer_count_at_vt == 0
                    # 丢帧判定 3: [pre_vt, pre_vt + 0.5×VSync] 内 buffer>0 且无减少事件
                    sf_window_ns = int(stand_ms * 0.5 * 1e6)
                    lo_3 = bisect.bisect_left(buffer_ev_ts, pre_vt)
                    hi_3 = bisect.bisect_right(buffer_ev_ts, pre_vt + sf_window_ns)
                    has_decrease = any(
                        buffer_events[i]["delta"] < 0 for i in range(lo_3, hi_3)
                    )
                    jank_3 = buffer_count_at_vt > 0 and not has_decrease

                if jank_1:
                    jank_num += max(1, int((vt - bt2) / 1e6 / stand_ms) - 1)
                    jank_types_in_seq.add("jank_1")
                    ajt1 = pre_bt1
                    sjt1 = bt2
                elif jank_2:
                    jank_num += 1
                    jank_types_in_seq.add("jank_2")
                    ajt1 = pre_bt1
                    sjt1 = pre_vt - int(pre_vsync_ns)
                elif jank_3:
                    jank_num += 1
                    jank_types_in_seq.add("jank_3")
                    if not ajt1:
                        ajt1 = pre_vt
                    sjt1 = pre_vt
                else:
                    if jank_num > 0:
                        ajt2 = pre_bt1
                        sjt2 = pre_vt
                        jank_records.append({
                            "jank_num": jank_num,
                            "jank_type": ",".join(sorted(jank_types_in_seq)),
                            "ajt1_ns": ajt1,
                            "ajt2_ns": ajt2,
                            "sjt1_ns": sjt1,
                            "sjt2_ns": sjt2,
                        })
                        jank_num = 0
                        jank_types_in_seq = set()
                        jank_times += 1
                        ajt1 = ajt2 = sjt1 = sjt2 = 0

                pre_bt1, pre_bt2 = bt1, bt2
                prev_cycle_ns = pre_vsync_ns
                pre_vt = vt
                frame_num += 1
                cycle_idx += 1

            result["jank_records"] = jank_records
            result["jank_times"] = jank_times
            result["frame_num"] = frame_num
    except Exception:
        _safe_close_tp(tp)
        raise

    return result, tp


def _safe_close_tp(tp: Any) -> None:
    """安全关闭 TraceProcessor，忽略 --noconsole 模式下的无效句柄错误。"""
    try:
        if hasattr(tp, "subprocess") and tp.subprocess:
            tp.subprocess.kill()
            tp.subprocess.wait(timeout=5)
            tp.subprocess = None
        if hasattr(tp, "http"):
            tp.http.conn.close()
    except OSError:
        pass
    except Exception:
        pass


def parse_trace(
    trace_path: str | Path,
    refresh_rate_preset: int | float = 60,
    process_filter: str | None = None,
) -> dict[str, Any]:
    """
    向后兼容包装：解析后自动关闭 tp，仅返回 result_dict。
    """
    result, tp = parse_trace_with_tp(trace_path, refresh_rate_preset, process_filter)
    _safe_close_tp(tp)
    return result


def run_parser_and_save(
    trace_path: str | Path,
    db_path: str,
    refresh_rate_preset: int | float = 60,
    log_timing: bool = False,
    process_filter: str | None = None,
) -> dict[str, Any]:
    """
    解析 trace 并写入 storage（先按规范化路径覆盖再插入）。
    使用批量写入减少 I/O，返回 parse_trace 的结果。
    log_timing=True 时向 stderr 输出各阶段耗时，便于定位性能瓶颈。
    process_filter: 指定目标进程/包名用于 BufferTX 轨道匹配。
    """
    from . import storage
    import time

    t0 = time.perf_counter()
    data = parse_trace(trace_path, refresh_rate_preset, process_filter=process_filter)
    t_parse = time.perf_counter() - t0

    conn = storage.get_connection(db_path)
    path_norm = str(Path(trace_path).resolve())
    parsed_at_ns = int(time.time() * 1e9)
    trace_id = storage.insert_trace_run(
        conn,
        path_norm,
        parsed_at_ns,
        trace_start_ns=data.get("trace_start_ns"),
        trace_end_ns=data.get("trace_end_ns"),
        realtime_offset_ns=data.get("realtime_offset_ns", 0),
    )

    cycles = [
        (cy["pre_vt_ns"], cy["vt_ns"], cy["stand_vsync_ms"])
        for cy in data["vsync_cycles"]
    ]
    if cycles:
        storage.insert_vsync_cycles_batch(conn, trace_id, cycles)
    if data["jank_records"]:
        storage.insert_jank_records_batch(conn, trace_id, data["jank_records"])

    t1 = time.perf_counter()
    storage.insert_trace_summary(
        conn,
        trace_id,
        data["jank_times"],
        data["frame_num"],
        inferred_refresh_rate_hz=data.get("inferred_refresh_rate_hz"),
        refresh_rate_switches=data.get("refresh_rate_switches"),
        max_buffer_count=data.get("max_buffer_count", 0),
    )
    conn.close()
    t_db = time.perf_counter() - t1

    if log_timing:
        msg = (
            f"[perfetto_analysis] 解析耗时: {t_parse:.2f}s, 写入 DB 耗时: {t_db:.2f}s"
        )
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
    return data
