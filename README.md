# LV Game Toolkit

游戏开发测试工具集 — 集成设备管理、性能分析、日志分析等能力。

**远程仓库**：<https://gitee.com/lv-game-toolkit/lv-game-toolkit>

## 目录

- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [开发环境](#开发环境)
- [模块开发](#模块开发)
- [测试](#测试)
- [构建](#构建)
- [Git 与提交规范](#git-与提交规范)

## 快速开始

### 用户（解压即用）

下载发布包 → 解压 → 双击 `Toolkit.exe`。

要求：Windows 10+ x64，Android 设备已开启 USB 调试。

### 开发者

```bash
git clone https://gitee.com/lv-game-toolkit/lv-game-toolkit.git
cd lv-game-toolkit

# 创建虚拟环境（推荐使用 uv）
uv venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # Linux

# 安装依赖
uv pip install -e ".[dev]"

# 启动 GUI
python -m toolkit.app

# 启动 CLI
python -m toolkit.app version
python -m toolkit.app plugin list
```

## 项目结构

```
lv-game-toolkit/
├── toolkit/                # 核心框架
│   ├── app.py              # 应用入口（GUI/CLI 自动切换）
│   ├── core/               # 核心服务层
│   │   ├── config_manager.py
│   │   ├── db_manager.py
│   │   ├── event_bus.py
│   │   ├── plugin_manager.py
│   │   ├── service_registry.py
│   │   ├── adb_manager.py
│   │   ├── process_bridge.py
│   │   └── logger.py
│   ├── gui/                # PyQt6 GUI 框架
│   │   ├── main_window.py
│   │   ├── home_tab.py
│   │   ├── base_tab.py
│   │   ├── styles.py
│   │   └── widgets/
│   ├── cli/                # Typer CLI 框架
│   │   └── main.py
│   └── sdk/                # 模块开发 SDK
│       ├── base_plugin.py
│       ├── models.py
│       ├── protocols.py
│       └── constants.py
├── modules/                # 功能模块（插件）
│   ├── device_disguise/    # 设备伪装模块
│   ├── game_perf/          # 游戏性能配置模块
│   └── perfetto_capture/   # Perfetto 卡顿抓取模块
├── tests/                  # 自动化测试
├── scripts/                # 工具脚本
│   ├── create_module.py    # 模块脚手架
│   └── doc/                # 脚本说明文档
├── specs/                  # 规格文档（speckit 工作流）
├── .specify/               # speckit 配置与模板
├── .cursor/                # Cursor IDE 共享配置
│   ├── commands/           # speckit 命令
│   ├── skills/             # speckit 技能
│   └── rules/              # 开发规则
├── doc/                    # 文档中心
│   ├── architecture/      #   架构设计文档
│   └── legacy/            #   旧版文档归档（迁移参考）
├── _archived_source/       # 旧代码归档（迁移参考）
└── pyproject.toml          # 项目配置
```

## 开发环境

- **语言**：Python 3.12+
- **GUI**：PyQt6
- **CLI**：Typer + Rich
- **插件**：pluggy 1.3+
- **数据模型**：Pydantic 2.0+
- **数据库**：SQLite + JSON 配置
- **包管理**：uv（推荐）/ pip
- **测试**：pytest
- **代码质量**：Ruff

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
| [架构设计文档](doc/architecture/architecture-overview.md) | 项目完整架构设计（11 章） |
| [技术决策记录](doc/architecture/technical-decisions.md) | 12 项 ADR 决策记录 |
| [模块开发指导手册](scripts/doc/module-development-guide.md) | 端到端开发流程、代码模板、命令速查 |
| [常见踩坑指南](scripts/doc/development-pitfalls.md) | 14 项常见问题及解决方案 |
| [构建脚本文档](scripts/doc/build.md) | PyInstaller 构建流程与产物说明 |
| [Constitution](.specify/memory/constitution.md) | 项目最高治理文档 |
| [脚手架说明](scripts/doc/create_module.md) | create_module.py 使用说明 |
| [文档中心索引](doc/README.md) | 所有文档的结构化索引 |

## 测试

```bash
# 运行全部测试（180 项，含主项目+所有模块）
python scripts/run_all_tests.py

# 运行特定模块测试
.venv\Scripts\python.exe -m pytest modules/game_perf/tests/ -v
```

## 构建

```bash
# 完整构建（GUI + CLI + 打包）
python scripts/build.py

# 仅构建 GUI 用于测试
python scripts/build.py --gui-only --no-package
```

构建产物：
- `Toolkit.exe` — GUI 入口（双击启动，无控制台窗口）
- `toolkit-cli.exe` — CLI 入口（终端使用）
- `dist/lv-game-toolkit-v1.0.0-windows.zip` — 最终分发包

详细说明参见 [构建脚本文档](scripts/doc/build.md)。

## Git 与提交规范

### 提交信息模板

使用 [.github/COMMIT_MSG_TEMPLATE.md](.github/COMMIT_MSG_TEMPLATE.md) 格式提交。

协作者首次拉取后建议配置模板：

```bash
git config commit.template .github/COMMIT_MSG_TEMPLATE.md
```

### 分支策略

- `main` / `master`：稳定发布分支
- `refactoring`：架构重构分支（当前活跃）
- `feat/<module>-<feature>`：特性开发分支

### 忽略规则

`.gitignore` 忽略：虚拟环境、编译产物、运行时数据、Python 缓存等。

共享内容（需提交）：`.cursor/commands/`、`.cursor/skills/`、`.cursor/rules/`。

---

**Version**: 1.0.0 | **License**: 企业内部使用
