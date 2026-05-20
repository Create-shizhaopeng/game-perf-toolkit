## 1. 框架层 — ToolDefinition 统一

- [x] 1.1 确认 `toolkit/core/llm/base.py` 中 `ToolDefinition` dataclass 定义完整（name/description/parameters/method）
- [x] 1.2 将 `modules/agent_chat/src/models.py` 中的 `ToolDefinition` 改为从 `toolkit.core.llm.base` 导入别名，删除重复定义
- [x] 1.3 验证 `modules/agent_chat/src/tools/registry.py` 的 `ToolDefinition` 导入路径正确

## 2. 框架层 — Skill Registry

- [x] 2.1 在 `toolkit/core/hookspecs.py` 中新增 `register_skills()` hook spec（返回 list[str]，模块返回 SKILL.md 文件路径列表）
- [x] 2.2 创建 `toolkit/core/skill_registry.py`，实现 `SkillRegistry` 类：加载 SKILL.md 文件、解析 YAML frontmatter（name/description/triggers）、提供 `get_skills()` 和 `get_skill_content(name)` 方法
- [x] 2.3 在 `toolkit/app.py` 的 `_load_plugins()` 中调用 `register_skills()` hook 收集各模块 Skill 路径并注册到 `SkillRegistry`
- [x] 2.4 将 SkillRegistry 实例注入到 context 中（`context["skill_registry"]`），供 `agent_chat` 模块使用

## 3. 框架层 — MCP Server

- [x] 3.1 创建 `toolkit/core/mcp_server.py`，使用 `mcp.server.fastmcp.FastMCP` 创建 MCP server 骨架
- [x] 3.2 实现 MCP tool 注册逻辑：遍历 `ToolRegistry.get_definitions()`，为每个 `ToolDefinition` 动态创建函数签名，桥接到 `ToolExecutor.execute()`
- [x] 3.3 实现 stdio 模式入口函数 `run_stdio()`：调用 `mcp.run(transport="stdio")`
- [x] 3.4 实现 SSE 模式入口函数 `run_sse(port)`：调用 `mcp.run(transport="sse", port=port)`
- [x] 3.5 在 `toolkit/app.py` 中新增 `run_mcp_server(transport, port)` 函数，在核心服务初始化完成后启动 MCP server
- [x] 3.6 确保 MCP server 在所有模块 `on_startup()` 完成后才注册工具（延迟初始化）

## 4. 模块层 — device_disguise 试点

- [x] 4.1 补全 `register_agent_tools()` 中所有工具的 `parameters` JSON Schema（device_status, device_disguise, device_reset）
- [x] 4.2 新增 profile 相关 Agent 工具：profile_list, profile_add, profile_import（补全 parameters schema）
- [x] 4.3 创建 `modules/device_disguise/skills/device-disguise/SKILL.md`，按团队公约格式编写（YAML frontmatter + 分析步骤 + 结论格式）
- [x] 4.4 创建 `modules/device_disguise/skills/device-disguise/references/` 目录，放入常见品牌/厂商/型号映射表
- [x] 4.5 在 `plugin.py` 中实现 `register_skills()` hook，返回 `skills/device-disguise/SKILL.md` 路径

## 5. CLI 移除

- [x] 5.1 识别所有含 CLI 命令的模块文件（`modules/*/src/cli_commands.py`、`modules/*/src/strings_cli.py`）
- [x] 5.2 删除所有 `modules/*/src/cli_commands.py` 文件
- [x] 5.3 删除所有 `modules/*/src/strings_cli.py` 文件
- [x] 5.4 在各模块 `plugin.py` 中移除 `register_cli_commands()` hook 实现
- [x] 5.5 在 `toolkit/cli/` 中移除 Typer 根命令组装逻辑
- [x] 5.6 删除 `toolkit/app.py` 中 `run_cli()` 分支的入口调用
- [x] 5.7 从 `pyproject.toml` 中移除 Typer 和 Rich 相关依赖

## 6. 测试与验证

- [x] 6.1 运行 `python -m pytest modules/device_disguise/tests/ -v` 确保现有测试通过（30 passed）
- [x] 6.2 编写 MCP Server 基本测试：handler 签名构建、JSON Schema 类型映射、server 创建、无 method 跳过（12 passed）
- [x] 6.3 编写 Skill Registry 基本测试：发现 SKILL.md 文件、解析 frontmatter、获取 skill content（9 passed）
- [x] 6.4 验证 ToolDefinition 统一后 agent_chat 模块的 `collect_from_plugins()` 正常工作
- [x] 6.5 运行全量测试通过（150 passed）
- [x] 6.6 验证 GUI 启动正常：`_build_context()` + `_load_plugins()` 正常，7 个模块全部加载成功
- [x] 6.7 验证 `cli_commands.py` 和 `strings_cli.py` 已从各模块目录中删除
