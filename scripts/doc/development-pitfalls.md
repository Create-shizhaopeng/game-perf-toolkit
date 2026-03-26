# 模块开发常见踩坑指南

## 代码规则（与本文档的关系）

本文件描述 **具体反例与修法**；**总纲级约定**（分层、Ruff、context 前缀、框架边界、合并前测试等）以架构文档 **[§5.0 代码规则（总纲）](../../doc/architecture/architecture-overview.md#50-代码规则总纲)** 与 **`.specify/memory/constitution.md`** 为准。踩坑条目中的 **MUST** 与总纲一并遵守。

## 目录

- [代码规则（与本文档的关系）](#代码规则与本文档的关系)
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
- [P15 — Perfetto detach 须配合 write_into_file](#p15--perfetto-detach-须配合-write_into_file)
- [P16 — Perfetto 同 UID 并发会话上限与残留进程](#p16--perfetto-同-uid-并发会话上限与残留进程)
- [P17 — Ring buffer clone 覆盖的时间范围](#p17--ring-buffer-clone-覆盖的时间范围)
- [P18 — PyQt6 设备监控与间歇性 COM 错误 (0x8001010d)](#p18--pyqt6-设备监控与间歇性-com-错误-0x8001010d)
- [P19 — QComboBox 自定义 Popup 导致 Windows 崩溃](#p19--qcombobox-自定义-popup-导致-windows-崩溃)
- [P20 — SQLite 跨线程连接访问](#p20--sqlite-跨线程连接访问)
- [P21 — QTableWidget 操作按钮刷新竞态](#p21--qtablewidget-操作按钮刷新竞态)
- [P22 — core.autocrlf 与 .editorconfig 行尾符冲突导致幽灵修改](#p22--coreautocrlf-与-editorconfig-行尾符冲突导致幽灵修改)
- [P23 — GLM API 400 错误：对话历史格式不合规](#p23--glm-api-400-错误对话历史格式不合规)
- [P24 — LLM Tool Schema 中 Callable 参数导致 API 拒绝](#p24--llm-tool-schema-中-callable-参数导致-api-拒绝)
- [P25 — Python 3.14 from \_\_future\_\_ import annotations 与 get\_type\_hints 冲突](#p25--python-314-from-__future__-import-annotations-与-get_type_hints-冲突)

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

---

## P15 — Perfetto detach 须配合 write_into_file

### 现象

使用 `perfetto --detach=<key>` 启动后台抓取后，`--attach` / `--clone` 行为异常，或会话无法按预期落盘、克隆失败。

### 根因

分离（detach）模式依赖将 trace **持续写入文件**（或等价持久化路径）。若 TraceConfig 中未设置 `write_into_file: true`（以及按需的 `file_write_period_ms` 等），与 detach/clone 相关的流程可能不符合 Perfetto 对后台会话的假设。

### 修复方案

在用于 `--detach` 的 TraceConfig（pbtxt / 二进制）中 **显式** 加入：

```text
write_into_file: true
# 按需：file_write_period_ms: 5000
```

并与 `unique_session_name`（若使用 `--clone-by-name`）等字段一并校验。

### 预防措施

- 模块内生成 TraceConfig 时，将「detach 模式」作为单独分支，强制校验 `write_into_file`
- 参考设备端验证脚本：`scripts/test_clone.py` 与 `scripts/doc/test_clone.md`

---

## P16 — Perfetto 同 UID 并发会话上限与残留进程

### 现象

多次启动抓取后，新的 `perfetto` 会话失败，或提示资源/会话数限制；设备上看似已无前台 trace，仍无法新建会话。

### 根因

Android 上 Perfetto 对 **同一 UID 的并发 tracing 会话数** 存在限制（常见为 **每个 UID 最多 5 个**）。异常退出、detach 未 attach stop、脚本重复运行等会留下残留 `perfetto` 进程，占满配额。

### 修复方案

在设备上清理残留进程后再试（需 root 或相应权限时视环境而定），例如：

```bash
adb shell pkill -f perfetto
# 或针对性 kill 已知 PID / 使用 perfetto --attach=<key> --stop
```

GUI/自动化流程在启动新会话前，可增加「检测并提示清理」或「先停止同模块已有会话」的逻辑（在业务允许范围内）。

### 预防措施

- 会话结束路径必须成对：`detach` → 最终 `attach --stop` 或明确 kill
- 开发调试频繁时，养成会话结束后检查 `ps | grep perfetto` 的习惯

---

## P17 — Ring buffer clone 覆盖的时间范围

### 现象

期望「clone 只拿到最近 N 秒（例如预热后的窗口）」的 ring buffer 快照，但实际文件很大或时间轴从会话开始就有数据。

### 根因

**Ring buffer** 在容量未绕回前，保留的是从 **会话开始** 写入的数据；clone 取出的是当前 buffer 中的内容，**不是**「仅最后 N 秒」。只有 buffer 写满并按 ring 策略覆盖后，行为才表现为保留最近一段窗口。预热阶段若 buffer 未满，clone 会包含从启动到当时的**全部**已采集数据。

### 修复方案

- 若业务需要「仅关心最近一段」，需结合 **buffer 大小、数据速率、写满时间** 设计，或缩短会话/分段重启，而不是假设 clone 自动截断为「最后 N 秒」
- 产品文案与 spec 中避免将 ring clone 描述为「仅快照最近 N 秒」除非已证明 buffer 已处于稳定 ring 覆盖状态

### 预防措施

- 在规格与测试中明确：clone 快照的时间跨度与 **buffer 填充阶段** 的关系

---

## P18 — PyQt6 设备监控与间歇性 COM 错误 (0x8001010d)

### 现象

在 Windows 上，设备连接状态轮询、`adb` 相关信号与 UI 更新并存时，**间歇性**出现 `0x8001010d`（`RPC_E_WRONG_THREAD`，部分日志显示为 COM 跨线程错误），崩溃或警告并非必现。

### 根因与区分

- **P01** 中同名错误可能由 **错误的 `context` 键** 导致调错 service（跨模块接口混用）。
- 本条目强调：在 **已正确使用模块前缀键、且遵循 QThread + `pyqtSignal`（见 P05）** 的前提下，仍可能因 **设备监控定时器 / 后台回调与 UI 线程交互边界**、或系统 COM 与 Qt 事件循环的竞态，出现**偶发**跨线程访问。

### 修复方案

- 严格保持 **P05**：任何 UI 控件更新仅在主线程；后台仅通过 `pyqtSignal` 投递结果。
- 设备列表/状态更新：在槽函数内避免长时间阻塞；对 `adb` 回调做串行化或防抖，减少重入。
- 若仍偶发，结合崩溃栈确认是否在非主线程触碰了 Qt/COM 对象；必要时将监控逻辑收口到单一 `QObject` 线程或 `moveToThread` 的 worker，信号统一回主线程。

### 预防措施

- 不将 **P01** 与 **P18** 混为一谈：先排除 context 错键，再查监控路径上的线程边界
- 与 **P05** 联动审查：所有从非 GUI 线程到界面的路径必须只有 signal/slot

---

## P19 — QComboBox 自定义 Popup 导致 Windows 崩溃

### 现象

使用 QComboBox 的子类实现多选下拉（override `hidePopup` 使其不自动关闭），在 Windows 上启动时即崩溃，报 `Windows fatal exception: code 0x8001010d`（COM 线程错误）。

### 根因

重写 `QComboBox.hidePopup()` 为空操作会破坏 Qt 内部的 popup 生命周期管理。Qt 在 Windows 上依赖 COM 机制管理弹出窗口（popup），当 `hidePopup` 被阻止时，内部状态机与 COM 线程之间产生不一致，导致跨线程 COM 调用崩溃。

### 修复方案

不使用 QComboBox 实现多选下拉，改用 QPushButton + QMenu 组合：

```python
class _PersistentMenu(QMenu):
    """点击可勾选项后保持打开，点击其他区域才关闭。"""
    def mouseReleaseEvent(self, event):
        action = self.activeAction()
        if action and action.isCheckable():
            action.trigger()
            return
        super().mouseReleaseEvent(event)

class _DimensionSelector(QPushButton):
    def __init__(self, parent=None):
        super().__init__("全部维度 ▾", parent)
        self._menu = _PersistentMenu(self)
        # 添加可勾选 action ...
        self.clicked.connect(self._show_menu)

    def _show_menu(self):
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._menu.popup(pos)
```

### 预防措施

- MUST NOT override QComboBox.showPopup / hidePopup 来阻止关闭行为
- 需要多选下拉时，使用 QPushButton + QMenu（checkable action）方案
- QMenu 的 `mouseReleaseEvent` 可以安全地阻止关闭，因为 QMenu 的 popup 机制与 QComboBox 不同

---

## P20 — SQLite 跨线程连接访问

### 现象

从 QThread 工作线程中使用主线程创建的 SQLite 连接执行写入操作时，报 `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`。

### 根因

Python `sqlite3` 模块默认设置 `check_same_thread=True`，创建连接的线程与使用连接的线程不同时会抛出异常。toolkit 的 `DatabaseManager.connection` 属性在主线程创建连接，工作线程无法复用。

### 修复方案

工作线程中需要写入数据库时，创建独立的 `sqlite3.connect()` 连接：

```python
def _write_task_to_shared_db(self, task):
    db_path = self._db_manager.connection  # 仅获取路径信息
    conn = sqlite3.connect(str(db_path))   # 独立连接
    try:
        conn.execute("INSERT ...", (...))
        conn.commit()
    finally:
        conn.close()
```

主线程读取可继续使用 `db_manager.connection` 属性。

### 预防措施

- 工作线程写入共享 DB MUST 使用独立连接
- 不要将主线程的 DB 连接对象传递到工作线程
- 考虑使用 `check_same_thread=False`（需自行保证线程安全）仅在确认不会并发写入时

---

## P21 — QTableWidget 操作按钮刷新竞态

### 现象

点击 QTableWidget 行内的操作按钮（如删除、重新分析）后，程序崩溃（`STATUS_STACK_BUFFER_OVERRUN`），或按钮回调中访问的表格行数据已被清除。

### 根因

按钮的 `clicked` 信号回调中直接调用了 `_refresh_history()`（清空并重填表格），此时按钮控件本身尚在事件处理中。Qt 在按钮被销毁后尝试完成事件循环，导致 use-after-free。

### 修复方案

使用 `QTimer.singleShot` 将刷新操作延迟到当前事件处理完成后：

```python
def _delete_report(self, report_dir, trace_path, task_id):
    # ... 删除逻辑 ...
    QTimer.singleShot(100, self._refresh_history)  # 延迟刷新
```

### 预防措施

- QTableWidget 行内按钮的回调中 MUST NOT 直接清空/重填表格
- 任何可能销毁当前控件的操作 MUST 延迟执行（`QTimer.singleShot`）
- 推荐延迟时间 100ms，足以让当前事件循环完成

---

## P22 — core.autocrlf 与 .editorconfig 行尾符冲突导致幽灵修改

### 现象

`git status` 显示大量文件 `modified`，但 `git diff` 无任何内容差异（0 行变更）。重复出现：`git checkout` 恢复后，编辑器一保存又变 modified。

### 根因

三方配置冲突形成恶性循环：

1. **`core.autocrlf = true`**（Windows 全局默认）：checkout 时 LF→CRLF
2. **`.editorconfig end_of_line = lf`**：编辑器保存时统一 LF
3. 工作目录始终是 LF，但 git 期望 CRLF → 标记 modified
4. `git diff` 比较时两侧归一化为 LF → 无差异

附带问题：空占位文件（`.gitkeep`、`__init__.py`）被 `.editorconfig` 的 `insert_final_newline = true` 添加尾换行，产生 0→1 字节变更。

### 诊断方法

```bash
# 确认内容哈希一致（证明是 stat cache 问题而非内容差异）
git ls-files -s -- <file>          # 索引哈希
git hash-object <file>             # 工作目录哈希
# 若两者一致，则为幽灵修改

# 检查文件实际行尾
git ls-files --eol -- <file>       # i/lf w/lf 表示均为 LF
```

### 修复方案

在 `.gitattributes` 中显式声明文本归一化规则，覆盖各协作者的 `autocrlf` 差异：

```gitattributes
# 文本文件统一 LF（与 .editorconfig 一致）
* text=auto eol=lf

# Windows 脚本保持 CRLF（与 .editorconfig 一致）
*.ps1 text eol=crlf
*.bat text eol=crlf
*.cmd text eol=crlf
```

修复后执行：

```bash
git add --renormalize .    # 刷新索引
git commit -m "normalize line endings"
# 对已被 autocrlf 转换的文件需要完整重建 stat cache：
git rm --cached <file> && git checkout HEAD -- <file>
```

### 预防措施

- 新项目 MUST 在首次提交时包含 `.gitattributes` 的 `* text=auto eol=lf` 规则
- `.gitattributes` 的 `eol` 设置 MUST 与 `.editorconfig` 的 `end_of_line` 一致
- 不要依赖 `core.autocrlf` 全局设置来统一行尾符——每个协作者的设置可能不同
- 出现幽灵修改时，先用 `git hash-object` 对比哈希，再用 `git ls-files --eol` 检查行尾

---

## P23 — GLM API 400 错误：对话历史格式不合规

**严重程度**：严重（多轮对话必现）

### 问题描述

Agent 首次消息正常，第二条消息起 GLM API 返回 `Error code: 400, "API调用参数有误"`。原因是多轮对话时历史消息格式不符合 OpenAI 兼容 API 的要求。

### 错误根因（三个并发）

1. **`arguments` 未序列化为 JSON string**：assistant 消息中的 `tool_calls[].function.arguments` 必须是 JSON 字符串，但代码中传递了 Python dict
2. **`tool_call_id` 缺失**：tool 角色消息必须包含 `tool_call_id` 字段，但未从 `Message` 对象中提取
3. **未知字段干扰**：消息中包含 API 不认识的额外字段（如 `report_paths`）

### 修复方案

在 `glm_provider.py` 中添加 `_sanitize_messages()` 函数，在发送前统一清洗：

```python
def _sanitize_messages(messages: list[dict]) -> list[dict]:
    _VALID_KEYS = {
        "system": {"role", "content"},
        "user": {"role", "content"},
        "assistant": {"role", "content", "tool_calls"},
        "tool": {"role", "content", "tool_call_id"},
    }
    # 1. 仅保留各角色允许的字段
    # 2. assistant + tool_calls: arguments 序列化为 JSON string
    # 3. assistant + tool_calls + 无 content: content 设为 None
    # 4. tool 消息必须有 tool_call_id，否则跳过
```

同时在 `Message` 数据模型中新增 `tool_call_id: str = ""` 字段，并在 `ConversationStore` 的 messages 表中持久化。

### 预防措施

- 凡是向 LLM API 发送历史消息，MUST 在发送前执行格式清洗
- 数据模型的字段变更 MUST 同步更新数据库 schema 和 CRUD 方法
- 在多轮对话测试中，MUST 包含至少一次工具调用后再发消息的场景

---

## P24 — LLM Tool Schema 中 Callable 参数导致 API 拒绝

**严重程度**：中等（特定工具注册时触发）

### 问题描述

通过 `inspect.signature()` + `get_type_hints()` 自动生成工具的 JSON Schema 时，Python 的 `Callable` 类型参数（如回调函数 `on_progress: Callable`）会被转换为 `{"type": "string"}`，LLM 无法传递回调函数，GLM API 可能拒绝该参数定义。

### 修复方案

在 `ToolRegistry._enhance_schema()` 中添加 `_is_callable_type()` 过滤函数：

```python
def _is_callable_type(hint: Any) -> bool:
    """检查是否为 Callable/Optional[Callable]/Callable | None。"""
    origin = getattr(hint, "__origin__", None)
    if origin is collections.abc.Callable:
        return True
    # 递归检查 Union 类型中的 Callable 成员
    ...
```

在遍历参数时跳过所有 `Callable` 类型的参数。

### 预防措施

- 模块暴露给 Agent 的方法 SHOULD 避免使用 `Callable` 参数；如需回调，提供不含回调的重载版本
- `register_agent_tools()` 中 SHOULD 显式提供 `parameters` JSON Schema 而非依赖自动推断
- 自动推断 MUST 过滤掉 `Callable`、`Generator`、`Iterator` 等非序列化类型

---

## P25 — Python 3.14 from \_\_future\_\_ import annotations 与 get\_type\_hints 冲突

**严重程度**：低（仅影响测试）

### 问题描述

在使用 `from __future__ import annotations` 的模块中，通过 `exec()` 或局部定义的函数使用 `typing.Callable` 作为类型注解时，`get_type_hints()` 会抛出 `NameError: name 'Callable' is not defined`。这是因为 `annotations` future 将所有注解变为字符串，求值时在函数的 `__globals__` 中找不到 `Callable`。

### 修复方案

测试中定义带类型注解的函数时，使用 `exec()` 在独立命名空间中创建，并使用 `collections.abc.Callable` 代替 `typing.Callable`：

```python
func_code = (
    "import collections.abc\n"
    "def my_tool(path: str, callback: collections.abc.Callable | None = None) -> str:\n"
    "    return 'ok'\n"
)
ns: dict = {}
exec(func_code, ns)
my_tool = ns["my_tool"]
```

### 预防措施

- 在测试中定义需要 `get_type_hints()` 处理的函数时，MUST 确保类型注解在函数的 `__globals__` 中可解析
- 优先使用 `collections.abc.Callable` 而非 `typing.Callable`（前者不受 annotations future 影响）
