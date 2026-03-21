# Implementation Plan: 框架完善与验证

**Branch**: `001-framework-completion` | **Date**: 2026-03-20 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-framework-completion/spec.md`

## Summary

完善 LV Game Toolkit 核心框架，覆盖四个方面：
1. GUI 主窗口验证和修复（自定义标题栏、导航面板、主题切换、设备断开状态处理）
2. 核心服务层单元测试覆盖（ConfigManager、EventBus、ServiceRegistry、DatabaseManager、PluginManager、AdbManager 基础场景）
3. CLI 内置命令和脚手架脚本的自动化验证
4. 日志级别可配置（config.json + CLI --verbose/--debug 参数）

框架层代码已基本完成，本次工作聚焦于验证、测试、澄清需求实现和修复。

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: PyQt6, Typer, Rich, Pydantic, pluggy
**Storage**: SQLite (via toolkit.core.db_manager), JSON config
**Testing**: pytest
**Target Platform**: Windows 10+ / Linux, 解压即用
**Project Type**: desktop-app (GUI + CLI 双入口)
**Performance Goals**: GUI 启动 < 3s, CLI 命令响应 < 2s
**Constraints**: UTF-8 中文输出无乱码, 无边框窗口拖拽流畅
**Scale/Scope**: 2-5 人团队, 当前 2 个骨架模块

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 状态 | 说明 |
|------|------|------|
| Plugin-First | ✅ | 模块已独立在 modules/ 下，通过 manifest.json 声明 |
| Three-Surface Unity | ✅ | GUI/CLI/Agent 共享 service 层设计已就位 |
| Agent-Driven Design | ✅ | ServiceRegistry + hookspecs 预留 Agent 工具注册 |
| Dependency Inversion | ✅ | 模块依赖 toolkit.sdk，核心不依赖模块 |
| Presentation Separation | ✅ | service.py 不含 GUI/CLI 代码 |
| Open-Closed | ✅ | 新模块通过 pluggy 自动发现，无需修改核心 |
| Spec-Driven Development | ✅ | 当前正在按 speckit 工作流执行 |

## Project Structure

### Documentation (this feature)

```text
specs/001-framework-completion/
├── spec.md              # 规格文档
├── plan.md              # 本文件 — 实现计划
├── research.md          # 技术调研（本次较简单）
├── checklists/          # 质量检查清单
│   └── requirements.md
└── tasks.md             # 任务列表（/speckit.tasks 生成）
```

### Source Code (repository root)

```text
toolkit/
├── core/                # 核心服务层（已完成，需测试）
│   ├── adb_manager.py
│   ├── config_manager.py
│   ├── db_manager.py
│   ├── event_bus.py
│   ├── hookspecs.py
│   ├── logger.py
│   ├── plugin_manager.py
│   ├── process_bridge.py
│   └── service_registry.py
├── sdk/                 # 公共 SDK（已完成，需测试）
│   ├── base_plugin.py
│   ├── models.py
│   ├── protocols.py
│   ├── exceptions.py
│   ├── utils.py
│   └── constants.py
├── gui/                 # GUI 框架（已完成，需启动验证）
│   ├── main_window.py
│   ├── home_tab.py
│   ├── base_tab.py
│   ├── device_monitor.py
│   ├── styles.py
│   └── widgets/
│       ├── title_bar.py
│       └── nav_panel.py
├── cli/                 # CLI 框架（已完成，需自动化测试）
│   └── main.py
└── app.py               # 应用入口

tests/
├── test_config_manager.py
├── test_event_bus.py
├── test_service_registry.py
├── test_db_manager.py
├── test_plugin_manager.py
├── test_adb_manager.py
├── test_cli.py
└── test_scaffold.py

scripts/
└── create_module.py     # 脚手架（已完成，需测试）
```

**Structure Decision**: 使用已有的 toolkit/ 分层结构，测试文件放在项目根 tests/ 目录。

## Complexity Tracking

无违规项 — 框架结构符合 Constitution 所有原则。
