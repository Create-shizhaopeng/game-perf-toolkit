## Context

当前底部日志面板 header 控件混杂：源过滤有两种不同风格的 UI（QTabBar 的「全部」+ 各模块 tab vs QPushButton 的「控制台」），导出按钮无 QSS 样式定义导致字体显示不全。设置面板目前仅有主题/LLM/Agent 三项，缺少日志管理入口。

目标是将日志管理操作（导出、历史查看、清空）收敛到设置面板，同时统一 header 中源过滤控件的风格。

约束：
- 遵循 [.claude/rules/log-panel-rules.md](.claude/rules/log-panel-rules.md) 日志开发规则
- 遵循 [.claude/rules/ui-style-guide.md](.claude/rules/ui-style-guide.md) UI 样式规范
- QSS 样式在 `styles.py` 中同时维护 dark/light 两套

## Goals / Non-Goals

**Goals:**
- 将「导出」从底部 header 移到设置 → 日志子菜单
- 设置菜单新增「日志」→「导出日志 / 历史日志 / 清空历史」二级菜单
- 「控制台」按钮改为 QTabBar tab，风格与「全部」一致，紧挨右侧
- 修复控制台、导出按钮的字体过大/显示不全问题

**Non-Goals:**
- 不改变底部面板的整体显示/隐藏逻辑
- 不改变日志内容区域（QTextEdit）的渲染方式
- 不改变 LogManager 的数据结构和信号
- 不新增外部依赖

## Decisions

### Decision 1: 设置菜单使用 QMenu 嵌套实现二级菜单

Qt 原生支持 `QMenu.addMenu()` 创建子菜单。直接在 `SettingsButton._show_menu()` 中添加一个 `QMenu("日志")`，向其添加三个 `QAction`。

**备选**: 将日志功能放在独立弹窗/面板中 → 过度设计，三个操作完全适合菜单。

### Decision 2: 「控制台」合并到 QTabBar 的 index=1 位置

`_tab_bar.addTab(_CONSOLE_TAB)` 在 "全部"(index=0) 之后插入。删除 `_console_btn` 控件和 `_show_console` 状态变量。

`_on_tab_changed` 调整逻辑：
- index 0 (全部): `_current_source = None`
- index 1 (控制台): `_current_source = "控制台"`（作为特殊源名）
- 其他: `_current_source = tab_text`

`_passes_filter` 简化：移除 `_show_console` 分支，仅依赖 `_current_source`。

### Decision 3: 设置菜单操作通过信号连接到底部面板

SettingsButton 新增信号：
- `log_export_requested` → MainWindow 连接 → BottomPanel._on_export()
- `log_open_dir_requested` → MainWindow 连接 → 打开目录
- `log_clear_history_requested` → MainWindow 连接 → 清空磁盘日志文件

MainWindow 持有 SettingsButton 和 BottomPanel 的引用，负责桥接。

**备选**: BottomPanel 直接持有 SettingsButton 引用 → 违反当前架构（SettingsButton 是 TitleBar 的一部分，BottomPanel 不应跨层依赖）。

### Decision 4: Header 右侧「清除」按钮保留

功能区分明确：
- header「清除」按钮 = `LogManager.clear()` 清空内存缓存 + 重新渲染
- 设置「清空历史」 = 删除 `data/logs/` 目录下 `.log` 文件（含确认弹窗）

## Risks / Trade-offs

- **[低风险] 控制台作为 Tab 后「控制台」源注册时需特殊处理**: 当前 `_on_source_registered` 已跳过 `_CONSOLE_SOURCE` 不加入 tab bar，现在需要在初始化时主动添加 tab。代码逻辑清晰，风险可控。
- **[低风险] 导出功能移到设置菜单后 header 变窄**: 移除的导出按钮宽度约 40-50px，影响极小。header 有足够弹性空间。
- **[无回归风险] 向后兼容**: 不影响任何模块 API，纯 UI 重构。
