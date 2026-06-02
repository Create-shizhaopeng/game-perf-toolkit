# Service API Contract: Agent 核心重构

**Feature**: 021-agent-core-refactor | **Date**: 2026-05-26

## 公共 API 变更

本次重构的核心原则：**不破坏 pluggy hookspecs 的接口约定**。模块开发者看到的 hook 签名不变，但底层注册目标变更。

### hookspecs 接口（不变）

```python
# toolkit/core/hookspecs.py — 接口签名不变

class ToolkitHookSpec:
    @hookspec
    def register_agent_tools(self) -> list[dict]:
        """返回模块向 Agent 暴露的工具列表。"""

    @hookspec
    def register_skills(self) -> list[str]:
        """返回模块 Skill 文件路径列表。"""

    @hookspec
    def on_startup(self, context: dict) -> None:
        """应用启动回调。context 中新增 mcp_registry。"""

    @hookspec
    def on_shutdown(self) -> None:
        """应用关闭回调。"""
```

### context 新增键

```python
# Phase 1 后 context 中新增
context["tool_registry"]     # ToolRegistry (原在 agent_chat 内部)
context["mcp_registry"]      # MCPRegistry (原在 agent_chat 内部)
context["skill_registry"]    # SkillRegistry (已存在，增强)
```

### ToolRegistry 公共接口（提升到 core）

```python
# toolkit/core/tool_registry.py

class ToolRegistry:
    # ── 模块级单例 ──
    # tool_registry = ToolRegistry()

    def register(self, name: str, toolset: str, schema: dict,
                 handler: Callable, *, check_fn=None, is_async=False,
                 description="", max_result_size_chars=None,
                 dynamic_schema_overrides=None, override=False) -> None: ...

    def deregister(self, name: str) -> None: ...

    def get_definitions(self, tool_names: set[str] | None = None) -> list[dict]:
        """返回 OpenAI Function Calling 格式工具列表。仅包含 check_fn 通过的工具。"""
        ...

    def dispatch(self, name: str, args: dict) -> str:
        """执行工具。返回 JSON string。"""
        ...

    def collect_from_plugins(self, plugin_manager) -> int:
        """从 pluggy hooks 收集模块注册的工具。返回注册数量。"""
        ...

    def register_mcp_tools(self, definitions: list) -> int: ...
    def unregister_by_prefix(self, prefix: str) -> int: ...
    def get_entry(self, name: str) -> ToolEntry | None: ...
    def get_tool_names_for_toolset(self, toolset: str) -> list[str]: ...
```

### SkillRegistry 增强接口

```python
# toolkit/core/skill_registry.py

class SkillRegistry:
    # ── 现有接口（不变）──
    def load_skills(self, paths: list[str]) -> None: ...
    def get_skills(self) -> list[SkillMetadata]: ...
    def get_skill(self, name: str) -> SkillMetadata | None: ...
    def get_skill_content(self, name: str) -> str | None: ...

    # ── 新增接口 ──
    def add_search_path(self, path: Path) -> None:
        """添加 Skill 搜索路径（支持递归扫描子目录）。"""
        ...

    def scan(self) -> list[SkillMetadata]:
        """扫描所有搜索路径，刷新 Skill 索引。"""
        ...

    def search(self, keyword: str) -> list[SkillMetadata]:
        """按关键词搜索 Skill（匹配 name/description/tags/triggers）。"""
        ...

    def get_resource(self, name: str, rel_path: str) -> str | None:
        """读取 Skill 子资源内容。"""
        ...

    def list_resources(self, name: str) -> dict[str, list[str]]:
        """列出 Skill 的子资源目录结构。"""
        ...
```

### MCPRegistry 公共接口（提升到 core）

```python
# toolkit/core/mcp/registry.py

class MCPSource(str, Enum):
    LOCAL = "local"
    EXTERNAL = "external"
    REMOTE = "remote"

class MCPRegistry:
    def __init__(self, tool_registry: ToolRegistry): ...

    # ── 注册 ──
    def register_local(self, module: str, handler_class) -> None: ...
    def register_external(self, config: MCPServerConfig) -> None: ...
    def register_remote(self, url: str, auth: dict | None = None) -> None: ...

    # ── 连接管理 ──
    async def connect(self, name: str) -> MCPConnection: ...
    async def connect_all(self) -> list[MCPConnection]: ...
    async def disconnect(self, name: str) -> None: ...

    # ── 工具桥接 ──
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    async def call_tool(self, server: str, tool: str, args: dict) -> Any: ...

    # ── 查询 ──
    def get_servers(self) -> dict[str, MCPServerConfig]: ...
    def get_connections(self) -> list[MCPConnection]: ...
    def add_server(self, config: MCPServerConfig) -> None: ...
    def remove_server(self, name: str) -> None: ...
    def update_server(self, name: str, **kwargs) -> None: ...
```

### AgentOrchestrator 接口（新建）

```python
# toolkit/agent/orchestrator.py

class AgentOrchestrator:
    def __init__(self, context: dict): ...

    def init_tools(self) -> list[ToolDefinition]:
        """构建统一工具视图：内置 + Skill + 模块 + MCP。"""
        ...

    def build_system_prompt(self, *, extra: str = "",
                            conv_id: str = "") -> str:
        """三段式 System Prompt 组装。"""
        ...

    def create_service(self) -> AgentService:
        """创建/返回 AgentService 实例。"""
        ...

    @property
    def is_ready(self) -> bool:
        """Provider 是否可用。"""
        ...

    # ── 配置变更回调 ──
    def on_provider_changed(self, provider_name: str) -> None: ...
    def on_skills_changed(self) -> None: ...
    def on_mcp_changed(self) -> None: ...

    # ── 预留 ──
    def spawn_subagent(self, config: SubAgentConfig) -> SubAgentResult:
        """预留：创建子 Agent 执行独立任务。Phase 2 后实现。"""
        raise NotImplementedError
```

## 模块适配契约

### Phase 3 前（兼容模式）

```python
# 模块继续使用 register_agent_tools() 注册 → ToolRegistry
# 模块继续使用 register_skills() 注册 → SkillRegistry
# 两者并行，无 breaking change
```

### Phase 3 后（目标模式）

```python
# 模块不再直接暴露裸方法，改为：
# 1. register_skills() → SKILL.md 文档（描述如何使用工具）
# 2. register_local(module, handler) → MCP Local 工具（可执行能力）
# register_agent_tools() 返回空列表
```

## app.py 启动流程变更

```python
# toolkit/app.py — 变更摘要

def _build_context():
    context = {
        # ... 现有服务 ...
        "tool_registry": ToolRegistry(),    # 新增
        "mcp_registry": MCPRegistry(),      # 新增
        # skill_registry 已存在
    }
    return context

def _load_plugins(context):
    # 不变：调用 on_startup → register_skills → skill_registry.load_skills()
    # 不变：AgentOrchestrator 在 MainWindow 创建后初始化
    ...

def run_gui():
    # Agent 从 set_agent_panel(tab) 改为：
    #   agent_panel = AgentPanel(orchestrator)
    #   right_panel.set_widget(agent_panel)
    ...
```
