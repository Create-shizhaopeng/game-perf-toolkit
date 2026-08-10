"""Agent 上下文注入逻辑测试（迁移到 toolkit/agent 的 AgentPanel）。

原测试针对旧 modules/agent_chat/src/gui_tab.py 的 AgentTab 私有接口，
Agent 核心重构后已迁移到 toolkit/agent/gui/agent_panel.py 的 AgentPanel。
"""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from toolkit.agent.gui.agent_panel import AgentPanel


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """保持 QApplication 在测试会话存活（不能丢弃引用，否则 QWidget 创建会 abort）。"""
    app = QApplication.instance() or QApplication([])
    yield app


def _ctx(path: str, missing: bool = False) -> dict:
    return {
        "file_path": path,
        "file_name": path.split("/")[-1],
        "context_type": "trace",
        "missing": missing,
    }


def test_apply_context_dedup_paths(qapp):
    """同一文件路径只保留一份。"""
    panel = AgentPanel()
    panel._conv_id = "conv_a"

    panel._apply_context(_ctx("/tmp/a.trace"))
    panel._apply_context(_ctx("/tmp/a.trace"))
    panel._apply_context(_ctx("/tmp/b.trace"))

    paths = [c["file_path"] for c in panel._conv_contexts["conv_a"]]
    assert paths.count("/tmp/a.trace") == 1
    assert paths.count("/tmp/b.trace") == 1


def test_context_isolated_per_conversation(qapp):
    """不同会话的上下文互相隔离。"""
    panel = AgentPanel()

    panel._conv_id = "conv_a"
    panel._apply_context(_ctx("/tmp/a.trace"))
    panel._conv_id = "conv_b"
    panel._apply_context(_ctx("/tmp/b.trace"))

    a_paths = [c["file_path"] for c in panel._conv_contexts["conv_a"]]
    b_paths = [c["file_path"] for c in panel._conv_contexts["conv_b"]]
    assert "/tmp/a.trace" in a_paths and "/tmp/b.trace" not in a_paths
    assert "/tmp/b.trace" in b_paths and "/tmp/a.trace" not in b_paths


def test_history_payload_cached_before_store_ready(qapp):
    """store 未就绪时上下文先缓存，等待 _flush_pending。"""
    panel = AgentPanel()
    panel._store = None

    panel._on_history_event(**_ctx("/tmp/a.trace"))

    assert len(panel._pending_contexts) == 1
    assert panel._pending_contexts[0]["file_path"] == "/tmp/a.trace"


@pytest.mark.skip(
    reason="删除单个上下文的功能未随 Agent 重构迁移到 AgentPanel（无对应方法），待实现后补测"
)
def test_delete_selected_context_logic(qapp):
    """（占位）删除选中上下文 — 旧 AgentTab 功能，新 AgentPanel 未迁移。"""
