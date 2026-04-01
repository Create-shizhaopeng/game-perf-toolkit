# SmartPerfetto 对比审查 — 可借鉴改进点

**来源文章**: SmartPerfetto AI Agent 的 Harness Engineering 实战分享
**审查时间**: 2026-03-31
**当前状态**: 待后续迭代评估

## 目录

- [背景](#背景)
- [对比分析](#对比分析)
  - [场景分类 Scene Classification](#场景分类-scene-classification)
  - [Artifact Store 工具结果压缩](#artifact-store-工具结果压缩)
  - [三层验证 Three-Layer Verification](#三层验证-three-layer-verification)
  - [YAML Skill 声明式 SQL](#yaml-skill-声明式-sql)
  - [SQL 纠错学习](#sql-纠错学习)
  - [工具结果分层展示](#工具结果分层展示)
- [优先级评估](#优先级评估)
- [独立产物知识管理架构（待实现）](#独立产物知识管理架构待实现)
  - [知识资产双重用途](#知识资产双重用途)
  - [待实现工作](#待实现工作)
- [与现有架构的兼容性](#与现有架构的兼容性)

## 背景

SmartPerfetto 是一个独立的 AI Agent 产品（Perfetto UI 插件），使用 Claude Agent SDK + MCP 直接调用 trace_processor。其架构演进经历了从固定流水线到 Agent 自主推理的过程，积累了场景分类、数据压缩、质量验证等关键工程决策。

我们的 perfetto_analysis 模块是 Cursor IDE 内的插件模块，Agent 由 Cursor LLM 承担，通过 agent_tools 调用原子工具集。架构差异决定了并非所有 SmartPerfetto 的设计都直接适用，但其核心理念值得借鉴。

## 对比分析

### 场景分类 Scene Classification

| 维度 | SmartPerfetto | 我们的模块 |
|------|--------------|-----------|
| 实现 | 关键词匹配 + 优先级排序，<1ms | `general-analysis.md` SOP 文档指引 |
| 效果 | System Prompt 15000→4500 tokens | SOP 按场景路由到对应分析文档 |
| 元数据 | `.strategy.md` frontmatter (keywords/priority) | SOP 中自然语言描述关键词 |

**改进方向**:
- SOP 的 YAML frontmatter 中加入结构化 `keywords`、`priority`、`compound_patterns`
- Agent 可根据元数据精确匹配场景，减少误路由
- 示例: jank-analysis.md 的 frontmatter 加入 `keywords: [卡顿, jank, 掉帧, fps, 帧率]`

### Artifact Store 工具结果压缩

| 维度 | SmartPerfetto | 我们的模块 |
|------|--------------|-----------|
| 粒度 | 每个 Skill 结果压缩到 ~440 tokens | 仅最终 CompressedSummary |
| 按需获取 | `fetch_artifact(id, 'rows', offset, limit)` 分页 | 无中间结果缓存 |
| token 节省 | 每个 Skill 从 ~3000→~440 tokens | 原子工具返回全量数据 |

**改进方向**:
- 原子工具（`analyze_dimension`、`detect_jank_frames`）增加 `compact=True` 参数
- compact 模式返回摘要（关键指标 + 行数 + 样本），全量数据可选获取
- 减少 Agent 上下文开销，提升推理聚焦度
- SmartPerfetto 的经验: "数据越多，Claude 的输出质量反而越差"

### 三层验证 Three-Layer Verification

| 维度 | SmartPerfetto | 我们的模块 |
|------|--------------|-----------|
| Layer 1 | 启发式正则匹配已知误判模式 | 无 |
| Layer 2 | Plan 遵从检查 | AnalysisChainStep 可回溯 |
| Layer 3 | 独立模型审查 (Haiku) | 无 |
| 误判率 | 上线 18 天后 ~30%，验证后显著降低 | 未统计 |

**改进方向**:
- 在 SOP 中加入"已知误判模式"章节（启发式检查清单）
  - VSync 对齐偏移 ≤±0.5ms 不算异常
  - Buffer Stuffing 默认不计入 App 侧掉帧
  - 单帧异常不构成模式，需确认重复性
  - CPU 小核上运行不一定是降频，需关联 governor 状态
- Agent 完成分析后自查结论是否命中已知误判模式
- 持续积累: 每次发现新的误判，更新 SOP 的误判模式清单

### YAML Skill 声明式 SQL

| 维度 | SmartPerfetto | 我们的模块 |
|------|--------------|-----------|
| 数量 | 158 个 YAML Skill | 引擎固定 SQL + MCP 工具 |
| SQL 来源 | 预定义参数化 SQL | 引擎内部固定 / MCP 内部执行 |
| 可回归测试 | 6 条 trace 全通过 | pytest 41 个 mock 测试 |

**评估**: 当前混合架构（引擎 + MCP）已覆盖此能力。引擎端 SQL 固定不变；MCP 端由 Perfetto MCP Server 管理 SQL。不需要额外的 YAML Skill 层，但 `execute_sql` 工具允许 Agent 按需编写 SQL，可考虑在 SOP 中提供常用查询模板。

### SQL 纠错学习

| 维度 | SmartPerfetto | 我们的模块 |
|------|--------------|-----------|
| 记录 | error→fix pairs 持久化 | 无 |
| 注入 | 最近 10 条加载到 System Prompt | 无 |
| TTL | 30 天过期 | N/A |

**改进方向**:
- 当 MCP 实际接入后，收集 `execute_sql` 工具的常见错误
- 在 SOP 中维护 "常见 SQL 错误" 章节
- 示例: Perfetto 的 `slice` 表没有 `utid` 列，需要通过 `thread_track` 中间表关联

### 工具结果分层展示

| 维度 | SmartPerfetto | 我们的模块 |
|------|--------------|-----------|
| 层级 | summary→key→detail→hidden 四级 | DimensionResult.data 扁平 dict |
| 前端 | DataEnvelope schema-driven 渲染 | Agent 直接读取 dict |

**改进方向**:
- `DimensionResult.data` 约定分层键: `summary`（一行摘要）、`key_findings`（关键发现）、`detail`（完整数据）
- Agent 首先读取 `summary` 和 `key_findings` 做判断，需要时再读 `detail`
- 与 compact 模式配合: compact 只返回 summary + key_findings

## 优先级评估

| 改进项 | 影响 | 复杂度 | 建议优先级 |
|--------|------|--------|-----------|
| SOP 结构化元数据 | 中 | 低 | P2 — 仅修改 SOP 文档 |
| 已知误判模式清单 | 高 | 低 | P1 — 直接提升分析质量 |
| 原子工具 compact 模式 | 高 | 中 | P1 — 减少 Agent 上下文开销 |
| DimensionResult 分层 | 中 | 中 | P2 — 需要修改数据模型 |
| SQL 常见错误收集 | 低 | 低 | P3 — 依赖 MCP 实际接入 |
| 独立模型审查 | 中 | 高 | P3 — 需要额外 LLM 调用 |

## 独立产物知识管理架构（待实现）

编译为独立产物后，Cursor IDE 的 Skill 触发、AGENTS.md 注入、MCP 协议均不可用。
需要 `agent_chat` 模块替代 Cursor LLM 的编排角色。

### 知识资产双重用途

| 资产 | Cursor IDE 中 | 独立产物中 |
|------|--------------|-----------|
| `tool-catalog.md` | Agent 阅读理解工具能力 | 转换为 function calling schema |
| `sop/*.md` | Skill 引导分析流程 | agent_chat 系统提示 / RAG |
| `patterns/*.md` | Agent 查阅已知根因 | RAG 检索 / few-shot |
| `cases/*.md` | Agent 参考历史案例 | RAG 参考资料 |
| 引擎能力 | 通过 `pa_*` CLI 调用 | 直接 Python API 调用 |
| MCP 工具 | 通过 Cursor MCP 协议 | 不可用，降级到引擎 |

### 待实现工作

1. `tool-catalog.md` → OpenAI/Anthropic function calling schema 转换脚本
2. `agent_chat` 模块集成 SOP/patterns 的知识加载器
3. 引擎 Python API 直接调用接口（绕过 CLI）
4. MCP 不可用时的完全引擎降级路径
5. 引擎 CLI 输出改进：当检测到 `refresh_rate_switches` 时，在 JSON 输出中增加混合刷新率提示（如 `"mixed_refresh_rates": true, "segments": [{"hz": 120, "duration_s": 1.0}, {"hz": 30, "duration_s": 3.3}]`），避免单一 `inferred_refresh_rate_hz` 造成误解
6. Agent 辅助数据准备脚本：封装 Skill 分析中的重复性数据计算（线程状态分布汇总、CPU 频率数据查询与格式化、时间戳转换、VSync 间隔分布统计），减少 LLM 内联计算错误风险。注意：**决策逻辑不脚本化**，Skill 中的决策树保持为 LLM 推理指南，脚本只提供格式化好的数据输入

## 与现有架构的兼容性

1. **SOP 改进项**（元数据、误判模式、SQL 错误）只需修改文档，零代码改动，完全兼容
2. **compact 模式**需要修改 `AnalysisToolkit` 和 `DimensionResult`，但是向后兼容（默认 compact=False）
3. **分层键约定**需要修改引擎分析器的输出格式和 `DimensionResult` 模型，影响范围较大
4. **三层验证**中的 Layer 1（启发式检查）可以作为 SOP 内容零代码实现；Layer 3（独立模型审查）需要额外基础设施
