# create_module.py — 模块脚手架脚本

## 目录

- [功能概述](#功能概述)
- [参数说明](#参数说明)
- [使用示例](#使用示例)
- [返回值与错误](#返回值与错误)

## 功能概述

根据 `scripts/templates/` 下的模板文件，自动生成新模块的完整目录结构，包括：

- `manifest.json` — 模块元数据
- `src/plugin.py` — 插件注册入口
- `src/service.py` — 服务层骨架
- `src/cli_commands.py` — CLI 子命令骨架
- `src/gui_tab.py` — GUI 页面骨架
- `AGENTS.md` — AI 开发规则
- `tests/` — 测试目录及基础测试
- `specs/`、`fixtures/`、`assets/` — 辅助目录

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
