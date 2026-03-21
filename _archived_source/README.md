# 待重构源码归档

## 目录

- [归档说明](#归档说明)
- [当前内容](#当前内容)
- [使用说明](#使用说明)

## 归档说明

本目录保存**尚未迁移到新架构**的旧版源码。已迁移完成的代码已于
2026-03-21 清理移除。

已完成迁移的模块：
- `device_disguise`（设备伪装） → `modules/device_disguise/`
- `game_perf`（游戏性能配置） → `modules/game_perf/`
- 核心框架（ADB、配置、数据库等） → `toolkit/core/`
- GUI 框架 → `toolkit/gui/`
- 构建系统 → `scripts/`

## 当前内容

| 文件 | 说明 | 目标 |
|------|------|------|
| `core/GamepolicyParse/get_game_policy.py` | 从 gameperfconfig.xml 按游戏提取策略的独立脚本 | 待决定：迁入 `scripts/` 或集成到 `game_perf` 模块 |

## 使用说明

本目录用于存放待重构集成的旧版功能源码。新功能完成重构后，
对应旧代码应从本目录移除。

**请勿在此目录下进行新的开发工作。**
