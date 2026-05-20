# Implementation Plan: Hardcoded String Extraction

**Branch**: `019-hardcoded-string-extraction` | **Date**: 2026-05-19 | **Spec**: [spec.md](specs/019-hardcoded-string-extraction/spec.md)

## Summary

将 5 个待迁移模块（perfetto_capture、agent_chat、perfetto_analysis、perfdog_insights、workspace_tools）和框架层（toolkit/gui/）中的硬编码中文字符串提取到 `strings_*.py` 文件中，同时更新源文件引用这些常量。采用 `Final[str]` 常量模式（与已迁移的 device_disguise/game_perf 一致），按功能前缀分组，并按需创建 strings_gui.py、strings_cli.py、strings_service.py。

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: PyQt6 (GUI)、Typer + Rich (CLI)、pluggy (插件系统)

**Storage**: N/A（纯代码重构，不涉及数据存储）

**Testing**: pytest（全量测试 + 自动化验证脚本）

**Target Platform**: Windows（GUI + CLI 双模式）

**Project Type**: Desktop application / CLI tool

**Performance Goals**: 无性能目标（纯静态常量提取，不引入运行时逻辑）

**Constraints**: 
- 迁移后 GUI 界面文案、CLI 帮助输出、Rich console 消息必须与迁移前完全一致
- GUI 和 CLI 的入口文件（gui_tab.py、cli_commands.py、service.py）功能行为不变
- 动态字符串使用 `.format()` 插值（不使用 f-string 存储，因为 strings.py 是常量文件）

**Scale/Scope**: 5 个模块 + 1 框架层，总计约 1040 行含中文文本（估算上限），预计涉及 30+ 文件

### 已有模式（device_disguise / game_perf）

已迁移模块采用以下模式，其余模块统一沿用：

```python
from typing import Final

TAB_TITLE: Final = "设备伪装"
LABEL_BRAND: Final = "品牌"
BTN_SAVE: Final = "保存"
MSG_CONFIRM_DELETE_FMT: Final = "确认删除档案 {}/{}/{}？"
LOG_ACTION_COMPLETE: Final = "✓ 操作完成"
```

关键约定：
- 使用 `Final[str]` 而非 `dict[str, str]`，支持 IDE 自动补全
- 常量按功能分组（按钮、标签、对话框、消息等），使用 section 分隔
- 带占位符的字符串以 `_FMT` 后缀命名
- 模块前缀：`BTN_`、`LABEL_`、`MSG_`、`LOG_`、`DLG_TITLE_` 等

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 检查项 | 状态 |
|------|--------|------|
| Library-First | strings_*.py 为纯数据文件，无副作用 | PASS |
| CLI Interface | CLI help 文本通过 strings_cli.py 注入 | PASS |
| Test-First | 每个模块迁移后运行测试验证 | PASS |
| 不修改 toolkit/ | 仅在各模块 src/ 下创建文件，不触碰核心框架 | PASS |
| 不引入新依赖 | 仅使用 Python 原生 Final 常量 | PASS |
| UTF-8 编码 | 所有文件 UTF-8 编码 | PASS |

无违规。

## Project Structure

### Documentation

```
specs/019-hardcoded-string-extraction/
├── plan.md          # 本文件
├── research.md      # Phase 0（已合并到 plan.md）
└── tasks.md         # Phase 2 输出
```

### Source Code

本次改动按模块分批进行：

```
modules/perfetto_capture/src/
├── strings_gui.py           # 新建 — GUI 文案
├── strings_cli.py           # 新建 — CLI 文案
├── strings_service.py       # 新建 — Service 文案
├── gui_tab.py               # 修改 — 引用 strings_gui
├── cli_commands.py          # 修改 — 引用 strings_cli
└── service.py               # 修改 — 引用 strings_service

modules/agent_chat/src/
├── strings_gui.py           # 新建
├── strings_service.py       # 新建
├── gui_tab.py               # 修改
└── service.py               # 修改

modules/perfetto_analysis/src/
├── strings_gui.py           # 新建
├── strings_cli.py           # 新建
├── strings_service.py       # 新建
├── gui_tab.py               # 修改
├── cli_commands.py          # 修改
└── service.py               # 修改

modules/perfdog_insights/src/
├── strings_gui.py           # 新建
├── strings_cli.py           # 新建
├── strings_service.py       # 新建
├── gui_tab.py               # 修改
├── cli_commands.py          # 修改
└── service.py               # 修改

modules/workspace_tools/src/
├── strings_gui.py           # 新建
├── strings_cli.py           # 新建
├── gui_tab.py               # 修改
└── cli_commands.py          # 修改

toolkit/gui/
├── strings.py               # 新建 — 框架层 GUI 文案
├── main_window.py           # 修改 — 引用 strings
├── toolkit_dialog.py        # 修改（如有中文）
└── ...                      # 其他含中文的 GUI 文件
```

**Structure Decision**: 单项目结构。每个模块在 `src/` 下创建 `strings_*.py`，修改对应入口文件引用这些常量。不涉及 contracts/ 或 quickstart.md（纯内部重构，无外部接口变更）。

## Implementation Approach

### 迁移顺序

按 spec 定义的优先级，从高到低：

1. **perfetto_capture** (~305 行含中文)
2. **agent_chat** (~271 行)
3. **perfetto_analysis** (~265 行)
4. **perfdog_insights** (~108 行)
5. **workspace_tools** (~91 行)
6. **toolkit/gui/** 框架层（所有模块完成后）

### 每个模块的迁移步骤

1. **识别中文硬编码**：扫描 gui_tab.py / cli_commands.py / service.py，列出所有中文字符串
2. **创建 strings_*.py**：按功能分组（BTN_、LABEL_、MSG_、DLG_TITLE_、LOG_ 等前缀），使用 `Final[str]`
3. **替换源文件引用**：将硬编码字符串替换为 `from .strings_gui import *` 等；CLI 的 `typer.Typer(help=...)` 字符串通过 `from .strings_cli import HELP_xxx` 在模块顶层静态导入，无需延迟加载
4. **动态字符串处理**：f-string 格式转为 `.format()` 模板
5. **运行测试验证**：确保功能行为和文案不变
6. **Lint 检查**：ruff check + ruff format

### 自动化验证脚本

创建 `scripts/check_hardcoded_strings.py`：
- 扫描所有模块 `src/` 下的 .py 文件
- 检测是否还有中文硬编码字符串（排除注释、import 语句、docstring）
- **检测规则**：使用 Unicode `一-鿿` 正则匹配汉字；逐行检查时若行以 `#` 开头或位于三引号 docstring 块内则跳过；排除 `strings_*.py` 文件自身以及顶层 `import`/`from` 语句行
- 输出遗漏的文件和行号
- 返回退出码 0/1 供 CI 使用

### 已迁移模块验证

对 device_disguise 和 game_perf：
- 运行 `ruff check` 确认无 lint 错误
- 确认 strings_*.py 中无遗漏未使用的常量
- 确认源文件中无残留中文硬编码

## Complexity Tracking

无需复杂度豁免 — 本次为纯字符串提取，不引入新架构模式。
