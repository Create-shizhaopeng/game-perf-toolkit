# Perfetto 卡顿抓取模块 — 知识入口

## 目录

- [模块简介](#模块简介)
- [关键约束速查](#关键约束速查)
- [相关踩坑](#相关踩坑)
- [规格文档](#规格文档)

## 模块简介

自动化 Perfetto trace 的抓取、管理与导出，用于分析 Android 设备上的卡顿问题。

- **前缀**：`pe_`（注意：与 `pa_`(perfetto_analysis) 区分）
- **类别**：perfetto
- **Agent 工具**：未注册（`agent_tools: false`）
- **详细开发规则**：见 `../AGENTS.md`

## 关键约束速查

- Perfetto 配置文件（.pbtx）存放在 `assets/` 目录
- 抓取完成后通过 EventBus 发布 `perfetto_capture.trace_ready` 事件
- Buffer 自动估算：轻载基线 9200 KB/s，`buffer_safety_factor` 默认 1.2
- Trace 文件路径：开发环境 `data/output/trace/`，打包后 `<exe_dir>/output/trace/`

## 相关踩坑

| 编号 | 说明 | 关联 |
|------|------|------|
| P15 | Perfetto detach 须配合 write_into_file | 核心相关 |
| P16 | 同 UID 并发会话上限与残留进程 | 核心相关 |
| P17 | Ring buffer clone 覆盖的时间范围 | 核心相关 |
| P02 | ADB 命令输出可能为 None | ADB 操作相关 |
| P05 | QThread 信号安全 | GUI 线程通信 |

## 规格文档

- `specs/001-migration/` — 迁移规格
- `specs/002-auto-buffer/` — Buffer 自动估算
- `specs/003-ui-enhancement/` — UI 增强
