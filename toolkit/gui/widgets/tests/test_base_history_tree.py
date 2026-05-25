# -*- coding: utf-8 -*-
"""BaseHistoryTreeWidget 单元测试。"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTreeWidgetItem

from toolkit.gui.widgets.base_history_tree import BaseHistoryTreeWidget


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestSendPayload:
    """_build_send_payload 测试。"""

    def test_trace_payload(self, tmp_path):
        trace = tmp_path / "test.perfetto-trace"
        trace.write_text("ok", encoding="utf-8")

        payload = BaseHistoryTreeWidget._build_send_payload(str(trace), "trace")
        assert payload == {
            "file_path": str(trace),
            "file_name": "test.perfetto-trace",
            "context_type": "trace",
            "missing": False,
        }

    def test_analysis_payload(self, tmp_path):
        result_dir = tmp_path / "analysis_1"
        result_dir.mkdir(parents=True)

        payload = BaseHistoryTreeWidget._build_send_payload(str(result_dir), "analysis")
        assert payload["context_type"] == "analysis"
        assert payload["file_name"] == "analysis_1"

    def test_missing_file(self, tmp_path):
        nonexistent = tmp_path / "does_not_exist.perfetto-trace"
        payload = BaseHistoryTreeWidget._build_send_payload(str(nonexistent), "trace")
        assert payload["missing"] is True


class TestFormatSize:
    """_format_size 测试。"""

    def test_bytes(self):
        assert BaseHistoryTreeWidget._format_size(512) == "512 B"

    def test_kilobytes(self):
        assert BaseHistoryTreeWidget._format_size(1536) == "1.5 KB"

    def test_megabytes(self):
        assert BaseHistoryTreeWidget._format_size(1536000) == "1.5 MB"

    def test_gigabytes(self):
        assert BaseHistoryTreeWidget._format_size(int(2.5 * 1024 ** 3)) == "2.50 GB"


class TestFilterByKeyword:
    """filter_by_keyword 测试。"""

    def test_filter_shows_matching(self):
        _ensure_app()
        tree = BaseHistoryTreeWidget()

        item_a = QTreeWidgetItem()
        item_a.setText(0, "Pixel 7 Pro")
        tree.addTopLevelItem(item_a)

        item_b = QTreeWidgetItem()
        item_b.setText(0, "Samsung S24")
        tree.addTopLevelItem(item_b)

        tree.filter_by_keyword("pixel")
        assert not item_a.isHidden()
        assert item_b.isHidden()

    def test_filter_empty_shows_all(self):
        _ensure_app()
        tree = BaseHistoryTreeWidget()
        item = QTreeWidgetItem()
        item.setText(0, "Test")
        tree.addTopLevelItem(item)

        item.setHidden(True)
        tree.filter_by_keyword("")
        assert not item.isHidden()


class TestSelectedItemsData:
    """_get_selected_items_data 测试。"""

    def test_returns_user_role_data(self):
        _ensure_app()
        tree = BaseHistoryTreeWidget()

        item = QTreeWidgetItem()
        item.setData(0, Qt.ItemDataRole.UserRole, {"type": "session", "id": "abc"})
        tree.addTopLevelItem(item)
        item.setSelected(True)

        data_list = tree._get_selected_items_data()
        assert len(data_list) == 1
        assert data_list[0]["type"] == "session"
        assert data_list[0]["id"] == "abc"


class TestTheme:
    """主题应用测试。"""

    def test_set_theme_applies_stylesheet(self):
        _ensure_app()
        tree = BaseHistoryTreeWidget()
        tree.set_theme("dark")
        ss = tree.styleSheet()
        assert "transparent" in ss or "color" in ss
        tree.set_theme("light")
        ss2 = tree.styleSheet()
        assert ss2  # should not be empty
