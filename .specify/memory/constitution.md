<!--
Sync Impact Report
- Version: 1.3.0
- Modules: device_disguise (dd_), game_perf (gp_), perfetto_capture (pe_)
- Quality Gates: context 前缀、ADB None 保护、QThread 信号通信
- Templates: plan/spec/tasks 模板已就绪
- Pitfalls doc: scripts/doc/development-pitfalls.md
-->

# LV Game Toolkit Constitution

## Core Principles

### I. Plugin-First（模块化优先）

- 每个功能 MUST 作为独立插件模块开发，放置在 `modules/<module_name>/` 目录下
- 模块 MUST 包含 `manifest.json` 声明元数据、依赖、CLI 命名空间和能力
- 模块 MUST 自包含：源码 (`src/`)、测试 (`tests/`)、规格文档 (`specs/`)、测试数据 (`fixtures/`)
- 模块之间 MUST NOT 直接导入对方 `src/` 下的实现代码，跨模块通信通过 EventBus 或 ServiceRegistry
- 新增功能 MUST 优先考虑独立模块，而非扩展现有模块

### II. Three-Surface Unity（三端统一）

- GUI (PyQt6)、CLI (Typer)、Agent 三种交互方式 MUST 共享同一套 Service API 层
- 业务逻辑 MUST 实现在模块的 `service.py` 中，GUI/CLI/Agent 仅作为调用入口
- 所有 CLI 命令 SHOULD 支持 JSON 格式输出（`--json` 标记），以便 Agent 程序化调用（渐进落地：各模块实现 CLI 命令时逐步添加，框架层不强制首期全量覆盖）
- 数据模型 MUST 使用 Pydantic 定义，确保 GUI/CLI/Agent 三端数据结构一致

### III. Agent-Driven Design（Agent 驱动设计）

- AI Agent 是系统的核心编排者，MUST 能以任意顺序调用任何模块服务
- 模块 MUST 通过 `register_agent_tools` 钩子声明自身可被 Agent 调用的能力
- 服务接口 MUST 通过 ServiceRegistry 注册，自动生成 JSON Schema 供 LLM Function Calling
- Agent 不是固定流水线，而是基于用户意图动态编排模块能力

### IV. Dependency Inversion（依赖反转）

- 模块 MUST 依赖核心框架定义的接口（`toolkit.core.hookspecs`、`toolkit.sdk.*`）
- 核心框架 MUST NOT 依赖任何具体模块的实现
- 模块 MUST 通过 `toolkit.sdk.protocols` 中的 Protocol 定义跨模块接口契约
- 允许导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`
- 禁止导入：`toolkit.core` 内部实现（plugin_manager, db_manager 等）

### V. Presentation Separation（表现分离）

- `service.py` MUST NOT 包含任何 GUI (PyQt6) 或 CLI (Typer) 相关代码
- GUI 组件（`gui_tab.py`）MUST 仅负责展示和用户输入，调用 service 获取数据
- CLI 命令（`cli_commands.py`）MUST 仅负责参数解析和输出格式化，调用 service 执行操作
- 测试 MUST 优先针对 service 层编写，不依赖 GUI/CLI 层

### VI. Open-Closed（开闭原则）

- 新增模块 MUST NOT 修改核心框架代码（`toolkit/core/`、`toolkit/sdk/`）
- 模块通过 pluggy 钩子机制自动发现和注册
- CLI 命名空间 MUST 在 `manifest.json` 中显式声明，PluginManager 负责冲突检测
- 预留的 CLI 命名空间（config, plugin, workflow, version, help, gui）MUST NOT 被模块占用

### VII. Spec-Driven Development（规格驱动开发）

- 新功能开发 MUST 遵循 speckit 工作流：Constitution → Specify → Plan → Tasks → Implement
- 项目根目录使用主 speckit 管理全局规则和通用组件
- 各模块 MUST 在模块目录下初始化独立 speckit（`--here --no-git`），继承全局规则
- 模块开发者 MUST NOT 修改主 speckit 空间的内容
- 模块的 `AGENTS.md` MUST 声明模块边界约束和允许/禁止的导入范围

## Technology Stack Constraints

- **Language**: Python 3.12+（MUST，利用性能提升和类型注解改进）
- **GUI**: PyQt6（MUST，支持 QML 集成用于未来其他技术栈工具）
- **CLI**: Typer + Rich（MUST，类型注解驱动 + Rich 美化输出）
- **Plugin**: pluggy 1.3+（MUST，钩子机制统一模块注册）
- **Data Model**: Pydantic 2.0+（MUST，结构化数据 + JSON Schema 生成）
- **Database**: SQLite（结构化数据）+ JSON（简单配置）+ 文件系统（大型报告/文档）
- **Build**: PyInstaller 6+（onedir 模式，解压即用，Windows + Linux 跨平台）
- **Encoding**: 所有文件和输出 MUST 使用 UTF-8 编码，确保中文不出现乱码
- **Code Quality**: Ruff（lint）+ .editorconfig（跨 IDE 格式统一）
- **Package Manager**: uv（开发环境管理）+ pip（兼容）

## Development Workflow

### 团队协作模式

- 2-5 人小团队，每人负责一个或多个独立模块
- 每个开发者在自己的模块目录下使用独立 speckit 进行 spec-driven 开发
- 通用框架（`toolkit/core/`、`toolkit/sdk/`）修改需主负责人审核
- Git 分支策略：`main` + `feat/<module>-<feature>` 特性分支
- 提交规范：`<type>(<scope>): <description>`，scope 为模块名或 core/sdk

### 模块开发标准流程

1. 使用脚手架 `python scripts/create_module.py <name>` 生成模块骨架
2. 在模块目录执行 `uvx --from git+https://github.com/github/spec-kit.git specify init --here --no-git --ai cursor-agent --script ps`
3. 按 speckit 工作流开发（见下方「Spec-Driven 标准开发流程」）
4. 模块内测试 MUST 通过后才可提交 PR

### Spec-Driven 标准开发流程

以下流程对主 spec（根 speckit）和子 spec（模块 speckit）均 MUST 生效：

| 步骤 | 动作 | 说明 |
|------|------|------|
| **Step 1** | `spec specify` | 创建功能规格文档（FR、SC、Edge Cases） |
| **Step 2** | `spec clarify` | 需求澄清：针对需求不清晰的部分与用户交互确认，所有决策回写 spec.md Clarifications |
| **Step 3** | UE/UI 设计 | 涉及界面时 MUST 设计 2-3 种方案供用户选择；子模块设计风格 MUST 与主模块一致 |
| **Step 4** | `spec plan` | 制定实现计划 |
| **Step 5** | `spec tasks` | 生成具体任务清单 |
| **Step 6** | `spec analysis` | 需求/计划/任务一致性分析，FAIL 项 MUST 清零后方可进入实现 |
| **Step 7** | `spec implement` | 执行实现 |
| **Step 8** | `spec analysis` | 实现后一致性验证，FAIL 项 MUST 清零 |

**说明**：
- Step 3 仅在涉及 GUI/界面的功能时必须执行；纯后端/CLI 功能可跳过
- Step 2 的澄清结果 MUST 影响 Step 3-5 的设计和任务
- 无界面的核心框架增强可简化为：Step 1 → Step 2 → Step 4 → Step 5 → Step 6 → Step 7 → Step 8

### Agent 验收工作流

Agent（AI 或人类开发者借助 AI）在用户验收阶段 MUST 遵循以下规则：

#### 简单 Bug 修复

当用户验收反馈的 Bug 满足以下全部条件时：
- 不涉及功能性变更
- 不涉及需求补充或设计调整
- 属于简单修复（样式、文案、逻辑小错误等）

Agent MUST：
1. 执行 `spec task` + Bug 描述 → 生成修复任务
2. 执行 `spec implement` → 修复代码
3. 执行 `spec analysis` → 确认修复后一致性

#### 需求变更或设计调整

当用户验收反馈涉及以下任一场景时：
- 需求补充（新功能、新约束）
- 功能变更（原有行为需要调整）
- 设计不合理需要重构

Agent MUST 按顺序执行：
1. `spec clarify` → 需求澄清，记录用户决策
2. 涉及 UI 变更时 → 更新 UE/UI 设计文档，提供方案供用户确认
3. `spec plan` → 制定修复/调整计划
4. `spec task` → 根据计划生成具体任务列表
5. `spec analysis` → 确认 clarify 内容与 task 的一致性
6. `spec implement` → 执行修复
7. `spec analysis`（最终） → 确保修复后的代码对齐 spec 和 constitution

#### Bug 修复方法论

Agent 在修复 Bug 时 MUST 遵循以下流程：
1. **分析根因**：通过日志、ADB 命令输出、代码追踪等手段定位问题的根本原因
2. **记录诊断**：在进度回调或日志中输出关键的命令返回值和状态信息，便于后续诊断
3. **基于根因修复**：针对确认的根因编写修复代码，MUST NOT 盲目尝试
4. **验证修复**：修复后通过测试和手动验证确认问题已解决
5. **更新文档**：如修复涉及流程或逻辑变更，同步更新 spec 文档

#### 通用约束

- 每次 `spec analysis` 的结果 MUST 达到 **FAIL 项清零** 方可进入下一阶段
- WARN 项 SHOULD 尽量修复，但允许记录为已知限制后跳过
- 所有 clarify 决策 MUST 回写到 `spec.md` 的 Clarifications 章节

### 质量门禁

- 模块 `service.py` 中每个公共方法 MUST 至少有一个测试用例
- CLI 输出 SHOULD 支持 JSON 格式（渐进落地，模块实现时逐步添加）
- Pydantic 模型 MUST 用于所有公共 API 的入参和返回值
- 中文文档和注释 MUST 使用 UTF-8 编码
- 插件 context 键名 MUST 使用模块前缀命名空间（如 `dd_service`、`gp_adb`），避免跨模块键名冲突
- ADB 命令输出（stdout/stderr）访问时 MUST 使用 `or ""` 保护，防止 None 拼接异常
- GUI 后台线程 MUST 通过 `pyqtSignal` 与主线程通信，MUST NOT 直接操作 UI 控件
- 已知踩坑问题汇总见 `scripts/doc/development-pitfalls.md`

## Governance

- 本 Constitution 是项目最高治理文档，所有开发活动 MUST 遵循
- Constitution 修改需要文档化修改理由，更新版本号并记录修改日期
- 版本号遵循语义化版本：MAJOR（原则变更）、MINOR（新增原则/章节）、PATCH（措辞修正）
- 所有 PR 和代码审查 MUST 验证是否符合 Constitution 原则
- 复杂度增加 MUST 有合理理由，优先选择简单方案

**Version**: 1.3.0 | **Ratified**: 2026-03-20 | **Last Amended**: 2026-03-21
