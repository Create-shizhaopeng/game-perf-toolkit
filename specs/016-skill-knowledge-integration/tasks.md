# Task Breakdown: Skill 知识层级应用 (G5)

**Branch**: `016-skill-knowledge-integration` | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

## 目录

- [Phase 1: Setup](#phase-1-setup)
- [Phase 2: Foundational — 辅助函数](#phase-2-foundational--辅助函数)
- [Phase 3: US2 — 按需知识拉取](#phase-3-us2--按需知识拉取)
- [Phase 4: US1 — SOP 引用指针增强](#phase-4-us1--sop-引用指针增强)
- [Phase 5: US3 — Skill 知识可达性](#phase-5-us3--skill-知识可达性)
- [Phase 6: Polish](#phase-6-polish)
- [Dependencies](#dependencies)

## Phase 1: Setup

- [x] T001 创建 G5 测试文件 `modules/perfetto_analysis/tests/test_g5_skill_knowledge.py`，包含基础 fixtures

## Phase 2: Foundational — 辅助函数

- [x] T002 [P] 在 `modules/perfetto_analysis/src/agent/tools.py` 模块级别定义 `_SKILLS_DIR` 常量，指向 `skills/perfetto-analysis/`
- [x] T003 [P] 在 `modules/perfetto_analysis/src/agent/tools.py` 模块级别实现 `_heading_to_anchor(heading: str) -> str`，Markdown 标题转锚点
- [x] T004 [P] 在 `modules/perfetto_analysis/src/agent/tools.py` 模块级别实现 `_build_toc_summary(content: str) -> str`，提取章节目录 + 每章节首句摘要
- [x] T005 在 `modules/perfetto_analysis/src/agent/tools.py` 模块级别实现 `_extract_section_by_anchor(content: str, anchor: str) -> str`，根据锚点提取章节内容

## Phase 3: US2 — 按需知识拉取

**Goal**: 新增 pa_read_knowledge 工具，实现两级加载。

**Independent Test**: 调用工具获取 L1 目录概览和 L2 章节详情。

- [x] T006 [US2] 在 `modules/perfetto_analysis/src/agent/tools.py` 的 `COMPRESSION_PROFILES` 中注册 `pa_read_knowledge: keep_all`
- [x] T007 [US2] 在 `modules/perfetto_analysis/src/agent/tools.py` 的 `build_analysis_tools` 内实现 `pa_read_knowledge` 工具函数，支持两级加载、路径越界保护、错误处理
- [x] T008 [US2] 在 `build_analysis_tools` 返回列表中添加 `pa_read_knowledge`

## Phase 4: US1 — SOP 引用指针增强

**Goal**: 在 SOP 文件中添加引用指针，指向 Skill 的 L2/L3 知识资产。

**Independent Test**: 检查 SOP 中引用指针格式正确且对应文件存在。

- [x] T009 [P] [US1] 在 `modules/perfetto_analysis/skills/perfetto-analysis/sop/jank-analysis.md` 末尾追加引用指针块
- [x] T010 [P] [US1] 在 `modules/perfetto_analysis/skills/perfetto-analysis/sop/anr-analysis.md` 末尾追加引用指针块
- [x] T011 [P] [US1] 在 `modules/perfetto_analysis/skills/perfetto-analysis/sop/startup-analysis.md` 末尾追加引用指针块
- [x] T012 [P] [US1] 在 `modules/perfetto_analysis/skills/perfetto-analysis/sop/memory-analysis.md` 末尾追加引用指针块
- [x] T013 [P] [US1] 在其余 SOP 文件（io-block, general, input-latency, response-latency, rotation）末尾追加通用引用指针块

## Phase 5: US3 — Skill 知识可达性

**Goal**: 确保 SOP 引用指针对应的 L2/L3 锚点存在。

- [x] T014 [US3] 扫描所有 SOP 中的引用指针，验证对应的 L2/L3 文件和锚点均可达。不可达的锚点需在对应知识文件中补充

## Phase 6: Polish

- [x] T015 编写 G5 单元测试 `modules/perfetto_analysis/tests/test_g5_skill_knowledge.py`：覆盖 _heading_to_anchor、_build_toc_summary、_extract_section_by_anchor、pa_read_knowledge L1/L2/错误场景
- [x] T016 运行 G5 单元测试并确保全部通过
- [x] T017 运行全量回归测试 `python scripts/run_all_tests.py`，确保零回归
- [x] T018 更新 `modules/perfetto_analysis/AGENTS.md`，增加 G5 Skill 知识层级应用特性描述
- [x] T019 更新 `modules/perfetto_analysis/docs/agent-memory-evolution.md`，标记 G5 为已实现

## Dependencies

```text
Phase 1 (Setup)
  └─→ Phase 2 (辅助函数: T002-T005)
        └─→ Phase 3 (US2 工具实现: T006-T008)
              ├─→ Phase 4 (US1 SOP 引用指针: T009-T013) ─→ Phase 5 (US3 可达性: T014)
              └─→ Phase 6 (Polish: T015-T019)
```

**Parallel Opportunities**:
- T002 ∥ T003 ∥ T004（独立辅助函数）
- T009 ∥ T010 ∥ T011 ∥ T012 ∥ T013（独立 SOP 文件修改）
- T018 ∥ T019（独立文档更新）

**MVP Scope**: Phase 1-3 (pa_read_knowledge 工具实现) — SubAgent 获得知识拉取能力。
