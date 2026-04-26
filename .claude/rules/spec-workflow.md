# Spec-Driven Agent 工作流规范

（基础硬约束和开发流程速查已纳入根目录 `CLAUDE.md` 「开发规范」章节。本文件保留完整规范中未纳入 CLAUDE.md 的补充规则。）

## 开发流程完整约束

完整流程和验收工作流详见 `.specify/memory/constitution.md`。本规则仅列出未在 CLAUDE.md 中详述的补充约束。

- Step 3 (UE/UI) 仅在涉及 GUI 时执行
- 每次 analysis MUST FAIL 项清零方可进入下一阶段
- 所有 clarify 决策 MUST 回写 `spec.md` Clarifications 章节

## Bug 修复

- MUST 先分析根因再修复，MUST NOT 盲目尝试
- BUG 修复完成后 MUST 同步更新 spec 文档

## 需求变更

- 需求变更：clarify → [UE/UI] → plan → task → analysis → implement → analysis
- 变更内容 MUST 同步更新 spec 文档

## Speckit 路由

Speckit 仅在项目根级维护，所有新 spec 统一输出到根 `specs/` 目录。

| 目标 | Speckit 路径 | Spec 输出目录 |
|------|-------------|-------------|
| 所有模块（统一） | `.specify/` | `specs/` |

> 历史遗留的 `modules/<name>/specs/` 不做迁移，但新 spec 一律在根 `specs/` 下创建。

模块开发时的约束和边界以 `modules/<name>/AGENTS.md` 为权威源。

## 补充硬约束

- Constitution（`.specify/memory/constitution.md`）是最高治理文档
- 新模块开发前 MUST 阅读 `docs/experience/development-pitfalls.md`
- 当前模块相关的 `AGENTS.md` MUST 在实现前阅读
- context 键名 MUST 使用模块前缀（如 `dd_service`、`gp_adb`）
