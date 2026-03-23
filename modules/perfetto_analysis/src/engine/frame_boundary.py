# -*- coding: utf-8 -*-
"""帧边界确定（FR-103）：根据 App 类型确定每帧的起止时间。"""
from __future__ import annotations

from typing import Any


def find_frame_boundaries(
    tp: Any,
    app_type: str,
    upid: int | None,
    window_start_ns: int,
    window_end_ns: int,
) -> list[dict[str, Any]]:
    """
    在指定窗口内查找帧边界。
    返回: [{"frame_start_ns": int, "frame_end_ns": int, "source": str}, ...]
    """
    if app_type == "game":
        return _game_frame_boundaries(tp, upid, window_start_ns, window_end_ns)
    elif app_type == "camera":
        return _camera_frame_boundaries(tp, upid, window_start_ns, window_end_ns)
    else:
        return _app_frame_boundaries(tp, upid, window_start_ns, window_end_ns)


def _app_frame_boundaries(
    tp: Any, upid: int | None, start_ns: int, end_ns: int,
) -> list[dict[str, Any]]:
    """一般 App：使用 Choreographer#doFrame slice 作为帧边界。"""
    if upid is None:
        return []
    try:
        rows = list(tp.query(f"""
            SELECT s.ts, s.dur
            FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE t.upid = {upid}
              AND s.name GLOB '*Choreographer#doFrame*'
              AND s.ts >= {start_ns} AND s.ts <= {end_ns}
            ORDER BY s.ts
        """))
        return [
            {
                "frame_start_ns": int(row.ts),
                "frame_end_ns": int(row.ts) + int(row.dur),
                "source": "Choreographer#doFrame",
            }
            for row in rows
        ]
    except Exception:
        return []


def _game_frame_boundaries(
    tp: Any, upid: int | None, start_ns: int, end_ns: int,
) -> list[dict[str, Any]]:
    """游戏：使用 eglSwapBuffers / vkQueuePresentKHR slice 作为帧边界。"""
    if upid is None:
        return []
    try:
        rows = list(tp.query(f"""
            SELECT s.ts, s.dur, s.name
            FROM slice s
            JOIN thread_track tt ON s.track_id = tt.id
            JOIN thread t ON tt.utid = t.utid
            WHERE t.upid = {upid}
              AND (s.name GLOB '*eglSwapBuffers*' OR s.name GLOB '*vkQueuePresentKHR*')
              AND s.ts >= {start_ns} AND s.ts <= {end_ns}
            ORDER BY s.ts
        """))
        return [
            {
                "frame_start_ns": int(row.ts),
                "frame_end_ns": int(row.ts) + int(row.dur),
                "source": str(row.name),
            }
            for row in rows
        ]
    except Exception:
        return []


def _camera_frame_boundaries(
    tp: Any, upid: int | None, start_ns: int, end_ns: int,
) -> list[dict[str, Any]]:
    """相机：UI 层用 Choreographer，预览层用 BufferTX bt1 时刻。"""
    frames = _app_frame_boundaries(tp, upid, start_ns, end_ns)
    if not frames:
        frames = _game_frame_boundaries(tp, upid, start_ns, end_ns)
    return frames
