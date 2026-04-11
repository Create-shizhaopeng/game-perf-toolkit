# 框架使用例外清单

## 目录

- [概述](#概述)
- [允许的 toolkit.core 导入](#允许的-toolkitcore-导入)
- [特殊测试位置](#特殊测试位置)

## 概述

Constitution 规定模块「禁止导入 `toolkit.core` 内部实现」。本文档列出经过审批的例外情况。

**适用场景**：当开发特定模块且需要确认是否允许某个导入时查阅。

## 允许的 toolkit.core 导入

| 模块 | 允许导入 | 原因 | 依据 |
|------|---------|------|------|
| perfdog_insights | `toolkit.core.perfdog` | PerfDog 核心逻辑实现在框架层，模块作为 UI 入口 | perfdog_insights/AGENTS.md |

其他模块仅允许导入：
- `toolkit.sdk.*`（SDK 公共接口）
- `toolkit.core.hookspecs`（钩子规格定义）

## 特殊测试位置

| 模块 | 测试位置 | 原因 |
|------|---------|------|
| perfdog_insights | 根目录 `tests/`（而非模块 `tests/`） | pytest import-mode 限制，避免跨模块文件名冲突（参考 P04） |

其他模块的测试 MUST 放在模块内的 `tests/` 目录。
