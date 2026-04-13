# Tasks: 相似案例注入 (G2)

**Input**: Design documents from `/specs/013-similar-case-injection/`  
**Prerequisites**: plan.md, spec.md, G1 已实现

## 目录

- [Format](#format)
- [Phase 1 L1 标签检索](#phase-1-l1-标签检索)
- [Phase 2 L2 向量搜索](#phase-2-l2-向量搜索)
- [Phase 3 编排器集成](#phase-3-编排器集成)
- [Phase 4 Polish](#phase-4-polish)
- [Dependencies](#dependencies--execution-order)

## Format

`[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: User story label (US1-US3)

---

## Phase 1: L1 标签检索

**Purpose**: 基于 SQL 的精确匹配和标签交叉匹配

- [x] T001 [US1] 新建 `src/agent/learnings_search.py`，定义 `LearningsSearcher` 类骨架（`__init__`, `search` 主入口方法签名）
- [x] T002 [US1] 实现 `_l1_exact_match` 方法：`SELECT ... FROM pa_learnings WHERE scene = ? AND process_name = ? AND archived = 0 ORDER BY confidence DESC, hit_count DESC LIMIT ?`
- [x] T003 [US1] 实现 `_l1_tag_cross_match` 方法：`scene` 匹配 + `root_cause_tags` 与 `issue_tags` 交叉判定，排除已命中 id
- [x] T004 [US1] 实现 `search` 主流程：L1 精确 → L1 标签交叉 → 合并去重 → 返回 limit 条

**Checkpoint**: 给定 pa_learnings 测试数据，L1 检索返回正确匹配结果

---

## Phase 2: L2 向量搜索 (可选增强)

**Purpose**: sentence-transformers + sqlite-vec 语义搜索

- [x] T005 [P] [US2] 在 `storage.py` 中新增 `_create_learning_embeddings_table` 函数（sqlite-vec 虚拟表），在 `init_db` 中条件调用（sqlite-vec 可用时）
- [x] T006 [P] [US2] 在 `storage.py` 中新增 `insert_learning_embedding` 函数：写入 embedding 向量
- [x] T007 [US2] 修改 G1 的 `_extract_and_save_learnings`：在 `insert_learning` 后，如果 embedder 可用，同步生成 embedding 并写入
- [x] T008 [US2] 在 `LearningsSearcher` 中实现 `_l2_semantic_search` 方法：encoding + vec_distance_cosine 查询
- [x] T009 [US2] 实现 `_try_init_embedder` 工厂函数：尝试加载 sentence-transformers，不可用返回 None
- [x] T010 [US2] 更新 `search` 主流程：L1 命中 < 2 条时触发 L2

**Checkpoint**: L2 可用时能返回语义相似结果，L2 不可用时静默降级到纯 L1

---

## Phase 3: 编排器集成

**Purpose**: 将案例检索集成到编排流程

- [x] T011 [US3] 实现 `_extract_issue_tags_from_prefetch` 函数：从预取结果提取 issue 标签（jank_type、issues 等）
- [x] T012 [US3] 在 `orchestrator.py` 中新增 `_search_similar_cases` 方法：创建 LearningsSearcher 实例 + 调用 search + 格式化结果
- [x] T013 [US3] 实现 `_format_learnings_block` 静态方法：将检索结果格式化为"历史分析参考"Markdown 区块
- [x] T014 [US3] 在 `analyze_single` 的预取完成后调用 `_search_similar_cases`，结果合并到 `prefetch_context`，并将 `injected_ids` 存入 result dict 以便 finalize 阶段使用
- [x] T015 [US3] 实现 `_update_hit_counts` 方法：分析完成后，比对结论 root_cause_tags 与注入案例标签交集，匹配的 +1
- [x] T016 [US3] 在 `analyze_single` 的 finalize 阶段调用 `_update_hit_counts`

**Checkpoint**: 有历史数据时 SubAgent prompt 包含"历史分析参考"区块，分析完成后匹配案例 hit_count 更新

---

## Phase 4: Polish

**Purpose**: 测试和文档

- [x] T017 [P] 编写 G2 单元测试：覆盖 L1 精确/标签匹配、L2 降级、issue_tags 提取、hit_count 更新、注入格式化，文件 `tests/test_g2_similar_case.py`
- [x] T018 [P] 更新 AGENTS.md 新增相似案例注入描述
- [x] T019 更新 `agent-memory-evolution.md` 标记 G2 为已实现

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (L1)**: 无依赖，立即开始
- **Phase 2 (L2)**: 依赖 Phase 1 的 LearningsSearcher 骨架
- **Phase 3 (集成)**: 依赖 Phase 1 完成，可与 Phase 2 并行（L2 为可选增强）
- **Phase 4 (Polish)**: 依赖 Phase 1/2/3 全部完成

### Execution Order

```
Phase 1 (L1) → Phase 2 (L2) + Phase 3 (集成) → Phase 4 (Polish)
```

### Task Summary

| Phase | Task Count | 说明 |
|-------|-----------|------|
| Phase 1 L1 检索 | 4 | SQL 标签匹配 |
| Phase 2 L2 搜索 | 6 | 向量语义搜索 (可选) |
| Phase 3 集成 | 6 | 编排器集成 |
| Phase 4 Polish | 3 | 测试 + 文档 |
| **Total** | **19** | |
