## Context

perfetto_analysis 模块当前有 14 个 pa_* Agent 工具，SQL 逻辑硬编码在 service.py 和 analysis_toolkit.py 中。同时，仓库内 `skills/smart-perfetto/` 有 220+ YAML 技能文件（来自 SmartPerfetto 项目），包含精心设计的 SQL、诊断规则、阈值评估和供应商覆盖，但 Agent 无法使用这些知识。

当前架构问题：
1. Agent 只能通过 14 个固定工具调用，分析流程不可组合
2. SQL 分散在 Python 代码中，无法复用、无法跨项目迁移
3. smart-perfetto YAML 知识库与 pa_* 工具断裂，两套体系互不相通
4. Skill 只有 SKILL.md 文档，无执行能力

## Goals / Non-Goals

**Goals:**
- Agent 通过单一工具 `pa_execute_sql` + YAML 技能库获得完整的 Perfetto 分析能力
- SKILL.md 成为 Agent 的操作手册，通过渐进式披露引导 Agent 找到正确的 YAML 技能
- smart-perfetto 的 220+ YAML 技能成为 perfetto-analysis Skill 的核心知识资产
- Skill 完全可迁移——不依赖框架内部实现，只依赖 `perfetto` Python 包

**Non-Goals:**
- 不实现 Python SkillRunner 引擎——Agent 自己编排执行步骤
- 不修改框架层 SkillRegistry 的数据模型——保持当前的平面注册
- 不实现 SmartPerfetto 的跨域专家对话协议——超出当前范围
- 不实现 SmartPerfetto 的 RAG/基线/案例库——超出当前范围
- 不修改 agent_chat 模块的 SkillsManager——两套 Skill 系统暂不统一

## Decisions

### D1: Agent 执行模型 — Agent 自编排

**决策**: Agent 读取 SKILL.md 索引→读取对应 YAML→通过 `pa_execute_sql` 执行 SQL→拿到结果→按模板生成报告。Agent 自己是编排者。

**替代方案**:
- Python SkillRunner 引擎（SmartPerfetto 方案）：自动执行 YAML 中的所有 steps。被否决，因为 Agent 自编排更灵活，可根据中间结果调整分析路径，且不需要额外实现和维护引擎。

**理由**: Agent 具备理解能力，读完 YAML 步骤后能自主决定执行顺序和参数替换。不需要硬编码执行流程。

### D2: 工具收拢 — 仅保留 pa_execute_sql

**决策**: 移除全部 14 个 pa_* 工具，仅保留 `pa_execute_sql(trace_path, sql)` 作为 Agent 的唯一执行通道。

**替代方案**:
- 保留高频工具 (pa_trace_overview, pa_detect_jank) + pa_execute_sql：被否决，因为这些工具的 SQL 可以直接放入 atomic YAML，Agent 通过 pa_execute_sql 执行。保留它们只是增加了维护成本。

**理由**: 一个工具 + YAML 知识库 = 完整分析能力。工具数量最小化，知识最大复用。

### D3: YAML 条件表达式 — 简化解析器

**决策**: 实现一个简化的 Python 表达式解析器，只支持属性访问、比较、逻辑运算，不支持 SmartPerfetto 中的 `?.`、`=>`、`Array.find()` 等 JS 语法。YAML 中的诊断规则条件由 Agent 自行解读和判断。

**替代方案**:
- eval() + JS→Python 转换：安全风险高，维护成本大
- 直接用 Python 语法：破坏与 SmartPerfetto YAML 的兼容性

**理由**: Agent 自编排模型下，diagnostic rules 由 Agent 读取并自行判断，不需要 Python 引擎解析条件表达式。解析器只需处理 SQL 中的 `${variable}` 替换。

### D4: YAML 文件迁移 — 分批迁移

**决策**: 按 P1→P4 四批迁移，每批有明确的验证目标。

| 批次 | 内容 | 验证目标 |
|------|------|---------|
| P1 | atomic (110+) + fragments (3) + SKILL.md 重写 + pa_execute_sql 实现 | Agent 能通过索引找到 atomic 技能，通过 pa_execute_sql 执行 SQL |
| P2 | composite (28+) | Agent 能按 composite 步骤编排多步分析 |
| P3 | pipelines (31) + vendors (8) | 管线检测 + 供应商适配可用 |
| P4 | modules (9+) + deep (2) | 跨域专家对话可用 |

### D5: SKILL.md 渐进式披露结构

**决策**: SKILL.md 实现三级渐进式披露：

- Level 0 (SKILL.md): 能力概览 + 场景索引表（问题→YAML 路径）
- Level 1 (composite YAML): 执行流程（步骤顺序、参数传递、诊断规则）
- Level 2 (atomic YAML): 具体 SQL 查询 + 返回数据结构

Agent 按需加载，避免一次性加载 220+ 文件的内容。

### D6: 目录结构

**决策**: 统一在 `skills/perfetto-analysis/` 下，替代当前的两个独立 Skill (perfetto-analysis + smart-perfetto)。

```
modules/perfetto_analysis/skills/perfetto-analysis/
├── SKILL.md              # Level 0: 能力概览 + 场景索引
├── tool-catalog.md       # pa_execute_sql 参数和返回结构详解
├── report-templates.md   # 报告生成模板
├── composite/            # Level 1: 组合技能
├── atomic/               # Level 2: 原子技能
├── deep/                 # 深度分析
├── modules/              # 跨域专家
├── pipelines/            # 管线检测
├── vendors/              # 供应商覆盖
└── fragments/            # 共享 SQL CTE
```

## Risks / Trade-offs

### [Agent 自编排可靠性] → SKILL.md 和 YAML 足够精确

Agent 自编排依赖 LLM 的理解和推理能力。如果 SKILL.md 索引不精确或 YAML 中的 SQL 有误，Agent 可能执行错误的查询。

**缓解**: SKILL.md 索引表必须精确到参数级别，YAML 中的 SQL 必须经过验证。P1 批次完成后做端到端验证。

### [YAML 迁移的 JS→Python 兼容性] → 逐步处理

SmartPerfetto 的 YAML 使用 JS 表达式（`?.`、`=>`、`Array.find()`），在 Agent 自编排模型下由 Agent 解读而非 Python 解析，但 YAML 文件中的 `${variable}` 替换仍需处理。

**缓解**: ${variable} 替换逻辑在 `pa_execute_sql` 的参数预处理中实现，不需要完整的表达式解析器。

### [220+ YAML 文件体积] → 渐进式披露

一次性加载所有 YAML 内容会超出 Agent 上下文限制。

**缓解**: SKILL.md 只提供索引，Agent 按需读取具体 YAML 文件。

### [现有 pa_* 工具用户迁移] → 无需迁移

当前 pa_* 工具仅 Agent 使用，无外部 API 消费者。移除后无需迁移。

## Open Questions

1. `pa_execute_sql` 是否需要支持 SQL 片段注入（将 fragments/*.sql 中的 CTE 自动拼接到用户 SQL 前）？还是由 Agent 自己组合？
2. composite YAML 中的 `type: skill` 步骤引用其他 YAML，Agent 如何解析这些引用？是在 SKILL.md 中说明还是在 YAML 中保持引用语法？
3. 供应商覆盖 (vendors/) 如何让 Agent 使用？是在 composite YAML 中通过 condition 自动应用，还是在 SKILL.md 中单独列出供应商相关的索引？
