# 模块开发常见踩坑指南

## 目录

- [P01 — 插件 context 键名冲突（严重）](#p01--插件-context-键名冲突严重)
- [P02 — ADB 命令输出可能为 None](#p02--adb-命令输出可能为-none)
- [P03 — 插件类必须继承 BasePlugin](#p03--插件类必须继承-baseplugin)
- [P04 — pytest 跨模块测试文件名冲突](#p04--pytest-跨模块测试文件名冲突)
- [P05 — QThread 信号安全（GUI 线程通信）](#p05--qthread-信号安全gui-线程通信)
- [P06 — Windows 控制台中文编码](#p06--windows-控制台中文编码)
- [P07 — GUI 状态重置需保留用户上下文](#p07--gui-状态重置需保留用户上下文)
- [P08 — Typer CLI 帮助命令退出码](#p08--typer-cli-帮助命令退出码)
- [P09 — ADB remount 首次需重启](#p09--adb-remount-首次需重启)
- [P10 — PowerShell heredoc 语法不兼容](#p10--powershell-heredoc-语法不兼容)
- [P11 — PyQt6 无边框窗口事件处理](#p11--pyqt6-无边框窗口事件处理)
- [P12 — Pydantic vs dataclass 选型](#p12--pydantic-vs-dataclass-选型)
- [P13 — PyInstaller noconsole 模式 sys.stdout/stderr 为 None](#p13--pyinstaller-noconsole-模式-sysstdoutstderr-为-none)
- [P14 — PyInstaller 资源文件路径解析](#p14--pyinstaller-资源文件路径解析)

---

## P01 — 插件 context 键名冲突（严重）

### 现象

多个模块的 `plugin.py` 在 `on_startup` 中往共享的 `context` 字典写入相同的键名（如 `context["service"]`、`context["adb"]`），后注册的模块覆盖先注册模块的实例。

GUI Tab 页取到的 service 实际是另一个模块的 service，调用方法时因接口不匹配导致崩溃。Windows 上表现为 `Windows fatal exception: code 0x8001010d` (RPC_E_WRONG_THREAD) 或 `STATUS_STACK_BUFFER_OVERRUN`。

### 根因

pluggy 按模块顺序加载插件，每个模块的 `on_startup` 钩子向同一个 `context` 字典写入 `service`、`adb` 等通用键名。后加载的模块覆盖了先加载模块的实例。

### 修复方案

**所有模块的 context 键名 MUST 使用模块前缀命名空间。**

```python
# ✗ 错误
context["service"] = MyService(...)
context["adb"] = adb

# ✓ 正确
context["dd_service"] = DeviceDisguiseService(...)
context["dd_adb"] = adb
context["gp_service"] = GamePerfService(...)
context["gp_adb"] = adb
```

GUI Tab 取值也要使用对应的命名空间键：

```python
self._service = context.get("gp_service")
self._adb = context.get("gp_adb")
```

### 预防措施

- 新建模块时，脚手架模板应预填带模块前缀的 context 键名
- Code Review 时检查 context 键名是否带前缀

---

## P02 — ADB 命令输出可能为 None

### 现象

`AdbManager.push()` 中 `result.stdout + result.stderr` 报错 `TypeError: can only concatenate str (not "NoneType") to str`。

### 根因

`subprocess.run` 在特定情况下（如进程被杀、管道异常）可能返回 `stdout=None` 或 `stderr=None`，尽管指定了 `capture_output=True, text=True`。

### 修复方案

所有使用 `AdbCmdResult` 的地方，访问 `stdout` 和 `stderr` 时 MUST 加 `or ""` 保护：

```python
stdout = result.stdout or ""
stderr = result.stderr or ""
combined = (stdout + stderr).lower()
```

### 预防措施

- 在 `_run_cmd_raw` 返回时统一做 None 保护
- 或在 `AdbCmdResult` 的构造中强制转换

---

## P03 — 插件类必须继承 BasePlugin

### 现象

模块加载时报错 `plugin.py 中未找到 BasePlugin 子类`。

### 根因

`PluginManager` 通过检查 `issubclass(cls, BasePlugin)` 发现插件类。如果插件类没有显式继承 `BasePlugin`，则无法被发现。

### 修复方案

```python
from toolkit.core.hookspecs import BasePlugin

class GamePerfPlugin(BasePlugin):  # 必须继承 BasePlugin
    ...
```

### 预防措施

- 脚手架生成的 `plugin.py` 模板中预填 `BasePlugin` 继承
- 如果模块加载失败，首先检查插件类是否继承了 `BasePlugin`

---

## P04 — pytest 跨模块测试文件名冲突

### 现象

从项目根目录同时运行所有测试时，pytest 报 `ModuleNotFoundError` 或导入冲突，因为多个模块下都有 `test_service.py`、`conftest.py` 等同名文件。

### 根因

pytest 默认使用 `prepend` 导入模式，将测试文件所在目录插入 `sys.path`。同名文件在不同目录下会产生模块名冲突。

### 修复方案

使用 `scripts/run_all_tests.py` 统一测试入口，将主项目和各模块的测试在独立的 pytest 会话中运行：

```bash
python scripts/run_all_tests.py
```

该脚本会依次执行：
1. `pytest tests/` — 主项目测试
2. `pytest modules/device_disguise/tests/` — 设备伪装模块测试
3. `pytest modules/game_perf/tests/` — 游戏性能模块测试
4. `pytest modules/perfetto_capture/tests/` — Perfetto 抓取模块测试

### 预防措施

- 禁止在 `pyproject.toml` 中使用 `--import-mode=importlib`（会引入其他副作用）
- 新模块添加后，在 `run_all_tests.py` 中注册其测试目录

---

## P05 — QThread 信号安全（GUI 线程通信）

### 现象

从后台线程（QThread）直接操作 UI 控件导致崩溃（`RPC_E_WRONG_THREAD`、`STATUS_STACK_BUFFER_OVERRUN`），或 `QTimer.singleShot` 在非 GUI 线程调用时行为不确定。

### 根因

PyQt6 要求所有 UI 操作必须在主线程（GUI 线程）执行。后台线程通过 `QTimer.singleShot` 回调到主线程的方式不可靠。

### 修复方案

使用 `pyqtSignal` 作为线程间通信的唯一方式：

```python
class _BackgroundWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(object)
    progress = pyqtSignal(str)  # 进度回调信号

    def run(self):
        try:
            result = self._fn()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(e)
```

Service 层的 `on_progress` 回调通过 worker 的 signal 转发：

```python
def _on_progress_safe(self, msg: str):
    if self._worker:
        self._worker.progress.emit(msg)
```

在主线程连接 signal 到 UI 更新槽：

```python
self._worker.progress.connect(self._on_progress_ui)
```

### 预防措施

- 禁止在 QThread.run() 中直接调用 `self.parent().some_ui_method()`
- 禁止在 QThread.run() 中使用 `QTimer.singleShot`
- Service 层永远不导入 PyQt6

---

## P06 — Windows 控制台中文编码

### 现象

运行测试或脚本输出中文时报 `UnicodeEncodeError: 'gbk' codec can't encode character '✓'`。

### 根因

Windows 默认控制台编码为 GBK (cp936)，无法编码 Unicode 特殊字符（如 ✓、✗、→ 等）。

### 修复方案

在脚本入口处强制 UTF-8：

```python
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
```

### 预防措施

- 所有入口脚本（`app.py`、`run_all_tests.py`、自定义脚本）统一加编码设置
- Constitution 已规定所有输出 MUST 使用 UTF-8 编码

---

## P07 — GUI 状态重置需保留用户上下文

### 现象

点击「重置修改」按钮后，界面跳回默认的第一个游戏/模式，而非保持用户当前选中的游戏/模式。

### 根因

重置逻辑调用 `_load_file()` 重新解析 XML 并重填 ComboBox，导致 `currentIndex` 被重置为 0。

### 修复方案

在重新加载前保存当前选择状态，加载后恢复：

```python
def _on_clear(self):
    filepath = self._file_input.text().strip()
    if filepath and os.path.isfile(filepath):
        prev_game = self._game_cbx.currentText()
        prev_mode = self._mode_cbx.currentText()
        self._load_file(filepath)
        if prev_game:
            idx = self._game_cbx.findText(prev_game)
            if idx >= 0:
                self._game_cbx.setCurrentIndex(idx)
                self._on_game_changed()
                if prev_mode:
                    midx = self._mode_cbx.findText(prev_mode)
                    if midx >= 0:
                        self._mode_cbx.setCurrentIndex(midx)
                        self._on_mode_changed()
        self._notes_input.clear()
```

### 预防措施

- 任何涉及 ComboBox 重填的操作前，先保存当前选择
- 通用模式：save-context → reload → restore-context

---

## P08 — Typer CLI 帮助命令退出码

### 现象

测试中 `assert result.exit_code == 0` 失败，实际退出码为 2。

### 根因

Typer/Click 在显示帮助信息或无效命令时使用退出码 2（而非 0）。

### 修复方案

在测试中正确断言：

```python
# 无参数显示帮助
result = runner.invoke(app)
assert result.exit_code == 2  # Typer 帮助退出码

# 或检查输出内容
assert "Usage:" in result.output or result.exit_code == 0
```

### 预防措施

- 编写 CLI 测试时，优先断言输出内容而非退出码
- 了解 Typer 的退出码约定：0=成功、1=应用错误、2=用法错误/帮助

---

## P09 — ADB remount 首次需重启

### 现象

首次执行设备伪装或配置推送时，设备重启两次（用户反馈"多重启了一次"）。

### 根因

设备首次执行 `adb remount` 时需要启用 overlayfs，此操作要求重启设备。重启后第二次 remount 才能成功。之后 build.prop 修改又需要一次重启。后续操作 remount 直接成功，只需一次重启。

### 预期行为

| 场景 | 重启次数 | 说明 |
|------|----------|------|
| 首次操作 | 2 次 | remount 启用 overlayfs → 重启 + build.prop 修改 → 重启 |
| 后续操作 | 1 次 | remount 直接成功 + build.prop 修改 → 重启 |

### 预防措施

- 在 UI 日志中明确提示"首次 remount 需要重启设备"
- AdbManager.remount() 已内置智能处理，模块无需自行实现

---

## P10 — PowerShell heredoc 语法不兼容

### 现象

使用 Bash heredoc 语法 `git commit -m "$(cat <<'EOF' ... EOF)"` 在 PowerShell 中执行失败。

### 修复方案

在 PowerShell 环境下，将提交消息写入临时文件后使用 `git commit -F`：

```powershell
$msg | Out-File -Encoding utf8 commit_msg.tmp
git commit -F commit_msg.tmp
Remove-Item commit_msg.tmp
```

### 预防措施

- 所有自动化脚本需考虑跨平台兼容性
- Git 提交优先使用 `-F` 而非 `-m` 传递多行消息

---

## P11 — PyQt6 无边框窗口事件处理

### 现象

自定义无边框窗口（`setWindowFlags(Qt.WindowType.FramelessWindowHint)`）在 Windows 上存在多种问题：
- 窗口边缘拖拽缩放不生效
- 最大化后 4px margin 导致不贴合屏幕
- 鼠标拖动状态恢复异常
- leaveEvent 不触发导致鼠标光标不恢复

### 修复要点

1. 必须在 `mousePressEvent`、`mouseMoveEvent`、`mouseReleaseEvent` 中完整处理拖拽和缩放
2. 最大化状态下动态调整 `_root_layout` 的 margins（最大化=0，正常=resize_margin）
3. 添加 `leaveEvent` 重置鼠标光标
4. 宽度和高度独立 clamp（不互相阻塞）

### 预防措施

- 使用 `_resize_margin` 常量统一管理可拖拽区域
- 最大化/还原必须同步更新 `_is_maximized` 标记和布局 margins

---

## P12 — Pydantic vs dataclass 选型

### 现象

初始设计使用 Pydantic model，实际实现改为 Python dataclass，导致 spec 文档与代码不一致。

### 选型建议

| 场景 | 推荐 | 理由 |
|------|------|------|
| 公共 API 入参/返回值 | Pydantic | 自动验证、JSON Schema 生成 |
| 内部数据传递 | dataclass | 轻量、无额外依赖 |
| XML/DOM 解析中间结构 | dataclass | 频繁创建，性能更好 |
| Agent 工具声明 | Pydantic | ServiceRegistry 自动生成 JSON Schema |

### 预防措施

- spec 文档中明确标注使用 Pydantic 还是 dataclass
- 如果 spec 写了 Pydantic，实现改为 dataclass 后必须同步更新 spec

---

## P13 — PyInstaller noconsole 模式 sys.stdout/stderr 为 None

### 现象

GUI 可执行文件双击启动后立即崩溃：
- `RuntimeError: sys.stderr is None`（faulthandler.enable()）
- `AttributeError: 'NoneType' object has no attribute 'encoding'`（logger 中访问 sys.stdout.encoding）

### 根因

PyInstaller 使用 `--noconsole`（或 `--windowed`）构建时，Windows 不会分配控制台。此时 `sys.stdout`、`sys.stderr`、`sys.stdin` 均为 `None`，任何对它们的属性访问或方法调用都会报错。

### 修复方案

所有访问 `sys.stdout` / `sys.stderr` 的代码 MUST 加 None 检查：

```python
# faulthandler
if sys.stderr is not None:
    faulthandler.enable()

# logger UTF-8 编码
if sys.stdout is not None and hasattr(sys.stdout, "encoding"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(...)

# logging.StreamHandler
stream = sys.stdout or sys.stderr
if stream is not None:
    handlers.append(logging.StreamHandler(stream))
```

### 预防措施

- GUI 构建 MUST 使用 `--noconsole`，CLI 构建 MUST 使用 `--console`
- 任何新增的日志、输出、调试功能必须假设 stdout/stderr 可能为 None
- 推荐使用文件日志（`logging.FileHandler`）作为 GUI 模式的主要日志输出

---

## P14 — PyInstaller 资源文件路径解析

### 现象

打包后的可执行文件找不到 `modules/`、`assets/`、`data/` 等目录，插件加载失败或图标不显示。

### 根因

PyInstaller `--onedir` 模式下，`__file__` 指向 `_internal/` 临时目录，而非源码目录。`sys._MEIPASS` 指向 `_internal/` 根目录，包含通过 `--add-data` 打入的所有文件。

### 修复方案

使用条件路径解析：

```python
def _resolve_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent

ROOT_DIR = _resolve_root()
MODULES_DIR = ROOT_DIR / "modules"

# 运行时数据目录应在 exe 同级而非 _MEIPASS 内
DATA_DIR = (
    Path(sys.executable).parent / "data"
    if getattr(sys, "frozen", False)
    else ROOT_DIR / "data"
)
```

### 预防措施

- 静态资源（图标、模板等）通过 `--add-data` 打入，使用 `sys._MEIPASS` 路径访问
- 运行时数据（数据库、用户配置等）使用 `sys.executable` 同级目录
- 构建脚本中新增资源目录时，需同步在 `_collect_*()` 函数中注册
