# Test Plan: core/mcp/registry

**关联 Spec**: `openspec/changes/agent-wiring-fix/specs/agent-core-refactor/spec.md` (FR-003, FR-015 delta)
**测试文件**: `tests/test_core_mcp_registry.py`
**被测模块**: `toolkit/core/mcp/registry.py`

## 测试目标

验证 `MCPRegistry.register_local()` 正确内省 handler class 并生成 `mcp__` 前缀工具、`register_remote()` 正确存储配置、以及注册操作不触发意外的自动持久化。

## 前置条件

- `ToolRegistry` 单例可用（空状态）
- `MCPRegistry` 已创建并注入 ToolRegistry
- 测试用的 `_MockHandler` 类有 2 个公开方法（list_items、get_item），每个有 docstring

## 测试用例

### 1. register_local — 工具以 mcp__ 前缀注册

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_registers_tools_with_mcp_prefix` |
| **输入** | `mcp_registry.register_local("test_module", _MockHandler)` |
| **预期** | ToolRegistry 包含 `mcp__test_module__list_items` 和 `mcp__test_module__get_item` |
| **验证点** | 工具名符合 Hermes 统一前缀规范 `mcp__{module}__{method}` |

### 2. register_local — 工具归属 mcp-local toolset

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_tools_have_correct_toolset` |
| **输入** | 同上 |
| **预期** | `get_entry("mcp__test_module__list_items").toolset == "mcp-local"` |
| **验证点** | toolset 分组正确，可在 ToolRegistry 中按来源过滤 |

### 3. register_local — handler 可调用

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_tool_handler_is_callable` |
| **输入** | 同上 |
| **预期** | `callable(entry.handler)` 返回 True |
| **验证点** | 生成的 handler 是合法 Python 可调用对象 |

### 4. register_remote — 存储远程配置

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_stores_remote_config` |
| **输入** | `mcp_registry.register_remote("https://example.com/mcp", {"token": "abc"})` |
| **预期** | `get_servers()` 返回非空字典 |
| **验证点** | 远程 MCP 配置被存储，可由 `connect_all()` 后续连接 |

### 5. 不自动持久化 — register_external 不触发 save

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_register_external_does_not_save` |
| **输入** | Monkey-patch `save_config` → `register_remote(...)` |
| **预期** | `save_config` 计数为 0（未被调用） |
| **验证点** | 注册操作不应产生文件 I/O 副作用；`add_server()` 仍然调用 save（计数=1） |

### 6. connect_all 安全空返回

| 项目 | 内容 |
|------|------|
| **测试方法** | `test_connect_all_sync_safety` |
| **输入** | 无配置的 MCPRegistry → `await connect_all()` |
| **预期** | 返回空列表，不抛异常 |
| **验证点** | MCP 连接失败不阻塞启动流程 |

## 覆盖的 Spec Requirements

| Spec 要求 | 测试用例 |
|-----------|---------|
| register_local 注册 `mcp__{module}__{method}` 格式工具 | 1, 2 |
| register_local 工具注入 ToolRegistry | 1, 3 |
| register_remote 存储远程配置 | 4 |
| 注册操作不自动持久化 | 5 |
| connect_all 失败不阻塞启动 | 6 |

## 不覆盖的内容

- 真实 MCP Server 连接（stdio/sse） — 需要外部进程，属于集成测试范围
- `connect_all()` 并发连接多个 server — 需要 mock MCP session，后续集成测试覆盖
- `register_local()` 的 handler 方法无 docstring — 应跳过该方法的逻辑由实现决定
