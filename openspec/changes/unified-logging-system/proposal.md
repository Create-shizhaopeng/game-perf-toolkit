## Why

当前项目存在**两套完全独立的日志体系**：Python 标准 `logging`（61+ 文件用于调试/后台输出）与 GUI `LogManager`（底部面板展示）。两者互不打通，导致：后台异常日志在 GUI 中不可见；GUI 面板日志无法持久化到文件；多处 `print()` 散落（尤其是 `perfetto_analysis/src/engine/` 模块），严重干扰终端输出。现需对日志系统进行统一规划，补全缺失的链路。

## What Changes

- **统一日志路由层**：新建 `UnifiedLogger`，将 `logging` 与 `LogManager` 打通，实现后台日志自动推送到 GUI 面板、GUI 日志可写文件
- **日志文件持久化**：增加文件日志支持（含轮转），支持按模块分文件存储
- **移除 print 污染**：将散落在 `perfetto_analysis/src/engine/` 及 `plugin.py` 中的 `print()` 替换为统一日志接口
- **清理冗余组件**：移除无人引用的 `LogTextEdit`（已废弃）
- **主题安全修复**：修复 `game_perf/gui_tab.py` 中硬编码颜色字符串的隐患
- **结构化日志支持**：API/分析类模块的日志统一使用结构化格式（JSON Lines/键值对），便于后续自动化分析

## Capabilities

### New Capabilities
- `unified-logging-core`: 统一日志核心框架，含 `UnifiedLogger` 类、`LogBridge` 桥接器、文件轮转策略
- `structured-logging-api`: 结构化的模块日志接口（`log_event(start_time, process_name, fields...)`），供 perfetto_analysis 等模块使用
- `gui-log-panel-v2`: 日志面板增强，支持日志源优先级排序、时间线视图、搜索过滤、导出面板日志到文件

### Modified Capabilities
- （无修改现有 spec 的需求，此变更属于基础设施层重构，不涉及模块功能需求变化）

## Impact

- **文件**: `toolkit/core/logger.py`, `toolkit/gui/log_manager.py`, `toolkit/gui/base_tab.py`, `toolkit/gui/log_widget.py`（可能删除）
- **模块**: `perfetto_analysis`（engine/ 下 print 替换）、`game_perf`（主题颜色修复）、`agent_chat`（startup print 替换）
- **API 变更**: `BaseTab._log()` 签名不变（向后兼容），新增可选 keyword 参数 `details`
- **依赖增减**: 需引入 `loguru`（统一日志库，零配置即开即用）
- **用户影响**: GUI 底部面板新增「控制台日志」频道，可查看后台 logging 输出；日志文件按日期轮转，调试更方便
- **构建打包影响**: 新增 `loguru` 需同步更新 `[build]` `hiddenimports` 和 `requirements`
