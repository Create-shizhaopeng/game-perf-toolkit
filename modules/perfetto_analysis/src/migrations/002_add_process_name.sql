-- 添加 process_name 列到 pa_analysis_tasks 表
ALTER TABLE pa_analysis_tasks ADD COLUMN process_name TEXT DEFAULT '';
