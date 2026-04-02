"""Perfetto 抓取模块 — 工具函数"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

from toolkit.core.adb_manager import AdbCmdResult


def normalize_filename_part(value: str) -> str:
    """将设备字段转换为文件名安全字符串。"""
    s = value.strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s)
    return s or "UNKNOWN"


def build_trace_filename(model: str, soc: str, device_timestamp: str) -> str:
    """`{MODEL}_{SOC}_{YYYYMMDD}_{HHMMSS}.perfetto-trace`"""
    model_s = normalize_filename_part(model)
    soc_s = normalize_filename_part(soc)
    ts_s = normalize_filename_part(device_timestamp).replace("-", "_")
    return f"{model_s}_{soc_s}_{ts_s}.perfetto-trace"


def choose_non_conflicting_path(path: Path) -> Path:
    """若 path 已存在，追加 _1/_2... 直到可用。"""
    if not path.exists():
        return path
    stem = path.stem
    suffix = "".join(path.suffixes)
    parent = path.parent
    for i in range(1, 10_000):
        cand = parent / f"{stem}_{i}{suffix}"
        if not cand.exists():
            return cand
    raise RuntimeError(f"输出目录下文件冲突过多：{path}")


def build_export_session_dirname(dt: datetime.datetime | None = None) -> str:
    """生成导出会话目录名（本机时间）：`yyyy_MM_dd-HH_mm_ss`"""
    dt2 = dt or datetime.datetime.now()
    return dt2.strftime("%Y_%m_%d-%H_%M_%S")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_unique_dir(parent: Path, dirname: str) -> Path:
    """创建 parent/dirname 目录；已存在则追加 _1/_2... 直到可用。"""
    base = parent / dirname
    if not base.exists():
        ensure_dir(base)
        return base
    for i in range(1, 10_000):
        cand = parent / f"{dirname}_{i}"
        if not cand.exists():
            ensure_dir(cand)
            return cand
    raise RuntimeError(f"无法创建会话目录：{base}")


def ensure_fault_prefix(filename: str) -> str:
    """确保文件名以 FAULT_ 开头。"""
    if filename.startswith("FAULT_"):
        return filename
    return f"FAULT_{filename}"


def is_device_unavailable(result: AdbCmdResult) -> bool:
    """识别 adb 常见"设备不可用/断线"场景。"""
    if result.returncode == 0:
        return False
    txt = f"{result.stderr or ''}\n{result.stdout or ''}".strip().lower()
    patterns = [
        "no devices/emulators found",
        "device offline",
        "device unauthorized",
        "unauthorized",
        "device not found",
        "error: device",
        "closed",
        "protocol fault",
        "cannot connect to daemon",
        "adb: error",
    ]
    return any(p in txt for p in patterns)


# ── 历史记录解析工具 ────────────────────────────────────────────────

# 标准 trace 文件名格式: {model}_{soc}_{YYYYMMDD}_{HHMMSS}.perfetto-trace
# 或带序号: {model}_{soc}_{YYYYMMDD}_{HHMMSS}_001.perfetto-trace
TRACE_FILENAME_PATTERN = re.compile(
    r"^(?P<model>[A-Za-z0-9._-]+)_(?P<soc>[A-Za-z0-9._-]+)_"
    r"(?P<ts>\d{4}[_-]?\d{2}[_-]?\d{2}[_-]?\d{2}[_-]?\d{2}[_-]?\d{2})"
    r"(?:_\d+)?\.perfetto-trace$"
)

# 会话目录名格式: yyyy_MM_dd-HH_mm_ss 或 yyyyMMdd_HHmmss
SESSION_DIRNAME_PATTERNS = [
    re.compile(r"^(\d{4})_(\d{2})_(\d{2})-(\d{2})_(\d{2})_(\d{2})(?:_\d+)?$"),  # 新格式
    re.compile(r"^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})(?:_\d+)?$"),       # 紧凑格式
]


class TraceFilenameInfo:
    """Trace 文件名解析结果。"""

    def __init__(
        self,
        model: str | None = None,
        soc: str | None = None,
        timestamp: datetime.datetime | None = None,
    ):
        self.model = model
        self.soc = soc
        self.timestamp = timestamp

    def __repr__(self) -> str:
        return f"TraceFilenameInfo(model={self.model!r}, soc={self.soc!r}, timestamp={self.timestamp})"


def parse_trace_filename(filename: str) -> TraceFilenameInfo:
    """
    解析 trace 文件名，提取设备型号、SoC 和时间戳。

    支持格式:
    - {model}_{soc}_{YYYYMMDD}_{HHMMSS}.perfetto-trace
    - {model}_{soc}_{YYYYMMDD}_{HHMMSS}_001.perfetto-trace
    - {model}_{soc}_{YYYY_MM_DD-HH_MM_SS}.perfetto-trace

    无法解析时返回空字段的 TraceFilenameInfo。
    """
    match = TRACE_FILENAME_PATTERN.match(filename)
    if not match:
        return TraceFilenameInfo()

    model = match.group("model")
    soc = match.group("soc")
    ts_str = match.group("ts")

    # 解析时间戳
    ts_clean = re.sub(r"[_-]", "", ts_str)
    timestamp = None
    if len(ts_clean) == 14:
        try:
            timestamp = datetime.datetime.strptime(ts_clean, "%Y%m%d%H%M%S")
        except ValueError:
            pass

    return TraceFilenameInfo(model=model, soc=soc, timestamp=timestamp)


def parse_session_dirname(dirname: str) -> datetime.datetime | None:
    """
    解析会话目录名，提取创建时间。

    支持格式:
    - yyyy_MM_dd-HH_mm_ss（如 2026_04_02-20_15_30）
    - yyyyMMdd_HHmmss（如 20260402_201530）

    无法解析时返回 None。
    """
    for pattern in SESSION_DIRNAME_PATTERNS:
        match = pattern.match(dirname)
        if match:
            groups = match.groups()
            try:
                return datetime.datetime(
                    year=int(groups[0]),
                    month=int(groups[1]),
                    day=int(groups[2]),
                    hour=int(groups[3]),
                    minute=int(groups[4]),
                    second=int(groups[5]),
                )
            except ValueError:
                continue
    return None
