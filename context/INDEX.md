# 跨项目知识资产索引

## 目录

- [概述](#概述)
- [目录结构](#目录结构)
- [团队级知识](#团队级知识)
- [跨项目经验](#跨项目经验)
- [使用说明](#使用说明)

## 概述

本目录存放**跨项目可复用**的通用知识资产。这些知识不绑定 lv-game-toolkit 项目本身，而是团队级别的通用规范和经验积累。

项目特定的知识请存放在 `doc/knowledge/` 和 `doc/experience/` 目录。
模块特定的知识请存放在 `modules/<name>/docs/` 目录。

## 目录结构

```text
context/
├── INDEX.md              # 本文件（Agent 检索入口）
├── team/                 # 团队级通用知识
│   ├── git-workflow.md   # Git 工作流与分支规范
│   ├── coding-conventions.md  # 跨项目编码规范
│   └── speckit-multi-module.md  # 多模块 Speckit 使用约定
└── experience/           # 跨项目经验积累
    └── cursor-interaction.md  # Cursor IDE 交互经验
```

## 团队级知识

| 文档 | 说明 |
|------|------|
| [team/git-workflow.md](team/git-workflow.md) | Git 分支策略、提交规范、PR 流程 |
| [team/coding-conventions.md](team/coding-conventions.md) | Python 编码规范、类型注解、文档字符串 |
| [team/speckit-multi-module.md](team/speckit-multi-module.md) | 多模块项目中 Speckit 的路由与治理约定 |

## 跨项目经验

| 文档 | 说明 |
|------|------|
| [experience/cursor-interaction.md](experience/cursor-interaction.md) | Cursor IDE 与 AI Agent 交互的经验积累 |

## 使用说明

- Agent 检索时优先扫描本 INDEX.md 确定哪些知识与当前任务相关
- 仅在确认相关后才加载具体知识文档
- 新增知识文档后 MUST 更新本索引
