# -*- coding: utf-8 -*-
"""待导出 trace 清单 — 持久化未导出的 trace 项，供设备重连后接续导出。

导出失败（设备断开、adb 错误、进程退出）时，`CaptureSession` 与 `TraceItem`
都是内存对象，一旦会话结束或进程退出，"待导出清单"就会丢失。本模块把待导出项
持久化为 JSON 文件（原子写 + 线程锁），跨会话、跨进程保留；设备重连后按
serial 过滤，只接续导出当前连接设备对应的项，避免跨设备串扰。
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# 清单文件名（位于 trace 输出目录下）
PENDING_EXPORT_FILENAME = ".pending_exports.json"


@dataclass
class PendingExportItem:
    """一条待导出 trace 记录。

    serial: 设备序列号（接续导出按此强隔离，跨设备不串扰）
    device_path: 设备端 trace 文件路径（如 /data/.../current_1.perfetto-trace）
    export_filename: 导出后的本地文件名（含设备信息与时间戳）
    session_dir: 会话导出目录名（相对 trace 输出目录）
    device_model: 设备型号（接续确认时的二次校验 / 展示用）
    created_at: 入队时间
    """

    serial: str
    device_path: str
    export_filename: str
    session_dir: str = ""
    device_model: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class PendingExportStore:
    """待导出清单的读写封装。

    - 原子写：先写临时文件再 rename，崩溃时最多丢最后一次写入
    - 线程锁：save/export/接续可能在后台 QThread 执行，GUI 检测在主线程，跨线程共享
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._items: list[PendingExportItem] = []

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def load(self) -> None:
        """从磁盘重新加载（忽略内存缓存）。"""
        with self._lock:
            self._items = self._read()

    def all(self) -> list[PendingExportItem]:
        with self._lock:
            return list(self._items)

    def get_for_serial(self, serial: str) -> list[PendingExportItem]:
        with self._lock:
            return [i for i in self._items if i.serial == serial]

    def has_pending(self, serial: str) -> bool:
        with self._lock:
            return any(i.serial == serial for i in self._items)

    # ------------------------------------------------------------------
    # 变更
    # ------------------------------------------------------------------

    def add(self, item: PendingExportItem) -> None:
        with self._lock:
            self._items.append(item)
            self._write()

    def remove(self, serial: str, export_filename: str) -> bool:
        """按 (serial, export_filename) 出队。成功移除返回 True。"""
        with self._lock:
            before = len(self._items)
            self._items = [
                i for i in self._items
                if not (i.serial == serial and i.export_filename == export_filename)
            ]
            if len(self._items) != before:
                self._write()
                return True
            return False

    def clear_serial(self, serial: str) -> int:
        """清空某设备的全部待导出项（如用户放弃会话）。返回移除数量。"""
        with self._lock:
            before = len(self._items)
            self._items = [i for i in self._items if i.serial != serial]
            removed = before - len(self._items)
            if removed:
                self._write()
            return removed

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _read(self) -> list[PendingExportItem]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.warning("读取待导出清单失败，按空处理: %s", e)
            return []
        raw = data.get("pending", []) if isinstance(data, dict) else []
        items: list[PendingExportItem] = []
        for r in raw:
            if not isinstance(r, dict):
                continue
            try:
                items.append(PendingExportItem(
                    serial=r.get("serial", ""),
                    device_path=r.get("device_path", ""),
                    export_filename=r.get("export_filename", ""),
                    session_dir=r.get("session_dir", ""),
                    device_model=r.get("device_model", ""),
                    created_at=r.get("created_at", ""),
                ))
            except Exception:
                continue
        return items

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "pending": [asdict(i) for i in self._items]}
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as e:
            logger.error("写入待导出清单失败: %s", e)
