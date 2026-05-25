# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

LV Game Toolkit 是一个基于插件架构的游戏开发测试工具集，支持 GUI（PyQt6）交互和 MCP Server / Skill 标准化 Agent 调用。核心框架提供配置、数据库、事件总线、服务注册表、插件管理、MCP Server、Skill Registry 等基础设施，各功能以独立模块形式存在于 `modules/` 目录。

**技术栈**：Python 3.12+ / PyQt6 / pluggy 1.3+ / Pydantic 2.0+ / MCP (FastMCP) / SQLite / uv（推荐包管理）/ pytest / Ruff。详见 [README.md](README.md)。

## 常用命令

### 开发环境

```bash
# 创建虚拟环境并安装依赖（推荐 uv）
uv venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

uv pip install -e ".[dev]"
```

### 运行应用

```bash
# 启动 GUI（无命令行参数时自动进入）
python -m toolkit.app

# 启动 MCP Server（stdio/sse 模式）
python -m toolkit.app mcp-serve
python -m toolkit.app mcp-serve --transport sse --port 8765
```

### 测试

```bash
# 运行全部测试（主项目 + 所有模块）
python scripts/run_all_tests.py

# 运行单组测试
python -m pytest tests/ -v
python -m pytest modules/perfetto_capture/tests/ -v

# 运行单个测试文件
python -m pytest modules/device_disguise/tests/test_models.py -v
```

### 代码质量

```bash
# Ruff lint（配置见 pyproject.toml [tool.ruff]）
ruff check .

# Ruff 格式化
ruff format .
```

### 构建

```bash
# 完整构建（GUI + 打包为 zip）
python scripts/build.py

# 仅构建 GUI 用于测试
python scripts/build.py --gui-only --no-package

# 手动指定版本号
python scripts/build.py --version 1.2.3
```

构建产物位于 `dist/`：
- `Toolkit/` 目录包含 `Toolkit.exe`（GUI，无控制台窗口）
- `dist/lv-game-toolkit-v{version}-windows.zip` 为最终分发包

### 创建新模块

```bash
python scripts/create_module.py <module_name> --display-name "显示名称"
```

## 架构概述

### 启动流程

`toolkit/app.py` 是唯一直接入口。`main()` 根据 `sys.argv` 决定启动模式：
- 无参数 → `run_gui()` → 创建 QApplication → 加载插件 → 显示 MainWindow
- `mcp-serve` → `run_mcp_server()` → 加载插件 → 启动 MCP Server（stdio/sse）

### 核心服务（在 `_build_context()` 中统一创建并注入）

| 服务 | 类 | 说明 |
|------|-----|------|
| 配置管理 | `ConfigManager` | JSON 文件（`data/config.json`），支持嵌套键 |
| 数据库 | `DatabaseManager` | SQLite（`data/toolkit.db`），WAL 模式，支持模块迁移 |
| 事件总线 | `EventBus` | 同步 pub/sub，事件命名规范：`{module}.{action}` |
| 服务注册表 | `ServiceRegistry` | 模块在启动时注册服务，供 Agent 和其他模块查找调用 |
| 插件管理 | `PluginManager` | 基于 pluggy 的模块发现、加载、生命周期管理 |
| Skill 注册表 | `SkillRegistry` | 发现和加载模块 Skill 文件（SKILL.md），供 Agent 发现和触发 |
| MCP Server | `FastMCP` | 将 ToolRegistry 中的工具通过标准 MCP 协议暴露（stdio/sse） |

### 模块系统

模块位于 `modules/<name>/`，必须包含 `manifest.json`，核心字段：

```json
{
  "name": "perfetto_capture",
  "entry": "src.plugin",
  "service_entry": "src.service",
  "dependencies": { "toolkit_modules": [] },
  "events": { "emits": [], "listens": [] }
}
```

模块的 `plugin.py` 中需定义一个继承 `toolkit.sdk.base_plugin.BasePlugin` 的类，并通过 `@hookimpl` 标记实现 `ToolkitHookSpec` 中的钩子：

- `get_plugin_info()` — 返回模块元数据
- `register_gui_tab()` — 返回 `BaseTab` 子类实例（无 GUI 返回 `None`）
- `register_agent_tools()` — 返回工具列表供 Agent 和 MCP Server 调用
- `register_skills()` — 返回 SKILL.md 文件路径列表，供 Skill Registry 加载
- `on_startup(context)` — 初始化，可在此注册服务到 `context["service_registry"]`
- `on_shutdown()` — 清理

模块加载顺序按 `dependencies.toolkit_modules` 做拓扑排序。

### GUI 框架

- `MainWindow` 管理左侧导航栏和右侧内容区
- 各模块返回的 `BaseTab` 子类实例被添加到内容区
- `BaseTab` 提供设备状态感知：`on_devices_changed(devices)` 在设备列表变化时自动调用
- 涉及设备操作的按钮应在回调中先调用 `self.require_device()`
- 全局对话框样式统一使用 `toolkit.gui.toolkit_dialog` 中的函数
- 图标使用 Codicons 字体（`toolkit.gui.codicons.load_codicons()`）

### MCP Server 与 Skill

- 模块通过 `register_agent_tools()` 向 MCP Server 暴露标准化工具（JSON Schema 参数定义）
- 模块通过 `register_skills()` 向 Skill Registry 注册 SKILL.md 操作指南
- MCP Server 支持 stdio/sse 传输模式，由 `toolkit/app.py` 的 `run_mcp_server()` 启动
- Skill 文件使用 YAML frontmatter 描述元数据（name/description/triggers/category）

### Agent 模块

`modules/agent_chat/` 提供智能助手能力：
- 支持多 LLM Provider（通过 LiteLLM 统一调用）
- 模块通过 `register_agent_tools` 向 Agent 暴露工具
- Agent Tab 始终固定在导航栏最上方

## 目录布局要点

```
toolkit/
  core/           # 核心服务（含 mcp_server.py、skill_registry.py）
  gui/            # PyQt6 GUI 框架
  sdk/            # 模块开发 SDK
modules/
  <name>/
    manifest.json          # 模块清单
    src/plugin.py          # 插件入口（必须含 BasePlugin 子类）
    src/service.py         # 业务服务（可选）
    skills/                # Skill 文件目录（可选）
    tests/                 # 模块测试
data/                   # 运行时数据（config.json、toolkit.db；运行时生成，gitignore）
scripts/                # 构建、测试、脚手架脚本
docs/                   # 文档中心（PROGRESS / SUMMARY / architecture / knowledge / experience）
specs/                  # Speckit 输出的需求/计划/任务（所有模块统一在此）
.specify/               # Speckit 配置与模板（含 constitution.md 最高治理文档）
.claude/rules/          # Claude Code 加载的项目规则
.cursor/rules/          # Cursor IDE 加载的项目规则（与 .claude/rules/ 内容对齐）
```

开发关键文件：
- `pyproject.toml` — 项目配置、依赖、工具设置
- `toolkit/core/hookspecs.py` — pluggy 钩子规范定义
- `docs/architecture/architecture-overview.md` — 完整架构设计文档

---

## 开发规范（核心规则）

### 不可违反的硬规则

1. 模块 **MUST NOT** 修改 `toolkit/` 核心框架目录
2. `service.py` **MUST NOT** 包含 GUI 代码（纯业务逻辑）
3. GUI 后台操作 **MUST** 使用 `QThread + pyqtSignal`，**MUST NOT** 在主线程执行阻塞操作
4. 所有输出 **MUST** 使用 UTF-8 编码
5. Pydantic 用于公共 API 的入参和返回值的数据校验与序列化
6. **GUI 日志**：MUST 用 `self._log(msg, level=...)`，MUST NOT 操作 `LogManager` 或在 Tab 内嵌 `LogTextEdit`（详见 [.claude/rules/log-panel-rules.md](.claude/rules/log-panel-rules.md)）
7. **日志输出**：MUST 使用统一日志体系（`logging` + `InterceptHandler`），MUST NOT 使用 `print()` 输出诊断/错误/警告信息（详见 [.claude/rules/log-panel-rules.md](.claude/rules/log-panel-rules.md)）
8. **GUI 样式**：MUST 通过 `objectName` + `toolkit/gui/styles.py` 全局 QSS；MUST NOT 硬编码主题颜色（用 `theme_colors.get_colors()`）；对话框 MUST 继承 `ToolkitDialog`（详见 [.claude/rules/ui-style-guide.md](.claude/rules/ui-style-guide.md)）
9. **中文硬编码字符串**：用户可见的中文文本 MUST 提取到 `strings_*.py` 中的 `Final[str]` 常量，按功能前缀分组；日志输出、调试诊断信息中的中文不需要提取（详见 [.claude/rules/string-extraction-gate.md](.claude/rules/string-extraction-gate.md)）
10. **历史面板**：历史树组件 MUST 继承 `BaseHistoryTreeWidget`；图标 MUST 使用 codicon 字体（禁止 Unicode Emoji）；输出目录 MUST 通过 `get_output_dir()` 统一获取；分析历史 MUST 直接映射文件系统结构（详见 [.claude/rules/history-panel.md](.claude/rules/history-panel.md)）
### Speckit 开发流程

模块新功能开发遵循 Spec-Driven 流程（详见 `.claude/rules/spec-workflow.md`）：

```
specify → clarify → [UE/UI] → plan → tasks → analysis → implement → analysis
```

- 每次 analysis **MUST** 清零所有 FAIL 项方可进入下一阶段
- 所有 clarify 决策 **MUST** 回写 `spec.md` Clarifications 章节
- BUG 修复 **MUST** 先分析根因再修复，完成后 **MUST** 同步更新 spec 文档

### 知识检索优先级

开发特定模块时，按以下优先级加载上下文（按需加载，禁止全量）：

1. `modules/<name>/AGENTS.md` — 模块边界约束（MUST 首先阅读）
2. `modules/<name>/docs/` — 模块级文档
3. `specs/` 下的当前 spec/plan/tasks — 需求上下文
4. `docs/knowledge/` — 项目跨模块知识
5. `docs/experience/development-pitfalls.md` — 踩坑经验
6. `.claude/rules/context-engineering.md` — 渐进式披露策略

### 上下文工程原则

避免在单次会话中加载超过 500 行的文档（按大文档策略分段加载）。禁止在一次会话中加载所有知识文档；禁止不涉及特定模块时加载其 `AGENTS.md`。

---

## 文档驱动工作流（longmemory）

项目使用 `docs/` 目录管理长期知识。`specs/` 目录由 Speckit 体系独立管理，两者互不重叠。

### 硬约束

- **不改不记**：代码变更完成后，必须同步更新 `docs/PROGRESS.md`「近期工作」。
- **不报假进展**：`docs/PROGRESS.md` 必须准确反映当前状态，已废弃方案要标记，过期计划要更新。

### 自动触发规则

| 场景 | 动作 |
|------|------|
| 新会话开始 / 上下文压缩后 | 自动读取 `docs/PROGRESS.md` + `SUMMARY.md` 重建上下文 |
| 代码变更或新建文档后 | 更新 `PROGRESS.md`，然后运行 `/longmemory sync` 刷新索引 |
| 每周/迭代末 | 主动建议运行 `/longmemory sync --dry-run` 审计文档系统 |

### Longmemory 知识检索优先级

1. `docs/PROGRESS.md`（首回合必读）
2. `docs/{bugfix,notes,analyze,design,journal}/SUMMARY.md`（按需加载）
3. `specs/` 下的 Spec/Plan（Speckit 体系）
4. `.specify/memory/constitution.md`（架构原则确认时）

### 禁止行为

- 不读 `PROGRESS.md` 就直接修改代码
- 完成修改后不更新任何文档
- 新建文档但不在 `SUMMARY.md` 中登记
- 基于 superseded/deprecated 状态的文档给出建议

### 状态卡片规范

BUG/ANALYZE/DESIGN 文档顶部必须包含状态卡片：

```html
<!--
  id: BUG-001
  title: 文档标题
  type: bugfix | analyze | design
  status: draft | active | done | superseded | investigating | root-caused | fixed | wontfix | implemented | deprecated
  created: YYYY-MM-DD
  updated: YYYY-MM-DD
  tags: [tag1, tag2]
  depends_on: [XXX-001]
  superseded_by: DES-005
-->
```

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
