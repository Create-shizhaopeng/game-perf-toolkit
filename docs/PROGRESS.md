# LV Game Toolkit — 项目进度

## 目录

- [当前阶段](#当前阶段)
- [活跃工作](#活跃工作)
- [近期完成](#近期完成)
- [业务汇报](#业务汇报)

## 当前阶段

Android 性能分析工具集，插件化架构 7 模块就绪，核心功能可用。当前聚焦 Perfetto 分析的 LLM 集成优化和 FPS 采集鲁棒性。

**活跃模块**：agent、perfetto_analysis、perfetto_capture

## 活跃工作

### R6: Agent 核心重构（toolkit/agent）✅

- 目标：`modules/agent_chat/` → `toolkit/agent/`，Tool/Skill/MCP 基础设施下沉到 `toolkit/core/`
- 设计方案已落盘：[DES-001](design/DES-001-agent-core-refactor.md)，参考 Hermes Agent 开源架构
- 4 项设计决策已确认：SOP 合并到 Skill、SubAgent 暂不实现、Toolset 预留不分、Agent 不做独立窗口
- Speckit 流程全部完成，Phase 1-6 实现完毕（80/80 tasks）
- 217/217 测试通过，SC-004 (零反向依赖) + SC-006 (测试通过率) 达成 ✅

### R7: Hermes Agent 深度引入 — Agent 框架升级（toolkit/agent）

- 目标：在 DES-001 基础上，深度引入 Hermes 的对话循环鲁棒性 + 质量保障 + 知识库 + 记忆管理能力
- 设计方案已落盘：[DES-002](design/DES-002-hermes-agent-upgrade.md)（2026-06-02，draft）
- 核心差距分析完成：lv-game-toolkit 已有 6 项 Hermes 模式，缺失/薄弱 12 项
- 四阶段路线：Phase 1 韧性基础（ErrorClassifier/CircuitBreaker/Watchdog）→ Phase 2 质量保障（Verification/ContextCompressor）→ Phase 3 知识库（KnowledgeBase/Memory）→ Phase 4 SubAgent
- 2026-06-02: agent-wiring-fix 49/50 完成后，对照 DES-002 全量差距分析 — **确认 20 项新交付物全部待开始**，详见 DES-002 文档
- 待进入 Speckit 流程（建议先创建 `hermes-phase1-resilience` change）

### R1: LLM 上下文优化（perfetto_analysis）

- ToolReturn 压缩机制已实现（≤300 token 摘要 + metadata 保留原始数据）
- 冗余工具已移除（11→9），SOP 场景映射补全（10 个场景）
- 待完成：graceful degradation（上下文溢出时部分完成报告）

### R5: FPS 采集鲁棒性（perfetto_capture）

- 待实现：SF latency 数据校验、Android 16 layer name regex、诊断日志

## 近期完成

### 2026-06-02（agent-wiring-fix 收尾 + DES-002 差距分析）

- agent-wiring-fix: 49/50 任务完成。本会话完成剩余 13 项任务：
  - 10.1: SkillsManager.create_agent_tools() 委托到 build_skill_tools()
  - 4.6: AgentPanel drag-to-resize（240-480px clamp），RightPanel/AgentPanel 宽度解锁
  - 4.7: AgentPanel session selector（QComboBox + 新建按钮 + 会话切换/消息加载）
  - 11.3: 消除最后一条反向依赖 — builtin.py 迁移到 `toolkit/agent/builtin.py`
  - 10.2: 修复 test_no_executor_returns_error（GLMProvider mock → provider 注入）
  - 1.5/9.5/11.6: 全部测试套件通过（agent_skill_tools 10p + mcp_registry 8p + agent_chat 37p）
  - 11.1-11.7: 全量语法/导入/反向依赖/启动链路验证通过
  - 仅剩 11.8（需 LLM API Key 手动 GUI 验证）
- DES-002 vs agent-wiring-fix 差距分析：确认 **20 项新交付物未覆盖**（ErrorClassifier/CircuitBreaker/Watchdog/ConversationLoop/ContextCompressor/Verification/KnowledgeBase/MemoryManager/SubAgent 等）
- 启动链路验证: 7 plugins, 24 tools (13 plugin + 9 skill + 2 builtin), service created OK

### 2026-05-26（Hermes Agent 深度引入 — 框架升级设计）

- 深度分析 AI-Performance-Platform 项目中 Hermes Agent 的完整能力矩阵（107 agent + 97 tools + 571 skills）
- 对比 lv-game-toolkit 当前架构（DES-001 完成态）与 Hermes 全景能力，识别 6 项已有 / 6 项薄弱 / 12 项缺失
- 撰写 [DES-002](design/DES-002-hermes-agent-upgrade.md) 框架升级设计文档，涵盖：
  - 对话循环升级：朴素递归 → 状态机驱动的鲁棒编排（ErrorClassifier + CircuitBreaker + Watchdog + RetryPolicy）
  - 工具执行安全层：ToolGuardrail 三层检查（静态规则 / 动态规则 / 自定义规则）
  - 上下文管理升级：ContextCompressor（关键数字保留 + 摘要）+ MemoryManager（跨会话记忆）
  - 分析质量保障：Verification + Reflection + ConfidenceModel（五级置信度）+ PlanGate（分析计划门禁）
  - 知识库体系：从空壳 ReportIndex → 可检索 KnowledgeBase（TF-IDF 搜索 Skill + 案例 + SOP + Vendor）
  - SubAgent 启步 + 错误韧性全链路
- 四阶段实施路线：Phase 1 韧性基础（3-5 天）→ Phase 2 质量保障（3-5 天）→ Phase 3 知识库与记忆（5-7 天）→ Phase 4 SubAgent（5-7 天）

### 2026-05-26（Agent 核心重构实现 — 80 tasks）

- `modules/agent_chat/` → `toolkit/agent/`：Agent 从"聊天模块"提升为框架级核心引擎
- `ToolRegistry`/`ToolExecutor`/`MCP Framework` 提升到 `toolkit/core/`，消除循环依赖
- `SkillRegistry` 增强：合并 discovery 扫描 + 三级渐进加载 + 平台过滤
- Agent GUI 从中央 Tab 改为右侧可展开面板（AgentPanel），独占 RightPanel 内容区
- System Prompt 三段式重构（Stable/Context/Volatile），借鉴 Hermes Agent 设计
- SOP 系统合并到 Skill 体系；SubAgent 空实现移除；AgentConfig 废弃 LLM 字段清理
- `llm_manager` 统一管理 LLM Provider，Agent 不再自行创建
- MCP 统一前缀 `mcp__{server}__{tool}`，支持 local/external/remote 三种来源
- 217/217 测试通过（6 deprecated、2 SubAgent/LLM 文件删除）

### 2026-05-26（Agent 核心重构设计方案）

- 完成 Agent 核心架构重构设计文档 [DES-001](design/DES-001-agent-core-refactor.md)
- 确定重构方向：`modules/agent_chat/` → `toolkit/agent/` + Core 基础设施下沉
- 参考 Hermes Agent 架构：Registry Pattern、Progressive Disclosure、三段式 System Prompt
- 关键决策：模块 Tool 不再直接暴露，统一封装为 Skill 或 MCP Tool
- 确定三层架构：Core (注册中心) → Agent (编排引擎) → Modules (能力提供者)

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
