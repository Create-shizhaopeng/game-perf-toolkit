# 字符串提取门禁

## 范围与目的

本文档规范项目中用户可见中文文本的集中管理方式。目标是消除源码中的中文硬编码，使 UI 文本可统一查找、复用和后续国际化扩展。

## 提取范围（MUST 提取）

以下场景中的中文文本 **必须** 提取到常量文件：

| 场景 | 示例 |
|------|------|
| GUI 控件标签 / 标题 | `QPushButton("开始采集")`、`QGroupBox("设备信息")` |
| GUI 占位提示文字 | `QLineEdit.setPlaceholderText("输入包名...")` |
| GUI 对话框标题与正文 | `warning_dialog(self, "解析失败", message)` |
| HTML 报告中的中文标题 | `<h3>会话摘要</h3>` |
| 状态枚举显示值 | ComboBox 中的中文选项 `"中文"`、`"English"` |
| 模块 display_name | `get_plugin_info() 返回的 "Agent 智能助手"` |
| Plugin 工具 description | `@register_agent_tools` 返回工具列表中的 `description` |

## 豁免范围（不需要提取）

以下场景的中文文本 **不需要** 提取：

| 场景 | 说明 |
|------|------|
| **日志输出** | `logger.debug("开始解析")`、`self._log("设备已连接", level="info")` |
| **调试诊断字符串** | 临时调试 print、trace 标注如 `[DIAG]`、`[DEBUG]` |
| **HTML/报告内部的数据值** | 动态生成的数值描述如 `f"丢帧{jank}/{frames}帧"` |
| **Pydantic `Field(description=...)`** | 模型字段描述属于 schema 注解，不是用户可见文本 |
| **代码注释与文档字符串** | `# 解析配置`、`"""模块说明"""` |

## 文件结构

每个模块 **按需** 创建常量文件——没有对应场景则 **不需要** 创建空文件：

```
modules/<name>/src/
  strings_gui.py      # GUI 标签、按钮、对话框、占位文字（仅 GUI 模块需要）
  strings_service.py  # 服务层进度消息、错误消息（用户可见部分）
```

判断规则：
- **strings_gui.py**：仅当模块注册了 GUI Tab（`register_gui_tab()` 返回非 None）时创建
- **strings_service.py**：仅当服务层有用户可见的进度/错误消息时创建
- 无 GUI 或无服务层用户可见文本的模块，**不需要** 创建对应的空 strings 文件

框架层统一放在：

```
toolkit/gui/strings.py    # MainWindow、对话框、Tab 基类等框架 GUI 文本
```

## 常量命名约定

### 类型标注

所有常量 **必须** 使用 `Final` 或 `Final[str]`：

```python
from typing import Final

BTN_START: Final = "开始采集"   # ✅ 推荐
BTN_START: Final[str] = "开始采集"  # ✅ 也正确
```

### 功能前缀

常量名 **必须** 按功能前缀分组，推荐顺序：

| 前缀 | 含义 | 例子 |
|------|------|------|
| `TAB_` | Tab 标题 | `TAB_TITLE` |
| `GROUP_` | QGroupBox 标题 | `GROUP_TRACE_FILE` |
| `LABEL_` | QLabel 标签 | `LABEL_TARGET_PROCESS` |
| `PLACEHOLDER_` | 占位文字 | `PLACEHOLDER_CHAT_INPUT` |
| `BTN_` | QPushButton 文字 | `BTN_BROWSE`, `BTN_SEND` |
| `DLG_TITLE_` | 对话框标题 | `DLG_TITLE_PARSE_FAILED` |
| `DLG_MSG_` | 对话框正文 | `DLG_MSG_INVALID_FILE` |
| `MSG_` | 通用消息/提示 | `MSG_NO_DEVICES` |
| `PROGRESS_` | 进度提示 | `PROGRESS_PARSING` |
| `LOG_` | 用户可见日志消息 | `LOG_PUSH_SUCCESS` |
| `FILE_FILTER_` | 文件选择过滤器 | `FILE_FILTER_EXCEL` |
| `TABLE_` | CLI 表格标题/列名 | `TABLE_TITLE_DEVICE_INFO` |
| `WELCOME_` | 欢迎页元素 | `WELCOME_SHORTCUT_TRACE` |
| `REPORT_` | 报告区块标题 | `REPORT_SESSION_SUMMARY` |
| `CHUNK_` | 报告异常区块标签 | `CHUNK_WALL_CLOCK` |
| `MODE_ITEM_` | ComboBox 选项 | `MODE_ITEM_FULL` |

### 多行文本与 HTML

允许常量值为多行 HTML 字符串。HTML 标签中的中文仍然需要提取，但 `<code>`、`<b>` 等纯标签不需要拆开。示例：

```python
REPORT_UNMAPPED_NOTE_1: Final = (
    'PerfDog <code>Data_v4</code> 中含多类指标：<b>采样序号</b>（Num）、'
    '<b>多种时间戳</b>（time / absTime / monoTime）...'
)
```

### 格式模板

含运行时占位符的模板字符串 **必须** 使用 `_FMT` 后缀，使用 `.format()` 风格：

```python
RICH_PUSH_SUCCESS_FMT: Final = "推送完成，版本 {version}"
RICH_ERR_FMT: Final = "错误: {e}"
```

运行时调用：

```python
rprint(sc.RICH_PUSH_SUCCESS_FMT.format(version=version))
```

**禁止** 在 `strings_*.py` 中使用 f-string 替代 `.format()` 模板。

## 导入方式

模块内使用统一别名 `s`：

```python
# gui_tab.py / service.py
from . import strings_gui as s   # 或 strings_service
```

框架层使用：

```python
# toolkit/gui/*.py
from toolkit.gui import strings as s
```

## 检测与微调

### 单模块扫描

```bash
python scripts/check_hardcoded_strings.py
```

该脚本扫描所有 `modules/<name>/src/*.py` 和 `toolkit/gui/*.py`，排除 `strings_*.py`、注释、文档字符串和 import 行，输出仍含中文硬编码的文件与行号。

### 微调流程

发现遗漏后，**无需重新创建文件**，直接补漏到已有 `strings_*.py` 中：

1. 运行脚本确认受影响文件和行号
2. 新增常量到对应 `strings_*.py`，遵循前缀分组
3. 在源文件中替换为 `s.NEW_CONSTANT`
4. 再次运行脚本确认该行已清零

**不需要** 为微调创建新的 Speckit spec 或 PR，直接在对应模块的日常迭代中处理。

## 新建模块脚手架

`scripts/create_module.py` 会自动生成空的 `strings_gui.py`、`strings_service.py` 模板。开发者应在实现功能的同时填充常量，**禁止** 在代码审查通过后再补字符串提取。

## 禁止行为

- **禁止** 在 `service.py` 中 import `strings_gui.py`
- **禁止** 在 `gui_tab.py` 中 import `strings_service.py`
- **禁止** 在 `strings_*.py` 中出现业务逻辑、条件分支、函数定义
- **禁止** 日志/调试文本提取到 strings 文件
