# 历史面板开发规范

## 架构约束

### 组件层次

```
LeftPanel
  └── HistoryArea (QTabBar + QStackedWidget)
        ├── 模块 A 的历史 Tab (widget A)
        └── 模块 B 的历史 Tab (widget B)
```

- 各模块通过 `BaseTab.history_widgets() -> list[tuple[str, QWidget]]` 注册历史 Tab
- `MainWindow.add_tab()` 自动调用 `history_widgets()` 并注册到 `HistoryArea`
- 模块 **MUST NOT** 直接操作 `HistoryArea` 或 `LeftPanel`

### 历史树组件

所有历史列表组件 **MUST** 继承 `BaseHistoryTreeWidget`（位于 `toolkit/gui/widgets/base_history_tree.py`）。

基类提供：
- 统一右键菜单框架：`_make_context_menu()` / `_add_menu_action()` / `_build_context_menu()`
- `send_to_agent_requested` 信号：标准化 payload `{file_path, file_name, context_type, missing}`
- 搜索过滤：`filter_by_keyword(keyword, column)`
- 多选数据获取：`_get_selected_items_data()` / `_get_first_selected_data()`
- 格式化工具：`_format_size(bytes)` / `_format_time(dt)`
- Codicon 图标：`_get_codicon(name)` → QIcon / `_set_item_icon(item, name)`
- 目录/文件操作：`_open_directory(path)` / `_open_file(path)`
- 主题切换：`set_theme(theme)` → 使用 `theme_colors.get_colors()`

**禁止行为**：
- **MUST NOT** 在树组件中硬编码颜色值（使用 `get_colors()` / `_apply_theme()`）
- **MUST NOT** 使用 Unicode Emoji 作为图标（使用 codicon 体系）
- **MUST NOT** 在树组件中创建自定义 `FileHandler` 或直接操作 `LogManager`
- **MUST NOT** 用内联 `setStyleSheet()` 覆盖全局 QSS 的 QTreeWidget 样式（如 `::item:selected` / `::item:hover`），这会导致选中高亮与其他模块不一致。仅允许设置 `background: transparent; border: none`

### 树结构约定

- 父节点（目录/会话）：`folder` 图标，展开时切换 `folder-opened`
- 文件/数据节点：`file` 图标
- 报告节点：`graph` 图标
- 状态图标：`check` / `error` / `watch` / `beaker` / `circle-slash` 等

---

## 输出目录

### 统一路径

所有模块的输出目录 **MUST** 通过 `toolkit.core.app_paths.get_output_dir(module)` 获取：

| 场景 | dev | frozen |
|------|-----|--------|
| 通用 | `<root>/data/output/<module>/` | `<exe>/output/<module>/` |
| trace 抓取 | `get_output_dir()` → HistoryService 追加 `/trace` | 同左 |
| 分析报告 | `get_output_dir("trace_report")` | 同左 |

**禁止行为**：
- **MUST NOT** 在模块代码中写死路径（如 `"data/output/trace"`、`"modules/perfetto_capture/data/output"`）
- **MUST NOT** 在模块代码中写 `is_frozen()` 分支来拼路径
- 回退路径仅允许在 `except Exception` 块中作为兜底

---

## 数据源

### 抓取历史

数据源：`HistoryService.scan_sessions()` — 扫描 `output_dir/trace/` 目录 + SQLite 索引同步

### 分析历史

数据源：**直接扫描 `trace_report/` 文件系统**，不依赖 DB。

扫描规则：
- 每个子目录为一个分析产出节点
- 报告文件识别：`jank_report.md`、`report.html`、`conclusion.html`、`*report*.html`
- 空目录（无报告文件）仍然展示为"0 个报告"的目录节点
- 报告文件类型扩展时只需修改 `_REPORT_NAMES` / `_REPORT_SUFFIXES`

---

## 图标规范

图标使用规则详见 [ui-style-guide.md](ui-style-guide.md)「图标规范」章节。
历史树组件通过 `BaseHistoryTreeWidget._set_item_icon(item, name)` 统一渲染，
参数与 `NavPanel` 对齐（14px 字体 / 20px 画布）。

树结构中的图标约定：
- 父节点（目录/会话）：`folder` 图标，展开时切换 `folder-opened`
- 文件/数据节点：`file` 图标
- 报告节点：`graph` 图标
- 状态图标：`check` / `error` / `watch` / `beaker` / `circle-slash` 等

---

## 字符串提取

历史面板中所有用户可见的中文文本 **MUST** 提取到模块的 `strings_gui.py`，使用 `Final` 常量。

命名前缀：
| 前缀 | 用途 |
|------|------|
| `HIST_MENU_` | 右键菜单项 |
| `HIST_REPORT_` | 报告节点标签 |
| `HIST_DLG_` | 删除确认对话框 |
| `HIST_COUNT_` | 数量后缀 |
| `HIST_*_FMT` | 含占位符的格式化模板 |

**禁止行为**：
- **MUST NOT** 在树组件代码中硬编码中文字符串（日志除外）
- **MUST NOT** 在 `strings_*.py` 中使用 f-string（使用 `.format()` 模板）

---

## 信号约定

### 模块间通信

历史面板向 Agent Chat 发送文件上下文使用 EventBus 事件：

```python
bus.emit("history.send_to_agent",
    file_path="/path/to/file",
    file_name="file.perfetto-trace",
    context_type="trace",    # "trace" | "analysis"
    missing=False,
)
```

`BaseHistoryTreeWidget._build_send_payload(path, context_type)` 已封装此逻辑，
子类可直接使用。

### 右键菜单信号

- `open_report_requested(str)` — 打开报告文件
- `send_to_agent_requested(dict)` — 发送到 Agent
- 删除操作直接在树组件内处理（操作文件系统 + 调用 `self.refresh()`），不 emit 信号

---

## 导入规范

项目启用 Ruff `I` 规则（isort），导入顺序 **MUST** 符合 PEP 8：

1. Standard library (`from __future__`, `import os`, `from pathlib import Path`)
2. Third-party (`from PyQt6.QtCore import ...`)
3. Project absolute (`from toolkit.gui.widgets.base_history_tree import ...`)
4. Relative (`from . import strings_gui as s`, `from .models import ...`)
