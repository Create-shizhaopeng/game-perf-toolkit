from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTreeWidgetItem

from modules.perfetto_capture.src.session_tree import SessionTreeWidget
from modules.perfetto_capture.src.analysis_tree import AnalysisHistoryTree


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """保持 QApplication 在整个测试会话存活。

    注意：不能把 QApplication 作为局部变量创建后丢弃（引用计数归零会被 GC），
    否则后续创建 QWidget 时 Qt 会报 "Must construct a QApplication before a QWidget"
    并调用 qFatal/abort，导致进程以 127 异常退出（表现为 hang）。
    """
    app = QApplication.instance() or QApplication([])
    yield app


def test_session_tree_send_payload_fields(tmp_path, qapp):
    tree = SessionTreeWidget()
    trace = tmp_path / "demo.perfetto-trace"
    trace.write_text("x", encoding="utf-8")

    item = QTreeWidgetItem()
    item.setData(
        0,
        Qt.ItemDataRole.UserRole,
        {"type": "trace", "path": str(trace)},
    )
    tree.addTopLevelItem(item)
    item.setSelected(True)

    received: list[dict] = []
    tree.send_to_agent_requested.connect(received.append)
    tree._ctx_send_to_agent()

    assert len(received) == 1
    payload = received[0]
    assert payload["file_path"] == str(trace)
    assert payload["file_name"] == trace.name
    assert payload["context_type"] == "trace"
    assert payload["missing"] is False


def test_analysis_tree_build_send_payload(tmp_path, qapp):
    tree = AnalysisHistoryTree()
    result_dir = tmp_path / "result_1"
    result_dir.mkdir(parents=True, exist_ok=True)

    # 与 AnalysisHistoryTree 实际调用一致：显式传 "analysis"
    payload = tree._build_send_payload(str(result_dir), "analysis")
    assert payload["file_path"] == str(result_dir)
    assert payload["file_name"] == result_dir.name
    assert payload["context_type"] == "analysis"
    assert payload["missing"] is False
