# 模块开发常见踩坑指南

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
- [P26 — Perfetto 引擎 Jank 检测误判（阈值与首周期）](#p26--perfetto-引擎-jank-检测误判阈值与首周期)
- [P27 — Speckit Skills 通用模板需项目适配](#p27--speckit-skills-通用模板需项目适配)
- [P28 — SurfaceView 游戏帧数据采集需 SurfaceFlinger fallback](#p28--surfaceview-游戏帧数据采集需-surfaceflinger-fallback)
- [P29 — Python 短路求值传 None 给 Qt setEnabled()](#p29--python-短路求值传-none-给-qt-setenabled)
- [P30 — QWidget 子类 CSS 背景不渲染](#p30--qwidget-子类-css-背景不渲染)
- [P31 — 函数早返回跳过资源清理逻辑](#p31--函数早返回跳过资源清理逻辑)
- [P32 — Bug 修复中用瞬时值替代稳定基准值导致级联回归](#p32--bug-修复中用瞬时值替代稳定基准值导致级联回归)
- [P33 — 技术选型阶段重复造轮子](#p33--技术选型阶段重复造轮子)
- [P34 — Pydantic AI + LiteLLM prompt 超出模型上下文限制](#p34--pydantic-ai--litellm-prompt-超出模型上下文限制)
- [按子系统快速索引](#按子系统快速索引)
  - [插件框架](#插件框架)
  - [GUI / PyQt6](#gui--pyqt6)
  - [ADB / 设备](#adb--设备)
  - [Perfetto](#perfetto)
  - [构建 / PyInstaller](#构建--pyinstaller)
  - [LLM / Agent](#llm--agent)
  - [工具链 / 环境](#工具链--环境)
- [按生命周期分类](#按生命周期分类)

---

## 按子系统快速索引

开发时根据当前工作的子系统快速定位相关踩坑经验，无需通读全部 31 项。

### 插件框架

| 编号 | 标题 | 严重度 | 关键词 |
|------|------|--------|--------|
| P01 | 插件 context 键名冲突 | 严重 | context 前缀、键名覆盖 |
| P03 | 插件类必须继承 BasePlugin | 中等 | pluggy、hookimpl |
| P04 | pytest 跨模块测试文件名冲突 | 中等 | conftest、import-mode |
| P12 | Pydantic vs dataclass 选型 | 低 | 公共 API、JSON Schema |

### GUI / PyQt6

| 编号 | 标题 | 严重度 | 关键词 |
|------|------|--------|--------|
| P05 | QThread 信号安全 | 严重 | pyqtSignal、线程通信 |
| P07 | GUI 状态重置需保留用户上下文 | 中等 | 刷新、状态丢失 |
| P11 | PyQt6 无边框窗口事件处理 | 低 | frameless、WA_TranslucentBackground |
| P18 | 设备监控与间歇性 COM 错误 | 严重 | COM、0x8001010d、QTimer |
| P19 | QComboBox 自定义 Popup 崩溃 | 严重 | Windows、Popup、showPopup |
| P20 | SQLite 跨线程连接访问 | 严重 | check_same_thread、QThread |
| P21 | QTableWidget 操作按钮刷新竞态 | 中等 | blockSignals、cellWidget |
| P29 | Python 短路求值传 None 给 Qt setEnabled() | 中等 | setEnabled、短路求值、bool |
| P30 | QWidget 子类 CSS 背景不渲染 | 中等 | paintEvent、QStyleOption、透明 |
| P31 | 函数早返回跳过资源清理逻辑 | 严重 | 早返回、cleanup、线程停止 |
| P32 | Bug 修复中用瞬时值替代稳定基准值导致级联回归 | 严重 | 瞬时值、基准、回归、Jank 检测 |
| P33 | 技术选型阶段重复造轮子 | 严重 | 技术选型、第三方库、LiteLLM、LLM Provider |

### ADB / 设备

| 编号 | 标题 | 严重度 | 关键词 |
|------|------|--------|--------|
| P02 | ADB 命令输出可能为 None | 中等 | stdout、`or ""`保护 |
| P09 | ADB remount 首次需重启 | 低 | remount、reboot |

### Perfetto

| 编号 | 标题 | 严重度 | 关键词 |
|------|------|--------|--------|
| P15 | Perfetto detach 须配合 write_into_file | 严重 | detach、文件输出 |
| P16 | 同 UID 并发会话上限与残留进程 | 中等 | UID、并发、cleanup |
| P32 | Bug 修复中用瞬时值替代稳定基准值导致级联回归 | 严重 | 瞬时值、基准、Jank |
| P17 | Ring buffer clone 覆盖的时间范围 | 中等 | ring_buffer、clone、时间窗口 |
| P26 | Jank 检测误判（阈值与首周期） | 中等 | jank_1、jank_3、VSync、首周期 |
| P28 | SurfaceView 游戏帧数据采集需 SF fallback | 严重 | SurfaceView、gfxinfo、SurfaceFlinger |

### 构建 / PyInstaller

| 编号 | 标题 | 严重度 | 关键词 |
|------|------|--------|--------|
| P13 | noconsole 模式 sys.stdout/stderr 为 None | 严重 | PyInstaller、noconsole、NoneType |
| P14 | 资源文件路径解析 | 中等 | _MEIPASS、sys._MEIPASS |

### LLM / Agent

| 编号 | 标题 | 严重度 | 关键词 |
|------|------|--------|--------|
| P23 | GLM API 400 错误：对话历史格式 | 中等 | GLM、message role、sanitize |
| P24 | Tool Schema 中 Callable 参数 | 严重 | Callable、JSON Schema、序列化 |
| P25 | Python 3.14 annotations 与 get_type_hints 冲突 | 低 | `__future__`、ForwardRef |
| P33 | 技术选型阶段重复造轮子 | 严重 | LiteLLM、自建 Provider、第三方评估 |
| P34 | Pydantic AI prompt 超出模型上下文限制 | 中 | pydantic-ai、LiteLLM、GLM、prompt length |

### 工具链 / 环境

| 编号 | 标题 | 严重度 | 关键词 |
|------|------|--------|--------|
| P06 | Windows 控制台中文编码 | 中等 | encoding、chcp、UTF-8 |
| P08 | Typer CLI 帮助命令退出码 | 低 | SystemExit、exit code |
| P10 | PowerShell heredoc 语法不兼容 | 低 | heredoc、`@"`...`"@` |
| P22 | core.autocrlf 与 .editorconfig 行尾符冲突 | 低 | CRLF、LF、幽灵修改 |
| P27 | Speckit Skills 通用模板需项目适配 | 低 | speckit、模板裁剪、技术工具 |

## 按生命周期分类

| 阶段 | 相关 Pitfalls |
|------|---------------|
| 设计时 | P01, P03, P04, P12 |
| 编码时（GUI） | P05, P07, P11, P18, P19, P20, P21, P29, P30, P31 |
| 编码时（ADB/设备） | P02, P09 |
| 编码时（Perfetto） | P15, P16, P17, P26, P28 |
| 编码时（Agent/LLM） | P23, P24, P25 |
| 构建时 | P13, P14, P22 |
| 环境/工具 | P06, P08, P10, P27 |

---

## 代码规则（与本文档的关系）

本文件描述 **具体反例与修法**；**总纲级约定**（分层、Ruff、context 前缀、框架边界、合并前测试等）以架构文档 **[§5.0 代码规则（总纲）](../../doc/architecture/architecture-overview.md#50-代码规则总纲)** 与 **`.specify/memory/constitution.md`** 为准。踩坑条目中的 **MUST** 与总纲一并遵守。

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

---

## P26 — Perfetto 引擎 Jank 检测误判（阈值与首周期）

**严重程度**：中等（影响分析准确度）

### 现象

引擎对无卡顿的游戏 trace（`com.tencent.lolm`，60Hz）报告 5 次丢帧，但人工在 Perfetto UI 中逐帧确认无实际丢帧，MCP 工具也报告 0 jank。

### 根因（三个并发问题）

1. **jank_1 阈值过严**：App Deadline Missed 判定条件为 `(vt - bt2) > 1× VSync 周期`（60Hz 下 16.67ms），导致 17ms 完成的正常帧被标为丢帧。实际用户标准为 1.5× VSync（25ms）
2. **jank_3 观测窗口不合理**：SF Composition Missed 使用固定 1ms 窗口检查 SF 是否消费了 buffer，该窗口过窄且与刷新率无关。SF 的正常消费延迟在不同刷新率下差异显著
3. **首周期无守卫**：trace 第一个 VSync 周期中 `prev_cycle_ns == 0` 导致双周期校验被跳过，`bt2` 初始化为 `pre_vt`（非真实消费时间戳），buffer 状态尚未稳态，jank_3 触发初始化伪影

### 修复方案

```python
# 1. 首周期守卫：第一个周期缺乏前置上下文，跳过 jank 判定
skip_jank = prev_cycle_ns == 0

# 2. jank_1: 阈值从 1× 放宽到 1.5× VSync
jank_1 = (vt - bt2) / 1e6 > stand_ms * 1.5 if bt2 else False

# 3. jank_3: 自适应窗口，按刷新率缩放
sf_window_ns = int(stand_ms * 0.5 * 1e6)  # 0.5× VSync
hi_3 = bisect.bisect_right(buffer_ev_ts, pre_vt + sf_window_ns)
```

### 阈值设计依据

| 判定 | 含义 | 旧阈值 | 新阈值 | 理由 |
|------|------|--------|--------|------|
| jank_1 | App 交付帧超时 | 1× VSync | 1.5× VSync | 与 SurfaceFlinger FrameTimeline 的 Jank 判定对齐 |
| jank_3 | SF 有 buffer 但未消费 | 固定 1ms | 0.5× VSync | 给 SF 合理响应时间，同时自适应不同刷新率 |
| 首周期 | trace 开头首个 VSync 周期 | 无守卫 | 跳过判定 | 缺乏前周期上下文和稳态 buffer 状态 |

### 验证结果

| Trace | 修复前 | 修复后 | 人工判定 |
|-------|--------|--------|----------|
| lolm 游戏（60Hz，无卡顿） | 5 次丢帧 | 0 次 | 0 次 |
| Launcher 慢划（120Hz，有卡顿） | 5 次丢帧 | 3 次 | 有丢帧 |

### 预防措施

- Jank 检测阈值 MUST 有明确的理论依据（如对齐 Android FrameTimeline 标准），MUST NOT 使用未经验证的固定值
- 与刷新率相关的参数 MUST 按 `stand_ms` 自适应缩放，MUST NOT 使用固定毫秒/纳秒常量
- Trace 边界（首/末周期）的 jank 判定需额外守卫，因为 VSync/BufferTX 状态机尚未/已经退出稳态
- 新增或修改 jank 判定逻辑后，MUST 同时用已知有卡顿和无卡顿的 trace 交叉验证

---

## P27 — Speckit Skills 通用模板需项目适配

| 属性 | 值 |
|------|------|
| 严重度 | 低 |
| 影响 | spec 质量 |
| 触发条件 | 使用 speckit skills 模板初始化或执行 spec 流程 |

### 现象

Speckit 的通用 skills（specify、implement、constitution 等）基于广泛假设设计，直接使用时部分规则不适合本项目：

1. `speckit-implement` 的 ignore-file matrix 包含大量非 Python 技术栈配置（如 Rust、Go、Java 相关），对纯 Python 项目无意义
2. `speckit-specify` 要求 spec "不涉及技术实现"，但本项目的模块（Perfetto 引擎、ADB 工具）本身是技术工具，spec 中需合理包含技术约束
3. `speckit-constitution` 的模板初始化适用于新项目，对已有成熟 constitution 的项目应做增量修订而非重建

### 应对

- 使用 speckit skills 时，根据本项目技术栈（Python 3.12+ / PyQt6 / Pydantic）裁剪不适用的配置
- 技术工具类模块的 spec 可在 Functional Requirements 中包含技术约束（如 CLI 参数格式、数据模型定义），不必严格遵循"不涉及技术实现"
- 对已有 constitution 执行增量修订（添加新原则/更新技术栈），而非从模板重建

---

## P28 — SurfaceView 游戏帧数据采集需 SurfaceFlinger fallback

| 属性 | 值 |
|------|------|
| 严重度 | 严重 |
| 影响 | 帧率监控完全失效 |
| 触发条件 | 对 SurfaceView 渲染的游戏使用 `dumpsys gfxinfo framestats` |

### 现象

使用 `dumpsys gfxinfo <pkg> framestats` 采集帧数据时，大多数游戏（Unity/Unreal/自研引擎）返回的 `---PROFILEDATA---` 段为空。日志显示 `解析帧数据为空`，FPS 曲线完全无数据。

### 根因

游戏通常使用 `SurfaceView` 渲染（OpenGL ES / Vulkan），不经过 Android HWUI 渲染管线。`gfxinfo framestats` 只统计 HWUI 管线的帧数据，对 SurfaceView 渲染无效。

### 解决方案

使用 `dumpsys SurfaceFlinger --latency <layer_name>` 作为 fallback：

1. **自动检测帧数据源**：先尝试 `gfxinfo framestats`，如果 `---PROFILEDATA---` 为空则切换到 SF latency
2. **SurfaceFlinger 图层名匹配**：通过 `dumpsys SurfaceFlinger --list` 列出所有图层，使用正则匹配包名 + `SurfaceView` + `(BLAST)` 后缀
3. **图层名必须精确**：`dumpsys SurfaceFlinger --latency` 要求完整图层名（含 hash 前缀和 `(BLAST)` 后缀），否则返回空数据

```python
# 图层名格式示例
# 正确：SurfaceView[com.game.pkg/Activity](BLAST)#12
# 错误：SurfaceView[com.game.pkg/Activity]  （缺少 BLAST 后缀）
pattern = re.compile(
    rf"SurfaceView\[{re.escape(package)}[^\]]*\].*?\(BLAST\)",
    re.IGNORECASE,
)
```

### 预防措施

- 帧率采集逻辑 MUST 先检测帧数据源，MUST NOT 硬编码 gfxinfo 为唯一来源
- 使用 `SurfaceFlinger --latency` 时 MUST 通过 `--list` 动态获取完整图层名
- 图层名匹配 SHOULD 优先选择 `(BLAST)` 图层（表示活跃渲染）

---

## P29 — Python 短路求值传 None 给 Qt setEnabled()

| 属性 | 值 |
|------|------|
| 严重度 | 中等 |
| 影响 | UI 初始化崩溃 |
| 触发条件 | `and` 表达式左侧为 `None` 的结果传给 `setEnabled()` |

### 现象

```
TypeError: setEnabled(self, a0: bool): argument 1 has unexpected type 'NoneType'
```

历史面板初始化时崩溃，因为 `_update_action_buttons_state(None)` 调用时计算的 `is_trace` 值为 `None`。

### 根因

Python 的 `and` 短路求值不返回 `bool`，而是返回第一个假值或最后一个值：

```python
item_data = None
is_trace = item_data and item_data.get("type") == "trace"
# is_trace = None，不是 False！

# 后续调用
btn.setEnabled(is_trace and btn.isEnabled())  # None 传给 setEnabled → TypeError
```

PyQt6 的 `setEnabled()` 严格要求 `bool` 类型，不接受 `None`。

### 解决方案

用 `bool()` 包装短路求值结果：

```python
is_trace = bool(item_data and item_data.get("type") == "trace")
```

### 预防措施

- 传给 Qt API 的布尔参数 MUST 确保为 `bool` 类型，SHOULD 使用 `bool()` 包装含 `and`/`or` 的表达式
- `None and X` 结果是 `None`，`None or X` 结果是 `X` — 与 `False` 的行为不同

---

## P30 — QWidget 子类 CSS 背景不渲染

| 属性 | 值 |
|------|------|
| 严重度 | 中等 |
| 影响 | 自定义面板透明，内容不可见 |
| 触发条件 | 自定义 QWidget 子类设置 CSS background 但不覆写 paintEvent |

### 现象

`HistoryPanel(QWidget)` 通过 CSS 设置了深色背景 `background: #313244`，但实际渲染时面板透明，内容与底层 UI 混叠难以阅读。

### 根因

Qt 的 QWidget 基类默认不处理 CSS 样式表中的背景绘制。只有 Qt 内置控件（QPushButton、QLabel 等）或显式覆写了 `paintEvent` 的自定义 QWidget 才能正确渲染 CSS 背景。

### 解决方案

覆写 `paintEvent` 并使用 `QStyleOption`：

```python
class HistoryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)

    def paintEvent(self, event):
        from PyQt6.QtWidgets import QStyleOption, QStyle
        from PyQt6.QtGui import QPainter
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        p.end()
```

### 预防措施

- 自定义 QWidget 子类使用 CSS background 时 MUST 覆写 `paintEvent` 或 `setAutoFillBackground(True)` + `QPalette`
- 此规则适用于所有直接继承 QWidget 的容器面板

---

## P31 — 函数早返回跳过资源清理逻辑

| 属性 | 值 |
|------|------|
| 严重度 | 严重 |
| 影响 | 后台线程泄漏，功能无法停止 |
| 触发条件 | 停止函数开头的前置条件检查导致清理代码被跳过 |

### 现象

用户点击"停止"按钮后，Perfetto 抓取停止了，但 Jank 监控线程继续运行（FPS 曲线持续刷新）。

### 根因

```python
def _on_stop(self) -> None:
    if not self._service or not self._serial:
        return  # 设备断连时 serial=None，直接返回
    # ... Jank 停止逻辑在这之后，被跳过了
    if self._jank_worker:
        self._stop_jank_monitor()
```

当设备短暂断连（`self._serial` 被置为 `None`）后，用户点击停止时，前置条件检查让函数提前返回，Jank 工作线程的清理逻辑被完全跳过。

### 解决方案

将资源清理逻辑放在前置条件检查之前：

```python
def _on_stop(self) -> None:
    self._set_capturing(False)
    self._timer.stop()

    if self._jank_worker:
        self._stop_jank_monitor()  # 无论设备状态如何，先清理线程

    if not self._service or not self._serial:
        return
    # ... 后续 Perfetto 停止逻辑
```

### 预防措施

- 包含资源清理的函数，清理逻辑 MUST 放在前置条件检查之前，确保任何退出路径都不会跳过清理
- 对于 QThread 等后台资源，停止/释放操作 SHOULD 无条件执行，即使关联的外部状态已变化
- 函数中的早返回（guard clause）MUST 审查是否会跳过后续的清理/释放/断开连接等副作用操作

## P32 — Bug 修复中用瞬时值替代稳定基准值导致级联回归

**子系统**：Perfetto Capture / Jank 检测  
**日期**：2026-04-03

### 现象

修复"30fps 游戏在 120Hz 屏幕上误触发 jank 抓取"的 bug 时，将丢帧判定的 vsync 基准从显示器刷新率（120Hz = 8.33ms）直接替换为 `stats.fps`（瞬时 FPS）计算的游戏帧周期。导致：

1. 首次采样 FPS 为 0 时 vsync 计算异常，检测完全失效
2. FPS 波动时（如游戏加载、场景切换）vsync 基准不稳定，时而误判时而漏判
3. 连续两次"修了再改"但未跑回归测试，引入更多回归

### 根因

1. **用瞬时值替代稳定基准**：`stats.fps` 是 200ms 批次的瞬时计算值，受帧数波动影响大，不适合做检测阈值的基准
2. **改动前缺乏影响分析**：没有梳理 vsync_ms 在状态机中的所有使用场景（触发条件、丢帧计数、稳定期判定）
3. **连续修改无验证**：第一次改坏后又改了一版，仍未通过实际设备验证就部署

### 解决方案

采用**滚动中位数估算游戏目标帧率**：
- 维护最近 15 次 FPS 采样的历史记录
- 取中位数作为游戏稳定帧率的估算（抗抖动）
- 前 5 次采样（约 1 秒）为热身期，不做触发判定，避免启动瞬态误触发
- `max(game_vsync, display_vsync)` 确保不低于显示器基线

```python
sorted_fps = sorted(self._fps_history)
median_fps = sorted_fps[len(sorted_fps) // 2]
game_vsync = 1000.0 / max(median_fps, 1)
return max(game_vsync, display_vsync)
```

### 预防措施

- 修改检测算法的基准值时 MUST 评估该值的稳定性和边界情况（零值、极值、波动）
- 核心逻辑修改 MUST 先输出影响分析（参见 `.cursor/rules/core-logic-change-gate.mdc`）
- Bug 修复 MUST NOT 连续多次修改同一段核心逻辑而不跑测试验证
- 涉及实时数据做基准的场景 SHOULD 使用滚动窗口统计量（中位数/均值）而非瞬时值

## P33 — 技术选型阶段重复造轮子

### 严重程度：严重

### 场景

需要为框架添加 LLM 多 Provider 统一调用能力时，直接从 `agent_chat` 模块中迁移了自建的 `GLMProvider`（手写 JWT + httpx SSE 流解析）和 `ClaudeProvider`（手写 Anthropic Stream 事件解析）。这些代码约 400 行，存在以下问题：

1. **维护成本高**：每新增一个 Provider 需要手写 HTTP 请求、认证、流解析、错误处理
2. **稳定性风险**：自建的 SSE 解析、JWT 生成、消息格式转换缺少充分测试
3. **功能缺失**：缺少重试、速率限制、并发控制等生产级能力

### 根因

- 技术选型阶段（speckit research）只确认了"技术栈已在项目中使用"，**没有评估是否存在更好的第三方方案**
- 从模块迁移代码时惯性思维，未重新审视"是否值得自建"

### 正确做法

引入 **LiteLLM**（`litellm>=1.80.0`），通过 `litellm.acompletion()` 统一所有 Provider 调用：

- GLM: `zai/glm-4-plus` 路由
- Claude: `claude-sonnet-4-20250514` 路由
- 新增 Provider: 只需修改 model name，无需写代码

```python
# 自建（已废弃）— 每个 Provider ~200 行
class GLMProvider(LLMProvider):
    def __init__(self, api_key, model):
        self._token = _generate_jwt(api_key)  # 手动 JWT
    async def stream_chat(self, messages, ...):
        resp = await self._client.post(...)  # 手动 HTTP + SSE

# LiteLLM（当前）— 一个类适配所有 Provider
class LiteLLMProvider(LLMProvider):
    async def stream_chat(self, messages, ...):
        async for chunk in await litellm.acompletion(
            model=self._litellm_model, messages=messages,
            api_key=self._api_key, stream=True,
        ):
            yield self._convert_chunk(chunk)
```

### 预防措施

- Speckit research 阶段 MUST 评估"是否有成熟的第三方库可以替代自建实现"
- 评估维度：社区活跃度、依赖重量、API 稳定性、功能覆盖度
- 从其他模块迁移代码时 MUST 重新审视"迁移 vs 引入第三方"
- `spec.md` 中的技术选型章节 SHOULD 包含"替代方案评估"小节

## P34 — Pydantic AI + LiteLLM prompt 超出模型上下文限制

### 严重程度：中

### 场景

使用 Pydantic AI 创建 SubAgent，其 system prompt 由以下部分组成：
1. Agent instructions（SOP 文档内容）
2. 工具 docstring（pydantic-ai 自动将所有注册工具的 docstring 序列化为 JSON schema 放入 system prompt）
3. 用户 prompt（trace 路径、分析场景等）

GLM-4-Plus（ZhipuAI）返回 `ZaiException - Prompt exceeds max length`，尽管模型标称 128K 上下文。

### 根因

实际测量后发现，**初始 prompt 仅约 5K token**（远低于 128K 上限），真正的瓶颈是：

- **工具返回值在对话历史中的累积**：每个 pa_* 工具返回的原始数据（丢帧列表、线程统计等）约 5K-20K token/次
- LLM 连续调用 3-4 个工具后，对话历史中的工具返回值累积超出模型上下文限制
- 冗余工具（pa_analyze_full、pa_cpu_overview 功能被 pa_analyze_dimension 覆盖）增加了不必要的 schema 占用

早期误判：
- 最初以为是 SOP 文档过长或工具 docstring 过于详细导致 system prompt 超限
- 实际上 SOP + 工具 schema + instructions 总计仅 ~5K token

### 解决方案（010-prompt-budget-management）

1. **ToolReturn 压缩工具返回值**：所有 pa_* 工具返回 Pydantic AI 的 `ToolReturn` 对象，`return_value` 为 ResultCompressor 压缩后的摘要（Top-5 + 统计，~300 token），`metadata` 保留原始数据给应用层
2. **移除冗余工具**：删除 pa_analyze_full 和 pa_cpu_overview（11 → 9 个工具），减少 ~20% 的 schema 占用
3. **SOP 完整加载**：取消 3000 字符截断限制，通过 SKILL 路由完整加载场景 SOP，提升分析质量
4. **上下文超限降级**：LLM 调用因上下文超限失败时，不终止分析，降级到 engine 分析并在报告中标注

### 预防措施

- 使用 Pydantic AI 的 `ToolReturn` 控制工具返回值大小，MUST 在 `return_value` 中只放摘要
- 工具 docstring SHOULD 尽量简短（一行描述）
- 注册的工具 MUST 无功能重叠，冗余工具及时清理
- 新增工具时 MUST 评估其返回值大小，超过 1K token 的原始数据 MUST 经过压缩
- 上下文超限 MUST 有降级方案，不可直接终止用户操作
