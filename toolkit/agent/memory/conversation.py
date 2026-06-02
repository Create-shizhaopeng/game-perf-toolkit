# -*- coding: utf-8 -*-
"""Agent 对话持久化存储（SQLite）。"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models import Conversation, Message, MessageRole, ToolCall, ToolCallStatus

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL DEFAULT '',
    sop_used      TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id   TEXT NOT NULL,
    role              TEXT NOT NULL,
    content           TEXT NOT NULL DEFAULT '',
    tool_call_id      TEXT NOT NULL DEFAULT '',
    tool_calls_json   TEXT NOT NULL DEFAULT '[]',
    report_paths_json TEXT NOT NULL DEFAULT '[]',
    token_usage_json  TEXT NOT NULL DEFAULT '{}',
    created_at        TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
"""

_ISO_FMT = "%Y-%m-%dT%H:%M:%S"


class ConversationStore:
    """SQLite 对话存储。

    每个实例持有独立的 sqlite3 连接，确保线程安全
    （不同 QThread 使用不同实例）。
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- Conversation CRUD -------------------------------------------------

    def create_conversation(self, conv: Conversation) -> str:
        now = conv.created_at.strftime(_ISO_FMT)
        self._conn.execute(
            "INSERT INTO conversations (id, title, sop_used, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (conv.id, conv.title, conv.sop_used, now, now),
        )
        self._conn.commit()
        return conv.id

    def list_conversations(self) -> list[dict[str, Any]]:
        """按更新时间倒序返回所有会话摘要。"""
        cur = self._conn.execute(
            "SELECT id, title, sop_used, created_at, updated_at "
            "FROM conversations ORDER BY updated_at DESC",
        )
        return [
            {
                "id": row[0],
                "title": row[1],
                "sop_used": row[2],
                "created_at": row[3],
                "updated_at": row[4],
            }
            for row in cur.fetchall()
        ]

    def load_conversation(self, conv_id: str) -> Conversation | None:
        cur = self._conn.execute(
            "SELECT id, title, sop_used, created_at, updated_at "
            "FROM conversations WHERE id = ?",
            (conv_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return Conversation(
            id=row[0],
            title=row[1],
            sop_used=row[2],
            created_at=datetime.strptime(row[3], _ISO_FMT),
            updated_at=datetime.strptime(row[4], _ISO_FMT),
        )

    def rename_conversation(self, conv_id: str, title: str) -> None:
        self._conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, datetime.now().strftime(_ISO_FMT), conv_id),
        )
        self._conn.commit()

    def delete_conversation(self, conv_id: str) -> None:
        self._conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
        self._conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        self._conn.commit()

    # -- Message CRUD ------------------------------------------------------

    def save_message(self, conv_id: str, msg: Message) -> int:
        """保存消息并更新会话的 updated_at。返回消息 ID。"""
        tool_calls_json = json.dumps(
            [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "status": tc.status.value,
                    "elapsed_ms": tc.elapsed_ms,
                }
                for tc in msg.tool_calls
            ],
            ensure_ascii=False,
        )
        cur = self._conn.execute(
            "INSERT INTO messages "
            "(conversation_id, role, content, tool_call_id, tool_calls_json, "
            "report_paths_json, token_usage_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                conv_id,
                msg.role.value,
                msg.content,
                msg.tool_call_id,
                tool_calls_json,
                json.dumps(msg.report_paths, ensure_ascii=False),
                json.dumps(msg.token_usage, ensure_ascii=False),
                msg.created_at.strftime(_ISO_FMT),
            ),
        )
        self._conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (datetime.now().strftime(_ISO_FMT), conv_id),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def load_messages(self, conv_id: str) -> list[Message]:
        cur = self._conn.execute(
            "SELECT role, content, tool_call_id, tool_calls_json, "
            "report_paths_json, token_usage_json, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id ASC",
            (conv_id,),
        )
        msgs: list[Message] = []
        for row in cur.fetchall():
            raw_tc = json.loads(row[3])
            tool_calls = [
                ToolCall(
                    id=tc.get("id", ""),
                    name=tc.get("name", ""),
                    arguments=tc.get("arguments", {}),
                    status=ToolCallStatus(tc.get("status", "pending")),
                    elapsed_ms=tc.get("elapsed_ms", 0.0),
                )
                for tc in raw_tc
            ]
            msgs.append(
                Message(
                    role=MessageRole(row[0]),
                    content=row[1],
                    tool_call_id=row[2],
                    tool_calls=tool_calls,
                    report_paths=json.loads(row[4]),
                    token_usage=json.loads(row[5]),
                    created_at=datetime.strptime(row[6], _ISO_FMT),
                )
            )
        return msgs

    def get_conversation_count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM conversations")
        return cur.fetchone()[0]
