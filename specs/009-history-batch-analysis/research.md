# Research: Pydantic AI 多 Agent 编排集成研究

**Feature**: 009-history-batch-analysis  
**Date**: 2026-04-03

## 目录

- [R1 — Pydantic AI 多 Agent 编排模式](#r1--pydantic-ai-多-agent-编排模式)
- [R2 — Pydantic AI + LiteLLM 集成](#r2--pydantic-ai--litellm-集成)
- [R3 — pa_* 工具注册方案](#r3--pa-工具注册方案)
- [R4 — PyQt6 异步集成](#r4--pyqt6-异步集成)
- [R5 — HTML 报告生成](#r5--html-报告生成)

## R1 — Pydantic AI 多 Agent 编排模式

### Decision

采用 Pydantic AI 的 **Agent Delegation（Level 2）+ Programmatic Hand-off（Level 3）** 组合模式。

### Rationale

Pydantic AI 支持 5 个级别的多 Agent 复杂度：

| 级别 | 模式 | 适用场景 |
|---|---|---|
| 1 | Single agent | 简单任务 |
| **2** | **Agent delegation** | **Agent 通过工具调用另一个 Agent** |
| **3** | **Programmatic hand-off** | **应用代码编排多个 Agent 的调用顺序** |
| 4 | Graph-based | 复杂状态机 |
| 5 | Deep Agents | 自治规划 |

我们的 3-Agent 模式适合 Level 2 + Level 3 的组合：
- **Level 3**：应用代码（`AnalysisOrchestrator`）编排 Main → Sub × N → Review 流程
- **Level 2**：MainAgent 通过工具委托 SubAgent 执行分析

### Alternatives Considered

- **Graph-based (Level 4)**：过于复杂，我们的流程是线性的（Main → Subs → Review），不需要循环或条件分支
- **subagents-pydantic-ai 第三方包**：提供便利的子代理配置，但引入额外依赖；原生 delegation 已够用
- **CrewAI/LangGraph**：依赖链过重，不适合桌面应用（详见 spec Clarifications）

### 编排架构

```
AnalysisOrchestrator (Python class, 非 Agent)
├── MainAgent (Pydantic AI Agent)
│   ├── 意图分析 → 场景路由
│   └── 结果汇总 → 报告生成
├── SubAgent × N (per-trace, 独立实例)
│   ├── 加载场景对应 SOP 作为 system prompt
│   └── 使用 pa_* toolset 执行分析
└── ReviewAgent (Pydantic AI Agent)
    └── 交叉评审 + 一致性检查
```

## R2 — Pydantic AI + LiteLLM 集成

### Decision

通过 `pydantic-ai-litellm` 包（v0.2.3）桥接 Pydantic AI 与我们现有的 LiteLLM 配置。

### Rationale

- `pydantic-ai-litellm` 提供 `LiteLLMModel` 类，直接接收 model_name 和 api_key
- 支持工具调用、流式输出、结构化输出
- 与我们的 `LLMManager` 兼容：从 `LLMManager.get_config()` 获取 model/key 参数

### 集成方式

```python
from pydantic_ai import Agent
from pydantic_ai_litellm import LiteLLMModel

config = llm_manager.get_config()
model = LiteLLMModel(
    model_name=config.model_name,  # e.g., "zai/glm-4-plus"
    api_key=config.get_api_key(),
)
agent = Agent(model=model, tools=[...])
```

### 关键注意事项

- token 消耗通过 `ctx.usage` 传递给 `LLMManager.record_tokens()`
- 流式输出通过 `agent.run_stream()` 实现
- 工具调用遵循 Pydantic AI 的自动 JSON Schema 生成

## R3 — pa_* 工具注册方案

### Decision

使用 Pydantic AI 的 `@agent.tool` 装饰器将现有 pa_* 函数注册为 Agent 工具。

### Rationale

Pydantic AI 工具注册支持两种方式：
1. `@agent.tool` 装饰器（推荐，类型安全）
2. `tools=[func]` 参数（简洁，适合动态注册）

我们的 pa_* 工具已定义在 `PerfettoAnalysisPlugin` 中，可通过 `context["pa_service"]` 获取服务实例。

### 注册策略

```python
def build_analysis_tools(pa_service) -> list[Callable]:
    """将 pa_service 的方法包装为 Pydantic AI 工具函数。"""

    def pa_trace_overview(trace_path: str, process_name: str = "") -> dict:
        """获取 trace 元数据概览（时长、帧数、进程、刷新率）"""
        return pa_service.get_trace_overview(trace_path, process_name)

    def pa_detect_jank(trace_path: str, process_name: str = "") -> dict:
        """检测卡顿帧"""
        return pa_service.detect_jank_frames(trace_path, process_name)

    # ... 其余 12 个工具类似包装

    return [pa_trace_overview, pa_detect_jank, ...]
```

### Alternatives Considered

- 直接传递 service 方法：签名不够清晰，缺少 docstring 供 LLM 理解
- BaseTool 子类：过于复杂，函数式足够

## R4 — PyQt6 异步集成

### Decision

使用 `QThread` + `asyncio.run()` 在工作线程中运行 Pydantic AI 的 async 调用，通过 `pyqtSignal` 回传结果到 GUI。

### Rationale

Pydantic AI 的核心 API 是 async 的（`agent.run()`、`agent.run_stream()`）。PyQt6 的主线程运行 Qt 事件循环，不能直接运行 asyncio。

### 集成模式

```
GUI 主线程 (Qt Event Loop)
    ↓ 发起分析请求
Worker 线程 (QThread)
    ↓ asyncio.run(orchestrator.analyze(...))
    ↓ 通过 callback/queue 发送流式数据
    ↓ pyqtSignal 回传到主线程
GUI 主线程
    ↓ 更新对话区域
```

流式输出的传递方案：
- Worker 线程中的 `run_stream()` 产生流式 chunk
- 每个 chunk 通过 `pyqtSignal(str)` 发送到主线程
- 主线程接收后更新对话区域的 QTextEdit/QTextBrowser

### Alternatives Considered

- `qasync`/`qt-asyncio`：更优雅但增加依赖，且兼容性不确定
- 直接 `run_sync()`：无法实现流式输出

## R5 — HTML 报告生成

### Decision

使用 Jinja2 模板引擎生成 HTML 报告，数据来自 Agent 分析结论的结构化输出。

### Rationale

- Jinja2 已被广泛使用，轻量且成熟
- 支持模板继承，方便维护报告样式
- Pydantic AI 支持结构化输出（`output_type=AnalysisReport`），可直接传入模板

### 报告结构

```
<trace_name>_analysis_<timestamp>/
├── report.html          # 可视化报告（含结论 + 数据引用）
└── raw_data/
    ├── trace_overview.json
    ├── jank_frames.json
    ├── dimension_*.json
    └── agent_conversation.json  # Agent 对话记录
```

### Alternatives Considered

- Markdown → HTML（Pandoc）：需要额外依赖，不如直接生成 HTML
- 现有 Markdown 报告：不够美观，且不便于引用原始数据
- PDF：生成复杂，不如 HTML 灵活
