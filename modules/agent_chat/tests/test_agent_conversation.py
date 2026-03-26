# -*- coding: utf-8 -*-
"""agent_chat 模块 — ConversationStore 测试。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from modules.agent_chat.src.memory.conversation import ConversationStore
from modules.agent_chat.src.models import (
    Conversation,
    Message,
    MessageRole,
    ToolCall,
    ToolCallStatus,
)


@pytest.fixture
def store(tmp_path: Path):
    """每个测试使用独立的内存级 SQLite 数据库。"""
    db = tmp_path / "test_chat.db"
    s = ConversationStore(db)
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Conversation CRUD
# ---------------------------------------------------------------------------

class TestConversationCRUD:

    def test_create_and_load(self, store: ConversationStore):
        conv = Conversation(id="conv001", title="测试对话", sop_used="jank")
        cid = store.create_conversation(conv)
        assert cid == "conv001"

        loaded = store.load_conversation("conv001")
        assert loaded is not None
        assert loaded.title == "测试对话"
        assert loaded.sop_used == "jank"

    def test_load_nonexistent(self, store: ConversationStore):
        assert store.load_conversation("nonexist") is None

    def test_list_conversations_order(self, store: ConversationStore):
        from time import sleep

        c1 = Conversation(id="c1", title="第一个")
        c2 = Conversation(id="c2", title="第二个")
        store.create_conversation(c1)
        store.create_conversation(c2)

        store.rename_conversation("c1", "更新后")

        result = store.list_conversations()
        assert len(result) == 2
        assert result[0]["id"] == "c1"
        assert result[0]["title"] == "更新后"

    def test_rename(self, store: ConversationStore):
        store.create_conversation(Conversation(id="r1", title="旧标题"))
        store.rename_conversation("r1", "新标题")

        loaded = store.load_conversation("r1")
        assert loaded is not None
        assert loaded.title == "新标题"

    def test_delete(self, store: ConversationStore):
        store.create_conversation(Conversation(id="d1", title="待删除"))
        msg = Message(role=MessageRole.USER, content="hello")
        store.save_message("d1", msg)

        store.delete_conversation("d1")

        assert store.load_conversation("d1") is None
        assert store.load_messages("d1") == []

    def test_count(self, store: ConversationStore):
        assert store.get_conversation_count() == 0
        store.create_conversation(Conversation(id="n1"))
        store.create_conversation(Conversation(id="n2"))
        assert store.get_conversation_count() == 2

    def test_delete_nonexistent_is_safe(self, store: ConversationStore):
        store.delete_conversation("no_such_id")


# ---------------------------------------------------------------------------
# Message CRUD
# ---------------------------------------------------------------------------

class TestMessageCRUD:

    def test_save_and_load_simple(self, store: ConversationStore):
        store.create_conversation(Conversation(id="m1"))
        msg = Message(role=MessageRole.USER, content="你好")
        mid = store.save_message("m1", msg)
        assert isinstance(mid, int)

        msgs = store.load_messages("m1")
        assert len(msgs) == 1
        assert msgs[0].role == MessageRole.USER
        assert msgs[0].content == "你好"

    def test_load_preserves_order(self, store: ConversationStore):
        store.create_conversation(Conversation(id="m2"))
        store.save_message("m2", Message(role=MessageRole.USER, content="消息1"))
        store.save_message("m2", Message(role=MessageRole.ASSISTANT, content="回复1"))
        store.save_message("m2", Message(role=MessageRole.USER, content="消息2"))

        msgs = store.load_messages("m2")
        assert len(msgs) == 3
        assert msgs[0].content == "消息1"
        assert msgs[1].content == "回复1"
        assert msgs[2].content == "消息2"

    def test_message_with_tool_calls(self, store: ConversationStore):
        store.create_conversation(Conversation(id="m3"))
        tc = ToolCall(
            id="call_1",
            name="analyze_trace",
            arguments={"path": "/tmp/trace.perfetto-trace"},
            status=ToolCallStatus.COMPLETE,
            elapsed_ms=1234.5,
        )
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="正在分析...",
            tool_calls=[tc],
        )
        store.save_message("m3", msg)

        msgs = store.load_messages("m3")
        assert len(msgs) == 1
        loaded_tc = msgs[0].tool_calls[0]
        assert loaded_tc.id == "call_1"
        assert loaded_tc.name == "analyze_trace"
        assert loaded_tc.status == ToolCallStatus.COMPLETE
        assert loaded_tc.elapsed_ms == 1234.5
        assert loaded_tc.arguments["path"] == "/tmp/trace.perfetto-trace"

    def test_message_with_report_paths(self, store: ConversationStore):
        store.create_conversation(Conversation(id="m4"))
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="报告已生成",
            report_paths=["/out/report.md", "/out/summary.html"],
        )
        store.save_message("m4", msg)

        msgs = store.load_messages("m4")
        assert msgs[0].report_paths == ["/out/report.md", "/out/summary.html"]

    def test_message_with_token_usage(self, store: ConversationStore):
        store.create_conversation(Conversation(id="m5"))
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="完成",
            token_usage={"prompt_tokens": 150, "completion_tokens": 80},
        )
        store.save_message("m5", msg)

        msgs = store.load_messages("m5")
        assert msgs[0].token_usage["prompt_tokens"] == 150
        assert msgs[0].token_usage["completion_tokens"] == 80

    def test_message_updates_conversation_timestamp(self, store: ConversationStore):
        store.create_conversation(Conversation(id="m6"))
        before = store.load_conversation("m6")
        assert before is not None

        store.save_message("m6", Message(role=MessageRole.USER, content="ping"))

        after = store.load_conversation("m6")
        assert after is not None
        assert after.updated_at >= before.updated_at

    def test_empty_conversation_returns_empty_messages(self, store: ConversationStore):
        store.create_conversation(Conversation(id="m7"))
        assert store.load_messages("m7") == []

    def test_all_message_roles(self, store: ConversationStore):
        store.create_conversation(Conversation(id="m8"))
        for role in MessageRole:
            store.save_message(
                "m8", Message(role=role, content=f"{role.value} msg")
            )
        msgs = store.load_messages("m8")
        assert len(msgs) == len(MessageRole)
        loaded_roles = {m.role for m in msgs}
        assert loaded_roles == set(MessageRole)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestStoreEdgeCases:

    def test_unicode_content(self, store: ConversationStore):
        store.create_conversation(Conversation(id="u1", title="中文标题"))
        store.save_message(
            "u1", Message(role=MessageRole.USER, content="こんにちは 🎮")
        )
        msgs = store.load_messages("u1")
        assert msgs[0].content == "こんにちは 🎮"

    def test_multiple_tool_calls_in_one_message(self, store: ConversationStore):
        store.create_conversation(Conversation(id="u2"))
        tcs = [
            ToolCall(id=f"tc_{i}", name=f"tool_{i}", status=ToolCallStatus.COMPLETE)
            for i in range(5)
        ]
        store.save_message(
            "u2", Message(role=MessageRole.ASSISTANT, tool_calls=tcs)
        )
        msgs = store.load_messages("u2")
        assert len(msgs[0].tool_calls) == 5

    def test_db_file_auto_created(self, tmp_path: Path):
        db = tmp_path / "sub" / "deep" / "chat.db"
        s = ConversationStore(db)
        assert db.exists()
        s.close()

    def test_tool_call_id_persisted(self, store: ConversationStore):
        """tool_call_id 字段正确持久化和加载。"""
        store.create_conversation(Conversation(id="tcid1"))
        msg = Message(
            role=MessageRole.TOOL,
            content="分析完成",
            tool_call_id="call_xyz_123",
        )
        store.save_message("tcid1", msg)

        msgs = store.load_messages("tcid1")
        assert len(msgs) == 1
        assert msgs[0].tool_call_id == "call_xyz_123"

    def test_tool_call_id_empty_by_default(self, store: ConversationStore):
        store.create_conversation(Conversation(id="tcid2"))
        msg = Message(role=MessageRole.USER, content="hello")
        store.save_message("tcid2", msg)

        msgs = store.load_messages("tcid2")
        assert msgs[0].tool_call_id == ""

    def test_mixed_messages_with_tool_call_id(self, store: ConversationStore):
        """多条消息中 tool_call_id 不互相影响。"""
        store.create_conversation(Conversation(id="tcid3"))
        store.save_message("tcid3", Message(
            role=MessageRole.USER, content="请分析"
        ))
        store.save_message("tcid3", Message(
            role=MessageRole.ASSISTANT, content="",
            tool_calls=[ToolCall(id="call_1", name="analyze")],
        ))
        store.save_message("tcid3", Message(
            role=MessageRole.TOOL, content="结果OK",
            tool_call_id="call_1",
        ))
        store.save_message("tcid3", Message(
            role=MessageRole.ASSISTANT, content="分析完成",
        ))

        msgs = store.load_messages("tcid3")
        assert len(msgs) == 4
        assert msgs[0].tool_call_id == ""
        assert msgs[2].tool_call_id == "call_1"
        assert msgs[3].tool_call_id == ""
