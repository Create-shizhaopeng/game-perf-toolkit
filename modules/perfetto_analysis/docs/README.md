# Perfetto 解析分析模块 — 知识入口

## 目录

- [模块简介](#模块简介)
- [关键约束速查](#关键约束速查)
- [GUI 开发要点](#gui-开发要点)
- [数据库要点](#数据库要点)
- [相关踩坑](#相关踩坑)
- [工具与 SOP](#工具与-sop)
- [设计文档](#设计文档)
- [规格文档](#规格文档)

## 模块简介

Perfetto trace 丢帧解析与多维度卡顿归因分析。支持 9 个分析维度 + Summary，生成 Markdown 报告和 JSON 数据。

- **前缀**：`pa_`（**注意**：不是 `pe_`，`pe_` 被 perfetto_capture 占用）
- **类别**：analysis
- **Agent 工具**：已注册
- **监听事件**：`perfetto_capture.trace_ready`
- **详细开发规则**：见 `../AGENTS.md`

## 关键约束速查

- 分析引擎在 `src/engine/`，使用相对导入
- `service.py` 封装 engine 能力，提供 `on_progress` 回调
- 使用独立 SQLite 数据库（`data/perfetto_analysis.db`）
- 去重策略：`trace_path + mode` 组合唯一

## GUI 开发要点

- 维度多选：使用 QPushButton + _PersistentMenu，**禁用 QComboBox 自定义 popup**（P19）
- 删除/刷新后：使用 `QTimer.singleShot(100ms)` 延迟刷新（P21）
- 工作线程：MUST NOT 直接操作 UI 控件，通过 pyqtSignal 通信（P05）

## 数据库要点

- 工作线程写入使用独立 `sqlite3.connect()` 连接（P20）
- 主线程读取可使用 `db_manager.connection`
- 迁移脚本在 `src/migrations/`，按序号命名

## 相关踩坑

| 编号 | 说明 | 关联 |
|------|------|------|
| P01 | context 键名冲突 — `pa_` 不是 `pe_` | 直接相关 |
| P05 | QThread 信号安全 | GUI 线程通信 |
| P18 | 间歇性 COM 错误 | 设备监控 |
| P19 | QComboBox 自定义 Popup 崩溃 | 维度选择控件 |
| P20 | SQLite 跨线程连接访问 | 数据库操作 |
| P21 | QTableWidget 刷新竞态 | 历史表刷新 |

## 工具、SOP 与分析经验

所有 Agent 分析相关知识资产统一管理在 `../skills/perfetto-analysis/` 下：

- [Agent 工具目录](../skills/perfetto-analysis/tool-catalog.md) — 全部 pa_* 工具、MCP 工具、CLI 命令
- [Cursor Skill 入口](../skills/perfetto-analysis/SKILL.md) — 全场景分析技能
- SOP 文档：`../skills/perfetto-analysis/sop/`（卡顿/通用/ANR/内存）
- 根因模式库：`../skills/perfetto-analysis/patterns/`
- 案例库：`../skills/perfetto-analysis/cases/`
- 团队原始 SOP：`sop-raw/`（未加工输入）

## 设计文档

- [引擎 vs MCP 对比 Demo 方案](perfetto-engine-vs-mcp-demo.md) — 架构演进方向验证
- [SmartPerfetto 对比审查](smartperfetto-insights.md) — 可借鉴改进点（待后续迭代）

## 规格文档

- `specs/001-migration/` — 迁移规格
- `specs/002-agent-mcp-hybrid/` — Agent 化 MCP 混合架构规格
