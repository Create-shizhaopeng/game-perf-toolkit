# LV Game Toolkit — 项目进度

## 目录

- [当前阶段](#当前阶段)
- [活跃工作](#活跃工作)
- [近期完成](#近期完成)
- [业务汇报](#业务汇报)

## 当前阶段

Android 性能分析工具集，插件化架构 7 模块就绪，核心功能可用。当前聚焦 Perfetto 分析的 LLM 集成优化和 FPS 采集鲁棒性。

**活跃模块**：perfetto_analysis、perfetto_capture

## 活跃工作

### R1: LLM 上下文优化（perfetto_analysis）

- ToolReturn 压缩机制已实现（≤300 token 摘要 + metadata 保留原始数据）
- 冗余工具已移除（11→9），SOP 场景映射补全（10 个场景）
- 待完成：graceful degradation（上下文溢出时部分完成报告）

### R5: FPS 采集鲁棒性（perfetto_capture）

- 待实现：SF latency 数据校验、Android 16 layer name regex、诊断日志

## 近期完成

### 2026-05-26（LLM Manager 模块重构：多 Provider 配置化 + 精简设置 + Thinking + Token 统计）

- 新建 `modules/llm_manager/` 独立模块：Provider 配置管理、Token 用量记录、插件化注册
- Provider 配置从硬编码（2 个）迁移到 `data/config/llm_providers.json`，支持多 Provider 自定义 API 地址/Key/模型列表
- 框架层 `LLMConfig` 从 9 字段精简到 2 字段（provider + model_name），移除 temperature/max_tokens/smart_switch/token_budget/budget_alert_threshold
- `LiteLLMProvider` 支持 `api_base`（自定义 URL）和 `thinking`（Anthropic extended thinking）参数
- `LLMManager` 精简：移除 smart_switch 降级逻辑、token_budget 预算告警、degradation_occurred 信号
- 设置面板精简为 Provider 下拉 + Model 下拉 + Thinking 开关 + Base URL/API Key 编辑 + 管理按钮
- 「管理 Provider」按钮改为直接打开 `llm_providers.json` 系统编辑器
- 状态栏上下文圆环改为单色填充 + hover tooltip，移除文字标签和颜色区分
- Token 用量后台 SQLite 记录（四维度：request/conversation/trace/total）
- Bug 修复：hookimpl 来源错误 → 插件钩子不触发（BUG-002）；ghostBtn 无颜色 → 按钮不可见；模型下拉不填充；QComboBox/QLineEdit 高度不一致

### 2026-05-25（日志面板 UI 重构：导出迁移 + 控制台 Tab 化 + 设置菜单扩展）

- 底部面板 header 移除「导出」按钮，迁移到右上角设置 → 日志 → 导出日志
- 设置菜单新增「日志」二级菜单（导出日志 / 历史日志 / 清空历史），SettingsButton 新增 3 个 pyqtSignal
- 「控制台」从独立 QPushButton checkable 改为 QTabBar tab，紧挨「全部」右侧，11px 统一字体
- 删除 `_show_console` / `_console_btn` / `_on_console_toggled`，源过滤逻辑简化
- header 清除按钮从 text+font 改为 `_cached_icon()` + `setIcon()` 方式，修复 QSS 覆盖导致图标不显示
- 底部面板新增 `export_logs` / `open_log_directory` / `clear_log_history` 公开方法
- MainWindow 新增 SettingsButton → BottomPanel 信号桥接

### 2026-05-25（历史面板架构重构：提取基类 + 统一数据源 + codicon 图标迁移）

- 提取 `BaseHistoryTreeWidget` 到 `toolkit/gui/widgets/` — 通用历史树基类，统一右键菜单、主题、搜索过滤、格式化工具、send_to_agent 信号
- 拆分 `history_panel.py`（~850行）为 `session_tree.py` 和 `analysis_tree.py`，各继承基类
- 删除未使用的覆盖式 `HistoryPanel`（~500行含动画、遮罩、双栏布局）
- 统一分析任务数据源：废弃 `pe_analysis_tasks`，以 `pa_analysis_tasks` 为权威表
- `PerfettoAnalysisService` 新增 `create_analysis_record` / `update_analysis_record` 写入方法，`get_analysis_history()` 归一化返回格式
- `gui_tab.py` 消除"创建 HistoryPanel → 拆出 widget → 重新挂载"反模式
- 历史面板所有 Unicode Emoji 迁移到 `assets/codicon.ttf` 字体图标，补充 22 个新 codicon 映射
- `app_paths.py` 新增 `get_output_dir()` 统一 dev/frozen 输出目录
- 测试：17+4 个已有测试通过，新增 11 个 BaseHistoryTreeWidget 测试

### 2026-05-20（Agent Tool Unification 重构：CLI → MCP Server + Skill）

- 全面移除 CLI 体系（移除 Typer/Rich 子命令、`cli_commands.py`、`test_cli.py`、`strings_cli.py`），以 MCP Server + Skill 替代
- 建立 MCP Server（FastMCP）与 Skill Registry（YAML frontmatter 标准化），框架层通过标准协议自动收集各模块工具
- `ToolkitDef` 统一，各模块通过 `register_agent_tools()` 返回 JSON Schema 工具定义、`register_skills()` 返回 SKILL.md 路径
- 以 `device_disguise` 为试点模块完成迁移验证
- 测试覆盖：150 个测试全部通过，含主项目、device_disguise 及各业务模块

### 2026-05-20（统一日志规范约束体系化）

- 统一日志体系规则写入 CLAUDE.md 与 .claude/rules/log-panel-rules.md：
  - 3 个场景的正确日志接口标准：Service/Engine 层用 `logging.getLogger()`、GUI Tab 层用 `self._log()`、结构化日志用 `UnifiedLogger.bind_module()`
  - 禁用 `print()` 输出诊断/错误/警告（保留 CLI 交互输出例外）
  - 日志级别语义与 GUI 面板行为对照表（debug/info/success/warning/error）
- `.cursor/rules/log-panel-rules.mdc` 与 `.claude/rules/log-panel-rules.md` 内容同步对齐
- `docs/knowledge/module-development-guide.md` 新增「日志输出规范」章节 + 「常见错误」条目 #6
- 7 个模块的 `print()` 已清理完毕，全部桥接到 `unified_logger` 统一路由

### 2026-05-20（字符串提取规范体系化与归档）

- 完成字符串提取规范的长期规则化：
  - CLAUDE.md「不可违反的硬规则」新增第 9 条：用户可见中文文本必须提取到 `strings_*.py`
  - 新建 `.claude/rules/string-extraction-gate.md`：明确提取范围、豁免范围、常量命名约定、导入方式、微调流程
  - 明确日志输出（`_log()`、`logger.debug()` 等）不需要提取，避免过度工程
- specs/019-hardcoded-string-extraction 归档：
  - 创建 `ARCHIVE.md` 记录完成交付物、已知遗留项、后续微调策略
  - `spec.md` 状态标记为 Archived
- 当前字符串提取模式已覆盖 7 个模块 + 框架层，后续按模块逐个微调即可

### 2026-05-20（硬编码中文字符串提取完成）

- 完成 5 个目标模块的硬编码字符串提取，统一提取到 `strings_gui.py` / `strings_service.py`（`strings_cli.py` 已随 CLI 移除）
  - perfetto_capture、agent_chat、perfetto_analysis、perfdog_insights、workspace_tools
- 完成 `toolkit/gui/` 框架层字符串提取，集中到 `toolkit/gui/strings.py`
  - 覆盖 main_window.py、home_tab.py、toolkit_dialog.py、llm_settings_dialog.py、base_tab.py、title_bar.py、llm_status_widget.py
- `Final[str]` 常量模式统一，功能前缀分组（BTN_、LABEL_、MSG_、DLG_TITLE_、CLI_HELP_ 等），格式模板使用 `_FMT` 后缀
- `scripts/check_hardcoded_strings.py` 确认：已迁移模块源码零中文硬编码残留（注释/文档字符串除外）
- 全量 pytest：
  - 主项目 tests/、device_disguise、perfetto_analysis（302 passed）、workspace_tools（15 passed）、game_perf（5 passed）通过
  - agent_chat（289 passed）、perfetto_capture（163 passed）通过
  - perfdog_insights 的 1 个失败为既有测试缺陷（CLI 子命令调用未传参），非迁移引入

### 2026-05-19（路径规范化重构）

- 新增 `toolkit/core/app_paths.py` 集中式路径工具，消除各模块重复的 `sys.frozen` 分支
- 所有 7 个模块迁移至新路径规范：
  - 配置文件：dev=`modules/<name>/config/<file>` → frozen=`data/config/<name>_<file>`（扁平命名）
  - 数据库：统一 `data/db/<module>_<db>.db`
  - 备份：统一 `data/backup/<module>/`
- 构建脚本更新为 `data/config/` 扁平目录结构，构建后自动生成带模块名前缀的配置文件

### 2026-04-09（长期记忆系统优化）

- 合并 7 个模块 constitution → AGENTS.md，AGENTS.md 成为统一权威约束源
- 删除 63 个模块级 Speckit 命令文件 + 84 个模板/脚本
- 为 7 个模块创建 specs/INDEX.md 状态索引
- 删除 doc/legacy/ 旧版文档归档
- 合并 doc/ + context/ → docs/ 统一文档目录
- context-engineering.mdc 添加大文档检索策略

### 2026-04-09（编译优化）

- 构建时间缩减 ~63%（双入口合并为单次构建 + PE header patching）
- 产物体积减少 ~55MB（排除 31 个无用依赖）
- 自动版本号管理（git tag → VERSION 文件 → 运行时读取）

### 2026-04-09（perfetto_analysis 架构审查）

- 修复 14 个问题（H1-H3, M1-M8, L1-L6）
- 分支清理（7 本地 + 4 远程废弃分支）
- analysis-architecture.md 文档全面对齐

## 业务汇报

向管理层汇报项目进度时，参见 [汇报流程](team/progress-reporting.md)。用户在会话中说"准备汇报"即可触发 Agent 协助生成飞书汇报文档。
