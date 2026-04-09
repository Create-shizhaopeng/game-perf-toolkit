# -*- coding: utf-8 -*-
"""App 类型自动检测（FR-100）：根据 trace 中目标进程特征判断 app/game/camera。"""
from __future__ import annotations

import sys
from typing import Any

APP_TYPES = ("app", "game", "camera")


def detect_app_type(
    tp: Any,
    process_name: str | None = None,
    manual_override: str = "auto",
) -> str:
    """
    检测 App 类型。
    manual_override != "auto" 时直接返回手动值。
    自动检测逻辑（顺序决定优先级）：
      1. camera 包名特征 → camera
      2. eglSwapBuffers / vkQueuePresentKHR → game
      3. Vulkan QueueSubmit（无 Choreographer 主导）或 SurfaceView BLAST 渲染 → game
      4. Choreographer#doFrame 存在 → 判断是否同时有 SurfaceView 渲染模式（Unity 等游戏引擎）
      5. 默认 app
    """
    if manual_override != "auto" and manual_override in APP_TYPES:
        return manual_override

    if not process_name:
        return "app"

    upid = _find_upid(tp, process_name)
    if upid is None:
        return "app"

    camera_keywords = ("camera", "Camera", "cam.", "photo", "Photo")
    is_camera_pkg = any(kw in process_name for kw in camera_keywords)
    if is_camera_pkg:
        return "camera"

    has_egl_swap = _has_slice_in_process(tp, upid, "eglSwapBuffers")
    has_vk_present = _has_slice_in_process(tp, upid, "vkQueuePresentKHR")
    if has_egl_swap or has_vk_present:
        return "game"

    has_vulkan_submit = _has_slice_in_process(tp, upid, "QueueSubmit")
    has_surfaceview = _has_surfaceview_rendering(tp, upid)
    has_choreographer = _has_slice_in_process(tp, upid, "Choreographer#doFrame")

    # Unity/Unreal 等引擎通过 SurfaceView 渲染但也触发 Choreographer
    if has_surfaceview and (has_vulkan_submit or not has_choreographer):
        return "game"

    # 有 Choreographer 但同时 SurfaceView 渲染量远超 Choreographer → game
    if has_choreographer and has_surfaceview:
        sv_count = _count_slices_in_process(tp, upid, "queueBuffer")
        ch_count = _count_slices_in_process(tp, upid, "Choreographer#doFrame")
        if sv_count > ch_count * 1.5:
            return "game"

    if has_choreographer:
        return "app"

    return "app"


def _find_upid(tp: Any, process_name: str) -> int | None:
    """根据进程名/包名查找 upid。同时检查 process.name 和主线程名（tid=pid）。"""
    safe_name = process_name.replace("'", "''")
    try:
        rows = list(tp.query(
            f"SELECT upid FROM process WHERE name = '{safe_name}' LIMIT 1"
        ))
        if rows:
            return int(rows[0].upid)
        rows = list(tp.query(
            f"SELECT upid FROM process WHERE name GLOB '*{safe_name}*' LIMIT 1"
        ))
        if rows:
            return int(rows[0].upid)
    except Exception:
        pass

    try:
        rows = list(tp.query(f"""
            SELECT p.upid FROM process p
            JOIN thread t ON t.upid = p.upid AND t.tid = p.pid
            WHERE t.name GLOB '*{safe_name}*'
            LIMIT 1
        """))
        if rows:
            return int(rows[0].upid)
    except Exception:
        pass

    return None


def find_target_upid(tp: Any, process_name: str) -> int | None:
    """公开的 upid 查找接口。"""
    return _find_upid(tp, process_name)


def _has_slice_in_process(tp: Any, upid: int, slice_name: str) -> bool:
    """检查指定进程中是否存在指定名称的 slice。"""
    try:
        rows = list(tp.query(f"""
            SELECT 1 FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE t.upid = {upid} AND s.name GLOB '*{slice_name}*'
            LIMIT 1
        """))
        return len(rows) > 0
    except Exception:
        return False


def _count_slices_in_process(tp: Any, upid: int, slice_name: str) -> int:
    """统计指定进程中某名称 slice 的数量。"""
    try:
        rows = list(tp.query(f"""
            SELECT COUNT(*) as cnt FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE t.upid = {upid} AND s.name GLOB '*{slice_name}*'
        """))
        return int(rows[0].cnt) if rows else 0
    except Exception:
        return 0


def _has_surfaceview_rendering(tp: Any, upid: int) -> bool:
    """检查进程是否有 SurfaceView BLAST 渲染模式（常见于游戏引擎）。"""
    try:
        rows = list(tp.query(f"""
            SELECT 1 FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE t.upid = {upid}
              AND s.name GLOB '*SurfaceView*BLAST*'
            LIMIT 1
        """))
        return len(rows) > 0
    except Exception:
        return False
