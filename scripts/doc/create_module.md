# create_module.py — 模块脚手架脚本

## 目录

- [功能概述](#功能概述)
- [代码规则](#代码规则)
- [参数说明](#参数说明)
- [使用示例](#使用示例)
- [返回值与错误](#返回值与错误)

## 功能概述

根据 `scripts/templates/` 下的模板文件，自动生成新模块的完整目录结构，并自动初始化 speckit。包括：

- `manifest.json` — 模块元数据
- `src/plugin.py` — 插件注册入口（预填命名空间 context 键）
- `src/service.py` — 服务层骨架
- `src/cli_commands.py` — CLI 子命令骨架
- `src/gui_tab.py` — GUI 页面骨架
- `AGENTS.md` — AI 开发规则（含踩坑指南引用）
- `tests/` — 测试目录及基础测试
- `specs/`、`fixtures/`、`assets/` — 辅助目录
- `.specify/` — speckit 管理目录（自动初始化，含模块级 constitution）
- `.cursor/commands/` — speckit slash 命令

## 代码规则

- 模块名 **必须** 为 `snake_case`（与 Python 包名一致），见下表参数说明。
- 生成骨架后，实现业务时遵守 **[架构文档 §5.0 代码规则（总纲）](../../doc/architecture/architecture-overview.md#50-代码规则总纲)**：Service 与 GUI/CLI 分离、context 键带模块前缀、Ruff + `.editorconfig`、合并前 pytest 等。
- 模块级 **`AGENTS.md` / `.specify/`** 是对 Constitution 的继承与补充，**不得**与总纲冲突。

## 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `module_name` | 是 | 模块名称，小写字母+下划线格式（如 `log_analysis`） |
| `--display-name` | 否 | 模块显示名称（如 `日志分析`），默认从模块名自动生成 |
| `--cli-ns` | 否 | CLI 命名空间（如 `log`），默认将下划线替换为连字符 |

## 使用示例

```powershell
# 基本用法
python scripts/create_module.py log_analysis

# 指定显示名称和 CLI 命名空间
python scripts/create_module.py trace_analysis --display-name "Trace分析" --cli-ns trace

# 查看帮助
python scripts/create_module.py -h
```

## 返回值与错误

- 成功时打印创建的目录路径和后续操作指引
- 模块名不合法（非小写字母+下划线）时报错退出
- 目录已存在时报错退出，防止覆盖
- speckit 初始化失败时打印警告，不阻断骨架创建（可后续手动初始化）

## 自动化行为

脚手架创建完成后会自动执行以下操作（需要 `uvx` 命令可用）：

1. 运行 `uvx --from git+https://github.com/github/spec-kit.git specify init --here --no-git --ai cursor-agent --script ps`
2. 生成模块级 `constitution.md`（继承主 Constitution，预填模块前缀和边界约束）
3. 如果 `uvx` 不可用，打印手动初始化命令
