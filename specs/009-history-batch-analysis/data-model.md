# Data Model: 历史面板批量操作与 Perfetto AI 分析

**Feature**: 009-history-batch-analysis  
**Date**: 2026-04-03

## 目录

- [实体关系概览](#实体关系概览)
- [新增/扩展模型](#新增扩展模型)
  - [AnalysisTask](#analysistask)
  - [AnalysisStatus](#analysisstatus)
  - [AnalysisReport](#analysisreport)
  - [PackageMapping](#packagemapping)
  - [ConversationMessage](#conversationmessage)
  - [AgentRole](#agentrole)
  - [AnalysisConfig](#analysisconfig)
- [现有模型扩展](#现有模型扩展)
  - [HistoryTrace 扩展](#historytrace-扩展)
- [数据库 Schema 变更](#数据库-schema-变更)

## 实体关系概览

```
HistorySession 1──N HistoryTrace
                         │
                    0──N AnalysisTask (一个 trace 可多次分析)
                         │
                    1──1 AnalysisReport
                         │
                    0──N ConversationMessage

PackageMapping (独立表，学习型)
AnalysisConfig (配置，存 config.json)
```

## 新增/扩展模型

### AnalysisTask

分析任务，记录一次分析的完整状态。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | str (UUID) | 任务唯一标识 |
| trace_path | str | 待分析 trace 文件路径 |
| process_name | str | 目标进程名（可空） |
| user_intent | str | 用户输入的分析意图 |
| scene | str | AI 路由的分析场景（jank/anr/memory/startup 等） |
| status | AnalysisStatus | 当前状态 |
| agent_role | AgentRole | 当前执行阶段的 Agent 角色 |
| result_dir | str | 分析结果文件夹路径（可空） |
| error_message | str | 失败时的错误信息 |
| token_used | int | 本次分析消耗的 token 数 |
| created_at | datetime | 创建时间 |
| completed_at | datetime | 完成时间（可空） |

### AnalysisStatus

分析状态枚举。

| 值 | 说明 |
|---|---|
| PENDING | 排队中 |
| ROUTING | 意图分析/场景路由中 |
| ANALYZING | Sub Agent 分析中 |
| REVIEWING | Review Agent 评审中 |
| REPORTING | 生成报告中 |
| COMPLETED | 完成 |
| FAILED | 失败 |
| CANCELLED | 用户取消 |
| TIMEOUT | 超时 |

### AnalysisReport

分析报告元数据。

| 字段 | 类型 | 说明 |
|---|---|---|
| task_id | str | 关联的 AnalysisTask ID |
| html_path | str | HTML 报告文件路径 |
| raw_data_dir | str | 原始数据子文件夹路径 |
| summary | str | 结论摘要（纯文本） |
| trace_overview | dict | trace 概览信息（时长、帧数等） |
| root_causes | list[dict] | 根因列表（severity、description、evidence） |

### PackageMapping

包名与进程名的映射关系。

| 字段 | 类型 | 说明 |
|---|---|---|
| package_name | str | 应用包名（如 com.tencent.tmgp.cod） |
| app_name | str | 应用显示名（如"使命召唤手游"） |
| process_names | list[str] | 关联的进程名列表 |
| source | str | 来源：auto_learn / manual / imported |
| updated_at | datetime | 最后更新时间 |

### ConversationMessage

对话消息，用于右栏对话区域显示。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | str (UUID) | 消息唯一标识 |
| task_id | str | 关联的 AnalysisTask ID |
| role | str | 角色：user / assistant / tool / system |
| content | str | 消息内容 |
| tool_name | str | 工具调用名称（role=tool 时） |
| tool_result | dict | 工具返回结果（role=tool 时） |
| timestamp | datetime | 时间戳 |

### AgentRole

Agent 角色枚举。

| 值 | 说明 |
|---|---|
| MAIN | 主编排 Agent |
| SUB | 独立分析 Sub Agent |
| REVIEW | 评审 Agent |

### AnalysisConfig

分析配置，存储在全局 config.json 中。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| parallel_count | int | 1 | 批量分析并行数（1=串行） |
| analysis_timeout_sec | int | 300 | 单次分析超时（秒） |
| auto_open_report | bool | True | 分析完成后自动打开浏览器 |
| user_trace_dir | str | "user_traces" | 用户拖入 trace 的托管目录名 |

## 现有模型扩展

### HistoryTrace 扩展

在现有 `HistoryTrace` 数据类中增加分析相关字段。

| 新增字段 | 类型 | 说明 |
|---|---|---|
| analysis_status | AnalysisStatus \| None | 最近一次分析的状态 |
| target_package | str | 目标包名（来自 jank 监控元数据） |
| last_analysis_id | str \| None | 最近一次分析任务 ID |

## 数据库 Schema 变更

### history.db 扩展（perfetto_capture 模块）

```sql
-- 现有 traces 表增加列
ALTER TABLE traces ADD COLUMN analysis_status TEXT;
ALTER TABLE traces ADD COLUMN target_package TEXT;
ALTER TABLE traces ADD COLUMN last_analysis_id TEXT;
```

### 新增表（perfetto_capture 或共享 DB）

```sql
CREATE TABLE IF NOT EXISTS analysis_tasks (
    id TEXT PRIMARY KEY,
    trace_path TEXT NOT NULL,
    process_name TEXT,
    user_intent TEXT,
    scene TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    result_dir TEXT,
    error_message TEXT,
    token_used INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS package_mappings (
    package_name TEXT PRIMARY KEY,
    app_name TEXT,
    process_names TEXT,  -- JSON array
    source TEXT DEFAULT 'auto_learn',
    updated_at TEXT NOT NULL
);
```
