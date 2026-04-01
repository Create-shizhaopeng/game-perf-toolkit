# Implementation Plan: MCP 管理、Skills 扩展管理、Sub-agent 支持

**Input**: [spec.md](spec.md)  
**Feature Branch**: `002-mcp-skills-subagent`

## 目录

- [Architecture Design](#architecture-design)
  - [异步架构改造](#异步架构改造)
  - [MCP 管理层](#mcp-管理层)
  - [Skills 管理层](#skills-管理层)
  - [Sub-agent 编排层](#sub-agent-编排层)
  - [工具统一注册](#工具统一注册)
- [数据模型](#数据模型)
- [实施阶段](#实施阶段)
- [设计原则](#设计原则)
- [Project Structure](#project-structure)

## Architecture Design

### 异步架构改造

将 agent_chat 模块内部全面转异步，不影响其他模块。

```
改造前（同步）                     改造后（异步）
─────────────────                 ─────────────────
CLI/GUI                          CLI: asyncio.run()
  ↓ sync                         GUI: QThread + event_loop
AgentService.chat()              AgentService.chat()  ← async def
  ↓ sync                           ↓ async
LLMProvider.stream_chat()        LLMProvider.stream_chat()  ← AsyncIterator
  ↓ sync                           ↓ async
ToolExecutor.execute()           ToolExecutor.execute()  ← async def
  ↓ sync                           ├ async tools: await directly
  本地工具                          └ sync tools: asyncio.to_thread()
```

**关键接口变更**：

| 接口 | 改造前 | 改造后 |
|------|--------|--------|
| `LLMProvider.stream_chat()` | `Iterator[StreamChunk]` | `AsyncIterator[StreamChunk]` |
| `AgentService.chat()` | `def chat(...)` | `async def chat(...)` |
| `ToolExecutor.execute()` | `def execute(...)` | `async def execute(...)` |
| `MCPManager` (新) | — | 全异步，`async def connect/call_tool` |
| CLI 入口 | 直接调用 | `asyncio.run(main())` |
| GUI Worker | `QThread.run()` 同步调用 | `QThread.run()` 内启动 `asyncio.EventLoop` |

### MCP 管理层

```
MCPManager
├── ServerRegistry          ← 从 mcp_servers.json 加载配置
│   └── MCPServerConfig[]   ← name, command, args, env, transport
├── ConnectionPool          ← 管理活跃连接
│   └── MCPConnection[]     ← session, status, available_tools
└── ToolBridge              ← MCP 工具 → ToolDefinition 转换
    └── register_to(ToolRegistry)
```

**连接流程**：

```
启动 → 读 mcp_servers.json → 遍历配置
  → StdioServerParameters / SSE 连接
  → session.initialize()
  → session.list_tools()
  → 转换为 ToolDefinition 注册到 ToolRegistry
```

**降级策略**：MCP 工具优先使用。本地同功能工具以 `local_` 前缀注册。当 MCP 工具调用失败时，ToolExecutor 自动降级到 `local_` 前缀的同名工具。

**版本管理**：启动时检查 `mcp` 包版本，记录到日志。配置中可设置 `sdk_version_check: true`，当检测到新稳定版时在 GUI 中提示。

### Skills 管理层

```
SkillManager
├── SkillDiscovery          ← 扫描搜索路径
│   ├── modules/*/skills/*/SKILL.md
│   └── 用户配置的额外路径
├── SkillRouter             ← 意图匹配
│   └── match(user_message) → SkillMetadata | None
└── SkillLoader             ← 三级渐进式加载
    ├── Level 1: 元数据列表 → system prompt
    ├── Level 2: SKILL.md 完整内容 → system prompt
    └── Level 3: skill_load_resource 工具 → 按需加载子资源
```

**搜索路径解析**：

```python
default_paths = [
    "modules/*/skills/*/SKILL.md",  # 模块提供
]
user_paths = config.get("skill_search_paths", [])
```

**意图匹配**：基于 SKILL.md 的 `description` 字段关键词匹配。使用简单的 TF-IDF 或关键词交集评分，选择得分最高的一个 Skill。

**渐进式加载流程**：

```
初始化时:
  SkillDiscovery.scan() → [SkillMetadata, ...]
  SkillLoader.inject_metadata_list(system_prompt)  # ~20 行

每轮对话:
  SkillRouter.match(user_message) → matched_skill
  if matched_skill and not already_loaded:
    SkillLoader.inject_full_content(system_prompt, matched_skill)  # ~190 行

深度分析时:
  LLM 调用 skill_load_resource(skill_name, resource_path)
  → SkillLoader.load_resource() → 返回 SOP/pattern 内容
```

### Sub-agent 编排层

```
SubAgentManager
├── AgentFactory            ← 创建子 Agent 实例
│   ├── 独立 LLM 会话
│   ├── Skill 绑定 → 注入指定 Skill 到 system prompt
│   └── 工具过滤 → 仅暴露相关工具
├── ExecutionPool           ← 并发管理（最大 3 个）
└── ResultCollector         ← 收集结构化摘要
```

**子 Agent 生命周期**：

```
主 Agent 创建任务
  → AgentFactory.create(task, skill, provider, tools)
  → 子 Agent 独立 LLM 会话
  → 子 Agent 执行（可调用工具）
  → 完成后返回 SubAgentResult（摘要）
  → 失败时触发重试策略：
     1. 第 1 次自动重试
     2. 第 2 次失败 → 询问用户
     3. 最多 3 次
```

**Provider 能力标签**：

```python
class ProviderCapabilities:
    supports_tools: bool = True
    supports_vision: bool = False
    supports_streaming: bool = True
    max_context_tokens: int = 128000
```

### 工具统一注册

SOPManager 移除后，ToolRegistry 成为唯一的工具和知识管理入口。

```
ToolRegistry
├── 插件工具（sync）        ← 各模块 register_agent_tools
│   └── asyncio.to_thread() 桥接
├── MCP 工具（async）       ← MCPManager.ToolBridge
│   └── 优先使用，失败降级
├── 内置工具（sync）        ← builtin.py
│   └── create_workspace, list_files
└── Skill 工具（sync）      ← SkillManager 注册
    └── skill_load_resource, skill_list
```

## 数据模型

### 新增 Pydantic 模型

```python
class MCPServerConfig(BaseModel):
    name: str
    command: str
    args: list[str] = []
    env: dict[str, str] = {}
    transport: str = "stdio"  # "stdio" | "sse"
    timeout: int = 30
    enabled: bool = True

class MCPConnectionStatus(str, Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"

class MCPConnection(BaseModel):
    server_name: str
    status: MCPConnectionStatus
    available_tools: list[str] = []
    last_error: str | None = None
    connected_at: datetime | None = None

class SkillMetadata(BaseModel):
    name: str
    description: str
    source_path: Path
    source_module: str | None = None
    sub_resources: list[str] = []

class SkillContext(BaseModel):
    """注入到 LLM 的 Skill 上下文（替代原 SOPDocument）"""
    skill_name: str
    content: str  # SKILL.md 完整内容或元数据摘要
    loaded_resources: list[str] = []  # 已加载的子资源路径
    level: int = 1  # 当前加载级别 (1=元数据, 2=完整内容, 3=含子资源)

class SubAgentConfig(BaseModel):
    task: str
    skill_binding: str | None = None
    provider: str | None = None  # None = 使用主 Agent 的 Provider
    tools_filter: list[str] | None = None
    max_tokens: int = 4096

class SubAgentResult(BaseModel):
    task_description: str
    summary: str
    confidence: float = 0.0
    elapsed_ms: int = 0
    provider_used: str = ""
    success: bool = True
    error: str | None = None
    retry_count: int = 0

class ProviderCapabilities(BaseModel):
    supports_tools: bool = True
    supports_vision: bool = False
    supports_streaming: bool = True
    max_context_tokens: int = 128000
```

### 配置文件扩展

`data/config.json` 新增字段：

```json
{
  "mcp_servers_path": "mcp_servers.json",
  "skill_search_paths": [],
  "subagent_max_concurrent": 3,
  "subagent_max_retries": 3,
  "multi_provider_enabled": false,
  "sdk_version_check": true
}
```

`data/mcp_servers.json`（新文件）：

```json
{
  "servers": {
    "perfetto-mcp": {
      "command": "npx",
      "args": ["-y", "@anthropic/perfetto-mcp-server"],
      "transport": "stdio",
      "enabled": true
    }
  }
}
```

## 实施阶段

### Phase 1: 异步架构改造（基础）

1. `LLMProvider.stream_chat()` 改为 `AsyncIterator`
2. `GlmProvider` 和 `ClaudeProvider` 适配异步
3. `ToolExecutor.execute()` 改为 `async def`，桥接同步工具
4. `AgentService.chat()` 改为 `async def`
5. CLI 入口适配 `asyncio.run()`
6. GUI `_AgentWorker` 适配异步 event loop
7. 所有现有测试适配 `pytest-asyncio`

### Phase 2: MCP 管理

8. 创建 `MCPServerConfig` 和 `MCPConnection` 模型
9. 实现 `MCPManager`（连接池、生命周期、工具发现）
10. 实现 `ToolBridge`（MCP 工具 → ToolDefinition 转换）
11. MCP 工具注册到 ToolRegistry + 降级策略
12. `mcp_servers.json` 配置文件支持
13. MCP 管理 GUI 面板

### Phase 3: Skills 扩展管理 + SOP 移除

14. 创建 `SkillMetadata` 模型
15. 实现 `SkillDiscovery`（搜索路径扫描）
16. 实现 `SkillRouter`（意图匹配）
17. 实现 `SkillLoader`（三级渐进式加载）
18. 注册 `skill_load_resource` 和 `skill_list` Agent 工具
19. Skill 管理 GUI 面板（替代原 SOP 管理面板）
20. 移除 SOPManager 及相关代码（`src/sop/`、models.py 中的 SOPDocument/SOPSource）
21. 移除全部编排类 SOP 文件，清理 `assets/sops/` 和 `data/sops/` 目录
22. 更新 `service.py`、`gui_tab.py`、`cli_commands.py` 中的 SOP 引用为 Skill 引用

### Phase 3.5: knowledge-curator Skill

23. 创建 `knowledge-curator` Skill 骨架（SKILL.md 描述 + 流程步骤 + 模板占位）
24. 实现 `kc_classify_document` 工具（文档内容分类）
25. 实现 `kc_match_skill` 工具（内容→目标 Skill 匹配）
26. 实现 `kc_format_resource` + `kc_write_resource` 工具（格式化 + 写入）
27. 在 Cursor 中验证 Skill 流程（手动测试原始文档→结构化子资源的完整链路）

### Phase 4: Sub-agent 编排

28. 创建 `SubAgentConfig` 和 `SubAgentResult` 模型
29. 实现 `SubAgentManager`（创建、执行、结果收集）
30. 实现 `AgentFactory`（独立会话 + Skill 绑定）
31. 三次重试策略
32. `ProviderCapabilities` 能力标签
33. `create_sub_agent` Agent 工具注册

### Phase 5: 001 缺口修复 + 打包支持

34. CLI `agent ask` 集成 PluginManager 工具注册
35. 上下文截断策略优化（SOP 上下文 → Skill 上下文）
36. PerfDog 报告索引完善
37. WorkflowTracker 移除 SOP 绑定，改为 Skill 绑定
38. 修改 `scripts/build.py` 的 `_collect_modules()` ，对 `skills/` 子目录取消 `.md` 过滤
39. 验证打包产物中 Skill 目录结构完整且 SkillDiscovery 可正常扫描

### Phase 6: 测试与文档

40. 各新增模块的单元测试（含 SOPManager 移除后的回归测试）
41. 集成测试（MCP + Skill + Sub-agent + knowledge-curator 协同）
42. 文档更新

## 设计原则

1. **不影响其他模块**：异步改造通过 `asyncio.to_thread()` 桥接同步工具，其他模块无需修改
2. **渐进式交付**：每个 Phase 独立可用，不需要全部完成才能使用
3. **避免过度设计**：Skill 匹配用简单关键词而非复杂 NLP；Sub-agent 在同进程内执行而非独立进程
4. **一致的降级策略**：MCP 不可用降级到本地工具；Provider 不支持工具调用降级到纯文本

## Project Structure

```text
modules/agent_chat/src/
├── mcp/                    # 新增: MCP 管理
│   ├── __init__.py
│   ├── manager.py          # MCPManager
│   ├── connection.py       # ConnectionPool
│   └── tool_bridge.py      # MCP → ToolDefinition
├── skills/                 # 新增: Skills 管理（替代原 sop/）
│   ├── __init__.py
│   ├── discovery.py        # SkillDiscovery
│   ├── router.py           # SkillRouter
│   └── loader.py           # SkillLoader
├── subagent/               # 新增: Sub-agent
│   ├── __init__.py
│   ├── manager.py          # SubAgentManager
│   ├── factory.py          # AgentFactory
│   └── result.py           # ResultCollector
├── llm/
│   ├── base.py             # 修改: AsyncIterator
│   ├── glm_provider.py     # 修改: async
│   └── claude_provider.py  # 修改: async
├── tools/
│   ├── executor.py         # 修改: async + 同步桥接
│   └── registry.py         # 修改: MCP/Skill 工具注册
├── service.py              # 修改: async + 移除 SOPManager 依赖
├── gui_tab.py              # 修改: async Worker + MCP/Skill 面板（移除 SOP 面板）
├── cli_commands.py         # 修改: asyncio.run
├── models.py               # 修改: 新增数据模型 + 移除 SOPDocument/SOPSource
└── [删除] sop/             # SOPManager 代码整体移除

modules/agent_chat/skills/
└── knowledge-curator/      # 新增: 知识策展 Skill
    ├── SKILL.md             # Skill 定义（描述 + 流程）
    └── templates.md         # 子资源格式化模板（SOP/Pattern/Case）
```

打包相关变更：

```text
scripts/build.py            # 修改: _collect_modules() 对 skills/ 子目录取消 .md 过滤
```
