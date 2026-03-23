# -*- coding: utf-8 -*-
"""文件 IO 阻塞分析（FR-111）。"""
from __future__ import annotations

import sys
from typing import Any

IO_BLOCKED_FUNCTIONS = {
    "do_page_fault", "filemap_fault", "wait_on_page_bit",
    "generic_file_read_iter", "ext4_file_read_iter",
    "vfs_read", "vfs_write", "do_sys_open",
    "sys_read", "sys_write",
}

PAGE_FAULT_FUNCTIONS = {
    "do_page_fault", "filemap_fault", "handle_mm_fault",
    "do_user_addr_fault",
}


def analyze_io(
    tp: Any,
    window_start_ns: int,
    window_end_ns: int,
    target_utids: list[int],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    文件 IO 阻塞分析。
    查询窗口内 D 状态 + blocked_function 分类。
    """
    result: dict[str, Any] = {
        "io_blocks": [],
        "io_block_total_ns": 0,
        "io_block_count": 0,
        "categories": {"file_io": 0, "page_fault": 0, "other": 0},
    }

    if not target_utids:
        return result

    utid_list = ",".join(str(u) for u in target_utids)

    try:
        rows = list(tp.query(f"""
            SELECT ts.ts, ts.dur, ts.utid, ts.blocked_function,
                   t.name as thread_name
            FROM thread_state ts
            JOIN thread t ON ts.utid = t.utid
            WHERE ts.utid IN ({utid_list})
              AND ts.state = 'D'
              AND ts.ts + ts.dur > {window_start_ns}
              AND ts.ts < {window_end_ns}
            ORDER BY ts.dur DESC
        """))

        blocks = []
        total_ns = 0
        cat_count = {"file_io": 0, "page_fault": 0, "other": 0}

        for row in rows:
            dur = int(row.dur) if row.dur else 0
            func = str(row.blocked_function) if row.blocked_function else ""
            category = _classify_blocked_function(func)

            blocks.append({
                "ts_ns": int(row.ts),
                "dur_ns": dur,
                "dur_us": round(dur / 1000, 1),
                "utid": int(row.utid),
                "thread_name": str(row.thread_name) if row.thread_name else "",
                "blocked_function": func,
                "category": category,
            })
            total_ns += dur
            cat_count[category] = cat_count.get(category, 0) + 1

        result["io_blocks"] = blocks[:50]
        result["io_block_total_ns"] = total_ns
        result["io_block_count"] = len(blocks)
        result["categories"] = cat_count

    except Exception as e:
        print(f"[perfetto_analysis] 警告: IO 阻塞分析失败: {e}", file=sys.stderr)

    return result


def _classify_blocked_function(func: str) -> str:
    """将 blocked_function 分类为 file_io / page_fault / other。"""
    if not func:
        return "other"
    func_lower = func.lower()
    for pf in PAGE_FAULT_FUNCTIONS:
        if pf.lower() in func_lower:
            return "page_fault"
    for iof in IO_BLOCKED_FUNCTIONS:
        if iof.lower() in func_lower:
            return "file_io"
    return "other"
