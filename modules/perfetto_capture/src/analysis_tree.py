# -*- coding: utf-8 -*-
"""Perfetto 抓取模块 — 分析历史树组件。

递归映射 trace_report/ 文件系统结构，仅展示报告文件和包含它们的目录。
呈现形式与 SessionTreeWidget 一致。
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QTreeWidgetItem, QMenu

from toolkit.core.app_paths import get_output_dir
from toolkit.gui.toolkit_dialog import confirm_dialog
from toolkit.gui.widgets.base_history_tree import BaseHistoryTreeWidget

from . import strings_gui as s

logger = logging.getLogger(__name__)

# 报告文件识别
_REPORT_NAMES = {"jank_report.md", "report.html", "conclusion.html"}


def _is_report(path: Path) -> bool:
    """判断是否是可展示的报告文件。"""
    if not path.is_file():
        return False
    if path.name in _REPORT_NAMES:
        return True
    if path.suffix == ".html":
        return True  # trace_report 下所有 .html 都是分析产出
    if path.suffix == ".md" and "report" in path.name.lower():
        return True
    return False


def _has_reports(dir_path: Path) -> bool:
    """递归检查目录树中是否包含任何报告文件。"""
    if not dir_path.is_dir():
        return False
    for child in dir_path.iterdir():
        if child.is_file() and _is_report(child):
            return True
        if child.is_dir() and _has_reports(child):
            return True
    return False


class AnalysisHistoryTree(BaseHistoryTreeWidget):
    """分析历史树 — 递归映射 trace_report/ 目录结构。"""

    open_report_requested = pyqtSignal(str)
    delete_analysis_requested = pyqtSignal(str)
    send_to_agent_requested = pyqtSignal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.itemDoubleClicked.connect(self._on_double_click)

    # ------------------------------------------------------------------
    # 数据刷新 — 递归扫描文件系统
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """扫描 trace_report/ 目录并构建递归树。"""
        self.clear()
        report_root = get_output_dir("trace_report")
        if not report_root.exists():
            return

        for child in sorted(report_root.iterdir(), reverse=True):
            if not child.is_dir():
                continue
            if not _has_reports(child):
                continue
            dir_item = self._create_dir_node(child)
            self.addTopLevelItem(dir_item)
            self._populate_children(dir_item, child)

    def _populate_children(self, parent_item: QTreeWidgetItem, dir_path: Path) -> None:
        """递归填充子目录和报告文件节点。"""
        for child in sorted(dir_path.iterdir()):
            if child.is_file() and _is_report(child):
                report_item = QTreeWidgetItem()
                report_item.setText(0, child.name)
                report_item.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "analysis_report",
                    "report_path": str(child),
                })
                self._set_item_icon(report_item, "graph")
                parent_item.addChild(report_item)
            elif child.is_dir() and _has_reports(child):
                sub_dir = QTreeWidgetItem()
                sub_dir.setText(0, child.name)
                sub_dir.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "analysis_subdir",
                    "dir_path": str(child),
                })
                self._set_item_icon(sub_dir, "folder")
                parent_item.addChild(sub_dir)
                self._populate_children(sub_dir, child)

    # ------------------------------------------------------------------
    # 节点构建
    # ------------------------------------------------------------------

    def _create_dir_node(self, dir_path: Path) -> QTreeWidgetItem:
        """创建顶层分析目录节点。"""
        item = QTreeWidgetItem()
        item.setText(0, dir_path.name)
        item.setData(0, Qt.ItemDataRole.UserRole, {
            "type": "analysis_dir",
            "dir_path": str(dir_path),
        })
        self._set_item_icon(item, "folder")
        return item

    # ------------------------------------------------------------------
    # 双击 — 打开报告文件 / 展开目录
    # ------------------------------------------------------------------

    def _on_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        rp = data.get("report_path", "")
        if rp and Path(rp).exists():
            self._open_file(rp)
        elif data.get("type") in ("analysis_dir", "analysis_subdir"):
            item.setExpanded(not item.isExpanded())

    # ------------------------------------------------------------------
    # 右键菜单
    # ------------------------------------------------------------------

    def _build_context_menu(self, menu: QMenu, items: list[QTreeWidgetItem]) -> None:
        if not items:
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        target_path = data.get("dir_path") or data.get("report_path", "")
        if target_path:
            self._add_menu_action(
                menu, s.HIST_MENU_OPEN_DIR,
                lambda: self._open_directory(target_path),
            )

        if len(items) == 1 and data.get("type") == "analysis_report":
            self._add_menu_action(menu, s.HIST_MENU_SEND_TO_AGENT, self._ctx_send_to_agent)

        count = len(items)
        delete_text = s.HIST_MENU_DELETE_N_FMT.format(count=count) if count > 1 else s.HIST_MENU_DELETE
        self._add_menu_action(menu, delete_text, self._ctx_delete)

    def _ctx_send_to_agent(self) -> None:
        data = self._get_first_selected_data()
        if not data:
            return
        target = data.get("report_path") or data.get("dir_path") or ""
        if target:
            payload = self._build_send_payload(target, "analysis")
            self.send_to_agent_requested.emit(payload)

    def _ctx_delete(self) -> None:
        data_list = self._get_selected_items_data()
        if not data_list:
            return

        dirs = [d for d in data_list if d.get("type") == "analysis_dir"]
        subdirs = [d for d in data_list if d.get("type") == "analysis_subdir"]
        reports = [d for d in data_list if d.get("type") == "analysis_report"]

        parts: list[str] = []
        if dirs:
            parts.append(s.HIST_COUNT_SESSIONS_FMT.format(n=len(dirs)))
        if subdirs:
            parts.append(s.HIST_COUNT_SUBDIRS_FMT.format(n=len(subdirs)))
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

        for data in data_list:
            if data.get("type") == "analysis_dir":
                dir_path = Path(data["dir_path"])
                try:
                    if dir_path.exists():
                        shutil.rmtree(dir_path)
                        logger.info("已删除分析目录: %s", dir_path)
                except Exception as e:
                    logger.warning("删除分析目录失败: %s", e)
            elif data.get("type") == "analysis_report":
                report_path = Path(data["report_path"])
                try:
                    if report_path.exists():
                        report_path.unlink()
                        logger.info("已删除报告: %s", report_path)
                except Exception as e:
                    logger.warning("删除报告失败: %s", e)
            elif data.get("type") == "analysis_subdir":
                dir_path = Path(data["dir_path"])
                try:
                    if dir_path.exists():
                        shutil.rmtree(dir_path)
                        logger.info("已删除子目录: %s", dir_path)
                except Exception as e:
                    logger.warning("删除子目录失败: %s", e)
        self.refresh()
