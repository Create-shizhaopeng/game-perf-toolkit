# Implementation Plan: 历史文件选中联动 Agent 对话上下文

**Branch**: `018-history-agent-context` | **Date**: 2026-04-14 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/018-history-agent-context/spec.md`

## 目录

- [Summary](#summary)
- [Technical Context](#technical-context)
- [Constitution Check](#constitution-check)
- [Project Structure](#project-structure)
  - [Documentation (this feature)](#documentation-this-feature)
  - [Source Code (repository root)](#source-code-repository-root)
- [Implementation Phases](#implementation-phases)
  - [Phase 0 — Research & Decisions](#phase-0--research--decisions)
  - [Phase 1 — Data/UI Contract Design](#phase-1--dataui-contract-design)
  - [Phase 2 — 右键菜单到 EventBus 事件链路](#phase-2--右键菜单到-eventbus-事件链路)
  - [Phase 3 — Agent Chat 上下文区与注入逻辑](#phase-3--agent-chat-上下文区与注入逻辑)
  - [Phase 4 — 会话隔离与上下文持久化](#phase-4--会话隔离与上下文持久化)
  - [Phase 5 — 测试与回归](#phase-5--测试与回归)
- [Complexity Tracking](#complexity-tracking)

## Summary

在左侧历史面板（抓取历史/分析历史）增加“发送到 Agent 对话”能力，通过 EventBus 将文件上下文注入右侧 Agent Chat。上下文按会话隔离、支持多文件去重、支持点击 `×` 或 Backspace/Delete 删除，并在发送消息时将活跃文件路径拼接到用户消息尾部传递给 LLM。

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: PyQt6、pluggy、EventBus（`toolkit.core.event_bus`）、现有 `agent_chat`/`perfetto_capture` 模块  
**Storage**: SQLite（`agent_chat.db`，会话与消息）；如需扩展可新增会话上下文字段/表  
**Testing**: pytest（模块测试 + GUI 逻辑单元测试）  
**Target Platform**: Windows 10/11 桌面（源码运行 + PyInstaller）  
**Project Type**: 插件化桌面应用（PyQt6）  
**Performance Goals**: 右键发送后 1s 内右侧面板打开并展示上下文；单次发送上下文拼接开销可忽略（<10ms）  
**Constraints**: 不破坏现有 Agent 对话流；UTF-8 全链路；上下文必须按会话隔离；保持 EventBus 解耦  
**Scale/Scope**: 影响 `modules/perfetto_capture`、`modules/agent_chat`、`toolkit/gui` 框架层，新增/修改约 8-12 个文件

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 状态 | 说明 |
|---|---|---|
| I. Plugin-First | ✅ PASS | 业务实现位于 `modules/perfetto_capture` 与 `modules/agent_chat`，框架层仅做面板联动 |
| II. Three-Surface Unity | ✅ PASS | 变更主要在 GUI，但上下文注入逻辑在 Agent 服务调用链保持一致 |
| III. Agent-Driven Design | ✅ PASS | 仅提供上下文，不限制 Agent 工具编排 |
| IV. Dependency Inversion | ✅ PASS | 通过 EventBus 交互，模块间无直接 `src` 导入 |
| V. Presentation Separation | ✅ PASS | 服务逻辑不下沉到 GUI；GUI 仅触发与展示 |
| VI. Open-Closed | ✅ PASS | 不修改核心插件机制 |
| VII. Spec-Driven Development | ✅ PASS | 已完成 clarify，当前进入 plan 阶段 |

## Project Structure

### Documentation (this feature)

```text
specs/018-history-agent-context/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── history-send-to-agent.event.json
└── tasks.md            # 由 /speckit.tasks 生成
```

### Source Code (repository root)

```text
modules/perfetto_capture/src/
├── history_panel.py                 # 右键菜单 + EventBus 发布
└── gui_tab.py                       # 现有历史容器联动（必要时）

modules/agent_chat/src/
├── gui_tab.py                       # 监听事件、上下文区 UI、消息注入、删除交互
├── service.py                       # 会话上下文持久化（如落库）
└── repositories/                    # 如需新增 context repository

toolkit/gui/
├── main_window.py                   # 确保右侧面板按需自动打开
└── panels/right_panel.py            # 右侧 Agent 容器状态协同（若需）

modules/agent_chat/tests/
└── test_context_injection.py        # 新增：注入与会话隔离测试
```

**Structure Decision**: 基于现有模块结构增量改造，不引入新模块。

## Implementation Phases

### Phase 0 — Research & Decisions

产出 `research.md`，确认以下关键决策：
- EventBus 事件 payload 合约（trace/analysis 统一字段）
- Agent Chat 多文件上下文的数据结构与去重策略
- 会话级上下文持久化方式（内存映射 vs SQLite 扩展）
- Backspace/Delete 删除的焦点与键盘事件处理边界

### Phase 1 — Data/UI Contract Design

产出 `data-model.md` + `contracts/history-send-to-agent.event.json` + `quickstart.md`：
- 定义 `FileContext` 与 `ConversationContextState`
- 定义事件 `history.send_to_agent` 的 JSON Schema
- 定义 ContextBar 交互契约（添加、去重、删除、会话切换恢复）

### Phase 2 — 右键菜单到 EventBus 事件链路

目标：历史条目右键可发送到 Agent，且 payload 完整。

主要改动：
- `modules/perfetto_capture/src/history_panel.py`
  - 在抓取历史/分析历史条目右键菜单加入“发送到 Agent 对话”
  - 构建 payload：`file_path`、`file_name`、`context_type`
  - 发布 `history.send_to_agent`
- 边界处理：
  - 路径不存在时仍允许发送，但标记 `missing=true`（供 UI 标注）

### Phase 3 — Agent Chat 上下文区与注入逻辑

目标：Agent Chat 显示多文件上下文，并在发送消息时注入。

主要改动：
- `modules/agent_chat/src/gui_tab.py`
  - 监听 `history.send_to_agent`
  - 收到事件后自动请求 `show_right_panel`
  - ContextBar 支持多文件渲染、按 `file_path` 去重
  - 文件项支持 `×` 删除与 Backspace/Delete 删除
  - 发送消息前将全部活跃路径拼接到用户消息尾部

### Phase 4 — 会话隔离与上下文持久化

目标：切换会话恢复各自上下文，新会话为空。

主要改动（按实现选型）：
- 若使用内存态：会话 ID -> `list[FileContext]` 映射
- 若使用数据库：在 `agent_chat.db` 增加上下文表或字段
- 会话切换、创建、删除时同步维护上下文映射

### Phase 5 — 测试与回归

测试覆盖：
- 右键发送 -> 事件发布正确
- Agent 接收事件 -> 右侧自动打开 + ContextBar 更新
- 多文件去重与单项删除（`×` / Backspace/Delete）
- 注入格式：用户消息尾部包含活跃路径
- 会话切换隔离：A 会话与 B 会话互不污染
- 无上下文发送：不追加路径信息

## Complexity Tracking

无 Constitution 违规，无需额外复杂度豁免。

| 风险点 | 缓解策略 |
|---|---|
| GUI 键盘事件焦点冲突 | 仅在 ContextBar 列表焦点内处理 Backspace/Delete 删除 |
| 会话切换状态错乱 | 统一以会话 ID 作为单一真值来源 |
| 事件早到（Agent 未初始化） | 在 Agent Tab 初始化后回放缓存事件 |
