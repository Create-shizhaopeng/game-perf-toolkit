# Implementation Plan: 分析经验自动沉淀 (G1)

**Branch**: `012-analysis-experience-auto-capture` | **Date**: 2026-04-09 | **Spec**: [spec.md](spec.md)

## 目录

- [Summary](#summary)
- [Technical Context](#technical-context)
- [Constitution Check](#constitution-check)
- [Project Structure](#project-structure)
- [Phase 0 Research](#phase-0-research)
- [Phase 1 Design](#phase-1-design)

## Summary

将 SubAgent 从自由文本输出改为 Pydantic 结构化输出（`AnalysisOutput`），实现分析经验的自动提取和持久化。核心变更：SubAgent 设置 `output_type=AnalysisOutput`，分析完成后从结构化字段直接提取根因标签、结论和定量数据写入 `pa_learnings` 表，HTML 报告基于结构化数据的三区块模板生成。

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: pydantic-ai, pydantic, jinja2  
**Storage**: SQLite (`perfetto_analysis.db`)，复用现有 DB  
**Testing**: pytest + unittest.mock  
**Target Platform**: Windows/Linux 桌面应用  
**Project Type**: 桌面工具模块  
**Performance Goals**: 经验提取 <1s，零额外 LLM 调用  
**Constraints**: 降级兜底确保 100% 不中断主流程  
**Scale/Scope**: 单模块 perfetto_analysis

## Constitution Check

| 原则 | 合规 | 说明 |
|------|------|------|
| 模块不修改 toolkit/ | ✅ | 仅修改 modules/perfetto_analysis/ |
| service.py 无 GUI 代码 | ✅ | 经验提取在 orchestrator 中 |
| Pydantic 用于公共 API | ✅ | RootCauseItem、AnalysisOutput 均为 Pydantic 模型 |
| UTF-8 输出 | ✅ | 中文输出使用 ensure_ascii=False |

## Project Structure

### 新增/修改文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/agent/__init__.py` | 修改 | 新增 RootCauseItem、AnalysisOutput 模型 |
| `src/agent/agents.py` | 修改 | SubAgent 设置 output_type=AnalysisOutput + retries=1 |
| `src/agent/orchestrator.py` | 修改 | 新增 _extract_learnings、_fallback_output、_calc_initial_confidence |
| `src/engine/storage.py` | 修改 | 新增 pa_learnings 表 CREATE + insert_learning |
| `src/agent/report.py` | 修改 | 基于 AnalysisOutput 三区块生成 HTML |
| `tests/test_g1_experience_capture.py` | 新增 | G1 单元测试 |

## Phase 0 Research

### R1: pydantic-ai output_type 重试机制

**Decision**: 使用 `Agent(output_type=AnalysisOutput, retries=1)`，pydantic-ai 内置 validation error → LLM 重试。最终失败后 catch 异常调用 `_fallback_output`。

**Rationale**: pydantic-ai 已内置输出验证和重试逻辑，无需自行实现。retries=1 在大多数情况下足够修复格式问题。

### R2: SubAgent output_type 对工具调用的影响

**Decision**: `output_type` 仅约束最终输出格式，不影响工具调用过程。SubAgent 仍可正常调用 `pa_*` 工具，只是最终响应必须符合 `AnalysisOutput` schema。

**Rationale**: pydantic-ai 的 output_type 在 tool-use agent 中仅约束最终 response，工具调用阶段的 LLM 输出不受限。

### R3: 占位符标记规范

**Decision**: `detailed_report` 中使用 `{{chart:key_name}}` 格式的占位符，key_name 对应缓存中的数据键（如 `cpu_freq`、`thread_timeline`）。报告生成时由 `report.py` 查找并替换为 HTML 图表组件。

**Rationale**: 与 Jinja2 模板的 `{{ }}` 语法一致，降低学习成本。

## Phase 1 Design

### 数据模型

```python
class RootCauseItem(BaseModel):
    tag: str                              # 根因标签: cpu_throttle, binder_ipc, gc_pause
    severity: str                         # CRITICAL / HIGH / WARNING / INFO
    qualitative: str                      # 定性描述
    quantitative: dict = Field(default_factory=dict)  # 定量数据 (Optional)
    evidence: str                         # 证据来源
    reasoning: str                        # 推理链
    suggestion: str = ""                  # 优化建议 (Optional)

class AnalysisOutput(BaseModel):
    user_intent_summary: str              # Section 1: 用户问题归纳
    trace_info: str                       # Section 1: trace 基本信息
    scene: str                            # 分析场景
    overall_conclusion: str               # Section 2: 整体结论
    root_causes: list[RootCauseItem] = Field(default_factory=list)
    detailed_report: str = ""             # Section 3: 详细分析报告（Markdown + 占位符）
```

### pa_learnings 表

```sql
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
);
```

### 经验提取流程

```
SubAgent 完成分析
      ↓
output_type=AnalysisOutput → pydantic-ai 自动解析
      ↓                              ↓
  解析成功                        解析失败 (retries=1)
      ↓                              ↓
  AnalysisOutput 实例           重试一次 → 仍失败
      ↓                              ↓
  root_causes 非空？          _fallback_output (不触发经验提取)
      ↓
  _extract_learnings → INSERT pa_learnings
```

### 降级策略

`_fallback_output` 将原始文本包装为 `AnalysisOutput`：
- `user_intent_summary`: "（结构化解析失败，以下为原始输出）"
- `root_causes`: [] （空列表，不触发经验提取）
- `detailed_report`: 完整原始文本

### HTML 报告三区块

| 区块 | 数据来源 | 内容 |
|------|---------|------|
| Section 1 | `user_intent_summary` + `trace_info` | 问题定义 + trace 概览 |
| Section 2 | `overall_conclusion` + `root_causes[]` | 分析摘要 + 根因表格 |
| Section 3 | `detailed_report` | 详细报告（占位符替换为图表） |

### 置信度计算

```python
def _calc_initial_confidence(root_causes: list[RootCauseItem]) -> float:
    if not root_causes:
        return 0.1
    severity_weights = {"CRITICAL": 0.9, "HIGH": 0.7, "WARNING": 0.5, "INFO": 0.3}
    max_severity = max(severity_weights.get(rc.severity, 0.3) for rc in root_causes)
    has_evidence = all(rc.evidence for rc in root_causes)
    return min(max_severity + (0.1 if has_evidence else 0), 1.0)
```
