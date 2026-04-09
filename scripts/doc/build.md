# build.py — 构建脚本

## 目录

- [功能概述](#功能概述)
- [参数说明](#参数说明)
- [使用示例](#使用示例)
- [版本号管理](#版本号管理)
- [构建产物](#构建产物)
- [依赖排除](#依赖排除)
- [数据收集函数](#数据收集函数)
- [返回值与错误](#返回值与错误)

## 功能概述

基于 PyInstaller 将 LV Game Toolkit 打包为可分发的可执行文件。
仅执行一次 PyInstaller 构建（GUI），CLI 入口通过 PE header patch 生成，
总构建时间比双次构建减少 ~63%。

- **GUI 入口**：`Toolkit.exe` — 使用 `--noconsole`，双击直接启动图形界面
- **CLI 入口**：`toolkit-cli.exe` — 通过 PE 头 Subsystem 标志从 GUI exe 派生

## 参数说明

| 参数 | 说明 |
|------|------|
| `--gui-only` | 仅构建 GUI 入口（Toolkit.exe） |
| `--cli-only` | 仅构建 CLI 入口（toolkit-cli.exe） |
| `--no-package` | 不执行最终打包（不生成 zip/tar.gz） |
| `--version` | 手动指定版本号（覆盖 git tag 自动提取） |

无参数时执行完整构建流程：GUI + CLI + 打包。

## 使用示例

```powershell
# 完整构建（GUI + CLI + 打包）
python scripts/build.py

# 仅构建 GUI 用于测试
python scripts/build.py --gui-only --no-package

# 手动指定版本号
python scripts/build.py --version 0.2.0
```

## 版本号管理

版本号遵循 SemVer 规范 (`MAJOR.MINOR.PATCH`)：

| 变更类型 | 版本位 | 示例 |
|---------|--------|------|
| Bug 修复、小调整 | PATCH +1 | v0.1.1 → v0.1.2 |
| 需求更新、功能迭代 | MINOR +1, PATCH 归零 | v0.1.2 → v0.2.0 |
| 新增模块、框架重构 | MAJOR +1, 其余归零 | v0.2.0 → v1.0.0 |

**自动提取流程**：

1. 构建脚本通过 `git describe --tags --abbrev=0` 读取最近的 tag
2. 将版本号写入项目根 `VERSION` 文件（已加入 .gitignore）
3. `VERSION` 文件被打入 PyInstaller 产物根目录
4. `toolkit/__init__.py` 的 `__version__` 优先从 `VERSION` 文件读取

**发版步骤**：

```powershell
git tag v0.2.0
git push origin v0.2.0
python scripts/build.py
```

## 构建产物

```text
dist/
├── Toolkit/                            # GUI 构建目录
│   ├── Toolkit.exe                     #   GUI 入口（无控制台窗口）
│   └── _internal/                      #   运行时依赖
│       ├── modules/                    #     模块文件
│       ├── assets/                     #     资源文件（app.ico 等）
│       └── VERSION                     #     版本号文件
├── lv-game-toolkit-vX.Y.Z-windows/     # 合并后的分发目录
│   ├── Toolkit.exe                     #   GUI 入口
│   ├── toolkit-cli.exe                 #   CLI 入口 (PE patch)
│   ├── VERSION                         #   版本号文件
│   ├── data/                           #   运行时数据目录
│   └── _internal/                      #   共享运行时
└── lv-game-toolkit-vX.Y.Z-windows.zip  # 最终分发包
```

## 依赖排除

以下未使用的传递依赖被排除，节省 ~55 MB：

| 依赖 | 来源 | 说明 |
|------|------|------|
| botocore, boto3, s3transfer | litellm | AWS SDK，未使用 |
| grpc, grpcio | litellm | gRPC，未使用 |
| hf_xet, huggingface_hub | litellm/tokenizers | HuggingFace，未使用 |
| IPython, jedi, parso | 间接依赖 | 交互式 Python，生产不需要 |
| fastavro | 间接依赖 | Avro 序列化，未使用 |
| tokenizers | tiktoken | HF tokenizers，未使用 |
| cohere | litellm | Cohere API，未使用 |
| opentelemetry_* | logfire | 可观测性，未使用 |
| logfire | litellm | 日志服务，未使用 |
| pytest, coverage | 开发工具 | 测试框架，生产不需要 |

如需恢复某个依赖，从 `build.py` 的 `EXCLUDE_MODULES` 列表中移除即可。

## 数据收集函数

| 函数 | 收集内容 | 说明 |
|------|----------|------|
| `_collect_modules()` | `modules/` 下运行时所需文件 | 仅包含 `src/`、`assets/`、`manifest.json`、`migrations/` 等运行时文件 |
| `_collect_data_dir()` | `data/` 目录结构 | 仅 `.gitkeep` 和必要模板 |
| `_collect_assets()` | `assets/` 资源文件 | 图标（`app.ico`）、Logo 等 |
| `_collect_perfetto_data()` | perfetto 包的 descriptor/proto 文件 | trace processor 运行时需要 |
| `_hidden_imports()` | 动态导入声明 | toolkit 核心、GUI、CLI 及各模块 src |
| `_get_version()` | 版本号 | 从 git tag 提取 |
| `_set_pe_subsystem()` | PE 头修改 | 将 GUI exe 的 Subsystem 改为 Console |

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
| `*.md` | 文件 | 开发文档（AGENTS.md 等），但 SOP/SKILL 中的 .md 保留 |
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
- **文件过大**: 检查 `EXCLUDE_MODULES` 是否需要新增排除项
- **GUI 启动崩溃**: 检查 `sys.stdout/stderr` 为 None 的情况（参见踩坑指南 P13）
- **资源文件找不到**: 确认 `_collect_assets()` 已包含新增资源（参见踩坑指南 P14）
- **CLI 入口不工作**: PE patch 仅在 Windows 上支持；检查 `_set_pe_subsystem()` 是否成功
- **版本号未更新**: 确认已执行 `git tag` 并推送

## 代码规则（构建侧）

- 发布构建不改变 Python 代码风格约定；开发与合并仍须遵守 **[架构文档 §5.0 代码规则（总纲）](../../doc/architecture/architecture-overview.md#50-代码规则总纲)**（Ruff、分层、UTF-8 等）。
- 修改 `build.py` 或收集逻辑后：确认 **相关模块可被 PyInstaller 收集**（`_hidden_imports()` 等），并尽量在 **无控制台 GUI 模式** 下烟测（[development-pitfalls.md P13](../../doc/experience/development-pitfalls.md#p13--pyinstaller-noconsole-模式-sysstdoutstderr-为-none)、P14）。
