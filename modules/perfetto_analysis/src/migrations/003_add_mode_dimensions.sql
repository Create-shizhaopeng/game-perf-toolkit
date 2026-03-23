-- 添加 mode 和 dimensions 列到 pa_analysis_tasks 表
ALTER TABLE pa_analysis_tasks ADD COLUMN mode TEXT DEFAULT 'full';
ALTER TABLE pa_analysis_tasks ADD COLUMN dimensions TEXT DEFAULT '';
