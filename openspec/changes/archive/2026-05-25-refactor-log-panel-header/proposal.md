## Why

日志面板 header 中「导出」「控制台」按钮缺少 QSS 样式定义，继承默认 QPushButton 字体导致文字显示不全；「控制台」作为源过滤功能与「全部」Tab 功能相同但风格割裂；导出功能混在 header 中占用空间。将导出/历史日志/清空历史收敛到右上角设置面板，并统一源过滤控件为 QTabBar 风格。

## What Changes

- 底部面板 header 移除「导出」按钮，改为设置菜单中的二级菜单项「日志 → 导出日志」
- 右上角设置菜单新增「日志」项，hover 展开二级菜单：导出日志、历史日志、清空历史
- 「控制台」从独立 QPushButton checkable 改为 QTabBar 的 tab，紧挨「全部」右侧，风格与「全部」一致
- 删除 `_console_btn` 控件、`_show_console` 状态变量、`_on_console_toggled` 回调，源过滤逻辑全部走 QTabBar tab 切换
- 底部面板 header 右侧「清除」按钮保留，功能不变（清空内存缓存），与设置「清空历史」（删除磁盘文件）形成功能区分
- 为新增/剩余的 header 控件补全 QSS 样式（如有遗漏）

## Capabilities

### New Capabilities

- `log-panel-settings-menu`: 设置面板新增「日志」子菜单，包含导出日志、历史日志、清空历史三个操作入口

### Modified Capabilities

<!-- No existing capabilities have spec-level requirement changes -->

## Impact

- `toolkit/gui/panels/bottom_panel.py` — 移除导出按钮、控制台按钮，控制台逻辑迁移到 QTabBar
- `toolkit/gui/widgets/title_bar.py` — SettingsButton 新增「日志」子菜单
- `toolkit/gui/styles.py` — 可能需补全/调整 QSS 样式
- `toolkit/gui/strings.py` — 新增菜单项字符串常量
