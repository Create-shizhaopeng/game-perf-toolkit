# Agent 记忆与经验演进设计

## 目录

- [背景与动机](#背景与动机)
- [OpenClaw 记忆系统架构参考](#openclaw-记忆系统架构参考)
  - [三层记忆模型](#三层记忆模型)
  - [记忆生命周期管理](#记忆生命周期管理)
  - [混合检索策略](#混合检索策略)
  - [Heartbeat 维护机制](#heartbeat-维护机制)
  - [子 Agent 编排模式](#子-agent-编排模式)
- [当前项目现状与差距分析](#当前项目现状与差距分析)
- [SubAgent 问题诊断（P1-P7）](#subagent-问题诊断p1-p7)
  - [P1 无记忆的一次性 Agent](#p1-无记忆的一次性-agent)
  - [P2 工具返回值过度压缩](#p2-工具返回值过度压缩)
  - [P3 MainAgent 路由过于粗浅](#p3-mainagent-路由过于粗浅)
  - [P4 SubAgent prompt 缺少推理链引导](#p4-subagent-prompt-缺少推理链引导)
  - [P5 request_limit 过高且无中间检查点](#p5-request_limit-过高且无中间检查点)
  - [P6 Review 实质失效](#p6-review-实质失效)
  - [P7 无反馈回路](#p7-无反馈回路)
- [改进方案设计（G0-G6）](#改进方案设计g0-g6)
  - [G0 SubAgent 推理链重构](#g0-subagent-推理链重构)
  - [G1 分析经验自动沉淀](#g1-分析经验自动沉淀)
  - [G2 相似案例注入](#g2-相似案例注入)
  - [G3 经验淘汰与晋升](#g3-经验淘汰与晋升)
  - [G4 Review 增强](#g4-review-增强)
  - [G5 Skill 知识层级应用](#g5-skill-知识层级应用)
  - [G6 接通 package_db 学习链](#g6-接通-package_db-学习链)
- [优先级与依赖关系](#优先级与依赖关系)
- [参考资料](#参考资料)

## 背景与动机

当前 perfetto_analysis 模块的 Agent 编排（Main → Sub → Review）已具备基本分析能力，但存在一个核心问题：**每次分析都从零开始，无法积累和复用历史分析经验**。

对比 [OpenClaw](https://github.com/openclaw/openclaw) 的记忆系统设计，我们的 Agent 在以下方面有明显差距：
- 无跨会话记忆：SubAgent 每次仅有 SOP 静态指令，不知道历史上类似 trace 的分析结论
- 经验闭环断裂：`raw_data/*.json` 落盘后不回注 Agent 上下文
- 无过时淘汰：分析历史只增不减，无价值评估和清理
- 模式库脱节：`patterns/cases/` 人工维护，不进入运行时 Agent

本文档参考 OpenClaw 的记忆架构，设计适合本项目 Perfetto 分析场景的改进方案。

## OpenClaw 记忆系统架构参考

> 信息来源：OpenClaw GitHub 仓库、腾讯云技术文章、知乎技术解析、Reddit 社区讨论

### 三层记忆模型

OpenClaw 将 Agent 记忆分为三个层次：

| 层级 | 名称 | 存储形式 | 特点 |
|------|------|----------|------|
| **L1** | 工作记忆 | 当前 Session JSONL | 短时、未加工、随会话销毁 |
| **L2** | 长期记忆 | `MEMORY.md` | 提炼后的结构化经验，跨会话持久 |
| **L5** | 知识图谱 | `ontology` + `vector_store.db` | 实体关系 + 向量语义检索 |

**设计哲学**：短期记忆是原始素材，长期记忆是精炼智慧，知识图谱是深层关联。

**与我们的映射**：
- L1 → 当前 SubAgent 的工具调用历史（已有，但不持久）
- L2 → **缺失**，这是最关键的差距
- L5 → `patterns/` + `cases/` 已有文档形态，但无自动检索层

### 记忆生命周期管理

OpenClaw 的记忆经历完整生命周期：

```
产生 → 评估 → 存储 → 检索 → 使用 → 衰减 → 淘汰/晋升
```

**核心评分公式**：

```
memory_score = recency × importance × frequency

其中：
- recency = decay_factor ^ (current_time - last_access)    # 时间衰减
- importance = weight（由 LLM 或规则评定）                   # 重要性权重
- frequency = log(access_count + 1)                         # 访问频率对数
```

**淘汰策略**：
- `score < low_threshold` → 直接删除
- `low_threshold ≤ score < high_threshold` → 压缩为摘要
- `score ≥ high_threshold` → 保留，定期晋升到 MEMORY.md

**与我们的映射**：当前项目完全没有记忆评分和淘汰机制。`pa_get_history` 只是按时间顺序列出所有历史，不做价值判断。

### 混合检索策略

OpenClaw 采用三信号加权的混合检索：

```
final_score = 0.5 × semantic_similarity   # 向量语义搜索
            + 0.3 × bm25_keyword_score    # 关键词精确匹配
            + 0.2 × time_decay            # 时间衰减（优先近期）
```

**关键设计**：
- 语义搜索用于捕捉"类似场景"（如"GPU 频率降频导致帧率不稳"与"GPU thermal throttling"的语义关联）
- BM25 用于精确匹配（如进程名、设备型号、根因标签）
- 时间衰减确保最新的分析经验被优先参考

**与我们的映射**：当前项目无任何检索机制。G2 方案初期可用标签匹配 + 关键词实现最小可行版本，后续升级 embedding。

### Heartbeat 维护机制

OpenClaw 的 Heartbeat 是一个定时触发的维护流程：

```
每 30 分钟触发：
1. 读取近 7 天的 daily notes (memory/YYYY-MM-DD.md)
2. LLM 提取有价值的 insights
3. 高价值 insight → 写入 MEMORY.md
4. 过期/低价值信息 → 清理
```

**Compaction（上下文压缩）**：当 Session 超过 40K tokens 时触发 `memoryFlush`：
- LLM 将当前对话蒸馏为：决策、状态变更、经验教训、阻塞点
- 写入 `memory/YYYY-MM-DD.md`
- 清理历史对话，释放上下文窗口

**Bootstrap Hook**：新 Session 启动时自动加载 `.learnings/` 和 `MEMORY.md`，确保 Agent 快速恢复状态。

**与我们的映射**：
- Heartbeat → 我们的场景是"每次分析完成后"（事件驱动，非定时），更适合在 `_finalize` 阶段触发经验提取
- Compaction → 我们的 `ResultCompressor` 已实现工具返回值压缩（≤300 token），但未对分析结论做压缩存储
- Bootstrap → 类似 G2 方案：分析前注入相关历史经验

### 子 Agent 编排模式

OpenClaw 的子 Agent 系统特点：

| 特性 | OpenClaw | 当前项目 |
|------|----------|---------|
| 隔离性 | 完全独立会话、独立上下文 | ✅ 每 trace 独立 SubAgent |
| 非阻塞 | `sessions_spawn` 立即返回 | ✅ GUI 层 QThread 异步 |
| 完成反馈 | 结构化 Announce 消息 | ❌ 仅 `summary[:200]` |
| 层级编排 | Main → 编排子 → 工作子（maxSpawnDepth=2） | ✅ Main → Sub → Review |
| 记忆继承 | 子 Agent 可访问父级 MEMORY.md | ❌ SubAgent 仅有 SOP |
| 流量隔离 | Lane Queue 分离 main/subagent/cron | ❌ 无（但并发场景少） |

## 当前项目现状与差距分析

### 已有的经验积累设施

| 设施 | 位置 | 进入 Agent 运行时？ | 状态 |
|------|------|---------------------|------|
| SOP 流程文档 | `skills/perfetto-analysis/sop/` | ✅ 全文注入 SubAgent | 已接入 |
| 根因模式库 | `skills/perfetto-analysis/patterns/` | ❌ 仅文档 | 人工维护 |
| 案例库 | `skills/perfetto-analysis/cases/` | ❌ 仅文档 | 模板已建 |
| SQL 模式库 | `skills/perfetto-analysis/sql-patterns.md` | ❌ 仅文档 | 已整理 |
| 分析历史 | `pa_analysis_tasks` + 磁盘 JSON | ⚠️ 工具可查询 | 不自动注入 |
| 包名映射 | `PackageMappingDB` | ❌ 未接线 | 代码已实现 |
| 原始分析数据 | `output/analysis/*/raw_data/*.json` | ❌ 仅落盘 | 不回注 |

### 核心差距总结

```
                        OpenClaw                    当前项目
                    ┌─────────────┐              ┌─────────────┐
   分析完成后       │ 提取经验     │              │ 落盘 JSON    │
                    │ → learnings │              │ → 结束       │ ← 断裂点
                    └──────┬──────┘              └─────────────┘
                           │
                    ┌──────▼──────┐
   定期维护         │ 评分/淘汰   │              （无）
                    │ → 晋升      │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
   新分析开始       │ 检索相似经验 │              （无）
                    │ → 注入上下文 │
                    └─────────────┘
```

## SubAgent 问题诊断（P1-P7）

> 以下问题基于代码审查发现，按严重程度排序。每个问题标注对应的 OpenClaw 对照设计。

### P1 无记忆的一次性 Agent

**代码位置**：`agents.py:32-55`、`orchestrator.py:270-360`

**现状**：SubAgent 的一生是线性且短暂的：

```
创建 → 注入 SOP 全文 → 接收固定 prompt → 自由调用 pa_* 工具（上限 100 次）→ 输出自由文本 → 销毁
```

每次分析都从零开始。SubAgent 不知道：
- 同一设备/应用的历史分析结论
- 过去哪些分析路径有效、哪些是死胡同
- 常见的根因模式和判断经验

**OpenClaw 对照**：
- OpenClaw 的 SubAgent 通过 Bootstrap Hook 加载 `MEMORY.md` 和 `.learnings/`
- 新 Session 启动即携带历史经验，不从零开始
- Active Memory (2026.4.10) 在回复前执行有界的记忆传递

**影响**：分析准确性完全依赖 SOP 的静态质量和 LLM 的通用知识，无法"越用越好"。

### P2 工具返回值过度压缩

**代码位置**：`tools.py:54`

```python
compressed = compressor.compress_tool_output(tool_name, raw, 300)
```

**现状**：所有 9 个工具的返回值一律压缩到 300 token。但不同工具的数据重要性差异巨大：
- `pa_list_dimensions` 返回 10 个维度名，50 token 足够
- `pa_analyze_dimension(cpu)` 返回 8 核频率变化 + 调度分布 + 延迟分析，300 token 远远不够
- `pa_detect_jank` 返回 Top-5 卡顿帧及时间窗口，需要完整保留

**OpenClaw 对照**：
- OpenClaw 不做单工具级压缩，而是在**会话级**通过 Compaction 管理总 token
- 40K token 触发 `memoryFlush`，蒸馏关键信息后清理历史
- 单个工具返回保持完整，确保推理质量

**影响**：LLM 只看到摘要性文字，无法做细粒度归因。例如 CPU 分析中"部分核心频率被限制"无法精确到"Core 4-7 在 ts=12.3s 从 2.8GHz 降到 1.4GHz"。

### P3 MainAgent 路由过于粗浅

**代码位置**：`agents.py:13-29`

```python
instructions=(
    "根据用户意图判断分析场景。场景: jank/anr/memory/startup/cpu/general。"
    "输出 scene, sop_name, process_name, reasoning。"
)
```

**现状**：MainAgent 只做场景分类（6 选 1），不做分析策略规划：
- 不决定优先分析哪些维度
- 不根据 trace overview 特征调整策略（如帧数为 0 时应该跳过 jank 检测）
- 不注入历史经验来指导路由

**OpenClaw 对照**：
- 编排层在路由前执行 memory retrieval，将相关历史注入决策
- 路由决策基于当前输入 **+** 历史上下文
- 通过 `HEARTBEAT.md` 清单驱动策略选择

**影响**：MainAgent 的路由结果可能不准确（如游戏 trace 被错误路由到 jank 场景），SubAgent 被迫按照错误的 SOP 分析。

### P4 SubAgent prompt 缺少推理链引导

**代码位置**：`orchestrator.py:311-321`

```python
prompt = (
    f"请分析以下 trace，并输出**人类可读的中文分析报告**:\n"
    f"- Trace 路径: {trace_path}\n"
    f"- 目标进程: {routing.process_name or '自动检测'}\n"
    f"- 分析场景: {routing.scene}\n\n"
    f"报告格式要求:\n"
    f"1. **问题概述**: ...\n2. **根因分析**: ...\n3. **关键数据**: ...\n4. **优化建议**: ...\n"
    f"\n注意：调用工具后请尽快归纳结论，避免过多重复调用。"
)
```

**现状**：prompt 只定义了输出格式（4 个章节），不定义推理路径。LLM 的行为不可预测：
- 可能随机选择维度分析顺序
- 可能忽略 SOP 中的判断条件（如"Running 高 + 小核/低频 → 调度策略问题"）
- 可能在结论中缺少证据链（"因为 X 所以 Y"）
- 可能重复调用同一工具或遗漏关键工具

**OpenClaw 对照**：
- OpenClaw 的 `SOUL.md` 定义 Agent 的人格和行为约束
- 任务描述包含明确的步骤和决策条件
- 通过工具调用序列的约束控制推理方向

**影响**：分析质量高度依赖 LLM 的"心情"。同一 trace 多次分析可能得到截然不同的结论。

### P5 request_limit 过高且无中间检查点

**代码位置**：`orchestrator.py:324-327`

```python
from pydantic_ai.usage import UsageLimits
result = await agent.run(
    prompt,
    usage_limits=UsageLimits(request_limit=100),
)
```

**现状**：允许 100 次 LLM 请求，没有中间检查点。SubAgent 可能：
- 在前 10 次调用中获得足够信息后仍继续调用（浪费 token）
- 陷入重复调用循环（如反复查询同一维度的不同参数）
- 100 次用完后被强制终止，得到不完整的结论

**OpenClaw 对照**：
- 通过 Compaction 在 40K token 时触发检查点
- `cache-ttl` 对上下文做时间剪枝
- 子 Agent 有明确的 `maxSpawnDepth` 限制

**影响**：token 消耗不可控，分析效率低。

### P6 Review 实质失效

**代码位置**：`report.py:60`、`orchestrator.py:494-499`

```python
# report.py
summary = conclusion[:200] if conclusion else ""

# orchestrator.py
summaries = "\n\n".join(
    f"## Trace {i+1}\n{r.summary}" for i, r in enumerate(reports) if r.summary
)
result = await agent.run(f"请交叉评审以下分析结论:\n{summaries}")
```

**现状**：ReviewAgent 只看到每个分析的前 200 字（通常是"问题概述"的前半段），无法做有效评审：
- 看不到根因分析的具体推理
- 看不到关键数据证据
- 看不到不同 trace 之间的指标对比
- 无法验证推理的合理性

**OpenClaw 对照**：
- 子 Agent 完成后通过结构化 `Announce` 消息反馈
- 消息包含任务结果的关键字段，不是简单的文本截断
- 编排器基于结构化数据做后续决策

**影响**：批量分析的交叉评审名存实亡。Review 的结论可能是空洞的"各分析结论基本一致"。

### P7 无反馈回路

**代码位置**：`orchestrator.py:130-131`、`orchestrator.py:563-571`

**现状**：分析完成后的反馈链条处处断裂：
- `raw_data/*.json` 落盘 → 永远不被 Agent 主动读取
- `quality_warnings` 仅打印到 stream → 不影响后续分析策略
- `_learn_package` 因 `plugin.py` 未传入 `package_db` → 默认路径不执行
- `_record_tokens` 只统计消耗量 → 不用于控制分析深度
- `tool_calls` 历史落盘后 → 不被分析用于改进未来的工具调用策略

**OpenClaw 对照**：
- `.learnings/` 记录运行时错误和经验
- 每日 23:30 晋升到 `MEMORY.md`
- Bootstrap Hook 在新 Session 启动时加载
- 形成完整的"产生 → 存储 → 检索 → 使用 → 更新"闭环

**影响**：系统永远不会从自身经验中学习。第 100 次分析和第 1 次分析的能力完全相同。

### 问题严重程度与改进方案映射

| 问题 | 严重度 | 解决方案 | 预期收益 |
|------|--------|---------|---------|
| P1 无记忆 | ⭐⭐⭐⭐⭐ | G1 + G2 | 历史经验注入，分析准确性逐步提升 |
| P2 过度压缩 | ⭐⭐⭐⭐ | G0 (Step 2) | 关键数据不丢失，细粒度归因 |
| P3 路由粗浅 | ⭐⭐⭐ | G0 (MainAgent 增强) | 路由准确，避免错误场景 |
| P4 无推理链 | ⭐⭐⭐⭐⭐ | G0 (Step 1) | 推理可控、可预测、可复现 |
| P5 无检查点 | ⭐⭐⭐ | G0 (Step 3) | token 节约，避免空转 |
| P6 Review 失效 | ⭐⭐⭐⭐ | G4 | 批量评审产生实际价值 |
| P7 无反馈 | ⭐⭐⭐⭐⭐ | G1 + G6 | 闭环形成，系统能自我进化 |

## 改进方案设计（G0-G6）

### G0 SubAgent 推理链重构

> **状态**：✅ 已实现（2026-04-09），详见 `specs/011-subagent-reasoning-chain/`

> **OpenClaw 原型**：`SOUL.md` 人格定义 + 结构化任务描述 + 会话级 Compaction（非单工具压缩）

**目标**：将 SubAgent 从"自由发挥的报告生成器"改造为"按推理链执行的分析师"。

**解决的问题**：P2（过度压缩）、P3（路由粗浅）、P4（无推理链）、P5（无检查点）

**设计分三步**：

#### Step 1: 统一分析流程 + 结构化推理 prompt

**流程架构**：所有分析（用户手动 + 自动抓取）走统一流程：

```
                       ┌── 用户手动: 用户意图 + trace 路径
触发入口 ──────────── ┤
                       └── 自动抓取: DB 预填 jank_count/process_name + 固定意图

                              ↓

编排器 Phase 0 ─── 意图路由（MainAgent）
                    输入: 意图 + trace overview + [DB 预填信息]
                    输出: AnalysisRouting(scene, process_name, ...)

                              ↓

编排器 Phase 1 ─── 场景感知预取
                    根据 scene 决定预取什么数据:
                    ├── jank: detect_jank → 卡顿帧窗口
                    ├── anr: analyze_anr → thread/binder/lock 概览
                    ├── startup: find_slices("ActivityStart") → 启动阶段
                    ├── cpu: analyze_dimension(cpu) → 频率/调度概览
                    └── general: trace_overview → 全面扫描
                    预取结果 → 写入 _analysis_cache + 注入 SubAgent prompt
                    (SubAgent 工具执行前先查缓存，避免重复查询 trace)

                              ↓

SubAgent Phase 2+ ── 深度分析 + 推理 + 报告
```

**自动抓取的唯一区别**：Phase 0 的输入更丰富（DB 已有 jank 和进程信息），不跳过任何步骤。

**SubAgent 推理链 prompt**（替代当前的"4 段格式要求"）：

```markdown
你是 Perfetto trace 分析专家。按以下推理链执行分析，每步必须有明确结论才能进入下一步。

## 已知信息
{编排器注入的预取结果，如 trace 概览、卡顿帧列表、目标进程等}

## Phase A — 根因排查（按优先级递减）
→ 必查: {scene_config.priority_dims}
→ 推荐: {scene_config.secondary_dims}
→ 辅助: {scene_config.optional_dims}（仅当前面维度未定位根因时）
→ **每个维度分析后立即判断**: 是否发现 severity=CRITICAL/HIGH 的问题？
→ **如果已找到 ≥2 个强根因证据，可跳过剩余低优先级维度**

## Phase B — 交叉验证
→ 检查根因之间的因果关系
  例: CPU 低频 → 主线程慢 → Binder 超时（是因果链而非独立根因）
→ 排除矛盾结论
→ 确定最终根因排序

## Phase C — 输出报告
每个根因 MUST 包含:
- 证据: 来自哪个工具、哪个指标、具体数值
- 推理: 为什么这个数据指向此根因
- 结论: 一句话定性
- 建议: 具体可操作的优化方案

## 行为约束
- 不要重复调用同一工具和相同参数
- 每个维度分析后立即给出该维度的判断，不要等所有维度分析完再统一判断
- 如果工具返回"无异常"，一句话记录后直接进入下一个维度
```

注意推理链中**不写具体工具调用次数限制**（弱模型会误解为硬限制，过早停止）。

**场景配置**（由编排器注入 prompt 中的 `{scene_config.*}` 占位符）：

```python
SCENE_CONFIG: dict[str, dict] = {
    "jank": {
        "priority_dims": ["cpu", "thread", "binder"],
        "secondary_dims": ["gpu", "sf", "io"],
        "optional_dims": ["gc", "input", "lock"],
    },
    "anr": {
        "priority_dims": ["thread", "binder", "lock"],
        "secondary_dims": ["cpu", "io"],
        "optional_dims": ["gc"],
    },
    "startup": {
        "priority_dims": ["cpu", "thread"],
        "secondary_dims": ["io", "binder"],
        "optional_dims": ["gc"],
    },
    "cpu": {
        "priority_dims": ["cpu"],
        "secondary_dims": ["thread"],
        "optional_dims": [],
    },
    "general": {
        "priority_dims": ["cpu", "thread", "binder", "gpu"],
        "secondary_dims": ["sf", "io", "gc"],
        "optional_dims": ["input", "lock"],
    },
}
```

#### Step 2: 结构化压缩（异常完整保留 + 正常精简）

替代当前固定 300 token 的一刀切截断策略。核心思想：**让引擎的 severity 判断驱动压缩策略**。

**当前问题**：

```python
# tools.py — 所有工具一律压缩到 300 token
compressed = compressor.compress_tool_output(tool_name, raw, 300)
```

LLM 只看到"部分核心频率被限制"，无法精确归因。

**改进方案**：

```python
def compress_structured(tool_name: str, raw: dict) -> str:
    """结构化压缩：异常完整保留，正常精简。"""
    parts = []

    # 1. 引擎标记的异常 — 完整保留（时间、数值、严重度）
    issues = raw.get("issues", [])
    for issue in issues:
        if issue.get("severity") in ("CRITICAL", "HIGH", "WARNING"):
            parts.append(f"- [{issue['severity']}] {issue['type']}: {issue['detail']}")

    # 2. 健康摘要 — 一句话
    health = raw.get("health_summary", {})
    if health:
        abnormal = {k: v for k, v in health.items() if v != "OK"}
        if abnormal:
            parts.append(f"- 异常维度: {abnormal}")
        normal_count = sum(1 for v in health.values() if v == "OK")
        if normal_count:
            parts.append(f"- 正常维度: {normal_count} 个，无异常")

    # 3. 关键指标 — 只保留极端值
    metrics = raw.get("key_metrics", {})
    if metrics:
        parts.append(f"- 关键指标: {_format_extremes(metrics)}")

    # 4. 引擎未标记 severity 的工具（如 pa_execute_sql）
    #    → 不做异常判断，按 token 预算截断
    if not issues and not health:
        return compressor.compress_tool_output(tool_name, raw, 500)

    return "\n".join(parts)
```

**异常判定规则**：
- 异常由**引擎层定义**（`cpu_analysis.py`、`gpu_analysis.py` 等已有 severity 计算）
- 压缩器**不做额外的异常判断**，只负责"引擎标为异常的 → 完整保留，其余 → 精简"
- `pa_execute_sql` 等返回原始数据的工具：不做异常判断，按 500 token 截断

**工具查询结果缓存**：

工具查询结果写入缓存，避免重复查询 trace：

```python
class PerfettoAnalysisService:
    def __init__(self):
        self._analysis_cache: dict[str, dict] = {}
        # key: f"{trace_path}:{dimension}:{process_name}"

    def analyze_dimensions(self, trace_path, process_name, dimensions, compact):
        cache_key = f"{trace_path}:{','.join(sorted(dimensions))}:{process_name}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]
        result = self._do_analyze(...)
        self._analysis_cache[cache_key] = result
        return result
```

缓存数据来源：
1. **Phase 1 预取**：编排器在预取阶段的工具调用结果直接写入缓存
2. **SubAgent 工具调用**：SubAgent 运行期间的工具查询结果实时写入

缓存命中时工具直接返回缓存数据（零 trace 查询开销）。缓存生命周期与单次分析会话一致，会话结束后释放。缓存结果同时为 G1（经验沉淀）提供数据源。

#### Step 3: 安全网 + 插桩观测（替代硬限制）

**设计理念**：借鉴 OpenClaw 的"引导收敛而非硬限制"思路，但不照搬其 Compaction 机制（因为我们是短会话场景）。

**OpenClaw 与我们的场景差异**：

| 维度 | OpenClaw | perfetto_analysis |
|------|----------|-------------------|
| 会话时长 | 小时/天 | 3-10 分钟 |
| Compaction 触发频率 | 频繁（长对话） | 极少（~7.5K token） |
| Compaction 成本 | 值得（后续节省大量 token） | 不值得（分析快完成了） |

**不直接采用 Compaction 的理由**：Compaction 需要额外 LLM 调用做"蒸馏"，在 3-10 分钟的短会话中性价比低。

**替代方案**：

1. **安全网**：`request_limit=50`，仅防止 LLM 失控（死循环调用），不作为行为引导
2. **推理链收敛引导**（写在 prompt 中，不写具体次数）：
   - "找到 ≥2 个强根因证据 → 跳过剩余低优先级维度"
   - "每个维度分析后立即判断是否发现高严重度问题"
   - 不写"建议 X 次工具调用"（弱模型会误解为硬限制，过早停止分析）
3. **插桩观测**：记录每次分析的工具调用和 token 消耗，积累样本后再决定是否需要场景级限制

**插桩数据模型**：

```python
analysis_telemetry = {
    "trace_id": str,
    "scene": str,
    "model_name": str,
    "tool_call_count": int,
    "tool_calls_detail": [
        {"tool": str, "args_hash": str, "tokens_in": int, "tokens_out": int, "elapsed_ms": int}
    ],
    "total_prompt_tokens": int,
    "total_completion_tokens": int,
    "conclusion_quality": list[str],   # quality_warnings
    "elapsed_sec": float,
    "created_at": str,
}
```

**建表 SQL**：

```sql
CREATE TABLE pa_telemetry (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id                 TEXT,                 -- 关联 pa_analysis_tasks.task_id
    trace_id                TEXT,
    scene                   TEXT,
    model_name              TEXT,
    tool_call_count         INTEGER,
    tool_calls_detail       TEXT,                 -- JSON: [{"tool","args_hash","tokens_in","tokens_out","elapsed_ms"}]
    total_prompt_tokens     INTEGER,
    total_completion_tokens INTEGER,
    conclusion_quality      TEXT,                 -- JSON: quality_warnings
    elapsed_sec             REAL,
    created_at              TEXT NOT NULL
);
```

插桩数据写入 DB，后续可分析：
- 不同场景的平均工具调用次数
- 哪些工具被反复调用（可能需要优化 prompt 或缓存）
- token 消耗分布
- 分析耗时与质量的关系

**工作量**：2 天（含插桩）

**与 OpenClaw 的差异**：
- OpenClaw 用 Compaction 做会话级 token 管理 → 我们不需要（短会话）
- OpenClaw 用 SOUL.md 引导行为 → 我们用推理链收敛引导
- OpenClaw 无 request_limit → 我们保留为安全网（50），不作为引导
- 共同理念：**引导收敛行为，而非硬限制调用次数**

### G1 分析经验自动沉淀 ✅ 已实现 (2026-04-09)

> **OpenClaw 原型**：`.learnings/` 目录 + 每日 23:30 晋升到 `MEMORY.md`

**目标**：每次分析完成后，自动从结构化输出中提取高价值经验写入数据库。

#### 前置条件：SubAgent 输出结构化

G1 依赖 SubAgent 输出 Pydantic 结构化数据（而非自由文本）。输出模型设计：

```python
from pydantic import BaseModel, Field

class RootCauseItem(BaseModel):
    """单个根因分析。"""
    tag: str                              # 根因标签: cpu_throttle, binder_ipc, gc_pause, ...
    severity: str                         # CRITICAL / HIGH / WARNING / INFO
    qualitative: str                      # 定性: "主线程在大核上被限频导致渲染超时"
    quantitative: dict = Field(default_factory=dict)  # 定量 (Optional): {"freq_khz": 1400000}
    evidence: str                         # 证据: 来自哪个工具、什么数据
    reasoning: str                        # 推理: 为什么这个数据指向此根因
    suggestion: str = ""                  # 优化建议 (Optional, 无法给出时留空)

class AnalysisOutput(BaseModel):
    """SubAgent 的结构化输出 — 同时服务于 HTML 报告和经验提取。"""

    # Section 1: 问题定义
    user_intent_summary: str              # 归纳后的用户问题描述（可能来自多轮碎片化描述）
    trace_info: str                       # trace 基本信息（时长、帧数、刷新率、进程）

    # Section 2: 分析摘要（G1 经验提取的数据来源）
    scene: str                            # 分析场景: jank/anr/memory/startup/cpu/general
    overall_conclusion: str               # 整体结论（一段话）
    root_causes: list[RootCauseItem] = Field(default_factory=list)  # 根因列表（按严重度排序，可为空）

    # Section 3: 详细分析报告
    detailed_report: str = ""             # 详细分析（Markdown 格式，含证据链）
```

**HTML 报告的三区块**（样式细节在实现阶段讨论）：

| 区块 | 数据来源 | 内容 |
|------|---------|------|
| Section 1 | `user_intent_summary` + `trace_info` | 用户问题归纳 + trace 概览 |
| Section 2 | `overall_conclusion` + `root_causes[]` | 定性定量摘要 + 根因表格 + 方案建议 |
| Section 3 | `detailed_report` | 详细分析叙述 + 可视化图表 + 原始日志（折叠） |

#### 设计

1. **触发时机**：`orchestrator._finalize` 阶段，同步提取（无额外 LLM 调用）
2. **提取方式**：从 SubAgent 的 `AnalysisOutput` 结构化字段直接读取
3. **存储位置**：复用 `perfetto_analysis.db`，新增 `pa_learnings` 表，与 `pa_analysis_tasks` 关联

**数据模型**：

```sql
CREATE TABLE pa_learnings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT,                    -- 关联 pa_analysis_tasks.task_id
    trace_id        TEXT NOT NULL,           -- trace 文件标识
    scene           TEXT NOT NULL,           -- 分析场景
    device_model    TEXT,                    -- 设备型号
    process_name    TEXT,                    -- 目标进程
    root_cause_tags TEXT NOT NULL,           -- 根因标签，逗号分隔
    insight         TEXT NOT NULL,           -- 整体结论（来自 overall_conclusion）
    key_metrics     TEXT,                    -- JSON: 各根因的定量数据
    confidence      REAL DEFAULT 0.5,        -- 置信度 [0,1]
    hit_count       INTEGER DEFAULT 0,       -- 被后续分析引用次数
    last_used       TEXT,                    -- 最后被引用时间
    created_at      TEXT NOT NULL,           -- 创建时间
    promoted        INTEGER DEFAULT 0,       -- 是否已晋升到 patterns/
    archived        INTEGER DEFAULT 0        -- 是否已归档（G3 软删除）
);
```

**提取逻辑**（`_extract_learnings`）：

```python
def _extract_learnings(output: AnalysisOutput, tool_cache: dict) -> dict:
    """从 SubAgent 的结构化输出中提取经验——无需额外 LLM 调用。"""
    return {
        "scene": output.scene,
        "root_cause_tags": ",".join(rc.tag for rc in output.root_causes),
        "insight": output.overall_conclusion[:500],
        "key_metrics": json.dumps({
            rc.tag: rc.quantitative
            for rc in output.root_causes
            if rc.quantitative
        }, ensure_ascii=False),
        "confidence": _calc_initial_confidence(output.root_causes),
    }

def _calc_initial_confidence(root_causes: list[RootCauseItem]) -> float:
    """基于根因的严重度和证据完整性计算初始置信度。"""
    if not root_causes:
        return 0.1
    severity_weights = {"CRITICAL": 0.9, "HIGH": 0.7, "WARNING": 0.5, "INFO": 0.3}
    max_severity = max(severity_weights.get(rc.severity, 0.3) for rc in root_causes)
    has_evidence = all(rc.evidence for rc in root_causes)
    return min(max_severity + (0.1 if has_evidence else 0), 1.0)
```

**降级兜底**：如果 SubAgent 无法生成完整的 `AnalysisOutput`（Pydantic 解析失败），降级处理：

```python
def _fallback_output(raw_text: str, scene: str) -> AnalysisOutput:
    """Pydantic 解析失败时的兜底输出。"""
    return AnalysisOutput(
        user_intent_summary="（结构化解析失败，以下为原始输出）",
        trace_info="",
        scene=scene,
        overall_conclusion=raw_text[:500],
        root_causes=[],
        detailed_report=raw_text,
    )
```

降级输出不触发 G1 经验提取（`root_causes` 为空），但仍生成 HTML 报告（Section 3 包含完整原始文本）。

**与 OpenClaw 的差异**：
- OpenClaw 用 LLM 提取 insights → 我们从**结构化输出直接读取**，零额外成本
- OpenClaw 用定时 Heartbeat 触发 → 我们用**事件驱动**（分析完成时），更贴合场景
- OpenClaw 的 learnings 是自由文本 → 我们的 learnings 来自 `AnalysisOutput` 的结构化字段，数据质量更高

### G2 相似案例注入 ✅ 已实现 (2026-04-13)

> **OpenClaw 原型**：`vector_similarity + bm25_score + time_decay` 混合检索 → 注入 prompt

**目标**：分析前自动检索历史相似案例，注入 SubAgent 上下文作为参考。

#### 分级检索策略（L1 标签匹配 → L2 向量搜索）

采用两级检索，优先精确匹配，无法命中时降级到语义搜索：

```
                   预取阶段的 issues[].type
                         │
                    ┌─────▼─────┐
             L1    │ SQL 标签    │ ← 精确、快速、零依赖
             检索  │ 交叉匹配    │
                    └─────┬─────┘
                          │
                    命中 ≥2 条？
                    ┌─────┴─────┐
                    │ 是         │ 否
                    ▼            ▼
              直接使用      ┌─────────┐
                           │ L2 向量  │ ← 语义召回、跨场景关联
                           │ 语义搜索 │
                           └─────────┘
```

**L1 — SQL 标签交叉匹配**（零依赖，优先执行）：

```sql
-- 第一优先级：完全匹配（同场景 + 同进程）
SELECT id, insight, root_cause_tags, key_metrics, confidence
FROM pa_learnings
WHERE scene = :scene AND process_name = :process_name
  AND promoted = 0 AND archived = 0
ORDER BY confidence DESC, hit_count DESC
LIMIT 2;

-- 第二优先级：根因标签交叉（不同进程但相似根因）
SELECT id, insight, root_cause_tags, key_metrics, confidence
FROM pa_learnings
WHERE scene = :scene
  AND id NOT IN (:already_found)
  AND promoted = 0 AND archived = 0
  AND EXISTS (
    SELECT 1 FROM (
      SELECT trim(value) AS tag
      FROM json_each('["' || replace(root_cause_tags, ',', '","') || '"]')
    ) WHERE tag IN (:prefetch_issue_tags)
  )
ORDER BY confidence DESC
LIMIT 1;
```

其中 `:prefetch_issue_tags` 来自 G0 编排器预取阶段已识别的引擎 issues 标签。

**L2 — 向量语义搜索**（L1 命中 < 2 条时触发）：

```python
from sqlite_vec import serialize_float32
import sentence_transformers

class LearningsSearcher:
    def __init__(self, db_path: str, model_name: str = "shibing624/text2vec-base-chinese"):
        self._embedder = sentence_transformers.SentenceTransformer(model_name)
        self._db = sqlite3.connect(db_path)
        self._db.enable_load_extension(True)
        self._db.load_extension("vec0")

    def semantic_search(self, query: str, exclude_ids: list[int], limit: int = 2) -> list[dict]:
        query_vec = self._embedder.encode(query)
        rows = self._db.execute("""
            SELECT l.id, l.insight, l.root_cause_tags, l.confidence,
                   vec_distance_cosine(e.embedding, :query_vec) AS distance
            FROM pa_learning_embeddings e
            JOIN pa_learnings l ON e.learning_id = l.id
            WHERE l.id NOT IN ({placeholders})
              AND l.promoted = 0 AND l.archived = 0
            ORDER BY distance ASC
            LIMIT :limit
        """, {...}).fetchall()
        return [dict(row) for row in rows]
```

**L2 的依赖**：
- `sentence-transformers` 包（embedding 生成）
- `sqlite-vec` 扩展（SQLite 向量搜索）
- 额外表 `pa_learning_embeddings(learning_id, embedding BLOB)`

**L2 作为可选增强**：如果 `sentence-transformers` 未安装，自动跳过 L2，仅使用 L1。

#### 注入位置

与 G0 编排器预取结果一起注入 SubAgent prompt 的"已知信息"段：

```markdown
## 已知信息

### Trace 概览
- 时长: 15.3s | 帧数: 920 | 刷新率: 120Hz | 目标进程: com.example.game

### 预检测结果
- 卡顿帧: 12 帧 (BigJank 3 帧)
- 最严重帧: ts=12.3s, 丢 8 帧, window=[12.1s, 12.5s]

### 历史分析参考（仅供参考，以当前 trace 数据为准）

#### 案例 1 (置信度 0.8, 命中 5 次)
- 场景: jank | 进程: com.example.game
- 根因: cpu_throttle, thermal
- 经验: SM8750 设备在高负载时大核频率被限制在 1.4GHz，与 thermal 节流相关
- 关键指标: {"max_freq_khz": 1400000, "throttle_ratio": 0.35}

#### 案例 2 (置信度 0.6, 命中 2 次, 语义召回)
- 场景: jank | 进程: com.another.game
- 根因: gpu_binderipc
- 经验: 游戏类进程 GPU DrawFrame 耗时异常，HWC binder 超时导致 SF 合成延迟
```

**token 预算**：≤500 token（约 3 条案例 × 150 字）。

#### 命中反馈闭环

分析完成后，从 `AnalysisOutput.root_causes` 的标签与注入案例的标签做交集检查：

```python
def _update_hit_counts(output: AnalysisOutput, injected_cases: list[dict]) -> None:
    """分析完成后，验证注入案例是否被采纳。"""
    result_tags = set(rc.tag for rc in output.root_causes)
    for case in injected_cases:
        case_tags = set(case["root_cause_tags"].split(","))
        if result_tags & case_tags:
            db.execute(
                "UPDATE pa_learnings SET hit_count = hit_count + 1, last_used = ? WHERE id = ?",
                (datetime.now().isoformat(), case["id"])
            )
```

**与 OpenClaw 的差异**：
- OpenClaw 用 `0.5*semantic + 0.3*bm25 + 0.2*time_decay` 单层混合 → 我们用**分级策略**（L1 精确优先，L2 语义兜底），更高效
- OpenClaw 始终执行语义搜索 → 我们的 L2 是**按需触发**（L1 不足时才用），降低延迟和依赖
- 后续演进：L1 和 L2 的结果可以用 OpenClaw 的时间衰减加权做最终排序

### G3 经验淘汰与晋升 ✅ 已实现 (2026-04-13)

> **OpenClaw 原型**：`memory_score = recency × importance × frequency` 评分 + Heartbeat/cron 定期 LLM 驱动晋升

**目标**：防止经验库膨胀，自动淘汰低价值条目，LLM 驱动高价值条目晋升。

#### 评分公式（直接采用 OpenClaw 方案）

```python
import math
from datetime import datetime

DECAY_FACTOR = 0.95  # OpenClaw 默认值，后续通过插桩数据调整

def memory_score(learning: dict, current_time: datetime | None = None) -> float:
    """OpenClaw 风格的记忆价值评估。"""
    current_time = current_time or datetime.now()
    last_access = learning.get("last_used") or learning["created_at"]
    if isinstance(last_access, str):
        last_access = datetime.fromisoformat(last_access)
    days_since = (current_time - last_access).days

    recency = DECAY_FACTOR ** days_since
    importance = learning["confidence"]
    frequency = math.log(learning["hit_count"] + 1)  # 自然对数

    return recency * importance * frequency
```

衰减因子 `DECAY_FACTOR` 和公式参数先用 OpenClaw 默认值，后续通过 G0 插桩数据验证和调整。

#### 淘汰策略

| 评分区间 | 操作 | 说明 |
|---------|------|------|
| `score < 0.05` | 软删除（`archived = 1`） | 不硬删，保留可追溯 |
| `0.05 ≤ score < 0.3` | 保留但降低优先级 | G2 检索时排在后面 |
| `score ≥ 0.3 且 hit_count ≥ 3` | 候选晋升 | 进入 LLM 评审 |

最低保留数量：至少保留 20 条经验（即使分数低），确保新系统有最基础的经验池。

#### LLM 驱动的晋升流程

对齐 OpenClaw 的 Heartbeat + cron 模式，由 LLM 而非人工执行经验评审：

```python
async def promote_learnings(llm_model: Any, db: sqlite3.Connection) -> dict:
    """LLM 驱动的经验晋升。"""
    # 应用层计算 memory_score（含 exp 运算，不适合纯 SQL）
    rows = db.execute("""
        SELECT id, scene, root_cause_tags, insight, key_metrics,
               confidence, hit_count, last_used, created_at
        FROM pa_learnings
        WHERE promoted = 0 AND archived = 0
          AND hit_count >= 3 AND confidence >= 0.6
    """).fetchall()

    if not rows:
        return {"promoted": 0, "merged": 0, "archived": 0}

    scored = [(row, memory_score(dict(row))) for row in rows]
    scored.sort(key=lambda x: x[1], reverse=True)
    candidates = [row for row, _ in scored[:10]]

    prompt = (
        "以下是 Perfetto 性能分析中积累的经验条目。请评估每条经验：\n"
        "1. 是否值得长期保留？（通用性、可复用性、跨设备/应用的适用性）\n"
        "2. 是否与其他条目重复或高度相似？如果是，指出合并对象\n"
        "3. 给出建议操作：promote（晋升为已验证经验）/ merge（合并到指定条目）/ keep（保持现状）/ archive（归档淘汰）\n\n"
        "输出 JSON 数组，每项包含 {id, action, merge_target_id?, reason}\n\n"
        f"{_format_candidates(candidates)}"
    )
    result = await llm_model.run(prompt)
    actions = _parse_promotion_result(result)

    stats = {"promoted": 0, "merged": 0, "archived": 0}
    for action in actions:
        if action["action"] == "promote":
            db.execute("UPDATE pa_learnings SET promoted = 1 WHERE id = ?", (action["id"],))
            stats["promoted"] += 1
        elif action["action"] == "merge":
            _merge_learnings(db, action["id"], action["merge_target_id"])
            stats["merged"] += 1
        elif action["action"] == "archive":
            db.execute("UPDATE pa_learnings SET archived = 1 WHERE id = ?", (action["id"],))
            stats["archived"] += 1
    db.commit()
    return stats
```

**晋升后的效果**：
- `promoted = 1` 的条目在 G2 注入时标注 `[已验证]`，权重更高
- 不写入静态 markdown 文件（避免 Git 提交依赖）
- 数据留在 DB 中，统一管理

#### 触发时机

| 触发条件 | 时机 | 说明 |
|---------|------|------|
| 自动 | 每累计 20 次分析后 | 后台自动执行，用户无感 |
| 手动 | CLI: `review-learnings` | 开发者按需触发 |
| GUI | "整理经验库"按钮 | 可选的 GUI 入口 |

#### 插桩

```python
promotion_telemetry = {
    "trigger": str,             # "auto_20" / "manual" / "gui"
    "candidates_count": int,
    "promoted_count": int,
    "merged_count": int,
    "archived_count": int,
    "llm_tokens_used": int,
    "elapsed_sec": float,
    "created_at": str,
}
```

**与 OpenClaw 的一致性**：
- 评分公式：直接采用 OpenClaw 的 `recency × importance × frequency`
- 晋升方式：LLM 驱动，对齐 OpenClaw 的 Heartbeat 机制
- 触发频率：按分析次数触发（事件驱动），适配我们的短会话场景
- 差异：OpenClaw 晋升到 MEMORY.md 文件 → 我们标记 DB 字段（更适合结构化查询）

### G4 Review 增强 ✅ 已实现 (2026-04-13)

> **OpenClaw 原型**：子 Agent 完成后的结构化 `Announce` 消息反馈机制

**目标**：让 ReviewAgent 基于结构化数据做有效评审，并为 G1 经验提供置信度校准。

#### Review 输入改造

基于 G1 引入的 `AnalysisOutput` 结构化模型，Review 的输入从 `summary[:200]` 改为完整结构化数据：

```python
async def _run_review(self, outputs: list[AnalysisOutput], on_stream) -> ReviewResult:
    review_input = "\n\n".join(
        f"## Trace {i+1}: {out.scene}\n"
        f"**结论**: {out.overall_conclusion}\n"
        f"**根因**:\n" + "\n".join(
            f"  - [{rc.severity}] {rc.tag}: {rc.qualitative} (证据: {rc.evidence[:100]})"
            for rc in out.root_causes
        )
        for i, out in enumerate(outputs)
    )
    agent = create_review_agent(self._get_model())
    result = await agent.run(f"请评审以下分析结论:\n\n{review_input}")
    return result
```

#### Review 输出结构化

```python
class ReviewResult(BaseModel):
    """ReviewAgent 的结构化评审结果。"""
    cross_consistency: str = ""           # 交叉一致性评价（仅批量同场景时有值）
    common_patterns: list[str] = []      # 共性问题
    contradictions: list[str] = []       # 矛盾点
    confidence_adjustments: list[dict] = []  # 置信度调整
    # 例: [{"trace_index": 0, "adjustment": +0.1, "reason": "证据充分且逻辑清晰"}]
    overall_assessment: str = ""         # 整体评审意见
```

置信度调整写回 `pa_learnings.confidence`，形成 G1 → G4 → G1 的反馈闭环。

#### 触发条件（场景感知）

**关键原则**：批量交叉 Review 仅在同场景 trace 间有意义。不同场景的 trace 做交叉对比会引入无意义的上下文污染。

```python
def _should_review(outputs: list[AnalysisOutput]) -> tuple[bool, str]:
    """判断是否需要触发 Review 以及 Review 类型。"""
    if len(outputs) > 1:
        scenes = set(out.scene for out in outputs)
        if len(scenes) == 1:
            return True, "cross_compare"  # 同场景，交叉对比
        else:
            # 不同场景：不做交叉对比，但每个低置信度的可做单独自检
            for out in outputs:
                if _needs_self_review(out):
                    return True, "individual_review"
            return False, ""

    # 单 trace 场景
    if len(outputs) == 1:
        return _needs_self_review(outputs[0]), "self_check"

    return False, ""

def _needs_self_review(output: AnalysisOutput) -> bool:
    """单个分析是否需要自检 Review。"""
    if len(output.root_causes) >= 3:
        return True  # 多根因，检查逻辑一致性
    avg_confidence = (
        sum(rc_confidence(rc) for rc in output.root_causes) / len(output.root_causes)
        if output.root_causes else 0
    )
    if avg_confidence < 0.5:
        return True  # 低置信度，二次确认
    return False
```

| 场景 | 触发？ | Review 类型 | 说明 |
|------|--------|------------|------|
| 批量 + 同 scene | ✅ | `cross_compare` | 交叉对比共性问题和矛盾 |
| 批量 + 不同 scene | ⚠️ 仅低置信度的 | `individual_review` | 逐个自检，不做跨场景对比 |
| 单 trace + 根因 ≥3 | ✅ | `self_check` | 检查根因间逻辑一致性 |
| 单 trace + 低置信度 | ✅ | `self_check` | 二次确认分析可靠性 |
| 单 trace + 高置信度 | ❌ | — | 不需要额外验证 |

**与 OpenClaw 的差异**：
- OpenClaw 的 Announce 是通用消息总线 → 我们的 Review 是专用评审 Agent，职责更聚焦
- OpenClaw 无场景感知的 Review 触发 → 我们根据场景一致性和置信度动态决定

### G5 Skill 知识层级应用 ✅ 已实现 (2026-04-13)

> **OpenClaw 原型**：按需分段加载（`read_file` 工具），避免全量注入

**目标**：复用项目 Skill 的渐进式披露层级（L0-L3），让 SubAgent 通过工具按需拉取 Skill 中的知识资产（patterns、SQL 模板、案例），精简 SOP 全文注入，释放上下文空间。

#### 前提：推理链 vs SOP 的职责分离

G0 引入推理链后，SOP 的部分内容变得冗余：

| 内容类型 | SOP 占比 | 推理链已覆盖？ | 处理 |
|---------|---------|--------------|------|
| 分析步骤顺序 | ~20% | ✅ Phase A/B/C | 删除 |
| 维度优先级 | ~10% | ✅ SCENE_CONFIG | 删除 |
| 判断条件和阈值 | ~30% | ❌ | 保留（核心价值） |
| 深度分析指引 | ~30% | ❌ | 拆到 detail 文件 |
| 常见模式索引 | ~10% | ⚠️ 部分与 patterns/ 重叠 | 精简为引用链接 |

#### 复用 Skill 知识层级（不创建新文件）

项目的 Skill 系统（`skills/perfetto-analysis/`）已经实现了渐进式披露的知识层级：

```
skills/perfetto-analysis/
  ├── SKILL.md                         ← L0: 入口和路由（Cursor IDE 用）
  ├── sop/*.md                         ← L1: 分析流程（当前全文注入 SubAgent）
  ├── patterns/root-cause-patterns.md  ← L2: 根因模式库（当前未接入 SubAgent）
  ├── sql-patterns.md                  ← L2: SQL 模板（当前未接入 SubAgent）
  ├── cases/                           ← L3: 案例库（当前未接入 SubAgent）
  └── tool-catalog.md                  ← L2: 工具参考（当前未接入 SubAgent）
```

**当前问题**：`load_sop()` 只读取 L1 全文，L2/L3 的知识资产在 SubAgent 运行时完全不可访问。Skill 的渐进式披露设计只在 Cursor IDE 层面生效，SubAgent 绕过了它。

**改造方案**：不创建新的 `-detail.md` 文件，而是让 SubAgent 通过工具复用 Skill 现有的 L2/L3 资产：

| 层级 | 注入方式 | 内容 |
|------|---------|------|
| L1 | instructions（精简版 SOP） | 判断条件 + 阈值 + **引用指针** |
| L2 | `pa_read_knowledge` 工具按需拉取 | patterns/ + sql-patterns.md |
| L3 | `pa_read_knowledge` 工具按需拉取 | cases/ |

精简版 SOP 中的引用指针对齐 Skill 结构：

```markdown
# 卡顿分析 — 场景特化规则

## 关键判断条件
- Running 高 + 小核/低频 → 调度策略 (→ patterns/root-cause-patterns.md#cpu-调度抢占)
- Running 高 + 大核/满频 → 应用代码热点 (查 hotspot)
- Runnable 高 → CPU 争抢 (查全局 CPU 使用率)
- D-State > 5ms → IO 阻塞 (→ sop/io-block-analysis.md)
- handleMessageRefresh 异常 → SF/HWC (→ patterns/root-cause-patterns.md#hwc-binder-超时)

## 阈值参考
- 调度延迟 > 1ms → WARNING | > 5ms → CRITICAL
- Binder 调用 > 50ms → WARNING
- GC 停顿 > 10ms → WARNING
- CPU 频率查询方法 → sql-patterns.md#cpu-频率查询

## 需要深入时
调用 pa_read_knowledge("资源路径") 获取详细分析指引或 SQL 模板。
```

#### 按需加载工具

新增第 10 个 pa_* 工具（替代原先设计的 `pa_read_sop_section`）：

```python
_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills" / "perfetto-analysis"

def pa_read_knowledge(resource_path: str) -> ToolReturn:
    """两级加载 Perfetto 分析知识库资源。

    **Level 1 — 目录概览**（不带锚点时）：
    返回文件的章节目录 + 每章节一句话摘要（~200 token），
    SubAgent 据此决定是否需要深入某个章节。

    **Level 2 — 章节详情**（带锚点时）：
    返回指定章节的完整内容（~200-400 token）。

    Args:
        resource_path: 相对于 skills/perfetto-analysis/ 的路径
            Level 1: "patterns/root-cause-patterns.md"         → 返回目录概览
            Level 2: "patterns/root-cause-patterns.md#cpu-调度抢占" → 返回该章节
    """
    path_part, _, anchor = resource_path.partition("#")
    full_path = _SKILLS_DIR / path_part

    if not full_path.exists():
        return _make_error_return("pa_read_knowledge", f"资源不存在: {path_part}")
    if not full_path.is_relative_to(_SKILLS_DIR):
        return _make_error_return("pa_read_knowledge", "路径越界")

    content = full_path.read_text(encoding="utf-8")

    if anchor:
        # Level 2: 返回指定章节完整内容
        section = _extract_section_by_anchor(content, anchor)
        if not section:
            return _make_error_return("pa_read_knowledge", f"锚点不存在: #{anchor}")
        return ToolReturn(
            return_value=section[:2000],
            metadata={"resource_path": resource_path, "level": 2,
                       "tool_name": "pa_read_knowledge"},
        )
    else:
        # Level 1: 返回目录概览（章节标题 + 首行摘要）
        toc = _build_toc_summary(content)
        return ToolReturn(
            return_value=toc,
            metadata={"resource_path": resource_path, "level": 1,
                       "tool_name": "pa_read_knowledge",
                       "hint": "使用 #锚点 获取具体章节详情"},
        )


def _build_toc_summary(content: str) -> str:
    """从 Markdown 内容提取章节目录 + 每章节首句摘要。"""
    lines = content.split("\n")
    toc_parts = []
    current_heading = None
    first_line_after = None

    for line in lines:
        if line.startswith("## ") or line.startswith("### "):
            if current_heading and first_line_after:
                toc_parts.append(f"{current_heading} — {first_line_after}")
            elif current_heading:
                toc_parts.append(current_heading)
            current_heading = line.strip()
            first_line_after = None
        elif current_heading and not first_line_after and line.strip():
            first_line_after = line.strip()[:80]

    if current_heading:
        if first_line_after:
            toc_parts.append(f"{current_heading} — {first_line_after}")
        else:
            toc_parts.append(current_heading)

    return "\n".join(toc_parts)
```

#### 预期 token 收益

```
改造前: SOP ~2000 token（全文注入）+ patterns/sql-patterns 不可访问
改造后: SOP ~800 token（精简版）+ 两级按需加载：
  Level 1 — 目录概览: ~200 token（SubAgent 浏览可用知识）
  Level 2 — 章节详情: ~200-400 token/次（仅拉取需要的章节）

释放空间: ~800 token → G2 案例注入 (~500) + 工具返回值空间
额外收益: patterns/sql-patterns/cases 首次对 SubAgent 可用
上下文效率: 两级加载避免一次性灌入大段无关知识
```

#### 改造范围

| 工作项 | 说明 |
|-------|------|
| 精简 9 个 SOP 文件 | 删除与推理链重复的步骤/优先级，保留判断条件和阈值 |
| 新增 `pa_read_knowledge` 工具 | 在 tools.py 中实现，注册到 SubAgent |
| 确保 patterns/sql-patterns 的锚点可用 | 检查并补充缺失的 H2/H3 锚点 |
| 不创建新文件 | 复用 Skill 现有结构 |

**与 OpenClaw 的差异**：
- OpenClaw 通过 `read_file` 通用工具读任意文件 → 我们用 `pa_read_knowledge` 限定在 Skill 目录内，更安全
- OpenClaw 无结构化知识层级 → 我们复用 Skill 的 L0/L1/L2/L3 层级，Cursor IDE 和 SubAgent 共享同一知识源

### G6 接通 package_db 学习链 ✅ 已完成

> **OpenClaw 原型**：无直接对应，这是本项目已有设计的修复

**目标**：修复 `PackageMappingDB` 在默认插件路径下未接线的问题。

**修改文件**：`src/plugin.py`

```python
from .agent.package_db import PackageMappingDB

package_db = PackageMappingDB(data_dir / "package_mappings.db")
orchestrator = AnalysisOrchestrator(
    llm_manager=llm_manager,
    pa_service=self._service,
    package_db=package_db,
)
context["pa_package_db"] = package_db
```

**完成日期**：2026-04-09

## 优先级与依赖关系

```
                    ┌─── G6 (接线修复, 0.5天) ─── 独立，立即可做
                    │
                    ├─── G0 (推理链重构, 2天) ─── 独立，最高优先级
阶段 0（基础）     ─┤                              解决 P2/P3/P4/P5
                    └─── G4 (Review增强, 1天) ───── 独立，解决 P6

                    ┌─── G1 (经验沉淀, 2天) ─┐
阶段 1（积累）     ─┤                         │     解决 P1/P7
                    └─── G5 (Skill知识层级, 1.5天) ─┤

阶段 2（闭环）     ─── G2 (案例注入, 1天) ───┤     依赖 G1 + G5 释放的 token 空间

阶段 3（演进）     ─── G3 (淘汰晋升, 1天) ───┘     依赖 G1+G2 产生足够数据
```

**建议执行顺序**：

1. **立即**：G6（接通 package_db，半天）
2. **优先**：G0（推理链重构，2 天）— 这是分析准确性的基础
3. **随后**：G4（Review 增强，1 天）+ G1（经验沉淀，2 天）
4. **接着**：G5（Skill 知识层级，1.5 天）+ G2（案例注入，1 天）
5. **最后**：G3（淘汰晋升，1 天）— 需要足够的分析数据验证评分公式

**预计总工作量**：~9 天

### 问题与方案交叉引用

| 问题 | 解决方案 | 阶段 |
|------|---------|------|
| P1 无记忆 | G1 + G2 | 阶段 1-2 |
| P2 过度压缩 | G0 Step 2 | 阶段 0 |
| P3 路由粗浅 | G0 MainAgent 增强 | 阶段 0 |
| P4 无推理链 | G0 Step 1 | 阶段 0 |
| P5 无检查点 | G0 Step 3 | 阶段 0 |
| P6 Review 失效 | G4 | 阶段 0 |
| P7 无反馈 | G1 + G6 | 阶段 0-1 |

## 参考资料

- [OpenClaw GitHub](https://github.com/openclaw/openclaw) — 项目主页
- [OpenClaw 记忆系统设计架构的思考](https://cloud.tencent.com/developer/article/2648358) — 腾讯云开发者社区
- [OpenClaw 多智能体系统深度技术解析](https://zhuanlan.zhihu.com/p/2006906353336218607) — 知乎专栏
- [OpenClaw Design Patterns: Orchestration Patterns](https://kenhuangus.substack.com/p/openclaw-design-patterns-part-3-of) — Substack
- [OpenClaw 多 Agents 分工协作教程](https://cloud.tencent.com/developer/article/2638746) — 腾讯云开发者社区
- [2026.4.10 Active Memory 讨论](https://www.reddit.com/r/openclaw/comments/1sidy98/) — Reddit
- [AI Agent 为什么会越用越懂你](https://www.fanyamin.com/2026-04-01-openclaw-agent-self-evolution.html) — 博客
