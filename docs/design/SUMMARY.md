# 设计方案索引

> **记忆压缩层**：当活跃文档超过 10 个时，此处汇总「编号 + 核心结论」供 AI 快速定位，无需逐篇加载全文。

## 活跃文档

| 编号 | 简述 | 状态 | 创建日期 | 核心结论（一句话） |
|------|------|------|----------|-------------------|
| [DES-001](DES-001-agent-core-refactor.md) | Agent 核心重构：agent_chat → toolkit/agent + Core 基础设施下沉 | implemented | 2026-05-26 | modules/agent_chat 提升为 toolkit/agent；ToolRegistry/SkillRegistry/MCP 统一收归 core；Module Tool 封装为 Skill/MCP |
| [DES-002](DES-002-hermes-agent-upgrade.md) | Hermes Agent 深度引入 — Agent 框架升级设计 | draft | 2026-06-02 | 在 DES-001 基础上引入 ErrorClassifier/CircuitBreaker/ContextCompressor/Verification/KnowledgeBase/Memory 六大能力 |
| [DES-003](DES-003-ui-design-standards.md) | UI 设计规范与 VSCode 差距补齐 | draft | 2026-08-12 | 建立 Design Token 体系（颜色/间距/字号/圆角/阴影）+ 组件六态规范 + P0-P3 差距清单 + 三期实施路线（Phase 1 token 落地先行） |

## 已归档

> 已移动到 `docs/archive/design/` 的历史文档。归档后保留原始编号，新编号继续递增。

| 编号 | 简述 | 归档日期 | 核心结论（一句话） |
|------|------|----------|-------------------|
