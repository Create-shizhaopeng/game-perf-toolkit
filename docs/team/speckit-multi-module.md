# 多模块项目 Speckit 使用约定

## 目录

- [适用场景](#适用场景)
- [核心原则](#核心原则)
- [路由规则](#路由规则)
- [模块 AGENTS.md 声明规范](#模块-agentsmd-声明规范)
- [脚本行为约束](#脚本行为约束)

## 适用场景

Monorepo 架构中，主项目和各子模块各自拥有独立 `.specify/` 目录（含 constitution、scripts、templates），且 AI Agent 需要判断用户意图对应哪个 speckit。

## 核心原则

1. **先路由后执行**：在运行任何 speckit 命令前，MUST 先确定目标模块
2. **子模块 spec 归子模块**：子模块的 spec 文件 MUST 存放在子模块的 `specs/` 目录下
3. **主模块管通用**：根 `specs/` 仅用于框架级/跨模块功能

## 路由规则

AI 在启动 spec 流程时，按以下顺序判断目标模块：

1. 用户是否显式指定了模块名？→ 使用该模块的 speckit
2. 用户描述的功能是否明确属于某个模块？→ 使用该模块的 speckit
3. 功能涉及多个模块或属于框架能力？→ 使用主项目的 speckit
4. 无法判断？→ 询问用户确认目标模块

判断后，加载该模块的 AGENTS.md 获取 speckit 具体路径。

## 模块 AGENTS.md 声明规范

每个模块的 AGENTS.md SHOULD 包含 speckit 路径声明：

```text
## Speckit
- 路径: `.specify/`
- Spec 输出: `specs/`
- 编号: 本模块独立编号（从 001 开始）
```

## 脚本行为约束

子模块的 `create-new-feature.ps1` 脚本 MUST：
- 将 spec 文件创建在本模块的 `specs/` 目录下
- 使用本模块独立的编号序列（不与主项目或其他模块冲突）
- 不修改主项目的 `specs/` 目录
