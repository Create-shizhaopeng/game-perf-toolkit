# UI 样式开发规范

## 核心原则

1. **全局 QSS 优先**: 通用控件样式 MUST 在 `toolkit/gui/styles.py` 中定义，MUST NOT 在模块中重复
2. **objectName 绑定**: 需要自定义样式的控件 MUST 通过 `setObjectName()` + 全局 QSS 选择器实现
3. **禁止硬编码颜色**: 模块代码 MUST NOT 硬编码主题颜色值（如 `#1e1e2e`），MUST 从 `theme_colors.py` 导入
4. **内联样式最小化**: `setStyleSheet()` 仅允许在动态状态切换和运行时创建的 widget 中使用

## 快速参考

```python
# ✅ 正确：使用 objectName + 全局 QSS
btn = QPushButton("保存")
btn.setObjectName("primaryBtn")

# ✅ 正确：使用共享颜色常量
from toolkit.gui.theme_colors import get_colors
c = get_colors(self._theme)

# ✅ 正确：使用共享日志组件
from toolkit.gui.log_widget import LogTextEdit
self._log = LogTextEdit()

# ✅ 正确：继承 ToolkitDialog
from toolkit.gui.toolkit_dialog import ToolkitDialog
class MyDialog(ToolkitDialog):
    def __init__(self, parent):
        super().__init__("标题", parent)
        # 在 self.content_layout 中添加内容

# ❌ 错误：在模块中定义颜色字典
_THEME_COLORS = {"dark": {"bg": "#1e1e2e", ...}}

# ❌ 错误：静态样式用 setStyleSheet
label.setStyleSheet("font-size: 13px; font-weight: bold;")

# ❌ 错误：对话框不继承 ToolkitDialog
class MyDialog(QDialog):  # 应该用 ToolkitDialog
```

## 可用 objectName

| objectName | 用途 |
|-----------|------|
| `primaryBtn` | 主要操作按钮（保存、确认、发送） |
| `secondaryBtn` | 次要操作按钮（取消、还原） |
| `dangerBtn` | 危险操作按钮（删除） |
| `ghostBtn` | 透明背景按钮（图标按钮） |
| `stopBtn` | 停止/取消操作按钮 |
| `fieldHint` | 小字提示标签（10px 斜体） |
| `fieldLabel` | 字段标签（13px） |
| `dlgMsgLabel` | 对话框正文标签 |
| `jankSectionLabel` | 区块标题标签（11px 粗体） |
| `jankSmallBtn` | 小号按钮（11px） |
| `dangerIconBtn` | 危险色图标按钮 |

## 新增样式的流程

1. 检查 `styles.py` 中是否已有匹配的全局规则
2. 如果没有，在 `styles.py` 的 `DARK_THEME` 和 `LIGHT_THEME` 中同时添加新规则
3. 在 widget 上调用 `setObjectName("新名称")`
4. objectName 命名使用模块前缀（如 `agent*`、`jank*`、`home*`）

## QTreeWidget 样式

全局 QSS（`styles.py`）已定义 `QTreeWidget` / `QTreeView` 的完整样式，
包括选中高亮、hover、前景色、背景色。各模块的树组件 **MUST NOT** 用内联
`setStyleSheet()` 覆盖这些全局规则。

### 正确模式

```python
# ✅ 正确：只设置容器内透明背景，其余交给全局 QSS
class MyTree(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QTreeWidget { background: transparent; border: none; }")
```

### 错误模式

```python
# ❌ 错误：内联 QSS 覆盖全局样式，导致选中高亮与其他模块不一致
class MyTree(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QTreeWidget { background: #1e1e2e; color: #cdd6f4; }
            QTreeWidget::item { padding: 4px; color: #cdd6f4; }
            QTreeWidget::item:selected { background: #cba6f7; color: #cdd6f4; }
            QTreeWidget::item:hover { background: rgba(255,255,255,0.08); }
        """)
```

### 右键菜单样式

`BaseHistoryTreeWidget._make_context_menu()` 已封装主题一致的 QMenu 样式，
子类 **MUST** 使用此方法创建右键菜单，**MUST NOT** 自行构造 QMenu 并设置内联 QSS。

## 图标规范

### 图标字体

所有图标 **MUST** 使用 `assets/codicon.ttf`（VS Code Codicons）字体系统，
通过 `toolkit/gui/codicons.py` 管理。**MUST NOT** 使用 Unicode Emoji 作为图标。

```python
from toolkit.gui.codicons import codicon_font, icon_char, load_codicons

# ✅ 正确：使用 codicon
icon = icon_char("folder")  # 返回 codicon Unicode 字符

# ❌ 错误：使用 Unicode Emoji
label = QLabel("📁 文件夹")
```

### 不同控件的渲染方式

| 控件 | 方式 | 示例 |
|------|------|------|
| `QTreeWidgetItem` | `setIcon()` + QPixmap 渲染 | `BaseHistoryTreeWidget._set_item_icon(item, "folder")` |
| `QPushButton` / 自定义绘制 | `QPainter.drawText()` + codicon 字体 | `painter.drawText(rect, AlignVCenter, icon_char("folder"))` |
| `QAction`（菜单项） | 不设图标，纯文字 | 右键菜单统一用纯文字 |
| 内联文本 | **禁止** | MUST NOT 在 `setText()` 中嵌入 codicon 字符 |

### QPixmap 渲染参数

与 `NavPanel` 保持一致的渲染参数：

```python
font = codicon_font(14)          # 字体大小 14px
canvas = 20                       # 画布 20x20（留边距防裁剪）
painter.drawText(0, 0, canvas, canvas, AlignVCenter | AlignHCenter, icon_char(name))
```

### 新增图标

1. 从官方源获取码点：`https://cdn.jsdelivr.net/npm/@vscode/codicons/dist/codicon.css`
2. 在 `toolkit/gui/codicons.py` 的 `ICONS` 字典中添加 `"name": "\ucodepoint"`
3. **MUST NOT** 猜测码点值（不同码点对应不同图标，猜错会导致显示错误图标）

### 图标名称与用途

| 名称 | 用途 |
|------|------|
| `folder` | 目录/会话节点（默认） |
| `folder-opened` | 目录/会话节点（展开状态） |
| `file` | 文件/数据节点 |
| `graph` | 分析报告 |
| `check` | 完成/成功 |
| `error` | 失败/错误 |
| `watch` | 等待中/超时 |
| `beaker` | 分析进行中 |
| `arrow-swap` | 路由中 |
| `dashboard` | 审查中 |
| `circle-slash` | 已取消 |
| `search` | 搜索 |
| `refresh` | 刷新 |
| `trash` | 删除 |
| `close` | 关闭 |
| `home` | 首页 |
| `robot` | Agent/机器人 |
| `device-mobile` | 设备 |
| `gear` | 设置 |

## 主题切换

- `BaseTab` 提供默认 `set_theme(theme)` 方法，子类仅在有动态内联样式时才重写
- 全局 QSS 已覆盖的控件无需在 `set_theme()` 中重复设置
- `MainWindow._propagate_theme()` 自动调用所有 Tab 的 `set_theme()`

## 架构文档

详细架构设计见 `docs/architecture/ui-style-architecture.md`
