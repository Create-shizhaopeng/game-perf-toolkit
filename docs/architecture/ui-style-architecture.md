# UI 样式管理架构

## 目录

- [概述](#概述)
- [样式管理分层](#样式管理分层)
  - [第一层：全局 QSS（styles.py）](#第一层全局-qssstylespy)
  - [第二层：颜色常量（theme_colors.py）](#第二层颜色常量theme_colorspy)
  - [第三层：模块内联样式](#第三层模块内联样式)
- [主题切换机制](#主题切换机制)
- [共享组件](#共享组件)
  - [ToolkitDialog](#toolkitdialog)
  - [DialogCloseButton](#dialogclosebutton)
- [日志面板系统](#日志面板系统)
- [objectName 命名规范](#objectname-命名规范)
- [文件清单](#文件清单)

## 概述

本项目的 GUI 基于 PyQt6 构建，采用 Catppuccin 调色板（Mocha 暗色 + Latte 亮色）作为设计语言。样式管理遵循「全局优先、按需内联」的原则，通过 Qt Style Sheet (QSS) 实现主题化。

核心设计目标：
1. **单点修改**: 颜色值只在一处定义（`theme_colors.py`），全局 QSS 引用这些颜色
2. **框架管理**: 通用控件样式由 `styles.py` 统一管理，模块无需重复定义
3. **主题自适应**: 通过 `QApplication.setStyleSheet()` 切换整套主题，模块无需感知主题变更细节

## 样式管理分层

### 第一层：全局 QSS（styles.py）

`toolkit/gui/styles.py` 定义了 `DARK_THEME` 和 `LIGHT_THEME` 两套完整的 QSS 字符串，通过 `get_theme_stylesheet(theme)` 函数获取。

**覆盖范围**：

| 类别 | 选择器 |
|------|--------|
| 通用控件 | `QWidget`, `QPushButton`, `QLineEdit`, `QTextEdit`, `QLabel`, `QGroupBox`, `QTabWidget`, `QTabBar`, `QTableWidget`, `QHeaderView`, `QScrollBar`, `QCheckBox`, `QSpinBox`, `QComboBox`, `QListWidget`, `QTreeWidget`, `QProgressBar`, `QSlider`, `QMenu`, `QFrame`, `QTextBrowser`, `QScrollArea` |
| 命名按钮 | `#primaryBtn`, `#secondaryBtn`, `#dangerBtn`, `#ghostBtn`, `#stopBtn` |
| 对话框 | `#llmSettingsDialog`, `#llmDialogTitleBar`, `#llmDialogTitle`, `#llmDialogCloseBtn`, `#llmDialogSeparator` |
| 导航栏 | `#navPanel`, `#navButton`, `#titleBar`, `#statusBar` |
| 面板布局 | `#bottomPanel`, `#bottomPanelHeader`, `#rightPanel`, `#rightPanelPlaceholder`, `#navToggleBtn`, `#bottomToggleBtn`, `#rightToggleBtn` |
| 日志面板 | `#logChannelBar`, `#logFilterBtn`, `#logClearBtn`, `#bottomPanelLog` |
| Agent 模块 | `#agentLeftPanel`, `#agentToolbar`, `#agentLblTitle`, `#agentInputBar`, `#agentBtnNewConv`, `#agentBtnSend`, `#agentConvList`, `#agentMsgScroll`, `#agentWelcomeTitle`, `#agentWelcomeSubtitle`, `#agentWelcomeHint`, `#agentShortcutBtn`, `#agentHistLabel`, `#agentChatInput` |
| 首页 | `#homeWelcome`, `#homeSubtitle`, `#homeModulesTitle`, `#noModulesHint`, `#moduleCard`, `#moduleNameLabel`, `#moduleVersionLabel`, `#moduleDescLabel` |
| 对话框标签 | `#dlgMsgLabel` |
| 通用字段 | `#fieldHint`, `#fieldLabel` |
| Jank 面板 | `#jankSectionLabel`, `#jankSmallBtn`, `#jankCaptureLabel` |
| Analysis Chat | `#analysisChatHeader`, `#analysisChatDisplay`, `#analysisChatInput` |
| History Panel | `#historyPanel` |
| Device Disguise | `#profileSelectBtn` |
| 配置对比 | `#gameperfDiffTree` |
| Perfetto Analysis | `#dimensionSelector`, `#analysisLog`, `#dangerIconBtn` |

### 第二层：颜色常量（theme_colors.py）

`toolkit/gui/theme_colors.py` 集中定义 Catppuccin 调色板：

```python
from toolkit.gui.theme_colors import THEMES, get_colors

colors = get_colors("dark")  # 或 "light"
accent = colors["accent"]    # #cba6f7 (dark) / #8839ef (light)
```

**主要颜色键**：`bg`, `bg_surface`, `card_bg`, `panel_bg`, `fg`, `fg_dim`, `border`, `hover`, `accent`, `success`, `error`, `warning`, `muted` 等。

### 第三层：模块内联样式

仅在以下场景保留 `setStyleSheet()` 调用：

1. **状态切换**: 拖放区域的 hover/active 状态、发送/取消按钮切换
2. **动态创建**: 聊天气泡、列表项等运行时生成的 widget
3. **per-instance 定制**: StatusCard 的 accent 色因实例而异
4. **复杂树样式**: SessionTreeWidget / AnalysisHistoryTree 的细粒度选择器

## 主题切换机制

```
用户点击主题切换按钮
    ↓
MainWindow._toggle_theme()
    ↓
_apply_theme(): QApplication.setStyleSheet(get_theme_stylesheet(theme))
    ↓  全局 QSS 立即生效于所有 objectName 匹配的控件
_propagate_theme(): 遍历 self._tabs → tab.set_theme(theme)
    ↓  BaseTab.set_theme() 默认只存储 self._theme
    ↓  子类可重写以更新动态内联样式
TitleBar.set_theme() / NavPanel.set_theme() / BottomPanel.set_theme() / RightPanel.set_theme()
```

**BaseTab.set_theme()**：所有 Tab 基类提供默认实现（仅存储 `_theme`），子类只在有动态样式需求时才重写。

## 共享组件

### ToolkitDialog

`toolkit/gui/toolkit_dialog.py` — 统一无边框对话框基类。

- 提供标题栏 + 关闭按钮 + 分隔线 + 可拖动
- 子类或函数在 `content_layout` 中添加内容
- 辅助函数: `confirm_dialog()`, `input_dialog()`, `warning_dialog()`, `info_dialog()`, `three_button_dialog()`

### DialogCloseButton

`toolkit/gui/toolkit_dialog.py` 中定义，使用 Codicons 字体绘制关闭图标。所有对话框统一使用此组件。

## 日志面板系统

日志输出已从各模块内嵌区域统一迁移到底部面板。详细架构设计见 [日志面板架构设计](log-panel-architecture.md)。

模块日志输出方式：

```python
self._log("操作成功", level="success")
self._log("发生错误", level="error")
self._log("普通信息")  # 默认 level="info"
```

> **已废弃**: `LogTextEdit`（`toolkit/gui/log_widget.py`）不再用于模块内嵌日志。
> 该组件仅保留供可能的历史兼容场景。新模块 MUST 使用 `BaseTab._log()` 输出日志。

## objectName 命名规范

| 前缀 | 作用域 | 示例 |
|------|--------|------|
| `agent*` | Agent 智能助手模块 | `agentLeftPanel`, `agentBtnSend` |
| `home*` | 首页模块 | `homeWelcome`, `homeSubtitle` |
| `jank*` | Jank 面板 | `jankSectionLabel`, `jankSmallBtn` |
| `analysisChat*` | 分析对话组件 | `analysisChatHeader`, `analysisChatDisplay` |
| `history*` | 历史面板 | `historyPanel` |
| `profile*` | 设备档案 | `profileSelectBtn` |
| `gameperf*` | 性能配置对比 | `gameperfDiffTree` |
| `field*` | 通用字段标签 | `fieldHint`, `fieldLabel` |
| `dlg*` | 对话框内容 | `dlgMsgLabel` |
| `log*` | 日志面板 | `logChannelBar`, `logFilterBtn`, `logClearBtn` |
| `bottom*` | 底部面板 | `bottomPanel`, `bottomPanelHeader`, `bottomPanelLog`, `bottomToggleBtn` |
| `right*` | 右侧面板 | `rightPanel`, `rightPanelPlaceholder`, `rightToggleBtn` |
| `*Btn` | 通用按钮角色 | `primaryBtn`, `secondaryBtn`, `dangerBtn`, `ghostBtn`, `stopBtn` |

## 文件清单

| 文件 | 职责 |
|------|------|
| `toolkit/gui/styles.py` | 全局 QSS 定义（暗色+亮色） |
| `toolkit/gui/theme_colors.py` | Catppuccin 调色板常量 |
| `toolkit/gui/base_tab.py` | Tab 基类（含 `set_theme()`） |
| `toolkit/gui/toolkit_dialog.py` | 统一对话框基类 + `DialogCloseButton` |
| `toolkit/gui/log_widget.py` | LogTextEdit（已废弃，仅保留兼容） |
| `toolkit/gui/log_manager.py` | LogManager 中央日志路由 |
| `toolkit/gui/panels/bottom_panel.py` | BottomPanel 底部日志面板 |
| `toolkit/gui/panels/right_panel.py` | RightPanel 右侧通用容器 |
| `toolkit/gui/main_window.py` | 主窗口（三面板布局 + 主题分发） |
| `toolkit/gui/codicons.py` | Codicons 字体加载 |
| `toolkit/gui/widgets/title_bar.py` | 标题栏（Logo + 布局切换按钮 + 控件按钮） |
| `toolkit/gui/widgets/nav_panel.py` | 导航面板 |
