# Agent 智能助手模块 Constitution

## 目录

- [继承关系](#继承关系)
- [模块边界约束](#模块边界约束)
- [技术约束](#技术约束)
- [开发规范](#开发规范)

## 继承关系

本模块 Constitution 继承自项目根 Constitution（`../../.specify/memory/constitution.md`），所有根 Constitution 中定义的原则、技术栈约束和开发流程均 MUST 适用于本模块。

以下仅补充模块级约束，不重复根级内容。

## 模块边界约束

- ✅ 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`、`assets/`
- ❌ 禁止修改：`toolkit/`、其他模块目录、项目根配置文件
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`、`toolkit.core.service_registry`（Agent 需要查询 ServiceRegistry 获取工具列表）
- ❌ 禁止导入：其他模块的 `src/` 实现代码
- 插件 context 键名 MUST 使用 `ac_` 前缀（如 `ac_service`、`ac_config`）
  - `ac_` 取自 **a**gent **c**hat 的缩写
  - 参见 `scripts/doc/development-pitfalls.md` P01

## 技术约束

- LLM SDK（`anthropic`、`zhipuai`）为可选依赖，MUST 在运行时动态导入并处理 ImportError
- API Key MUST 存储在 `data/config.json`（gitignored），MUST NOT 出现在代码或 git 仓库中
- SOP 文档为 Markdown 格式，存放在 `assets/sops/` 目录
- 对话历史持久化使用 SQLite，数据库文件位于 `data/agent_chat.db`
- 工具调用通过直接引用 method 对象执行，在同进程内调用，无需序列化/RPC
- 工具调用结果 MUST 序列化为 JSON string 后反馈给 LLM
- 对话循环中 LLM 的 tool_use 响应 MUST 逐个执行并收集结果，再继续下一轮 LLM 调用
- GUI Agent Tab MUST 使用 QThread + pyqtSignal 异步执行 LLM 调用和工具执行，不阻塞 UI

## 开发规范

- 遵循项目根 `scripts/doc/development-pitfalls.md` 中列出的踩坑指南
- service 层纯同步，MUST NOT 包含 PyQt6 代码
- LLM Provider 实现 MUST 处理网络超时、API 错误等异常，返回结构化错误信息
- 工具执行器 MUST 捕获所有异常，将错误信息作为 ToolResult 返回给 LLM，MUST NOT 让异常中断对话循环
- Agent Tab 对话消息展示 MUST 区分：用户消息、Agent 文本回复、工具调用记录、工具执行结果

**Version**: 1.0.0 | **Last Updated**: 2026-03-25
