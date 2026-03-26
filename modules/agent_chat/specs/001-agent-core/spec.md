# Feature Specification: Agent 智能助手模块

**Feature Branch**: `001-agent-core`
**Created**: 2026-03-25
**Status**: Draft
**Input**: 在工具箱内置 AI Agent，通过 SOP 驱动的工作流自动编排模块工具，完成游戏性能分析任务。

## 目录

- [Clarifications](#clarifications)
- [设计背景](#设计背景)
- [User Scenarios & Testing](#user-scenarios--testing)
  - [US-1 SOP 自动发现与渐进式披露](#us-1-sop-自动发现与渐进式披露-priority-p1)
  - [US-2 Trace 分析](#us-2-trace-分析-priority-p1)
  - [US-3 PerfDog 数据分析](#us-3-perfdog-数据分析-priority-p2)
  - [US-4 策略配置审查](#us-4-策略配置审查-priority-p2)
  - [US-5 综合卡顿分析](#us-5-综合卡顿分析-priority-p3)
  - [US-6 工作流学习与沉淀](#us-6-工作流学习与沉淀-priority-p2)
  - [US-7 历史知识增强](#us-7-历史知识增强-priority-p3)
  - [Edge Cases](#edge-cases)
- [Requirements](#requirements)
  - [Phase 0: Agent 基础设施](#phase-0-agent-基础设施fr-001--fr-015)
  - [Phase 1: 单项分析能力](#phase-1-单项分析能力fr-100--fr-130)
  - [Phase 1.5: 工作流学习与沉淀](#phase-15-工作流学习与沉淀fr-150--fr-155)
  - [Phase 2: 综合分析能力](#phase-2-综合分析能力fr-200--fr-203)
  - [Phase 3: 知识增强](#phase-3-知识增强fr-300--fr-302)
- [Key Entities](#key-entities)
- [架构决策](#架构决策)
- [LLM Provider 技术选型](#llm-provider-技术选型)
- [Success Criteria](#success-criteria)

---

## Clarifications

### Session 2026-03-25

- **C-001**: API Key 管理方式？ → **三级策略**：(1) 首次无 Key 时 GUI 弹窗提示用户配置；(2) 主窗口设置页可随时修改；(3) 环境变量（`ANTHROPIC_API_KEY` / `ZHIPUAI_API_KEY`）作为兜底，有环境变量时自动读取。优先级：环境变量 > data/config.json。
- **C-002**: 默认 LLM Provider？ → **GLM 作为默认**（国内网络稳定、成本低）。同时实现**智能切换**：根据场景复杂度和可用 Key 自动选择——简单工具调用用 GLM，复杂综合分析（如 US-5）且有 Claude Key 时自动切换 Claude。SOP 中标注推荐 Provider。
- **C-003**: Agent Tab 位置？ → **第一个 Tab（最左侧）**，与架构文档 §8.1 预留设计一致。
- **C-004**: 流式输出？ → **直接实现流式输出**（打字机效果）。工具调用部分仍为同步等待，流式仅用于 Agent 文本回复。额外工作量约 0.5-1 天。GUI 通过 pyqtSignal 逐步更新消息，不阻塞 UI。
- **C-005**: 模型差异影响？ → SOP 越详细则模型差异越小。单项分析（US-2/3/4）差异不大；综合分析（US-5）受模型推理能力影响最大。GLM 默认配合详细 SOP 可满足大部分场景。
- **C-006**: SOP 发现机制？ → **Agent 自动匹配**。每个 SOP 文件包含 YAML frontmatter（title、keywords、description），所有 SOP 元数据注入 LLM system prompt，由 LLM 根据用户输入语义匹配最合适的 SOP。用户无需手动从下拉框选择。
- **C-007**: 工作流学习机制？ → **对话结束时主动提示**。Agent 记录工具调用序列，检测到新工作流或 SOP 偏差时，询问用户是否保存。保存后生成 Markdown SOP 到 `data/sops/`，后续可被自动发现和使用。实现人+AI 双向提升闭环。
- **C-008**: SOP 编辑方式？ → **用系统默认编辑器打开 .md 文件**。工作流沉淀时 Agent 生成 SOP 文件后，调用 `os.startfile()` 打开供用户编辑。设置面板中的"编辑"按钮同理。不内嵌编辑器。
- **C-009**: 是否支持多并行会话？ → **支持多会话**。用户可同时开多个分析对话，切换查看。左侧面板列出所有会话，点击切换。同一时刻只有一个会话在活跃执行 LLM/工具调用。
- **C-010**: 分析工作目录？ → **默认自动创建 + 用户可覆盖**。开发环境：`modules/agent_chat/data/agent_workspace/<内容>_<时间戳>/`；打包后：`<exe_dir>/output/agent_workspace/<内容>_<时间戳>/`。用户可在对话中指定自定义目录。
- **C-011**: 停止按钮行为？ → **立即取消**。取消当前工具执行 + 停止 LLM 调用 + 清空工作区域。提示用户"工作已结束，工作区已清空"。已产生的部分结果不保留。
- **C-012**: 模型列表管理？ → **用户输入模型名 + 预设常用 + 选择记忆**。根据用户已配置的 Provider 预设常用模型，同时支持手动输入任意模型名。用户选择后记忆到 config，下次启动自动使用。
- **C-013**: Agent 回复语言？ → **默认中文**，可在设置中切换。system prompt 中注入语言指令。
- **C-014**: Token 用量展示？ → **作为额外插件功能**。每次回复后显示本次 token 用量（input/output），会话总量，和费用预估（按模型单价计算）。作为 Phase 0 的可选增强。
- **C-015**: 工具重试策略？ → **自动重试 1 次**，仍失败则报告用户并询问是否再次重试。

---

## 设计背景

### 现有架构预留

项目在设计之初已预留 Agent 集成接口（ADR-009, Constitution III）：

- `register_agent_tools` hookspec 已定义，`game_perf`、`device_disguise`、`perfetto_analysis` 已有初步工具注册
- `ServiceRegistry` 已实现 `get_service_schema()` 自动从 Pydantic 类型生成 JSON Schema
- 三端统一 Service 层使 Agent 可调用与 GUI/CLI 完全相同的 API
- GUI 主窗口预留 Agent Tab 位

### 核心使用场景

用户输入一句话（如"分析当前游戏的卡顿问题"），Agent 自主完成：
1. 根据预置或用户导入的 SOP 文档编排工作流
2. 创建分析工作目录，引导用户提供所需文件
3. 自动调用工具分析（trace 分析、PerfDog 分析、策略配置解读）
4. 汇总分析结果：问题描述、问题原因、新策略参数建议及调整理由

### 用户群体

仅开发团队（熟悉技术细节，能看原始数据），可访问外网。

---

## User Scenarios & Testing

### US-1 SOP 自动发现与渐进式披露 (Priority: P1)

用户输入自然语言任务描述，Agent 自动匹配最合适的 SOP 并加载执行，无需手动选择。Agent 根据 SOP 步骤渐进式向用户索要所需文件和信息，而非一次性要求全部输入。

**Why this priority**: 这是区别于简单对话的核心差异化能力，决定了 Agent 是否真正"智能"。

**Independent Test**: 输入"帮我分析下游戏的卡顿"，Agent 自动识别匹配"Trace 分析 SOP"并开始引导。

**Acceptance Scenarios**:

1. **Given** 多个 SOP 已注册，**When** 用户输入"分析这个 trace 的卡顿问题"，**Then** Agent 自动匹配 `trace_analysis` SOP 并开始按步骤执行
2. **Given** 用户输入模糊描述"看看性能有没有问题"，**When** 多个 SOP 都可能匹配，**Then** Agent 列出候选 SOP 供用户选择（渐进式披露）
3. **Given** SOP 需要 trace 文件但用户未提供，**When** Agent 开始执行 SOP，**Then** Agent 主动询问"请提供 trace 文件路径"
4. **Given** 用户直接提供了所有必要信息，**When** Agent 识别到全部输入就绪，**Then** 跳过已满足的步骤直接执行
5. **Given** API Key 未配置，**When** 尝试对话，**Then** 显示配置引导提示

---

### US-2 Trace 分析 (Priority: P1)

用户提供 Perfetto trace 文件路径，Agent 按 SOP 自动执行 trace 分析并给出结论。

**Why this priority**: Trace 分析是最常用的单项分析，验证 SOP 驱动工作流的核心能力。

**Independent Test**: 提供 trace 文件路径，Agent 调用 `pa_analyze`，返回丢帧数、原因分析和报告位置。

**Acceptance Scenarios**:

1. **Given** 有效的 trace 文件，**When** 输入"分析这个 trace: /path/to/file.trace"，**Then** Agent 调用 `pa_analyze`，展示丢帧数、帧数、各维度问题摘要
2. **Given** 无效文件路径，**When** 输入分析命令，**Then** Agent 友好提示文件不存在
3. **Given** SOP 已加载，**When** 分析完成，**Then** Agent 按 SOP 定义的输出格式呈现结果

---

### US-3 PerfDog 数据分析 (Priority: P2)

用户提供 PerfDog 导出的 xlsx 文件，Agent 加载并分析性能数据。

**Why this priority**: PerfDog 是团队常用的第三方性能采集工具，数据分析是高频需求。

**Independent Test**: 提供 PerfDog xlsx 路径，Agent 返回 FPS、Jank 率、内存等关键指标摘要。

**Acceptance Scenarios**:

1. **Given** 有效的 PerfDog xlsx，**When** 输入分析命令，**Then** Agent 调用 `pdi_load_report` 并展示关键指标
2. **Given** 同时有策略配置，**When** 用户提供 policy_dict，**Then** Agent 执行联合分析

---

### US-4 策略配置审查 (Priority: P2)

用户提供 gameperfconfig.xml，Agent 解析并展示当前策略参数配置。

**Why this priority**: 策略参数是综合分析中产出"新策略建议"的基础。

**Independent Test**: 提供 XML 文件路径，Agent 返回结构化的频点、温控、模式配置摘要。

**Acceptance Scenarios**:

1. **Given** 有效的 gameperfconfig.xml，**When** 输入审查命令，**Then** Agent 调用 `gp_analyze_config` 展示 CPU/GPU 频点、场景策略列表
2. **Given** XML 格式错误，**Then** Agent 报告具体的 XML 解析错误

---

### US-5 综合卡顿分析 (Priority: P3)

用户提供 trace + PerfDog + 策略配置三份数据，Agent 按综合 SOP 进行交叉分析，输出完整报告和策略调整建议。

**Why this priority**: 这是最终目标场景，依赖 US-2/3/4 的单项能力。

**Independent Test**: 提供三份文件，Agent 依次调用三个分析工具，交叉关联结果，输出综合报告。

**Acceptance Scenarios**:

1. **Given** 三份分析文件已就绪，**When** 输入"综合分析卡顿问题"，**Then** Agent 按 SOP 依次执行三项分析
2. **Then** 输出包含：问题列表、原因归因、新策略参数建议、调整理由
3. **Then** 建议参数与当前参数形成对比表格

---

### US-6 工作流学习与沉淀 (Priority: P2)

当用户在对话中创建了新的分析流程（工具调用序列与判断逻辑），或对已有 SOP 做了变更时，Agent 主动提示用户是否保存为新 SOP 或更新现有 SOP，实现人+AI 双向提升。

**Why this priority**: 这是 Agent 从"工具"进化为"知识载体"的关键能力，影响长期价值。

**Independent Test**: 完成一轮非 SOP 驱动的分析后，Agent 提示"是否保存为新的工作流？"

**Acceptance Scenarios**:

1. **Given** 用户通过自由对话完成了一组分析（未使用预置 SOP），**When** 对话结束或用户说"完成"，**Then** Agent 生成工作流摘要并询问"是否保存为新 SOP？"
2. **Given** 用户在 SOP 驱动分析中跳过或修改了某些步骤，**When** 分析完成，**Then** Agent 提示"您的操作与原 SOP 有差异，是否更新 SOP？"
3. **Given** 用户确认保存，**When** Agent 生成 SOP Markdown，**Then** 用户可预览编辑后保存到 `data/sops/` 目录
4. **Given** 用户拒绝保存，**Then** 不做任何 SOP 变更

---

### US-7 历史知识增强 (Priority: P3)

Agent 在分析时参考历史分析报告，识别相似案例，辅助判断和建议。

**Why this priority**: 知识积累是长期价值，但不影响基础分析能力。

**Independent Test**: 已有历史报告的情况下，新分析时 Agent 提及"类似案例"作为参考。

**Acceptance Scenarios**:

1. **Given** 有 10+ 历史报告，**When** 新分析完成，**Then** Agent 检索相似历史案例并引用
2. **Given** 无历史报告，**When** 分析完成，**Then** Agent 正常输出，不受影响

---

### Edge Cases

- **LLM 网络异常**：API 超时或服务不可用时显示超时提示 + 重试按钮，不丢失已输入内容
- **API Key 无效/额度用尽**：明确错误提示，引导用户检查或更换 Key
- **工具调用失败**：Agent 报告工具错误（如 ADB 断连），不进入死循环；最多重试 1 次后交由用户决定
- **上下文溢出**：超长对话自动截断早期历史，保留 SOP + 最近 3 轮工具结果 + 最近 5 轮用户消息
- **工具返回超大结果**：截断为摘要（前 2000 字符），提供完整结果的文件路径
- **历史报告已删除**：对话中的报告链接显示"报告文件已不存在"灰色提示，不崩溃
- **SOP 文件外部修改/删除**：SOP Manager 每次加载时从磁盘重新读取，删除的 SOP 自动从列表移除
- **工作流沉淀 SOP 重名**：保存时自动在文件名后追加序号（如 `trace_analysis_2.md`）
- **长时间工具执行期间关闭窗口**：对话状态持久化到 DB，下次打开可查看部分结果
- **无任何 SOP 可用**：Agent 仍可自由对话和调用工具，只是不按预置流程执行

---

## Requirements

### Phase 0: Agent 基础设施（FR-001 ~ FR-015）

- **FR-001**: 模块 MUST 以 `agent_chat` 名称注册，context 前缀 `ac_`，CLI 命名空间 `agent`
- **FR-002**: MUST 实现 LLM Provider 抽象层，支持 Claude（Anthropic API）和 GLM（智谱 API）两个后端；GLM 为默认 Provider（C-002）
- **FR-003**: LLM Provider MUST 支持流式调用（C-004），Agent 文本回复以打字机效果逐步展示；工具调用部分为同步等待
- **FR-004**: MUST 实现增强版 ToolRegistry，将各模块 `register_agent_tools()` 返回的工具转化为 LLM Function Calling 格式（JSON Schema）
- **FR-005**: 对于工具定义中缺少 `parameters` 字段的，ToolRegistry MUST 通过 `inspect.signature()` + `get_type_hints()` 自动生成 JSON Schema
- **FR-006**: MUST 实现对话循环核心：接收用户消息 → 调用 LLM → 处理 tool_use 响应 → 执行工具 → 反馈结果 → 循环直到 LLM 返回最终文本
- **FR-007**: MUST 实现 SOP Manager：加载、发现、匹配 SOP 文档。每个 SOP 包含 YAML frontmatter 元数据（title、keywords、description、recommended_provider），正文为 Markdown 操作步骤
- **FR-008**: MUST 实现 SOP 自动发现（C-006）：用户输入后，将所有 SOP 元数据注入 system prompt，由 LLM 根据用户意图选择最匹配的 SOP；多个候选时列出供用户选择
- **FR-009**: MUST 实现渐进式披露：Agent 按 SOP 步骤逐步向用户索要输入，已提供的信息直接使用，缺失的信息主动询问
- **FR-010**: MUST 提供 GUI Agent Tab（聊天界面）：左侧面板（会话历史 + SOP 管理）+ 右侧聊天区（消息列表 + 工具调用卡片 + 报告链接）+ 输入区域 + 设置弹窗
- **FR-010a**: MUST 实现对话历史持久化（SQLite `agent_chat.db`），支持跨会话查看和继续对话。左侧面板按日期分组展示历史会话。
- **FR-010b**: 分析工具产生的报告路径 MUST 持久化在对话记录中，支持从历史会话中点击"打开报告"和"打开目录"
- **FR-010c**: 设置弹窗 MUST 包含三个 Tab：模型配置、SOP 管理（查看/编辑/删除/导入/导出）、高级设置
- **FR-010d**: 工具完成卡片 MUST 包含"打开报告目录"按钮（调用 `os.startfile`）和"查看报告"链接；历史会话中这些操作仍可用
- **FR-010e**: 左侧会话历史面板 MUST 支持：新建对话、点击切换查看历史、右键重命名/删除。支持多会话并存（C-009），同一时刻只有一个活跃执行
- **FR-010f**: 停止按钮 MUST 立即取消当前工具执行 + LLM 调用 + 清空工作区域，提示用户"工作已结束"（C-011）
- **FR-010g**: SHOULD 在每次 Agent 回复后显示 token 用量（input/output）和费用预估（C-014），作为可选增强
- **FR-011a**: MUST 提供 CLI 命令 `agent ask "<message>"`，支持 `--sop <name>` 参数
- **FR-011b**: SOP 文档格式 MUST 为 Markdown + YAML frontmatter，frontmatter 包含：`title`（标题）、`keywords`（关键词列表）、`description`（场景描述）、`recommended_provider`（推荐 LLM，可选）、`required_tools`（依赖的工具名列表，可选）。示例：

```yaml
---
title: Trace 丢帧分析
keywords: [trace, 丢帧, perfetto, 卡顿]
description: 从 Perfetto trace 文件中检测丢帧事件并分析原因
recommended_provider: glm
required_tools: [pa_analyze]
---
```

- **FR-012**: AgentConfig MUST 为 Pydantic 模型，包含：api_key、provider（claude/glm）、model_name、max_tokens、temperature、sop_dir、language 等字段。API Key 支持三级策略（C-001）：环境变量 > config.json > GUI 弹窗引导。模型选择支持用户手动输入 + 预设常用 + 选择记忆（C-012）
- **FR-013**: MUST 实现智能 Provider 切换逻辑（C-002）：根据场景复杂度和可用 Key 自动选择 Provider，SOP 中可通过 `recommended_provider` 字段标注推荐模型
- **FR-014**: Agent 回复语言默认中文，可在设置中切换（C-013）。system prompt 中注入语言指令
- **FR-015**: 工具调用失败时自动重试 1 次，仍失败则报告用户并询问是否重试（C-015）

### Phase 1: 单项分析能力（FR-100 ~ FR-130）

- **FR-100**: `perfetto_analysis` 的 `register_agent_tools` MUST 返回含完整 `parameters` JSON Schema 的工具定义
- **FR-101**: `AnalysisResult` MUST 提供 `to_summary_dict()` 方法，返回 Agent 可直接消费的结构化摘要
- **FR-102**: MUST 编写 `trace_analysis.md` SOP 文档，定义 trace 分析的完整操作步骤和输出格式
- **FR-110**: `perfdog_insights` MUST 实现 `register_agent_tools`，注册 `pdi_load_report` 和 `pdi_summarize` 工具
- **FR-111**: `PerfdogInsightsService` MUST 新增 `summarize_report()` 方法，提取关键指标摘要（FPS 统计、Jank 率、内存峰值、功耗）
- **FR-112**: MUST 编写 `perfdog_analysis.md` SOP 文档
- **FR-120**: `game_perf` MUST 新增 `analyze_config()` 方法，调用 `GamePerfParser` 解析 XML 并返回结构化策略摘要
- **FR-121**: 策略摘要 MUST 包含：CPU 集群频点配置、GPU 频点配置、支持的游戏列表、各场景策略模式
- **FR-122**: `register_agent_tools` MUST 新增 `gp_analyze_config` 工具
- **FR-123**: MUST 编写 `strategy_review.md` SOP 文档

### Phase 1.5: 工作流学习与沉淀（FR-150 ~ FR-160）

- **FR-150**: MUST 记录每次对话中的工具调用序列（工具名、参数、结果摘要、用户决策点），形成 WorkflowTrace
- **FR-151**: 对话结束时（用户明确结束或长时间无输入），MUST 检测当前会话是否包含可沉淀的工作流：(a) 未使用预置 SOP 但调用了 2+ 个工具；(b) 使用了 SOP 但步骤有偏差
- **FR-152**: 满足沉淀条件时，Agent MUST 主动提示用户"是否保存为新的工作流 SOP？"或"是否更新现有 SOP？"
- **FR-153**: 用户确认保存后，Agent MUST 自动生成 SOP Markdown（含 YAML frontmatter + 步骤描述），展示给用户预览和编辑
- **FR-154**: 保存的 SOP MUST 写入 `data/sops/` 目录，并自动注册到 SOP Manager 供后续发现
- **FR-155**: 用户自定义 SOP 与内置 SOP（`assets/sops/`）MUST 共存，同名时用户版本优先

### Phase 2: 综合分析能力（FR-200 ~ FR-210）

- **FR-200**: MUST 编写 `jank_comprehensive.md` 综合卡顿分析 SOP，编排三个单项分析的执行顺序和交叉关联逻辑
- **FR-201**: Agent MUST 支持创建分析工作目录（C-010）：开发环境 `modules/agent_chat/data/agent_workspace/<内容>_<时间戳>/`，打包后 `<exe_dir>/output/agent_workspace/<内容>_<时间戳>/`。用户可覆盖指定自定义目录
- **FR-202**: MUST 实现内置工具 `create_workspace` 和 `list_workspace_files`，供 Agent 管理文件
- **FR-203**: 综合分析结果 MUST 包含：问题列表、原因归因（关联到 trace 维度数据和 PerfDog 指标）、策略参数调整建议（新旧对比）、调整理由

### Phase 3: 知识增强（FR-300 ~ FR-310）

- **FR-300**: MUST 实现历史报告索引，初期使用上下文注入（将最近 N 份报告摘要放入 system prompt）
- **FR-301**: 后续可升级为 SQLite FTS5 全文检索或向量检索，当前版本不强制要求
- **FR-302**: 保存的工作流 SOP SHOULD 记录生成来源（原始对话 ID），支持追溯

---

## Key Entities

- **AgentConfig**: 模块配置（Pydantic），含 API 密钥、模型选择、SOP 目录、对话历史设置等
- **Message**: 对话消息（role: user/assistant/tool, content, tool_calls, created_at）
- **ToolDefinition**: 工具定义（name, description, parameters JSON Schema, method 引用）
- **ToolCall**: 工具调用请求（id, name, arguments dict, status, elapsed_ms）
- **ToolResult**: 工具执行结果（tool_call_id, content, is_error, report_paths）
- **LLMResponse**: LLM 响应（text, tool_calls, usage, model, provider）
- **Conversation**: 对话会话（id, title, sop_used, workflow_trace, messages, created_at, updated_at）
- **SOPDocument**: SOP 文档（path, title, keywords, description, recommended_provider, content, source: builtin/custom）
- **WorkflowTrace**: 工作流记录（tool_calls 有序列表、用户决策点、与原 SOP 的偏差信息）

---

## 架构决策

| 决策项 | 结论 | 理由 |
|--------|------|------|
| 模块名称 | `agent_chat`，context 前缀 `ac_`，CLI: `agent` | 与架构文档 §9 预留一致 |
| LLM 调用方式 | 直接 HTTP API（通过官方 SDK） | 无需额外中间件，SDK 成熟稳定 |
| Tool Schema | JSON Schema（与 LLM Function Calling 原生格式对齐） | Claude/GLM/OpenAI 均使用此格式 |
| SOP 格式 | Markdown 文件，注入 system prompt | 简单直观，无需解析器；LLM 天然理解 Markdown |
| 对话循环 | 同步循环 + QThread 异步 GUI | Service 保持同步（Constitution II），GUI 用 QThread 不阻塞 |
| 工具执行 | 同进程直接调用 method 引用 | 零序列化开销，利用已有 Service 实例 |
| 结果序列化 | dataclass/Pydantic → dict → JSON string 反馈给 LLM | LLM 需要文本格式的工具结果 |
| API Key 存储 | 写入 `data/config.json`（gitignored），不入库 | 安全性：密钥不进 git |
| 依赖管理 | `anthropic`、`zhipuai` 作为可选依赖 | 用户按需安装，不增加基础包体积 |

---

## LLM Provider 技术选型

### Claude (Anthropic API)

```python
# 核心调用方式
import anthropic
client = anthropic.Anthropic(api_key=config.api_key)
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system=system_prompt,
    messages=messages,
    tools=tool_definitions,  # JSON Schema 格式
)
```

- 优势：tool_use 能力强，支持 streaming，中文理解好
- 需要：外网访问，API Key

### GLM (智谱 API)

```python
# 核心调用方式
from zhipuai import ZhipuAI
client = ZhipuAI(api_key=config.api_key)
response = client.chat.completions.create(
    model="glm-4-plus",
    messages=messages,
    tools=tool_definitions,  # OpenAI 兼容格式
)
```

- 优势：国内网络无障碍，成本较低
- 需要：智谱 API Key

### Provider 切换

通过 `AgentConfig.provider` 字段选择，运行时动态实例化对应 Provider。两个 Provider 的 ToolDefinition 格式有细微差异（Claude 用 `input_schema`，GLM 用 `parameters`），在 Provider 内部做适配。

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: 用户从输入消息到收到 Agent 首次流式响应的时间 < 5 秒（不含工具执行时间）
- **SC-002**: Agent 能正确识别用户意图并自动匹配 SOP 的成功率 > 90%（基于预置 SOP 场景）
- **SC-003**: 单项分析（trace/PerfDog/策略）端到端流程可在 Agent 引导下完成，无需用户手动操作工具
- **SC-004**: 综合分析产出的报告包含：问题列表、原因归因、策略建议三个必要部分
- **SC-005**: LLM API 调用失败时不崩溃，给出明确错误提示并允许重试
- **SC-006**: 新工作流沉淀为 SOP 后，下次相同类型任务 Agent 能自动匹配到该 SOP
- **SC-007**: 历史会话中的报告链接可正常打开（报告存在时），且对话可继续（追加新消息）
