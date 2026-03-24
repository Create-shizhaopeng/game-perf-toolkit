"""Perfetto 抓取模块 — 数据模型"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ── Pydantic 配置模型 (公共 API) ──────────────────────────────────


class TargetConfig(BaseModel):
    mode: str = "global"
    packages: list[str] = Field(default_factory=list)


class AdvancedConfig(BaseModel):
    available_ftrace_events: list[str] = Field(default_factory=lambda: [
        "sched/sched_switch", "sched/sched_wakeup",
        "power/cpu_frequency", "power/cpu_idle",
        "power/suspend_resume", "irq/irq_handler_entry",
        "irq/irq_handler_exit", "irq/softirq_entry",
        "irq/softirq_exit", "block/block_rq_issue",
        "block/block_rq_complete", "filemap/mm_filemap_add_to_page_cache",
        "vmscan/mm_vmscan_direct_reclaim_begin", "gpu_mem/gpu_mem_total",
        "mali/mali_PM_MCU_HCTL_CORES_NOTIFY_PEND",
        "thermal/thermal_temperature",
    ])
    ftrace_events: list[str] = Field(default_factory=list)
    sampling: dict[str, Any] = Field(default_factory=dict)
    enable_raw_perfetto_config: bool = False
    raw_perfetto_config_text: str = ""


class ExportConfig(BaseModel):
    cleanup_device_files: bool = False


class LoggingConfig(BaseModel):
    debug: bool = False


class CaptureConfig(BaseModel):
    """Perfetto 抓取配置模型，由模块级 config.json 加载。"""

    atrace_categories: list[str] = Field(
        default_factory=lambda: [
            "sched", "gfx", "view", "input", "am", "wm", "freq",
        ]
    )
    duration_sec: int = Field(default=15, ge=1)
    buffer_size_kb: int | None = Field(default=None, ge=1)
    buffer_manual_override: bool = False
    buffer_safety_factor: float = Field(default=1.2, ge=1.0, le=5.0)
    device_trace_dir: str = "/data/misc/perfetto-traces"
    output_dir: str = "output"
    target: TargetConfig = Field(default_factory=TargetConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def validate_semantics(self) -> None:
        """校验配置语义（Pydantic 无法覆盖的业务规则）。"""
        if not self.atrace_categories:
            raise ValueError("atrace_categories 不能为空")
        if self.target.mode not in ("global", "packages"):
            raise ValueError("target.mode 必须是 global 或 packages")
        if self.target.mode == "packages" and not self.target.packages:
            raise ValueError("target.mode=packages 时，target.packages 不能为空")
        if self.advanced.enable_raw_perfetto_config and not self.advanced.raw_perfetto_config_text.strip():
            raise ValueError("enable_raw_perfetto_config=true 时，raw_perfetto_config_text 不能为空")


# ── 内部数据模型 (dataclass) ──────────────────────────────────────


class TraceKind(str, Enum):
    NORMAL = "normal"
    FAULT = "fault"


class DeviceConnectionState(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    WAITING_RECONNECT = "waiting_reconnect"


class CaptureState(str, Enum):
    IDLE = "idle"
    CAPTURING = "capturing"
    SAVING = "saving"
    EXPORTING = "exporting"


class CaptureMode(str, Enum):
    """抓取引擎模式。"""
    SNAPSHOT = "snapshot"      # detach + clone（优先）
    AUTOBUFFER = "autobuffer"  # 传统 background 模式（降级）


@dataclass(frozen=True)
class PerfettoCapabilities:
    help_text: str

    @property
    def supports_detach(self) -> bool:
        return "--detach" in self.help_text

    @property
    def supports_clone(self) -> bool:
        return "--clone" in self.help_text

    @property
    def supports_snapshot_mode(self) -> bool:
        return self.supports_detach and self.supports_clone

    def summary(self) -> str:
        flags = []
        for k in ("--background", "--background-wait", "--attach", "--stop",
                   "--detach", "--clone", "--trigger", "--txt", "-c", "--config"):
            if k in self.help_text:
                flags.append(k)
        return " ".join(flags) if flags else "(no-known-flags-detected)"


@dataclass(frozen=True)
class RunningTrace:
    device_output_path: str
    mode: CaptureMode
    detach_key: str | None = None
    session_name: str | None = None
    pid: int | None = None


@dataclass
class TraceItem:
    kind: TraceKind
    device_path: str
    export_filename: str
    export_path: Path | None = None
    exported: bool = False


@dataclass(frozen=True)
class DeviceInfo:
    serial: str
    model: str
    soc: str


@dataclass
class CaptureSession:
    """一轮抓取会话：启动 → 多次保存 → 导出退出。"""

    session_id: str
    device_serial: str
    export_session_dir: Path
    saved_traces: list[TraceItem] = field(default_factory=list)
    conn_state: DeviceConnectionState = DeviceConnectionState.CONNECTED
    capture_state: CaptureState = CaptureState.IDLE
    running: RunningTrace | None = None
    trace_idx: int = 0
    start_time: datetime.datetime | None = None
