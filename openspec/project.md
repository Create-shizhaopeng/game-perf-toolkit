# LV Game Toolkit

游戏开发测试工具集 — 基于插件架构，支持 GUI（PyQt6）和 CLI（Typer）双模式运行的 Android 性能分析平台。

## Tech Stack

| Category | Technology | Version |
|----------|-----------|---------|
| Language | Python | 3.12+ |
| GUI | PyQt6 | >=6.5.0 |
| CLI | Typer + Rich | >=0.9.0 / >=13.0.0 |
| Plugin | pluggy | >=1.3.0 |
| Data Model | Pydantic | >=2.0.0 |
| Database | SQLite | WAL mode, per-module migrations |
| Config | JSON | `data/config.json` |
| Package Manager | uv (recommended) | — |
| Testing | pytest + pytest-asyncio | >=7.0.0 |
| Lint/Format | Ruff | py312, line-length 100 |
| Build | PyInstaller | >=6.0.0 |
| Agent/LLM | LiteLLM + pydantic-ai | >=1.80.0 / >=0.1.0 |
| Versioning | SemVer via git tag | — |

## Architecture

### Core Framework (`toolkit/`)

- **`toolkit/app.py`** — 唯一入口，根据 `sys.argv` 长度自动切换 GUI/CLI 模式
- **`toolkit/core/`** — 核心服务层：ConfigManager、DatabaseManager、EventBus、ServiceRegistry、PluginManager、ADBManager
- **`toolkit/gui/`** — PyQt6 GUI 框架：MainWindow（左侧导航+右侧内容区）、BaseTab（设备状态感知）、全局 QSS 样式、Codicons 图标
- **`toolkit/cli/`** — Typer CLI 框架，内置 version/config/plugin/device 命令
- **`toolkit/sdk/`** — 模块开发 SDK：BasePlugin 基类、Pydantic models、协议定义

### Plugin System

模块通过 pluggy hook 与框架交互。每个模块提供继承 `BasePlugin` 的类，实现以下钩子：

- `get_plugin_info()` → 模块元数据
- `register_cli_commands(cli_app)` → 挂载 CLI 子命令
- `register_gui_tab()` → 返回 BaseTab 子类（无 GUI 返回 None）
- `register_agent_tools()` → Agent 工具列表
- `on_startup(context)` → 初始化，注册服务
- `on_shutdown()` → 清理

模块加载按 `dependencies.toolkit_modules` 拓扑排序。

### Event System

同步 pub/sub，命名规范：`{module}.{action}`。核心事件：
- `device.connected` / `device.disconnected` — 设备状态变化
- `perfetto_capture.trace_ready` — trace 抓取完成
- `perfetto_analysis.analysis_complete` — 分析完成

### GUI Architecture

- MainWindow 管理左侧导航 + 右侧内容区 + 底部日志面板 + 右侧扩展面板
- BaseTab 提供设备状态感知：`on_devices_changed(devices)` 自动回调
- 对话框统一继承 `ToolkitDialog`，图标使用 Codicons 字体
- 全局 QSS 通过 objectName 选择器管理，颜色从 `theme_colors.get_colors()` 获取

## Modules

| Module | Display Name | Description | GUI | CLI | Agent |
|--------|-------------|-------------|-----|-----|-------|
| agent_chat | Agent 智能助手 | LLM 驱动的 SOP 工作流编排，调用模块工具完成分析任务 | ✗ | ✓ | ✗ |
| device_disguise | 设备伪装工具 | 修改 Android 设备品牌/型号/厂商，支持配置文件管理 | ✓ | ✓ | ✓ |
| game_perf | 游戏性能配置 | 解析、编辑、推送 gameperfconfig.xml | ✓ | ✓ | ✓ |
| perfdog_insights | PerfDog 分析 | 导入 PerfDog Excel 导出，生成性能摘要与异常洞察 | ✓ | ✓ | ✗ |
| perfetto_analysis | Perfetto 解析分析 | trace 丢帧解析与多维度卡顿归因分析 | ✓ | ✓ | ✓ |
| perfetto_capture | Perfetto 抓取 | 自动化 Perfetto trace 抓取、管理与导出 | ✓ | ✓ | ✗ |
| workspace_tools | 性能配置对比 | gameperfconfig 多文件对比与合并 | ✓ | ✓ | ✗ |

## Development Conventions

### Hard Rules (Non-Negotiable)

1. Module **MUST NOT** modify `toolkit/` core framework directory
2. `service.py` **MUST NOT** contain GUI/CLI code (pure business logic only)
3. GUI background operations **MUST** use `QThread + pyqtSignal`, **MUST NOT** block the main thread
4. All output **MUST** use UTF-8 encoding
5. Pydantic for public API input/output validation and serialization
6. **Logging**: MUST use `self._log(msg, level=...)`, MUST NOT operate LogManager directly
7. **UI Style**: MUST use `objectName` + global QSS in `toolkit/gui/styles.py`; dialog MUST inherit `ToolkitDialog`

### Spec-Driven Workflow

```
specify → clarify → [UE/UI] → plan → tasks → analysis → implement → analysis
```

- All clarify decisions MUST be written back to spec.md Clarifications section
- Bug fixes MUST analyze root cause first, then sync spec documents after completion
- All specs are unified under root `specs/` directory

### Versioning (SemVer)

- Bug fixes → PATCH +1
- Feature iteration → MINOR +1, PATCH reset
- New module / framework refactor → MAJOR +1, rest reset
- Version managed via git tag, auto-read by build scripts

## Key Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project config, dependencies, tool settings |
| `toolkit/core/hookspecs.py` | pluggy hook specification |
| `toolkit/app.py` | Application entry point |
| `docs/architecture/architecture-overview.md` | Full architecture design doc |
| `docs/PROGRESS.md` | Project progress tracking |
| `.specify/memory/constitution.md` | Governance constitution |
| `.claude/rules/` | Claude Code project rules |
| `.cursor/rules/` | Cursor IDE project rules (aligned with .claude/rules/) |

## Remote Repository

<https://gitee.com/lv-game-toolkit/lv-game-toolkit>
