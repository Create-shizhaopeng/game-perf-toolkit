# Game Perf Toolkit

游戏性能测试工具集 — 集成设备管理、性能分析、日志分析等能力。

**远程仓库**：GitHub [`Create-shizhaopeng/game-perf-toolkit`](https://github.com/Create-shizhaopeng/game-perf-toolkit)（公开）

## 目录

- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [开发环境](#开发环境)
- [模块开发](#模块开发)
- [测试](#测试)
- [构建](#构建)
- [Git 与提交规范](#git-与提交规范)

## 快速开始

### 用户（安装版）

下载 `Setup.exe` → 双击安装 → 从开始菜单或桌面快捷方式启动。

应用内自动检查更新（GitHub Releases feed），有新版本后台 delta 下载，下次启动生效。用户数据独立保存，升级不丢失。

> 老便携版（zip）用户：首次启动新安装版会弹出数据迁移助手，选择旧便携版目录即可迁移历史数据。

要求：Windows 10+ x64，Android 设备已开启 USB 调试。

### 开发者

```bash
git clone git@github.com:Create-shizhaopeng/game-perf-toolkit.git
cd game-perf-toolkit

# 创建虚拟环境（推荐使用 uv）
uv venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # Linux

# 安装依赖
uv pip install -e ".[dev]"

# 启动 GUI
python -m toolkit.app

# 启动 MCP Server
python -m toolkit.app mcp-serve
```

## 项目结构

```
game-perf-toolkit/
├── toolkit/                # 核心框架
│   ├── app.py              # 应用入口（GUI / MCP Server 切换）
│   ├── agent/              # Agent 核心引擎（orchestrator/service/gui/skill_router）
│   ├── core/               # 核心服务层
│   │   ├── config_manager.py
│   │   ├── db_manager.py
│   │   ├── event_bus.py
│   │   ├── plugin_manager.py
│   │   ├── service_registry.py
│   │   ├── tool_registry.py
│   │   ├── skill_registry.py
│   │   ├── app_paths.py
│   │   ├── unified_logger.py
│   │   ├── adb_manager.py
│   │   ├── mcp/            # MCP server/registry/client/bridge
│   │   └── llm/            # LLM Manager + Provider（基于 LiteLLM）
│   ├── gui/                # PyQt6 GUI 框架
│   │   ├── main_window.py
│   │   ├── base_tab.py
│   │   ├── styles.py
│   │   ├── panels/         # LeftPanel/BottomPanel/RightPanel/HistoryArea
│   │   └── widgets/        # TitleBar/NavPanel/BaseHistoryTreeWidget 等
│   └── sdk/                # 模块开发 SDK
│       ├── base_plugin.py
│       ├── models.py
│       ├── protocols.py
│       └── constants.py
├── modules/                # 功能模块（插件）
│   ├── agent_chat/         # Agent 兼容垫片（核心已下沉到 toolkit/agent）
│   ├── device_disguise/    # 设备伪装模块
│   ├── llm_manager/        # LLM 管理模块
│   ├── perfdog_insights/   # PerfDog 导入分析模块
│   ├── perfetto_analysis/  # Perfetto 解析分析模块
│   └── perfetto_capture/   # Perfetto 卡顿抓取模块
├── tests/                  # 自动化测试
├── scripts/                # 工具脚本
│   ├── build.py            # 构建（PyInstaller + Velopack）
│   ├── create_module.py    # 模块脚手架
│   ├── run_all_tests.py   # 全量测试
│   └── doc/                # 脚本说明文档
├── specs/                  # 规格文档（speckit 工作流）
├── .specify/               # speckit 配置与模板
├── .claude/rules/          # Claude Code 项目规则
├── .cursor/                # Cursor IDE 共享配置（commands/skills/rules）
├── docs/                   # 文档中心
│   ├── PROGRESS.md        #   项目进度总览
│   ├── README.md          #   文档中心索引
│   ├── architecture/      #   架构设计文档
│   ├── knowledge/         #   项目知识库
│   ├── experience/        #   踩坑经验库
│   └── team/              #   团队规范
└── pyproject.toml          # 项目配置
```

> `modules/game_perf/`（游戏性能配置）为本地保留模块，已通过 `.gitignore` 排除公开发布，clone 后不会看到。

## 开发环境

- **语言**：Python 3.12+
- **GUI**：PyQt6
- **插件**：pluggy 1.3+
- **Agent**：基于 LiteLLM 的多 LLM Provider（`toolkit/core/llm/`）
- **MCP**：FastMCP（stdio/sse/streamable-http）
- **数据模型**：Pydantic 2.0+
- **数据库**：SQLite + JSON 配置
- **包管理**：uv（推荐）/ pip
- **测试**：pytest
- **代码质量**：Ruff

> 安装 Agent 相关依赖（zhipuai/anthropic/mcp 等）：`uv pip install -e ".[agent]"`

## 模块开发

### 创建新模块

```bash
python scripts/create_module.py <模块名> --display-name "显示名称"
```

脚手架自动完成：生成模块骨架、初始化 speckit、生成模块级 Constitution。

### Spec-Driven 开发流程

每个模块使用独立的 speckit 工作流（8 步）：

specify → clarify → UE/UI design → plan → tasks → analysis → implement → analysis

### 开发文档

| 文档 | 说明 |
|------|------|
| [架构设计文档](docs/architecture/architecture-overview.md) | 项目完整架构设计（11 章） |
| [技术决策记录](docs/architecture/technical-decisions.md) | 12 项 ADR 决策记录 |
| [模块开发指导手册](docs/knowledge/module-development-guide.md) | 端到端开发流程、代码模板、命令速查 |
| [常见踩坑指南](docs/experience/development-pitfalls.md) | 25 项常见问题及解决方案 |
| [构建脚本文档](scripts/doc/build.md) | PyInstaller 构建流程与产物说明 |
| [Constitution](.specify/memory/constitution.md) | 项目最高治理文档 |
| [脚手架说明](scripts/doc/create_module.md) | create_module.py 使用说明 |
| [文档中心索引](docs/README.md) | 所有文档的结构化索引 |

## 测试

```bash
# 运行全部测试（主项目 + 所有模块）
python scripts/run_all_tests.py

# 运行特定模块测试
python -m pytest modules/perfetto_capture/tests/ -v

# 运行单个测试文件
python -m pytest modules/device_disguise/tests/test_models.py -v
```

## 构建

```bash
# 完整构建（PyInstaller → Velopack 打包 Setup.exe + delta 更新包）
python scripts/build.py

# 仅构建 GUI 用于测试（不打包；--no-package 跳过 Velopack 打包）
python scripts/build.py --no-package

# 额外产出便携 zip（过渡期兼容）
python scripts/build.py --zip

# 手动指定版本号
python scripts/build.py --version 1.2.3
```

构建产物：
- `dist/publish/` — PyInstaller `--onedir` 产出（Velopack 打包输入）
- `dist/Setup.exe` — Velopack 安装包（首次安装）
- `dist/*.nupkg` / delta 包 — 发布到 GitHub Releases feed 供自动更新
- `--zip` 时额外产 `dist/game-perf-toolkit-v{version}-windows.zip`（便携包）

> Velopack 打包前置：`dotnet tool install -g vpk`（需 .NET SDK）。代码签名可选（环境变量 `VP_SIGNING_CERT`）。

详细说明参见 [构建脚本文档](scripts/doc/build.md) 与 [分发架构](docs/architecture/distribution-paths-architecture.md)。

## Git 与提交规范

### 提交信息格式

采用 Conventional Commits 风格：`<type>(<scope>): <subject>`，例如 `fix(gui): 修复 TitleBar 启动崩溃`、`feat(perfetto_capture): Jank 监测前台热切换`。常见 type：`feat` / `fix` / `docs` / `refactor` / `test` / `chore`。

### 分支策略

- `master`：稳定发布分支
- `dev`：开发集成分支
- `toTester`：测试交付分支
- `feat/<module>-<feature>`：特性开发分支

### 忽略规则

`.gitignore` 忽略：虚拟环境、编译产物、运行时数据、Python 缓存等。

共享内容（需提交）：`.cursor/commands/`、`.cursor/skills/`、`.cursor/rules/`。

---

**Version**: 1.0.0 | **License**: 企业内部使用
