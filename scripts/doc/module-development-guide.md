# 模块开发指导手册

## 目录

- [快速开始](#快速开始)
- [开发前准备](#开发前准备)
  - [环境要求](#环境要求)
  - [项目结构认知](#项目结构认知)
  - [必读文档](#必读文档)
- [Step 1 — 创建模块骨架](#step-1--创建模块骨架)
- [Step 2 — Spec-Driven 开发流程](#step-2--spec-driven-开发流程)
  - [2.1 specify — 功能规格](#21-specify--功能规格)
  - [2.2 clarify — 需求澄清](#22-clarify--需求澄清)
  - [2.3 UE/UI design — 界面设计](#23-ueui-design--界面设计)
  - [2.4 plan — 实现计划](#24-plan--实现计划)
  - [2.5 tasks — 任务清单](#25-tasks--任务清单)
  - [2.6 analysis — 预实现一致性检查](#26-analysis--预实现一致性检查)
  - [2.7 implement — 代码实现](#27-implement--代码实现)
  - [2.8 analysis — 实现后验证](#28-analysis--实现后验证)
- [Step 3 — 代码实现规范](#step-3--代码实现规范)
  - [模块文件结构](#模块文件结构)
  - [Service 层](#service-层)
  - [GUI 层](#gui-层)
  - [CLI 层](#cli-层)
  - [Plugin 注册](#plugin-注册)
  - [测试](#测试)
- [Step 4 — 验收与提交](#step-4--验收与提交)
- [常见错误与避坑指南](#常见错误与避坑指南)
- [附录 — 命令速查](#附录--命令速查)

---

## 快速开始

```powershell
# 1. 创建模块骨架（自动初始化 speckit）
python scripts/create_module.py my_module --display-name "我的模块"

# 2. 进入模块目录
cd modules/my_module

# 3. 使用 speckit 开始 spec-driven 开发
# 在 Cursor 中使用 /speckit.specify 命令

# 4. 运行测试
cd ../..
python scripts/run_all_tests.py
```

---

## 开发前准备

### 环境要求

| 工具 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+ | 运行时 |
| uv | 最新 | 包管理 |
| uvx | 最新 | speckit 安装 |
| Cursor | 最新 | AI Agent IDE |
| Git | 任意 | 版本控制 |
| ADB | 最新 | 设备调试（如需） |

```powershell
# 安装虚拟环境和依赖
uv venv
uv pip install -e ".[dev]"

# 验证环境
.venv\Scripts\python.exe -m toolkit.app --help
```

### 项目结构认知

```
lv-game-toolkit/
├── toolkit/              # 核心框架（❌ 模块开发禁止修改）
│   ├── core/             #   核心服务（AdbManager, ConfigManager 等）
│   ├── sdk/              #   公共模型和异常（✅ 模块可导入）
│   └── gui/              #   GUI 框架（BaseTab, MainWindow 等）
├── modules/              # 功能模块目录
│   ├── device_disguise/  #   设备伪装模块（参考实现）
│   ├── game_perf/        #   游戏性能配置模块（参考实现）
│   └── perfetto_capture/ #   Perfetto 卡顿抓取模块
├── scripts/              # 脚手架和工具脚本
├── .specify/             # 主 speckit（全局规则）
└── .cursor/rules/        # Cursor Agent 规则
```

### 必读文档

在开始开发前，请务必阅读以下文档：

1. **`.specify/memory/constitution.md`** — 项目最高治理文档，所有原则和约束
2. **`scripts/doc/development-pitfalls.md`** — 踩坑指南（12 项常见问题）
3. **`.cursor/rules/spec-workflow.mdc`** — Spec-Driven 工作流规范
4. **已有模块源码** — `modules/game_perf/` 是最完整的参考实现

---

## Step 1 — 创建模块骨架

```powershell
# 格式
python scripts/create_module.py <module_name> [--display-name "显示名称"] [--cli-ns 命名空间]

# 示例
python scripts/create_module.py log_analysis --display-name "日志分析" --cli-ns log
```

脚手架会自动完成以下操作：

1. 生成模块目录结构（`src/`、`tests/`、`specs/`、`fixtures/`）
2. 生成骨架文件（`plugin.py`、`service.py`、`cli_commands.py`、`gui_tab.py`）
3. 初始化模块级 speckit（`.specify/`）
4. 生成模块级 Constitution（继承主 Constitution）
5. 生成 `AGENTS.md`（AI 开发规则）

> **重要**：如果 `uvx` 未安装，speckit 初始化会被跳过，请手动执行。

---

## Step 2 — Spec-Driven 开发流程

本项目强制使用 8 步 Spec-Driven 流程。所有步骤必须在模块目录的 speckit 环境下执行。

### 2.1 specify — 功能规格

**目的**：定义功能需求、用户故事、验收标准

在 Cursor 中打开模块目录，使用 `/speckit.specify` 命令，输出到 `specs/<feature-id>/spec.md`。

spec.md 必须包含：
- **User Stories** — 按优先级排列，含验收场景（Given/When/Then）
- **Edge Cases** — 异常和边界情况
- **Functional Requirements** — FR-001 到 FR-NNN
- **Key Entities** — 核心类/模型说明
- **Success Criteria** — 可度量的成功标准

### 2.2 clarify — 需求澄清

**目的**：消除需求歧义，与用户确认设计决策

使用 `/speckit.clarify` 或与用户对话，针对以下问题进行澄清：
- 技术方案选择（如数据模型用 Pydantic 还是 dataclass）
- 业务逻辑的边界条件
- 与其他模块的交互方式
- 数据存储方案

**所有澄清结论必须回写到 `spec.md` 的 Clarifications 章节。**

### 2.3 UE/UI design — 界面设计

**目的**：设计 GUI 界面布局，确保与整体风格一致

- 涉及 GUI 的功能 MUST 提供 2-3 种界面方案供用户选择
- 子模块界面风格 MUST 与主模块一致
- 输出到 `specs/<feature-id>/ui-design.md`

> 纯后端/CLI 模块可跳过此步骤。

### 2.4 plan — 实现计划

使用 `/speckit.plan` 生成实现计划，输出到 `specs/<feature-id>/plan.md`。

计划须包含：
- 技术上下文（依赖项）
- Constitution 合规性检查
- 影响范围（新增/修改的文件）
- 分阶段实施方案

### 2.5 tasks — 任务清单

使用 `/speckit.tasks` 生成任务清单，输出到 `specs/<feature-id>/tasks.md`。

任务清单须包含：
- 每个任务的具体行动项（checkbox 格式）
- 任务间依赖关系
- FR ↔ Task 可追溯矩阵

### 2.6 analysis — 预实现一致性检查

使用 `/speckit.analyze` 检查 spec → plan → tasks 的一致性。

**FAIL 项必须清零后方可进入实现阶段。**

### 2.7 implement — 代码实现

按 tasks 清单逐项实现。实现时遵循 [代码实现规范](#step-3--代码实现规范)。

### 2.8 analysis — 实现后验证

实现完成后再次执行 `/speckit.analyze`，确保代码与 spec 对齐。

**FAIL 项必须清零方可提交。**

---

## Step 3 — 代码实现规范

### 模块文件结构

```
modules/my_module/
├── manifest.json          # 模块元数据
├── AGENTS.md              # AI 开发规则
├── src/
│   ├── __init__.py
│   ├── plugin.py          # 插件注册入口（hookimpl）
│   ├── service.py         # 核心业务逻辑（纯同步）
│   ├── models.py          # 数据模型
│   ├── cli_commands.py    # CLI 子命令
│   ├── gui_tab.py         # GUI Tab 页
│   └── migrations/        # 数据库迁移脚本
├── tests/
│   ├── __init__.py
│   ├── test_service.py    # 服务层测试
│   ├── test_cli.py        # CLI 测试
│   └── conftest.py        # 测试固件
├── specs/                 # speckit 功能规格
├── fixtures/              # 测试数据
├── .specify/              # speckit 管理元数据
└── .cursor/commands/      # speckit slash 命令
```

### Service 层

Service 层是模块的核心，所有业务逻辑集中于此。

**必须遵循的规则：**

```python
# ✅ 正确：纯同步，不依赖 GUI 框架
class MyModuleService:
    def __init__(self, adb: AdbManager, data_dir: str):
        self._adb = adb
        self._data_dir = data_dir

    def do_something(self, serial: str, on_progress=None):
        """纯同步方法，可选 on_progress 回调。"""
        self._notify(on_progress, "步骤 1...")
        result = self._adb.shell(serial, "some command")
        return result

# ❌ 错误：在 service 中导入 PyQt6
from PyQt6.QtWidgets import QMessageBox  # 禁止！
```

**进度回调签名**：`Callable[[str], None] | None`

### GUI 层

GUI Tab 继承 `BaseTab`，使用 `QThread` + `pyqtSignal` 执行耗时操作。

```python
from toolkit.gui.base_tab import BaseTab

class MyModuleTab(BaseTab):
    tab_title = "我的模块"
    tab_icon = "🔧"

    def __init__(self, context=None, parent=None):
        super().__init__(context, parent)
        # ⚠️ 使用模块前缀获取 context 值
        self._service = context.get("mm_service")  # mm_ 前缀
        self._adb = context.get("mm_adb")

    def on_devices_changed(self, devices):
        super().on_devices_changed(devices)
        # 根据设备连接状态启用/禁用按钮
```

**线程安全规则：**

```python
class _Worker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(object)
    progress = pyqtSignal(str)  # ✅ 通过 signal 传递进度

    def run(self):
        try:
            result = self._fn()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(e)

# ❌ 禁止在 QThread 中直接操作 UI
# ❌ 禁止在 QThread 中使用 QTimer.singleShot
```

### CLI 层

使用 Typer 注册子命令。

```python
import typer

my_app = typer.Typer(help="我的模块")

@my_app.command("info")
def info():
    """显示模块信息"""
    svc = _get_service()
    data = svc.get_info()
    # 使用 rich 格式化输出
```

### Plugin 注册

**关键：context 键名必须使用模块前缀！**

```python
from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin

class MyModulePlugin(BasePlugin):  # ⚠️ 必须继承 BasePlugin

    @hookimpl
    def on_startup(self, context: dict):
        self.context = context
        adb = context.get("adb_manager")

        # ✅ 使用模块前缀注册 context
        context["mm_adb"] = adb
        context["mm_service"] = MyModuleService(adb, data_dir)

        # ❌ 禁止使用通用键名
        # context["service"] = ...
        # context["adb"] = ...

    @hookimpl
    def register_gui_tab(self):
        from .gui_tab import MyModuleTab
        return MyModuleTab(self.context)  # 传递 context
```

### 测试

```powershell
# 运行所有测试（推荐）
python scripts/run_all_tests.py

# 只运行当前模块测试
.venv\Scripts\python.exe -m pytest modules/my_module/tests/ -v
```

**测试要求：**
- `service.py` 中每个公共方法至少一个测试用例
- 使用 `unittest.mock` 模拟 ADB 操作
- 测试数据放在 `fixtures/` 目录
- 新模块添加后在 `scripts/run_all_tests.py` 中注册

---

## Step 4 — 验收与提交

### 验收流程

1. 所有测试通过
2. `spec analysis` FAIL 项清零
3. GUI 界面验证（如有）
4. CLI 命令验证（如有）

### Bug 修复规则

**简单 Bug**（不涉及功能/需求变更）：

```
spec task + Bug 描述 → spec implement → spec analysis
```

**需求变更/设计调整**：

```
spec clarify → spec plan → spec task → spec analysis → spec implement → spec analysis
```

**Bug 修复方法论**（必须遵循）：

1. 分析根因（日志、代码追踪）
2. 记录诊断信息
3. 基于根因修复（禁止盲目尝试）
4. 验证修复
5. 更新文档

### 提交规范

```
<type>(<scope>): <description>

# type: feat, fix, refactor, docs, test, chore
# scope: 模块名或 core/sdk

# 示例
feat(log_analysis): 实现日志解析和关键字搜索功能
fix(game_perf): 修复推送时 stdout 为 None 导致的拼接错误
```

---

## 常见错误与避坑指南

完整清单见 `scripts/doc/development-pitfalls.md`，以下为最高频问题：

### 1. Context 键名冲突（严重度：致命）

```python
# ❌ 多个模块使用同一个键名会互相覆盖
context["service"] = MyService(...)

# ✅ 使用模块前缀
context["mm_service"] = MyService(...)
```

### 2. ADB 输出 None 保护

```python
# ❌ 可能报 TypeError
combined = result.stdout + result.stderr

# ✅ 加 or "" 保护
stdout = result.stdout or ""
stderr = result.stderr or ""
```

### 3. 插件必须继承 BasePlugin

```python
# ❌ 不会被 PluginManager 发现
class MyPlugin:
    pass

# ✅ 必须继承
class MyPlugin(BasePlugin):
    pass
```

### 4. pytest 跨模块冲突

不要从项目根直接运行 `pytest`，使用 `python scripts/run_all_tests.py`。

### 5. Windows 中文编码

脚本入口加：
```python
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
```

---

## 附录 — 命令速查

| 操作 | 命令 |
|------|------|
| 创建模块 | `python scripts/create_module.py <name>` |
| 运行所有测试 | `python scripts/run_all_tests.py` |
| 运行单模块测试 | `.venv\Scripts\python.exe -m pytest modules/<name>/tests/ -v` |
| 启动 GUI | `.venv\Scripts\python.exe -m toolkit.app` |
| CLI 帮助 | `.venv\Scripts\python.exe -m toolkit.app --help` |
| speckit specify | `/speckit.specify`（在 Cursor 中） |
| speckit clarify | `/speckit.clarify`（在 Cursor 中） |
| speckit plan | `/speckit.plan`（在 Cursor 中） |
| speckit tasks | `/speckit.tasks`（在 Cursor 中） |
| speckit analyze | `/speckit.analyze`（在 Cursor 中） |
| speckit implement | `/speckit.implement`（在 Cursor 中） |
| 安装依赖 | `uv pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple` |
