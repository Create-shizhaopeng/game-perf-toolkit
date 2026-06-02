<!--
  id: DES-002
  title: Hermes Agent 深度引入 — lv-game-toolkit Agent 框架升级设计
  type: design
  status: draft
  created: 2026-06-02
  updated: 2026-06-02
  tags: [agent, architecture, hermes, upgrade, conversation-loop, guardrails, knowledge-base]
  depends_on: [DES-001]
-->

# Hermes Agent 深度引入 — lv-game-toolkit Agent 框架升级设计

> **目标**：在 R6 Agent 核心重构（DES-001）已完成的基础上，深度引入 Hermes Agent 的核心能力模式，将 lv-game-toolkit 的 Agent 从"聊天助手"升级为"自主性能分析引擎"。

## 目录

- [1. 背景与现状分析](#1-背景与现状分析)
  - [1.1 当前架构（DES-001 完成态）](#11-当前架构des-001-完成态)
  - [1.2 Hermes Agent 全景能力矩阵](#12-hermes-agent-全景能力矩阵)
  - [1.3 差距分析总览](#13-差距分析总览)
- [2. 设计目标与原则](#2-设计目标与原则)
- [3. 框架升级方案](#3-框架升级方案)
  - [3.1 对话循环升级：从朴素递归到鲁棒编排](#31-对话循环升级从朴素递归到鲁棒编排)
  - [3.2 工具执行安全层：Guardrails + Circuit Breaker](#32-工具执行安全层guardrails--circuit-breaker)
  - [3.3 上下文管理升级：智能压缩 + Memory 跨会话](#33-上下文管理升级智能压缩--memory-跨会话)
  - [3.4 分析质量保障：Verification + Reflection + Checkpoint](#34-分析质量保障verification--reflection--checkpoint)
  - [3.5 知识库体系：从空壳到可检索](#35-知识库体系从空壳到可检索)
  - [3.6 多 Agent 协作：SubAgent + ACP 启步](#36-多-agent-协作subagent--acp-启步)
  - [3.7 错误韧性：Error Classifier + Failover](#37-错误韧性error-classifier--failover)
- [4. 目标架构总览](#4-目标架构总览)
- [5. 分阶段实施路线](#5-分阶段实施路线)
- [6. 关键决策与待决事项](#6-关键决策与待决事项)
- [7. 风险与缓解](#7-风险与缓解)

---

## 1. 背景与现状分析

### 1.1 当前架构（DES-001 完成态）

lv-game-toolkit 在 R6 Agent 核心重构后，已建立了三层架构：

```
toolkit/core/          ← 基础设施层（ToolRegistry / SkillRegistry / MCP Framework）
toolkit/agent/         ← 编排引擎层（AgentOrchestrator / AgentService / SystemPrompt）
modules/<name>/        ← 能力提供层（各模块通过 Skill + MCP 暴露能力）
```

**已引入的 Hermes 模式**：

| 模式 | 实现文件 | 成熟度 |
|------|---------|--------|
| Registry Pattern（单例 + 线程安全） | [toolkit/core/tool_registry.py](../../toolkit/core/tool_registry.py) | ⭐⭐⭐⭐ 完整 |
| Progressive Disclosure（三级加载） | [toolkit/core/skill_registry.py](../../toolkit/core/skill_registry.py) | ⭐⭐⭐⭐ 完整 |
| 三段式 System Prompt | [toolkit/agent/system_prompt.py](../../toolkit/agent/system_prompt.py) | ⭐⭐⭐ 基础 |
| Iteration Budget | [toolkit/agent/iteration_budget.py](../../toolkit/agent/iteration_budget.py) | ⭐⭐⭐ 基础 |
| MCP 统一前缀 | [toolkit/core/mcp/tool_bridge.py](../../toolkit/core/mcp/tool_bridge.py) | ⭐⭐⭐ 基础 |

**核心对话循环现状**（[toolkit/agent/service.py](../../toolkit/agent/service.py) `_run_loop`）：

```
用户消息 → System Prompt 构建 → LLM 调用 → 工具执行 → 结果回注 → 递归循环
                                                          ↑______________|
```

这是一个**朴素递归循环**，缺少：
- 错误分类与差异化重试
- 工具失败熔断（连续失败无感知）
- 上下文溢出保护（仅简单截断）
- 分析质量事后验证
- 跨会话经验积累

### 1.2 Hermes Agent 全景能力矩阵

以下是 Hermes Agent（基于 `conversation_loop.py` 3900 行 + 工具系统 + 技能系统分析）的完整能力矩阵，按 lv-game-toolkit 的相关性分 P0-P3：

#### P0 — 对话循环鲁棒性（直接提升分析可靠性）

| 能力 | Hermes 来源 | 对 lv-game-toolkit 的价值 |
|------|------------|--------------------------|
| **错误分类器** (Error Classifier) | `error_classifier.py` | 区分瞬态错误（retryable）vs 永久错误（不可重试），减少无效重试 |
| **熔断器** (Circuit Breaker) | `conversation_loop.py` 中的 tool failure 监控 | 连续工具失败 > 阈值 → 切换策略 / 降级，防止无限循环 |
| **看门狗** (Watchdog) | `conversation_loop.py` 中的超时检测 | 单轮分析超时 → 注入 `[请尽快总结]` → 优雅降级 |
| **安全超时** (Safety Timeout) | `conversation_loop.py` Promise.race | 整体分析硬超时 → 强制终止 + 部分结果返回 |
| **差异化重试** (Retry Policy) | `anthropic_adapter.py` + `codex_responses_adapter.py` | 429（限流）退避重试、5xx 切换 Provider、4xx 直接失败 |

#### P1 — 分析质量保障（提升结果可信度）

| 能力 | Hermes 来源 | 对 lv-game-toolkit 的价值 |
|------|------------|--------------------------|
| **结论验证** (Verification) | 借鉴 SmartPerfetto `claudeVerifier.ts` + `claimVerification` | LLM 输出结论 → 用 Check Tool 核实数据 → 矛盾则修正 |
| **反思重试** (Reflection) | 借鉴 SmartPerfetto `generateCorrectionPrompt` | 验证失败 → 生成修正提示 → 二次分析（最多 2 次） |
| **置信度模型** (Confidence) | Hermes `conversation_loop.py` 中的 evidence tracking | 每条结论标注置信度：verified / knowledge_matched / partial / inference |
| **分析计划提交** (Plan Gate) | 借鉴 SmartPerfetto `submit_plan` | 复杂任务强制 AI 先提交计划 → 验证覆盖度 → 再执行 |

#### P2 — 上下文与知识管理（提升长期价值）

| 能力 | Hermes 来源 | 对 lv-game-toolkit 的价值 |
|------|------------|--------------------------|
| **上下文压缩** (Context Compressor) | `context_compressor.py` | 当上下文接近 token 限制时，智能压缩历史工具结果（保留关键数据 + 摘要） |
| **跨会话记忆** (Memory Manager) | `memory_manager.py` | 记忆用户偏好、常用分析模式、设备特征 → 减少重复配置 |
| **知识库检索** (Knowledge Search) | 借鉴 SmartPerfetto `lookup_knowledge` | BM25/TF-IDF 搜索案例库 + 已知根因模式 → 加速分析 |
| **模式记忆** (Pattern Memory) | 借鉴 SmartPerfetto `analysisPatternMemory` | 成功分析 → 保存模式；失败路径 → 避免重复 |

#### P3 — 高级编排（长期演进方向）

| 能力 | Hermes 来源 | 对 lv-game-toolkit 的价值 |
|------|------------|--------------------------|
| **SubAgent 执行** | `delegate` 工具 + ACP 协议 | 复杂任务拆分到子 Agent 并行分析 |
| **工具安全门禁** (Tool Guardrails) | `tool_guardrails.py` | 工具参数校验、文件系统沙箱、速率限制 |
| **凭证池** (Credential Pool) | `credential_pool.py` | 多 API Key 轮换 + 配额管理（当前 llm_manager 已覆盖） |
| **后台 Review** | `conversation_loop.py` background review | 分析完成后异步审查，标记改进点 |
| **Skill 包管理** | `skill_bundles.py` / `skill_commands.py` | 技能打包、版本管理、CLI 命令化 |

### 1.3 差距分析总览

```
lv-game-toolkit 当前能力                  Hermes 完整能力
═══════════════════════                  ════════════════

✅ ToolRegistry (单例/线程安全)         ✅ ToolRegistry
✅ ToolExecutor (async/sync)             ✅ ToolExecutor
✅ SkillRegistry (三级渐进加载)          ✅ Skill System (SKILL.md)
✅ MCP Framework (Server+Client)         ✅ MCP Server
✅ IterationBudget (基础)                ✅ IterationBudget (完整)
✅ 三段式 SystemPrompt (≤3000 chars)     ✅ 三段式 SystemPrompt
✅ SkillRouter (TF-IDF)                  ⬜ Skill Bundles
⚠️ _run_loop (朴素递归)                 ✅ conversation_loop (鲁棒循环)
⚠️ _smart_truncate (简单优先保留)        ✅ context_compressor (智能摘要)
⚠️ 失败 refund 预算 (不区分错误类型)     ✅ error_classifier + failover
⬜ 无                                    ✅ Circuit Breaker / Watchdog
⬜ 无                                    ✅ Verification + Reflection
⬜ 无                                    ✅ Confidence Model
⬜ 无                                    ✅ Submit Plan (计划门禁)
⬜ ConversationStore (仅存消息)          ✅ Memory Manager (跨会话)
⬜ ReportIndex (简单文件索引)            ✅ Knowledge Base (BM25 + 向量)
⬜ 无                                    ✅ Pattern Memory (跨会话学习)
⬜ SubAgent 模型定义 (未实现)            ✅ SubAgent (delegate tool)
⬜ 无                                    ✅ Tool Guardrails
⬜ 无                                    ✅ Background Review

图例: ✅ 已有  ⚠️ 有但弱  ⬜ 缺失
```

---

## 2. 设计目标与原则

### 目标

1. **鲁棒性优先**：分析不因单次工具失败而崩溃，错误自动分类处理
2. **结果可信**：每次分析结论有据可查，置信度透明
3. **持续学习**：成功经验可复用，失败路径可避免
4. **渐进式升级**：每个 Phase 独立可交付，不破坏现有功能

### 设计原则

| 原则 | 说明 |
|------|------|
| **不重复造 Claude Agent SDK** | SmartPerfetto 将 Agent 循环委托给 Claude SDK。lv-game-toolkit 走 LiteLLM 通用路线，需要自建循环控制逻辑 |
| **确定性优先于 AI 智能** | 能工具做的事不给 AI 猜。错误分类、熔断、验证 → 确定性规则 |
| **借鉴模式不照搬代码** | Hermes 是通用 Agent 框架，包含大量不相关功能（browser/discord/image_gen）。提取设计模式，Python 原生实现 |
| **保持桌面应用约束** | 单用户、本地运行、SQLite 存储。不引入 Redis/PostgreSQL/消息队列 |
| **向后兼容** | 现有 ToolRegistry/SkillRegistry/MCP 接口不变，新能力通过扩展接入 |

---

## 3. 框架升级方案

### 3.1 对话循环升级：从朴素递归到鲁棒编排

#### 现状问题

当前 `AgentService._run_loop()` 是朴素尾递归：
- 工具失败 → `refund()` 退预算 → 无错误分类
- 连续 5 次同一工具失败 → 仍然继续尝试
- LLM 调用超时 → 无超时控制
- 上下文增长 → 简单截断（可能丢失关键数据）

#### 升级方案

新增 `toolkit/agent/conversation_loop.py`，将 `_run_loop` 重构为状态机驱动的鲁棒循环：

```python
# 新增: toolkit/agent/conversation_loop.py
class ConversationLoop:
    """鲁棒的多轮对话循环（借鉴 Hermes conversation_loop.py 设计模式）。

    状态机:
      INIT → LLM_CALL → TOOL_DISPATCH → RESULT_INJECT → LLM_CALL
                ↓              ↓               ↓
              DONE        GUARDRAIL       CONTEXT_OVERFLOW
                            ↓                  ↓
                        CIRCUIT_BREAK    COMPRESS_AND_CONTINUE
    """

    def __init__(
        self,
        provider: BaseLLMProvider,
        tool_executor: ToolExecutor,
        budget: IterationBudget,
        guardrail: ToolGuardrail,           # ← 新增
        context_compressor: ContextCompressor,  # ← 新增
        error_classifier: ErrorClassifier,      # ← 新增
        circuit_breaker: CircuitBreaker,        # ← 新增
        watchdog: Watchdog,                     # ← 新增
    ): ...

    async def run(
        self,
        messages: list[dict],
        system_prompt: str,
        on_chunk: Callable | None = None,
    ) -> LoopResult:
        """执行完整对话循环，内置所有韧性机制。"""
```

**关键新增组件**：

| 组件 | 文件 | 职责 |
|------|------|------|
| `ErrorClassifier` | `toolkit/agent/error_classifier.py` | 将 LLM/工具错误分为 retryable / fallback / fatal |
| `CircuitBreaker` | `toolkit/agent/circuit_breaker.py` | 工具连续失败 N 次 → 熔断 → 切换策略 |
| `Watchdog` | `toolkit/agent/watchdog.py` | 单轮/全局超时检测 → 注入总结提示 |
| `RetryPolicy` | `toolkit/agent/retry_policy.py` | 429 退避、5xx Provider 切换、4xx 立即失败 |

#### ErrorClassifier 设计

```python
# toolkit/agent/error_classifier.py
from enum import Enum

class ErrorCategory(Enum):
    RETRYABLE = "retryable"        # 瞬态错误：429, 503, timeout, connection reset
    RETRYABLE_WITH_BACKOFF = "retryable_with_backoff"  # 限流类：指数退避
    FALLBACK = "fallback"          # 可降级：当前 Provider 不可用 → 切换备选
    DEGRADED = "degraded"         # 可降级：工具部分失败 → 用部分结果继续
    FATAL = "fatal"                # 不可恢复：4xx auth error, invalid request
    TOOL_NOT_FOUND = "tool_not_found"  # 工具不存在 → 提示 LLM 换工具
    TOOL_ARG_ERROR = "tool_arg_error"   # 参数错误 → 让 LLM 修正参数

class ErrorClassifier:
    """分类 LLM 和工具执行中的错误，决定后续策略。"""

    def classify_llm_error(self, error: Exception, provider_name: str) -> ErrorCategory: ...
    def classify_tool_error(self, tool_name: str, error: Exception) -> ErrorCategory: ...
    def get_action(self, category: ErrorCategory) -> ErrorAction:
        """返回 {retry_with_backoff, switch_provider, skip_tool, abort, ...}"""
```

#### CircuitBreaker 设计

```python
# toolkit/agent/circuit_breaker.py
class CircuitBreaker:
    """工具熔断器 — 借鉴 Hermes + SmartPerfetto watchdog 设计。

    三种状态:
      CLOSED — 正常，工具调用正常通过
      HALF_OPEN — 探测期，允许 1 次调用尝试
      OPEN — 熔断，拒绝工具调用，强制降级策略
    """

    def __init__(
        self,
        failure_threshold: int = 5,       # 连续失败 > 此值 → 熔断
        overall_failure_rate: float = 0.6, # 全局失败率 > 60% → 熔断
        recovery_timeout: float = 30.0,    # 熔断后 N 秒进入半开
    ): ...

    def record_success(self, tool_name: str) -> None: ...
    def record_failure(self, tool_name: str, error: str) -> CircuitState: ...
    def before_call(self, tool_name: str) -> bool:  # True = 允许调用
        """如果熔断打开 → 返回 False + 生成替代提示注入 System Prompt"""
```

#### 升级后的对话循环流程

```
analyze(query)
  │
  ├─ Phase 0: 意图 + 预算初始化
  │   ├─ SkillRouter.match(query) → top-3 Skills
  │   ├─ IterationBudget(max=config.max_iterations)
  │   └─ CircuitBreaker.reset()
  │
  ├─ Phase 1: 对话循环（状态机驱动）
  │   │
  │   ├─ [LLM_CALL]
  │   │   ├─ Watchdog.start(per_turn_timeout=60s)
  │   │   ├─ provider.stream_chat()
  │   │   ├─ ErrorClassifier.classify_llm_error() → retry/fallback/fatal
  │   │   └─ Watchdog.stop()
  │   │
  │   ├─ [CHECK_TOOL_CALLS]
  │   │   ├─ 无工具调用 → DONE
  │   │   └─ 有工具调用 → TOOL_DISPATCH
  │   │
  │   ├─ [TOOL_DISPATCH]
  │   │   ├─ Guardrail.validate(tool_name, args) → reject hint / allow
  │   │   ├─ CircuitBreaker.before_call(tool_name) → allow / reject
  │   │   ├─ ToolExecutor.execute() → ToolResult
  │   │   ├─ ErrorClassifier.classify_tool_error() → skip/retry/degrade
  │   │   ├─ CircuitBreaker.record_success/failure()
  │   │   └─ _check_budget() → 预算耗尽 → 注入 "请总结"
  │   │
  │   ├─ [RESULT_INJECT]
  │   │   ├─ ContextCompressor.compress_if_needed(messages, max_tokens)
  │   │   └─ messages.append(tool_result) → 回到 LLM_CALL
  │   │
  │   └─ [SAFETY_TIMEOUT] (全局 300s)
  │       └─ 硬超时 → 强制注入 "时间不足，请给出部分结论"
  │
  ├─ Phase 2: 质量验证（见 3.4）
  │
  └─ Phase 3: 记忆更新（见 3.3）
```

---

### 3.2 工具执行安全层：Guardrails + Circuit Breaker

#### 设计

Hermes 的 `tool_guardrails.py` 提供了多层安全检查。在 lv-game-toolkit 的语境下，工具安全门禁的核心价值是：

1. **防止 AI 调用危险操作**（如删除文件、修改配置）
2. **参数合法性校验**（如 trace 文件路径是否存在）
3. **频率限制**（防止 AI 循环调用同一工具）

```python
# 新增: toolkit/agent/tool_guardrail.py
from dataclasses import dataclass

@dataclass
class GuardrailResult:
    allowed: bool
    rejection_reason: str = ""
    correction_hint: str = ""  # 如果参数有问题，给 LLM 的修正建议

class ToolGuardrail:
    """工具调用安全门禁（借鉴 Hermes tool_guardrails.py）。

    三层检查:
      1. 静态规则 — 黑名单工具 / 危险参数模式
      2. 动态规则 — 文件路径沙箱 / 频率限制
      3. 自定义规则 — 模块可注册自己的 validate 回调
    """

    def __init__(self, workspace_root: Path): ...

    def validate(self, tool_name: str, arguments: dict) -> GuardrailResult:
        """返回 (allowed, rejection_hint)。

        rejection_hint 会注入到 LLM 的下一条 system message 中，
        引导 LLM 换工具或修正参数。
        """

    # 预定义规则
    DANGEROUS_PATTERNS = [
        r"rm\s+-rf", r"DELETE\s+FROM", r"os\.system", r"subprocess",
    ]

    FILE_WRITE_ALLOWED_DIRS = ["data/output/", "data/workspace/"]
```

---

### 3.3 上下文管理升级：智能压缩 + Memory 跨会话

#### ContextCompressor

当前 `_smart_truncate` 仅按优先级保留 Skill 消息，其余直接截断。Hermes 的 `context_compressor.py` 提供了更智能的方案：

```python
# 新增: toolkit/agent/context_compressor.py
class ContextCompressor:
    """智能上下文压缩（借鉴 Hermes context_compressor.py）。

    策略（按优先级尝试）:
      1. 摘要压缩 — 对旧工具结果生成 ≤200 char 摘要替代原文
      2. 片段保留 — 关键数字（FPS、耗时、百分比）从原文中提取保留
      3. 截断降级 — 仍然超出时，保留最近 N 轮完整 + 早期摘要
    """

    def compress_if_needed(
        self,
        messages: list[dict],
        max_tokens: int,
        preserve_recent: int = 4,  # 保留最近 4 轮完整内容
    ) -> list[dict]:
        """估算 token 数 → 超出则压缩 → 返回压缩后的消息列表。"""

    def _extract_key_numbers(self, text: str) -> str:
        """从工具结果中提取关键数值指标。"""
        patterns = {
            'fps': r'(\d+\.?\d*)\s*fps',
            'duration_ms': r'(\d+\.?\d*)\s*ms',
            'percentage': r'(\d+\.?\d*)%',
            'count': r'(\d+)\s*(?:帧|次|个)',
        }
        # 返回 "核心数据: FPS=58.2, 耗时=1234ms, 丢帧=15"
```

#### Memory Manager

当前 `ConversationStore` 只存消息。借鉴 Hermes `memory_manager.py`，增加跨会话记忆：

```python
# 扩展: toolkit/agent/memory/conversation.py → 新增 memory_manager.py
class MemoryManager:
    """跨会话记忆管理（借鉴 Hermes memory_manager.py）。

    三类记忆:
      1. 用户偏好 — 常用 Provider/Model、语言偏好、分析风格
      2. 设备特征 — 已知设备的平台/厂商/GPU 型号
      3. 分析模式 — 成功分析路径 → 快速复用
    """

    def remember_user_preference(self, key: str, value: Any) -> None: ...
    def recall_device_info(self, device_id: str) -> dict | None: ...
    def save_analysis_pattern(self, pattern: AnalysisPattern) -> None: ...
    def find_similar_analysis(self, query: str) -> list[AnalysisPattern]: ...
```

---

### 3.4 分析质量保障：Verification + Reflection + Checkpoint

借鉴 SmartPerfetto 的 `claimVerification` + `finalReportContractGate` + Hermes 的证据追踪：

```python
# 新增: toolkit/agent/verification.py
class VerificationRunner:
    """分析结论验证（借鉴 SmartPerfetto claimVerificationRunner.ts）。

    验证管道:
      1. 数据核实 — 结论中引用的数字是否与工具输出一致
      2. 逻辑检查 — 因果推断是否合理（相关性 ≠ 因果性）
      3. 完整性检查 — 是否覆盖了 SOP 规定的必查维度
      4. 知识库对照 — 结论是否与已知模式一致/矛盾
    """

    def verify(self, response: LLMResponse, tool_results: list[ToolResult]) -> VerificationReport:
        """返回包含 passed/warning/error 的验证报告。"""

    def generate_correction_prompt(self, report: VerificationReport) -> str:
        """如果验证未通过，生成修正提示用于二次分析。"""


class ConfidenceModel:
    """置信度五级标注（借鉴 SmartPerfetto 置信度模型）。

    verified          — SQL + 知识库 + Check Tool 全确认
    knowledge_matched — 知识库命中，部分数据支撑
    partial           — SQL 支撑但无知识库命中
    inference         — AI 推理，无直接数据
    unsupported       — 无证据
    """
```

**分析计划门禁**（借鉴 SmartPerfetto `submit_plan`）：

```python
# 扩展: toolkit/agent/orchestrator.py
class PlanGate:
    """复杂分析的计划门禁 — 强制 AI 先提交计划再执行。

    触发条件: 检测到 >5 个工具调用的复杂分析任务
    行为: 要求 LLM 先调用 submit_plan({phases: [...], estimated_tools: [...]})
           → 验证阶段覆盖 mandatory_aspects → 放行/退回重写
    """
```

---

### 3.5 知识库体系：从空壳到可检索

当前 `ReportIndex` 仅做文件名索引，无内容检索。lv-game-toolkit 已有的案例库 + SOP + vendor override 需要被检索到：

```python
# 新增: toolkit/agent/knowledge/knowledge_base.py
class KnowledgeBase:
    """本地知识库（借鉴 Hermes skill system + SmartPerfetto ragStore）。

    内容来源:
      1. modules/*/skills/ 下的 SKILL.md — 分析方法论
      2. modules/*/cases/ 下的案例 — 历史分析案例
      3. modules/*/vendors/ 下的 override — 厂商特定知识
      4. modules/*/sop/ 下的 SOP — 标准操作流程

    检索方式:
      Phase 1: TF-IDF + 关键词匹配（复用 SkillRouter 的 TF-IDF 引擎）
      Phase 2: 可选 BM25（需评估精度需求）
    """

    def __init__(self, skill_registry: SkillRegistry): ...

    def build_index(self) -> None:
        """扫描所有 Skill 文件 + 案例 + SOP + Vendor，建立统一索引。"""

    def search(self, query: str, top_k: int = 5, domain: str = "") -> list[KnowledgeEntry]:
        """搜索相关知识条目，返回按相关度排序的结果。"""

    def get_entry(self, entry_id: str) -> KnowledgeEntry | None:
        """获取单条知识完整内容（渐进式加载）。"""
```

**整合到 System Prompt**：

```python
# 扩展 system_prompt.py 的 _build_stable_prompt
def _build_stable_prompt(tools, skills, knowledge_entries, ...):
    # 在 "可用 Skill" 之后新增:
    # "## 相关知识库条目"
    # for entry in knowledge_entries:
    #     f"- {entry.title}: {entry.summary[:100]}"
```

---

### 3.6 多 Agent 协作：SubAgent + ACP 启步

当前 SubAgent 模型已定义但 `spawn_subagent()` 抛出 `NotImplementedError`。

#### Phase 1: 基础 SubAgent

```python
# 扩展: toolkit/agent/orchestrator.py 的 spawn_subagent()
async def spawn_subagent(self, config: SubAgentConfig) -> SubAgentResult:
    """基于工具过滤 + 限定预算的独立子 Agent。

    使用场景:
      - 同时分析 CPU 和 GPU 维度 → 两个 SubAgent 并行
      - 对比两份 Trace 的启动阶段 → 各自分析后合并
    """
    # 1. 创建受限 ToolRegistry（仅 config.tool_filter 中的工具）
    # 2. 独立 IterationBudget(max_turns)
    # 3. 独立 ConversationLoop（不共享上下文）
    # 4. 结果返回给主 Agent → 主 Agent 合并结论
```

#### Phase 2: ACP 启步（远期）

```python
# 预留: toolkit/agent/acp.py
class ACPMessage:
    """Agent Communication Protocol 消息格式。
    借鉴 Hermes ACP 协议：标准化 Agent 间通信的消息格式。
    """
    sender_id: str
    receiver_id: str
    intent: str          # "delegate" | "query" | "inform" | "request_approval"
    payload: dict
    correlation_id: str  # 关联主任务的 ID
```

---

### 3.7 错误韧性：Error Classifier + Failover

完整的错误处理链：

```
异常发生
  │
  ├─ ErrorClassifier.classify()
  │   ├─ RETRYABLE → 重试（原 Provider/工具）
  │   ├─ RETRYABLE_WITH_BACKOFF → 指数退避重试 (1s→2s→4s→8s)
  │   ├─ FALLBACK → 切换备选 Provider / 跳过该工具
  │   ├─ FATAL → 终止分析 + 用户通知 + 日志
  │   ├─ TOOL_NOT_FOUND → 注入 hint "工具 X 不存在，请使用 Y 或 Z"
  │   └─ TOOL_ARG_ERROR → 注入 hint "工具 X 参数错误: {detail}，请修正"
  │
  └─ CircuitBreaker 跟踪全局失败率
      ├─ failure_rate < 30% → 正常
      ├─ failure_rate 30-60% → 注入提示 "部分工具不稳定，请谨慎"
      └─ failure_rate > 60% → 熔断 + 切换策略 + 通知用户
```

---

## 4. 目标架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│  toolkit/agent/                                                      │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  AgentOrchestrator (编排入口)                                  │   │
│  │  • 生命周期管理  • 工具发现  • System Prompt 组装             │   │
│  │  • SubAgent 调度  • 配置变更响应                               │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                        │
│  ┌──────────────────────────▼───────────────────────────────────┐   │
│  │  ConversationLoop (鲁棒对话循环) — 状态机驱动                  │   │
│  │                                                                │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────────┐    │   │
│  │  │ Error    │  │ Circuit      │  │ Watchdog             │    │   │
│  │  │ Classifier│  │ Breaker      │  │ (超时检测)           │    │   │
│  │  └──────────┘  └──────────────┘  └──────────────────────┘    │   │
│  │                                                                │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────────┐    │   │
│  │  │ Retry    │  │ Context      │  │ Tool                 │    │   │
│  │  │ Policy   │  │ Compressor   │  │ Guardrail             │    │   │
│  │  └──────────┘  └──────────────┘  └──────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  质量保障层                                                     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │ Verification │  │ Confidence   │  │ PlanGate         │   │   │
│  │  │ Runner       │  │ Model        │  │ (计划门禁)        │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  记忆与知识层                                                   │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │ Memory       │  │ Knowledge    │  │ Pattern          │   │   │
│  │  │ Manager      │  │ Base         │  │ Memory           │   │   │
│  │  │ (跨会话记忆)  │  │ (Skill+案例) │  │ (分析模式)        │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  AgentService (对外接口 — 保持现有 API 兼容)                   │   │
│  │  • chat() — 同步对话入口                                      │   │
│  │  • 流式回调 / 取消 / Provider 切换                             │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘

toolkit/core/ (基础设施 — DES-001 已交付，本次不变更)
┌─────────────────────────────────────────────────────────────────────┐
│  ToolRegistry  │  SkillRegistry  │  MCP Framework  │  ToolExecutor  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. 分阶段实施路线

### Phase 1: 韧性基础（3-5 天）— 🎯 MVP

**目标**：对话循环不再因单次错误崩溃

| 交付物 | 文件 | 说明 |
|--------|------|------|
| ErrorClassifier | `toolkit/agent/error_classifier.py` | 5 种错误分类 + 差异化动作映射 |
| RetryPolicy | `toolkit/agent/retry_policy.py` | 指数退避 + Provider 切换 |
| CircuitBreaker | `toolkit/agent/circuit_breaker.py` | 工具熔断器（三态） |
| Watchdog | `toolkit/agent/watchdog.py` | 单轮/全局超时 |
| ConversationLoop | `toolkit/agent/conversation_loop.py` | 集成以上组件的新循环 |
| 测试 | `tests/test_agent_conversation_loop.py` | 错误注入 + 熔断验证 |

**验收标准**：
- 注入 5 次连续工具失败 → CircuitBreaker 熔断 → 降级策略执行
- LLM 429 错误 → 自动退避重试（3 次）
- 全局超时 300s → Watchdog 触发 → 返回部分结果

### Phase 2: 质量保障（3-5 天）

**目标**：分析结论有据可查，置信度透明

| 交付物 | 文件 | 说明 |
|--------|------|------|
| ContextCompressor | `toolkit/agent/context_compressor.py` | 智能压缩 + 关键数字保留 |
| VerificationRunner | `toolkit/agent/verification.py` | 数据核实 + 逻辑检查 + 完整性 |
| ConfidenceModel | `toolkit/agent/verification.py` | 五级置信度标注 |
| ToolGuardrail | `toolkit/agent/tool_guardrail.py` | 静态/动态规则 + rejection hint |
| PlanGate | `toolkit/agent/orchestrator.py` (扩展) | 复杂任务计划门禁 |

**验收标准**：
- 结论中的数据声称与工具输出一致（验证管道 PASS）
- 上下文超限时压缩不丢失 FPS/Jank/耗时关键数据
- 置信度标签正确展示在 AgentPanel

### Phase 3: 知识库与记忆（5-7 天）

**目标**：历史经验可检索复用

| 交付物 | 文件 | 说明 |
|--------|------|------|
| KnowledgeBase | `toolkit/agent/knowledge/knowledge_base.py` | TF-IDF 搜索 Skill + 案例 + SOP |
| MemoryManager | `toolkit/agent/memory/memory_manager.py` | 用户偏好 + 设备特征 + 分析模式 |
| PatternMemory | `toolkit/agent/memory/pattern_memory.py` | 成功/失败路径记录 |
| SkillRouter 增强 | `toolkit/agent/skill_router.py` (扩展) | 整合 KnowledgeBase 搜索结果到路由 |
| SystemPrompt 增强 | `toolkit/agent/system_prompt.py` (扩展) | 注入相关知识库条目 |

**验收标准**：
- 查询 "Camera 冷启动慢" → KnowledgeBase 返回相关案例（命中率 ≥ 60%）
- 同一设备二次分析 → MemoryManager 自动注入设备特征到 System Prompt
- 成功分析路径被记录 → 下次类似问题可快速复用

### Phase 4: SubAgent + ACP 启步（5-7 天）— 远期可选

| 交付物 | 文件 | 说明 |
|--------|------|------|
| SubAgent 实现 | `toolkit/agent/subagent/` | 工具过滤 + 独立预算 + 结果合并 |
| ACP 协议定义 | `toolkit/agent/acp.py` | 消息格式 + 路由 |
| Tool Guardrail 增强 | `toolkit/agent/tool_guardrail.py` | 自定义规则注册接口 |

---

## 6. 关键决策与待决事项

| # | 决策项 | 选项 | 建议 |
|---|--------|------|------|
| 1 | ConversationLoop 是替换还是包装现有 `_run_loop`？ | A: 替换 (一次性迁移) / B: 包装 (旧路径兼容) | **A** — 现有代码量小（~130行），替换风险低 |
| 2 | ContextCompressor 是否需要 LLM 参与摘要？ | A: 纯规则提取 / B: LLM 摘要（额外 API 调用） | **A Phase 1** — 规则提取零成本；B 作为 Phase 2 优化项 |
| 3 | 知识库用什么检索算法？ | A: TF-IDF（已有 SkillRouter 引擎）/ B: BM25 / C: 本地 Embedding | **A Phase 1** — 复用现有代码；精度不足时评估 B |
| 4 | Pattern Memory 存哪里？ | A: SQLite（与 ConversationStore 同库）/ B: JSON 文件 | **A** — 结构化查询更方便 |
| 5 | 是否引入多 Provider failover？ | A: 仅提示用户切换 / B: 自动切换备选 Provider | **A Phase 1** — 桌面应用单 Provider 场景为主 |
| 6 | CircuitBreaker 熔断后是降级还是终止？ | A: 降级（用部分结果） / B: 终止（返回错误） | **A** — 部分结果比没有结果更有价值 |

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| ConversationLoop 重构引入回归 | 对话功能不可用 | Phase 1 保留旧 `_run_loop` 为 `_run_loop_legacy`，feature flag 切换 |
| ContextCompressor 误删关键数据 | 分析结论错误 | 保留"关键数字提取"白名单（FPS/耗时/百分比），其余仅摘要 |
| 知识库冷启动（案例不足） | 搜索命中率低 | Phase 1 直接用 Skill 的 name+description+tags 作为种子索引 |
| TF-IDF 精度不足 | 知识库搜索体验差 | 预留 BM25 接口，Phase 2 按需升级 |
| 新增组件过多导致复杂度爆炸 | 维护困难 | 每个组件 ≤ 200 行，单一职责；ConversationLoop 仅做编排不包含具体逻辑 |
| SubAgent 并行执行的线程安全 | 数据竞争 | Agent 场景下 SubAgent 通常是独立任务（不同维度分析），共享只读数据 |

---

> **文档状态**：初稿完成。下一步：团队 review → 确认 Phase 1 范围 → 创建 Speckit spec 进入开发。
