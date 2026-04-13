# Agent 记忆与经验系统 — 架构总览

## 目录

- [完整架构图](#完整架构图)
- [数据流时序](#数据流时序)
- [组件交互矩阵](#组件交互矩阵)
- [数据模型汇总](#数据模型汇总)
- [设计一致性检查](#设计一致性检查)

## 完整架构图

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                              触发入口                                       ║
║  ┌──────────────────┐    ┌──────────────────────────────────┐              ║
║  │ 用户手动分析      │    │ 自动抓取 (perfetto_capture)      │              ║
║  │ 意图 + trace路径  │    │ DB 预填 jank/process + 固定意图  │              ║
║  └────────┬─────────┘    └──────────────┬───────────────────┘              ║
╚═══════════╪═════════════════════════════╪════════════════════════════════════╝
            │                             │
            ▼                             ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  编排器 (AnalysisOrchestrator)                                    [G0]     ║
║                                                                            ║
║  Phase 0 ─── MainAgent 意图路由                                            ║
║              输入: 意图 + trace_overview + [DB预填信息]                      ║
║              输出: AnalysisRouting(scene, process_name, ...)                ║
║                    │                                                       ║
║                    ▼                                                       ║
║  Phase 1 ─── 场景感知预取                                                   ║
║              ├── jank: detect_jank → 卡顿帧窗口                            ║
║              ├── anr: analyze_anr概览                                      ║
║              ├── startup: find_slices概览                                   ║
║              └── cpu/general: dimension概览                                 ║
║              输出: prefetch_result + prefetch_issue_tags                    ║
║                    │                                                       ║
║                    ▼                                                       ║
║  Phase 1.5 ── G2 历史案例检索 ◄───────────────────────────────── [G2]      ║
║              ├── L1: SQL标签交叉匹配 (scene + issue_tags)                   ║
║              └── L2: 向量语义搜索 (可选, L1不足时)                           ║
║              输出: injected_cases (≤3条, ≤500 token)                       ║
║                    │                                                       ║
║                    ▼                                                       ║
║  Prompt 组装 ── 推理链 + 精简SOP + 预取结果 + 历史案例 ◄───── [G0+G5]     ║
║                    │                                                       ║
╚════════════════════╪═══════════════════════════════════════════════════════╝
                     │
                     ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  SubAgent (Pydantic AI Agent)                                    [G0+G5]   ║
║                                                                            ║
║  instructions: 精简版 SOP (判断条件+阈值+引用指针)                          ║
║  output_type:  AnalysisOutput (Pydantic)                         [G1]      ║
║  request_limit: 50 (安全网)                                      [G0]      ║
║                                                                            ║
║  工具集 (10个):                                                            ║
║  ┌─────────────────────────────────────────────────────────────────┐       ║
║  │ pa_trace_overview   pa_detect_jank    pa_analyze_dimension     │       ║
║  │ pa_list_dimensions  pa_get_history    pa_find_slices           │       ║
║  │ pa_execute_sql      pa_analyze_anr    pa_analyze_memory        │       ║
║  │ pa_read_knowledge ◄── 新增, 读取 Skill L2/L3 知识资产  [G5]   │       ║
║  └──────────────────────────┬──────────────────────────────────────┘       ║
║                             │                                              ║
║  工具返回 → 结构化压缩 (异常完整保留 + 正常精简)                [G0 Step2]  ║
║           → 结果缓存 (避免重复查询 trace)                       [G0 Step2]  ║
║                                                                            ║
║  推理链: Phase A(根因排查) → Phase B(交叉验证) → Phase C(输出报告)         ║
║                             │                                              ║
║                             ▼                                              ║
║  输出: AnalysisOutput                                            [G1]      ║
║  ┌──────────────────────────────────────────────────────────────┐          ║
║  │ Section 1: user_intent_summary + trace_info                  │          ║
║  │ Section 2: scene + overall_conclusion + root_causes[]        │          ║
║  │ Section 3: detailed_report (Markdown)                        │          ║
║  └──────────────────────────────────────────────────────────────┘          ║
╚════════════════════════════════════════════════════════════════════════════╝
                     │
                     ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  后处理 (orchestrator._finalize)                                           ║
║                                                                            ║
║  ┌───────────────────────────────────────────────────────────────────┐     ║
║  │                                                                   │     ║
║  │  1. HTML报告生成 ──────────────────────────────────────────────── │     ║
║  │     Section 1 → 问题定义区块                                      │     ║
║  │     Section 2 → 分析摘要区块 (根因表格+方案建议)                   │     ║
║  │     Section 3 → 详细分析区块 (可视化+折叠日志)                     │     ║
║  │                                                                   │     ║
║  │  2. G1 经验提取 ─────────────────────────────────────── [G1]     │     ║
║  │     AnalysisOutput.root_causes → root_cause_tags                  │     ║
║  │     AnalysisOutput.overall_conclusion → insight                   │     ║
║  │     root_causes[].quantitative → key_metrics                      │     ║
║  │     _calc_initial_confidence → confidence                         │     ║
║  │     → 写入 pa_learnings 表                                        │     ║
║  │                                                                   │     ║
║  │  3. G2 命中反馈 ─────────────────────────────────────── [G2]     │     ║
║  │     result_tags ∩ injected_case_tags → hit_count += 1             │     ║
║  │                                                                   │     ║
║  │  4. 包名学习 ──────────────────────────────────────── [G6]       │     ║
║  │     process_name → PackageMappingDB.learn()                       │     ║
║  │                                                                   │     ║
║  │  5. 插桩记录 ──────────────────────────────────────── [G0 Step3] │     ║
║  │     tool_call_count, tokens, elapsed → pa_telemetry 表            │     ║
║  │                                                                   │     ║
║  └───────────────────────────────────────────────────────────────────┘     ║
║                             │                                              ║
║                             ▼                                              ║
║  Review 判断 ─── _should_review(outputs) ────────────────── [G4]          ║
║  ├── 批量 + 同 scene → cross_compare                                      ║
║  ├── 单 trace + 根因≥3 或 低置信度 → self_check                           ║
║  └── 否 → 跳过                                                            ║
║                             │                                              ║
║                             ▼ (如果触发)                                   ║
║  ReviewAgent ── 结构化输入 → ReviewResult ────────────────── [G4]         ║
║  └── confidence_adjustments → 写回 pa_learnings.confidence                ║
║                                                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  定期维护 (每20次分析触发 / 手动触发)                             [G3]      ║
║                                                                            ║
║  pa_learnings 评分 ── memory_score(recency × importance × frequency)       ║
║  ├── score < 0.05 → archived = 1                                          ║
║  ├── score ∈ [0.05, 0.3) → 保留, 低优先级                                 ║
║  └── score ≥ 0.3 且 hit_count ≥ 3 → LLM 评审                             ║
║      └── promote / merge / archive / keep                                  ║
║                                                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  数据存储层                                                                ║
║                                                                            ║
║  perfetto_analysis.db                                                      ║
║  ├── pa_analysis_tasks     (现有)                                          ║
║  ├── pa_learnings          (新增, G1)                                      ║
║  ├── pa_learning_embeddings(新增, G2 L2, 可选)                             ║
║  ├── pa_telemetry          (新增, G0 Step3)                                ║
║  └── pa_package_mappings   (现有, G6 接线)                                  ║
║                                                                            ║
║  Skill 知识资产 (只读, G5)                                                 ║
║  skills/perfetto-analysis/                                                 ║
║  ├── sop/*.md              (L1, 精简后注入 instructions)                    ║
║  ├── patterns/*.md         (L2, pa_read_knowledge 按需拉取)                 ║
║  ├── sql-patterns.md       (L2, pa_read_knowledge 按需拉取)                 ║
║  └── cases/*.md            (L3, pa_read_knowledge 按需拉取)                 ║
║                                                                            ║
║  内存缓存 (会话级)                                                         ║
║  └── PerfettoAnalysisService._analysis_cache (G0 Step2)                    ║
║                                                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

## 数据流时序

```
时间线 ──────────────────────────────────────────────────────────►

1. 触发     │ 用户/自动抓取
2. Phase 0  │ MainAgent路由 → scene
3. Phase 1  │ 场景预取 → prefetch_result + issue_tags
4. G2 检索  │ L1标签匹配 → [L2向量搜索] → injected_cases
5. 组装     │ 推理链 + 精简SOP + 预取 + 案例 → prompt
6. SubAgent │ Phase A→B→C → AnalysisOutput
7. 报告     │ HTML 三区块生成
8. G1 提取  │ AnalysisOutput → pa_learnings
9. G2 反馈  │ result_tags ∩ case_tags → hit_count++
10. G6 学习 │ process_name → PackageMappingDB
11. 插桩    │ telemetry → pa_telemetry
12. G4 判断 │ _should_review → [ReviewAgent]
13. G4 校准 │ confidence_adjustments → pa_learnings

定期:
14. G3 维护 │ 每20次 → 评分 → LLM审评 → promote/merge/archive
```

## 组件交互矩阵

```
              G0   G1   G2   G3   G4   G5   G6   DB   Skill  Cache
G0 推理链     —    写入  读取  —    —    读取  —    写T   读SOP  写/读
G1 经验沉淀  依赖  —    写入  读取  写回  —    —    写L   —     读
G2 案例注入  依赖  依赖  —    —    —    —    —    读L   —     —
G3 淘汰晋升   —   依赖  依赖  —    —    —    —    读写L —     —
G4 Review    依赖  依赖  —    —    —    —    —    写L   —     —
G5 SOP分层   互补   —    —    —    —    —    —    —    读L2   —
G6 package   独立   —    —    —    —    —    —    写P   —     —

DB: L=pa_learnings, T=pa_telemetry, P=pa_package_mappings
Skill: SOP=sop/*.md, L2=patterns/sql-patterns
Cache: PerfettoAnalysisService._analysis_cache
```

## 数据模型汇总

### pa_learnings（G1 创建, G2/G3/G4 读写）

```sql
CREATE TABLE pa_learnings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT,
    trace_id        TEXT NOT NULL,
    scene           TEXT NOT NULL,
    device_model    TEXT,
    process_name    TEXT,
    root_cause_tags TEXT NOT NULL,
    insight         TEXT NOT NULL,
    key_metrics     TEXT,              -- JSON
    confidence      REAL DEFAULT 0.5,
    hit_count       INTEGER DEFAULT 0,
    last_used       TEXT,
    created_at      TEXT NOT NULL,
    promoted        INTEGER DEFAULT 0,
    archived        INTEGER DEFAULT 0  -- ← G3 需要, G1 schema 中需补充
);
```

### pa_learning_embeddings（G2 L2, 可选）

```sql
CREATE TABLE pa_learning_embeddings (
    learning_id INTEGER PRIMARY KEY REFERENCES pa_learnings(id),
    embedding   BLOB NOT NULL          -- float32 向量
);
```

### pa_telemetry（G0 Step3 插桩）

```sql
CREATE TABLE pa_telemetry (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id                TEXT,
    scene                   TEXT,
    model_name              TEXT,
    tool_call_count         INTEGER,
    tool_calls_detail       TEXT,      -- JSON
    total_prompt_tokens     INTEGER,
    total_completion_tokens INTEGER,
    conclusion_quality      TEXT,      -- JSON (quality_warnings)
    elapsed_sec             REAL,
    created_at              TEXT NOT NULL
);
```

## 设计一致性检查

### 已发现并修复的缺漏

| # | 问题 | 涉及 | 修复方案 | 状态 |
|---|------|------|---------|------|
| 1 | `pa_learnings` 缺少 `archived` 字段 | G1 vs G3 | G1 schema 加 `archived INTEGER DEFAULT 0` | ✅ 已修复 |
| 2 | `pa_telemetry` 缺完整 schema | G0 Step3 | 补充完整 CREATE TABLE | ✅ 已修复 |
| 3 | `pa_read_knowledge` 压缩策略未明确 | G5 vs G0 | 采用两级加载：L1 目录概览，L2 章节详情 | ✅ 已修复 |
| 4 | G2 SQL 未过滤 `archived` | G2 vs G3 | 3 处 SQL 均加 `AND archived = 0` | ✅ 已修复 |
| 5 | `AnalysisOutput` 字段可靠性 | G0+G1 | `suggestion`/`detailed_report` 可选 + 降级兜底 | ✅ 已修复 |
| 6 | Phase 1 预取未入缓存 | G0 Step1 vs Step2 | 预取结果写入 `_analysis_cache` | ✅ 已修复 |
| 7 | `memory_score` 含 exp 运算不适合纯 SQL | G3 | 应用层计算后排序取 top-10 | ✅ 已修复 |

### 无冲突确认

| 检查项 | 结论 |
|--------|------|
| G0 推理链 vs G5 SOP | 互补无冲突：推理链定义通用框架，SOP 提供场景特化规则 |
| G1 结构化输出 vs G4 Review | 一致：Review 输入来自 AnalysisOutput，G1 提取也来自同一数据源 |
| G2 案例注入 vs G0 prompt 组装 | 顺序明确：Phase 0→1→G2→组装→SubAgent |
| G3 淘汰 vs G2 检索 | 一致：promoted/archived 条目被 G2 正确过滤（修复 #4 后） |
| G6 接线 vs 编排器 | 独立无冲突 |
| 内存缓存 vs DB 存储 | 互补：缓存是会话级加速，DB 是持久化存储 |
