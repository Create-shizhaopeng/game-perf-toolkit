# build.py — 构建脚本

## 目录

- [功能概述](#功能概述)
- [参数说明](#参数说明)
- [使用示例](#使用示例)
- [构建产物](#构建产物)
- [数据收集函数](#数据收集函数)
- [返回值与错误](#返回值与错误)

## 功能概述

基于 PyInstaller 将 LV Game Toolkit 打包为可分发的可执行文件。
生成 GUI 和 CLI 双入口可执行文件，合并后打包为 zip（Windows）或
tar.gz（Linux）。

- **GUI 入口**：`Toolkit.exe` — 使用 `--noconsole`，双击直接启动图形界面
- **CLI 入口**：`toolkit-cli.exe` — 使用 `--console`，在终端中使用命令行

## 参数说明

| 参数 | 说明 |
|------|------|
| `--gui-only` | 仅构建 GUI 入口（Toolkit.exe） |
| `--cli-only` | 仅构建 CLI 入口（toolkit-cli.exe） |
| `--no-package` | 不执行最终打包（不生成 zip/tar.gz） |

无参数时执行完整构建流程：GUI + CLI + 打包。

## 使用示例

```powershell
# 完整构建（GUI + CLI + 打包）
python scripts/build.py

# 仅构建 GUI 用于测试
python scripts/build.py --gui-only --no-package

# 仅构建 CLI 用于测试
python scripts/build.py --cli-only --no-package
```

## 构建产物

```text
dist/
├── Toolkit/                        # GUI 构建目录
│   ├── Toolkit.exe                 #   GUI 入口（无控制台窗口）
│   └── _internal/                  #   运行时依赖
│       ├── modules/                #     模块文件
│       └── assets/                 #     资源文件（app.ico 等）
├── toolkit-cli/                    # CLI 构建目录
│   ├── toolkit-cli.exe             #   CLI 入口（有控制台窗口）
│   └── _internal/                  #   运行时依赖
├── lv-game-toolkit-v1.0.0-windows/ # 合并后的分发目录
│   ├── Toolkit.exe                 #   GUI 入口
│   ├── toolkit-cli.exe             #   CLI 入口
│   ├── data/                       #   运行时数据目录
│   └── _internal/                  #   共享运行时
│       ├── modules/                #     模块文件
│       └── assets/                 #     资源文件
└── lv-game-toolkit-v1.0.0-windows.zip  # 最终分发包
```

## 数据收集函数

| 函数 | 收集内容 | 说明 |
|------|----------|------|
| `_collect_modules()` | `modules/` 下运行时所需文件 | 仅包含 `src/`、`assets/`、`manifest.json`、`migrations/` 等运行时文件 |
| `_collect_data_dir()` | `data/` 目录结构 | 仅 `.gitkeep` 和必要模板 |
| `_collect_assets()` | `assets/` 资源文件 | 图标（`app.ico`）、Logo 等 |
| `_hidden_imports()` | 动态导入声明 | toolkit 核心、GUI、CLI 及各模块 src |

### _collect_modules 排除规则

| 排除项 | 类型 | 理由 |
|--------|------|------|
| `__pycache__` | 目录 | Python 编译缓存 |
| `data` | 目录 | 运行时生成的数据（DB、用户配置），不打入产物 |
| `.pytest_cache` | 目录 | pytest 缓存 |
| `out` | 目录 | speckit 输出 |
| `.cursor` | 目录 | Cursor IDE 命令配置 |
| `.specify` | 目录 | Speckit 模板、脚本、constitution |
| `specs` | 目录 | 规格文档（spec/plan/tasks/ui-design） |
| `tests` | 目录 | 测试文件 |
| `fixtures` | 目录 | 测试数据 |
| `image` | 目录 | 文档配图（README 等），运行时不需要 |
| `*.md` | 文件 | 开发文档（AGENTS.md 等） |
| `*.pyc` / `*.pyo` | 文件 | 编译字节码 |

新增模块或资源目录时，需在对应的收集函数中注册。

## 返回值与错误

| 退出码 | 说明 |
|--------|------|
| 0 | 构建成功 |
| 非 0 | PyInstaller 构建失败，查看终端输出排查 |

常见问题：
- **ModuleNotFoundError**: 新增模块后需确认 `_hidden_imports()` 覆盖
- **缺少 DLL**: 检查 PyQt6 安装完整性
- **文件过大**: 构建脚本已排除 PIL、numpy、pandas、matplotlib 等不必要包；模块目录中的开发文档、测试、IDE 配置等已排除（详见排除规则表）
- **GUI 启动崩溃**: 检查 `sys.stdout/stderr` 为 None 的情况（参见踩坑指南 P13）
- **资源文件找不到**: 确认 `_collect_assets()` 已包含新增资源（参见踩坑指南 P14）

## 代码规则（构建侧）

- 发布构建不改变 Python 代码风格约定；开发与合并仍须遵守 **[架构文档 §5.0 代码规则（总纲）](../../doc/architecture/architecture-overview.md#50-代码规则总纲)**（Ruff、分层、UTF-8 等）。
- 修改 `build.py` 或收集逻辑后：确认 **相关模块可被 PyInstaller 收集**（`_hidden_imports()` 等），并尽量在 **无控制台 GUI 模式** 下烟测（[development-pitfalls.md P13](development-pitfalls.md#p13--pyinstaller-noconsole-模式-sysstdoutstderr-为-none)、P14）。
