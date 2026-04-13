# Tasks: 经验淘汰与晋升 (G3)

**Input**: Design documents from `specs/014-learning-eviction-promotion/`
**Prerequisites**: plan.md (required), spec.md (required)

## 目录

- [Phase 1 Setup](#phase-1-setup)
- [Phase 2 Foundational](#phase-2-foundational-评分引擎与淘汰)
- [Phase 3 US1](#phase-3-user-story-1---自动淘汰低价值经验-p1--mvp)
- [Phase 4 US2](#phase-4-user-story-2---llm-驱动经验晋升-p2)
- [Phase 5 US3](#phase-5-user-story-3---手动触发经验整理-p3)
- [Phase 6 Polish](#phase-6-polish--cross-cutting)
- [Dependencies](#dependencies--execution-order)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: 创建 G3 核心文件和 Pydantic 模型

- [x] T001 创建 `src/agent/learnings_manager.py` 文件，定义模块常量 `DECAY_FACTOR=0.95`, `EVICT_THRESHOLD=0.05`, `MIN_RETAIN_COUNT=20`, `COOLDOWN_DAYS=7`, `PROMOTE_HIT_THRESHOLD=3`, `PROMOTE_CONFIDENCE_THRESHOLD=0.6`, `PROMOTE_CANDIDATE_LIMIT=10`
- [x] T002 [P] 在 `src/agent/learnings_manager.py` 中定义 `PromotionAction` Pydantic 模型，字段：`id: int`, `action: Literal["promote", "merge", "keep", "archive"]`, `merge_target_id: int | None`, `reason: str`

---

## Phase 2: Foundational — 评分引擎与淘汰

**Purpose**: 实现 memory_score 纯函数和淘汰核心逻辑（US1 的前置依赖）

- [x] T003 在 `src/agent/learnings_manager.py` 中实现 `memory_score(learning: dict, now: datetime | None = None) -> float` 纯函数，公式 `recency × importance × frequency`
- [x] T004 在 `src/agent/learnings_manager.py` 中实现 `evict_low_score_learnings(conn) -> dict`，包含冷却期保护（FR-004）、最低保留数量（FR-003）、分数阈值淘汰（FR-002）

**Checkpoint**: 评分引擎和淘汰逻辑可独立测试

---

## Phase 3: User Story 1 - 自动淘汰低价值经验 (P1) MVP

**Goal**: 分析完成后自动检测并触发淘汰

**Independent Test**: 插入老旧低分经验 → 触发淘汰 → 确认 archived=1 且不超过保留数量

- [x] T005 [US1] 在 `src/agent/learnings_manager.py` 中实现 `_should_trigger_maintenance(conn) -> bool`，查询 `SELECT COUNT(*) FROM pa_telemetry` 取模 20 判断（每行即一次完成的分析）
- [x] T006 [US1] 在 `src/agent/orchestrator.py` 的 `analyze_single` finalize 阶段调用 `_maybe_trigger_maintenance`，异步执行淘汰流程（不阻塞返回结果）
- [x] T007 [US1] 在 `src/agent/learnings_manager.py` 中实现 `_record_maintenance_telemetry(conn, trigger, evict_result, promote_result)` 记录淘汰遥测数据到 `pa_telemetry`

**Checkpoint**: 每 20 次分析后自动淘汰低价值经验

---

## Phase 4: User Story 2 - LLM 驱动经验晋升 (P2)

**Goal**: 高频高置信经验通过 LLM 评审后晋升为已验证状态

**Independent Test**: 准备满足门槛的候选 → 触发晋升 → 确认 promoted=1 和合并效果

- [x] T008 [US2] 在 `src/agent/learnings_manager.py` 中实现 `_build_promotion_prompt(candidates: list[dict]) -> str`，将候选条目格式化为 LLM 评审 prompt
- [x] T009 [US2] 在 `src/agent/learnings_manager.py` 中实现 `promote_learnings(conn, llm_manager) -> dict`，筛选候选 → 排序取 top 10 → LLM 评审 → 解析执行动作（FR-005 ~ FR-007）。LLM 调用失败或返回非法 JSON 时安全降级，记录错误日志，返回零操作统计（FR-009）
- [x] T010 [US2] 在 `src/agent/learnings_manager.py` 中实现 `_merge_learnings(conn, source_id, target_id) -> bool`，累加 hit_count、取 max confidence、源条目 archived=1（FR-008）
- [x] T011 [US2] 在 `src/agent/learnings_manager.py` 中实现 `_apply_promotion_actions(conn, actions, candidates) -> dict`，遍历 LLM 返回的动作列表执行 promote/merge/archive/keep，返回统计
- [x] T012 [US2] 在 `src/agent/orchestrator.py` 的 `_maybe_trigger_maintenance` 中集成晋升流程：淘汰完成后执行 `promote_learnings`
- [x] T013 [US2] 修改 `src/agent/learnings_search.py` 的 `_l1_exact_match` 和 `_l1_tag_cross_match` SQL，ORDER BY 增加 `promoted DESC`（FR-012）
- [x] T014 [US2] 修改 `src/agent/orchestrator.py` 的 `_format_learnings_block`（L1061），为 `promoted=1` 的条目添加 `[已验证]` 标签，并修改 L1 SQL SELECT 增加 `promoted` 字段返回

**Checkpoint**: LLM 评审 → promote/merge/archive 动作执行 → G2 注入时标注已验证

---

## Phase 5: User Story 3 - 手动触发经验整理 (P3)

**Goal**: CLI 命令 `review-learnings` 手动触发淘汰 + 晋升

**Independent Test**: 执行 CLI 命令 → 确认输出包含评分排名和操作统计

- [x] T015 [US3] 在 `src/cli_commands.py` 中新增 `review-learnings` 子命令，支持 `--json` 输出，调用 `evict_low_score_learnings` + `promote_learnings`
- [x] T016 [US3] 在 `review-learnings` 中增加评分排名展示：列出所有未归档经验的 memory_score 排序

**Checkpoint**: CLI 手动触发完整的经验库整理

---

## Phase 6: Polish & Cross-Cutting

**Purpose**: 测试、文档、回归验证

- [x] T017 [P] 编写 G3 单元测试 `tests/test_g3_eviction_promotion.py`，覆盖：memory_score 计算、冷却期保护、最低保留数、淘汰阈值、晋升候选筛选、merge 操作、LLM 降级、自动触发判断、promoted 排序
- [x] T018 运行全量回归测试确认无回归
- [x] T019 [P] 更新 `AGENTS.md` 新增经验淘汰与晋升描述
- [x] T020 更新 `docs/agent-memory-evolution.md` 标记 G3 为已实现

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 无依赖
- **Phase 2 (Foundational)**: 依赖 Phase 1
- **Phase 3 (US1)**: 依赖 Phase 2（评分+淘汰逻辑）
- **Phase 4 (US2)**: 依赖 Phase 2（评分逻辑），可与 Phase 3 并行但建议顺序执行
- **Phase 5 (US3)**: 依赖 Phase 3 + Phase 4（复用淘汰+晋升函数）
- **Phase 6 (Polish)**: 依赖 Phase 3 ~ Phase 5

### Parallel Opportunities

- T001 + T002 可并行（同文件但不同部分）
- T013 + T014 可并行（不同文件或同文件不同函数）
- T017 + T019 可并行（不同文件）

---

## Implementation Strategy

### MVP First (US1 Only)

1. Phase 1 → Phase 2 → Phase 3
2. 验证：淘汰流程正确执行，archived 条目不被 G2 检索返回
3. 此时已有基本的经验库膨胀控制

### Incremental Delivery

1. US1 (淘汰) → US2 (晋升) → US3 (CLI)
2. 每个 US 完成后独立测试验证

---

## Notes

- 总任务数：20
- US1 (P1): 3 个任务
- US2 (P2): 7 个任务
- US3 (P3): 2 个任务
- Setup: 2 个任务
- Foundational: 2 个任务
- Polish: 4 个任务
