# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

Game Perf Toolkit 是一个基于插件架构的游戏性能测试工具集，支持 GUI（PyQt6）交互和 MCP Server / Skill 标准化 Agent 调用。核心框架提供 Agent 引擎（位于 `toolkit/agent/`）以及配置、数据库、事件总线、服务注册表、插件管理、工具注册表、MCP Server、Skill Registry、LLM 管理等基础设施，其余功能以独立模块形式存在于 `modules/` 目录。

> **公开仓库说明**：`modules/game_perf/`（游戏性能配置）为本地保留模块，已通过 `.gitignore` 排除公开发布，clone 仓库后不会看到该模块。

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

> **dev 路径覆盖**：用户数据走 OS 标准路径（`%APPDATA%`/`%LOCALAPPDATA%`/Documents）。
> 开发时设置环境变量 `LV_TOOLKIT_DATA_DIR=<项目根>/data` 可让 data 层（db/backup/output）回落到项目本地 `data/`，便于测试 fixture。frozen 模式忽略此变量。

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
# 完整构建（PyInstaller → Velopack 打包产 Setup.exe + delta 更新包）
python scripts/build.py

# 仅构建 GUI 用于测试（不打包；--no-package 跳过 Velopack 打包）
python scripts/build.py --no-package

# 额外产出便携 zip（过渡期兼容；默认仅 Velopack Setup.exe）
python scripts/build.py --zip

# 手动指定版本号
python scripts/build.py --version 1.2.3
```

构建产物位于 `dist/`：
- `dist/publish/` 为 PyInstaller `--onedir` 产出（Velopack 打包输入）
- `dist/` 下 Velopack 产出的 `Setup.exe`（首次安装）+ delta 更新包（发 GitHub Releases feed）
- `--zip` 时额外产 `dist/game-perf-toolkit-v{version}-windows.zip`（便携包，过渡期）

> **Velopack 打包前置**：需安装 vpk CLI（`dotnet tool install -g vpk`，依赖 .NET SDK）。
> 代码签名可选：环境变量 `VP_SIGNING_CERT` 配置签名凭证，未配置则产出未签名（Windows SmartScreen 警告）。

### 创建新模块

```bash
python scripts/create_module.py <module_name> --display-name "显示名称"
```

## 架构概述

### 启动流程

`toolkit/app.py` 是唯一直接入口。`main()` 根据 `sys.argv` 决定启动模式：
- 无参数 → `run_gui()` → 创建 QApplication → 加载插件 → 显示 MainWindow
- `mcp-serve` → `run_mcp_server()` → 加载插件 → 启动 MCP Server（stdio/sse）

### 核心服务

启动时分阶段创建并注入 `context`：多数在 `_build_context()`（`toolkit/app.py`），`PluginManager`/`SkillRegistry` 在 `_load_plugins()` 阶段，`LLMManager` 在 `QApplication` 之后由 `_init_llm_manager()` 注入。

| 服务 | 类 | 说明 |
|------|-----|------|
| 配置管理 | `ConfigManager` | JSON 文件（`toolkit_config.json`，dev: `data/config/`，frozen: `%APPDATA%`），支持嵌套键；实时同步状态见 [config-sync-rules.md](.claude/rules/config-sync-rules.md)「项目现状与待修复」 |
| 数据库 | `DatabaseManager` | SQLite（`data/db/toolkit.db`，frozen: `%LOCALAPPDATA%`），WAL 模式，支持模块迁移 |
| 事件总线 | `EventBus` | 同步 pub/sub，事件命名规范：`{module}.{action}` |
| 服务注册表 | `ServiceRegistry` | 模块在启动时注册服务，供 Agent 和其他模块查找调用 |
| 工具注册表 | `ToolRegistry` | 线程安全单例，收集 pluggy hooks / Skill / MCP 桥接工具，供 Agent 与 MCP Server 调用（`_build_context` 注入） |
| MCP 注册表 | `MCPRegistry` | MCP 服务器全生命周期管理（local/external/remote），`_build_context` 注入 |
| 插件管理 | `PluginManager` | 基于 pluggy 的模块发现、加载、生命周期管理（`_load_plugins` 阶段创建） |
| Skill 注册表 | `SkillRegistry` | 发现和加载模块 Skill 文件（SKILL.md），供 Agent 发现和触发（`_load_plugins` 阶段创建） |
| LLM 管理 | `LLMManager` | 框架层 LLM 能力中心，Provider 生命周期/配置持久化/信号通知（基于 LiteLLM），`QApplication` 后注入 |
| MCP Server | `FastMCP` | 将 `ToolRegistry` 中的工具通过标准 MCP 协议暴露（stdio/sse/streamable-http），由 `create_mcp_server` 工厂按需创建 |

> 核心基础设施（非 context 注入实例，表外单列）：`toolkit/core/app_paths.py`（用户数据三层分层路径 config/data/output）、`toolkit/core/unified_logger.py`（loguru 统一日志三层路由）、`toolkit/core/config_service.py`（`FileConfigService` 基类，文件型配置服务 MUST 继承）。

### 模块系统

模块位于 `modules/<name>/`，必须包含 `manifest.json`，核心字段：

> 注：`modules/agent_chat/` 为 R6 重构遗留壳（无 `manifest.json`，不再加载），Agent 插件入口已迁至 `toolkit/agent/__init_plugin.py`（作为框架级内置插件，`name=agent_chat`）。

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

- `MainWindow` 布局：自定义标题栏（`TitleBar`）+ 左侧面板（`LeftPanel` = `NavPanel` + `HistoryArea`）+ 中间内容堆栈（各 `BaseTab`）+ 底部日志面板（`BottomPanel`）+ 右侧 Agent Overlay 面板（`RightPanel`）+ 状态栏
- 框架级组件：`toolkit/gui/panels/`（`LeftPanel`/`BottomPanel`/`RightPanel`/`HistoryArea`）、`toolkit/gui/widgets/`（`TitleBar`/`NavPanel`/`BaseHistoryTreeWidget`/`LLMStatusWidget`）；`BaseTab.history_widgets()` 注册到 `HistoryArea`，`RightPanel` 仅承载 Agent Overlay
- 各模块返回的 `BaseTab` 子类实例被添加到内容堆栈
- `BaseTab` 提供设备状态感知：`on_devices_changed(devices)` 在设备列表变化时自动调用
- 涉及设备操作的按钮应在回调中先调用 `self.require_device()`
- 全局对话框样式统一使用 `toolkit.gui.toolkit_dialog` 中的函数
- 图标使用 Codicons 字体（`toolkit.gui.codicons.load_codicons()`）

### MCP Server 与 Skill

- 模块通过 `register_agent_tools()` 向 MCP Server 暴露标准化工具（JSON Schema 参数定义）
- 模块通过 `register_skills()` 向 Skill Registry 注册 SKILL.md 操作指南
- MCP Server 支持 stdio/sse/streamable-http 传输模式，由 `toolkit/app.py` 的 `run_mcp_server()` 启动
- Skill 文件使用 YAML frontmatter 描述元数据（name/description/triggers/category）

### Agent 核心引擎

`toolkit/agent/` 提供智能助手能力（R6 重构已从 `modules/agent_chat/` 下沉为框架级核心引擎）：
- `AgentOrchestrator` 驱动对话循环，统一 Skill/Tool/MCP 视图与生命周期
- `AgentService` 执行对话循环；`AgentPanel`（`toolkit/agent/gui/`）以**右侧 Overlay 面板**形式呈现，不再作为导航栏 Tab（旧 `AgentTab` 已降级为 stub）
- 支持多 LLM Provider（通过 LiteLLM 统一调用，由 `toolkit/core/llm/` 的 `LLMManager` 管理）
- 各模块通过 `register_agent_tools` 向 Agent 暴露工具
- `modules/agent_chat/` 已降级为向后兼容 re-export 垫片（无 `manifest.json`，不再作为插件加载）

## 目录布局要点

```
toolkit/
  agent/          # Agent 核心引擎（orchestrator/service/gui/skill_router/knowledge/memory/workflow）
  core/           # 核心服务（含 mcp/ 包、llm/ 包、tool_registry、skill_registry、app_paths 等）
  gui/            # PyQt6 GUI 框架（panels/、widgets/、base_tab、styles 等）
  sdk/            # 模块开发 SDK
modules/
  <name>/
    manifest.json          # 模块清单
    src/plugin.py          # 插件入口（必须含 BasePlugin 子类）
    src/service.py         # 业务服务（可选）
    skills/                # Skill 文件目录（可选）
    tests/                 # 模块测试
data/                   # 运行时数据（config/toolkit_config.json、db/toolkit.db、output/；运行时生成，gitignore）
scripts/                # 构建、测试、脚手架脚本
docs/                   # 文档中心（PROGRESS / README 索引 / architecture / knowledge / experience）
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
11. **代码质量门禁**：代码移动 MUST cp+Edit（禁止 Write 重写）；完成后 MUST 执行启动验证（`python -m toolkit.app` 或无头路径）；禁止用 sed 跳过测试；新建模块 MUST 包含单元测试（详见 [.claude/rules/code-quality-gate.md](.claude/rules/code-quality-gate.md)）
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

1. `modules/<name>/AGENTS.md` — 模块边界约束（若存在则 MUST 首先阅读；Agent 边界约束改看 `toolkit/agent/` 下文档）
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
| 新会话开始 / 上下文压缩后 | 自动读取 `docs/PROGRESS.md` + `docs/README.md` 重建上下文 |
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
（当前无进行中的 Speckit feature）
<!-- SPECKIT END -->
