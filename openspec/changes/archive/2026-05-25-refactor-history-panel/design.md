## Context

历史面板当前实现位于 `modules/perfetto_capture/src/history_panel.py`（~850行），包含 `HistoryPanel`、`SessionTreeWidget`、`AnalysisHistoryTree`、`OverlayMask` 四个类。问题：

1. `HistoryPanel` 作为覆盖式滑动面板创建完整 UI（动画、遮罩、左右双栏），然后 `gui_tab.py` 通过 `self._history_panel._session_tree` 访问私有属性拆出两个 TreeWidget，丢弃其余 ~500 行
2. `SessionTreeWidget` 和 `AnalysisHistoryTree` 重复实现了右键菜单、样式、send_to_agent 信号、格式化工具
3. 两张分析任务表 (`pe_analysis_tasks` vs `pa_analysis_tasks`) 同时存在，数据冗余
4. 项目架构向纯 Skill/MCP 方向演进，perfetto_analysis 已是纯 Skill 模块（`register_gui_tab` → `None`），其 `pa_analysis_tasks` 是更规范的分析任务数据源

## Goals / Non-Goals

**Goals:**
- 提取 `BaseHistoryTreeWidget` 到框架层，消除 TreeWidget 重复代码
- 拆分 `history_panel.py` 为 `session_tree.py` 和 `analysis_tree.py`
- 删除未使用的覆盖式 `HistoryPanel` 及动画代码
- 统一分析任务数据源为 `pa_analysis_tasks`，废弃 `pe_analysis_tasks`
- 消除 gui_tab.py 中"创建后拆出"反模式
- 统一输出目录逻辑到 `app_paths.get_output_dir()`
- 将所有 Unicode Emoji 图标迁移到 `assets/codicon.ttf` 字体图标

**Non-Goals:**
- 不改变 `HistoryArea` 容器或 `BaseTab.history_widgets()` 注册机制（已足够好）
- 不创建新的独立模块（只有一个消费者，不够抽象门槛）
- 不改变左侧面板 UI 外观和行为
- 不迁移已有数据库中的 `pe_analysis_tasks` 历史数据（按项目惯例，新数据写入新表即可）

## Decisions

### D1: BaseHistoryTreeWidget 放在 `toolkit/gui/widgets/`

**选择**：框架层 `toolkit/gui/widgets/base_history_tree.py`

**备选方案**：
- 放在 `toolkit/gui/panels/` — 但它是通用 widget 不是 panel
- 放在 perfetto_capture 模块内 — 无法被其他模块复用

**理由**：与项目中已有的 `toolkit/gui/widgets/nav_panel.py` 保持一致的模式。当其他模块需要历史列表时可直接继承。

### D2: 不使用独立 history 模块

**选择**：保持当前 `HistoryArea` + `BaseTab.history_widgets()` 的注册机制

**理由**：
- 目前仅 `perfetto_capture` 一个消费者，创建独立模块是过度抽象
- 框架层已有 `HistoryArea` 容器和注册机制，满足当前需求
- 不同模块的"历史"概念差异很大（trace 文件 vs 对话记录 vs 导入数据），强行统一数据模型会扭曲各模块的自然表达

### D3: pa_analysis_tasks 作为权威分析任务表

**选择**：所有分析任务读写统一使用 `pa_analysis_tasks`，删除 `pe_analysis_tasks`

**理由**：
- `pa_analysis_tasks` 有正式的迁移脚本管理（001/002/003），`pe_analysis_tasks` 是手动建表
- `pa_analysis_tasks` 在共享 DB 中，支持跨模块发现
- perfetto_analysis 作为纯 Skill 模块，天然是分析任务数据的管理者
- 字段兼容性：pa 表缺少的 `user_intent`/`scene`/`token_used` 在 GUI 树中未显示，可安全丢弃

**时间格式适配**：`pa_analysis_tasks.created_at` 使用 INTEGER (epoch)，`get_analysis_history()` 方法负责转换为 ISO 字符串供 GUI 消费。

### D4: 删除覆盖式 HistoryPanel

**选择**：删除 `HistoryPanel`、`OverlayMask` 及所有动画代码

**理由**：
- GUI tab 初始化时创建了 `HistoryPanel` 但只从中提取两个内部 TreeWidget，面板本身的 UI 从未被显示
- 左侧面板的 `HistoryArea` 才是实际的历史展示位置
- 如果未来需要覆盖式面板，可以从 git 历史恢复，或基于 `BaseHistoryTreeWidget` 重新构建

### D5: 使用 codicon.ttf 字体图标替代 Unicode Emoji

**选择**：历史面板中所有图标统一使用 `toolkit/gui/codicons.py` 提供的 codicon 字体系统

**理由**：
- Unicode Emoji 在不同 OS 上渲染效果不一致（Windows/Mac/Linux 各有各的 emoji 字体）
- `assets/codicon.ttf` 已集成在项目中，`NavPanel` 已在用，应统一风格
- codicon 作为矢量字体，缩放不失真，颜色可通过 QPainter/QSS 控制
- `toolkit/gui/codicons.py` 已有 `ICONS` 映射字典和 `codicon_font()` 工具函数

**实现方式**：
- 对 `QTreeWidgetItem` 文本：在 setText 中使用 `icon_char("folder")` 替代 "📁"
- 对 `QAction` 文本：同样使用 `icon_char("export")` 替代 "📤"
- 对 `QPushButton`：设置 codicon 字体 + `icon_char()` 或使用 `QPainter` 绘制
- 补充缺失的 codicon 映射到 `ICONS` 字典（如 `trash`、`refresh`、`check`、`error`、`watch` 等）

**备选方案**：
- 继续用 Unicode Emoji — 跨平台渲染不一致，不采纳
- 用 Qt 内置 QIcon + PNG/SVG — 增加资源文件管理负担，不采纳

## Risks / Trade-offs

- **[风险] `pa_analysis_tasks` 的字段名和值与旧表不同** → 在 `PerfettoAnalysisService` 中做字段映射和格式转换，对外暴露统一接口
- **[风险] `update_trace_analysis_status()` 被删除后 trace 分析状态标记丢失** → 改为在 `_refresh_history()` 中通过 `pa_analysis_tasks` 联查获取最新分析状态
- **[取舍] 不迁移旧 `pe_analysis_tasks` 数据** → 新数据写入 `pa_analysis_tasks`，旧数据库文件保留在磁盘但不被读取。用户可手动删除 `data/db/perfetto_capture_history.db` 来清理旧数据
- **[取舍] BaseHistoryTreeWidget 只支持 QTreeWidget 模式** → 如果未来需要 QListView 或自定义渲染，可以在基类上扩展

## Open Questions

<!-- 无待解决问题，已在探索阶段充分讨论 -->
