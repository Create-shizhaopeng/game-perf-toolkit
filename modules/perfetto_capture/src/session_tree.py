# -*- coding: utf-8 -*-
"""Perfetto 抓取模块 — 历史会话树组件。

继承 BaseHistoryTreeWidget，提供 session → trace → report 三级树形结构。
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QTreeWidgetItem, QMenu

from toolkit.core.app_paths import get_output_dir
from toolkit.gui.toolkit_dialog import confirm_dialog
from toolkit.gui.widgets.base_history_tree import BaseHistoryTreeWidget

from . import strings_gui as s
from .models import HistorySession

logger = logging.getLogger(__name__)


class SessionTreeWidget(BaseHistoryTreeWidget):
    """历史会话树形列表 — 三级结构：session → trace → report。"""

    open_directory_requested = pyqtSignal(Path)
    delete_session_requested = pyqtSignal(str)
    delete_trace_requested = pyqtSignal(Path)
    send_to_agent_requested = pyqtSignal(dict)
    open_report_requested = pyqtSignal(Path)
    delete_report_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.itemExpanded.connect(self._on_item_expanded)
        self.itemCollapsed.connect(self._on_item_collapsed)

    # ------------------------------------------------------------------
    # 数据刷新
    # ------------------------------------------------------------------

    def refresh(self, sessions: list[HistorySession]) -> None:
        """刷新会话列表。"""
        self.clear()
        for session in sessions:
            session_item = self._create_session_item(session)
            self.addTopLevelItem(session_item)
            for trace in session.traces:
                trace_item = self._create_trace_item(trace, session.id)
                session_item.addChild(trace_item)
                self._attach_report_children(trace_item, trace.file_path)

    # ------------------------------------------------------------------
    # 树节点构建
    # ------------------------------------------------------------------

    def _create_session_item(self, session: HistorySession) -> QTreeWidgetItem:
        """创建会话节点 — 默认 folder 图标，展开时切换为 folder-opened。"""
        time_str = session.created_at.strftime("%Y-%m-%d %H:%M")
        device_str = f"{session.device_model or '?'} · {session.device_soc or '?'}"
        size_str = self._format_size(session.total_size_bytes)

        item = QTreeWidgetItem()
        item.setText(0, s.HIST_SESSION_ITEM_FMT.format(
            time=time_str, device=device_str,
            count=session.trace_count, size=size_str,
        ))
        item.setData(0, Qt.ItemDataRole.UserRole, {
            "type": "session", "id": session.id, "path": session.dir_path,
        })
        self._set_item_icon(item, "folder")
        return item

    def _create_trace_item(self, trace, session_id: str) -> QTreeWidgetItem:
        """创建 trace 节点。"""
        size_str = self._format_size(trace.file_size_bytes)
        item = QTreeWidgetItem()
        item.setText(0, f"{trace.file_name} ({size_str})")
        item.setData(0, Qt.ItemDataRole.UserRole, {
            "type": "trace", "session_id": session_id, "path": trace.file_path,
        })
        self._set_item_icon(item, "file")
        return item

    def _attach_report_children(self, trace_item: QTreeWidgetItem, trace_path: str) -> None:
        """为 trace 节点附加分析报告子节点。"""
        from pathlib import Path as _Path

        trace_stem = _Path(trace_path).stem
        candidates: list[_Path] = []

        # dev: <root>/data/output/trace_report/<stem>/report.html
        # frozen: Documents/Game Perf Toolkit/trace_report/<stem>/report.html
        try:
            candidates.append(get_output_dir("trace_report") / trace_stem / "report.html")
            # 兼容旧版 frozen 在 exe 同级 perfetto_report 的遗留路径
            from toolkit.core.app_paths import get_exe_dir, is_frozen
            if is_frozen():
                candidates.append(get_exe_dir() / "output" / "perfetto_report" / trace_stem / "report.html")
        except Exception:
            candidates.append(_Path("data/output/trace_report") / trace_stem / "report.html")

        found = False
        for candidate in candidates:
            if candidate.is_file():
                report_item = QTreeWidgetItem()
                report_item.setText(0, s.HIST_REPORT_LABEL)
                report_item.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "analysis_report",
                    "trace_path": trace_path,
                    "report_path": str(candidate.resolve()),
                })
                self._set_item_icon(report_item, "graph")
                trace_item.addChild(report_item)
                found = True
                break

        if not found:
            try:
                jank_dir = get_output_dir("trace_report") / trace_stem
            except Exception:
                jank_dir = _Path("data/output/trace_report") / trace_stem
            jank_report = jank_dir / "jank_report.md"
            if jank_report.is_file():
                report_item = QTreeWidgetItem()
                report_item.setText(0, s.HIST_REPORT_LABEL_OLD)
                report_item.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "analysis_report",
                    "trace_path": trace_path,
                    "report_path": str(jank_report.resolve()),
                })
                self._set_item_icon(report_item, "graph")
                trace_item.addChild(report_item)

    # ------------------------------------------------------------------
    # 展开/折叠图标切换
    # ------------------------------------------------------------------

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data.get("type") == "session":
            self._set_item_icon(item, "folder-opened")

    def _on_item_collapsed(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data.get("type") == "session":
            self._set_item_icon(item, "folder")

    # ------------------------------------------------------------------
    # 右键菜单
    # ------------------------------------------------------------------

    def _build_context_menu(self, menu: QMenu, items: list[QTreeWidgetItem]) -> None:
        """构建 SessionTree 右键菜单。"""
        self._add_menu_action(menu, s.HIST_MENU_OPEN_DIR, self._ctx_open_directory)

        if len(items) == 1 and items[0].data(0, Qt.ItemDataRole.UserRole):
            item_data = items[0].data(0, Qt.ItemDataRole.UserRole)
            if item_data.get("type") in ("trace", "analysis_report"):
                self._add_menu_action(menu, s.HIST_MENU_SEND_TO_AGENT, self._ctx_send_to_agent)

        menu.addSeparator()

        count = len(items)
        delete_text = s.HIST_MENU_DELETE_N_FMT.format(count=count) if count > 1 else s.HIST_MENU_DELETE
        self._add_menu_action(menu, delete_text, self._ctx_delete)

    def _ctx_open_directory(self) -> None:
        items = self.selectedItems()
        if not items:
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if data and data.get("path"):
            self._open_directory(data["path"])

    def _ctx_delete(self) -> None:
        items = self.selectedItems()
        if not items:
            return

        selected_data = []
        for item in items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                selected_data.append(data)

        sessions = [d for d in selected_data if d.get("type") == "session"]
        traces = [d for d in selected_data if d.get("type") == "trace"]
        reports = [d for d in selected_data if d.get("type") == "analysis_report"]

        parts: list[str] = []
        if sessions:
            parts.append(s.HIST_COUNT_SESSIONS_FMT.format(n=len(sessions)))
        if traces:
            parts.append(s.HIST_COUNT_TRACES_FMT.format(n=len(traces)))
        if reports:
            parts.append(s.HIST_COUNT_REPORTS_FMT.format(n=len(reports)))
        summary = s.HIST_SEPARATOR_COMMA.join(parts)

        ok = confirm_dialog(
            self, s.HIST_DLG_DELETE_TITLE,
            s.HIST_DLG_DELETE_MSG_FMT.format(summary=summary),
            confirm_text=s.HIST_DLG_DELETE_CONFIRM, danger=True,
        )
        if not ok:
            return

        for session in sessions:
            sid = session.get("id")
            if sid:
                self.delete_session_requested.emit(sid)
        for t in traces:
            path = t.get("path")
            if path:
                self.delete_trace_requested.emit(Path(path))
        for r in reports:
            rdir = r.get("report_path")
            if rdir:
                self.delete_report_requested.emit(rdir)

    def _ctx_send_to_agent(self) -> None:
        items = self.selectedItems()
        if not items:
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not data or data.get("type") not in ("trace", "analysis_report"):
            return
        path = str(data.get("path") or data.get("report_path") or "")
        if not path:
            return
        ctx_type = data.get("type", "trace")
        if ctx_type == "analysis_report":
            ctx_type = "analysis"
        payload = self._build_send_payload(path, ctx_type)
        self.send_to_agent_requested.emit(payload)
