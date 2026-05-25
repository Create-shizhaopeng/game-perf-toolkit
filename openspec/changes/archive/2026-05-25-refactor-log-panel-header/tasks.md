## 1. 字符串常量准备

- [x] 1.1 在 `toolkit/gui/strings.py` 中新增设置菜单新增项的字符串常量（日志子菜单标题、导出日志、历史日志、清空历史、清空确认对话框文案）

## 2. 设置菜单实现

- [x] 2.1 在 `SettingsButton` 中新增 `log_export_requested` / `log_open_dir_requested` / `log_clear_history_requested` 三个 pyqtSignal
- [x] 2.2 在 `_show_menu()` 中添加 separator 和「日志」QMenu 子菜单（含导出日志/历史日志/清空历史三个 QAction）

## 3. 底部面板 header 重构

- [x] 3.1 移除 header 中导出按钮（`_export_btn`）的创建和布局代码，删除 `_on_export` 私有方法
- [x] 3.2 在 `_tab_bar` 初始化时将「控制台」添加为 index=1 的 tab（在「全部」之后）
- [x] 3.3 移除 `_console_btn` QPushButton 控件创建、布局代码及 `_on_console_toggled` 方法
- [x] 3.4 删除 `_show_console` 状态变量，简化 `_passes_filter` 移除 `_show_console` 分支
- [x] 3.5 将 `_on_export` 逻辑改为可公开调用的方法（供外部信号调用）
- [x] 3.6 新增 `open_log_directory` 和 `clear_log_history` 公开方法供外部信号调用

## 4. MainWindow 信号桥接

- [x] 4.1 在 `MainWindow` 中连接 SettingsButton 的三个新信号到 BottomPanel 对应方法
- [x] 4.2 「清空历史」确认对话框放在 BottomPanel 方法内实现

## 5. QSS 样式验证

- [x] 5.1 确认 header 中所有控件均有 QSS 样式定义，无需新增（控制台合并到 QTabBar 后自动继承 11px 字体）

## 6. 测试

- [x] 6.1 启动 GUI 验证设置菜单「日志」子菜单正常显示和触发
- [x] 6.2 验证「控制台」tab 与「全部」tab 风格一致，切换过滤正确
- [x] 6.3 验证「导出日志」功能与原有导出行为一致
- [x] 6.4 验证「历史日志」正确打开日志目录
- [x] 6.5 验证「清空历史」确认后正确删除 .log 文件
- [x] 6.6 验证 header「清除」按钮仍正常工作
