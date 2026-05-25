## 1. Framework: BaseHistoryTreeWidget

- [x] 1.1 创建 `toolkit/gui/widgets/base_history_tree.py`，实现 `BaseHistoryTreeWidget(QTreeWidget)`
  - `_setup_context_menu(actions: list[dict])` — 通用右键菜单框架，支持条件显示
  - `send_to_agent_requested = pyqtSignal(dict)` — 标准化信号
  - `filter_by_keyword(keyword: str, column: int = 0)` — 搜索过滤
  - `_get_selected_items_data() -> list[dict]` — 多选数据获取
  - `_build_send_payload(path, context_type) -> dict` — 构建标准 payload
  - `_open_directory(path)` — 统一打开目录（Windows explorer / macOS Finder / Linux xdg-open）
  - `_format_size(bytes) -> str` 和 `_format_time(dt) -> str` — 格式化工具
  - `set_theme(theme)` — 使用 `theme_colors.get_colors()` 设置树样式
  - 默认启用 `ExtendedSelection`、`setHeaderHidden(True)`、`setAnimated(True)`
  - 图标统一使用 `icon_char()` + codicon 字体，禁止 Unicode Emoji

- [x] 1.2 在 `toolkit/core/app_paths.py` 新增 `get_output_dir(module: str = "") -> Path`

- [x] 1.3 在 `toolkit/gui/codicons.py` 的 `ICONS` 字典中补充历史面板所需的 codicon 映射：`file`、`folder-opened`、`export`、`trash`、`refresh`、`check`、`error`、`watch`、`circle-slash`、`cloud-download`、`save`、`database`（从 codicon.ttf 字体文件中提取准确的 Unicode 码点）

## 2. perfetto_analysis: Service 扩展

- [x] 2.1 在 `PerfettoAnalysisService` 中新增 `create_analysis_record(task_id, trace_path, process_name, status, result_dir)` 方法，写入 `pa_analysis_tasks`
- [x] 2.2 在 `PerfettoAnalysisService` 中新增 `update_analysis_record(task_id, status, result_dir, error_message)` 方法，更新 `pa_analysis_tasks`
- [x] 2.3 更新 `get_analysis_history()` 返回格式：`created_at` INTEGER → ISO 字符串，统一字段名 `task_id` → `id`、`report_dir_path` → `result_dir`，状态值统一为大写

## 3. perfetto_capture: 拆分历史面板文件

- [x] 3.1 新建 `modules/perfetto_capture/src/session_tree.py`，将 `SessionTreeWidget` 从 `history_panel.py` 移出，继承 `BaseHistoryTreeWidget`
  - 保留：三级树结构（session → trace → report）、`_create_session_item`、`_create_trace_item`、`_attach_report_children`
  - `_attach_report_children()` 中的报告路径扫描改用 `get_output_dir()`
  - 所有 Unicode Emoji 替换为 `icon_char()` 调用：📁→`icon_char("folder")`、📄→`icon_char("file")`、📊→`icon_char("graph")`
  - 右键菜单文本中的 Emoji 替换为对应 codicon：📂→`icon_char("folder-opened")`、📤→`icon_char("export")`、🗑→`icon_char("trash")`

- [x] 3.2 新建 `modules/perfetto_capture/src/analysis_tree.py`，将 `AnalysisHistoryTree` 从 `history_panel.py` 移出，继承 `BaseHistoryTreeWidget`
  - 保留：状态图标映射、双击打开报告、分析任务特有菜单项
  - 状态图标改用 codicon：✅→`icon_char("check")`、❌→`icon_char("error")`、⏳→`icon_char("watch")`、🔬→`icon_char("beaker")`、⏰→`icon_char("watch")`、🚫→`icon_char("circle-slash")` 等

- [x] 3.3 删除 `history_panel.py` 中的 `HistoryPanel`、`OverlayMask` 类及 `_setup_animation`、`show_animated`、`hide_animated`、`mousePressEvent`、`mouseMoveEvent`、`mouseReleaseEvent`、`paintEvent` 等覆盖式面板代码
- [x] 3.4 删除 `history_panel.py` 中的 `build_trace_send_payload()` 和 `build_analysis_send_payload()` 工具函数（功能已由 `BaseHistoryTreeWidget._build_send_payload()` 提供）
- [x] 3.5 将 `HistoryPanel` 中所有硬编码的 Unicode Emoji 标签文本（如 `📂 历史记录 & 分析`、`💾`、`🔄`、`✕`、`🔍`、`🗑`、`📥`、`📤`、`💬`）替换为 codicon 等价物

## 4. perfetto_capture: gui_tab.py 集成清理

- [x] 4.1 重写 `_ensure_history_panel()`：直接实例化 `SessionTreeWidget` 和 `AnalysisHistoryTree`，删除通过 `HistoryPanel` 中转的反模式
- [x] 4.2 更新 `_refresh_history()`：分析历史数据源切换为 `self.context["pa_service"].get_analysis_history()`
- [x] 4.3 更新 `_save_analysis_record()`：切换写入目标为 `pa_service.create_analysis_record()` / `update_analysis_record()`
- [x] 4.4 删除 `self._history_panel` 字段和相关 import

## 5. perfetto_capture: HistoryStorage 清理

- [x] 5.1 从 `_ensure_tables()` 中删除 `pe_analysis_tasks` 的 CREATE TABLE 和索引
- [x] 5.2 删除以下方法：`create_analysis_task`、`update_task_status`、`get_tasks_for_trace`、`get_all_analysis_tasks`、`delete_analysis_task`、`update_trace_analysis_status`

## 6. 测试更新

- [x] 6.1 新建 `toolkit/gui/widgets/tests/test_base_history_tree.py`，覆盖：右键菜单、过滤器、格式化工具、send_payload 构建
- [x] 6.2 更新 `modules/perfetto_capture/tests/test_history_storage.py`，删除 `pe_analysis_tasks` 相关测试用例
- [x] 6.3 更新 `modules/perfetto_capture/tests/test_history_panel_send_to_agent.py`，适配新的 import 路径
- [x] 6.4 运行 `python scripts/run_all_tests.py` 确认全部通过

## 7. 清理与验证

- [x] 7.1 运行 `python -m toolkit.app` 验证 GUI：左侧面板"抓取历史"和"分析历史"两个 Tab 正常显示，右键菜单功能完整
- [x] 7.2 运行 `python scripts/check_hardcoded_strings.py` 确认无新增硬编码中文
- [x] 7.3 更新 `docs/PROGRESS.md` 记录本次重构
