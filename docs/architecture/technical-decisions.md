# LV Game Toolkit — 技术决策记录 (ADR)

## 代码规则（索引）

日常编码约定（分层、Ruff、Pydantic、context 前缀、QThread 等）已收敛为 **[architecture-overview.md §5.0 代码规则（总纲）](./architecture-overview.md#50-代码规则总纲)**，并与 **Constitution**（`.specify/memory/constitution.md`）对齐。本文 **ADR** 记录「为何选用某技术」；**如何做** 以 §5.0 + 模块开发手册为准。

## 目录

- [ADR-001 技术栈选择](#adr-001-技术栈选择)
- [ADR-002 插件系统选型](#adr-002-插件系统选型)
- [ADR-003 仓库管理方式](#adr-003-仓库管理方式)
- [ADR-004 数据存放策略](#adr-004-数据存放策略)
- [ADR-005 CLI 框架选型](#adr-005-cli-框架选型)（已废弃）
- [ADR-005b Agent 调用统一方案：MCP Server + Skill](#adr-005b-agent-调用统一方案mcp-server--skill)
- [ADR-006 模块间通信方式](#adr-006-模块间通信方式)
- [ADR-007 数据管道设计](#adr-007-数据管道设计)
- [ADR-008 GUI 布局模式](#adr-008-gui-布局模式)
- [ADR-009 Agent 集成策略](#adr-009-agent-集成策略)
- [ADR-010 跨平台部署方案](#adr-010-跨平台部署方案)
- [ADR-011 Speckit 分层管理](#adr-011-speckit-分层管理)

---

## ADR-001 技术栈选择

**状态**：已采纳

**上下文**：项目需要从简单工具集升级为可扩展的模块化平台，需要选择合适的技术栈。

**决策**：继续使用 Python 3.12+ + PyQt6，新增 Typer 作为 CLI 框架。

**理由**：
- 团队已有 Python + PyQt6 经验，无需学习新语言
- Python 3.12 性能提升 30%+，内置 tomllib
- PyQt6 跨平台且支持 QML 集成（为未来 QML 模块预留）
- Typer 基于 click，类型注解友好，对 Agent 调用友好

**替代方案**：
- Electron + Web 前端：学习成本高，团队无 Web 经验
- C++ Qt：开发效率低，AI 辅助编程支持较弱

---

## ADR-002 插件系统选型

**状态**：已采纳

**上下文**：需要模块化架构，各功能独立开发并动态注册。

**决策**：使用 pluggy 作为插件管理框架。

**理由**：
- pytest 同款，久经验证
- 提供灵活的钩子机制（hookspec/hookimpl）
- 支持插件排序和依赖管理
- 社区活跃，文档完善

**替代方案**：
- 自研轻量方案：简单但功能有限，后期可能不够用
- stevedore：OpenStack 出品，功能强大但偏重

---

## ADR-003 仓库管理方式

**状态**：已采纳

**上下文**：2-5 人团队，各自用 speckit + AI 开发独立模块，需要选择仓库管理方式。

**决策**：Monorepo（单仓库），所有模块在同一仓库下。

**理由**：
- 管理复杂度低，一个仓库搞定
- 构建简单，一次构建全部完成
- 代码共享方便，直接 import
- 支持原子提交（核心+模块同时修改）
- 团队规模小（2-5人），无需仓库级隔离

**替代方案**：
- Git Submodule：管理复杂，跨仓库构建困难
- 多仓库 + 包发布：对小团队过重

**Speckit 隔离方案**：通过目录级 `.cursor/rules/` + AGENTS.md + 代码层接口实现。

---

## ADR-004 数据存放策略

**状态**：已采纳

**上下文**：各模块有运行时数据需求，每个模块有独立的 speckit。

**决策**：分布式方案 — 模块内自带 data/ 目录 + 全局共享 data/ 仅存全局配置。

**理由**：
- 模块 speckit 可触达模块内所有文件
- 模块完全自包含，便于独立开发和测试
- 跨模块数据交换通过事件总线，不依赖文件路径

**替代方案**：
- 集中式 data/：模块 speckit 无法访问外部数据目录

---

## ADR-005 CLI 框架选型

**状态**：已废弃（SUPERSEDED）

⚠️ **已废弃**：CLI 已在 agent-tool-unification 重构中移除，Agent 调用改为 MCP Server + Skill 标准化方案（见 ADR-005b）。

**上下文**：需要完整的 CLI 工具，可完全替代 GUI 操作，且对 AI Agent 友好。

**原决策**：使用 Typer（基于 click）。

**替代方案**：
- click：需要更多样板代码
- argparse：标准库但功能有限
- fire：自动推断参数但控制力弱

**废弃原因**：CLI 对 LLM Agent 不友好（浪费 token、协议不规范、效果不稳定），MCP 是 LLM 调用工具的标准协议。

---

## ADR-005b Agent 调用统一方案：MCP Server + Skill

**状态**：已采纳

**上下文**：Agent 工具调用需要从 CLI（Typer）迁移到标准化方案，使 LLM 能以统一协议发现和调用工具。

**决策**：采用 MCP 协议（FastMCP）+ Skill 文档（YAML frontmatter）方案。

**理由**：
- MCP（Model Context Protocol）是 LLM 调用工具的行业标准协议
- FastMCP 提供了 Python 端的 MCP Server 实现
- Skill 文档（SKILL.md YAML frontmatter）为 Agent 提供自然语言工具描述
- 相比 CLI 方案：Token 消耗更低、协议更规范、调用效果更稳定

**架构要点**：
- ToolRegistry 统一管理各模块暴露的工具
- ToolExecutor 负责工具的发现、调用、错误处理
- Skill Registry 通过 `register_skills` 钩子收集各模块 SKILL.md
- Agent 通过 MCP 协议统一发现和调用所有工具

**替代方案**：
- 保留 CLI（Typer）：Token 浪费大，格式不稳定，已废弃
- 直接 Function Calling：耦合度高，不够标准化

---

## ADR-006 模块间通信方式

**状态**：已采纳

**上下文**：模块间需要数据交互（如日志分析结果传给预测模块），但要保持松耦合。

**决策**：事件总线（Event Bus）+ 服务注册表（ServiceRegistry）。

**理由**：
- 事件总线：异步通知，模块不需要直接引用其他模块
- 服务注册表：Agent 可以发现和调用任意模块的服务
- 两者结合覆盖推/拉两种通信模式

---

## ADR-007 数据管道设计

**状态**：已采纳（修正）

**上下文**：日志分析、Trace 分析、策略预测等模块间存在数据流转需求。

**决策**：Agent 为中心的灵活调度，而非固定链式管道。工作流引擎作为可选的预设流程工具。

**初始方案**：固定链式管道（日志→Trace→策略→预测）

**修正理由**：Agent 是核心编排者，应该能按任意顺序调用模块。固定链式限制了灵活性。

**最终方案**：
- 每个模块暴露独立的 Service API
- Agent/用户自由决定调用顺序
- 工作流引擎允许保存和复用常用组合

---

## ADR-008 GUI 布局模式

**状态**：已采纳

**上下文**：需要同时支持传统工具操作和 Agent 对话交互。

**决策**：混合模式 — Agent Tab + 工具集 Tab，Agent 为第一个 Tab（预留），工具集为第二个 Tab（当前主力）。

**布局要点**：
- 自定义 Title Bar 始终显示设备连接状态和伪装状态
- 设备伪装作为左侧导航中的一项（非独立大 Tab）
- Title Bar 支持多设备勾选

**替代方案**：
- 类 VSCode 布局（工具为主 + Agent 侧边栏）
- 聊天为主体布局
- 最终选择混合模式，渐进式从工具模式向 Agent 模式演进

---

## ADR-009 Agent 集成策略

**状态**：已采纳

**上下文**：Agent AI 是长期目标，当前需要做架构预留。

**决策**：预留接口，不实现具体功能。所有模块按「结构化 Service + Agent Tools 声明」规范开发。

**关键预留**：
- hookspecs 中的 register_agent_tools 钩子
- ServiceRegistry 的 get_service_schema 方法
- LLMProvider 抽象接口（云端 API 配置）
- Agent Tab 位置（第一个顶级 Tab）

**LLM 方向**：倾向云端 API，可配置切换。

---

## ADR-010 跨平台部署方案

**状态**：已采纳

**上下文**：需要支持 Windows 和 Linux，企业内部使用，解压即用。

**决策**：PyInstaller onedir 模式 + zip/tar.gz 分发。

**单入口策略**：
- `Toolkit.exe`（console=False）— GUI 入口，双击启动

**理由**：CLI 入口已在 agent-tool-unification 重构中移除，Agent 调用改为 MCP Server + Skill 标准化方案。仅保留 GUI 构建入口。

**注意**：`--noconsole` 模式下 `sys.stdout/stderr` 为 None，所有日志和调试代码 MUST 做 None 保护（参见踩坑指南 P13）。

---

## ADR-011 Speckit 分层管理

**状态**：已采纳

**上下文**：多人用 speckit + AI 协作开发，需要父子 speckit 隔离且规则继承。

**决策**：主项目 speckit + 模块独立 speckit（--no-git 模式）+ monorepo 补丁。

**规则传递三层机制**：
1. Cursor Rules — .cursor/rules/ 全局生效
2. AGENTS.md — 模块级 AI 规则
3. Code-Level — SDK 基类和 Protocol 强制

**已知限制**：spec-kit 暂无原生 monorepo 父子关系支持，需要手动补丁 common.sh/common.ps1。待 spec-kit Issue #790 解决后可迁移到官方方案。

---

## ADR-012 数据存储方案

**状态**：已采纳

**上下文**：项目需要存储配置数据、设备信息、分析结果、报告文件等多种类型数据。

**决策**：混合存储方案 — JSON（配置）+ SQLite（结构化数据）+ 文件系统（大型文档）。

**理由**：
- JSON 适合简单配置（ADB 路径、主题等），可读性好
- SQLite 适合结构化数据查询（设备记录、分析结果索引），无需额外部署
- 报告/日志/Trace 等大型文件直接存储为文件，数据库保存文件路径
- AI Agent 可直接读取 Markdown 格式的报告文件

**关键设计**：
- 公共表（devices、analysis_results）由框架管理
- 模块表由各模块的 migrations/ 迁移脚本管理
- 框架在加载模块时自动执行迁移

---

> 文档版本：v1.0.0
> 创建日期：2026-03-20
