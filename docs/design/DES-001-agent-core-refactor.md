<!--
  id: DES-001
  title: Agent 核心重构 — modules/agent_chat → toolkit/agent + Core 基础设施下沉
  type: design
  status: implemented
  created: 2026-05-26
  updated: 2026-05-26
  tags: [agent, architecture, refactor, skill, mcp, tool-registry]
  depends_on: [020-llm-manager-refactor]
-->

# Agent 核心重构设计方案

## 目录

- [概述与目标](#概述与目标)
- [参考架构: Hermes Agent](#参考架构-hermes-agent)
- [整体架构](#整体架构)
  - [重构前后对比](#重构前后对比)
  - [目标目录结构](#目标目录结构)
- [数据流](#数据流)
  - [启动注册流](#启动注册流)
  - [对话执行流](#对话执行流)
  - [工具发现与调用流](#工具发现与调用流)
- [关键模块细分设计](#关键模块细分设计)
  - [Core: ToolRegistry](#core-toolregistry)
  - [Core: SkillRegistry](#core-skillregistry)
  - [Core: MCP Framework](#core-mcp-framework)
  - [Agent: AgentOrchestrator](#agent-agentorchestrator)
  - [Agent: System Prompt 三段式](#agent-system-prompt-三段式)
  - [Agent: GUI AgentPanel](#agent-gui-agentpanel)
- [模块适配指南](#模块适配指南)
- [迁移路径](#迁移路径)
- [风险与未决问题](#风险与未决问题)
- [变更记录](#变更记录)

## 概述与目标

### 背景

当前 `modules/agent_chat/` 存在以下结构性问题：

1. **命名误导**：`agent_chat` 暗示"聊天界面"，但它是整个工具的核心编排引擎
2. **架构倒置**：`toolkit/core/mcp_server.py` 反向依赖 `modules/agent_chat/src/tools/registry.py`
3. **Skill 双轨制**：`toolkit/core/skill_registry.py` 和 `modules/agent_chat/src/skills/` 功能重叠
4. **MCP 框架散落**：MCP Client 在 agent_chat 内部，MCP Server 在 core，各自为政
5. **模块工具直接暴露**：各模块通过 `register_agent_tools()` 直接暴露内部方法，粒度太细

### 目标

| 目标 | 描述 |
|------|------|
| **Agent 晋升** | `modules/agent_chat/` → `toolkit/agent/`，与 `toolkit/core/` 同级 |
| **基础设施下沉** | `ToolRegistry`、`SkillRegistry`、`MCP Framework` 统一收归 `toolkit/core/` |
| **统一工具视图** | Skill 工具 + MCP 工具 → Agent 看到的统一工具池 |
| **模块能力封装** | 模块不再暴露裸方法，统一封装为 Skill 文档或 MCP Tool |
| **右侧面板** | Agent GUI 从中央 Tab 改为右侧可展开面板 |
| **自主编排** | Agent 通过 LLM 自主决策加载哪个 Skill、调用哪个工具 |

### 参考模型

借鉴开源项目 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的以下设计：

- **Registry Pattern**：线程安全单例 ToolRegistry，模块 import 时自注册
- **Progressive Disclosure**：Skill 三级渐进式加载（元数据 → SKILL.md → 子资源）
- **三段式 System Prompt**：Stable / Context / Volatile 分层组装
- **Toolset 组合**：工具按 Toolset 分组，Agent 按场景启用/禁用
- **MCP 统一前缀**：外部 MCP 工具以 `mcp__{server}__{tool}` 命名注入 Registry

---

## 参考架构: Hermes Agent

```
hermes-agent/
├── tools/
│   ├── registry.py          ← 核心：单例 ToolRegistry (RLock + 代际计数器)
│   ├── skills_tool.py       ← skills_list / skill_view / skill_manage
│   ├── mcp_tool.py          ← MCP Client (stdio/sse/http 连接 + 工具桥接)
│   └── *.py                 ← 各工具模块 (import 时自注册)
├── agent/
│   ├── agent_init.py        ← Agent 初始化 (provider 发现、工具发现、context engine)
│   ├── conversation_loop.py ← 核心对话循环 (LLM → tools → LLM → reply)
│   ├── system_prompt.py     ← 三段式 system prompt 组装
│   ├── tool_executor.py     ← 串行/并发工具执行 (ThreadPoolExecutor)
│   ├── tool_guardrails.py   ← 工具调用安全门禁
│   ├── skill_utils.py       ← Skill 元数据解析 + 平台过滤
│   └── ...
├── mcp_serve.py             ← MCP Server (将 Hermes 暴露为 MCP 工具)
└── providers/               ← LLM Provider 注册表
```

**关键设计模式**：

1. **Registry 自注册**：每个工具文件在模块级调用 `registry.register(name, toolset, schema, handler)`
2. **check_fn + TTL 缓存**：工具可用性检查函数带 30 秒缓存，避免频繁探测外部状态
3. **Skill 纯文档**：Skill = SKILL.md (YAML frontmatter + Markdown 内容)，通过内置工具暴露给 LLM
4. **MCP 动态注册**：MCP 工具以 `mcp-{server}` 为 toolset 前缀，支持 server refresh 时 nuke-and-repave
5. **System Prompt 稳定层**：身份 + 工具引导 + Skill 索引 在整个会话期间不变，保持 prompt cache 热度

---

## 整体架构

### 重构前后对比

```
BEFORE:                                 AFTER:
───────                                 ──────

toolkit/core/                           toolkit/core/
├── hookspecs.py                        ├── hookspecs.py
├── skill_registry.py  (仅扫描)         ├── tool_registry.py    ← NEW
├── mcp_server.py      (依赖 agent_chat)├── tool_executor.py    ← NEW
└── ...                                 ├── skill_registry.py   ← 增强
                                        ├── mcp/                ← NEW
modules/agent_chat/                     │   ├── server.py
├── src/                                │   ├── client.py
│   ├── tools/registry.py               │   └── registry.py
│   ├── tools/executor.py               └── ...
│   ├── skills/ (discovery/loader/...)
│   ├── mcp/ (connection/manager/...)   toolkit/agent/          ← NEW
│   ├── service.py (AgentService)       ├── orchestrator.py
│   ├── models.py                       ├── service.py
│   └── gui_tab.py (AgentTab)           ├── system_prompt.py
└── ...                                 ├── models.py
                                        ├── memory/
modules/perfetto_analysis/              ├── workflow/
├── src/plugin.py                       ├── gui/
│   └── register_agent_tools()          │   └── agent_panel.py
│       → pa_execute_sql (裸方法)       └── ...
│
│                                       modules/perfetto_analysis/
                                        ├── skills/perfetto-analysis/
                                        │   └── SKILL.md         ← 封装为 Skill
                                        └── src/plugin.py
                                            └── register_skills()
                                            └── register_mcp()   ← 或 MCP Tool
```

### 目标目录结构

```
toolkit/
├── core/
│   ├── hookspecs.py              # pluggy 钩子规范
│   ├── tool_registry.py          # ★ 统一工具注册中心 (借鉴 Hermes)
│   ├── tool_executor.py          # ★ 工具执行器 (串行/并发)
│   ├── skill_registry.py         # ★ 增强: Skill 发现 + 元数据索引 + 内容读取
│   ├── mcp/                      # ★ MCP 统一框架
│   │   ├── __init__.py
│   │   ├── server.py             #   MCP Server (FastMCP, 对外暴露工具)
│   │   ├── client.py             #   MCP Client (连接外部 MCP, 原 ConnectionPool)
│   │   ├── registry.py           #   MCP 注册中心 (local/external/remote)
│   │   └── tool_bridge.py        #   MCP 工具 → ToolDefinition 桥接
│   ├── ...                        #   (config_manager, db_manager, event_bus 等不变)
│   └── llm/                       #   LLM Manager (不变, 由 agent 消费)
│       ├── manager.py
│       ├── litellm_provider.py
│       └── models.py
│
├── agent/                         # ★ 重命名自 modules/agent_chat/
│   ├── __init__.py
│   ├── orchestrator.py           # AgentOrchestrator: 初始化 + 工具发现 + 生命周期
│   ├── service.py                # AgentService: 对话循环 (User→LLM→Tools→Reply)
│   ├── system_prompt.py          # 三段式 System Prompt 组装
│   ├── models.py                 # Agent 专属数据模型
│   ├── memory/                   # 对话存储
│   │   └── conversation.py       #   ConversationStore
│   ├── knowledge/                # 知识索引
│   │   └── report_index.py       #   ReportIndex
│   ├── workflow/                 # 工作流追踪
│   │   ├── tracker.py            #   WorkflowTracker
│   │   └── generator.py          #   SOP 生成
│   ├── gui/                      # GUI
│   │   └── agent_panel.py        #   AgentPanel (右侧可展开面板)
│   └── strings_gui.py            # GUI 字符串常量
│
├── gui/                          # 框架 GUI (不变)
│   ├── main_window.py            #   修改: Agent 从 Tab 改为右侧面板
│   ├── base_tab.py
│   ├── styles.py
│   └── ...

modules/                           # 业务模块 (适配新的注册方式)
├── perfetto_analysis/
│   ├── skills/                   # Skill 文档
│   └── src/plugin.py             # register_skills() → SkillRegistry
├── device_disguise/
│   ├── skills/
│   └── src/plugin.py
├── game_perf/
├── perfetto_capture/
├── perfdog_insights/
├── llm_manager/                  # LLM Provider 管理 (不变)
└── workspace_tools/
```

---

## 数据流

### 启动注册流

```
app.py main()
  │
  ├─ _build_context()
  │   ├─ ToolRegistry()            ← 创建空注册中心
  │   ├─ SkillRegistry()           ← 创建空 Skill 索引
  │   ├─ MCPRegistry()             ← 创建空 MCP 注册中心
  │   └─ ... (其他 core 服务)
  │
  ├─ _load_plugins()
  │   ├─ pm.load_all()             ← 发现所有模块
  │   ├─ pm.hook.on_startup()      ← 模块初始化
  │   └─ pm.hook.register_skills() ← 收集 SKILL.md 路径 → SkillRegistry
  │
  ├─ AgentOrchestrator.init(context)
  │   ├─ tool_registry.collect_from_plugins(pm)
  │   │   └─ pm.hook.register_agent_tools()  ← 模块工具注册
  │   ├─ skill_registry.get_skills()          ← 获取 Skill 索引
  │   ├─ mcp_registry.connect_all()           ← 连接外部 MCP
  │   │   └─ tool_registry.register_mcp_tools() ← MCP 工具注入
  │   └─ 构建统一工具视图
  │
  └─ MainWindow(context)
      └─ AgentPanel(orchestrator)   ← 右侧面板
```

### 对话执行流

```
User Input (AgentPanel)
  │
  ▼
AgentService.chat(user_message)
  │
  ├─ 1. 组装 System Prompt
  │   ├─ Stable:  身份 + Skill 索引摘要 + 工具引导
  │   ├─ Context: 当前上下文文件
  │   └─ Volatile: Memory 快照 + 时间戳
  │
  ├─ 2. 加载对话历史 (ConversationStore)
  │
  ├─ 3. LLM 调用 (通过 LLMManager.get_provider())
  │   └─ Provider.stream_chat(messages, tools, system_prompt)
  │
  ├─ 4. 解析响应
  │   ├─ text → 流式输出到 AgentPanel
  │   └─ tool_calls → 进入工具执行
  │
  ├─ 5. 工具执行循环 (max 10 轮)
  │   │
  │   ├─ ToolRegistry.dispatch(name, args)
  │   │   ├─ 查找 ToolEntry
  │   │   ├─ 执行 handler (async/sync 自动桥接)
  │   │   └─ 序列化结果
  │   │
  │   ├─ 结果注入 messages
  │   └─ 回到步骤 3 (递归)
  │
  └─ 6. 保存对话 + 返回完整响应
```

### 工具发现与调用流

```
┌─────────────────────────────────────────────────────────┐
│                  ToolRegistry (统一入口)                  │
│                                                         │
│  get_definitions() → LLM Function Calling 格式工具列表    │
│  dispatch(name, args) → 执行工具并返回结果                │
└──────────────┬──────────────────────────────────────────┘
               │
   ┌───────────┼───────────┬──────────────┐
   │           │           │              │
   ▼           ▼           ▼              ▼
┌──────┐ ┌──────┐ ┌──────────┐ ┌──────────────┐
│Skill │ │Module│ │MCP Local │ │MCP External  │
│Tools │ │Tools │ │(子模块)  │ │(stdio/sse)   │
├──────┤ ├──────┤ ├──────────┤ ├──────────────┤
│skill │ │内置  │ │子模块通过 │ │外部 MCP      │
│_list │ │工具  │ │MCP协议注册│ │Server 连接   │
│skill │ │      │ │          │ │              │
│_load │ │      │ │          │ │              │
└──────┘ └──────┘ └──────────┘ └──────────────┘
```

**工具命名规范**：

| 来源 | 前缀/命名 | 示例 |
|------|----------|------|
| Skill 工具 | `skill_*` | `skill_list`, `skill_load`, `skill_load_resource` |
| Agent 内置 | `agent_*` 或无前缀 | `create_workspace`, `list_workspace_files` |
| 模块 MCP (local) | `mcp__local__{module}__{tool}` | `mcp__local__perfetto_analysis__execute_sql` |
| 外部 MCP | `mcp__{server}__{tool}` | `mcp__github__search_repos` |

---

## 关键模块细分设计

### Core: ToolRegistry

**设计来源**：借鉴 Hermes `tools/registry.py` 的 ToolRegistry 单例模式。

```python
# toolkit/core/tool_registry.py

import threading
import time
from typing import Callable, Optional

class ToolEntry:
    """单个工具的元数据 + 处理器。"""
    __slots__ = (
        "name", "toolset", "schema", "handler",
        "check_fn", "is_async", "description",
        "max_result_size_chars", "dynamic_schema_overrides",
    )

class ToolRegistry:
    """线程安全单例工具注册中心。

    收集三种来源的工具：
    1. 模块通过 register_agent_tools() hook 注册
    2. Skill 系统生成的 skill_* 工具
    3. MCP 框架桥接的外部工具
    """

    def __init__(self):
        self._tools: dict[str, ToolEntry] = {}
        self._toolset_checks: dict[str, Callable] = {}
        self._lock = threading.RLock()
        self._generation: int = 0

    def register(self, name, toolset, schema, handler, *,
                 check_fn=None, is_async=False, description="",
                 max_result_size_chars=None,
                 dynamic_schema_overrides=None,
                 override=False) -> None:
        """注册工具。override=True 允许同 toolset 内覆盖。"""
        ...

    def deregister(self, name: str) -> None:
        """注销工具（MCP 动态刷新使用）。"""
        ...

    def get_definitions(self, tool_names: set[str] | None = None) -> list[dict]:
        """返回 OpenAI Function Calling 格式的工具列表。
        仅包含 check_fn() 返回 True 的可用工具。
        check_fn 结果带 30 秒 TTL 缓存。
        """
        ...

    def dispatch(self, name: str, args: dict) -> str:
        """执行工具。async handler 自动桥接。异常统一捕获为 JSON error。"""
        ...

    def collect_from_plugins(self, plugin_manager) -> int:
        """从 pluggy hook 收集模块注册的工具。"""
        ...

    def register_mcp_tools(self, definitions: list) -> int:
        """批量注册 MCP 桥接工具，返回新增数量。"""
        ...

    def unregister_by_prefix(self, prefix: str) -> int:
        """按前缀注销工具（MCP server 下线时清理）。"""
        ...

# 模块级单例
tool_registry = ToolRegistry()
```

**与现有实现的差异**：
- 现有 `ToolRegistry._enhance_schema()` 自动生成 JSON Schema → 保留
- 新增 `check_fn` 机制：模块可提供"工具是否可用"的检查函数
- 新增 `toolset` 分组：按模块/Skill/MCP 来源分组
- 新增 `dynamic_schema_overrides`：支持运行时动态修改工具描述

### Core: SkillRegistry

**设计来源**：整合现有的 `toolkit/core/skill_registry.py`(扫描) + `agent_chat/src/skills/discovery.py`(发现) + `agent_chat/src/skills/loader.py`(三级加载)。

```python
# toolkit/core/skill_registry.py (增强版)

class SkillMetadata:
    """Skill 元数据（从 SKILL.md YAML frontmatter 解析）。"""
    name: str
    version: str = "1.0.0"
    description: str = ""
    tags: list[str] = []
    triggers: list[str] = []        # 触发关键词
    platforms: list[str] = []       # 平台限制 (windows/linux/macos)
    prerequisites: dict = {}        # 前置依赖 (env_vars, commands)
    file_path: Path                 # SKILL.md 绝对路径
    skill_dir: Path                 # Skill 目录

class SkillRegistry:
    """Skill 发现 + 元数据索引 + 内容读取。

    Core 层面只负责：
    1. 扫描搜索路径，发现 SKILL.md 文件
    2. 解析 YAML frontmatter，提取元数据
    3. 提供 get_content() / get_resource() 内容读取

    Agent 层面负责：
    1. 意图匹配路由
    2. 生成 skill_* 工具注入 ToolRegistry
    3. 运行时 Skill 加载决策
    """

    def __init__(self):
        self._skills: dict[str, SkillMetadata] = {}

    # ── 发现与扫描 ──
    def add_search_path(self, path: Path) -> None: ...
    def scan(self) -> list[SkillMetadata]: ...
    def load_from_paths(self, paths: list[str]) -> None: ...

    # ── 索引查询 ──
    def get_skills(self) -> list[SkillMetadata]: ...
    def get_skill(self, name: str) -> SkillMetadata | None: ...
    def search(self, keyword: str) -> list[SkillMetadata]: ...

    # ── 内容读取 ──
    def get_content(self, name: str) -> str | None: ...
    def get_resource(self, name: str, rel_path: str) -> str | None: ...
    def list_resources(self, name: str) -> dict[str, list[str]]: ...

    # ── 平台过滤 ──
    def get_platform_skills(self) -> list[SkillMetadata]: ...
```

**Skill 目录结构规范** (继承现有 + 对齐 Hermes)：

```
modules/<name>/skills/<skill-name>/
├── SKILL.md              # 主文件 (YAML frontmatter + Markdown)
├── sop/                  # 操作流程
│   └── jank-analysis.md
├── patterns/             # 分析模式
│   └── frame-patterns.md
├── cases/                # 案例库
│   └── case-001.md
└── ref/                  # 参考资料
    └── perfetto-sql.md
```

### Core: MCP Framework

**设计来源**：提升现有 `agent_chat/src/mcp/` + 借鉴 Hermes `tools/mcp_tool.py`。

```
toolkit/core/mcp/
├── __init__.py
├── server.py           # MCP Server: 将 ToolRegistry 暴露为 MCP 工具 (现有 mcp_server.py)
├── client.py           # MCP Client: 连接外部 MCP Server (现有 connection.py)
├── registry.py         # MCP 注册中心: 管理 local/external/remote 三种来源
└── tool_bridge.py      # MCP 工具 → ToolDefinition 桥接 (现有 tool_bridge.py)
```

```python
# toolkit/core/mcp/registry.py

from enum import Enum

class MCPSource(str, Enum):
    LOCAL = "local"          # 子模块实现的 MCP 能力
    EXTERNAL = "external"    # 外部 stdio/sse MCP Server
    REMOTE = "remote"        # 远程 HTTP MCP Server

class MCPRegistry:
    """MCP 统一注册中心。

    三种注册方式：
    1. register_local(module_name, server_class)
       → 子模块实现 MCP Server 协议，同进程内调用
    2. register_external(server_config)
       → 外部进程 MCP Server (stdio/sse)，通过 MCP Client 连接
    3. register_remote(url, auth)
       → 远程 HTTP MCP 服务
    """

    def __init__(self, tool_registry: ToolRegistry):
        self._tool_registry = tool_registry
        self._servers: dict[str, MCPRegistration] = {}
        self._connections: dict[str, MCPConnection] = {}

    # ── 注册 ──
    def register_local(self, module: str, handler_class) -> None: ...
    def register_external(self, config: MCPServerConfig) -> None: ...
    def register_remote(self, url: str, auth: dict | None = None) -> None: ...

    # ── 连接管理 ──
    async def connect(self, name: str) -> MCPConnection: ...
    async def connect_all(self) -> list[MCPConnection]: ...
    async def disconnect(self, name: str) -> None: ...

    # ── 工具发现 ──
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    async def call_tool(self, server: str, tool: str, args: dict) -> Any: ...

    # ── 生命周期 ──
    def get_servers(self) -> dict: ...
    def remove_server(self, name: str) -> None: ...
```

**与现有实现的差异**：
- 新增 `register_local()`：子模块实现的 MCP 能力不需要独立进程
- 新增 `register_remote()`：支持远程 HTTP MCP
- MCP Server 和 MCP Client 统一在同一个 registry 管理

### Agent: AgentOrchestrator

```python
# toolkit/agent/orchestrator.py

class AgentOrchestrator:
    """Agent 生命周期管理 + 工具发现。

    职责：
    - 从 Core 获取 Skill/Tool/MCP 统一视图
    - 构建 System Prompt (三段式)
    - 管理 AgentService 实例
    - 处理配置变更 (Provider 切换等)
    """

    def __init__(self, context: dict):
        self._tool_registry: ToolRegistry = context["tool_registry"]
        self._skill_registry: SkillRegistry = context["skill_registry"]
        self._mcp_registry: MCPRegistry = context["mcp_registry"]
        self._llm_manager = context.get("llm_manager")

    # ── 初始化 ──
    def init_tools(self) -> list[ToolDefinition]:
        """构建统一工具视图。

        1. Agent 内置工具 (create_workspace, list_workspace_files)
        2. Skill 工具 (skill_list, skill_load, skill_load_resource, skill_list_resources)
        3. 模块注册工具 (仅限 Skill 封装后的)
        4. MCP 外部工具 (mcp__{server}__{tool})
        """
        ...

    def build_system_prompt(self, *, extra: str = "", conv_id: str = "") -> str:
        """三段式 System Prompt 组装。"""
        ...

    # ── 对话 ──
    def create_service(self) -> AgentService:
        """创建 AgentService 实例。"""
        ...

    # ── 配置变更 ──
    def on_provider_changed(self, provider_name: str) -> None: ...
    def on_skills_changed(self) -> None: ...
    def on_mcp_changed(self) -> None: ...
```

### Agent: System Prompt 三段式

**设计来源**：借鉴 Hermes `agent/system_prompt.py` 的三段式设计。

```python
# toolkit/agent/system_prompt.py

def build_system_prompt(
    *,
    tools: list[ToolDefinition],
    skills: list[SkillMetadata],
    language: str = "zh",
    extra: str = "",
    report_index: ReportIndex | None = None,
) -> str:
    """组装三段式 System Prompt。

    Stable (稳定层 - 会话期间不变):
      - 身份声明
      - 工具列表摘要
      - Skill 索引摘要
      - 工具使用指导

    Context (上下文层 - 按对话变化):
      - 用户提供的上下文文件
      - 额外的 system_message

    Volatile (易变层 - 每次请求变化):
      - Memory 快照
      - 时间戳 / 会话 ID
    """

    stable = _build_stable_prompt(tools, skills, language)
    context = _build_context_prompt(extra)
    volatile = _build_volatile_prompt()

    return "\n\n".join([stable, context, volatile])
```

**Stable 层内容**：

```
# 身份
你是 LV Game Toolkit 的智能助手，专注于游戏性能分析与测试工具。

# 可用工具
- skill_list: 列出所有可用 Skill 及其描述、标签
- skill_load: 加载指定 Skill 的完整内容
- skill_load_resource: 加载 Skill 子资源
- skill_list_resources: 列出 Skill 子资源目录
- create_workspace: 创建分析工作目录
- list_workspace_files: 列出工作目录文件
- mcp__perfetto_analysis__execute_sql: [MCP] 执行 PerfettoSQL 查询
- mcp__device_disguise__push_config: [MCP] 推送设备伪装配置
...

# 可用 Skill
- perfetto-analysis: Perfetto Trace 性能分析，含卡顿/Jank/帧率分析方法论
- device-disguise: Android 设备信息伪装，用于绕过游戏设备检测
- knowledge-curator: 知识管理与经验沉淀
...

# 使用指导
- 复杂任务 (5+ 工具调用) 完成后，考虑沉淀为新的 Skill
- 遇到新的分析模式时，使用 skill_manage 保存经验
- 不确定使用哪个工具时，先用 skill_list 查看可用 Skill
```

**System Prompt 长度控制**：
- Stable 层 ≤ 3000 字符（工具列表 + Skill 索引摘要）
- 超过时裁剪 Skill 索引为仅名称列表
- 报告上下文超过 500 字符时截断为最近 3 条

### Agent: GUI AgentPanel

**设计来源**：继承现有右侧面板基础设施，将 Agent 从中央 Tab 改造为右侧面板。

```python
# toolkit/agent/gui/agent_panel.py

class AgentPanel(QWidget):
    """Agent 右侧可展开面板。

    生命周期：
    - 默认折叠：仅显示窄条 (24px) + 图标，不干扰主工作区
    - 点击展开：宽度 ~360px，挤压中央内容区
    - 支持拖拽调整宽度 (240px ~ 480px)
    """

    # ── 信号 ──
    panel_expanded = pyqtSignal()
    panel_collapsed = pyqtSignal()
    message_sent = pyqtSignal(str)

    # ── 内容组件 ──
    # 复用现有 AgentTab 的消息渲染组件:
    #   _UserMessageWidget, _AgentTextWidget, _ToolCallCard, _TokenUsageLabel
    # 移除:
    #   会话 Tab 栏 (顶部) → 简化为标题 + 新建/历史下拉
    #   欢迎页 → 折叠状态下不可见，展开后显示
    #   设置弹窗 → 迁移到设置 → Agent 菜单
    #   快捷按钮 → 精简
```

**面板布局**：

```
┌─────────────────────────┐
│ Agent 智能助手    [+][×] │  ← 标题栏 (36px)
├─────────────────────────┤
│                         │
│  ┌───────────────────┐  │
│  │ 历史会话 | 新建   │  │  ← 会话选择 (compact)
│  └───────────────────┘  │
│                         │
│  ┌─ 消息区域 ─────────┐ │
│  │                    │ │
│  │  欢迎消息 / 对话   │ │
│  │                    │ │
│  │  用户消息 (右对齐) │ │
│  │  Agent 回复 (左)   │ │
│  │  工具调用卡片      │ │
│  │                    │ │
│  └────────────────────┘ │
│                         │
│  ┌─ 输入区 ───────────┐ │
│  │ [输入框]      [发送]│ │
│  └────────────────────┘ │
│                         │
└─────────────────────────┘
```

**与现有 MainWindow 的集成**：

```python
# toolkit/gui/main_window.py 变更

class MainWindow(QMainWindow):
    def __init__(self, context):
        ...
        # Agent 从 "set_agent_panel" 变为右侧面板
        self._agent_panel = AgentPanel(context)
        self._right_panel.add_widget("agent", self._agent_panel)

        # 不再有 agent_tab 特殊处理
        # 模块 Tab 统一通过 add_tab() 添加到中央区域
```

---

## 模块适配指南

### 模块能力暴露方式变更

**BEFORE** (直接暴露裸方法):

```python
# modules/perfetto_analysis/src/plugin.py
@hookimpl
def register_agent_tools(self) -> list:
    return [
        {"name": "pa_execute_sql", "description": "...", "method": execute_sql},
        {"name": "pa_get_slice", "description": "...", "method": get_slice},
    ]
```

**AFTER** (封装为 Skill):

```python
# modules/perfetto_analysis/skills/perfetto-analysis/SKILL.md
---
name: perfetto-analysis
description: Perfetto Trace 性能分析
version: 1.0.0
tags: [perfetto, trace, jank, fps]
triggers: [分析trace, 卡顿, jank, 帧率, 渲染性能]
platforms: [windows, linux, macos]
---

# Perfetto Trace 性能分析

## 适用场景
- 需要分析 Android/Chrome Perfetto trace 文件
- 诊断游戏卡顿 (Jank)、丢帧问题
- 评估帧率稳定性

## 使用方式
调用 `mcp__local__perfetto_analysis__execute_sql` 执行 PerfettoSQL 查询。
...
```

```python
# modules/perfetto_analysis/src/plugin.py
@hookimpl
def register_skills(self) -> list[str]:
    return [str(_SKILL_DIR / "SKILL.md")]

@hookimpl
def register_agent_tools(self) -> list:
    return []  # 不再直接暴露裸方法
```

### 如果模块必须暴露可执行能力

使用 MCP Local 方式：

```python
# modules/perfetto_analysis/src/plugin.py
@hookimpl
def on_startup(self, context: dict) -> None:
    mcp_registry = context["mcp_registry"]
    mcp_registry.register_local(
        module="perfetto_analysis",
        handler_class=PerfettoAnalysisMCPHandler,
    )
```

---

## 迁移路径

### Phase 1: 基础设施下沉 (不改逻辑，只移动)

**目标**：打破循环依赖，建立正确的依赖方向。

| 步骤 | 操作 | 影响 |
|------|------|------|
| 1.1 | `ToolRegistry` + `ToolExecutor` 从 `modules/agent_chat/src/tools/` → `toolkit/core/` | `mcp_server.py` 不再反向依赖模块 |
| 1.2 | `ToolCall` / `ToolResult` / `ToolDefinition` 等核心模型移至 `toolkit/core/models.py` | 解决跨层 import |
| 1.3 | `modules/agent_chat/src/mcp/` 整体提升至 `toolkit/core/mcp/` | MCP 框架统一 |
| 1.4 | `SkillRegistry` 增强：合并 `agent_chat/src/skills/discovery.py` 的扫描能力 | Skill 单轨制 |
| 1.5 | agent_chat 内部引用更新为新的 import 路径 | 功能不变 |

### Phase 2: Agent 重构

**目标**：从模块提升为框架级组件，UI 改造。

| 步骤 | 操作 | 影响 |
|------|------|------|
| 2.1 | `modules/agent_chat/` → `toolkit/agent/`，重命名 `AgentChatPlugin` → `AgentPlugin` | 命名修正 |
| 2.2 | 引入 `AgentOrchestrator`，重构初始化流程 | 统一工具视图 |
| 2.3 | System Prompt 三段式重构 | 更好的 LLM 行为引导 |
| 2.4 | `AgentService` 使用新的 Core 接口 | 移除内部 ToolRegistry/Provider fallback |
| 2.5 | GUI: `AgentTab` → `AgentPanel` 右侧面板 | UI 位置变更 |
| 2.6 | SOP 系统合并到 Skill 体系：SOPManager/WorkflowTracker/Generator 适配 SKILL.md 格式 | 统一知识载体 |
| 2.7 | 移除 `SubAgentManager` 空占位实现，保留 `SubAgentConfig`/`SubAgentResult` 模型占位 | 推迟到后续需求 |

### Phase 3: 模块适配

**目标**：模块统一走 Skill/MCP 暴露能力。

| 步骤 | 操作 | 影响 |
|------|------|------|
| 3.1 | `perfetto_analysis`: 编写 SKILL.md，移除直接工具注册 | Agent 通过 Skill 发现分析能力 |
| 3.2 | `device_disguise`: 已有 Skill，验证+补全 | 已有基础 |
| 3.3 | `game_perf`: 按需评估 | 可能不需要 Agent 集成 |
| 3.4 | 清理旧的 `AgentConfig` 中已废弃的 LLM 字段 | 完全依赖 llm_manager |

---

## 已确认决策

以下 4 个设计问题已经过讨论并做出决策（2026-05-26）：

| # | 问题 | 决策 | 理由 |
|---|------|------|------|
| 1 | **SOP 系统去留** | **合并到 Skill 体系** | SOP 本质是结构化操作流程，可作为特殊 Skill；`SOPManager` 职责由 `SkillRegistry` + Agent 工具替代；`WorkflowTracker` 沉淀触发改为"保存为新 Skill"而非"保存为新 SOP" |
| 2 | **SubAgent 实现范围** | **Phase 2 不实现，保留模型占位** | 当前 Agent 工具调用循环 (max 10 轮) 已能处理多步骤任务；`SubAgentConfig`/`SubAgentResult` 模型保留，`SubAgentManager` 空实现移除，`AgentOrchestrator` 预留 `spawn_subagent()` 接口 |
| 3 | **Toolset 分组** | **预留 toolset 字段，暂不分组** | `ToolEntry.toolset` 字段已在架构中就绪；当前工具数量 < 20，分组收益有限；待工具 > 30 或出现明确分场景需求时再引入 |
| 4 | **Agent 独立窗口** | **不做独立窗口，仅右侧面板** | Agent 作为右侧面板已满足主要使用场景；弹出窗口功能推迟到后续有明确需求时再评估 |

## 风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Phase 1 import 路径大规模变更 | 测试大面积失败 | 逐步迁移，每个步骤跑全量测试 |
| AgentPanel 右侧面板交互体验 | 用户不习惯 | 右侧面板已有成熟基础设施，展开/折叠行为可配置 |
| Skill 封装后 LLM 工具选择准确率下降 | 分析任务失败 | 在 SKILL.md 中写清楚工具名称和调用方式 |
| MCP Local 模式性能开销 | 同进程调用多一层协议开销 | 评估后可选择直连模式 |

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-05-26 | 初始版本：整体架构 + 数据流 + 模块细分设计 |
| 2026-05-26 | 状态 → active；Speckit spec/plan/tasks 完成；4 项设计决策确认 |
| 2026-05-26 | 状态 → implemented；80/80 任务完成；217/217 测试通过；SC-004/SC-006 验证 |
