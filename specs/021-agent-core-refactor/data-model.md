# Data Model: Agent 核心重构

**Feature**: 021-agent-core-refactor | **Date**: 2026-05-26

## 核心实体

### ToolEntry

单个工具的注册信息。注册在 `ToolRegistry` 中，每个条目包含工具的完整定义和执行所需的所有元数据。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | 是 | 工具唯一标识。命名规范：`skill_*`（Skill 工具）、`mcp__*`（MCP 工具）、`agent_*`（Agent 内置）或无前缀 |
| `toolset` | `str` | 是 | 来源分组：`"skill"`、`"agent"`、`"module"`、`"mcp-local"`、`"mcp-external"` |
| `schema` | `dict` | 是 | OpenAI Function Calling 格式的 JSON Schema（含 `type`, `properties`, `required`） |
| `handler` | `Callable` | 是 | 可调用方法。async handler 由 dispatch 自动桥接 |
| `check_fn` | `Callable \| None` | 否 | 工具可用性检查函数。返回 `bool`。注册时自动按 toolset 分组缓存，结果带 30s TTL |
| `is_async` | `bool` | 否 | handler 是否为 async 函数（默认 `False`） |
| `description` | `str` | 否 | 工具描述，从 schema 自动提取 |
| `max_result_size_chars` | `int \| None` | 否 | 结果最大字符数，超过截断 |
| `dynamic_schema_overrides` | `Callable \| None` | 否 | 零参可调用，返回 dict，在 `get_definitions()` 时合并到 schema |

**唯一性规则**: `name` 在 Registry 内唯一。不同 toolset 下的同名工具注册被拒绝（除非显式 `override=True`）。MCP 工具允许同 toolset 内覆盖（server 刷新）。

**生命周期**: 模块 import 时通过 `registry.register()` 注册 → Agent 调用 `get_definitions()` 获取 → `dispatch()` 执行 → MCP 工具支持 `deregister()` 动态注销。

---

### ToolCall / ToolResult

工具调用的请求-响应模型（dataclass，非持久化）。

| ToolCall | 类型 | 说明 |
|----------|------|------|
| `id` | `str` | LLM 生成的 tool_call id |
| `name` | `str` | 工具名称 |
| `arguments` | `dict[str, Any]` | 调用参数 |
| `status` | `ToolCallStatus` | pending → running → complete/failed |
| `elapsed_ms` | `float` | 执行耗时（毫秒） |

| ToolResult | 类型 | 说明 |
|------------|------|------|
| `tool_call_id` | `str` | 对应 ToolCall 的 id |
| `content` | `str` | JSON 序列化后的结果 |
| `is_error` | `bool` | 是否执行失败 |
| `report_paths` | `list[str]` | 工具产出的报告文件路径 |

---

### SkillMetadata

Skill 文档的元数据（从 SKILL.md 的 YAML frontmatter 解析）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | 是 | Skill 唯一名称，≤64 字符 |
| `version` | `str` | 否 | 语义化版本，默认 `"1.0.0"` |
| `description` | `str` | 否 | 一句话描述，≤1024 字符 |
| `tags` | `list[str]` | 否 | 分类标签 |
| `triggers` | `list[str]` | 否 | 触发关键词，用于 System Prompt 中的索引展示 |
| `platforms` | `list[str]` | 否 | 操作系统限制：`"windows"`, `"linux"`, `"macos"`。空 = 全平台 |
| `prerequisites` | `dict` | 否 | 前置依赖声明 `{"env_vars": [...], "commands": [...]}` |
| `file_path` | `Path` | 是 | SKILL.md 绝对路径 |
| `skill_dir` | `Path` | 是 | Skill 目录路径（用于加载子资源） |

**加载层级**:
- Level 0: 仅元数据（`skills_list` 返回，注入 System Prompt）
- Level 1: 加载 SKILL.md 全文（`skill_load` 工具触发）
- Level 2: 按需加载子资源（`skill_load_resource` 工具触发）

**搜索路径优先级**: 本地模块 skills/ > 外部 Skill 目录。后发现的同名 Skill 覆盖先发现的（警告日志）。

**文件结构**:
```
<skill-dir>/
├── SKILL.md           # 主文件
├── sop/               # 操作流程子资源
├── patterns/          # 模式库
├── cases/             # 案例库
└── ref/               # 参考资料
```

---

### MCPConnection

MCP Server 的连接状态（dataclass）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `server_name` | `str` | 服务器名称 |
| `status` | `MCPConnectionStatus` | `connecting` → `connected` / `error` → `disconnected` |
| `available_tools` | `list[str]` | 已发现的工具名列表 |
| `last_error` | `str \| None` | 最后一次错误信息 |
| `connected_at` | `datetime \| None` | 连接成功时间 |

**状态流转**: `CONNECTING` → `CONNECTED`（成功）或 `ERROR`（失败）。断开后回到 `DISCONNECTED`。

---

### MCPServerConfig

MCP Server 配置（Pydantic，持久化到 JSON）。

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `name` | `str` | - | 服务器唯一名称 |
| `command` | `str` | - | 启动命令 |
| `args` | `list[str]` | `[]` | 命令行参数 |
| `env` | `dict[str, str]` | `{}` | 环境变量 |
| `transport` | `str` | `"stdio"` | 传输类型：`"stdio"`, `"sse"` |
| `timeout` | `int` | `30` | 连接超时（秒） |
| `enabled` | `bool` | `True` | 是否在启动时自动连接 |

---

### AgentOrchestrator（聚合根）

Agent 生命周期管理者。不持久化，运行时创建。

| 持有引用 | 类型 | 说明 |
|----------|------|------|
| `tool_registry` | `ToolRegistry` | Core 工具注册中心（单例） |
| `skill_registry` | `SkillRegistry` | Core Skill 索引（单例） |
| `mcp_registry` | `MCPRegistry` | Core MCP 注册中心（单例） |
| `llm_manager` | `LLMManager` | LLM Provider 管理器 |
| `service` | `AgentService \| None` | 对话服务实例（惰性创建） |

---

### SystemPrompt（值对象）

三段式提示词，纯数据无行为。

| 层 | 内容 | 生命周期 |
|----|------|----------|
| **Stable** | 身份声明 + 工具摘要 + Skill 索引 + 使用指导 | 会话期间不变 |
| **Context** | AGENTS.md 上下文文件 + 用户提供的 system_message | 按需变化 |
| **Volatile** | Memory 快照 + 时间戳 + 会话 ID | 每次请求更新 |

长度控制：
- Stable 层 ≤ 3000 字符。超过时裁剪 Skill 索引为仅名称列表
- Context 层中报告上下文 > 500 字符时截断为最近 3 条

## 实体关系图

```
AgentOrchestrator
    ├── ToolRegistry ◄── (注册) ─── Skill 工具 (skill_list/load/...)
    │       ├── (注册) ─── Agent 内置工具 (create_workspace/...)
    │       └── (注册) ─── MCP 工具 (mcp__{server}__{tool})
    │               └── MCPRegistry
    │                     ├── MCPConnection ─── MCPServerConfig
    │                     └── tools ─── ToolDefinition
    ├── SkillRegistry ◄── (扫描) ─── SKILL.md 文件
    │       └── SkillMetadata
    │             ├── file_path → 内容读取
    │             └── skill_dir → 子资源列表
    ├── LLMManager → Provider
    └── AgentService
          ├── SystemPrompt (三段式)
          ├── ConversationStore (SQLite)
          └── WorkflowTracker
```
