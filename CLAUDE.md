# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

LV Game Toolkit 是一个基于插件架构的游戏开发测试工具集，支持 GUI（PyQt6）和 CLI（Typer）双模式运行。核心框架提供配置、数据库、事件总线、服务注册表、插件管理等基础设施，各功能以独立模块形式存在于 `modules/` 目录。

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

# 启动 CLI（带任意参数时自动进入）
python -m toolkit.app version
python -m toolkit.app plugin list
python -m toolkit.app device list
```

### 测试

```bash
# 运行全部测试（主项目 + 所有模块）
python scripts/run_all_tests.py

# 运行单组测试
python -m pytest tests/ -v
python -m pytest modules/perfetto_capture/tests/ -v

# 运行单个测试文件
python -m pytest modules/game_perf/tests/test_cli.py -v
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
# 完整构建（GUI + CLI + 打包为 zip）
python scripts/build.py

# 仅构建 GUI 用于测试
python scripts/build.py --gui-only --no-package

# 手动指定版本号
python scripts/build.py --version 1.2.3
```

构建产物位于 `dist/`：
- `Toolkit/` 目录包含 `Toolkit.exe`（GUI，无控制台窗口）和 `toolkit-cli.exe`（CLI）
- `dist/lv-game-toolkit-v{version}-windows.zip` 为最终分发包

### 创建新模块

```bash
python scripts/create_module.py <module_name> --display-name "显示名称" [--cli-ns 命名空间]
```

## 架构概述

### 启动流程

`toolkit/app.py` 是唯一直接入口。`main()` 根据 `sys.argv` 长度决定启动模式：
- 无参数 → `run_gui()` → 创建 QApplication → 加载插件 → 显示 MainWindow
- 有参数 → `run_cli()` → 加载插件 → 解析并执行 Typer 命令

### 核心服务（在 `_build_context()` 中统一创建并注入）

| 服务 | 类 | 说明 |
|------|-----|------|
| 配置管理 | `ConfigManager` | JSON 文件（`data/config.json`），支持嵌套键 |
| 数据库 | `DatabaseManager` | SQLite（`data/toolkit.db`），WAL 模式，支持模块迁移 |
| 事件总线 | `EventBus` | 同步 pub/sub，事件命名规范：`{module}.{action}` |
| 服务注册表 | `ServiceRegistry` | 模块在启动时注册服务，供 Agent 和其他模块查找调用 |
| 插件管理 | `PluginManager` | 基于 pluggy 的模块发现、加载、生命周期管理 |

### 模块系统

模块位于 `modules/<name>/`，必须包含 `manifest.json`，核心字段：

```json
{
  "name": "perfetto_capture",
  "entry": "src.plugin",
  "service_entry": "src.service",
  "dependencies": { "toolkit_modules": [] },
  "cli_namespace": "perfetto",
  "events": { "emits": [], "listens": [] }
}
```

模块的 `plugin.py` 中需定义一个继承 `toolkit.sdk.base_plugin.BasePlugin` 的类，并通过 `@hookimpl` 标记实现 `ToolkitHookSpec` 中的钩子：

- `get_plugin_info()` — 返回模块元数据
- `register_cli_commands(cli_app)` — 用 `cli_app.add_typer()` 挂载子命令
- `register_gui_tab()` — 返回 `BaseTab` 子类实例（无 GUI 返回 `None`）
- `register_agent_tools()` — 返回工具列表供 Agent 调用
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

### CLI 框架

- 根命令由 `toolkit.cli.main.create_cli_app()` 创建
- 内置命令：`version`、`config get/set/list`、`plugin list`、`device list`
- 各模块通过 `register_cli_commands` 钩子用 `add_typer()` 挂载子命令组
- CLI 命名空间由 `manifest.json` 的 `cli_namespace` 定义，框架预留命名空间见 `PluginManager.RESERVED_CLI_NAMESPACES`

### Agent 模块

`modules/agent_chat/` 提供智能助手能力：
- 支持多 LLM Provider（通过 LiteLLM 统一调用）
- 模块通过 `register_agent_tools` 向 Agent 暴露工具
- Agent Tab 始终固定在导航栏最上方

## 目录布局要点

```
toolkit/
  core/           # 核心服务
  gui/            # PyQt6 GUI 框架
  cli/            # Typer CLI 框架
  sdk/            # 模块开发 SDK
modules/
  <name>/
    manifest.json          # 模块清单
    src/plugin.py          # 插件入口（必须含 BasePlugin 子类）
    src/service.py         # 业务服务（可选）
    tests/                 # 模块测试
data/                   # 运行时数据
scripts/                # 构建、测试、脚手架脚本
docs/                   # 文档中心
```

开发关键文件：
- `pyproject.toml` — 项目配置、依赖、工具设置
- `toolkit/core/hookspecs.py` — pluggy 钩子规范定义
- `docs/architecture/architecture-overview.md` — 完整架构设计文档

---

## 开发规范（核心规则）

### 不可违反的硬规则

1. 模块 **MUST NOT** 修改 `toolkit/` 核心框架目录
2. `service.py` **MUST NOT** 包含 GUI/CLI 代码（纯业务逻辑）
3. GUI 后台操作 **MUST** 使用 `QThread + pyqtSignal`，**MUST NOT** 在主线程执行阻塞操作
4. 所有输出 **MUST** 使用 UTF-8 编码
5. Pydantic 用于公共 API 的入参和返回值的数据校验与序列化

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
