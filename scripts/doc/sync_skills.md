# sync_skills.py — 模块 Skills 同步脚本

## 目录

- [功能概述](#功能概述)
- [参数说明](#参数说明)
- [使用示例](#使用示例)
- [返回值与错误](#返回值与错误)

## 功能概述

扫描 `modules/*/skills/*/SKILL.md`，将模块级 Cursor Skills 复制到 `.cursor/skills/` 目录供 Cursor IDE 自动发现。同时更新 `.cursor/skills/.gitignore` 以排除同步副本。

**设计动机**：模块 Skills 的源文件应与模块代码一起管理（版本控制、打包），但 Cursor IDE 仅从 `.cursor/skills/` 发现 Skills，因此需要同步机制。

## 参数说明

| 参数 | 说明 |
|------|------|
| `sync`（默认） | 扫描并同步模块 Skills |
| `clean` | 清理所有由本脚本同步的条目（通过 `.module-synced` 标记识别） |

## 使用示例

```bash
# 同步模块 Skills
python scripts/sync_skills.py

# 显式指定 sync
python scripts/sync_skills.py sync

# 清理同步条目
python scripts/sync_skills.py clean
```

## 返回值与错误

- 退出码 0：操作成功
- 退出码 1：未知参数
- 未找到 `modules/` 目录时输出提示但不报错
- 未发现任何模块 Skills 时输出提示但不报错
