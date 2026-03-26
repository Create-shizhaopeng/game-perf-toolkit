# Implementation Plan: Agent 智能助手模块

## 目录

- [技术上下文](#技术上下文)
- [Constitution 合规性](#constitution-合规性)
- [影响范围](#影响范围)
- [项目结构](#项目结构)
- [分阶段实施方案](#分阶段实施方案)
  - [Phase 0: 模块骨架与基础设施](#phase-0-模块骨架与基础设施)
  - [Phase 1: LLM Provider + 对话循环](#phase-1-llm-provider--对话循环)
  - [Phase 2: SOP Manager + 工具注册增强](#phase-2-sop-manager--工具注册增强)
  - [Phase 3: GUI Agent Tab](#phase-3-gui-agent-tab)
  - [Phase 4: 单项分析能力适配](#phase-4-单项分析能力适配)
  - [Phase 5: 工作流学习与沉淀](#phase-5-工作流学习与沉淀)
  - [Phase 6: 综合分析 SOP](#phase-6-综合分析-sop)
  - [Phase 7: 知识增强](#phase-7-知识增强)
  - [Phase 8: 测试与文档](#phase-8-测试与文档)
- [依赖安装](#依赖安装)
- [风险与缓解](#风险与缓解)

---

## 技术上下文

### 依赖项

| 依赖 | 版本 | 用途 | 安装方式 |
|------|------|------|---------|
| zhipuai | >=3.0.0 | GLM API SDK | 可选依赖，运行时 try-import |
| anthropic | >=0.40.0 | Claude API SDK | 可选依赖，运行时 try-import |
| PyYAML | >=6.0 | 解析 SOP frontmatter | 项目已有 |
| Pydantic | >=2.0 | 配置/数据模型 | 项目已有 |
| PyQt6 | 已有 | GUI Agent Tab | 项目已有 |
| Typer | 已有 | CLI | 项目已有 |
| pluggy | >=1.3 | 插件注册 | 项目已有 |

### 现有基础设施

| 组件 | 状态 | 说明 |
|------|------|------|
| `register_agent_tools` hookspec | ✅ 已定义 | 各模块已有初步工具注册 |
| `ServiceRegistry.get_service_schema()` | ✅ 已实现 | 从 Pydantic 类型自动生成 JSON Schema |
| GUI Agent Tab 预留位 | ✅ 已预留 | 架构文档 §8.1 |
| 各模块 Service 层 | ✅ 已实现 | 可直接被 Agent 调用 |
| SQLite 数据库框架 | ✅ 已实现 | 可复用连接管理和迁移模式 |

---

## Constitution 合规性

| 原则 | 合规状态 | 说明 |
|------|---------|------|
| I. Plugin-First | ✅ | `agent_chat` 作为独立模块，manifest.json 已创建 |
| II. Three-Surface Unity | ✅ | AgentService 为共享 Service，GUI/CLI/Agent 三端调用 |
| III. Agent-Driven Design | ✅ | 本模块即为 Agent 实现 |
| IV. Dependency Inversion | ✅ | 通过 hookspec 获取工具，不导入其他模块 src/ |
| V. Presentation Separation | ✅ | service.py 纯同步无 GUI 代码 |
| VI. Open-Closed | ✅ | 不修改 toolkit/core/ |
| VII. Spec-Driven | ✅ | 已完成 specify → clarify → UI 设计 |

### 特殊考量

- `agent_chat` 需要通过 `ServiceRegistry` 访问其他模块的工具列表，这是架构允许的（Constitution IV 允许导入 `toolkit.core.service_registry`）
- LLM SDK 为可选依赖，模块在无 SDK 时仍可加载（plugin 注册不报错），仅在使用 Agent 功能时检查

---

## 影响范围

| 范围 | 影响 | 详情 |
|------|------|------|
| `modules/agent_chat/` | 新增 | 完整新模块 |
| `modules/perfetto_analysis/src/plugin.py` | 修改 | 完善 `register_agent_tools` 返回的 JSON Schema |
| `modules/perfetto_analysis/src/models.py` | 修改 | 新增 `to_summary_dict()` |
| `modules/perfdog_insights/src/plugin.py` | 修改 | 新增 `register_agent_tools` 实现 |
| `modules/perfdog_insights/src/service.py` | 修改 | 新增 `summarize_report()` |
| `modules/game_perf/src/service.py` | 修改 | 新增 `analyze_config()` |
| `modules/game_perf/src/plugin.py` | 修改 | 新增 `gp_analyze_config` 工具 |
| `pyproject.toml` | 修改 | 添加可选依赖组 `[agent]` |

---

## 项目结构

```text
modules/agent_chat/
├── manifest.json
├── AGENTS.md
├── .specify/
│   ├── init-options.json
│   ├── memory/constitution.md
│   ├── templates/
│   └── scripts/
├── specs/001-agent-core/
│   ├── spec.md
│   ├── ui-design.md
│   ├── plan.md              ← 本文件
│   └── tasks.md
├── src/
│   ├── __init__.py
│   ├── plugin.py             # pluggy 注册入口（ac_ 前缀）
│   ├── service.py            # AgentService：对话循环核心
│   ├── models.py             # Pydantic：AgentConfig, Message, ToolCall 等
│   ├── cli_commands.py       # Typer CLI：agent ask / agent sop
│   ├── gui_tab.py            # PyQt6 Agent Tab（聊天 + 会话历史 + SOP 管理）
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py           # LLMProvider ABC + LLMResponse 类型
│   │   ├── claude_provider.py
│   │   └── glm_provider.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py       # ToolRegistry：收集 + Schema 增强
│   │   ├── executor.py       # ToolExecutor：安全执行 + 结果序列化
│   │   └── builtin.py        # 内置工具：create_workspace, list_files 等
│   ├── sop/
│   │   ├── __init__.py
│   │   └── manager.py        # SOPManager：加载/发现/匹配
│   └── memory/
│       ├── __init__.py
│       └── conversation.py   # ConversationStore：SQLite 持久化
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_service.py
│   ├── test_llm_provider.py
│   ├── test_tool_registry.py
│   ├── test_sop_manager.py
│   └── test_cli.py
├── assets/
│   ├── config.json           # 默认配置
│   └── sops/                 # 内置 SOP 文档
│       ├── trace_analysis.md
│       ├── perfdog_analysis.md
│       ├── strategy_review.md
│       └── jank_comprehensive.md
├── data/                     # 运行时数据（gitignored）
│   ├── config.json           # 用户配置（含 API Key）
│   ├── agent_chat.db         # 对话历史
│   ├── sops/                 # 用户自定义 SOP
│   └── agent_workspace/      # 分析工作目录
└── fixtures/                 # 测试数据
```

---

## 分阶段实施方案

### Phase 0: 模块骨架与基础设施

**目标**：完成模块注册、数据模型定义、配置管理

**技术要点**：
- `models.py`：定义 `AgentConfig`（Pydantic）、`Message`、`ToolDefinition`、`ToolCall`、`ToolResult`、`LLMResponse`、`SOPDocument`、`WorkflowTrace`、`Conversation`
- `plugin.py`：pluggy 注册，`on_startup` 存入 `ac_service` / `ac_config` 到 context
- `assets/config.json`：默认配置模板（provider=glm, model=glm-4-plus, temperature=0.3）
- API Key 三级策略：环境变量 → data/config.json → 空（触发 GUI 引导）

**产出**：模块可被 PluginManager 发现和加载

### Phase 1: LLM Provider + 对话循环

**目标**：实现 LLM 调用和对话循环核心逻辑

**技术要点**：
- `llm/base.py`：`LLMProvider` ABC，定义 `stream_chat()` 接口，返回 `Iterator[StreamChunk]`
- `llm/glm_provider.py`：`zhipuai` SDK 封装，`stream_chat()` 使用 `client.chat.completions.create(stream=True)`
  - tool_use 格式：OpenAI 兼容（`tools` 参数 + `function` type）
  - 流式 chunk 中 `delta.tool_calls` 需要累积合并
- `llm/claude_provider.py`：`anthropic` SDK 封装，`stream_chat()` 使用 `client.messages.stream()`
  - tool_use 格式：`input_schema` 字段，需在 Provider 内转换为统一格式
  - 流式 chunk 类型：`content_block_start` / `content_block_delta` / `content_block_stop`
- `service.py`：`AgentService.chat()` 对话循环
  - 接收用户消息 → 构建 messages + system prompt → 调用 `provider.stream_chat()`
  - 处理 tool_use → 调用 executor → 收集结果 → 继续循环
  - 直到 LLM 返回纯文本（无 tool_use）→ 结束
  - 自动重试：工具失败后重试 1 次（FR-015）
  - token 计数：从 LLM response 的 usage 字段提取
- 智能 Provider 切换（FR-013）：SOP 有 `recommended_provider` 时优先使用

**产出**：CLI `agent ask "你好"` 能收到 LLM 回复

### Phase 2: SOP Manager + 工具注册增强

**目标**：实现 SOP 加载/发现/匹配 + 工具 Schema 增强

**技术要点**：
- `sop/manager.py`：`SOPManager`
  - 加载 `assets/sops/` + `data/sops/` 下所有 `.md` 文件
  - 解析 YAML frontmatter（`title`, `keywords`, `description`, `recommended_provider`, `required_tools`）
  - `get_all_metadata()` → 返回所有 SOP 的摘要信息（供 system prompt 注入）
  - `get_sop_content(name)` → 返回完整 SOP 正文
  - 同名冲突时 `data/sops/` 优先于 `assets/sops/`
- `tools/registry.py`：`ToolRegistry`
  - 收集各模块 `register_agent_tools()` 返回的工具列表
  - 对缺少 `parameters` 的工具：通过 `inspect.signature()` + `get_type_hints()` 自动生成 JSON Schema
  - 对 Pydantic 参数类型：调用 `model_json_schema()` 自动嵌入
  - `get_definitions()` → 返回 LLM Function Calling 格式的工具列表
  - Claude/GLM 格式差异在 Provider 内适配，Registry 输出统一中间格式
- `tools/executor.py`：`ToolExecutor`
  - `execute(tool_call)` → 安全调用 method，捕获所有异常
  - dataclass 结果 → `dataclasses.asdict()` → JSON string
  - Pydantic 结果 → `model_dump(mode="json")` → JSON string
  - 结果超长截断（>2000 字符）
  - 提取 report_paths（从结果中识别报告路径）
- system prompt 构建：Constitution 摘要 + SOP 元数据列表 + 可用工具列表 + 语言指令

**产出**：Agent 能自动匹配 SOP 并调用工具

### Phase 3: GUI Agent Tab

**目标**：实现完整的聊天界面

**技术要点**：
- `gui_tab.py`：继承 `BaseTab`，左右分栏
  - 左侧面板（220px 固定宽度）：
    - 上半部分：会话历史（QListWidget，按日期分组）
    - 下半部分：SOP 管理（QTreeWidget，内置/自定义分组）
  - 右侧聊天区：
    - 顶部工具栏：模型指示器（可点击切换）+ 设置按钮
    - 消息区域（QScrollArea + QVBoxLayout）：
      - 用户消息：右对齐蓝色气泡
      - Agent 文本：左对齐透明背景，流式渲染
      - 工具调用卡片：可折叠 QFrame，状态标记 + 报告链接
      - 工作流概览：紫色左边框卡片
      - 学习提示：黄色左边框卡片
    - 输入区域：QTextEdit（自适应 1-5 行）+ 发送/停止按钮
  - 设置弹窗（QDialog + QTabWidget，三个 Tab）
- QThread 异步调用：
  - `_AgentWorker(QThread)`：运行 `service.chat()`，通过信号推送消息更新
  - 信号：`text_chunk(str)` / `tool_start(dict)` / `tool_end(dict)` / `finished(str)` / `error(str)`
  - 停止按钮：设置 `worker.cancelled` 标志 + 终止线程
- 对话持久化：
  - `memory/conversation.py`：`ConversationStore`
  - SQLite 表：`conversations`（id, title, sop_used, created_at, updated_at）、`messages`（id, conversation_id, role, content, tool_calls_json, report_paths_json, token_usage_json, created_at）
  - 线程安全：每个 worker 使用独立 sqlite3 连接
- Token 用量展示：每条 Agent 回复底部灰色小字

**产出**：GUI 中可进行完整对话（含工具调用可视化 + 历史管理）

### Phase 4: 单项分析能力适配

**目标**：完善三个分析模块的 Agent 工具注册和 SOP

**技术要点**：
- `perfetto_analysis`：
  - `plugin.py`：`register_agent_tools` 返回含完整 `parameters` JSON Schema 的 5 个工具
  - `models.py`：`AnalysisResult.to_summary_dict()` → 摘要 dict
  - `assets/sops/trace_analysis.md`：Trace 分析 SOP
- `perfdog_insights`：
  - `plugin.py`：新增 `register_agent_tools`，注册 `pdi_load_report` + `pdi_summarize`
  - `service.py`：新增 `summarize_report(report) -> dict`（FPS/Jank/内存/功耗摘要）
  - `assets/sops/perfdog_analysis.md`：PerfDog 分析 SOP
- `game_perf`：
  - `service.py`：新增 `analyze_config(xml_path) -> dict`（调用 GamePerfParser）
  - `plugin.py`：`register_agent_tools` 新增 `gp_analyze_config`
  - `assets/sops/strategy_review.md`：策略审查 SOP

**产出**：Agent 能独立完成三种单项分析

### Phase 5: 工作流学习与沉淀

**目标**：实现工作流记录、沉淀检测、SOP 生成

**技术要点**：
- `service.py` 扩展：`WorkflowTracker` 类
  - 每次工具调用时记录到 `WorkflowTrace`
  - 对话结束时调用 `check_workflow_deposit()`
  - 沉淀条件：(a) 未用 SOP 但调用 2+ 工具；(b) 用了 SOP 但步骤偏差
- SOP 自动生成：
  - 从 `WorkflowTrace` 生成 YAML frontmatter + 步骤 Markdown
  - 保存到 `data/sops/`
  - 文件名冲突时追加序号
- GUI 集成：学习提示卡片 + "保存/编辑/跳过"按钮

**产出**：完成分析后提示保存工作流

### Phase 6: 综合分析 SOP

**目标**：编写综合卡顿分析 SOP + 工作目录管理

**技术要点**：
- `assets/sops/jank_comprehensive.md`：编排 trace + PerfDog + 策略三项分析
- `tools/builtin.py`：`create_workspace` + `list_workspace_files`
  - 路径策略：开发 `data/agent_workspace/` / 打包 `<exe_dir>/output/agent_workspace/`
- SOP 内容：收集文件 → trace 分析 → PerfDog 分析 → 策略审查 → 交叉关联 → 报告 + 建议

**产出**：端到端综合卡顿分析

### Phase 7: 知识增强

**目标**：历史报告上下文注入

**技术要点**：
- 历史报告索引：从 `perfetto_analysis` 和 `perfdog_insights` 的 DB/文件系统中扫描已有报告
- 上下文注入：最近 N 份报告摘要放入 system prompt
- 后续可升级为 FTS5/向量检索

**产出**：Agent 分析时参考历史案例

### Phase 8: 测试与文档

**目标**：单元测试 + 文档更新

**技术要点**：
- 测试覆盖：models、service（mock LLM）、tool_registry、sop_manager、CLI
- 文档更新：README、architecture-overview.md、development-pitfalls.md

**产出**：全量测试通过 + 文档同步

---

## 依赖安装

```bash
# GLM SDK（国内源）
pip install zhipuai -i https://mirrors.aliyun.com/pypi/simple/

# Claude SDK（需外网）
pip install anthropic -i https://mirrors.aliyun.com/pypi/simple/

# PyYAML（项目可能已有）
pip install pyyaml -i https://mirrors.aliyun.com/pypi/simple/
```

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| GLM Function Calling 不够准确 | 工具调用参数错误 | SOP 中明确参数格式；executor 做参数校验；自动重试 |
| LLM SDK 版本更新导致 API 变化 | 运行时错误 | 固定 SDK 最低版本；Provider 封装隔离变化 |
| 流式输出 + QThread 竞态 | GUI 闪退 | 遵循 P05（pyqtSignal）、P21（延迟刷新） |
| 超长 system prompt 超过模型上下文窗口 | SOP + 工具列表太大 | 动态裁剪：仅注入匹配的 SOP 正文，工具列表按需过滤 |
| 打包后 LLM SDK 缺失 | EXE 启动报错 | 运行时 try-import，缺失时 GUI 提示安装 |
| SQLite 跨线程访问 | 数据库锁死 | 遵循 P20：每个 worker 独立连接 |
