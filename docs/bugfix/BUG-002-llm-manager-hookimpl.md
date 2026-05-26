<!--
  id: BUG-002
  title: LLM Manager 模块实现 — hookimpl 标记错误导致插件钩子不触发
  type: bugfix
  status: fixed
  created: 2026-05-26
  updated: 2026-05-26
  tags: [llm_manager, plugin, hookimpl, ServiceRegistry, COM, modal-dialog, crash]
-->

# BUG-002: LLM Manager 插件钩子不触发导致 Service 未注册

## 现象

1. 设置面板「管理 Provider」按钮点击无反应
2. 模型下拉列表始终为空
3. 日志输出 `LLMManagerService 未注册，无法打开 Provider 管理对话框`

## 根因

`modules/llm_manager/src/plugin.py` 中使用了错误的 hookimpl 来源：

```python
# 错误写法
from pluggy import HookimplMarker
hookimpl = HookimplMarker("toolkit")
```

项目 hookspec 定义的项目名是 `lv_toolkit` 而非 `toolkit`，因此 `HookimplMarker("toolkit")` 创建的标记器无法匹配项目 hookspec，导致所有 `@hookimpl` 装饰的钩子方法都不会被 pluggy 调用。

其他所有模块的正确写法：

```python
from toolkit.core.hookspecs import hookimpl
```

## 修复

1. 将 `hookimpl` 导入改为 `from toolkit.core.hookspecs import hookimpl`
2. 为 `LLMManager` 添加 `set_llm_service()` 直接引用（兜底 ServiceRegistry 不可用时）
3. 插件 `on_startup` 同时注册到 `context` 字典和 `ServiceRegistry`（双通道）

## 受影响文件

- `modules/llm_manager/src/plugin.py` — hookimpl 来源修正
- `toolkit/core/llm/manager.py` — 新增 `_llm_service` 直接引用

## 关联 Bug

### BUG-002a: ghostBtn QSS 导致按钮文字不可见

`#ghostBtn` QSS 定义在 `styles.py` 中仅有 `background: transparent; border: none; padding: 0; margin: 0;`，缺少 `color` 和 `font-size`，导致按钮文字在暗色背景 (#1e1e2e) 上完全不可见。

**修复**: 改为 `#manageProviderBtn`，明确定义 `color: #a6adc8; font-size: 12px` + hover 下划线样式。

### BUG-002b: 模型下拉列表不填充

`_load_config()` 依赖 `QComboBox.setCurrentIndex()` 触发 `currentIndexChanged` 信号 → `_on_provider_changed` → 填充模型列表。但信号在特定时序下可能不触发。

**修复**: 改为 `_load_config()` 中显式调用 `_refresh_models(idx)`，不再依赖信号链。

### BUG-002c: QComboBox / QLineEdit 高度不一致

QComboBox 默认 `padding: 6px 10px` 和 QLineEdit `padding: 4px 8px` 导致在同一行中高度不匹配。

**修复**: 统一 QSS 为 `padding: 2px 8px; min-height: 22px; max-height: 28px`。

### BUG-002d: Modal Dialog + DeviceMonitor COM 重入崩溃

**现象**:
```
QFont::setPointSize: Point size <= 0 (-1), must be greater than 0
Windows fatal exception: code 0x8001010d
```
崩溃堆栈指向 `_open_llm_settings` → `dialog.exec()`。

**根因**: `0x8001010d` = `RPC_E_CANTCALLOUT_ININPUTSYNCCALL` — Windows COM 线程重入错误。

```
QDialog.exec() 创建嵌套事件循环
  → DeviceMonitor (QTimer) 在嵌套循环中继续触发
    → ADB 操作涉及 Windows COM 对象
      → COM 检测到同步调用重入 → crash
```

崩溃只发生在 `dialog.exec()` 期间 DeviceMonitor 定时器恰好触发 ADB 操作时，属于偶发问题。

**修复**: 在 `_open_llm_settings` 和 `_open_agent_settings` 中暂停/恢复 DeviceMonitor：

```python
self._device_monitor.stop()
try:
    dialog = LLMSettingsDialog(llm_manager, parent=self)
    dialog.exec()
finally:
    self._device_monitor.start()
```

**受影响文件**: `toolkit/gui/main_window.py` — `_open_llm_settings`, `_open_agent_settings`

### BUG-002e: provider_dialog.py + strings_gui.py 死代码残留

ProviderManageDialog 废弃后，`provider_dialog.py` (255行) 和 `strings_gui.py` 中 20 个常量无人引用，属于死代码。违反"不留无用代码"原则。

**修复**: 删除 `provider_dialog.py`，精简 `strings_gui.py` 为 4 行（仅保留 plugin 元数据常量）。

## 经验教训

1. **永远从 `toolkit.core.hookspecs` 导入 `hookimpl`**，不要自行创建 `HookimplMarker`
2. **GUI 关键信号链不要做唯一依赖**，显式调用兜底
3. **新增 QSS objectName 时确保完整定义**（color/font-size/background 一个不能少）
4. **modal dialog + 后台定时器 + Windows COM = 崩溃三角** — 打开 modal dialog 前暂停后台服务
5. **废弃功能立即清理** — 对话框改为 `os.startfile()` 后应同步删除旧 GUI 代码和 strings 常量
