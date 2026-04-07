# LLM Prompt 预算管理 — 设计讨论记录

**日期**: 2026-04-05
**参与者**: 用户 + AI 助手
**状态**: 已完成 clarify (v3)

## 目录

- [问题背景](#问题背景)
- [根因分析](#根因分析)
- [已有基础设施](#已有基础设施)
- [Pydantic AI v1.x 原生能力调研](#pydantic-ai-v1x-原生能力调研)
  - [FunctionToolset — 场景化工具集](#functiontoolset--场景化工具集)
  - [ToolReturn — 返回值分离](#toolreturn--返回值分离)
  - [Agent.iter — 逐步执行](#agentiter--逐步执行)
  - [FunctionToolset.instructions — 工具集指令](#functiontoolsetinstructions--工具集指令)
  - [三层压缩策略 — 业界最佳实践](#三层压缩策略--业界最佳实践)
  - [对原方案的影响](#对原方案的影响)
- [目标架构](#目标架构)
  - [上下文控制策略](#上下文控制策略)
  - [架构全景图](#架构全景图)
  - [Phase 2 步骤化分析流程](#phase-2-步骤化分析流程)
  - [上下文超限接续策略](#上下文超限接续策略)
- [待完善项](#待完善项)
- [关键设计决策](#关键设计决策)
- [Clarify 核心发现](#clarify-核心发现-v3)

## 问题背景

使用 GLM-4-Plus (128K 上下文) 进行 Perfetto trace 分析时，出现 `litellm.BadRequestError: ZaiException - Prompt exceeds max length` 错误。

已尝试的优化（均未彻底解决）：
1. SOP 内容截断到 3000 字符
2. 工具 docstring 精简为单行
3. Agent 指令大幅压缩

## 根因分析

当前 SubAgent 的 prompt 由以下部分组成：

| 组成部分 | 预估 token 数 | 来源 |
|---|---|---|
| Agent instructions | ~50 | `agents.py` SubAgent 指令 |
| SOP 内容 | ~1000 | `prompts.py` 截断到 3000 字符 |
| 11 个工具 schema | ~3000-5000 | Pydantic AI 自动从函数签名+docstring 生成 |
| 用户 prompt | ~200 | orchestrator 构建 |
| 工具返回值累积 | **不可预估** | 工具返回的原始数据直接回传给 LLM |

**核心问题**：
1. 全部 11 个工具的 schema 一次性注入 system prompt，大量工具对当前场景无用
2. SOP 全文嵌入 system prompt，而非按需加载
3. 工具返回的原始数据（可能很大）直接回传给 LLM，没有经过压缩
4. Agent 编排层（`src/agent/`）与已有基础设施（`result_compressor.py`、`analysis_mode.py`）未打通

## 已有基础设施

| 组件 | 文件 | 状态 | 说明 |
|---|---|---|---|
| **McpAnalysisClient** | `src/mcp_client.py` | 占位实现 | 所有 MCP 调用返回 None，设计为注入真实调用 |
| **ResultCompressor** | `src/result_compressor.py` | **已实现** | 将分析结果压缩为 CompressedSummary |
| **FeatureFlagManager** | `src/analysis_mode.py` | **已实现** | 维度级 MCP/Engine 路由控制 |
| **AnalysisMode** | `src/models.py` | **已实现** | mcp_preferred / engine_only / mcp_only 枚举 |
| **SKILL.md** | `skills/perfetto-analysis/SKILL.md` | **已有** | Perfetto 分析的完整 Skill 定义（Cursor 使用） |
| **SOP 文件** | `skills/perfetto-analysis/sop/*.md` | **已有** | 各场景的标准操作流程 |

**关键发现**：`ResultCompressor` 和 `FeatureFlagManager` 已存在但未被 Agent 编排层使用。

## Pydantic AI v1.x 原生能力调研

**调研日期**: 2026-04-05
**验证版本**: pydantic-ai v1.77.0

当前安装的 Pydantic AI v1.77.0 原生提供了解决上下文超长问题所需的全部核心能力，无需从零构建 SkillNavigator 等自定义组件。

### FunctionToolset — 场景化工具集

`FunctionToolset` 支持按场景动态组合工具，并在 `agent.run()` 时传入不同的 toolset：

```python
from pydantic_ai import Agent, FunctionToolset

jank_toolset = FunctionToolset(
    tools=[pa_trace_overview, pa_detect_jank, pa_analyze_dimension],
    instructions="分析 trace 中的卡顿帧，给出丢帧统计和原因"
)
anr_toolset = FunctionToolset(
    tools=[pa_trace_overview, pa_analyze_anr, pa_analyze_dimension],
    instructions="分析 ANR 事件，定位主线程阻塞原因"
)

# 按场景传入不同 toolset，只有相关工具进入 prompt
result = await agent.run(prompt, toolsets=[jank_toolset])
```

**关键能力**：
- `tools` 参数接受工具列表，按需组合
- `instructions` 参数为每个 toolset 附加专属指令（替代全局 SOP 嵌入）
- `filtered()` 方法可进一步过滤 toolset 中的工具
- `defer_loading=True` 可隐藏工具直到通过搜索发现

### ToolReturn — 返回值分离

`ToolReturn` 将工具的"返回给 LLM 的内容"和"应用层使用的数据"分离：

```python
from pydantic_ai.tools import ToolReturn

def pa_detect_jank(ctx, trace_path: str) -> ToolReturn:
    raw = pa_service.detect_jank(trace_path)    # 原始大数据
    compressed = compressor.compress(raw)         # 本地压缩
    return ToolReturn(
        return_value=compressed,                  # 压缩后的摘要 → 发给 LLM
        metadata={"raw": raw, "token_saved": len(str(raw)) - len(str(compressed))}
    )
```

**关键能力**：
- `return_value`: 发送给 LLM 的内容（可控大小）
- `content`: 额外内容（与 return_value 分开发送）
- `metadata`: 应用层数据，**不发送给 LLM**

**效果**：工具返回值压缩从"架构方案"变为"一行代码改动"。

### Agent.iter — 逐步执行

Agent 提供 `iter()` 方法实现逐步执行，可在每步之间插入监控和干预逻辑：

```python
async with agent.iter(prompt, toolsets=[step_toolset]) as run:
    async for node in run:
        if agent.is_call_tools_node(node):
            # 监控工具调用，可在此注入压缩/中断逻辑
            pass
        elif agent.is_end_node(node):
            result = node.data
```

**用途**：替代自定义 StepOrchestrator，用原生 API 实现步骤级监控。

### FunctionToolset.instructions — 工具集指令

每个 `FunctionToolset` 可携带自己的 `instructions`，在该 toolset 被使用时自动注入 system prompt：

```python
overview_toolset = FunctionToolset(
    tools=[pa_trace_overview],
    instructions="第一步：获取 trace 概览。关注时长、帧数、关键进程。"
)
jank_toolset = FunctionToolset(
    tools=[pa_detect_jank],
    instructions="第二步：检测丢帧。关注连续丢帧区间和严重帧。"
)
```

**效果**：SOP 分步指令不再需要嵌入全局 prompt，而是随工具集按需注入。彻底替代 SkillNavigator 的 SOP 拆解功能。

### 三层压缩策略 — 业界最佳实践

参考 BSWEN 2026-03 文章，结合 Pydantic AI 能力：

| 层级 | 触发条件 | 动作 | 实现方式 |
|---|---|---|---|
| **micro_compact** | 每轮执行后 | 3 轮前的工具结果替换为占位符 | Agent history_processors |
| **auto_compact** | token > 50K | LLM 摘要整个对话 | Agent.iter 中间拦截 |
| **local_compress** | 每次工具返回 | ResultCompressor 压缩 | ToolReturn |

### 对原方案的影响

原计划需要自定义 SkillNavigator、StepOrchestrator 等组件。发现 Pydantic AI 原生能力后，大幅简化：

| 原计划组件 | 替代方案 | 代码量影响 |
|---|---|---|
| SkillNavigator（解析 SKILL.md） | FunctionToolset.instructions（每步指令随工具集注入） | **删除**整个组件 |
| StepInstruction 数据模型 | FunctionToolset 自带 instructions | **删除** |
| SCENE_TOOLS_MAP（场景工具映射） | 预构建 FunctionToolset 实例 | **简化**为字典 |
| 自定义工具返回压缩管道 | ToolReturn + ResultCompressor | **一行代码**改动 |
| StepOrchestrator（步骤编排） | Agent.iter（原生逐步执行） | **删除**整个组件 |
| SKILL.md 解析/打包逻辑 | 不再需要 | **删除** |

**结论**：从"构建自定义框架"变为"配置 Pydantic AI 原生功能"，开发量减少约 60-70%。

## 目标架构

### 上下文控制策略 (v3 — Clarify 后修正)

**关键发现**：实际测量显示初始 prompt 仅 ~5K token（11 工具 schema ~2K + SOP ~3K），远低于 128K 上限。真正的瓶颈是工具返回值在对话历史中的累积。

采用三层策略组合：

```
策略 1: ToolReturn + ResultCompressor (核心 — 工具返回值压缩)
  工具返回 ToolReturn → return_value 为统计+Top-5摘要 (~300 token)
  metadata 保留原始数据给应用层
  控制: 防止大数据回传撑爆上下文 (每次工具调用从 ~5K-20K 降至 ~300 token)

策略 2: 冗余工具清理 (辅助)
  移除 pa_analyze_full, pa_cpu_overview (功能与 pa_analyze_dimension 重叠)
  工具数 11 → 8-9，工具 schema 减少 ~1000 token
  控制: 减小初始 prompt 中的工具 schema 占用

策略 3: SOP 完整加载 (质量提升)
  取消 3000 字符截断，通过 SKILL 路由完整加载场景 SOP
  不使用默认 SOP 兜底
  效果: LLM 获得完整分析方法论，提升分析质量
  （初始 prompt 增加 ~500 token，但总量仍远低于限制）
```

**设计原则**：LLM 自主决定分析路径和工具调用顺序，系统不预设步骤序列。

### 架构全景图（v3 — LLM 自主决策 + 工具返回值压缩）

```
┌─────────────────────────────────────────────────────────────────┐
│                       用户 GUI 层                               │
│  AnalysisChatWidget → AnalysisWorker(QThread) → asyncio.run()  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                 AnalysisOrchestrator (编排器)                    │
│                                                                 │
│  Phase 1: 场景路由 (不变)                                       │
│  ┌────────────────────────────────────────────────────┐        │
│  │ MainAgent (无工具, ~200 token prompt)               │        │
│  │ → 输出 AnalysisRouting (scene, process_name)       │        │
│  └────────────────────────────────────────────────────┘        │
│                            │                                    │
│                            ▼                                    │
│  Phase 2: LLM 自主分析 (核心变更)                               │
│  ┌────────────────────────────────────────────────────┐        │
│  │ SubAgent                                            │        │
│  │ ├── instructions: 完整 SOP (通过 SKILL 路由加载)   │        │
│  │ ├── tools: 8-9 个工具 (移除冗余)                   │        │
│  │ └── LLM 自主决定: 调用顺序 / 分析路径 / 维度选择   │        │
│  │                                                     │        │
│  │ 工具返回值压缩 (ToolReturn):                        │        │
│  │ ┌──────────────────────────────────────────────┐   │        │
│  │ │ pa_detect_jank() 返回 200 条 jank             │   │        │
│  │ │ → ResultCompressor.compress()                 │   │        │
│  │ │ → ToolReturn(                                 │   │        │
│  │ │     return_value="总计200条, Top-5: [...]",   │   │        │
│  │ │     metadata={"raw": 原始200条}               │   │        │
│  │ │   )                                           │   │        │
│  │ │ LLM 只看到 ~300 token (而非 ~15K token)       │   │        │
│  │ └──────────────────────────────────────────────┘   │        │
│  │                                                     │        │
│  │ 超限处理:                                           │        │
│  │ ├── 捕获 context overflow → 用已有结果继续          │        │
│  │ ├── LLM 完全不可用 → fallback engine                │        │
│  │ └── 流式通知用户降级状态                             │        │
│  └────────────────────────────────────────────────────┘        │
│                            │                                    │
│                            ▼                                    │
│  Phase 3: 报告生成                                              │
│  ┌────────────────────────────────────────────────────┐        │
│  │ LLM 结论 + 工具 metadata 原始数据 → HTML 报告       │        │
│  └────────────────────────────────────────────────────┘        │
│                                                                 │
│  Phase 4: 后处理                                                │
│  ┌────────────────────────────────────────────────────┐        │
│  │ PackageDB 学习 / LLMManager token 记录 / 历史存储   │        │
│  └────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘

资源层:
┌─────────────────────────────────────────────────────────────────┐
│ src/agent/tools.py         ← 改造! 工具返回 ToolReturn          │
│ src/result_compressor.py   ← 已有! 扩展 token 预算控制          │
│ src/agent/prompts.py       ← 改造! SOP 完整加载, 移除截断       │
│ skills/perfetto-analysis/sop/*.md  ← SOP 文件 (SKILL 路由加载) │
│ src/analysis_mode.py       ← 已有! 路由逻辑复用                │
│ src/mcp_client.py          ← 占位，后续打通                     │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 2 步骤化分析流程

```
Step 1: 获取概览
  指令: "获取 trace 概览信息"
  工具: pa_trace_overview
  输出: trace 时长、帧数、进程列表、刷新率

Step 2: 丢帧检测
  指令: "检测卡顿帧"
  工具: pa_detect_jank
  输入: Step 1 压缩结果
  输出: jank 列表、统计摘要

Step 3: 维度分析 (按场景选择维度)
  指令: "分析 {dimension} 维度"
  工具: pa_analyze_dimension
  输入: Step 1+2 压缩结果
  输出: 维度分析摘要

Step N: 综合结论
  指令: "综合以上分析结果输出结论"
  工具: (无, 纯推理)
  输入: 所有步骤压缩结果
  输出: 结论文本
```

### 上下文超限接续策略

即使采用步骤化执行，以下场景仍可能出现上下文超限：
1. 工具返回的压缩结果仍然较大
2. 多步累积的上下文超过模型限制
3. LLM 提供商对单次请求有额外限制

**接续策略**：

```
┌───────────────────────────────────────────────────────┐
│              上下文超限检测与恢复流程                    │
│                                                       │
│  Step N 发送请求前:                                   │
│  ├── estimate_tokens(prompt) 估算                     │
│  ├── 超过模型 80% → 触发压缩                          │
│  │   ├── 1. 进一步截断上步结果                        │
│  │   ├── 2. 合并多步结果为单一摘要                    │
│  │   └── 3. 仍超限 → 标记当前步 SKIP                 │
│  │                                                    │
│  Step N 请求失败 (API 返回 context overflow):          │
│  ├── 捕获异常                                         │
│  ├── 不中断: 使用当前已有步骤结果继续                   │
│  ├── 标记: 记录哪些步骤被跳过                          │
│  ├── 接续: 用更少的上下文重试当前步                    │
│  └── 最终降级: 所有步骤失败 → fallback engine 分析     │
│                                                       │
│  报告生成时:                                           │
│  ├── 综合已完成步骤的结果                              │
│  ├── 标注: "以下维度因上下文限制未完成: [...]"          │
│  └── 确保: 即使部分失败也能生成有价值的报告             │
└───────────────────────────────────────────────────────┘
```

**核心原则**：
- **永不中断**: 任何步骤失败不终止整个分析，跳过并继续
- **渐进降级**: 超限 → 压缩 → 跳过 → fallback engine
- **透明通知**: 每次降级/跳过都通过 on_stream 通知用户
- **结果完整性**: 报告中标注哪些维度完成、哪些被跳过

## 待完善项

1. **McpClient 打通**: 当前占位实现。需决定应用内 MCP 调用方案（后续独立迭代）
2. ~~**SKILL.md 解析规范**~~: ✅ 不再需要
3. ~~**步骤间错误传播**~~: ✅ LLM 自主决策，系统只在 LLM 失败时降级
4. **ResultCompressor token 预算**: 当前按 Top-N 压缩，需增加 ~300 token/次的预算控制
5. ~~**Phase 3 上下文控制**~~: ✅ 工具返回值已压缩，Phase 3 无累加问题
6. ~~**SKILL.md 格式适配**~~: ✅ 不再需要
7. **tools.py 改造**: 现有工具需改造为返回 `ToolReturn`
8. ~~**toolsets.py 场景配置**~~: ✅ 不再预构建场景 toolset
9. **SOP 文件更新**: 移除冗余工具后，所有 SOP 中对 pa_cpu_overview 的引用需替换为 pa_analyze_dimension(cpu)

## 关键设计决策

| # | 决策 | 选择 | 理由 |
|---|---|---|---|
| D1 | SOP 加载方式 | **SKILL 路由 + 完整加载** | 通过 SKILL 路由到场景 SOP，完整加载不截断 |
| D2 | 工具使用策略 | **LLM 自主决策** | 不预设步骤序列，LLM 根据 SOP 自主决定分析路径 |
| D3 | 工具结果处理 | **ToolReturn + ResultCompressor** | 工具返回 ToolReturn，return_value 为统计+Top-5，metadata 保留原始数据 |
| D4 | 上下文超限处理 | 永不中断 + 渐进降级 | 保证分析流程的鲁棒性和用户体验 |
| D5 | MCP 打通 | 后续迭代 | 当前 MCP 占位实现，先聚焦上下文控制 |
| D6 | 向后兼容 | **直接替换** | 旧无压缩模式直接替换为 ToolReturn 压缩，fallback engine 已有兜底 |
| D7 | 压缩粒度 | **统计 + Top-5 (~300 token/次)** | 兼顾 LLM 分析质量和 token 控制 |
| D8 | 默认 SOP | **不需要** | 全部通过 SKILL 路由，未匹配时 LLM 自主分析 |

## Clarify 核心发现 (v3)

**实际测量数据**（2026-04-05）：

| 组成部分 | 字符数 | 预估 token |
|---|---|---|
| 11 个工具 JSON schema | 4,974 | ~2,000 |
| SOP (jank, 完整) | ~3,500 | ~3,000 |
| Instructions | ~50 | ~50 |
| 用户 prompt | ~300 | ~200 |
| **初始 prompt 总计** | **~8,824** | **~5,250** |
| 每次工具返回 (压缩前) | 5K-20K | 5K-20K |
| 每次工具返回 (压缩后) | ~600 | ~300 |

**结论**：初始 prompt ~5K token 不是瓶颈。工具返回值累积是真正问题。每次压缩从 ~10K 降至 ~300 token，5 次工具调用累积从 ~50K 降至 ~1.5K token。
