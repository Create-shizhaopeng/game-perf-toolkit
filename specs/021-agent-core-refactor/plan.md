# Implementation Plan: Agent 核心重构

**Branch**: `dev` | **Date**: 2026-05-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from [spec.md](spec.md)
**Design**: [docs/design/DES-001-agent-core-refactor.md](../../docs/design/DES-001-agent-core-refactor.md)

## Summary

将 `modules/agent_chat/` 提升为 `toolkit/agent/`，与 `toolkit/core/` 同级。`ToolRegistry`、`SkillRegistry`（增强）、`MCP Framework` 统一收归 `toolkit/core/`，打破循环依赖。Agent GUI 从中央 Tab 改为右侧可展开面板（独占 RightPanel 内容区）。模块能力逐步从直接暴露裸方法迁移为 Skill 文档 + MCP Local 工具。

技术方案：借鉴 Hermes Agent 的 Registry Pattern、Progressive Disclosure、三段式 System Prompt 设计模式，自建实现。

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: PyQt6, pluggy 1.3+, Pydantic 2.0+, LiteLLM, mcp SDK (FastMCP + ClientSession)
**Storage**: SQLite (WAL) — 对话历史; JSON — 配置文件
**Testing**: pytest
**Target Platform**: Windows desktop (dev) / Windows exe (frozen)
**Project Type**: desktop-app
**Performance Goals**: 启动 < 5s; Agent 首字响应 < 5s; 面板动画 < 300ms
**Constraints**: Phase 1 仅移动代码不改变逻辑；测试保持 100% 通过率
**Scale/Scope**: 单用户桌面应用，工具数量 < 50

## Constitution Check

*GATE: 项目 `.specify/memory/constitution.md` 为未填充模板，使用 `CLAUDE.md` 中的开发规范作为门禁。

| 门禁 | 状态 | 说明 |
|------|------|------|
| 模块 MUST NOT 修改 `toolkit/` 核心框架 | ⚠️ 授权修改 | 本次重构的目标就是将 agent_chat 的基础设施提升到 core，属于框架级变更 |
| GUI MUST 使用 QThread + pyqtSignal | ✅ 不涉及新增后台操作 | AgentPanel 复用现有 _AgentWorker (QThread) |
| 中文 MUST 提取到 `strings_*.py` | ✅ 落实 | toolkit/agent/strings_gui.py 已存在，保持不变 |
| 日志 MUST 使用统一日志体系 | ✅ 落实 | 通过 `logging.getLogger(__name__)` |
| 图标 MUST 使用 codicon | ✅ 落实 | 现有图标体系不变 |
| 对话框 MUST 继承 `ToolkitDialog` | ✅ 不涉及新增对话框 | |
| QSS MUST 通过 `objectName` + `styles.py` | ✅ 落实 | AgentPanel 新增 objectName |
| 路径 MUST 通过 `app_paths` | ✅ 落实 | 现有路径工具不变 |

## Project Structure

### Documentation (this feature)

```
specs/021-agent-core-refactor/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: Technical research & decisions
├── data-model.md        # Phase 1: Data model & entity relationships
├── quickstart.md        # Phase 1: Developer onboarding guide
├── contracts/           # Phase 1: Interface contracts
│   └── service-api.md   #   ToolRegistry, SkillRegistry, MCPRegistry, AgentOrchestrator APIs
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

#### Phase 1: 新增/修改的文件

```
toolkit/core/
├── tool_registry.py              # ← 从 modules/agent_chat/src/tools/registry.py 提升
├── tool_executor.py              # ← 从 modules/agent_chat/src/tools/executor.py 提升
├── models.py                     # ← 新增: ToolCall/ToolResult/ToolDefinition 等核心模型
├── skill_registry.py             # ← 增强: 合并 discovery 扫描能力
├── mcp/                          # ← 从 modules/agent_chat/src/mcp/ 提升 + mcp_server.py 合并
│   ├── __init__.py
│   ├── server.py                 #   ← 从 toolkit/core/mcp_server.py 移入
│   ├── client.py                 #   ← 从 modules/agent_chat/src/mcp/connection.py
│   ├── registry.py               #   ← 从 modules/agent_chat/src/mcp/manager.py
│   └── tool_bridge.py            #   ← 从 modules/agent_chat/src/mcp/tool_bridge.py
└── mcp_server.py                 # ← 删除 (合并到 mcp/server.py)

modules/agent_chat/src/tools/     # ← 保留 re-export 兼容层
├── registry.py                   #   ← from toolkit.core.tool_registry import *
├── executor.py                   #   ← from toolkit.core.tool_executor import *
modules/agent_chat/src/mcp/       # ← 保留 re-export 兼容层
modules/agent_chat/src/skills/discovery.py  # ← 删除 (合并到 core skill_registry)
```

#### Phase 2: 新增/修改的文件

```
toolkit/agent/                    # ← 从 modules/agent_chat/ 重命名+重构
├── __init__.py
├── orchestrator.py               # ← 新建: AgentOrchestrator
├── service.py                    # ← 重构: 移除 Provider fallback
├── system_prompt.py              # ← 新建: 三段式 System Prompt
├── models.py                     # ← 精简: 移除已提升到 core 的模型
├── memory/
│   └── conversation.py           # ← 从 modules/agent_chat/src/memory/
├── knowledge/
│   └── report_index.py           # ← 从 modules/agent_chat/src/knowledge/
├── workflow/
│   ├── tracker.py                # ← 适配: 输出 SKILL.md 格式
│   └── generator.py              # ← 适配: 输出 SKILL.md 格式
├── gui/
│   └── agent_panel.py            # ← 新建: AgentPanel (右侧面板)
└── strings_gui.py                # ← 从 modules/agent_chat/src/strings_gui.py

toolkit/gui/
├── main_window.py                # ← 修改: Agent 从 set_agent_panel(Tab) → right_panel.set_widget(agent_panel)

modules/agent_chat/               # ← Phase 2 完成后删除
```

#### Phase 3: 新增/修改的文件

```
modules/perfetto_analysis/
└── skills/
    └── perfetto-analysis/
        └── SKILL.md              # ← 新建: 分析方法论文档

modules/device_disguise/
└── skills/                       # ← 已有 skill，验证+补全
```

## Complexity Tracking

无违反项。本次重构消除了架构中的 5 个结构性问题（命名误导、架构倒置、Skill 双轨制、MCP 散落、裸方法暴露），整体复杂度下降。

## Phase 0 Deliverables

- [x] [research.md](research.md) — 5 项技术决策 (Hermes 参考、依赖方向修正、Skill 合并、AgentPanel 策略、迁移策略)
- [x] Technical Context 填充完毕

## Phase 1 Deliverables

- [x] [data-model.md](data-model.md) — 7 个核心实体 + 关系图
- [x] [contracts/service-api.md](contracts/service-api.md) — 4 个公共接口定义 + app.py 变更
- [x] [quickstart.md](quickstart.md) — 开发环境准备 + 验证步骤 + FAQ

## Next: Phase 2 (/speckit-tasks)

运行 `/speckit-tasks` 生成按 Phase 1/2/3 分组、带依赖排序的可执行任务列表。
