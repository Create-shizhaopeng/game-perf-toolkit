-- perfetto_analysis 共享 DB 索引表
-- 用于跨模块发现分析任务

CREATE TABLE IF NOT EXISTS pa_analysis_tasks (
    task_id TEXT PRIMARY KEY,
    trace_path TEXT NOT NULL,
    device_serial TEXT DEFAULT '',
    analysis_db_path TEXT NOT NULL,
    report_dir_path TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at INTEGER NOT NULL,
    completed_at INTEGER,
    error_message TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_pa_tasks_status ON pa_analysis_tasks(status);
CREATE INDEX IF NOT EXISTS idx_pa_tasks_trace ON pa_analysis_tasks(trace_path);
