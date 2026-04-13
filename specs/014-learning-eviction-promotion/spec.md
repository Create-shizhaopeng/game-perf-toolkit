# Feature Specification: 经验淘汰与晋升 (G3)

**Feature Branch**: `014-learning-eviction-promotion`
**Created**: 2026-04-09
**Status**: Draft
**Input**: G3 经验淘汰与晋升 — 基于 OpenClaw memory_score 公式实现记忆价值评估、自动淘汰低价值经验、LLM 驱动高价值经验晋升

## 目录

- [User Scenarios & Testing](#user-scenarios--testing)
  - [User Story 1 - 自动淘汰低价值经验](#user-story-1---自动淘汰低价值经验-priority-p1)
  - [User Story 2 - LLM 驱动经验晋升](#user-story-2---llm-驱动经验晋升-priority-p2)
  - [User Story 3 - 手动触发经验整理](#user-story-3---手动触发经验整理-priority-p3)
  - [Edge Cases](#edge-cases)
- [Requirements](#requirements)
  - [Functional Requirements](#functional-requirements)
  - [Key Entities](#key-entities)
- [Success Criteria](#success-criteria)
- [Clarifications](#clarifications)
- [Assumptions](#assumptions)
- [Constraints](#constraints)

## User Scenarios & Testing

### User Story 1 - 自动淘汰低价值经验 (Priority: P1)

随着分析次数增多，`pa_learnings` 表不断膨胀。系统自动评估每条经验的价值分数，将长期未被命中、置信度低的条目标记为归档，防止检索结果被低质量经验稀释。

**Why this priority**: 经验库膨胀直接影响 G2 检索质量和性能，是最核心的需求。

**Independent Test**: 插入若干条老旧、未命中的经验记录，触发淘汰后确认 `archived = 1` 且检索不再返回这些条目。

**Acceptance Scenarios**:

1. **Given** `pa_learnings` 中有 50 条记录，其中 10 条创建于 30 天前且 `hit_count = 0`，**When** 系统触发淘汰流程，**Then** 这些低分条目被标记 `archived = 1`。
2. **Given** 淘汰后剩余未归档条目不足 20 条，**When** 系统执行淘汰，**Then** 保留分数最高的 20 条，不再继续归档。
3. **Given** 一条记录 `archived = 1`，**When** G2 检索触发，**Then** 该记录不出现在检索结果中。

---

### User Story 2 - LLM 驱动经验晋升 (Priority: P2)

高频命中、高置信度的经验条目经 LLM 评审后晋升为"已验证"状态，在后续分析中获得更高权重。LLM 还负责识别重复条目并合并。

**Why this priority**: 晋升机制提升经验质量上限，使高价值经验在 G2 注入时被优先参考。

**Independent Test**: 准备若干 `hit_count ≥ 3` 且 `confidence ≥ 0.6` 的候选条目，触发 LLM 晋升后确认 `promoted = 1` 状态变更和重复条目合并。

**Acceptance Scenarios**:

1. **Given** 5 条候选经验满足晋升门槛，**When** LLM 评审返回 `promote` 动作，**Then** 对应记录 `promoted = 1`。
2. **Given** 2 条经验内容高度相似，**When** LLM 返回 `merge` 动作指定合并目标，**Then** 源条目 `archived = 1`，目标条目的 `hit_count` 累加。
3. **Given** LLM 返回 `archive` 动作，**When** 系统执行，**Then** 对应记录 `archived = 1`。
4. **Given** `promoted = 1` 的经验被 G2 检索命中，**When** 注入 prompt，**Then** 标注 `[已验证]` 标签。

---

### User Story 3 - 手动触发经验整理 (Priority: P3)

开发者可以通过 CLI 命令手动触发经验库整理，查看评分排名，按需执行淘汰和晋升。

**Why this priority**: 提供人工干预入口，便于调试和初期验证。

**Independent Test**: 执行 CLI 命令后确认输出包含评分排名和执行结果统计。

**Acceptance Scenarios**:

1. **Given** 开发者执行 `review-learnings` CLI 命令，**When** 命令完成，**Then** 输出包含候选条目列表、评分、LLM 评审结果和操作统计（promoted/merged/archived 数量）。
2. **Given** 经验库为空，**When** 执行 `review-learnings`，**Then** 输出"无候选条目"提示，不调用 LLM。

---

### Edge Cases

- 全部经验分数均低于淘汰阈值时，保留分数最高的 20 条（最低保留数量）
- LLM 返回不合法 JSON 时，安全跳过，不执行任何操作
- 新创建的经验（`hit_count = 0`）不应立即被淘汰（需要冷却期）
- `merge` 操作的源和目标 ID 相同时忽略
- LLM 调用失败（网络/quota）时记录错误并跳过晋升，不影响淘汰

## Requirements

### Functional Requirements

- **FR-001**: 系统 MUST 实现 `memory_score` 函数，公式为 `recency × importance × frequency`，其中 `recency = 0.95 ^ days_since_last_access`，`importance = confidence`，`frequency = log(hit_count + 1)`
- **FR-002**: 系统 MUST 在淘汰流程中将 `memory_score < 0.05` 的条目标记为 `archived = 1`（软删除）
- **FR-003**: 系统 MUST 保留至少 20 条未归档经验（最低保留数量），即使所有分数均低于阈值
- **FR-004**: 系统 MUST 在淘汰时跳过创建时间不足 7 天的记录（冷却期保护）
- **FR-005**: 系统 MUST 筛选 `hit_count ≥ 3 AND confidence ≥ 0.6 AND promoted = 0 AND archived = 0` 的条目作为晋升候选
- **FR-006**: 系统 MUST 将候选条目（按 `memory_score` 降序取前 10）提交 LLM 评审
- **FR-007**: LLM 评审 MUST 输出 JSON 数组，每项包含 `{id, action, merge_target_id?, reason}`，`action` 取值为 `promote / merge / keep / archive`
- **FR-008**: 系统 MUST 对 `merge` 动作执行：源条目 `archived = 1`，目标条目 `hit_count += 源条目 hit_count`，`confidence = max(源, 目标)`。insight 和 root_cause_tags 保留目标条目内容不变
- **FR-009**: 系统 MUST 在 LLM 返回非法 JSON 或调用失败时安全降级，记录错误日志，不执行任何数据变更
- **FR-010**: 系统 MUST 在每累计 20 次分析后自动触发淘汰 + 晋升流程，通过 `SELECT COUNT(*) FROM pa_telemetry` 取模 20 判断（每行即一次完成的分析）
- **FR-011**: 系统 MUST 提供 CLI 入口 `review-learnings` 支持手动触发
- **FR-012**: G2 检索注入时，`promoted = 1` 的经验 MUST 标注 `[已验证]` 标签，且 L1 SQL 查询 MUST 在 ORDER BY 中加入 `promoted DESC` 确保已验证条目排序优先
- **FR-013**: 系统 MUST 记录每次淘汰/晋升的遥测数据（trigger、候选数、各操作数、LLM token 消耗、耗时）

### Key Entities

- **memory_score**: 经验价值评估函数，基于 OpenClaw `recency × importance × frequency` 公式。衰减因子 `DECAY_FACTOR = 0.95`
- **pa_learnings 状态字段**: `promoted`（0=未晋升，1=已晋升）、`archived`（0=活跃，1=已归档）
- **pa_telemetry（扩展）**: 记录淘汰/晋升遥测数据的表

## Success Criteria

### Measurable Outcomes

- **SC-001**: 经验库在持续使用 30 天后，活跃记录数保持在合理范围（不超过 200 条未归档记录或无限膨胀）
- **SC-002**: 淘汰流程执行时间不超过 5 秒（不含 LLM 调用）
- **SC-003**: LLM 晋升评审结果中 80% 以上的决策无需人工修正
- **SC-004**: 淘汰后 G2 检索质量不降低（已验证经验优先返回）

## Clarifications

### Session 2026-04-13

- Q: 自动触发计数器（每 20 次分析）如何持久化？ → A: 复用 `pa_telemetry` 表，通过 `SELECT COUNT(*) FROM pa_telemetry` 取模 20 判断（每行即一次完成的分析）
- Q: 合并操作时 insight 文本如何处理？ → A: 保留目标条目的 insight，仅累加 hit_count 和取最大 confidence，丢弃源条目的文本
- Q: promoted 条目在 G2 检索中是否应获得排序优势？ → A: 是，L1 查询 ORDER BY 增加 `promoted DESC`，已验证条目排在前面

## Assumptions

- `pa_learnings` 表已由 G1 创建并包含 `confidence`、`hit_count`、`last_used`、`created_at`、`promoted`、`archived` 字段
- G2 的 `LearningsSearcher` 已实现 `AND archived = 0` 过滤
- LLM 模型可通过现有 `LLMManager` 获取，无需额外配置
- 衰减因子 `DECAY_FACTOR = 0.95` 为初始值，后续可通过插桩数据调整

## Constraints

- 淘汰操作 MUST 是软删除（`archived = 1`），不得硬删数据
- 晋升/淘汰流程 MUST NOT 阻塞正常分析流程
- LLM 调用失败 MUST NOT 导致淘汰流程失败
- 合并操作 MUST 保留更高的 `confidence` 和累加的 `hit_count`
