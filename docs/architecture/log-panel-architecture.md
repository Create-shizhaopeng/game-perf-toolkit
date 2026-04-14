# 日志面板架构设计

## 目录

- [概述](#概述)
- [架构总览](#架构总览)
  - [数据流](#数据流)
  - [组件关系图](#组件关系图)
- [核心组件](#核心组件)
  - [LogManager — 中央日志路由](#logmanager--中央日志路由)
  - [BottomPanel — 底部日志面板](#bottompanel--底部日志面板)
  - [RightPanel — 右侧通用面板](#rightpanel--右侧通用面板)
- [三面板布局](#三面板布局)
  - [Splitter 嵌套结构](#splitter-嵌套结构)
  - [面板可见性管理](#面板可见性管理)
  - [TitleBar 布局切换按钮](#titlebar-布局切换按钮)
- [模块集成接口](#模块集成接口)
  - [日志输出：BaseTab._log()](#日志输出basetab_log)
  - [右侧面板：BaseTab.right_panel_widget()](#右侧面板basetabright_panel_widget)
  - [Context 注入](#context-注入)
- [自动弹出机制](#自动弹出机制)
- [主题适配](#主题适配)
- [文件清单](#文件清单)

## 概述

本项目采用 VS Code 风格的三面板布局，将原先分散在各模块中的日志输出区域统一收归到底部面板，并提供可扩展的右侧面板供模块注册自定义内容（如历史记录）。

设计目标：
1. **日志集中化** — 所有模块日志通过 `LogManager` 统一路由，BottomPanel 聚合展示
2. **布局可控** — 三个面板（左侧导航 / 底部日志 / 右侧扩展）均可通过标题栏按钮独立切换
3. **模块无感** — 模块只需调用 `self._log()` 即可输出日志，无需关心 UI 细节
4. **可扩展** — 右侧面板为通用容器，各模块可注册专属内容

## 架构总览

### 数据流

```
模块 Tab (BaseTab 子类)
    │
    │  self._log("消息", level="info")
    ▼
BaseTab._log()
    │
    │  context["log_manager"].log(tab_title, msg, level=level)
    ▼
LogManager (QObject, 中央路由)
    │
    ├── log_added signal ──────► BottomPanel._on_log_added()
    │                               │
    │                               ▼
    │                           频道过滤 → 级别过滤 → QTextEdit 追加
    │
    ├── error_logged signal ───► MainWindow._on_error_logged()
    │                               │
    │                               ▼
    │                           自动弹出底部面板
    │
    └── source_registered signal ► BottomPanel._on_source_registered()
                                    │
                                    ▼
                                动态添加频道 Tab
```

### 组件关系图

```
MainWindow
├── TitleBar
│   ├── _nav_toggle      (左侧导航开关)
│   ├── _bottom_toggle   (底部面板开关)
│   └── _right_toggle    (右侧面板开关)
│
├── _splitter (QSplitter, Horizontal)
│   ├── NavPanel              ← toggle_nav_panel 控制
│   ├── _center_splitter (QSplitter, Vertical)
│   │   ├── ContentStack      (QStackedWidget, 模块页面)
│   │   └── BottomPanel       ← toggle_bottom_panel 控制
│   └── RightPanel            ← toggle_right_panel 控制
│
├── StatusBar
└── LogManager (QObject, 无 UI, 纯数据路由)
```

## 核心组件

### LogManager — 中央日志路由

**文件**: `toolkit/gui/log_manager.py`

职责：接收所有模块日志，维护环形缓冲区，并通过 Qt 信号广播给订阅者。

| 属性/方法 | 说明 |
|-----------|------|
| `_entries: deque[LogEntry]` | 环形缓冲区，最大 5000 条 |
| `_sources: list[str]` | 已注册日志源（按首次出现排序） |
| `log(source, msg, *, level)` | 记录一条日志并广播 |
| `clear(source=None)` | 清除指定源或全部日志 |
| `get_sources()` | 返回已注册日志源列表 |
| `get_entries(source, levels)` | 返回过滤后的日志条目（面板打开时回填） |

**信号**：

| 信号 | 参数 | 触发时机 |
|------|------|----------|
| `log_added` | `(ts, source, msg, level)` | 每条日志记录时 |
| `error_logged` | 无 | level 为 error/warning 时 |
| `source_registered` | `(source_name)` | 新日志源首次出现时 |

**LogEntry 数据结构**：

```python
@dataclass
class LogEntry:
    timestamp: str   # HH:MM:SS
    source: str      # 模块 tab_title
    message: str     # 日志内容
    level: str       # info / success / warning / error
```

### BottomPanel — 底部日志面板

**文件**: `toolkit/gui/panels/bottom_panel.py`

VS Code 风格的统一日志输出区域，聚合所有模块日志。

**布局结构**：

```
BottomPanel
├── Header (28px)
│   ├── QTabBar#logChannelBar   频道切换（全部 / 各模块源）
│   ├── stretch
│   ├── _FilterButton × 3      级别过滤（Error / Warning / Info）
│   └── QPushButton#logClearBtn 清除按钮（Codicon: clear-all）
└── QTextEdit#bottomPanelLog    日志内容（只读、等宽字体）
```

**过滤机制**：
- **频道过滤**：TabBar 切换时设置 `_current_source`，"全部" 显示所有源
- **级别过滤**：三个 toggle 按钮控制 `_active_levels()` 返回的级别集合
- `success` 级别始终显示（不受过滤按钮影响）

**日志着色**：通过 `QTextCharFormat` 设置前景色，颜色来自 `theme_colors.get_colors()`：

| 级别 | 颜色键 |
|------|--------|
| error | `c["error"]` |
| warning | `c["warning"]` |
| success | `c["success"]` |
| info | `c["fg"]`（默认前景色） |

### RightPanel — 右侧通用面板

**文件**: `toolkit/gui/panels/right_panel.py`

通用容器，各模块可注册自定义内容。通过 `QStackedWidget` 管理每个模块的面板页面。

| 方法 | 说明 |
|------|------|
| `register_widget(tab_index, widget)` | 为指定 Tab 注册右侧面板 widget |
| `switch_to_tab(tab_index)` | 切换到指定 Tab 对应的面板内容 |
| `has_content(tab_index)` | 查询指定 Tab 是否有注册内容 |
| `set_theme(theme)` | 遍历所有子 widget 调用 `set_theme()` |

未注册内容的 Tab 切换时显示占位文本。

## 三面板布局

### Splitter 嵌套结构

```
_splitter (Horizontal)
├── [0] NavPanel          width: 180 (saved)
├── [1] _center_splitter  stretch: 1
│       ├── [0] ContentStack   stretch: 1
│       └── [1] BottomPanel    stretch: 0, height: 200 (saved)
└── [2] RightPanel        width: 350 (saved)
```

初始状态：`_splitter.setSizes([180, 820, 0])`，BottomPanel 和 RightPanel 均 `hide()`。

### 面板可见性管理

每个面板有对应的 saved 尺寸（在隐藏前保存，显示时恢复）：

| 面板 | 保存变量 | 默认值 |
|------|----------|--------|
| NavPanel | `_nav_saved_width` | 180 |
| BottomPanel | `_bottom_saved_height` | 200 |
| RightPanel | `_right_saved_width` | 350 |

切换逻辑：
- **显示**：调用 `widget.show()` → 恢复 saved 尺寸到 splitter sizes
- **隐藏**：保存当前尺寸 → 调用 `widget.hide()`

### TitleBar 布局切换按钮

`_LayoutToggleButton` 继承自 `_CodiconButton`，管理 on/off 两种图标状态：

| 按钮 | ON 图标 | OFF 图标 | objectName | 默认状态 |
|------|---------|----------|------------|----------|
| 左侧导航 | `layout-sidebar-left` | `layout-sidebar-left-off` | `navToggleBtn` | active |
| 底部面板 | `layout-panel` | `layout-panel-off` | `bottomToggleBtn` | inactive |
| 右侧面板 | `layout-sidebar-right` | `layout-sidebar-right-off` | `rightToggleBtn` | inactive |

`set_panel_active(panel, active)` 方法允许外部同步按钮状态（如自动弹出时）。

## 模块集成接口

### 日志输出：BaseTab._log()

```python
def _log(self, msg: str, *, level: str = "info") -> None:
```

模块只需调用 `self._log("消息", level="error")` 即可。`level` 是关键字参数。

支持的 level 值：`info`、`success`、`warning`、`error`。

> **兼容性注意**：部分旧模块（如 perfetto_capture）的 `_log()` 接受 `level` 为位置参数，
> 通过在子类定义兼容 wrapper 解决：
> ```python
> def _log(self, msg: str, level: str = "info") -> None:
>     super()._log(msg, level=level)
> ```

### 右侧面板：BaseTab.right_panel_widget()

```python
def right_panel_widget(self) -> QWidget | None:
```

子类重写此方法，返回一个 `QWidget` 实例作为右侧面板内容。`MainWindow.add_tab()` 在注册 Tab 时自动调用此方法并注册到 `RightPanel`。

当前使用此接口的模块：
- `perfetto_capture` — 注册 HistoryPanel 到右侧面板

### Context 注入

`MainWindow` 在初始化时向 context 注入：

| 键 | 值 | 说明 |
|----|----|----|
| `log_manager` | `LogManager` 实例 | 供 `BaseTab._log()` 使用 |
| `show_right_panel` | `Callable` | 显示右侧面板（同步按钮状态） |
| `hide_right_panel` | `Callable` | 隐藏右侧面板（同步按钮状态） |

## 自动弹出机制

底部面板在以下条件下自动弹出：
1. `LogManager` 收到 `level` 为 `error` 或 `warning` 的日志
2. 触发 `error_logged` 信号
3. `MainWindow._on_error_logged()` 检查面板是否已可见
4. 若不可见，同步按钮状态并调用 `_on_toggle_bottom(True)`

该机制确保用户在操作正常时不会被日志面板干扰，只在出现异常时自动提示。

## 主题适配

面板样式通过全局 QSS（`styles.py`）管理，使用 objectName 选择器：

| 选择器 | 说明 |
|--------|------|
| `QWidget#bottomPanel` | 底部面板容器 |
| `QWidget#bottomPanelHeader` | 底部面板头部栏 |
| `QTabBar#logChannelBar` | 频道切换标签栏 |
| `QPushButton#logFilterBtn` | 级别过滤按钮 |
| `QPushButton#logClearBtn` | 清除按钮 |
| `QTextEdit#bottomPanelLog` | 日志内容区域 |
| `QWidget#rightPanel` | 右侧面板容器 |
| `QLabel#rightPanelPlaceholder` | 右侧面板占位文本 |
| `QPushButton#navToggleBtn` | 导航切换按钮 |
| `QPushButton#bottomToggleBtn` | 底部面板切换按钮 |
| `QPushButton#rightToggleBtn` | 右侧面板切换按钮 |

`BottomPanel.set_theme()` 在主题切换时刷新日志视图（重绘颜色）。

## 文件清单

| 文件 | 职责 |
|------|------|
| `toolkit/gui/log_manager.py` | LogManager 中央日志路由 + LogEntry 数据结构 |
| `toolkit/gui/panels/__init__.py` | panels 包初始化 |
| `toolkit/gui/panels/bottom_panel.py` | BottomPanel 底部日志面板 |
| `toolkit/gui/panels/right_panel.py` | RightPanel 右侧通用容器 |
| `toolkit/gui/widgets/title_bar.py` | _LayoutToggleButton + 三个布局切换按钮 |
| `toolkit/gui/main_window.py` | 三面板 Splitter 布局 + 面板切换逻辑 |
| `toolkit/gui/base_tab.py` | `_log()` + `right_panel_widget()` 模块接口 |
| `toolkit/gui/codicons.py` | 布局/日志相关 Codicon 图标注册 |
| `toolkit/gui/styles.py` | 面板 QSS 样式（暗色+亮色） |
| `toolkit/gui/theme_colors.py` | 日志着色使用的颜色常量 |
