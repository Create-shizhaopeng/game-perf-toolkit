# Agent 智能助手模块 — 知识入口

## 目录

- [模块简介](#模块简介)
- [关键约束速查](#关键约束速查)
- [LLM Provider 要点](#llm-provider-要点)
- [相关踩坑](#相关踩坑)
- [规格文档](#规格文档)

## 模块简介

内置 AI Agent，通过 SOP 驱动的工作流自动编排其他模块的工具能力。

- **前缀**：`ac_`
- **类别**：agent
- **SOP 文档**：`assets/sops/`（内置）、`data/sops/`（用户自定义）
- **详细开发规则**：见 `../AGENTS.md`

## 关键约束速查

- 工具定义 MUST 包含 `parameters` JSON Schema
- 工具执行结果 MUST 序列化为 JSON string
- 工具执行异常 MUST 捕获并作为错误结果返回
- SOP 中可使用 `{{tool_list}}` 占位符

## LLM Provider 要点

- `anthropic`、`zhipuai` 为可选依赖，运行时 `try: import`
- Claude 使用 `input_schema` 格式，GLM 使用 `parameters` 格式
- 流式响应优先使用

## 相关踩坑

| 编号 | 说明 | 关联 |
|------|------|------|
| P23 | GLM API 400 错误：对话历史格式 | LLM 调用 |
| P24 | Tool Schema 中 Callable 参数 | 工具注册 |
| P25 | Python 3.14 annotations 冲突 | 类型系统 |
| P05 | QThread 信号安全 | GUI 线程通信 |

## 规格文档

- `specs/001-agent-core/` — Agent 核心功能规格
