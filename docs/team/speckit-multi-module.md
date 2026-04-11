# 多模块项目 Speckit 使用约定

## 目录

- [适用场景](#适用场景)
- [当前架构](#当前架构)
- [路由规则](#路由规则)
- [模块 Spec 管理](#模块-spec-管理)
- [模块 AGENTS.md 声明规范](#模块-agentsmd-声明规范)

## 适用场景

Monorepo 架构中，项目仅在根目录维护统一 speckit（`.specify/`），各模块的 spec 文档输出到各自的 `specs/` 目录。AI Agent 需要判断用户意图对应哪个模块，以确定 spec 输出位置。

## 当前架构

- **统一 Speckit**：仅根目录 `.specify/` 维护 constitution、scripts、templates
- **模块约束分离**：各模块的开发规则和边界约束记录在 `modules/<name>/AGENTS.md`
- **Spec 输出分离**：各模块的 spec 文档存放在 `modules/<name>/specs/`，状态索引见 `specs/INDEX.md`
- **根 Spec**：框架级/跨模块功能的 spec 存放在根 `specs/`

> 历史说明：模块级独立 `.specify/` 目录已于 2026-04-09 移除，内容合并到各模块 `AGENTS.md`。

## 路由规则

AI 在启动 spec 流程时，按以下顺序判断目标模块：

1. 用户是否显式指定了模块名？→ spec 输出到该模块 `specs/`
2. 用户描述的功能是否明确属于某个模块？→ spec 输出到该模块 `specs/`
3. 功能涉及多个模块或属于框架能力？→ spec 输出到根 `specs/`
4. 无法判断？→ 询问用户确认目标模块

判断后，加载该模块的 `AGENTS.md` 获取模块约束。

## 模块 Spec 管理

- 各模块 `specs/` 目录使用独立编号序列（从 001 开始），不与根 specs 或其他模块冲突
- 各模块 `specs/INDEX.md` 维护 spec 状态索引（Implemented / Draft / Deprecated）
- `AGENTS.md` 中的「Spec 索引」段落列出当前活跃 spec，供 Agent 快速定位

## 模块 AGENTS.md 声明规范

每个模块的 `AGENTS.md` SHOULD 包含 Spec 索引段：

```text
## Spec 索引

当前无活跃 Spec。完整索引见 [specs/INDEX.md](specs/INDEX.md)。
```

或有活跃 spec 时：

```text
## 活跃 Spec

- **002-agent-mcp-hybrid**（Implemented）— Agent 多智能体编排

完整索引见 [specs/INDEX.md](specs/INDEX.md)。
```
