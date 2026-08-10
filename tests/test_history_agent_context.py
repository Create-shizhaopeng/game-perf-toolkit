from __future__ import annotations

from pathlib import Path

import pytest
from toolkit.gui.widgets.base_history_tree import BaseHistoryTreeWidget


def test_history_payload_fields_for_trace(tmp_path):
    trace = tmp_path / "demo.perfetto-trace"
    trace.write_text("ok", encoding="utf-8")

    payload = BaseHistoryTreeWidget._build_send_payload(str(trace), "trace")
    assert payload == {
        "file_path": str(trace),
        "file_name": trace.name,
        "context_type": "trace",
        "missing": False,
    }


def test_history_payload_fields_for_analysis(tmp_path):
    result_dir = tmp_path / "analysis_001"
    result_dir.mkdir(parents=True, exist_ok=True)

    payload = BaseHistoryTreeWidget._build_send_payload(str(result_dir), "analysis")
    assert payload["file_path"] == str(result_dir)
    assert payload["file_name"] == result_dir.name
    assert payload["context_type"] == "analysis"
    assert payload["missing"] is False


@pytest.mark.skip(
    reason="compose_message_with_context 函数已随 Agent 核心重构移除（逻辑内联到 toolkit/agent/gui/agent_panel.py 的 _on_send），待迁移后重写"
)
def test_context_injection_dedup_and_format():
    contexts = [
        {"file_path": "/tmp/a.trace", "file_name": "a.trace", "context_type": "trace", "missing": False},
        {"file_path": "/tmp/a.trace", "file_name": "a.trace", "context_type": "trace", "missing": False},
        {"file_path": "/tmp/b.trace", "file_name": "b.trace", "context_type": "trace", "missing": False},
    ]

    msg = compose_message_with_context("请分析", contexts)
    assert msg.startswith("请分析")
    assert msg.count("/tmp/a.trace") == 1
    assert msg.count("/tmp/b.trace") == 1
    assert "[文件上下文]" in msg


@pytest.mark.skip(
    reason="compose_message_with_context 函数已随 Agent 核心重构移除（逻辑内联到 toolkit/agent/gui/agent_panel.py 的 _on_send），待迁移后重写"
)
def test_context_isolation_effect():
    conv_1_contexts = [
        {"file_path": "/tmp/a.trace", "file_name": "a.trace", "context_type": "trace", "missing": False},
    ]
    conv_2_contexts = [
        {"file_path": "/tmp/b.trace", "file_name": "b.trace", "context_type": "trace", "missing": False},
    ]

    before = compose_message_with_context("m1", conv_1_contexts)
    assert "/tmp/a.trace" in before and "/tmp/b.trace" not in before

    after = compose_message_with_context("m2", [])
    assert after == "m2"

    other = compose_message_with_context("m3", conv_2_contexts)
    assert "/tmp/b.trace" in other
