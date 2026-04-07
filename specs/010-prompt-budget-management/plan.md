# Implementation Plan: LLM Prompt 预算管理

**Branch**: `010-prompt-budget-management` | **Date**: 2026-04-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/010-prompt-budget-management/spec.md`
**Design Reference**: [design-discussion.md](design-discussion.md)

## 目录

- [Summary](#summary)
- [Technical Context](#technical-context)
- [Constitution Check](#constitution-check)
- [Project Structure](#project-structure)
- [Implementation Phases](#implementation-phases)
  - [Phase 1 — 工具返回值压缩](#phase-1--工具返回值压缩-p1)
  - [Phase 2 — 冗余工具清理与 SOP 完整加载](#phase-2--冗余工具清理与-sop-完整加载-p1)
  - [Phase 3 — 上下文超限接续与降级](#phase-3--上下文超限接续与降级-p2)
  - [Phase 4 — 测试与验证](#phase-4--测试与验证)
- [Complexity Tracking](#complexity-tracking)

## Summary

解决 Perfetto 分析 Agent 的 "Prompt exceeds max length" 错误。实际测量显示初始 prompt 仅 ~5K token（远低于模型上下文限制），真正瓶颈是工具返回值在对话历史中的累积（每次 ~5K-20K token）。通过 Pydantic AI 原生 `ToolReturn` 将工具返回值压缩为统计摘要 + Top-5 关键条目（~300 token/次），配合冗余工具清理和 SOP 完整加载，从根本上解决上下文超长问题。

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: Pydantic AI v1.77+ (ToolReturn, FunctionToolset), LiteLLM, pydantic-ai-litellm
**Storage**: SQLite (existing analysis history)
**Testing**: pytest (existing test infrastructure)
**Target Platform**: Windows desktop (PyInstaller), 源码运行
**Project Type**: Desktop application (PyQt6) with LLM Agent capabilities
**Performance Goals**: 每次工具返回值压缩后 <= 300 token；LLM 连续 5 次工具调用后累积上下文不超出模型限制
**Constraints**: 保持 LLM 自主决策能力，不预设分析步骤序列
**Scale/Scope**: perfetto_analysis 模块内改造，涉及 6 个源文件 + SOP 文档更新

## Constitution Check

*GATE: Must pass before implementation.*

| 原则 | 状态 | 说明 |
|---|---|---|
| I. Plugin-First | ✅ PASS | 变更局限于 `modules/perfetto_analysis/` 模块内 |
| II. Three-Surface Unity | ✅ PASS | 变更在 service/agent 层，不影响 GUI/CLI 接口 |
| III. Agent-Driven Design | ✅ PASS | 保持 LLM 自主决策，不限制工具调用顺序 |
| IV. Dependency Inversion | ✅ PASS | 不引入新的跨模块依赖 |
| V. Presentation Separation | ✅ PASS | 变更不涉及 GUI/CLI 代码 |
| VI. Open-Closed | ✅ PASS | 不修改核心框架代码 |
| VII. Spec-Driven | ✅ PASS | 遵循 speckit 工作流 |

**额外检查**：
- Pydantic 数据模型: ToolReturn 是 Pydantic AI 原生组件，无需自定义模型
- UTF-8 编码: 不涉及编码变更
- context 前缀: 不引入新 context 键

## Project Structure

### Documentation (this feature)

```text
specs/010-prompt-budget-management/
├── spec.md              # 功能规格 (v3)
├── plan.md              # 本文件
├── design-discussion.md # 设计讨论记录
├── checklists/
│   └── requirements.md  # 质量检查清单
├── research.md          # Phase 0 研究
├── data-model.md        # 数据模型
└── tasks.md             # 任务分解 (speckit.tasks)
```

### Source Code (affected files)

```text
modules/perfetto_analysis/
├── src/
│   ├── agent/
│   │   ├── tools.py           ← 核心改造: 工具返回 ToolReturn
│   │   ├── orchestrator.py    ← 改造: 超限处理、降级逻辑
│   │   ├── agents.py          ← 改造: SubAgent 移除冗余工具
│   │   └── prompts.py         ← 改造: SOP 完整加载、移除截断
│   └── result_compressor.py   ← 扩展: token 预算控制
├── skills/
│   └── perfetto-analysis/
│       └── sop/
│           └── jank-analysis.md  ← 更新: 移除冗余工具引用
└── tests/
    └── test_tool_return.py    ← 新增: ToolReturn 压缩测试
```

**Structure Decision**: 在现有模块结构内改造，不引入新目录或新模块。

## Implementation Phases

### Phase 1 — 工具返回值压缩 (P1)

**目标**: 所有 pa_* 工具返回 `ToolReturn`，压缩后的摘要给 LLM，原始数据通过 metadata 保留。

**变更文件**:
- `modules/perfetto_analysis/src/agent/tools.py` — 核心改造
- `modules/perfetto_analysis/src/result_compressor.py` — 扩展 token 预算

**技术方案**:

1. **扩展 ResultCompressor**:
   - 新增 `compress_tool_output(tool_name: str, raw_output: dict, token_budget: int = 300) -> str` 方法
   - 按工具类型应用不同压缩策略:
     - `pa_detect_jank`: Top-5 严重 jank + 统计摘要（总数、平均耗时、最大耗时）
     - `pa_analyze_dimension`: 保留 issues + top 指标，去除原始数据
     - `pa_trace_overview`: 保留关键元数据（时长、帧数、进程列表、刷新率），数据量本身较小
     - 其他工具: 通用截断策略（按 token 预算截断）
   - 错误结果不压缩，原样返回

2. **改造 tools.py 中的工具函数**:
   - 每个 pa_* 函数返回 `ToolReturn` 而非 `dict`
   - `return_value` = `ResultCompressor.compress_tool_output()` 的结果
   - `metadata` = `{"raw": 原始数据, "tool_name": 工具名}`

**代码示例**:

```python
from pydantic_ai.tools import ToolReturn

def pa_detect_jank(trace_path: str, process_name: str = "") -> ToolReturn:
    """检测卡顿帧(Jank/BigJank),返回丢帧列表和统计"""
    _notify_tool_call("pa_detect_jank", {"trace_path": trace_path})
    try:
        raw = pa_service.parse_only(trace_path, process_name)
        raw = raw if isinstance(raw, dict) else {"data": str(raw)}
        compressed = compressor.compress_tool_output("pa_detect_jank", raw, 300)
        _notify_tool_result("pa_detect_jank", raw)
        return ToolReturn(return_value=compressed, metadata={"raw": raw})
    except Exception as e:
        return ToolReturn(return_value=f"错误: {e}", metadata={"error": str(e)})
```

### Phase 2 — 冗余工具清理与 SOP 完整加载 (P1)

**目标**: 移除冗余工具，SOP 通过 SKILL 路由完整加载。

**变更文件**:
- `modules/perfetto_analysis/src/agent/tools.py` — 移除冗余工具
- `modules/perfetto_analysis/src/agent/prompts.py` — 移除截断和默认 SOP
- `modules/perfetto_analysis/skills/perfetto-analysis/sop/jank-analysis.md` — 更新工具引用

**技术方案**:

1. **移除冗余工具**:
   - 移除 `pa_analyze_full` — 功能完全由 `pa_analyze_dimension` 覆盖
   - 移除 `pa_cpu_overview` — 等价于 `pa_analyze_dimension(trace_path, "cpu")`
   - 从 `build_analysis_tools()` 返回列表中删除

2. **SOP 完整加载**:
   - `prompts.py` 中移除 `_DEFAULT_SOP` 和 3000 字符截断逻辑
   - `load_sop()` 返回完整 SOP 文件内容
   - SOP 不存在时返回空字符串（不使用默认兜底），由 LLM 自主分析

3. **更新 SOP 文件**:
   - `jank-analysis.md` 中 `pa_cpu_overview` 引用替换为 `pa_analyze_dimension(cpu)`
   - 检查其他 SOP 文件中是否引用了被移除的工具

### Phase 3 — 上下文超限接续与降级 (P2)

**目标**: LLM 调用失败时不终止分析，渐进降级。

**变更文件**:
- `modules/perfetto_analysis/src/agent/orchestrator.py` — 超限处理

**技术方案**:

1. **异常分类**:
   - 识别上下文超限异常: `litellm.BadRequestError` + "max length" / "context" 关键字
   - 与超时异常 (`asyncio.TimeoutError`) 区分处理

2. **渐进降级流程**:
   ```
   LLM 调用失败 (context overflow)
   ├── 1. 通过 on_stream 通知用户
   ├── 2. 如果已有工具返回数据 → 用已有数据生成报告
   ├── 3. 如果无工具返回数据 → fallback engine 分析
   └── 4. 报告标注降级原因和未完成维度
   ```

3. **报告标注**:
   - 报告 HTML 中增加"分析完成度"标注
   - 标注分析由 LLM 完成 / 部分完成 / engine 降级完成

### Phase 4 — 测试与验证

**变更文件**:
- `modules/perfetto_analysis/tests/test_tool_return.py` — 新增
- `modules/perfetto_analysis/tests/test_result_compressor.py` — 扩展

**测试用例**:

1. **ToolReturn 压缩测试**:
   - 200 条 jank 记录 → 压缩后仅 Top-5 + 统计
   - 字典数据 → 保留 issues + top 指标
   - 错误数据 → 原样保留
   - 空数据 → 返回 "工具未返回数据"

2. **ResultCompressor token 预算测试**:
   - 验证压缩结果不超过 300 token 预算
   - 验证不同工具类型应用不同压缩策略

3. **超限降级测试**:
   - 模拟 `litellm.BadRequestError` → 验证降级到 engine
   - 验证部分结果可用时的报告生成
   - 验证流式输出通知用户

4. **集成测试**:
   - 端到端 jank 分析 → 验证无 "Prompt exceeds max length" 错误
   - 验证冗余工具已移除（工具列表不包含 pa_analyze_full/pa_cpu_overview）

## Complexity Tracking

无 Constitution 违规，无需记录复杂度偏差。

| 维度 | 评估 |
|---|---|
| 新增文件 | 1 个测试文件 |
| 修改文件 | 5-6 个 |
| 新增依赖 | 0（使用 Pydantic AI 已有 API） |
| 风险 | 低 — ToolReturn 是 Pydantic AI 原生 API，已验证可用 |
| 预计工作量 | 中等 — 主要是 tools.py 逐个工具改造 + ResultCompressor 扩展 |
