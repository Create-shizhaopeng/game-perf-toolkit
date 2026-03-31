# PerfDog 分析模块 — 知识入口

## 目录

- [模块简介](#模块简介)
- [关键约束速查](#关键约束速查)
- [特殊规则](#特殊规则)
- [相关踩坑](#相关踩坑)
- [规格文档](#规格文档)

## 模块简介

PerfDog 导出数据的离线分析：Excel 导入、会话摘要、问题洞察、联合分析。

- **前缀**：`pdi_`
- **类别**：perfdog
- **Agent 工具**：未注册（`agent_tools: false`）
- **模块 README**：`../README.md`（用户操作入口文档）
- **详细开发规则**：见 `../AGENTS.md`

## 关键约束速查

- 核心分析逻辑在 `toolkit.core.perfdog`（框架层），本模块是 UI 入口
- 依赖 `device_disguise` 和 `perfetto_capture` 模块

## 特殊规则

本模块有两个例外于全局规范的特殊规则（详见 `doc/knowledge/toolkit-exceptions.md`）：

1. **允许导入 `toolkit.core.perfdog`** — PerfDog 核心逻辑实现在框架层
2. **测试位于根目录 `tests/`** — 因 pytest import-mode 限制（参考 P04）

## 相关踩坑

| 编号 | 说明 | 关联 |
|------|------|------|
| P04 | pytest 跨模块测试文件名冲突 | 测试位置 |
| P05 | QThread 信号安全 | GUI 线程通信 |

## 规格文档

- **权威 spec**：根目录 `specs/004-perfdog-import-insights/`（非模块内 specs）
