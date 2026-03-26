# Task List: Agent 智能助手模块

## 目录

- [Phase 0: 模块骨架与基础设施](#phase-0-模块骨架与基础设施)
- [Phase 1: LLM Provider + 对话循环](#phase-1-llm-provider--对话循环)
- [Phase 2: SOP Manager + 工具注册增强](#phase-2-sop-manager--工具注册增强)
- [Phase 3: GUI Agent Tab](#phase-3-gui-agent-tab)
- [Phase 4: 单项分析能力适配](#phase-4-单项分析能力适配)
- [Phase 5: 工作流学习与沉淀](#phase-5-工作流学习与沉淀)
- [Phase 6: 综合分析 SOP + 工作目录](#phase-6-综合分析-sop--工作目录)
- [Phase 7: 知识增强](#phase-7-知识增强)
- [Phase 8: 测试与文档](#phase-8-测试与文档)
- [FR 可追溯矩阵](#fr-可追溯矩阵)

---

## Phase 0: 模块骨架与基础设施

**目标**：模块可被 PluginManager 发现和加载，数据模型就绪

- [ ] **T001**: 创建 `src/__init__.py` — 空包文件
- [ ] **T002**: 创建 `src/models.py` — 定义所有 Pydantic/dataclass 数据模型（FR-012）
  - `AgentConfig(BaseModel)`：provider, api_key, model_name, max_tokens, temperature, sop_dir, language, smart_switch, max_conversations, max_context_messages, tool_result_max_length, workflow_learning_enabled
  - `Message`：role(user/assistant/tool), content, tool_calls, report_paths, token_usage, created_at
  - `ToolDefinition`：name, description, parameters(JSON Schema dict), method(Callable)
  - `ToolCall`：id, name, arguments(dict), status(pending/running/complete/failed), elapsed_ms
  - `ToolResult`：tool_call_id, content(str), is_error(bool), report_paths(list)
  - `LLMResponse`：text, tool_calls(list), usage(dict), model, provider
  - `SOPDocument`：path, title, keywords, description, recommended_provider, required_tools, content, source(builtin/custom)
  - `WorkflowTrace`：tool_calls(有序列表), user_decisions, sop_deviation
  - `Conversation`：id, title, sop_used, workflow_trace, created_at, updated_at
  - `StreamChunk`：type(text/tool_start/tool_end/error), data(str/dict)
- [ ] **T003**: 创建 `assets/config.json` — 默认配置模板（FR-012）
  - provider: "glm", model_name: "glm-4-plus", temperature: 0.3, language: "zh", smart_switch: true
- [ ] **T004**: 创建 `src/plugin.py` — pluggy 注册入口（FR-001）
  - `ac_` context key 前缀
  - `on_startup`：加载配置、初始化 AgentService、存入 context（`ac_service`, `ac_config`）
  - `register_gui_tab`：返回 AgentTab 类
  - `register_cli`：返回 Typer app
  - API Key 三级策略加载逻辑（C-001）：环境变量 → data/config.json → 空
- [ ] **T005**: 创建 `src/cli_commands.py` — Typer CLI 骨架（FR-011a）
  - `agent ask "<message>"` 命令（--sop, --provider 参数）
  - `agent sop list` / `agent sop show <name>` 子命令
  - 此阶段仅实现骨架和参数解析，实际调用在后续 Phase 补全
- [ ] **T006**: 创建 `memory/__init__.py`, `memory/conversation.py` — 对话存储骨架（FR-010a）
  - `ConversationStore` 类
  - SQLite 表设计：`conversations`(id, title, sop_used, created_at, updated_at), `messages`(id, conversation_id, role, content, tool_calls_json, report_paths_json, token_usage_json, created_at)
  - 方法骨架：`create_conversation()`, `save_message()`, `load_conversation()`, `list_conversations()`, `delete_conversation()`, `rename_conversation()`
- [ ] **T007**: 创建 `data/` 目录结构
  - `data/config.json`（首次运行时从 assets/config.json 复制）
  - `data/agent_chat.db`（运行时创建）
  - `data/sops/`（用户自定义 SOP 目录）
  - `data/agent_workspace/`（分析工作目录）
  - 确保 `data/` 在 `.gitignore` 中

- [ ] **T007b**: 更新 `pyproject.toml` — 添加可选依赖组 `[agent]`
  - `zhipuai>=3.0.0`, `anthropic>=0.40.0`
  - 安装方式：`pip install -e ".[agent]"`

**Checkpoint**: `python -c "from modules.agent_chat.src import plugin"` 无 ImportError

---

## Phase 1: LLM Provider + 对话循环

**目标**：CLI `agent ask "你好"` 能收到 LLM 回复

- [ ] **T008**: 创建 `llm/__init__.py`, `llm/base.py` — LLM Provider 抽象基类（FR-002）
  - `LLMProvider` ABC
  - `stream_chat(messages, tools, system_prompt) -> Iterator[StreamChunk]` 接口
  - `count_tokens(messages) -> int` 可选方法
  - `get_available_models() -> list[str]` 预设模型列表
- [ ] **T009**: 创建 `llm/glm_provider.py` — GLM Provider 实现（FR-002, FR-003）
  - `zhipuai` SDK 封装（运行时 try-import）
  - `stream_chat()` 实现：`client.chat.completions.create(stream=True)`
  - 工具定义格式转换：中间格式 → OpenAI 兼容 `tools` 参数
  - 流式 chunk 累积：`delta.tool_calls` 需要跨 chunk 合并
  - token usage 从 response 的最后一个 chunk 提取
  - 预设模型：glm-4-plus, glm-4-flash, glm-4-long
- [ ] **T010**: 创建 `llm/claude_provider.py` — Claude Provider 实现（FR-002, FR-003）
  - `anthropic` SDK 封装（运行时 try-import）
  - `stream_chat()` 实现：`client.messages.stream()`
  - 工具定义格式转换：中间格式 → Claude `input_schema` 格式
  - 流式 chunk 类型处理：`content_block_start` / `content_block_delta` / `content_block_stop`
  - token usage 从 `message_stop` 事件提取
  - 预设模型：claude-sonnet-4-20250514, claude-3-5-haiku-20241022
- [ ] **T011**: 创建 `src/service.py` — AgentService 对话循环核心（FR-006）
  - `AgentService.__init__(config, tool_registry, sop_manager, conversation_store)`
  - `chat(user_message, conversation_id, on_chunk) -> LLMResponse`
    - 构建 system prompt（Constitution 摘要 + SOP 元数据 + 工具列表 + 语言指令）
    - 调用 `provider.stream_chat()`，通过 `on_chunk` 回调传递流式数据
    - 处理 tool_use → 调用 executor → 收集结果 → 继续循环
    - 直到 LLM 返回纯文本 → 结束
  - `_build_system_prompt()` — 拼装 system prompt
  - `_handle_tool_calls(tool_calls) -> list[ToolResult]`
  - 自动重试逻辑：工具失败后重试 1 次（FR-015）
  - token 计数：从 LLMResponse.usage 提取
  - 智能 Provider 切换：检查 SOP 的 `recommended_provider`（FR-013）
  - 上下文溢出处理：messages 超长时截断早期历史，保留 SOP + 最近 3 轮工具结果 + 最近 5 轮用户消息（Edge Case）
  - LLM 网络异常/API 错误：捕获 `TimeoutError`/`APIError` 等，返回 `StreamChunk(type="error")` 而非崩溃（Edge Case）
- [ ] **T012**: 连接 CLI `agent ask` 命令到 AgentService（FR-011a）
  - `cli_commands.py` 的 `ask` 命令调用 `AgentService.chat()`
  - 终端以流式方式输出 Agent 回复（rich console）
  - 工具调用显示为 `[🔧 calling: tool_name] ... [✓ done]` 格式

**Checkpoint**: `python -m toolkit.main agent ask "你好"` 能收到 LLM 回复

---

## Phase 2: SOP Manager + 工具注册增强

**目标**：Agent 能自动匹配 SOP 并调用工具

- [ ] **T013**: 创建 `sop/__init__.py`, `sop/manager.py` — SOPManager（FR-007, FR-008）
  - `SOPManager.__init__(builtin_dir, custom_dir)`
  - `load_all() -> list[SOPDocument]`：加载 `assets/sops/` + `data/sops/` 下所有 `.md`
  - `_parse_frontmatter(content) -> dict`：解析 YAML frontmatter（FR-011b）
  - `get_all_metadata() -> list[dict]`：返回所有 SOP 的摘要（供 system prompt 注入）
  - `get_sop_content(name) -> str`：返回完整 SOP 正文
  - `import_sop(path) -> SOPDocument`：导入外部 SOP 到 `data/sops/`
  - `delete_sop(name)`：仅删除 custom SOP
  - `export_sop(name, target_path)`：导出 SOP
  - 同名冲突时 `data/sops/` 优先于 `assets/sops/`（FR-155）
- [ ] **T014**: 创建 `tools/__init__.py`, `tools/registry.py` — ToolRegistry（FR-004, FR-005）
  - `ToolRegistry.__init__(plugin_manager)`
  - `collect_tools()`：调用各模块 `register_agent_tools()` 收集工具列表
  - `_enhance_schema(tool) -> ToolDefinition`：对缺少 `parameters` 的工具通过 `inspect.signature()` + `get_type_hints()` 自动生成 JSON Schema
  - `_pydantic_to_schema(type_hint)`：Pydantic 类型 → `model_json_schema()`
  - `get_definitions() -> list[dict]`：返回 LLM Function Calling 中间格式
  - `get_tool(name) -> ToolDefinition`：按名称查找工具
- [ ] **T015**: 创建 `tools/executor.py` — ToolExecutor（FR-004）
  - `ToolExecutor.__init__(registry)`
  - `execute(tool_call) -> ToolResult`
    - 根据 name 查找 ToolDefinition.method
    - 安全调用：try/except 全捕获
    - 结果序列化：dataclass → `asdict()` → JSON；Pydantic → `model_dump(mode="json")` → JSON；其他 → str()
    - 结果截断：超过 `tool_result_max_length`（默认 2000）时截断并附加文件路径
    - 提取 report_paths：从结果中识别报告路径
    - 计时：`elapsed_ms`
- [ ] **T016**: 更新 `src/service.py` — 集成 SOPManager 和 ToolRegistry
  - `_build_system_prompt()` 注入 SOP 元数据列表
  - SOP 自动发现：LLM 在 system prompt 中看到所有 SOP 元数据，根据用户意图选择
  - 渐进式披露：SOP 步骤作为上下文指导 LLM 逐步引导（FR-009）
  - 无 SOP 可用时：Agent 仍正常工作（自由对话 + 工具调用），不按预置流程执行（Edge Case）
- [ ] **T017**: 连接 CLI `agent sop` 子命令到 SOPManager
  - `sop list`：列出所有 SOP（名称、来源、关键词）
  - `sop show <name>`：显示 SOP 完整内容

**Checkpoint**: `python -m toolkit.main agent ask "分析这个trace" --sop trace_analysis` 能按 SOP 流程调用工具

---

## Phase 3: GUI Agent Tab

**目标**：GUI 中可进行完整对话

### 3.1 基础聊天界面

- [ ] **T018**: 创建 `src/gui_tab.py` — AgentTab 基础框架（FR-010, C-003）
  - 继承 `BaseTab`
  - 左右分栏布局（QSplitter）：左 220px 固定 / 右侧自适应
  - 左侧面板骨架（QVBoxLayout）：会话历史区域 + SOP 管理区域
  - 右侧聊天区骨架：顶部工具栏 + 消息列表 + 输入区域
  - 顶部工具栏：模型名称 Label（可点击弹出设置）+ ⚙ 设置按钮
  - 欢迎页面：无对话时显示快捷入口按钮

### 3.2 消息区域

- [ ] **T019**: 实现消息渲染组件（FR-010）
  - 消息区域：QScrollArea + QVBoxLayout
  - 用户消息 Widget：右对齐蓝色气泡
  - Agent 文本 Widget：左对齐，支持流式追加文本
  - 工具调用卡片 Widget：可折叠 QFrame
    - 状态标记：⏳ 执行中 / ✅ 完成 / ❌ 失败
    - 参数摘要（折叠区域）
    - 结果摘要（折叠区域）
    - "📂 打开报告目录"按钮 + "📋 查看报告"链接（FR-010d）
  - 工作流概览卡片：紫色左边框（SOP 检测到时显示）
  - 自动滚动到底部

### 3.3 输入区域 + 异步执行

- [ ] **T020**: 实现输入区域和异步 Worker（FR-010, C-004, C-011）
  - QTextEdit（自适应高度 1-5 行）
  - Enter 发送 / Shift+Enter 换行
  - 发送按钮 → 执行中变为红色"停止"按钮（C-011）
  - 文件拖拽支持（显示文件路径）
  - `_AgentWorker(QThread)`：调用 `AgentService.chat()`
    - 信号：`text_chunk(str)`, `tool_start(dict)`, `tool_end(dict)`, `finished(str)`, `error(str)`
    - `cancelled` 标志位 + 停止逻辑（C-011）
    - error 信号处理：网络异常时显示重试按钮，不清空输入框内容（Edge Case）
    - 窗口关闭事件（`closeEvent`）：若 worker 活跃，持久化当前对话状态后再退出（Edge Case）
  - Token 用量显示：每条 Agent 回复底部灰色小字（FR-010g, C-014）

### 3.4 会话历史管理

- [ ] **T021**: 实现左侧会话历史面板（FR-010a, FR-010e, C-009）
  - QListWidget，按日期分组（今天/昨天/更早）
  - 会话标题：首条消息前 20 字截断
  - 高亮当前会话
  - "➕ 新建对话"按钮
  - 点击切换：加载历史消息到聊天区
  - 右键菜单：重命名 / 删除
  - 多会话支持：同一时刻只有一个会话活跃执行

### 3.5 SOP 管理面板

- [ ] **T022**: 实现左侧 SOP 管理面板（FR-010c）
  - QTreeWidget：内置 SOP / 自定义 SOP 分组
  - 每个 SOP 显示：名称 + 来源标记
  - 双击 SOP：调用 `os.startfile()` 打开编辑（C-008）
  - "导入"按钮：文件对话框选择 `.md` 文件
  - "管理"按钮：打开设置弹窗的 SOP 管理 Tab

### 3.6 设置弹窗

- [ ] **T023**: 实现设置弹窗（FR-010c, FR-012, C-001, C-012, C-013）
  - QDialog + QTabWidget（三个 Tab）
  - Tab 1 — 模型配置：
    - Provider 选择（GLM / Claude）
    - API Key 输入（密码模式 + 显示/隐藏切换）
    - 模型选择（QComboBox：预设 + 可编辑输入，C-012）
    - Temperature 滑块
    - 智能切换开关（C-002）
    - 回复语言选择（C-013）
  - Tab 2 — SOP 管理：
    - SOP 表格（名称、来源、状态、操作）
    - 操作：编辑（os.startfile）/ 删除（仅 custom）
    - 导入 / 导出按钮
  - Tab 3 — 高级设置：
    - 最大保留会话数
    - 最大上下文消息数
    - 工具结果最大长度
    - 工作流学习开关

### 3.7 对话持久化集成

- [ ] **T024**: 完善 `memory/conversation.py` 并集成到 GUI（FR-010a, FR-010b）
  - 实现 T006 中定义的所有方法
  - 线程安全：每个 QThread worker 使用独立 sqlite3 连接
  - 报告路径持久化：在 `messages` 表的 `report_paths_json` 字段中存储
  - 历史会话中的报告链接验证（报告已删除时显示灰色提示）
  - 对话切换时保存当前对话状态

**Checkpoint**: GUI Agent Tab 完整可用——可对话、可查看历史、可管理 SOP、可配置设置

---

## Phase 4: 单项分析能力适配

**目标**：Agent 能独立完成三种单项分析

### 4.1 Perfetto Analysis 适配

- [ ] **T025**: 更新 `modules/perfetto_analysis/src/plugin.py` — 完善 `register_agent_tools`（FR-100）
  - 返回含完整 `parameters` JSON Schema 的工具定义
  - 工具列表：`pa_analyze`（完整分析）, `pa_parse`（仅 Phase 1）, `pa_dimensions`（按维度分析）, `pa_report`（导出报告）, `pa_history`（查询历史）
- [ ] **T026**: 更新 `modules/perfetto_analysis/src/models.py` — 新增 `to_summary_dict()`（FR-101）
  - `AnalysisResult.to_summary_dict() -> dict`
  - 返回：frame_count, jank_count, jank_ratio, per_dimension_issues（各维度 top 问题摘要）, report_path
- [ ] **T027**: 编写 `modules/agent_chat/assets/sops/trace_analysis.md` — Trace 分析 SOP（FR-102）
  - YAML frontmatter：title, keywords([trace, 丢帧, perfetto, 卡顿]), description, recommended_provider(glm), required_tools([pa_analyze])
  - 步骤：1. 询问 trace 文件路径 → 2. 确认分析参数 → 3. 调用 pa_analyze → 4. 解读结果 → 5. 给出结论和建议

### 4.2 PerfDog Insights 适配

- [ ] **T028**: 更新 `modules/perfdog_insights/src/plugin.py` — 实现 `register_agent_tools`（FR-110）
  - 注册 `pdi_load_report` 和 `pdi_summarize` 工具
  - 含完整 `parameters` JSON Schema
- [ ] **T029**: 更新 `modules/perfdog_insights/src/service.py` — 新增 `summarize_report()`（FR-111）
  - `summarize_report(report) -> dict`
  - 返回：fps_stats(avg/min/max/p1), jank_rate, memory_peak, power_avg, key_bottlenecks
- [ ] **T030**: 编写 `modules/agent_chat/assets/sops/perfdog_analysis.md` — PerfDog 分析 SOP（FR-112）
  - YAML frontmatter：title, keywords([perfdog, fps, jank, 内存, 功耗]), description, recommended_provider(glm), required_tools([pdi_load_report, pdi_summarize])
  - 步骤：1. 询问 xlsx 文件路径 → 2. 加载报告 → 3. 汇总分析 → 4. 解读关键指标 → 5. 给出优化建议

### 4.3 Game Perf 适配

- [ ] **T031**: 更新 `modules/game_perf/src/service.py` — 新增 `analyze_config()`（FR-120）
  - `analyze_config(xml_path) -> dict`
  - 调用 `GamePerfParser` 解析 XML
  - 返回：cpu_clusters(频点配置), gpu_freq, supported_games, scene_policies, thermal_strategy
- [ ] **T032**: 更新 `modules/game_perf/src/plugin.py` — 新增 `register_agent_tools`（FR-122）
  - 注册 `gp_analyze_config` 工具
  - 含完整 `parameters` JSON Schema
- [ ] **T033**: 编写 `modules/agent_chat/assets/sops/strategy_review.md` — 策略审查 SOP（FR-123）
  - YAML frontmatter：title, keywords([策略, 配置, gameperfconfig, CPU, GPU]), description, recommended_provider(glm), required_tools([gp_analyze_config])
  - 步骤：1. 询问 XML 文件路径 → 2. 解析配置 → 3. 展示当前策略概览 → 4. 分析合理性 → 5. 给出调整建议

**Checkpoint**: Agent 能分别完成 trace 分析、PerfDog 分析、策略审查三个单项分析

---

## Phase 5: 工作流学习与沉淀

**目标**：完成分析后提示保存工作流

- [ ] **T034**: 扩展 `src/service.py` — WorkflowTracker 类（FR-150, FR-151）
  - `WorkflowTracker`：在对话过程中记录工具调用序列
  - 记录内容：tool_name, arguments, result_summary, user_decision_points, timestamp
  - `check_deposit_condition() -> bool`：检测是否满足沉淀条件
    - 条件 a：未使用预置 SOP 但调用了 2+ 工具
    - 条件 b：使用了 SOP 但步骤有偏差（调用了 SOP 未列出的工具，或跳过了列出的工具）
- [ ] **T035**: 实现 SOP 自动生成（FR-152, FR-153, FR-154）
  - `generate_sop_from_trace(workflow_trace) -> str`：从 WorkflowTrace 生成 Markdown
    - 自动生成 YAML frontmatter（title, keywords 从工具名提取, description 从对话摘要生成）
    - 步骤描述从工具调用序列和用户交互生成
  - 保存到 `data/sops/` 目录
  - 文件名冲突时追加序号（如 `trace_analysis_2.md`）
  - 调用 `os.startfile()` 打开生成的文件供用户编辑（C-008）
- [ ] **T036**: GUI 集成工作流学习（FR-152）
  - 对话结束时显示黄色"💡 工作流沉淀"卡片
  - 卡片内容：工作流摘要 + "保存为新 SOP" / "更新现有 SOP" / "跳过"按钮
  - 保存后 SOP 自动注册到 SOPManager

**Checkpoint**: 完成非 SOP 分析后，Agent 提示保存工作流

---

## Phase 6: 综合分析 SOP + 工作目录

**目标**：端到端综合卡顿分析

- [ ] **T037**: 创建 `tools/builtin.py` — 内置工具（FR-202）
  - `create_workspace(name) -> str`：创建分析工作目录
    - 开发环境：`modules/agent_chat/data/agent_workspace/<name>_<timestamp>/`
    - 打包后：`<exe_dir>/output/agent_workspace/<name>_<timestamp>/`
  - `list_workspace_files(workspace_path) -> list[str]`：列出工作目录下的文件
  - 注册为 Agent 工具（在 ToolRegistry 中自动收集）
- [ ] **T038**: 编写 `modules/agent_chat/assets/sops/jank_comprehensive.md` — 综合卡顿分析 SOP（FR-200）
  - YAML frontmatter：title, keywords([卡顿, 综合分析, trace, perfdog, 策略]), description, recommended_provider(claude), required_tools([pa_analyze, pdi_load_report, pdi_summarize, gp_analyze_config, create_workspace])
  - 步骤编排：
    1. 创建分析工作目录
    2. 收集三份文件（trace / PerfDog xlsx / gameperfconfig.xml）
    3. 执行 Trace 分析 → 提取丢帧原因
    4. 执行 PerfDog 分析 → 提取性能指标
    5. 执行策略审查 → 提取当前策略
    6. 交叉关联：丢帧原因 × PerfDog 指标 × 策略配置
    7. 输出综合报告（FR-203）：问题列表 + 原因归因 + 新旧策略对比 + 调整理由
- [ ] **T039**: 连接 `create_workspace` / `list_workspace_files` 到 ToolRegistry
  - 在 `plugin.py` 中通过 `register_agent_tools` 注册内置工具
  - 含完整 JSON Schema

**Checkpoint**: Agent 能按综合 SOP 依次执行三项分析并交叉关联

---

## Phase 7: 知识增强

**目标**：Agent 分析时参考历史案例

- [ ] **T040**: 实现历史报告索引（FR-300）
  - 扫描 `perfetto_analysis` 和 `perfdog_insights` 的输出目录
  - 提取每份报告的摘要信息（文件名、分析时间、关键指标）
  - 最近 N 份报告摘要注入 system prompt
- [ ] **T041**: system prompt 上下文管理优化（FR-300）
  - 当 system prompt 超过模型上下文窗口的 30% 时，动态裁剪：
    - 仅注入 LLM 匹配到的 SOP 正文（而非全部 SOP）
    - 历史报告按相关性排序后取 top 5
    - 工具列表按 SOP 的 `required_tools` 过滤

**Checkpoint**: 新分析时 Agent 能引用历史案例

---

## Phase 8: 测试与文档

**目标**：全量测试通过 + 文档同步

### 8.1 单元测试

- [ ] **T042**: [P] 创建 `tests/test_models.py` — 数据模型测试
  - AgentConfig 默认值、序列化/反序列化
  - Message 各 role 类型
  - SOPDocument frontmatter 解析
- [ ] **T043**: [P] 创建 `tests/test_llm_provider.py` — LLM Provider 测试（mock SDK）
  - GLM Provider：mock zhipuai SDK，验证 stream_chat 流式输出
  - Claude Provider：mock anthropic SDK，验证 stream_chat 流式输出
  - 工具定义格式转换验证
- [ ] **T044**: [P] 创建 `tests/test_tool_registry.py` — 工具注册测试
  - `collect_tools()` 收集工具
  - `_enhance_schema()` 自动 Schema 生成
  - `get_definitions()` 格式正确性
- [ ] **T045**: [P] 创建 `tests/test_sop_manager.py` — SOP Manager 测试
  - 加载 builtin + custom SOP
  - frontmatter 解析
  - 同名冲突优先级
  - 导入/删除/导出
- [ ] **T046**: [P] 创建 `tests/test_service.py` — AgentService 测试（mock LLM）
  - 对话循环：mock LLM 返回文本 → 验证结果
  - 工具调用：mock LLM 返回 tool_use → executor 执行 → 反馈 → LLM 再回复
  - 自动重试逻辑
  - 智能 Provider 切换
- [ ] **T047**: [P] 创建 `tests/test_conversation_store.py` — 对话存储测试
  - CRUD 操作
  - 报告路径持久化
  - 并发安全（多线程测试）
- [ ] **T048**: [P] 创建 `tests/test_agent_cli.py` — CLI 测试
  - `agent ask` 命令解析
  - `agent sop list` / `agent sop show` 输出格式
  - mock AgentService

### 8.2 文档更新

- [ ] **T049**: [P] 更新 `scripts/doc/architecture-overview.md` — 新增 agent_chat 模块说明
- [ ] **T050**: [P] 更新 `scripts/doc/development-pitfalls.md` — 记录开发中遇到的陷阱
- [ ] **T051**: [P] 更新 `scripts/build.py` — 打包配置（可选依赖处理）
  - zhipuai / anthropic 作为可选依赖的打包策略
  - SOP 文件和 assets 的打包包含

**Checkpoint**: 全量测试通过，文档同步完成

---

## FR 可追溯矩阵

| FR | Tasks | Phase |
|----|-------|-------|
| FR-001 | T004 | 0 |
| FR-002 | T008, T009, T010 | 1 |
| FR-003 | T009, T010 | 1 |
| FR-004 | T014, T015 | 2 |
| FR-005 | T014 | 2 |
| FR-006 | T011 | 1 |
| FR-007 | T013 | 2 |
| FR-008 | T013 | 2 |
| FR-009 | T016 | 2 |
| FR-010 | T018, T019, T020 | 3 |
| FR-010a | T006, T021, T024 | 0, 3 |
| FR-010b | T024 | 3 |
| FR-010c | T022, T023 | 3 |
| FR-010d | T019 | 3 |
| FR-010e | T021 | 3 |
| FR-010f | T020 | 3 |
| FR-010g | T020 | 3 |
| FR-011a | T005, T012 | 0, 1 |
| FR-011b | T013 | 2 |
| FR-012 | T002, T003, T007b, T023 | 0, 3 |
| FR-013 | T011 | 1 |
| FR-014 | T011 | 1 |
| FR-015 | T011 | 1 |
| FR-100 | T025 | 4 |
| FR-101 | T026 | 4 |
| FR-102 | T027 | 4 |
| FR-110 | T028 | 4 |
| FR-111 | T029 | 4 |
| FR-112 | T030 | 4 |
| FR-120 | T031 | 4 |
| FR-121 | T031 | 4 |
| FR-122 | T032 | 4 |
| FR-123 | T033 | 4 |
| FR-150 | T034 | 5 |
| FR-151 | T034 | 5 |
| FR-152 | T035, T036 | 5 |
| FR-153 | T035 | 5 |
| FR-154 | T035 | 5 |
| FR-155 | T013 | 2 |
| FR-200 | T038 | 6 |
| FR-201 | T037 | 6 |
| FR-202 | T037, T039 | 6 |
| FR-203 | T038 | 6 |
| FR-300 | T040, T041 | 7 |
| FR-301 | — | 后续版本 |
| FR-302 | T035 | 5 |

---

## 依赖与执行顺序

### Phase 依赖关系

```text
Phase 0 (骨架)
  └─→ Phase 1 (LLM + 对话)
        └─→ Phase 2 (SOP + 工具)
              ├─→ Phase 3 (GUI)           ← 可与 Phase 4 并行
              └─→ Phase 4 (单项分析适配)   ← 可与 Phase 3 并行
                    └─→ Phase 5 (工作流学习)
                          └─→ Phase 6 (综合分析)
                                └─→ Phase 7 (知识增强)
Phase 8 (测试文档) ← 贯穿全过程，每个 Phase 完成后补充
```

### 并行机会

- **Phase 3 与 Phase 4**：GUI 开发和模块适配可并行（不同文件，无依赖）
- **Phase 4 内部**：三个模块适配（4.1 / 4.2 / 4.3）可并行
- **Phase 8 测试**：所有测试文件标记 [P] 可并行编写
- **T009 与 T010**：两个 LLM Provider 可并行开发

### 推荐实施策略（单人）

1. Phase 0 → Phase 1 → Phase 2：建立核心对话能力（约 3-4 天）
2. Phase 4.1（trace 适配）→ Phase 3 基础 GUI：验证端到端流程（约 3 天）
3. Phase 4.2 + 4.3 + Phase 3 完善：补全分析能力和 GUI（约 2-3 天）
4. Phase 5 → Phase 6：学习和综合分析（约 2-3 天）
5. Phase 7 + Phase 8：知识增强和测试收尾（约 2 天）

**预估总工期**：12-15 个工作日

---

## Spec Phase → Plan Phase 映射

| Spec 需求阶段 | Plan 实施阶段 | 说明 |
|--------------|-------------|------|
| Phase 0: Agent 基础设施 (FR-001~015) | Phase 0 + 1 + 2 + 3 | 基础设施按实施关系拆分为四个实施阶段 |
| Phase 1: 单项分析能力 (FR-100~130) | Phase 4 | 三个模块分别适配 |
| Phase 1.5: 工作流学习 (FR-150~155) | Phase 5 | 独立实施阶段 |
| Phase 2: 综合分析能力 (FR-200~203) | Phase 6 | 依赖 Phase 4 的单项能力 |
| Phase 3: 知识增强 (FR-300~302) | Phase 7 | 最后实施 |

---

## Success Criteria 验证

| SC | 验证方式 | 对应 Task |
|----|---------|-----------|
| SC-001: 首次响应 < 5s | Phase 1 完成后手动计时验证 | T011, T012 |
| SC-002: SOP 匹配率 > 90% | Phase 2 完成后用预置 SOP 场景测试 | T016, T046 |
| SC-003: 单项分析端到端 | Phase 4 Checkpoint | T025-T033 |
| SC-004: 综合报告三要素 | Phase 6 Checkpoint | T038 |
| SC-005: API 失败不崩溃 | T046 mock 异常测试 | T011, T046 |
| SC-006: 沉淀 SOP 可被发现 | Phase 5 Checkpoint | T034-T036, T045 |
| SC-007: 历史报告链接可用 | Phase 3 Checkpoint | T024, T047 |
