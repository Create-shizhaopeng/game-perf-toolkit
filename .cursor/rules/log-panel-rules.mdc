# 日志面板开发规则

模块日志输出和面板扩展的硬约束。架构详见 `docs/architecture/log-panel-architecture.md`。

## 日志输出

- MUST 使用 `self._log(msg, level=level)` 输出日志，MUST NOT 直接操作 `LogManager`
- `level` 是 **keyword-only** 参数，值限 `info` / `success` / `warning` / `error`
- 旧模块若 `_log()` 接受位置参数 `level`，MUST 在子类定义兼容 wrapper：
  ```python
  def _log(self, msg: str, level: str = "info") -> None:
      super()._log(msg, level=level)
  ```
- MUST NOT 在模块 Tab 中创建 `LogTextEdit` 或内嵌日志区域
- MUST NOT 在模块中 import `LogTextEdit`（已废弃）

## 右侧面板

- 模块需要右侧面板时 MUST 重写 `right_panel_widget() -> QWidget`
- 返回的 widget SHOULD 实现 `set_theme(theme: str)` 方法以支持主题切换
- 面板显示/隐藏 MUST 通过 `context["show_right_panel"]()` / `context["hide_right_panel"]()` 控制
- MUST NOT 直接操作 `RightPanel` 实例

## 面板样式

- 面板 UI 样式 MUST 通过 `styles.py` 全局 QSS 管理，使用 objectName 选择器
- 日志着色 MUST 使用 `theme_colors.get_colors()` 获取颜色，MUST NOT 硬编码颜色值
- 新增面板 objectName MUST 遵循命名规范（`bottom*` / `right*` / `log*` 前缀）

## 自动弹出

- 底部面板仅在 `error` / `warning` 级别日志时自动弹出
- MUST NOT 在 `info` / `success` 级别触发自动弹出
- 自动弹出 MUST 同步标题栏按钮状态（`set_panel_active`）
