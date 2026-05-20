# Spec 归档说明：019-hardcoded-string-extraction

## 归档日期

2026-05-20

## 归档原因

- 5 个目标模块（perfetto_capture、agent_chat、perfetto_analysis、perfdog_insights、workspace_tools）及框架层（toolkit/gui/）的字符串提取已完成
- 提取规范已升级为项目长期规则，写入 [CLAUDE.md](../../CLAUDE.md) 开发规范和 [.claude/rules/string-extraction-gate.md](../../.claude/rules/string-extraction-gate.md)
- 部分模块存在遗漏（perfdog_insights/gui_tab.py HTML 报告内中文、perfetto_analysis/gui_tab.py 大量 HTML 标题、agent_chat/gui_tab.py 等），后续按模块逐个微调
- 当前源码中日志/调试输出被过度提取，后续微调时按新规则剔除（日志输出不进入 strings_*.py）

## 已完成交付物

| 模块 | strings_gui.py | strings_cli.py | strings_service.py | 源文件更新 |
|------|---------------|----------------|-------------------|-----------|
| perfetto_capture | ✅ | ✅ | ✅ | gui_tab.py, cli_commands.py, service.py |
| agent_chat | ✅ | ✅ | ✅ | gui_tab.py, cli_commands.py, service.py |
| perfetto_analysis | ✅ | ✅ | ✅ | gui_tab.py, cli_commands.py, service.py |
| perfdog_insights | ✅ | ✅ | ✅ | gui_tab.py, cli_commands.py, service.py |
| workspace_tools | ✅ | ✅ | ✅ | gui_tab.py, cli_commands.py, service.py, plugin.py |
| toolkit/gui/ | strings.py（集中） | — | — | main_window.py, home_tab.py, toolkit_dialog.py, llm_settings_dialog.py, base_tab.py, title_bar.py, llm_status_widget.py |

## 已知遗留项

- perfdog_insights `gui_tab.py` `_render_report` 中 HTML 报告中文（`<h3>会话摘要</h3>` 等）
- perfetto_analysis `gui_tab.py` `_build_report` / `_render_info_panel` 中大量 HTML 中文
- agent_chat `gui_tab.py` `addItems(["中文", "English"])` 及 `f"工具: {...}"` 等
- agent_chat `cli_commands.py` `f"用户指定 SOP: {sop}"`
- 各模块 strings_*.py 中混入了日志输出常量（如 `LOG_` 前缀常量实际是 `_log()` 调用），后续微调剔除

## 后续微调策略

1. 按模块运行 `python scripts/check_hardcoded_strings.py`
2. 将遗漏的用户可见中文字符串补充到已有 `strings_*.py`
3. 从 `strings_*.py` 中删除日志/调试相关的常量，恢复为源码中的 f-string 或 `_log()` 直接调用
4. 直接在对应模块的日常迭代中处理，无需创建新的 Spec

## 规范参考

- CLAUDE.md 第 9 条硬规则
- `.claude/rules/string-extraction-gate.md`
- `scripts/check_hardcoded_strings.py`
