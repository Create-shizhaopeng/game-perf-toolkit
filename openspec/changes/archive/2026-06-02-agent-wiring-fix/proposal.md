## Why

DES-001 Agent 核心重构对标 Hermes Agent，底层组件（ToolRegistry、SkillRegistry、MCP Framework、三段式 System Prompt）已全部实现并独立验证通过。但审计发现 18 处偏差——涵盖启动连线断裂（HIGH）、API 不一致（MEDIUM）、UI 功能缺失（MEDIUM）、代码质量问题（LOW）。核心症状：AgentOrchestrator 被绕过，Skill 工具从未注入，MCP 从未连接，Agent 无法正常使用。本次修复覆盖全部 18 项，聚焦"让已有组件正确协作"，不涉及组件内部逻辑重写。

## What Changes

**启动连线（HIGH）：**
- AgentOrchestrator 作为唯一初始化入口，串联模块工具 → Skill 工具 → MCP 连接 → AgentService
- AgentPanel 不再绕过 Orchestrator 自行创建 ToolRegistry/SkillsManager
- `run_mcp_server()` 改用 toolkit.core 单例而非旧 module 路径
- MCP register_local/remote 从空 stub 实现为可工作方法

**Skill 工具模块化（HIGH）：**
- 新建 `toolkit/agent/skill_tools.py` 和 `skill_router.py`，从旧模块提取纯函数
- 旧 `SkillsManager` 改为 compat shim

**API 一致性（MEDIUM）：**
- System Prompt 补充 `report_index` 参数和 `conv_id` 注入 Volatile 层
- `SkillMetadata.triggers` 类型从 `dict` 修正为 `list[str]`
- `SkillRegistry` 补充 `get_content()` 别名
- `ToolRegistry` 补充 `dispatch()` 方法

**AgentPanel 完善（MEDIUM）：**
- 声明 `panel_expanded`/`panel_collapsed`/`message_sent` 信号
- 实现拖拽调整宽度（240px-480px）
- 新增会话选择器（历史下拉 + 新建按钮）

**基础设施（MEDIUM/LOW）：**
- `_build_context()` 补充 ToolRegistry/MCPRegistry 创建
- MCP 注册不再自动持久化副作用
- AgentService 移除未定义的类型注解
- `_enhance_schema` 改为 ToolRegistry 方法
- `AgentPanel._ctx` 命名修正

**单元测试（质量门禁）：**
- 新建模块 `toolkit/agent/skill_tools.py`、`skill_router.py` MUST 包含单元测试
- 修改模块 `toolkit/core/mcp/registry.py` MUST 补充 register_local/remote 测试

## Capabilities

### New Capabilities
- `agent-skill-tools`: 统一 Skill 工具生成（9 tools），基于 SkillRegistry + SkillRouter，含单元测试
- `agent-wiring`: AgentOrchestrator 唯一初始化入口，串联 ToolRegistry → Skill Tools → MCP → AgentService
- `agent-panel-polish`: AgentPanel 信号、拖拽调整宽度、会话选择器

### Modified Capabilities
- `agent-core-refactor`: 修复全部 18 项审计偏差（FR-003/007/008/010/013/015 的实现偏差，API 不一致，类型修正）

## Impact

- `toolkit/app.py` — 启动连线重构，`_build_context()` 补全
- `toolkit/agent/orchestrator.py` — 新增 4 个方法
- `toolkit/agent/system_prompt.py` — 补充 report_index + conv_id
- `toolkit/agent/gui/agent_panel.py` — 委托 Orchestrator + 信号 + 拖拽 + 会话选择器
- `toolkit/agent/service.py` — 移除未定义类型注解
- `toolkit/core/tool_registry.py` — 新增 dispatch()
- `toolkit/core/skill_registry.py` — triggers 类型修正 + get_content 别名
- `toolkit/core/mcp/registry.py` — register_local/remote 实现 + auto-save 移除
- `toolkit/agent/skill_tools.py` — 新建（含测试）
- `toolkit/agent/skill_router.py` — 新建（含测试）
- `modules/agent_chat/src/skills/manager.py` — compat shim
