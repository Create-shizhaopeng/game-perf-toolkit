# Research: LLM Prompt 预算管理

**Date**: 2026-04-05

## 目录

- [瓶颈验证](#瓶颈验证)
- [Pydantic AI ToolReturn API](#pydantic-ai-toolreturn-api)
- [ResultCompressor 现状](#resultcompressor-现状)
- [冗余工具分析](#冗余工具分析)

## 瓶颈验证

### Decision: 工具返回值累积是真正瓶颈，非初始 prompt

### Rationale

实际测量数据（Pydantic AI v1.77.0 + 11 个 pa_* 工具）：

| 组成部分 | 字符数 | 预估 token |
|---|---|---|
| 11 个工具 JSON schema | 4,974 | ~2,000 |
| SOP (jank-analysis.md 完整) | ~3,500 | ~3,000 |
| Agent instructions | ~50 | ~50 |
| 用户 prompt | ~300 | ~200 |
| **初始 prompt 总计** | **~8,824** | **~5,250** |

对于 GLM-4-Plus (128K 上下文)，~5K token 的初始 prompt 不是问题。但每次工具返回值 ~5K-20K token，连续 3-4 次调用后累积到 ~30K-60K token，超出模型限制。

### Alternatives Considered

1. ~~FunctionToolset 预置步骤序列~~ — 限制了 LLM 自主决策能力，与 Agent-Driven Design 原则冲突
2. ~~defer_loading 延迟加载~~ — 需要模型提供商支持 tool_search 协议，GLM-4-Plus 不支持
3. ~~SkillNavigator 自定义解析~~ — 过度工程化，不如直接压缩返回值

## Pydantic AI ToolReturn API

### Decision: 使用 Pydantic AI v1.77+ 原生 ToolReturn

### Rationale

v1.77.0 已验证可用的 API：

```python
from pydantic_ai.tools import ToolReturn

# return_value → 发送给 LLM（压缩后的摘要）
# metadata → 应用层使用（原始数据），不发送给 LLM
ToolReturn(
    return_value="统计: 200条, Top-5: [...]",
    metadata={"raw": original_data}
)
```

### Alternatives Considered

1. ~~自定义工具返回压缩管道~~ — 需要修改 Pydantic AI 内部流程，维护成本高
2. ~~Agent history_processors~~ — 仅压缩历史，不控制单次返回值大小

## ResultCompressor 现状

### Decision: 扩展现有 ResultCompressor，增加 token 预算控制

### Rationale

`modules/perfetto_analysis/src/result_compressor.py` 已实现 Top-N 压缩逻辑。需扩展：
- 新增 `compress_tool_output(tool_name, raw_output, token_budget)` 方法
- 按工具类型应用不同策略（jank → Top-5 + 统计，dimension → issues + top 指标）
- 硬限制：结果不超过 token_budget（默认 300）

### Alternatives Considered

1. ~~新建独立压缩器~~ — 重复已有代码，违反 DRY
2. ~~LLM 自行摘要~~ — 消耗额外 token，且大数据返回本身就会超限

## 冗余工具分析

### Decision: 移除 pa_analyze_full 和 pa_cpu_overview

### Rationale

| 工具 | 等价调用 | 移除理由 |
|---|---|---|
| pa_analyze_full | `pa_service.analyze()` 直接调用 | 功能与逐维度 pa_analyze_dimension 完全重叠，且返回值巨大 |
| pa_cpu_overview | `pa_analyze_dimension(trace, "cpu")` | 完全等价，仅是 dimension="cpu" 的别名 |

移除后工具数从 11 降至 9，减少 ~1000 token 的 schema 空间。

### Alternatives Considered

1. ~~保留但标记 deprecated~~ — 增加维护负担，LLM 可能仍然调用
2. ~~保留 pa_analyze_full 用于一键分析~~ — 返回值太大，与压缩策略冲突
