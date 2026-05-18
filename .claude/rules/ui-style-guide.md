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

## 主题切换

- `BaseTab` 提供默认 `set_theme(theme)` 方法，子类仅在有动态内联样式时才重写
- 全局 QSS 已覆盖的控件无需在 `set_theme()` 中重复设置
- `MainWindow._propagate_theme()` 自动调用所有 Tab 的 `set_theme()`

## 架构文档

详细架构设计见 `docs/architecture/ui-style-architecture.md`
