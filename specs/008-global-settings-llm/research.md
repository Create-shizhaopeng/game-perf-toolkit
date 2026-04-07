# Research: 全局设置与 LLM 能力抽象

**Feature**: 008-global-settings-llm | **Date**: 2026-04-03

## 目录

- [技术栈确认](#技术栈确认)
- [PyQt6 自定义绘制](#pyqt6-自定义绘制)
- [线程安全模式](#线程安全模式)
- [配置迁移策略](#配置迁移策略)

## 技术栈确认

所有技术栈已在项目中使用，无需外部调研：

| 技术 | 状态 | 在项目中的使用位置 |
|------|------|-------------------|
| PyQt6 | ✅ 已使用 | `toolkit/gui/`, 各模块 `gui_tab.py` |
| anthropic | ✅ 已使用 | `modules/agent_chat/src/llm/claude_provider.py` |
| zhipuai | ✅ 已使用 | `modules/agent_chat/src/llm/glm_provider.py` |
| Pydantic 2.0+ | ✅ 已使用 | 各模块 `models.py` |
| ConfigManager | ✅ 已使用 | `toolkit/core/config_manager.py` |

## PyQt6 自定义绘制

- **Decision**: 使用 QPainter 在 QWidget.paintEvent 中绘制空心圆环
- **Rationale**: 项目中已有 ThemeButton 的自定义绘制先例（太阳/月亮图标），团队熟悉此模式
- **Alternatives considered**: QSvgWidget（需要额外 SVG 资源管理）、QProgressBar 设置为环形（样式受限）

## 线程安全模式

- **Decision**: 使用 `threading.Lock` 保护 `_provider` 和 `_session_tokens` 的读写
- **Rationale**: 
  - QMutex 是 Qt 原生方案，但 `threading.Lock` 更 Pythonic 且在项目中已有使用
  - Provider 实例化在主线程（配置变更时），`stream_chat` 调用在工作线程（QThread）
  - Lock 粒度：仅保护 `get_provider()` 返回引用和 `record_tokens()` 累加操作
- **Alternatives considered**: QMutex（Qt 原生但增加依赖）、无锁只用 signal/slot（无法保护非 Qt 代码路径）

## 配置迁移策略

- **Decision**: 首次启动时一次性迁移，标记 `_migrated: true`
- **Rationale**: 
  - 简单可靠，不引入持续的兼容逻辑
  - agent_chat 旧配置文件路径已知且固定（`modules/agent_chat/data/config.json`）
  - 迁移标记防止多次执行
- **Alternatives considered**: 双读策略（框架配置优先，回退读 agent_chat）— 增加复杂度且长期维护成本高
