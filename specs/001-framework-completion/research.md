# Research: 框架完善与验证

**Branch**: `001-framework-completion` | **Date**: 2026-03-20

## 调研背景

本次是对已实现框架代码的完善和验证，技术栈已在架构设计阶段确定，无需重新调研。以下记录关键技术决策的确认。

## 技术决策确认

### 1. GUI 无边框窗口实现

- **Decision**: 使用 `Qt.WindowType.FramelessWindowHint` + 自定义 TitleBar 实现拖拽
- **Rationale**: PyQt6 原生支持，无需第三方库，自定义 TitleBar 可集成设备状态
- **Alternatives considered**: 系统原生标题栏（无法定制），第三方库如 PyQtDarkTheme（依赖过重）

### 2. 主题系统方案

- **Decision**: QSS 字符串切换（暗色/亮色两套完整样式表）
- **Rationale**: 简单直接，通过 `QApplication.setStyleSheet()` 全局应用，支持运行时切换
- **Alternatives considered**: QML 主题引擎（复杂度过高），QPalette（样式控制力不足）

### 3. 测试策略

- **Decision**: pytest 单元测试覆盖核心服务，GUI 部分通过手动启动验证
- **Rationale**: 核心服务逻辑可独立测试，GUI 测试需要 QApplication 上下文且自动化成本高
- **Alternatives considered**: pytest-qt（适合深度 GUI 测试，当前阶段不需要）

### 4. 插件动态导入

- **Decision**: `importlib.util.spec_from_file_location` + 手动注册父包到 `sys.modules`
- **Rationale**: modules/ 不是标准 Python 包，需要支持模块内部的相对导入（如 `from .cli_commands import ...`）
- **Alternatives considered**: 将 modules/ 加入 sys.path（污染全局命名空间），使用 entry_points（需要每个模块单独安装）

### 5. 设备断开时的 UX 行为

- **Decision**: 标题栏显示断开状态，涉及设备操作的功能按钮禁用，点击时提示"设备已断开"，用户已填写数据保留
- **Rationale**: 不丢失用户工作数据，同时明确指示哪些操作不可用
- **Alternatives considered**: 全屏遮罩提示（打断用户工作流），仅标题栏提示不禁用按钮（可能导致误操作）

### 6. 日志级别配置策略

- **Decision**: config.json 配置日志级别 + CLI --verbose/--debug 参数覆盖，CLI 参数优先级高于配置文件
- **Rationale**: 双通道配置适应不同场景：config.json 适合长期设置，CLI 参数适合临时调试
- **Alternatives considered**: 固定 INFO（不够灵活），仅 config.json（CLI 调试不便）

## 结论

所有技术决策已在实现中验证可行，澄清会议补充了设备断开行为和日志级别配置策略。进入实现阶段。
