"""PerfettoCaptureService 中文用户可见字符串常量。

通过 Final[str] 常量集中管理，避免在业务逻辑中硬编码。
"""

from __future__ import annotations

from typing import Final


# ── Service Info ──
SERVICE_DISPLAY_NAME: Final = "Perfetto 卡顿抓取"

# ── Progress ──
PROGRESS_AUTO_SAVE: Final = "自动保存当前 trace..."
PROGRESS_EXPORT_FMT: Final = "导出中: {}"

# ── Error ──
ERR_DEVICE_UNAVAILABLE: Final = "设备不可用"
ERR_READ_TIMESTAMP: Final = "读取设备时间失败"
ERR_NO_ACTIVE_SESSION: Final = "无活动会话"
ERR_NO_ACTIVE_CAPTURE: Final = "无活动抓取"
ERR_PERFETTO_START_FMT: Final = "启动 perfetto 失败: {}"
ERR_PERFETTO_PID_FMT: Final = "无法解析 perfetto PID: {}"
ERR_SNAPSHOT_FMT: Final = "快照失败: {}"
ERR_DEVICE_MKDIR_FMT: Final = (
    "无法创建设备目录: {}\n"
    "请确认该目录可写，推荐 /data/misc/perfetto-traces\n"
    "详细: {}"
)
ERR_AUTO_SAVE_FMT: Final = "自动保存 trace 失败: {}"

# ── Warn ──
WARN_STOP_NONZERO: Final = "停止 perfetto 返回非零: {}"

# ── Info ──
INFO_AUTO_BUFFER_MODE: Final = "使用自动缓冲模式 (background + 停止-重启)"
INFO_NO_TRACES: Final = "本次会话无保存的 trace，跳过导出"

# ── Log ──
LOG_DIR_FALLBACK: Final = "已回退 device_trace_dir 到 {}"
LOG_SESSION_CREATED: Final = "创建会话: {} (目录将在首次保存时创建)"
LOG_CLEANUP_RESIDUAL: Final = "已清理设备上残留的 perfetto 进程"
LOG_EXPORT_DIR: Final = "创建会话导出目录: {}"
LOG_SAVED_TRACE_FMT: Final = "已保存第 {} 段 trace: {}"
LOG_EXPORT_COMPLETE_FMT: Final = "会话结束，已导出 {} 个文件"
LOG_SESSION_ABANDON_FMT: Final = "会话已放弃 (session_id={}, 已保存 {} 段)"
LOG_EXPORT_FAIL_FMT: Final = "导出失败: {} -> {}"
