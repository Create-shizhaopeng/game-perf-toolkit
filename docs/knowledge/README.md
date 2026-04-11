# 项目知识库

## 目录

- [概述](#概述)
- [知识清单](#知识清单)
- [维护规则](#维护规则)

## 概述

本目录存放 lv-game-toolkit 项目的**跨模块**知识资产。这些知识关联项目整体而非某个特定模块。

模块特定的知识存放在 `modules/<name>/docs/` 目录。
团队协作规范与跨项目通用知识存放在 `docs/team/` 目录。

## 知识清单

| 文档 | 说明 | 最后更新 |
|------|------|---------|
| [module-registry.md](module-registry.md) | 模块注册表：前缀、事件总线、框架导入例外 | 2026-03-31 |
| [toolkit-exceptions.md](toolkit-exceptions.md) | 框架使用例外清单：允许的 `toolkit.core` 直接导入 | 2026-03-31 |
| [module-development-guide.md](module-development-guide.md) | 新模块开发完整指南（环境 → Spec → 实现 → 测试） | 2026-03-31 |
| [长期记忆其他实践.md](长期记忆其他实践.md) | AI Agent 长期记忆系统的外部实践参考（文档驱动方案对比） | 2026-04-09 |

## 维护规则

- 新增跨模块知识时 MUST 更新本索引
- 每个知识文档 MUST 标注最后更新日期
- 知识文档 SHOULD 包含「适用场景」说明，便于 Agent 判断相关性
