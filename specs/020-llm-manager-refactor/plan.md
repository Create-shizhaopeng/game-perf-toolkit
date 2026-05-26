# Implementation Plan: LLM Manager 模块重构

**Branch**: `dev` | **Date**: 2026-05-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from [spec.md](spec.md)

## Summary

创建新模块 `modules/llm_manager/`，将 LLM Provider 配置从硬编码的 `toolkit/core/llm/` 和 `toolkit_config.json` 中抽离为独立的 `data/config/llm_providers.json` 配置文件。支持多 Provider（GLM、Claude、DeepSeek 等），每个 Provider 可自定义 API 地址、模型列表、API Key。精简 LLM 设置面板为 Provider 下拉 + Model 下拉 + Thinking 开关三个控件。新增 Thinking 特性支持（Anthropic extended thinking API）。Token 用量后台记录到 SQLite（四维度：request/conversation/trace/total）。状态栏上下文用量显示改为纯圆环填充百分比（hover 显示精确数字，无文字标签，无颜色区分）。

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: PyQt6, LiteLLM, Pydantic 2.0+, pluggy 1.3+
**Storage**: JSON 文件（`data/config/llm_providers.json`）+ SQLite（`data/db/llm_token_usage.db`）
**Testing**: pytest
**Target Platform**: Windows desktop (dev) / Windows exe (frozen)
**Project Type**: desktop-app (PyQt6 GUI + MCP Server)
**Performance Goals**: Token 记录 1 秒内持久化；上下文圆环 500ms 内更新；模型切换 200ms 内更新
**Constraints**: 模块 MUST NOT 修改 `toolkit/` 核心框架目录（除了必要的 `LLMConfig` 字段精简和 `LLMManager/LiteLLMProvider` 参数扩展）；设置面板控件 ≤ 5 个
**Scale/Scope**: 单用户桌面应用，Provider 数量 ≤ 20 个

## Constitution Check

*GATE: 项目的 `.specify/memory/constitution.md` 为未填充模板，无硬性门禁。替代使用项目 `CLAUDE.md` 中的开发规范作为门禁。*

| 门禁 | 状态 | 说明 |
|------|------|------|
| 模块 MUST NOT 修改 `toolkit/` 核心框架 | ⚠️ 必要改动 | `LLMConfig` 字段精简、`LLMManager`/`LiteLLMProvider` 参数扩展是本次重构目标 |
| GUI MUST 使用 QThread + pyqtSignal | ✅ 不涉及 | llm_manager 无后台线程操作 |
| 中文 MUST 提取到 `strings_*.py` | ✅ 落实 | 新增 `strings_gui.py` + `strings_service.py` |
| 日志 MUST 使用统一日志体系 | ✅ 落实 | 通过 `logging.getLogger(__name__)` |
| 图标 MUST 使用 codicon | ✅ 落实 | 所有 GUI 图标走 codicon 字体 |
| 对话框 MUST 继承 `ToolkitDialog` | ✅ 落实 | `ProviderManageDialog` 继承 `ToolkitDialog` |
| QSS MUST 通过 `objectName` + `styles.py` | ✅ 落实 | 所有新控件有 objectName，QSS 写入全局 styles.py |
| 路径 MUST 通过 `app_paths` | ✅ 落实 | 配置文件走 `get_exe_dir() / "data" / "config"` |
| 模块 MUST NOT 跨模块直接操作数据 | ✅ 落实 | conversation_id 由 Agent Chat 传入 |

## Project Structure

### Documentation (this feature)

```
specs/020-llm-manager-refactor/
├── spec.md              # Feature specification
├── ui-mockups.md        # UI ASCII diagrams
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── service-api.md   # LLMManagerService public API contract
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

详细 API 约定见 [contracts/service-api.md](contracts/service-api.md)，此处仅列出目录结构。

```
modules/llm_manager/                  # ← 新建模块
├── manifest.json
├── AGENTS.md
├── config/
│   └── llm_providers.json           # 默认模板（首次复制到 data/config/）
├── src/
│   ├── __init__.py
│   ├── plugin.py                    # BasePlugin hooks
│   ├── service.py                   # LLMManagerService
│   ├── models.py                    # ProviderConfig, ModelConfig, token record
│   ├── token_tracker.py             # TokenTracker (SQLite)
│   ├── provider_dialog.py           # ProviderManageDialog
│   ├── strings_gui.py               # GUI 中文字符串常量
│   └── strings_service.py           # 服务层字符串常量
└── tests/                             (T055 创建)
    ├── __init__.py
    ├── test_service.py
    ├── test_models.py
    └── test_token_tracker.py

toolkit/core/llm/                    # ← 精简修改
├── manager.py                       # 修改: 加载 llm_providers.json, 精简字段
├── litellm_provider.py              # 修改: 接收 api_base + thinking 参数
└── models.py                        # 修改: 移除硬编码 context windows (迁移到 llm_manager)

toolkit/sdk/models.py                # ← 修改: LLMConfig 移除已废弃字段

toolkit/gui/
├── llm_settings_dialog.py           # 修改: 精简为 3 控件
├── widgets/llm_status_widget.py     # 修改: 移除文字标签和颜色区分
├── styles.py                        # 修改: 新增 QSS 样式
└── strings.py                       # 修改: 新增字符串常量

data/config/
└── llm_providers.json               # ← 运行时生成 (首次启动自动创建)

data/db/
└── llm_token_usage.db               # ← 运行时生成 (首次记录时创建)
```

## Complexity Tracking

> 项目 Constitution 为空模板，本表替代门禁跟踪。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| 修改 `toolkit/core/llm/` 框架层代码 | 框架层 manager/provider 必须适配新的配置来源和参数 | 无法避免：LLMConfig 字段精简、LiteLLMProvider 接收 api_base/thinking 参数是功能核心 |
| 新建独立模块 | Provider 管理需要独立的 service + GUI + 配置 | 放在现有模块中会违反单一职责，且不利于后续飞书集成扩展 |
| 修改 `toolkit/sdk/models.py` | LLMConfig Pydantic 模型必须移除硬编码的 provider 限制 | 不修改则无法支持自定义 provider |
