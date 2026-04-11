# Agent 智能助手 — AI 开发规则

> 继承项目根 Constitution（`.specify/memory/constitution.md`），以下为模块级补充约束。

## 目录

- [模块概述](#模块概述)
- [模块边界约束](#模块边界约束)
- [LLM Provider 开发](#llm-provider-开发)
- [工具注册与执行](#工具注册与执行)
- [SOP 文档管理](#sop-文档管理)
- [数据存储](#数据存储)
- [活跃 Spec](#活跃-spec)
- [GUI 开发注意事项](#gui-开发注意事项)

## 模块概述

`agent_chat` 模块实现内置 AI Agent，通过 SOP 驱动的工作流自动编排其他模块的工具能力，完成性能分析等复杂任务。

## 模块边界约束

- ✅ 可编辑：`src/`、`tests/`、`specs/`、`fixtures/`、`assets/`
- ❌ 禁止编辑：`toolkit/`、其他模块的 `src/` 目录
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`、`toolkit.core.service_registry`（Agent 需查询 ServiceRegistry 获取工具列表）
- ❌ 禁止导入：其他模块的 `src/` 实现代码
- 插件 context 键名使用 `ac_` 前缀（如 `ac_service`、`ac_config`）

## LLM Provider 开发

- `anthropic`、`zhipuai` 为可选依赖，MUST 在运行时 `try: import` 处理
- Provider 初始化失败（无 API Key 或包未安装）MUST 返回友好错误信息
- Provider MUST 处理网络超时、API 错误等异常，返回结构化错误信息
- Claude 使用 `input_schema` 格式，GLM 使用 `parameters` 格式，在 Provider 内部适配
- 流式响应 SHOULD 优先使用（提升用户体验）

## 工具注册与执行

- 工具定义 MUST 包含 `parameters` JSON Schema（与 LLM Function Calling 对齐）
- 工具通过直接引用 method 对象执行，在同进程内调用，无需序列化/RPC
- 工具执行结果 MUST 序列化为 JSON string
- dataclass 结果使用 `dataclasses.asdict()` 转换
- Pydantic 结果使用 `model_dump(mode="json")` 转换
- 工具执行异常 MUST 捕获并作为错误结果返回，MUST NOT 中断对话循环
- LLM 的 tool_use 响应 MUST 逐个执行并收集结果，再继续下一轮 LLM 调用

## SOP 文档管理

- 内置 SOP 放在 `assets/sops/` 目录
- 用户自定义 SOP 放在 `data/sops/` 目录
- SOP 为 Markdown 格式，整体注入 system prompt
- SOP 中可使用 `{{tool_list}}` 占位符，运行时替换为可用工具列表

## 数据存储

- API Key MUST 存储在 `data/config.json`（gitignored），MUST NOT 出现在代码或 git 仓库中
- 对话历史持久化使用 SQLite，数据库文件位于 `data/agent_chat.db`
- service 层纯同步，MUST NOT 包含 PyQt6 代码

## 活跃 Spec

- [002-mcp-skills-subagent](specs/002-mcp-skills-subagent/) — MCP 管理、Skills 扩展、Sub-agent 编排 (Draft)

完整 Spec 索引见 [specs/INDEX.md](specs/INDEX.md)。

## GUI 开发注意事项

- Agent Tab 的 LLM 调用和工具执行 MUST 在 QThread 中执行
- 消息更新通过 pyqtSignal 回传 GUI 线程
- 流式响应时 SHOULD 逐步更新 Agent 消息气泡
- 工具调用过程 SHOULD 在消息流中可视化展示
- 消息展示 MUST 区分四类：用户消息、Agent 文本回复、工具调用记录、工具执行结果
