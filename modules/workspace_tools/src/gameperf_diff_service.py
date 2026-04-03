"""gameperfconfig 多文件对比与合并 — Service（纯同步，无 Qt）"""

from __future__ import annotations

import logging
import os
import re
import threading
import uuid
from collections.abc import Callable
from typing import Any

from lxml import etree

from toolkit.sdk.exceptions import AdbError

from .gameperf_constants import (
    LOCAL_GAMEPERF_CONFIG_BASENAME,
    PULL_CACHE_SUBDIR,
    REMOTE_GAMEPERF_CONFIG_PATH,
)
from .gameperf_diff_engine import apply_merge_spec, build_diff_items
from .gameperf_diff_errors import DiffValidationError, GamePerfDevicePullError
from .gameperf_diff_models import (
    ComparisonSession,
    DiffItem,
    FileProvenance,
    MergeOperation,
    SessionStatus,
)
from .gameperf_xml import is_valid_gameperf_config_filename, parse_gameperf_xml

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None] | None


class GamePerfConfigDiffService:
    """对比会话、语义 diff、合并与保存。"""

    def __init__(self, adb: Any, data_dir: str) -> None:
        self._adb = adb
        self._data_dir = os.path.abspath(data_dir)
        self._session_id: str | None = None
        self._baseline_path: str | None = None
        self._baseline_tree: etree._Element | None = None
        self._baseline_snapshot: bytes | None = None
        self._working: etree._Element | None = None
        self._comparator_trees: list[etree._Element] = []
        self._comparator_provenance: list[FileProvenance] = []
        self._comparator_paths: list[str] = []
        self._active_index: int = 0
        self._diff_cache: dict[int, list[DiffItem]] = {}
        self._diff_by_id: dict[str, DiffItem] = {}
        self._parse_errors: list[str] = []
        self._undo_snapshots: list[bytes] = []
        self._merge_ops: list[MergeOperation] = []
        self._status: SessionStatus = "idle"

    @staticmethod
    def _safe_serial_dir(serial: str) -> str:
        return re.sub(r'[\\/:*?"<>|]', "_", serial)

    @staticmethod
    def _serialize_root(root: etree._Element) -> bytes:
        return etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True)

    def _clone_tree(self, root: etree._Element) -> etree._Element:
        # MUST 使用 encoding="utf-8"：默认 tostring() 会输出 ASCII 字节并把注释里的中文变成 &#…;
        # 而 XML 注释内不解析实体，再 parse 后中文会永久变成字面 &# 序列。
        return etree.fromstring(etree.tostring(root, encoding="utf-8"))

    def load_session(self, baseline_path: str) -> ComparisonSession:
        """载入基准文件并重置对比列表与工作副本。"""
        path = os.path.abspath(baseline_path)
        if not is_valid_gameperf_config_filename(os.path.basename(path)):
            raise DiffValidationError("基准文件名须包含 gameperfconfig 且为 .xml")
        root = parse_gameperf_xml(path)
        self._session_id = str(uuid.uuid4())
        self._baseline_path = path
        self._baseline_tree = root
        self._baseline_snapshot = self._serialize_root(root)
        self._working = self._clone_tree(root)
        self._comparator_trees.clear()
        self._comparator_provenance.clear()
        self._comparator_paths.clear()
        self._active_index = 0
        self._diff_cache.clear()
        self._diff_by_id.clear()
        self._parse_errors.clear()
        self._undo_snapshots.clear()
        self._merge_ops.clear()
        self._status = "idle"
        prov = FileProvenance(
            kind="local",
            display_label=os.path.basename(path),
            path=path,
            serial=None,
        )
        return self._build_session(prov)

    def add_comparator_local(self, path: str) -> None:
        """添加本地对比文件；坏文件记入 parse_errors。"""
        if self._baseline_tree is None:
            raise DiffValidationError("请先选择基准文件")
        ap = os.path.abspath(path)
        base = os.path.basename(ap)
        if not is_valid_gameperf_config_filename(base):
            self._parse_errors.append(f"已跳过（文件名不符合规则）: {ap}")
            return
        try:
            tree = parse_gameperf_xml(ap)
        except Exception as e:
            self._parse_errors.append(f"已跳过（无法解析）: {ap} — {e}")
            return
        self._comparator_trees.append(tree)
        self._comparator_paths.append(ap)
        self._comparator_provenance.append(
            FileProvenance(kind="local", display_label=base, path=ap, serial=None)
        )
        self._diff_cache.clear()
        self._diff_by_id.clear()

    def add_comparator_from_device(
        self,
        serial: str,
        cancel_event: threading.Event | None = None,
        on_progress: ProgressCallback = None,
    ) -> None:
        """从设备 pull 到 data_dir/pull_cache/<serial>/gameperfconfig.xml 并加入对比列表。"""
        if self._baseline_tree is None:
            raise DiffValidationError("请先选择基准文件")
        serial = (serial or "").strip()
        if not serial:
            raise GamePerfDevicePullError("未检测到设备序列号", failure_kind="transport")

        cache_dir = os.path.join(self._data_dir, PULL_CACHE_SUBDIR, self._safe_serial_dir(serial))
        local_path = os.path.join(cache_dir, LOCAL_GAMEPERF_CONFIG_BASENAME)
        os.makedirs(cache_dir, exist_ok=True)

        def cancelled() -> bool:
            return cancel_event is not None and cancel_event.is_set()

        def notify(msg: str) -> None:
            if on_progress:
                on_progress(msg)

        try:
            if cancelled():
                raise GamePerfDevicePullError("已取消从设备拉取。", failure_kind="cancelled")
            notify("[拉取 1/5] adb root...")
            self._adb.root(serial)
            notify("✓ adb root 成功")
            if cancelled():
                raise GamePerfDevicePullError("已取消从设备拉取。", failure_kind="cancelled")
            notify("[拉取 2/5] adb remount...")
            self._adb.remount(serial, on_progress=on_progress)
            notify("✓ adb remount 成功")
            if cancelled():
                raise GamePerfDevicePullError("已取消从设备拉取。", failure_kind="cancelled")
            notify("[拉取 3/5] setenforce 0...")
            self._adb.shell(serial, "setenforce 0")
            notify("✓ setenforce 0 成功")
            if cancelled():
                raise GamePerfDevicePullError("已取消从设备拉取。", failure_kind="cancelled")
            notify(f"[拉取 4/5] pull → {local_path}...")
            self._adb.pull(serial, REMOTE_GAMEPERF_CONFIG_PATH, local_path)
            notify("✓ pull 成功")
            if cancelled():
                _cleanup_pull_target(local_path, cache_dir)
                raise GamePerfDevicePullError("已取消从设备拉取。", failure_kind="cancelled")
        except GamePerfDevicePullError:
            raise
        except AdbError as e:
            _cleanup_pull_target(local_path, cache_dir)
            kind, msg = _classify_device_pull_error(e)
            raise GamePerfDevicePullError(msg, failure_kind=kind) from e
        except Exception as e:
            logger.exception("add_comparator_from_device 未预期异常")
            _cleanup_pull_target(local_path, cache_dir)
            raise GamePerfDevicePullError(f"从设备拉取失败：{e}", failure_kind="transport") from e

        notify("[拉取 5/5] 校验 XML...")
        try:
            tree = parse_gameperf_xml(local_path)
        except Exception as e:
            _cleanup_pull_target(local_path, cache_dir)
            raise GamePerfDevicePullError(
                f"设备上的配置文件不是合法 gameperfconfig：{e}",
                failure_kind="parse",
            ) from e
        notify("✓ XML 校验通过")
        self._comparator_trees.append(tree)
        self._comparator_paths.append(local_path)
        label = f"设备 ({serial})"
        self._comparator_provenance.append(
            FileProvenance(
                kind="device_pull",
                display_label=label,
                path=local_path,
                serial=serial,
            )
        )
        self._diff_cache.clear()
        self._diff_by_id.clear()

    def remove_comparator(self, index: int) -> None:
        if index < 0 or index >= len(self._comparator_trees):
            raise DiffValidationError("对比文件索引无效")
        del self._comparator_trees[index]
        del self._comparator_paths[index]
        del self._comparator_provenance[index]
        self._diff_cache.clear()
        self._diff_by_id.clear()
        if self._active_index >= len(self._comparator_trees):
            self._active_index = max(0, len(self._comparator_trees) - 1)

    def set_baseline_from_comparator(self, index: int) -> None:
        """将指定对比文件设为新基准（清空对比列表）。"""
        if index < 0 or index >= len(self._comparator_paths):
            raise DiffValidationError("对比文件索引无效")
        new_base = self._comparator_paths[index]
        self.load_session(new_base)

    def set_active_comparator(self, index: int) -> None:
        if index < 0 or index >= len(self._comparator_trees):
            raise DiffValidationError("对比文件索引无效")
        self._active_index = index

    def run_diff(self, cancel_event: threading.Event | None = None) -> list[DiffItem]:
        """对全部对比文件计算 diff 并缓存；返回当前选中对比文件的列表。"""
        if self._baseline_tree is None:
            raise DiffValidationError("未载入基准文件")
        if not self._comparator_trees:
            raise DiffValidationError("请至少添加一个对比文件")
        self._status = "computing"
        self._diff_cache.clear()
        self._diff_by_id.clear()
        try:
            for i in range(len(self._comparator_trees)):
                if cancel_event is not None and cancel_event.is_set():
                    raise DiffValidationError("对比已取消")
                items = build_diff_items(self._baseline_tree, self._comparator_trees[i], i)
                self._diff_cache[i] = items
                for it in items:
                    self._diff_by_id[it.id] = it
            self._status = "ready"
            return list(self._diff_cache.get(self._active_index, []))
        except DiffValidationError:
            self._diff_cache.clear()
            self._diff_by_id.clear()
            self._status = "error"
            raise
        except Exception as e:
            self._status = "error"
            logger.exception("run_diff 失败")
            raise DiffValidationError(f"对比失败：{e}") from e

    def get_diff_for_comparator(self, index: int) -> list[DiffItem]:
        return list(self._diff_cache.get(index, []))

    def diff_counts_summary(self) -> list[tuple[str, int]]:
        """(展示标签, 差异条数) 按对比文件顺序。"""
        out: list[tuple[str, int]] = []
        for i, prov in enumerate(self._comparator_provenance):
            n = len(self._diff_cache.get(i, []))
            out.append((prov.display_label, n))
        return out

    def apply_merge(self, diff_item_id: str, side: str, comparator_index: int) -> None:
        if self._working is None or self._baseline_tree is None:
            raise DiffValidationError("无活动会话")
        if side not in ("baseline", "comparator"):
            raise DiffValidationError("side 须为 baseline 或 comparator")
        if comparator_index < 0 or comparator_index >= len(self._comparator_trees):
            raise DiffValidationError("comparator_index 无效")
        item = self._diff_by_id.get(diff_item_id)
        if item is None or item.comparator_index != comparator_index:
            raise DiffValidationError("找不到对应的差异项")
        if not item.mergeable or not item.merge_spec:
            raise DiffValidationError("该差异项不支持一键采纳")
        src = self._baseline_tree if side == "baseline" else self._comparator_trees[comparator_index]
        snap = self._serialize_root(self._working)
        self._undo_snapshots.append(snap)
        apply_merge_spec(self._working, src, item.merge_spec)
        self._merge_ops.append(
            MergeOperation(
                diff_item_id=diff_item_id,
                side=side,  # type: ignore[arg-type]
                comparator_index=comparator_index,
                payload=dict(item.merge_spec),
            )
        )

    def undo_merge(self) -> tuple[bool, str]:
        """撤销最近一次采纳。成功时返回 (True, 供日志展示的中文描述)，否则 (False, '')。"""
        if not self._undo_snapshots or self._working is None:
            return False, ""
        desc = ""
        op: MergeOperation | None = self._merge_ops[-1] if self._merge_ops else None
        if op is not None:
            item = self._diff_by_id.get(op.diff_item_id)
            path = item.semantic_path if item is not None else op.diff_item_id
            if op.side == "baseline":
                desc = f"{path}（采纳自基准侧）"
            else:
                lbl = (
                    self._comparator_provenance[op.comparator_index].display_label
                    if 0 <= op.comparator_index < len(self._comparator_provenance)
                    else f"对比#{op.comparator_index}"
                )
                desc = f"{path}（采纳自对比侧：{lbl}）"
        raw = self._undo_snapshots.pop()
        self._working = etree.fromstring(raw)
        if self._merge_ops:
            self._merge_ops.pop()
        return True, desc

    def reset_merge(self) -> None:
        if self._baseline_tree is None:
            return
        self._working = self._clone_tree(self._baseline_tree)
        self._undo_snapshots.clear()
        self._merge_ops.clear()

    def get_merge_dirty(self) -> bool:
        if self._working is None or self._baseline_snapshot is None:
            return False
        return self._serialize_root(self._working) != self._baseline_snapshot

    def save_merged_as(self, target_path: str, *, atomic: bool = True) -> None:
        if self._working is None:
            raise DiffValidationError("无工作副本可保存")
        path = os.path.abspath(target_path)
        parent = os.path.dirname(path)
        os.makedirs(parent, exist_ok=True)
        data = self._serialize_root(self._working)
        if not atomic:
            with open(path, "wb") as f:
                f.write(data)
            return
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)

    def get_parse_errors(self) -> list[str]:
        return list(self._parse_errors)

    def clear_parse_errors(self) -> None:
        self._parse_errors.clear()

    def get_session(self) -> ComparisonSession | None:
        if self._session_id is None or self._baseline_path is None:
            return None
        prov = FileProvenance(
            kind="local",
            display_label=os.path.basename(self._baseline_path),
            path=self._baseline_path,
            serial=None,
        )
        return self._build_session(prov)

    def _build_session(self, baseline_prov: FileProvenance) -> ComparisonSession:
        comps: list[tuple[FileProvenance, str]] = list(
            zip(self._comparator_provenance, self._comparator_paths, strict=True)
        )
        return ComparisonSession(
            session_id=self._session_id or "",
            baseline_path=self._baseline_path or "",
            baseline_provenance=baseline_prov,
            comparators=comps,
            active_comparator_index=self._active_index,
            status=self._status,  # type: ignore[arg-type]
            parse_errors=list(self._parse_errors),
        )

    @property
    def active_comparator_index(self) -> int:
        return self._active_index

    @property
    def comparator_count(self) -> int:
        return len(self._comparator_trees)

    @staticmethod
    def stat_path(path: str) -> os.stat_result | None:
        """供 GUI 检测保存目标是否被外部修改。"""
        try:
            return os.stat(path)
        except OSError:
            return None


def _cleanup_pull_target(local_path: str, cache_dir: str) -> None:
    try:
        if os.path.isfile(local_path):
            os.unlink(local_path)
    except OSError:
        pass
    try:
        if os.path.isdir(cache_dir) and not os.listdir(cache_dir):
            os.rmdir(cache_dir)
    except OSError:
        pass


def _classify_device_pull_error(exc: AdbError) -> tuple[str, str]:
    text = str(exc).lower()
    if (
        "no such file" in text
        or "does not exist" in text
        or "not found" in text
        or "remote object" in text
    ):
        return (
            "missing",
            "设备上未找到 /system/etc/gameperfconfig.xml，或路径不可访问。",
        )
    if "permission" in text or "denied" in text:
        return (
            "permission",
            "无法读取设备上的配置文件，请确认设备已 root 且 remount 成功。",
        )
    return ("transport", f"从设备拉取失败：{exc}")
