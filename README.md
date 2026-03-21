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
│   └── game_perf/          # 游戏性能配置模块
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
├── doc/                    # 旧项目文档（迁移参考）
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
python scripts/create_module.py <模块名>
```

生成的模块骨架包含：`manifest.json`、`plugin.py`、`service.py`、`cli_commands.py`、`gui_tab.py`、`AGENTS.md` 和测试文件。

### Spec-Driven 开发流程

每个模块使用独立的 speckit 工作流：

```bash
cd modules/<模块名>
uvx --from git+https://github.com/github/spec-kit.git specify init --here --no-git --ai cursor-agent --script ps
```

然后按流程执行：specify → plan → tasks → implement → analysis。

详见 Constitution 文档：[.specify/memory/constitution.md](.specify/memory/constitution.md)

## 测试

```bash
# 运行全部测试（83 项）
.venv\Scripts\python.exe -m pytest tests/ -v

# 运行特定测试
.venv\Scripts\python.exe -m pytest tests/test_config_manager.py -v
```

## 构建

```bash
# PyInstaller onedir 模式
pyinstaller --noconfirm --onedir toolkit/app.py
```

## Git 与提交规范

### 提交信息模板

使用 [.github/COMMIT_MSG_TEMPLATE.md](.github/COMMIT_MSG_TEMPLATE.md) 格式提交。

协作者首次拉取后建议配置模板：

```bash
git config commit.template .github/COMMIT_MSG_TEMPLATE.md
```

### 分支策略

- `master`：稳定发布分支
- `refactoring`：架构重构分支（当前活跃）
- `feat/<module>-<feature>`：特性开发分支

### 忽略规则

`.gitignore` 忽略：虚拟环境、编译产物、运行时数据、Python 缓存等。

共享内容（需提交）：`.cursor/commands/`、`.cursor/skills/`、`.cursor/rules/`。

---

**Version**: 1.0.0 | **License**: 企业内部使用
