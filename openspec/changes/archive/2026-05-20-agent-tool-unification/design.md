## Context

当前项目有 7 个模块，其中 5 个实现了 `register_agent_tools()` hook。工具通过 `ToolRegistry.collect_from_plugins()` 收集后，仅供内置 `agent_chat` 模块在进程内调用。CLI 命令通过 Typer 暴露，是给人类终端用的（Rich 格式化输出），但当前也被 Agent 用作调用入口 — 导致 token 浪费和调用不稳定。

项目依赖已包含 `mcp>=1.26.0`（pyproject.toml:34），但尚未使用。

框架层 `ToolDefinition` 有两份定义：`toolkit/core/llm/base.py` 和 `modules/agent_chat/src/models.py`，字段一致（name/description/parameters/method），需要统一。

## Goals / Non-Goals

**Goals:**
- 框架层提供统一 MCP Server（stdio/sse），将 `ToolRegistry` 工具通过标准 MCP 协议暴露
- 框架层提供 Skill 发现机制：扫描模块 `skills/` 目录，将 `SKILL.md` 注册为 Agent 可触发的分析工作流
- 模块可选择性地注册 MCP 工具、Skill 文档、或两者兼有，不强制
- `register_agent_tools()` 规范化：补全 JSON Schema parameters，返回值结构化
- device_disguise 模块作为试点，完整验证 MCP + Skill 双路径

**Non-Goals:**
- 不做 SmartPerfetto 式的重型 YAML Skill 引擎（SQL executor、展示配置、诊断规则）
- 不修改 Service 层纯业务逻辑
- 不强求每个模块都暴露 MCP 和 Skill（按需选择）
- Skill 文档本身可独立复制到别的项目中运行（不依赖 toolkit 框架代码）

## Decisions

### 1. MCP Server 采用框架级统一入口，不从模块分散

**决策**: 在 `toolkit/core/mcp_server.py` 中创建单一 MCP Server，从 `ToolRegistry` 收集所有已注册工具。

**理由**:
- 项目已有 `ToolRegistry` 和 `ToolExecutor`，只需加一层 MCP 协议桥接
- 单一 MCP Server 对外一个连接点，外部 Agent（Claude Code 等）只需连一次
- 模块不需要各自维护 MCP 连接生命周期

**替代方案**: 每个模块独立 MCP Server — 太重，连接管理复杂，且模块间工具有依赖关系（如 perfetto_capture → perfetto_analysis），统一注册更容易发现。

### 2. MCP Server 使用 mcp 官方 SDK 的 stdio 模式

**决策**: 使用项目已依赖的 `mcp>=1.26.0` 库的 stdio server 模式。

```python
# toolkit/core/mcp_server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("lv-game-toolkit")

@mcp.tool()
async def device_disguise(serial: str, brand: str, ...) -> str:
    # bridge to ToolExecutor
```

**理由**:
- 已有依赖，零新增
- stdio 模式是 Claude Code 等 MCP Client 的标准连接方式
- SSE 模式作为后续扩展（需要 HTTP 服务时使用）

**替代方案**: 手动实现 MCP JSON-RPC 协议 — 没必要，官方 SDK 已成熟。

### 3. ToolDefinition 统一迁移到 `toolkit/core/llm/base.py`

**决策**: `modules/agent_chat/src/models.py` 中的 `ToolDefinition` 改为从 `toolkit.core.llm.base` 导入别名，不再维护两份。

**理由**: 两处定义完全一致，统一后 MCP Server 和 agent_chat 共享同一类型。

### 4. Skill 发现采用"文档扫描 + 注册表"轻量模式

**决策**:
- 新 hook `register_skills()` — 模块返回 `skills/` 目录下的 SKILL.md 路径列表
- 框架在 `toolkit/core/skill_registry.py` 中加载：解析 SKILL.md YAML frontmatter（name, description, trigger 等元数据）
- Agent 模块通过 `SkillRegistry.get_skills()` 获取所有 Skill 元数据，作为上下文注入 LLM
- SKILL.md 文件本身内容不解析为执行引擎 — Agent 直接读取文件内容并按其指引工作

**理由**:
- 团队公约要求 Skill 可独立剥离到别的项目，意味着 Skill 本质是"文档"不是"代码"
- Agent（如 Claude Code）天然能读懂 SKILL.md 并按流程执行
- 框架只需负责发现和注册，不需要解析引擎

### 5. CLI 命令整体移除

**决策**: 删除所有 Typer CLI 命令文件（`modules/*/src/cli_commands.py`）。人类用户通过 GUI 操作；Agent 通过 MCP 工具或 Skill 调用。

**理由**:
- CLI 和 GUI 功能重叠，CLI 存在维护成本
- GUI 已覆盖所有 CLI 能力
- 删除 CLI 后，有一个统一的 Agent 调用入口（MCP），降低认知负担

### 6. device_disguise 试点具体改造

- `register_agent_tools()`: 补全 profile_list/profile_add/profile_import 工具，补全所有工具的 parameters JSON Schema
- 新增 `skills/device-disguise/SKILL.md`: 按团队公约格式，覆盖伪装操作流程指南
- 新增 `skills/device-disguise/references/`: 常见品牌/厂商/型号映射表

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| MCP Server 启动时 `ToolRegistry` 可能为空（模块未完成 startup） | MCP Server 延迟初始化，在 `on_startup` hook 全部完成后才注册工具 |
| Service 方法返回 Pydantic 模型时 MCP 序列化可能丢失类型信息 | `ToolExecutor._serialize_result()` 已处理 Pydantic/dataclass，复用即可 |
| Skill 文档不经过代码验证，Agent 可能读到过期的操作指南 | 在 CI 中加 Skill 文档的基本校验（frontmatter 完整性、触发词非空） |
| 模块可能既注册了 MCP 工具又写了 Skill，造成 Agent 调用路径冗余 | 文档规范中明确：动作型功能只注册 MCP，分析型流程才写 Skill |
| `mcp` 库版本升级可能导致 API 不兼容 | 锁定 `mcp>=1.26.0,<2.0.0` 范围 |
