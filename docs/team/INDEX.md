# 团队规范索引

## 目录

- [概述](#概述)
- [知识清单](#知识清单)
- [使用说明](#使用说明)

## 概述

本目录存放团队级通用规范和经验积累。

项目特定知识见 `docs/knowledge/` 和 `docs/experience/`。
模块特定知识见 `modules/<name>/docs/`。

## 知识清单

| 文档 | 说明 |
|------|------|
| [git-workflow.md](git-workflow.md) | Git 分支策略、提交规范、PR 流程 |
| [coding-conventions.md](coding-conventions.md) | Python 编码规范、类型注解、文档字符串 |
| [speckit-multi-module.md](speckit-multi-module.md) | 多模块项目中 Speckit 的路由与治理约定 |
| [cursor-interaction.md](cursor-interaction.md) | Cursor IDE 与 AI Agent 交互的经验积累 |
| [progress-reporting.md](progress-reporting.md) | 项目进度汇报流程（技术进度 → 飞书业务汇报） |

## 使用说明

- Agent 检索时优先扫描本 INDEX.md 确定哪些知识与当前任务相关
- 仅在确认相关后才加载具体知识文档
- 新增知识文档后 MUST 更新本索引
