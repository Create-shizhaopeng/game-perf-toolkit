## Why

`perfetto_capture` 模块中的历史面板实现存在严重的架构反模式：`HistoryPanel`（850行）作为 widget 工厂被创建后立即拆解，~500行的覆盖式面板代码从未使用。同时 `pe_analysis_tasks` 和 `pa_analysis_tasks` 两张表重复存储分析任务数据，`SessionTreeWidget` 和 `AnalysisHistoryTree` 之间存在大量重复的树组件代码。项目正在向纯 Skill/MCP 架构演进，perfetto_analysis 已是纯 Skill 模块，需要统一以 `pa_analysis_tasks` 为权威数据源。

## What Changes

- **新增** `BaseHistoryTreeWidget` 到 `toolkit/gui/widgets/` — 通用历史树基类，统一右键菜单、主题、send_to_agent 信号、搜索过滤
- **新增** `get_output_dir()` 到 `toolkit/core/app_paths.py` — 统一 dev/frozen 输出目录逻辑
- **拆分** `history_panel.py` 为 `session_tree.py` 和 `analysis_tree.py`，各自继承 `BaseHistoryTreeWidget`
- **删除** 覆盖式 `HistoryPanel`、`OverlayMask`、滑动动画等未使用代码（~500行）
- **废弃** `pe_analysis_tasks` 表及相关 CRUD 方法，统一以 `pa_analysis_tasks` 为权威数据源
- **新增** `PerfettoAnalysisService` 的 analysis record 写入方法
- **消除** gui_tab.py 中"创建 HistoryPanel → 访问私有属性拆出 widget → 重新挂载"的反模式
- **统一图标**：历史面板中所有 Unicode Emoji（📁📄📊📂📤🗑等）迁移到 `assets/codicon.ttf` 字体图标，补充缺失的 codicon 映射到 `toolkit/gui/codicons.py`

## Capabilities

### New Capabilities

- `base-history-tree`: 通用历史树基类组件，提供统一的右键菜单、主题支持、send_to_agent 信号、搜索过滤等能力，供各模块创建历史记录树时继承复用

### Modified Capabilities

<!-- 无现有 capability 的需求变更，纯代码重构，不影响外部行为 -->

## Impact

- **受影响的代码**：
  - `toolkit/gui/codicons.py` — 新增/补充 codicon 图标映射
  - `toolkit/gui/widgets/` — 新增 `base_history_tree.py`
  - `toolkit/core/app_paths.py` — 新增 `get_output_dir()`
  - `modules/perfetto_capture/src/history_panel.py` — 大幅删减（仅保留 payload 构建工具函数）
  - `modules/perfetto_capture/src/gui_tab.py` — 重写历史面板初始化逻辑
  - `modules/perfetto_capture/src/history_storage.py` — 删除 `pe_analysis_tasks` 相关代码
  - `modules/perfetto_analysis/src/service.py` — 新增 create/update analysis record 方法
- **数据库**：`pe_analysis_tasks` 表废弃（新数据写入 `pa_analysis_tasks`），`pe_history_sessions` 和 `pe_history_traces` 不变
- **无 API 破坏性变更**：左侧面板 UI 行为完全不变
