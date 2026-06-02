# Research: Agent 核心重构

**Feature**: 021-agent-core-refactor | **Date**: 2026-05-26

## 第三方方案评估

### Hermes Agent 参考架构

| 方案 | 优势 | 劣势 | 适配成本 |
|------|------|------|---------|
| 自建设计 | 完全适配项目，无额外依赖 | 需要从零设计 | N/A (本项目) |
| Hermes Agent (参考) | 开源验证的 Registry/Progressive Disclosure/Toolset 模式；Python 生态 | 非库，需手动提取设计模式 | 中等（仅借鉴模式，不引入代码） |

**决策**: 借鉴 Hermes 设计模式，自建实现。Hermes 的 ToolRegistry 单例模式、三段式 System Prompt、Skill 渐进式加载、MCP 统一前缀设计已被验证有效，直接适配到本项目的 PyQt6 + pluggy 生态。

### 依赖方向修正

当前 `toolkit/core/mcp_server.py` 反向 import `modules/agent_chat/src/tools/registry.py`。

| 方案 | 优势 | 劣势 |
|------|------|------|
| A: 移动 ToolRegistry 到 core | 根本解决循环依赖 | 需要批量更新 import |
| B: 在 core 中新建抽象层 | 改动最小 | 增加一层间接，未来需要合并 |
| C: 延迟 import | 最简单 | 治标不治本 |

**决策**: 方案 A — 移动 ToolRegistry/ToolExecutor 到 `toolkit/core/`。这是唯一正确消除循环依赖的方式，Phase 1 中完成。

### SkillRegistry 合并策略

| 方案 | 优势 | 劣势 |
|------|------|------|
| A: 增强 core SkillRegistry，合并 agent_chat discovery 能力 | 单轨制，API 统一 | 需要迁移 agent_chat 中的调用方 |
| B: 保留两套，通过适配器桥接 | 改动最小 | 双轨制持续存在，维护负担 |

**决策**: 方案 A — `toolkit/core/skill_registry.py` 增强为包含递归目录扫描、YAML frontmatter 解析、内容读取能力。agent_chat 的 `SkillsManager` 降级为 Agent 层的薄封装（路由 + skill_* 工具生成）。

### AgentPanel 右侧面板

| 方案 | 优势 | 劣势 |
|------|------|------|
| A: 替换现有 RightPanel 内容区 | 简洁，Agent 独享右侧 | 其他模块不能在右侧同时展示 |
| B: 与现有 RightPanel 共存 (Tab 切换) | 兼容性强 | 用户需要在两个面板间切换 |
| C: QDockWidget 可拖拽 | 灵活 | 需要处理浮动窗口状态管理 |

**决策**: 方案 A — 已通过 clarify 确认。Agent 不再是导航栏中的一个 Tab，而是始终可用的右侧面板。当前无其他模块使用 RightPanel 内容区。

### Phase 1 迁移策略

| 方案 | 优势 | 劣势 |
|------|------|------|
| A: 逐步迁移（保留旧路径兼容 import） | 每一步可测试 | 需要临时 re-export 层 |
| B: 大爆炸（一次性移动所有文件 + 更新所有 import） | 没有中间状态 | 可能长时间不可运行 |

**决策**: 方案 A — 渐进式迁移。Phase 1 中每步移动文件后，在原位置保留 `from toolkit.core.xxx import *` 的兼容 re-export，确保 agent_chat 模块仍可运行。Phase 2 完成后删除旧目录。

## 技术上下文确认

| 项目 | 值 |
|------|-----|
| 语言 | Python 3.12+ |
| GUI | PyQt6 |
| 插件系统 | pluggy 1.3+ |
| 数据模型 | Pydantic 2.0+ / dataclass |
| LLM | LiteLLM (通过 LLMManager) |
| MCP | mcp SDK (FastMCP 服务端 + ClientSession 客户端) |
| 存储 | SQLite (WAL), JSON 文件 |
| 测试 | pytest |
| 平台 | Windows desktop (dev) / Windows exe (frozen) |
| 项目类型 | desktop-app |
| 性能目标 | 启动 <5s, Agent 首字响应 <5s, 面板动画 <300ms |
| 约束 | 模块 MUST NOT 修改 `toolkit/`（本次重构是框架级变更，授权修改） |
