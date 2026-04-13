# -*- coding: utf-8 -*-
"""SQLite 持久化：schema、按规范化 trace_path 覆盖、插入/查询。"""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

# 表结构见 data-model.md
SCHEMA = """
CREATE TABLE IF NOT EXISTS trace_run (
    trace_id TEXT PRIMARY KEY,
    trace_path TEXT NOT NULL UNIQUE,
    parsed_at_ns INTEGER,
    trace_start_ns INTEGER,
    trace_end_ns INTEGER,
    realtime_offset_ns INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vsync_cycle (
    id TEXT PRIMARY KEY,
    trace_run_id TEXT NOT NULL,
    pre_vt_ns INTEGER NOT NULL,
    vt_ns INTEGER NOT NULL,
    stand_vsync_ms REAL NOT NULL,
    FOREIGN KEY (trace_run_id) REFERENCES trace_run(trace_id)
);

CREATE TABLE IF NOT EXISTS buffer_event (
    id TEXT PRIMARY KEY,
    vsync_cycle_id TEXT NOT NULL,
    pre_bt1_ns INTEGER,
    pre_bt2_ns INTEGER,
    bt1_ns INTEGER,
    bt2_ns INTEGER,
    buffer_count_at_vt INTEGER,
    FOREIGN KEY (vsync_cycle_id) REFERENCES vsync_cycle(id)
);

CREATE TABLE IF NOT EXISTS jank_record (
    id TEXT PRIMARY KEY,
    trace_run_id TEXT NOT NULL,
    jank_num INTEGER NOT NULL,
    jank_type TEXT,
    ajt1_ns INTEGER,
    ajt2_ns INTEGER,
    sjt1_ns INTEGER,
    sjt2_ns INTEGER,
    FOREIGN KEY (trace_run_id) REFERENCES trace_run(trace_id)
);

CREATE TABLE IF NOT EXISTS trace_summary (
    trace_run_id TEXT PRIMARY KEY,
    jank_times INTEGER NOT NULL,
    frame_num INTEGER NOT NULL,
    inferred_refresh_rate_hz INTEGER,
    refresh_rate_switches TEXT,
    max_buffer_count INTEGER DEFAULT 0,
    FOREIGN KEY (trace_run_id) REFERENCES trace_run(trace_id)
);

CREATE INDEX IF NOT EXISTS idx_trace_run_path ON trace_run(trace_path);
CREATE INDEX IF NOT EXISTS idx_vsync_trace ON vsync_cycle(trace_run_id);
CREATE INDEX IF NOT EXISTS idx_jank_trace ON jank_record(trace_run_id);
"""


def _normalize_trace_path(trace_path: str | Path) -> str:
    """规范化路径为绝对路径字符串，用于唯一键。"""
    return str(Path(trace_path).resolve())


def _migrate_trace_run_columns(conn: sqlite3.Connection) -> None:
    """为已有库的 trace_run 表补充新增列（兼容旧库）。"""
    cur = conn.execute("PRAGMA table_info(trace_run)")
    cols = [row[1] for row in cur.fetchall()]
    for col in ("trace_start_ns", "trace_end_ns"):
        if col not in cols:
            conn.execute(f"ALTER TABLE trace_run ADD COLUMN {col} INTEGER")
    if "realtime_offset_ns" not in cols:
        conn.execute("ALTER TABLE trace_run ADD COLUMN realtime_offset_ns INTEGER DEFAULT 0")
    conn.commit()


def _migrate_trace_summary_columns(conn: sqlite3.Connection) -> None:
    """为已有库的 trace_summary 表补充刷新率相关列（兼容旧库）。"""
    cur = conn.execute("PRAGMA table_info(trace_summary)")
    cols = [row[1] for row in cur.fetchall()]
    for col in ("inferred_refresh_rate_hz", "refresh_rate_switches"):
        if col not in cols:
            dtype = "INTEGER" if col == "inferred_refresh_rate_hz" else "TEXT"
            conn.execute(f"ALTER TABLE trace_summary ADD COLUMN {col} {dtype}")
    if "max_buffer_count" not in cols:
        conn.execute("ALTER TABLE trace_summary ADD COLUMN max_buffer_count INTEGER DEFAULT 0")
    conn.commit()


def _migrate_jank_record_columns(conn: sqlite3.Connection) -> None:
    """为已有库的 jank_record 表补充 jank_type 列（兼容旧库）。"""
    cur = conn.execute("PRAGMA table_info(jank_record)")
    cols = [row[1] for row in cur.fetchall()]
    if "jank_type" not in cols:
        conn.execute("ALTER TABLE jank_record ADD COLUMN jank_type TEXT")
    conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    """创建/应用 schema。"""
    conn.executescript(SCHEMA)
    _migrate_trace_run_columns(conn)
    _migrate_trace_summary_columns(conn)
    _migrate_jank_record_columns(conn)
    _create_phase2_tables(conn)
    _create_telemetry_table(conn)
    _create_learnings_table(conn)
    _create_learning_embeddings_table(conn)
    conn.commit()


def _ensure_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def delete_by_trace_path(conn: sqlite3.Connection, trace_path_norm: str) -> None:
    """按规范化路径删除该 trace 的所有相关数据（覆盖策略）。"""
    cur = conn.execute(
        "SELECT trace_id FROM trace_run WHERE trace_path = ?", (trace_path_norm,)
    )
    row = cur.fetchone()
    if not row:
        return
    tid = row[0]
    conn.execute("DELETE FROM buffer_event WHERE vsync_cycle_id IN (SELECT id FROM vsync_cycle WHERE trace_run_id = ?)", (tid,))
    conn.execute("DELETE FROM vsync_cycle WHERE trace_run_id = ?", (tid,))
    conn.execute("DELETE FROM jank_record WHERE trace_run_id = ?", (tid,))
    conn.execute("DELETE FROM trace_summary WHERE trace_run_id = ?", (tid,))
    conn.execute("DELETE FROM trace_run WHERE trace_id = ?", (tid,))
    conn.commit()


def insert_trace_run(
    conn: sqlite3.Connection,
    trace_path: str | Path,
    parsed_at_ns: int | None = None,
    trace_start_ns: int | None = None,
    trace_end_ns: int | None = None,
    realtime_offset_ns: int | None = 0,
) -> str:
    """插入或替换 trace_run；先按规范化路径删除旧数据再插入。返回 trace_id。"""
    path_norm = _normalize_trace_path(trace_path)
    delete_by_trace_path(conn, path_norm)
    trace_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO trace_run (trace_id, trace_path, parsed_at_ns, trace_start_ns, trace_end_ns, realtime_offset_ns)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (trace_id, path_norm, parsed_at_ns, trace_start_ns, trace_end_ns, realtime_offset_ns or 0),
    )
    conn.commit()
    return trace_id


def insert_vsync_cycle(
    conn: sqlite3.Connection,
    trace_run_id: str,
    pre_vt_ns: int,
    vt_ns: int,
    stand_vsync_ms: float,
) -> str:
    """插入一条 vsync_cycle，返回 id。"""
    id_ = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO vsync_cycle (id, trace_run_id, pre_vt_ns, vt_ns, stand_vsync_ms)
           VALUES (?, ?, ?, ?, ?)""",
        (id_, trace_run_id, pre_vt_ns, vt_ns, stand_vsync_ms),
    )
    conn.commit()
    return id_


def insert_vsync_cycles_batch(
    conn: sqlite3.Connection,
    trace_run_id: str,
    cycles: list[tuple[int, int, float]],
) -> None:
    """批量插入 vsync_cycle，单次提交，减少 I/O。"""
    rows = [
        (str(uuid.uuid4()), trace_run_id, pre_vt_ns, vt_ns, stand_vsync_ms)
        for pre_vt_ns, vt_ns, stand_vsync_ms in cycles
    ]
    conn.executemany(
        """INSERT INTO vsync_cycle (id, trace_run_id, pre_vt_ns, vt_ns, stand_vsync_ms)
           VALUES (?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()


def insert_jank_record(
    conn: sqlite3.Connection,
    trace_run_id: str,
    jank_num: int,
    jank_type: str | None = None,
    ajt1_ns: int | None = None,
    ajt2_ns: int | None = None,
    sjt1_ns: int | None = None,
    sjt2_ns: int | None = None,
) -> str:
    """插入一条 jank_record，返回 id。"""
    id_ = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO jank_record (id, trace_run_id, jank_num, jank_type, ajt1_ns, ajt2_ns, sjt1_ns, sjt2_ns)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (id_, trace_run_id, jank_num, jank_type, ajt1_ns, ajt2_ns, sjt1_ns, sjt2_ns),
    )
    conn.commit()
    return id_


def insert_jank_records_batch(
    conn: sqlite3.Connection,
    trace_run_id: str,
    records: list[dict[str, Any]],
) -> None:
    """批量插入 jank_record，单次提交。records 每项含 jank_num, jank_type, ajt1_ns, ajt2_ns, sjt1_ns, sjt2_ns。"""
    rows = [
        (
            str(uuid.uuid4()),
            trace_run_id,
            r["jank_num"],
            r.get("jank_type"),
            r.get("ajt1_ns"),
            r.get("ajt2_ns"),
            r.get("sjt1_ns"),
            r.get("sjt2_ns"),
        )
        for r in records
    ]
    conn.executemany(
        """INSERT INTO jank_record (id, trace_run_id, jank_num, jank_type, ajt1_ns, ajt2_ns, sjt1_ns, sjt2_ns)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()


def insert_trace_summary(
    conn: sqlite3.Connection,
    trace_run_id: str,
    jank_times: int,
    frame_num: int,
    inferred_refresh_rate_hz: int | None = None,
    refresh_rate_switches: list[dict[str, Any]] | None = None,
    max_buffer_count: int = 0,
) -> None:
    """插入或替换 trace_summary。refresh_rate_switches 存为 JSON 字符串。"""
    switches_json = (
        json.dumps(refresh_rate_switches, ensure_ascii=False)
        if refresh_rate_switches is not None
        else None
    )
    conn.execute(
        """INSERT OR REPLACE INTO trace_summary
           (trace_run_id, jank_times, frame_num, inferred_refresh_rate_hz, refresh_rate_switches, max_buffer_count)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (trace_run_id, jank_times, frame_num, inferred_refresh_rate_hz, switches_json, max_buffer_count),
    )
    conn.commit()


def _create_learning_embeddings_table(conn: sqlite3.Connection) -> None:
    """创建 G2 经验 embedding 虚拟表（需要 sqlite-vec 扩展）。"""
    try:
        import sqlite_vec
        sqlite_vec.load(conn)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS pa_learning_embeddings USING vec0(
                learning_id INTEGER PRIMARY KEY,
                embedding FLOAT[384]
            )
        """)
        conn.commit()
    except (ImportError, Exception):
        pass


def insert_learning_embedding(
    conn: sqlite3.Connection,
    learning_id: int,
    embedding_blob: bytes,
) -> None:
    """写入一条经验 embedding 记录。embedding_blob 是序列化后的向量。"""
    conn.execute(
        "INSERT INTO pa_learning_embeddings (learning_id, embedding) VALUES (?, ?)",
        (learning_id, embedding_blob),
    )
    conn.commit()


def _create_learnings_table(conn: sqlite3.Connection) -> None:
    """创建 G1 经验表 pa_learnings。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pa_learnings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id         TEXT,
            trace_id        TEXT NOT NULL,
            scene           TEXT NOT NULL,
            device_model    TEXT,
            process_name    TEXT,
            root_cause_tags TEXT NOT NULL,
            insight         TEXT NOT NULL,
            key_metrics     TEXT,
            confidence      REAL DEFAULT 0.5,
            hit_count       INTEGER DEFAULT 0,
            last_used       TEXT,
            created_at      TEXT NOT NULL,
            promoted        INTEGER DEFAULT 0,
            archived        INTEGER DEFAULT 0
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_learnings_scene ON pa_learnings(scene)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_learnings_tags ON pa_learnings(root_cause_tags)"
    )
    conn.commit()


def _create_telemetry_table(conn: sqlite3.Connection) -> None:
    """创建 G0 遥测表 pa_telemetry。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pa_telemetry (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id                 TEXT,
            trace_id                TEXT,
            scene                   TEXT,
            model_name              TEXT,
            tool_call_count         INTEGER,
            tool_calls_detail       TEXT,
            total_prompt_tokens     INTEGER,
            total_completion_tokens INTEGER,
            conclusion_quality      TEXT,
            elapsed_sec             REAL,
            created_at              TEXT NOT NULL
        )
    """)
    conn.commit()


def _create_phase2_tables(conn: sqlite3.Connection) -> None:
    """创建 Phase 2 新增表（cpu_topology + analysis_report）。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cpu_topology (
            trace_run_id TEXT PRIMARY KEY,
            topology_json TEXT NOT NULL,
            total_cpu_count INTEGER NOT NULL,
            FOREIGN KEY (trace_run_id) REFERENCES trace_run(trace_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_report (
            id TEXT PRIMARY KEY,
            trace_run_id TEXT NOT NULL,
            report_type TEXT NOT NULL,
            dimension TEXT NOT NULL,
            file_path TEXT NOT NULL,
            format TEXT NOT NULL DEFAULT 'md',
            created_at INTEGER NOT NULL,
            FOREIGN KEY (trace_run_id) REFERENCES trace_run(trace_id)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_trace ON analysis_report(trace_run_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_type ON analysis_report(report_type, dimension)"
    )
    conn.commit()


def delete_phase2_by_trace_run(conn: sqlite3.Connection, trace_run_id: str) -> None:
    """删除指定 trace 的所有 Phase 2 DB 数据。文件覆盖由 report_writer 处理。"""
    conn.execute("DELETE FROM cpu_topology WHERE trace_run_id = ?", (trace_run_id,))
    conn.execute("DELETE FROM analysis_report WHERE trace_run_id = ?", (trace_run_id,))
    conn.commit()


def insert_cpu_topology(
    conn: sqlite3.Connection,
    trace_run_id: str,
    topology_json: str,
    total_cpu_count: int,
) -> None:
    """插入或替换 cpu_topology 记录。"""
    conn.execute(
        """INSERT OR REPLACE INTO cpu_topology (trace_run_id, topology_json, total_cpu_count)
           VALUES (?, ?, ?)""",
        (trace_run_id, topology_json, total_cpu_count),
    )
    conn.commit()


def insert_analysis_report(
    conn: sqlite3.Connection,
    trace_run_id: str,
    report_type: str,
    dimension: str,
    file_path: str,
    fmt: str = "md",
) -> str:
    """插入或替换 analysis_report 记录，返回 id。"""
    import time

    id_ = str(uuid.uuid4())
    created_at = int(time.time() * 1e9)
    conn.execute(
        """INSERT OR REPLACE INTO analysis_report
           (id, trace_run_id, report_type, dimension, file_path, format, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (id_, trace_run_id, report_type, dimension, file_path, fmt, created_at),
    )
    conn.commit()
    return id_


def insert_telemetry(
    conn: sqlite3.Connection,
    task_id: str,
    trace_id: str,
    scene: str,
    model_name: str,
    tool_call_count: int,
    tool_calls_detail: str,
    total_prompt_tokens: int,
    total_completion_tokens: int,
    conclusion_quality: str,
    elapsed_sec: float,
) -> None:
    """写入一条分析遥测记录。"""
    from datetime import datetime

    conn.execute(
        """INSERT INTO pa_telemetry
           (task_id, trace_id, scene, model_name, tool_call_count,
            tool_calls_detail, total_prompt_tokens, total_completion_tokens,
            conclusion_quality, elapsed_sec, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            task_id, trace_id, scene, model_name, tool_call_count,
            tool_calls_detail, total_prompt_tokens, total_completion_tokens,
            conclusion_quality, elapsed_sec,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()


def insert_learning(
    conn: sqlite3.Connection,
    task_id: str,
    trace_id: str,
    scene: str,
    root_cause_tags: str,
    insight: str,
    device_model: str | None = None,
    process_name: str | None = None,
    key_metrics: str | None = None,
    confidence: float = 0.5,
) -> int:
    """写入一条分析经验记录，返回自增 id。"""
    from datetime import datetime

    cursor = conn.execute(
        """INSERT INTO pa_learnings
           (task_id, trace_id, scene, device_model, process_name,
            root_cause_tags, insight, key_metrics, confidence,
            hit_count, last_used, created_at, promoted, archived)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, 0, 0)""",
        (
            task_id, trace_id, scene, device_model, process_name,
            root_cause_tags, insight, key_metrics, confidence,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    return cursor.lastrowid or 0


def get_connection(db_path: str) -> sqlite3.Connection:
    """获取已初始化 schema 的连接。"""
    return _ensure_connection(db_path)


def list_trace_runs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """列出所有 trace_run（用于导出）。含 trace_start_ns, trace_end_ns, realtime_offset_ns。"""
    cur = conn.execute(
        """SELECT trace_id, trace_path, parsed_at_ns, trace_start_ns, trace_end_ns, realtime_offset_ns
           FROM trace_run ORDER BY parsed_at_ns"""
    )
    return [dict(row) for row in cur.fetchall()]


def get_jank_records(conn: sqlite3.Connection, trace_run_id: str) -> list[dict[str, Any]]:
    """获取指定 trace_run 的 jank_record。"""
    cur = conn.execute(
        """SELECT id, trace_run_id, jank_num, jank_type, ajt1_ns, ajt2_ns, sjt1_ns, sjt2_ns
           FROM jank_record WHERE trace_run_id = ? ORDER BY ajt1_ns""",
        (trace_run_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def get_trace_summary(conn: sqlite3.Connection, trace_run_id: str) -> dict[str, Any] | None:
    """获取指定 trace_run 的 trace_summary。refresh_rate_switches 解析为 list。"""
    cur = conn.execute(
        """SELECT trace_run_id, jank_times, frame_num, inferred_refresh_rate_hz, refresh_rate_switches, max_buffer_count
           FROM trace_summary WHERE trace_run_id = ?""",
        (trace_run_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    if d.get("refresh_rate_switches") and isinstance(d["refresh_rate_switches"], str):
        try:
            d["refresh_rate_switches"] = json.loads(d["refresh_rate_switches"])
        except (json.JSONDecodeError, TypeError):
            d["refresh_rate_switches"] = []
    elif d.get("refresh_rate_switches") is None:
        d["refresh_rate_switches"] = []
    return d
