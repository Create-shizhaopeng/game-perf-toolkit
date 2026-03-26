# Agent 智能助手 — AI 开发规则

## 目录

- [模块概述](#模块概述)
- [文件边界](#文件边界)
- [Context 键前缀](#context-键前缀)
- [LLM Provider 开发](#llm-provider-开发)
- [工具注册与执行](#工具注册与执行)
- [SOP 文档管理](#sop-文档管理)
- [GUI 开发注意事项](#gui-开发注意事项)

## 模块概述

`agent_chat` 模块实现内置 AI Agent，通过 SOP 驱动的工作流自动编排其他模块的工具能力，完成性能分析等复杂任务。

## 文件边界

- ✅ 可编辑：`src/`、`tests/`、`specs/`、`fixtures/`、`assets/`、模块 `.specify/`
- ❌ 禁止编辑：`toolkit/`、其他模块的 `src/` 目录

## Context 键前缀

本模块使用 `ac_` 前缀：

- `ac_service` — AgentService 实例
- `ac_config` — AgentConfig 配置

## LLM Provider 开发

- `anthropic`、`zhipuai` 为可选依赖，MUST 在运行时 `try: import` 处理
- Provider 初始化失败（无 API Key 或包未安装）MUST 返回友好错误信息
- Claude 使用 `input_schema` 格式，GLM 使用 `parameters` 格式，在 Provider 内部适配
- 流式响应 SHOULD 优先使用（提升用户体验）

## 工具注册与执行

- 工具定义 MUST 包含 `parameters` JSON Schema（与 LLM Function Calling 对齐）
- 工具执行结果 MUST 序列化为 JSON string
- dataclass 结果使用 `dataclasses.asdict()` 转换
- Pydantic 结果使用 `model_dump(mode="json")` 转换
- 工具执行异常 MUST 捕获并作为错误结果返回，MUST NOT 中断对话循环

## SOP 文档管理

- 内置 SOP 放在 `assets/sops/` 目录
- 用户自定义 SOP 放在 `data/sops/` 目录
- SOP 为 Markdown 格式，整体注入 system prompt
- SOP 中可使用 `{{tool_list}}` 占位符，运行时替换为可用工具列表

## GUI 开发注意事项

- Agent Tab 的 LLM 调用和工具执行 MUST 在 QThread 中执行
- 消息更新通过 pyqtSignal 回传 GUI 线程
- 流式响应时 SHOULD 逐步更新 Agent 消息气泡
- 工具调用过程 SHOULD 在消息流中可视化展示（工具名、参数、结果摘要）
