# Data Model: LLM Prompt 预算管理

**Date**: 2026-04-05

## 目录

- [实体关系](#实体关系)
- [ToolReturn (Pydantic AI 原生)](#toolreturn-pydantic-ai-原生)
- [CompressedToolOutput (新增)](#compressedtooloutput-新增)
- [StepResult (已有，需扩展)](#stepresult-已有需扩展)
- [状态转换](#状态转换)

## 实体关系

```
ToolReturn (Pydantic AI 原生)
  ├── return_value: str          → 压缩后摘要，发送给 LLM
  ├── metadata: dict             → 原始数据 + 元信息，不发送给 LLM
  └── content: str | None        → 额外内容（暂不使用）

CompressedToolOutput (ResultCompressor 输出)
  ├── summary: str               → 统计摘要
  ├── top_items: list[dict]      → Top-5 关键条目
  ├── total_count: int           → 原始数据总数
  └── token_estimate: int        → 预估 token 数

SCENE_SOP_MAP (已有，不变)
  └── Dict[str, str]             → 场景名 → SOP 文件名
```

## ToolReturn (Pydantic AI 原生)

**来源**: `pydantic_ai.tools.ToolReturn`
**用途**: 分离 LLM 可见内容和应用层数据

| 字段 | 类型 | 说明 |
|---|---|---|
| return_value | ToolReturnContent | 压缩后的文本摘要，发送给 LLM (~300 token) |
| content | str \| Sequence \| None | 额外内容（本次不使用） |
| metadata | Any | 原始工具返回数据 + 元信息，不发送给 LLM |

**metadata 结构**:

```python
{
    "raw": dict,           # 工具原始返回数据
    "tool_name": str,      # 工具名称
    "token_saved": int,    # 节省的 token 数估算
}
```

## CompressedToolOutput (新增)

**位置**: `modules/perfetto_analysis/src/result_compressor.py`
**用途**: ResultCompressor 的工具输出压缩结果

不需要新增 Pydantic 模型——压缩结果直接以格式化字符串形式作为 `ToolReturn.return_value`。格式化策略按工具类型区分：

| 工具 | 压缩策略 | 输出格式 |
|---|---|---|
| pa_detect_jank | Top-5 严重 + 统计 | "总计X条jank。Top-5: [{frame, duration, severity}...]。平均耗时Xms，最大Xms" |
| pa_analyze_dimension | issues + top 指标 | "维度: X。关键问题: [...]。Top指标: [...]" |
| pa_trace_overview | 全量保留 | 原样返回（数据量本身很小） |
| pa_list_dimensions | 全量保留 | 原样返回（固定列表） |
| 其他 | 通用截断 | 按 token_budget 截断，保留前 N 个字段 |

## StepResult (已有，需扩展)

当前暂不需要 StepResult 数据模型——LLM 自主决策模式下没有显式的"步骤"概念。ToolReturn 的 metadata 已经记录了每次工具调用的原始数据。

如果后续需要追踪分析过程，可通过 Agent 的 `run_stream_events` 或 `iter` API 获取工具调用历史。

## 状态转换

分析流程的状态转换不变（已在 orchestrator.py 中实现）。新增的降级路径：

```
ANALYZING → [LLM context overflow]
  ├── 有已有工具返回 → REPORTING (用已有数据生成报告)
  └── 无工具返回 → FALLBACK → REPORTING (engine 分析后生成报告)

REPORTING → COMPLETED (报告标注分析完成度)
```
