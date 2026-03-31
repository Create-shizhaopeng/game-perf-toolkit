---
name: module-context-loader
description: 开发特定模块时，按需加载该模块的 AGENTS.md、docs/ 知识文档和相关踩坑经验。
  当开始开发某个模块或需要了解模块约束时使用此技能。
compatibility: lv-game-toolkit 模块开发
metadata:
  author: lv-game-toolkit
  version: "1.0.0"
---

# 模块上下文加载技能

## 适用场景

- 开始开发某个模块的功能时
- 需要了解模块的约束、前缀、事件等信息时
- 修复某个模块的 Bug 时

## 执行步骤

### Step 1: 识别目标模块

从用户意图中识别涉及的模块名称。可用模块：

| 模块 | 前缀 | 说明 |
|------|------|------|
| device_disguise | dd_ | 设备伪装 |
| game_perf | gp_ | 游戏性能配置 |
| perfetto_capture | pe_ | Perfetto 抓取 |
| perfetto_analysis | pa_ | Perfetto 解析分析 |
| perfdog_insights | pdi_ | PerfDog 分析 |
| agent_chat | ac_ | Agent 智能助手 |

### Step 2: 加载模块知识（渐进式）

按以下顺序加载，每步判断是否需要继续深入：

1. **MUST** 读取 `modules/<name>/AGENTS.md` — 模块边界约束
2. **MUST** 读取 `modules/<name>/docs/README.md` — 模块知识入口和相关踩坑索引
3. **按需** 读取 `doc/knowledge/module-registry.md` — 如涉及跨模块交互
4. **按需** 读取 `doc/knowledge/toolkit-exceptions.md` — 如涉及框架导入问题
5. **按需** 从 `doc/experience/development-pitfalls.md` 的"按子系统快速索引"定位相关踩坑条目

### Step 3: 输出上下文摘要

加载完成后，向用户输出简短摘要：
- 当前模块的关键约束（2-3 条）
- 与当前任务最相关的踩坑提醒（如有）
- 需要特别注意的事项

## 注意事项

- MUST NOT 同时加载所有模块的 AGENTS.md
- MUST NOT 将所有 pitfalls 全部加载到上下文中
- 仅加载与当前模块和任务相关的知识
