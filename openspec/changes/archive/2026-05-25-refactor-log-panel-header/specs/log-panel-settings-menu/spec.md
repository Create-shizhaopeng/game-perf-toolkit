## ADDED Requirements

### Requirement: Settings menu has log management submenu

右上角 SettingsButton 的弹出菜单 SHALL 包含「日志」菜单项，hover 时展开二级菜单，包含「导出日志」「历史日志」「清空历史」三个操作。

#### Scenario: User opens settings menu and sees log submenu

- **WHEN** 用户点击右上角齿轮图标打开设置菜单
- **THEN** 菜单在 separator 之后显示「日志」项，带有子菜单箭头指示器

#### Scenario: User hovers over log menu item

- **WHEN** 用户将鼠标悬停在「日志」菜单项上
- **THEN** 展开二级菜单，显示「导出日志」「历史日志」「清空历史」三个选项

### Requirement: Export logs from settings menu

「导出日志」菜单项 SHALL 触发与当前底部面板导出相同的文件保存对话框，将当前过滤后的日志条目导出为 `.log` 文件。

#### Scenario: User exports logs with entries available

- **WHEN** 用户点击「导出日志」且面板中有日志条目
- **THEN** 弹出 QFileDialog 保存对话框，默认文件名为 `logs_export.log`，筛选器为「日志文件 (*.log);;所有文件 (*.*)」
- **AND** 保存后文件内容包含 timestamp / source / message / details

#### Scenario: User exports logs with no entries

- **WHEN** 用户点击「导出日志」但面板中无日志条目
- **THEN** 不弹出保存对话框，无操作

### Requirement: Open log directory from settings menu

「历史日志」菜单项 SHALL 使用系统默认文件管理器打开 `data/logs/` 目录。

#### Scenario: User opens log directory

- **WHEN** 用户点击「历史日志」
- **THEN** 系统文件管理器打开 `data/logs/` 目录

#### Scenario: Log directory does not exist

- **WHEN** 用户点击「历史日志」但 `data/logs/` 目录不存在
- **THEN** 静默失败，不弹出错误弹窗

### Requirement: Clear log history from settings menu

「清空历史」菜单项 SHALL 在确认后删除 `data/logs/` 目录下的所有 `.log` 文件。

#### Scenario: User clears log history with confirmation

- **WHEN** 用户点击「清空历史」
- **THEN** 弹出确认对话框询问是否删除日志文件
- **AND** 用户确认后删除 `data/logs/` 目录下所有 `.log` 文件

#### Scenario: User cancels clear log history

- **WHEN** 用户点击「清空历史」后弹出确认对话框
- **AND** 用户点击取消
- **THEN** 不删除任何文件

#### Scenario: No log files to delete

- **WHEN** 用户点击「清空历史」但 `data/logs/` 目录下无 `.log` 文件
- **THEN** 不弹出确认对话框，无操作

### Requirement: Console button replaced by tab

底部面板 header 中的「控制台」QPushButton SHALL 被替换为 QTabBar 中的一个 tab，位于「全部」tab 右侧。

#### Scenario: Console tab appears next to All tab

- **WHEN** 底部面板显示
- **THEN** QTabBar 中「全部」右侧紧挨着「控制台」tab
- **AND** 「控制台」tab 使用与「全部」相同的 QSS 样式（11px 字体、透明背景、选中时底部边框高亮）

#### Scenario: User clicks console tab

- **WHEN** 用户点击 QTabBar 中的「控制台」tab
- **THEN** 日志面板仅显示 source 为"控制台"的日志条目

#### Scenario: User clicks All tab after selecting console

- **WHEN** 当前选中「控制台」tab，用户点击「全部」tab
- **THEN** 日志面板恢复显示所有源的日志条目

### Requirement: Export button removed from bottom panel header

底部面板 header SHALL NOT 包含「导出」QPushButton。

#### Scenario: Bottom panel header without export button

- **WHEN** 底部面板显示
- **THEN** header 中不存在独立的「导出」按钮

### Requirement: Clear button remains in bottom panel header

底部面板 header 右侧的「清除」按钮 SHALL 保留，功能为清空当前内存缓存（LogManager.clear()）。

#### Scenario: User clears current log buffer

- **WHEN** 用户点击 header 右侧清除按钮
- **THEN** 当前 LogManager 中所有条目被清空
- **AND** 面板重新渲染为空状态
