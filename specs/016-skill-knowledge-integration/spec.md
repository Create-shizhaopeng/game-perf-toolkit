# Feature Specification: Skill 知识层级应用 (G5)

**Feature Branch**: `016-skill-knowledge-integration`
**Created**: 2026-04-13
**Status**: Draft
**Input**: G5 Skill 知识层级应用 — 复用 Skill 渐进式披露层级，让 SubAgent 通过工具按需拉取 L2/L3 知识资产，精简 SOP 全文注入

## 目录

- [User Scenarios & Testing](#user-scenarios--testing)
  - [User Story 1 - SOP 引用指针增强](#user-story-1---sop-引用指针增强-priority-p1)
  - [User Story 2 - 按需知识拉取](#user-story-2---按需知识拉取-priority-p2)
  - [User Story 3 - Skill 知识可达性](#user-story-3---skill-知识可达性-priority-p3)
  - [Edge Cases](#edge-cases)
- [Requirements](#requirements)
  - [Functional Requirements](#functional-requirements)
  - [Key Entities](#key-entities)
- [Success Criteria](#success-criteria)
- [Assumptions](#assumptions)
- [Constraints](#constraints)

## User Scenarios & Testing

### User Story 1 - SOP 引用指针增强 (Priority: P1)

在现有 SOP 文件中添加引用指针（`→ 资源路径#锚点`），指向 Skill 的 L2/L3 知识资产。SOP 内容本身暂不精简（后续人工审核后独立执行），但需确保 SubAgent 知道可以通过 `pa_read_knowledge` 工具深入获取详情。

**Why this priority**: 引用指针是 SubAgent 发现和利用 L2/L3 知识资产的入口。

**Independent Test**: 检查 SOP 中是否包含有效的引用指针，指针对应的 L2/L3 锚点可达。

**Acceptance Scenarios**:

1. **Given** jank-analysis.md 中包含引用指针 `→ patterns/root-cause-patterns.md#cpu-调度抢占`，**When** SubAgent 需要深入分析，**Then** 可通过 `pa_read_knowledge` 工具跟随指针获取详情。
2. **Given** SOP 中新增了引用指针，**When** 加载 SOP 为 instructions，**Then** 原有内容无删减，仅追加了指针信息。

---

### User Story 2 - 按需知识拉取 (Priority: P2)

新增 `pa_read_knowledge` 工具，实现两级加载：Level 1 返回文件目录概览（~200 token），Level 2 返回指定章节详情（~200-400 token）。SubAgent 可按需拉取 Skill 中的 patterns、SQL 模板、案例等知识资产。

**Why this priority**: 让 SubAgent 首次获得 L2/L3 知识的访问能力。

**Independent Test**: 调用 `pa_read_knowledge("patterns/root-cause-patterns.md")` → 返回目录概览；调用 `pa_read_knowledge("patterns/root-cause-patterns.md#cpu-调度抢占")` → 返回章节详情。

**Acceptance Scenarios**:

1. **Given** `pa_read_knowledge("sql-patterns.md")`，**When** 不带锚点，**Then** 返回 ToolReturn 含章节目录 + 每章节一句话摘要。
2. **Given** `pa_read_knowledge("patterns/root-cause-patterns.md#hwc-binder-超时")`，**When** 带锚点，**Then** 返回该章节完整内容（截取至 2000 字符）。
3. **Given** 不存在的路径，**When** 调用，**Then** 返回错误提示 ToolReturn。
4. **Given** 路径尝试越界（如 `"../../secret.txt"`），**When** 调用，**Then** 返回路径越界错误。

---

### User Story 3 - Skill 知识可达性 (Priority: P3)

确保 Skill 中的 L2/L3 知识文件具备完整的 H2/H3 锚点，使 `pa_read_knowledge` 的 Level 2 加载能正确定位章节。

**Why this priority**: L2/L3 文件如果锚点缺失，按需拉取将失效。

**Independent Test**: 扫描 `patterns/root-cause-patterns.md` 和 `sql-patterns.md` → 确认所有 SOP 引用指针对应的锚点存在。

**Acceptance Scenarios**:

1. **Given** SOP 中引用了 `patterns/root-cause-patterns.md#cpu-调度抢占`，**When** 检查该文件，**Then** 该锚点对应的 H2/H3 章节存在。
2. **Given** SOP 中引用了 `sql-patterns.md#cpu-频率查询`，**When** 检查该文件，**Then** 该锚点对应的章节存在。

---

### Edge Cases

- `pa_read_knowledge` 请求的文件不在 Skill 目录内（路径越界保护）
- Skill 文件为空或格式异常（返回空目录概览）
- 锚点不存在时返回明确的错误信息
- SOP 精简后缺少关键判断条件（需人工审核确认）
- Level 1 目录概览中文件无任何 H2/H3 标题（返回文件前 200 字符作为摘要）

## Requirements

### Functional Requirements

- **FR-001**: SOP 文件 MUST 包含引用指针（`→ 资源路径#锚点`），指向 Skill 的 L2/L3 知识资产。SOP 内容精简作为后续人工审核任务
- **FR-002**: 精简后的 SOP MUST 包含引用指针（`→ 资源路径#锚点`），指向 Skill 中的 L2/L3 知识资产
- **FR-003**: 系统 MUST 新增 `pa_read_knowledge` 工具，注册到 SubAgent 工具集
- **FR-004**: `pa_read_knowledge` MUST 实现两级加载：无锚点返回目录概览，有锚点返回章节详情
- **FR-005**: `pa_read_knowledge` 返回 MUST 使用 `ToolReturn` 格式（压缩摘要 + metadata）
- **FR-006**: `pa_read_knowledge` MUST 限制路径在 Skill 目录内（`skills/perfetto-analysis/`），拒绝越界访问
- **FR-007**: Level 2 章节详情 MUST 截取至 2000 字符上限，避免大段注入
- **FR-008**: Skill 的 L2/L3 知识文件中被 SOP 引用的锚点 MUST 存在

## Key Entities

- **pa_read_knowledge**: 新增的第 10 个 pa_* 工具，两级加载 Skill 知识资产
- **ToolReturn**: 已有的工具返回格式（压缩摘要 + metadata）
- **_SKILLS_DIR**: Skill 目录根路径常量
- **引用指针**: SOP 中的 `→ 资源路径#锚点` 格式引用

## Success Criteria

### Measurable Outcomes

- **SC-001**: 所有场景的 SOP 至少包含 1 个有效引用指针
- **SC-002**: SubAgent 可通过 `pa_read_knowledge` 访问 patterns/sql-patterns/cases 三类知识资产
- **SC-003**: L2 加载（带锚点）单次返回 ≤ 2000 字符
- **SC-004**: 所有 SOP 引用指针对应的 L2/L3 锚点 100% 可达

## Assumptions

- Skill 目录结构（`modules/perfetto_analysis/skills/perfetto-analysis/`）已稳定
- G0 推理链已覆盖分析步骤顺序和维度优先级
- `ToolReturn` 格式和工具注册机制已就绪（G0 已实现）
- SOP 精简需人工审核确认关键判断条件未丢失

## Constraints

- 不创建新的知识文件，复用 Skill 现有结构
- `pa_read_knowledge` MUST NOT 允许访问 Skill 目录外的文件
- SOP 精简 MUST NOT 删除判断条件和阈值
- Level 2 章节详情截取不得超过 2000 字符

## Clarifications

1. **Q1: SOP 精简策略** — 选择 B: 本次迭代聚焦 `pa_read_knowledge` 工具实现。SOP 内容精简作为后续独立任务，由人工逐个审核确认后执行。US1 在本次迭代中调整为"确保 SOP 中包含引用指针"，不做内容删减。
2. **Q2: pa_read_knowledge 返回值压缩** — 使用 `keep_all` 策略透传。知识文本已是精简的参考材料（L1 ~200 token, L2 ≤2000 字符上限），无需额外压缩。
