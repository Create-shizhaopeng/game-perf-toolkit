from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from modules.agent_chat.src.gui_tab import AgentTab
from toolkit.core.event_bus import EventBus


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _build_tab() -> AgentTab:
    _ensure_app()
    context = {"event_bus": EventBus()}
    tab = AgentTab(context=context)
    return tab


def test_context_message_injection_dedup_paths():
    tab = _build_tab()
    tab._new_conv_mode = False
    tab._current_conv_id = "conv_a"
    tab._conv_contexts["conv_a"] = [
        {"file_path": "/tmp/a.trace", "file_name": "a.trace", "context_type": "trace", "missing": False},
        {"file_path": "/tmp/a.trace", "file_name": "a.trace", "context_type": "trace", "missing": False},
        {"file_path": "/tmp/b.trace", "file_name": "b.trace", "context_type": "trace", "missing": False},
    ]

    composed = tab._compose_message_with_context("请分析卡顿")
    assert "请分析卡顿" in composed
    assert composed.count("/tmp/a.trace") == 1
    assert composed.count("/tmp/b.trace") == 1


def test_context_isolated_per_conversation():
    tab = _build_tab()
    tab._conv_contexts["conv_a"] = [
        {"file_path": "/tmp/a.trace", "file_name": "a.trace", "context_type": "trace", "missing": False}
    ]
    tab._conv_contexts["conv_b"] = [
        {"file_path": "/tmp/b.trace", "file_name": "b.trace", "context_type": "trace", "missing": False}
    ]

    tab._current_conv_id = "conv_a"
    msg_a = tab._compose_message_with_context("A")
    tab._current_conv_id = "conv_b"
    msg_b = tab._compose_message_with_context("B")

    assert "/tmp/a.trace" in msg_a and "/tmp/b.trace" not in msg_a
    assert "/tmp/b.trace" in msg_b and "/tmp/a.trace" not in msg_b


def test_delete_selected_context_logic():
    tab = _build_tab()
    tab._current_conv_id = "conv_a"
    tab._conv_contexts["conv_a"] = [
        {"file_path": "/tmp/a.trace", "file_name": "a.trace", "context_type": "trace", "missing": False}
    ]
    tab._refresh_context_ui()
    tab._context_list.setCurrentRow(0)

    tab._remove_selected_context()

    assert tab._conv_contexts["conv_a"] == []
    assert tab._context_bar.isVisible() is False


def test_history_payload_cached_before_store_ready():
    tab = _build_tab()
    tab._store = None
    tab._on_history_send_to_agent(
        file_path="/tmp/a.trace",
        file_name="a.trace",
        context_type="trace",
        missing=False,
    )
    assert len(tab._pending_history_payloads) == 1
