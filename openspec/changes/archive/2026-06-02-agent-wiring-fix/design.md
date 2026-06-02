## Context

DES-001 重构将 `modules/agent_chat/` 提升为 `toolkit/agent/`，基础设施下沉到 `toolkit/core/`。底层组件（ToolRegistry 单例、SkillRegistry 三级加载、MCP Client/Server、三段式 System Prompt）均已实现并独立验证通过。但启动连线有系统性偏差：

- `AgentOrchestrator` 存在但被 `AgentPanel._ensure_service()` 绕过
- `Orchestrator.init_tools()` 从未被调用
- `MCPRegistry.connect_all()` 从未被调用
- Skill 工具从未注入 ToolRegistry
- `run_mcp_server()` 仍使用旧 module 路径

修复策略：不改组件逻辑，只修连线。

## Goals / Non-Goals

**Goals:**
- AgentOrchestrator 成为启动时唯一的初始化入口
- 启动流程覆盖三个工具来源：模块工具 + Skill 工具 + MCP 工具
- AgentPanel 不再自行创建 ToolRegistry/SkillsManager
- MCP register_local/remote 从 stub 变为可工作实现
- `run_mcp_server()` 使用 toolkit.core 路径

**Non-Goals:**
- 不改 ToolRegistry/SkillRegistry/MCP 组件内部逻辑
- 不改 System Prompt 三段式结构
- 不改 AgentPanel UI 布局
- 不移动 tests（后续独立处理）

## Decisions

### D1: 初始化入口归一化

**选择**：`AgentOrchestrator.init()` 作为唯一同步入口，`init_async()` 处理 MCP 异步连接。

```python
# toolkit/agent/orchestrator.py
class AgentOrchestrator:
    def init(self) -> None:
        """同步初始化 — 模块 tools + skill tools"""
        self._register_skill_tools()    # 注入 skill_* 工具到 ToolRegistry
        self._register_builtin_tools()  # workspace 工具

    async def init_async(self) -> None:
        """异步初始化 — MCP 连接，由 QTimer 在 event loop 启动后调度"""
        if self._mcp_registry:
            await self._mcp_registry.connect_all()
        self.init_tools()  # 刷新统一视图
```

**替代方案**：让 app.py 直接调用各个注册函数 → 拒绝，违背"Orchestrator 是唯一入口"的设计。

### D2: AgentPanel 服务创建委托

**选择**：`AgentPanel._ensure_service()` 改为 `self._orch.create_service(conversation_store=store)`。

移除了以下在 AgentPanel 中的重复逻辑：
- 创建本地 ToolRegistry
- 创建本地 SkillsManager
- 手动遍历注册 skill_* 工具

### D3: Skill 工具模块化

**选择**：新建 `toolkit/agent/skill_tools.py` 统一生成 skill_* 工具，从 `modules/agent_chat/src/skills/` 中提取纯函数（无状态依赖的部分）。

- `skill_router.py` — 从 `modules/agent_chat/src/skills/router.py` 移植，改为引用 `toolkit.core.skill_registry.SkillMetadata`
- `skill_tools.py` — `build_skill_tools(skill_registry, router)` 返回 9 个 ToolDefinition
- curator 工具函数（classify_document, match_skill, format_resource 等）直接从 `modules/agent_chat/src/skills/curator_tools.py` 提取，只改 import 路径

### D4: MCP stub 实现策略

**register_local()**：接收 handler_class → 内省公开方法 → 以 `mcp__{module}__{method}` 格式注册到 ToolRegistry

**register_remote()**：创建 MCPServerConfig → 存入 servers 字典 → 由 connect_all() 统一连接

### D5: app.py 启动流

```python
# run_gui():
context["tool_registry"] = tool_registry
context["mcp_registry"] = MCPRegistry(tool_registry=tool_registry)
tool_registry.collect_from_plugins(pm)  # 模块 tools

orchestrator = AgentOrchestrator(context)
orchestrator.init()                      # skill tools + builtin tools

agent_panel = AgentPanel(orchestrator=orchestrator)
agent_panel.set_event_bus(context.get("event_bus"))
window.set_agent_panel_widget(agent_panel)

# MCP 异步连接在 event loop 就绪后调度
QTimer.singleShot(100, lambda: asyncio.ensure_future(orchestrator.init_async()))
```

### D6: SkillMetadata.triggers 类型修正

**选择**：将 `triggers: dict` 改为 `triggers: list[str]`，对齐 Hermes 的 YAML frontmatter 格式 `triggers: [keyword1, keyword2]`。`search()` 方法增加触发关键词匹配。

### D7: System Prompt 补充参数

**选择**：`build_system_prompt()` 增加 `report_index` 参数，Volatile 层注入 `conv_id`。不改变 Stable/Context/Volatile 三层结构。

### D8: AgentPanel 拖拽与信号

**选择**：AgentPanel 声明 `panel_expanded`/`panel_collapsed`/`message_sent` 信号。拖拽调整复用 `RightPanel._ResizeHandle` 机制（已有的左边缘拖拽手柄）。会话选择器用 `QComboBox` 实现。

### D9: 单元测试策略

**选择**：新建 `tests/test_agent_skill_tools.py` 和 `tests/test_core_mcp_registry.py`。每个公开方法至少 1 个 smoke test，验证工具生成和注册流程。

### D10: MCP 持久化分离

**选择**：`register_external()` 和 `register_remote()` 只做内存注册，不自动持久化。`add_server()` 和 `remove_server()` 负责持久化。避免启动时的注册操作覆盖用户配置文件。

## Risks / Trade-offs

- **SkillRouter 移植可能引入 import 断裂**：旧代码依赖 Pydantic 版 `SkillMetadata`（有 `triggers`/`tags`），新 core 版 `SkillMetadata` 字段不完全一致 → 需要在移植时对齐字段访问
- **MCP 异步连接失败不阻塞启动** → 这是预期行为（设计如此），但需确保错误被合理记录
- **AgentPanel 现有 `_is_running` 状态管理不变** → 发送/停止逻辑不受影响

## Open Questions

- `modules/agent_chat/src/skills/` 中哪些文件可以完全删除（vs 保留为 compat shim）？→ 本次保留 curator_tools.py 作为内部实现，manager.py 改为 shim
