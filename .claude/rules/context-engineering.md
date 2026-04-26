# 上下文工程规范

上下文空间是稀缺资源。MUST 遵循渐进式披露原则，按需加载知识，避免上下文过载。

## 渐进式披露策略

1. **入口层**（始终可用）：`.cursor/rules/` 中的精简规则
2. **索引层**（按需查阅）：`INDEX.md` / `README.md` — 扫描标题和摘要即可定位
3. **详情层**（深入时加载）：具体知识文档 — 仅在确认相关时完整阅读

## 知识检索优先级

开发特定模块或功能时，按以下优先级检索上下文：

1. `modules/<name>/AGENTS.md` — 模块边界约束（MUST 首先阅读）
2. `modules/<name>/docs/` — 模块级知识和经验
3. 当前 `specs/` 下的 spec/plan/tasks — 需求和设计上下文
4. `docs/knowledge/` — 项目跨模块知识（前缀注册表、框架例外等）
5. `docs/experience/development-pitfalls.md` — 踩坑经验（按子系统快速索引定位相关条目）
6. `.specify/memory/constitution.md` — 架构原则（仅在需要确认原则时）
7. `docs/team/` — 团队规范（Git 工作流、编码规范等）

## 经验沉淀规则

遇到以下情况时 SHOULD 记录经验：
- AI 犯了需要纠正的错误 → 记录到 `docs/experience/` 或模块 `docs/`
- 发现可复用的模式/方案 → 记录到 `docs/knowledge/`
- 发现跨项目通用的经验 → 记录到 `docs/team/`
- 发现新的踩坑问题 → 补充到 `docs/experience/development-pitfalls.md`

## 大文档检索策略

以下文档超过 500 行，MUST 先读取目录段（前 30 行）定位相关章节，再按需读取该章节，MUST NOT 全文加载：

- `docs/experience/development-pitfalls.md`（1353 行）— 按子系统快速索引定位
- `docs/architecture/architecture-overview.md`（1475 行）— 按章节号定位

## 禁止行为

- MUST NOT 在一次会话中加载所有知识文档
- MUST NOT 重复加载已在 rules 中声明的规则
- MUST NOT 在不涉及特定模块时加载该模块的 AGENTS.md
- MUST NOT 全文加载超过 500 行的文档（按大文档检索策略操作）
