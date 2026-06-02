# Feature Specification: Agent 核心重构

**Feature Branch**: `021-agent-core-refactor`

**Created**: 2026-05-26

**Status**: Implemented

**Input**: User description: "DES-001 Agent 核心重构设计方案 — modules/agent_chat 提升为 toolkit/agent，Tool/Skill/MCP 基础设施下沉到 toolkit/core，Agent 右侧面板，模块能力统一封装为 Skill/MCP"

**Design Reference**: [docs/design/DES-001-agent-core-refactor.md](../../docs/design/DES-001-agent-core-refactor.md)

## Clarifications

### Session 2026-05-26

- Q: AgentPanel 与现有 RightPanel 基础设施的关系是什么？ → A: AgentPanel 独占右侧面板，替换现有 RightPanel 的内容区。Agent 不在左侧导航栏中作为 Tab 出现。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent 作为右侧面板辅助分析 (Priority: P1)

用户在游戏性能分析工作流中（如查看 Perfetto trace 数据），可以展开右侧 Agent 面板，直接向 Agent 提问"当前 trace 文件的卡顿原因是什么？"。Agent 自动发现已注册的 `perfetto-analysis` Skill，加载其 SKILL.md 内容，根据文档指引调用 `pa_execute_sql` 工具执行 PerfettoSQL 查询，并将分析结果以流式文本返回给用户。整个过程无需切换 Tab，Agent 和主分析界面同屏显示。

**Why this priority**: 这是 Agent 存在的最核心价值——在分析工作流中提供"不离开当前界面"的智能辅助。将此作为 P1 确保重构后用户的核心工作流程不被中断。

**Independent Test**: 打开 trace 文件到分析界面 → 点击右侧 Agent 面板 → 输入"帮我分析这个 trace 的卡顿" → Agent 自动加载相关 Skill → 调用分析工具 → 返回分析结果。整个过程验证了 Skill 发现、工具编排、流式输出的完整链路。

**Acceptance Scenarios**:

1. **Given** 应用已启动且模块已注册 Skill，**When** 用户展开 Agent 面板并输入分析请求，**Then** Agent 通过 LLM 自主决定加载哪个 Skill 并调用正确的工具完成分析
2. **Given** Agent 面板处于折叠状态，**When** 用户点击展开按钮，**Then** 面板从右侧滑出，宽度约 360px，中央主工作区相应缩小
3. **Given** Agent 正在执行分析任务（如 LLM 调用中），**When** 用户点击停止按钮，**Then** 当前任务被取消，Agent 返回就绪状态
4. **Given** Skill 尚未在系统提示词中完整展开，**When** Agent 判断需要某个 Skill 的知识，**Then** Agent 通过 `skill_load` 工具按需加载该 Skill 的完整 SKILL.md 内容

---

### User Story 2 - 模块通过 Skill 文档暴露能力 (Priority: P2)

`perfetto_analysis` 模块不再通过 `register_agent_tools()` 直接暴露 `pa_execute_sql` 等裸方法。取而代之，模块维护一个 `skills/perfetto-analysis/SKILL.md` 文档，描述如何使用其 MCP 工具进行性能分析。Agent 通过 Core 的 `SkillRegistry` 发现该 Skill，在用户提问时自动加载对应的分析方法论。

**Why this priority**: 统一模块能力暴露方式是本次重构的核心架构目标。P2 优先级表明：先确保 Agent 本身正常工作（P1），再逐步将各模块的能力适配到新的注册模式。

**Independent Test**: 检查 `perfetto_analysis` 模块的 `register_agent_tools()` 返回值是否为空（或仅返回经过 Skill 封装的引用），验证 `register_skills()` 返回的 SKILL.md 路径指向一个包含正确 YAML frontmatter 的 Skill 文档。

**Acceptance Scenarios**:

1. **Given** 一个模块注册了 Skill 文档，**When** 应用启动，**Then** `SkillRegistry` 扫描并索引该 Skill 的元数据（name, description, tags, triggers）
2. **Given** Skill 已索引，**When** Agent 构建系统提示词，**Then** Skill 的 name + description 出现在 Stable 层的 Skill 索引摘要中
3. **Given** 模块需要暴露可执行能力，**When** 模块在 `on_startup` 中调用 `mcp_registry.register_local()`，**Then** 对应的 MCP 工具以 `mcp__local__{module}__{tool}` 格式注册到 `ToolRegistry`

---

### User Story 3 - 开发者可以连接外部 MCP 服务扩展 Agent 能力 (Priority: P3)

开发者在 `data/config/mcp_servers.json` 中配置一个外部 MCP Server（如 GitHub MCP Server），启动应用后，Agent 自动连接该 Server 并发现其工具。用户在 Agent 面板中提问时，Agent 可以调用这些外部工具。例如："帮我创建一个分析报告相关的 GitHub Issue"。

**Why this priority**: 外部 MCP 集成是扩展性目标。先确保内置的 Skill/Tool 体系正常工作（P1/P2），再支持外部集成。当前 MCP Client 能力已在 agent_chat 中部分实现，Phase 1 将其提升到 Core 即可。

**Independent Test**: 在 `mcp_servers.json` 配置一个可用 MCP Server → 启动应用 → Agent 自动连接 → Agent 的工具列表中包含 `mcp__{server}__{tool}` 格式的外部工具 → Agent 能成功调用并返回结果。

**Acceptance Scenarios**:

1. **Given** MCP Server 配置已就绪，**When** 应用启动，**Then** `MCPRegistry` 自动连接所有已启用的 MCP Server 并将其工具注入 `ToolRegistry`
2. **Given** MCP Server 连接失败，**When** 应用启动，**Then** 启动不中断，Agent 仅使用已成功连接的工具，失败原因记录到日志
3. **Given** MCP Server 动态刷新了工具列表，**When** Agent 下一次构建工具视图时，**Then** 工具列表反映最新的变化

---

### Edge Cases

- **循环依赖消除**：`toolkit/core/mcp_server.py` 不再 import `modules/agent_chat/` 中的任何模块。MCP Server 功能使用 `toolkit/core/tool_registry.py`。
- **Skill 搜索路径冲突**：同名 Skill 出现在多个搜索路径中时，优先使用本地模块的 Skill（后发现的覆盖先发现的）。
- **工具数量爆炸**：连接多个外部 MCP Server 时工具数量可能超过 LLM 上下文限制。系统提示词中仅列出工具名称和一句话描述，完整描述由 LLM 按需通过 `skill_load` 获取。
- **LLM Provider 未配置**：启动时若未配置任何 LLM Provider，Agent 面板显示"请先配置 LLM Provider"引导，不尝试连接 LLM。
- **SOP 旧数据迁移**：`data/sops/` 目录下已有的 SOP 文档由 `SkillRegistry` 识别为一种 Skill（添加搜索路径），不丢失已有数据。

## Requirements *(mandatory)*

### Functional Requirements

**Phase 1: 基础设施下沉**

- **FR-001**: `ToolRegistry` 和 `ToolExecutor` MUST 从 `modules/agent_chat/src/tools/` 移动至 `toolkit/core/`，保持已有功能不变
- **FR-002**: `ToolCall`、`ToolResult`、`ToolDefinition` 等核心数据模型 MUST 从 `modules/agent_chat/src/models.py` 提取至 `toolkit/core/models.py`，消除 `mcp_server.py` 对 agent_chat 模块的反向依赖
- **FR-003**: MCP Client 组件（`connection.py`、`manager.py`、`tool_bridge.py`）MUST 从 `modules/agent_chat/src/mcp/` 提升至 `toolkit/core/mcp/`，与现有 `mcp_server.py` 合并为统一的 MCP 子包
- **FR-004**: `SkillRegistry` MUST 合并 `agent_chat/src/skills/discovery.py` 的递归目录扫描和 YAML frontmatter 解析能力，消除 Skill 双轨制
- **FR-005**: agent_chat 内部所有 import 路径 MUST 更新为指向新的 `toolkit.core` 位置，功能保持不变

**Phase 2: Agent 框架化**

- **FR-006**: `modules/agent_chat/` MUST 整体重命名为 `toolkit/agent/`，`AgentChatPlugin` 类重命名为 `AgentPlugin`
- **FR-007**: 新建 `AgentOrchestrator` 类，负责从 Core 的 `ToolRegistry`、`SkillRegistry`、`MCPRegistry` 获取统一工具视图，并管理 `AgentService` 生命周期
- **FR-008**: 系统提示词 MUST 改为三段式组装（Stable / Context / Volatile）。Stable 层在会话期间不变，包含身份声明 + 工具摘要 + Skill 索引
- **FR-009**: `AgentService` MUST 移除内部 LLM Provider 初始化的 fallback 逻辑，完全依赖 `LLMManager` 获取 Provider
- **FR-010**: Agent GUI MUST 从中央 Tab（`AgentTab`）改为右侧面板（`AgentPanel`），独占现有 RightPanel 内容区，Agent 不在左侧导航栏中作为 Tab 出现。面板默认折叠，展开宽度约 360px
- **FR-011**: SOP 系统（`SOPManager`、`WorkflowTracker`、SOP 生成器）MUST 合并到 Skill 体系。`WorkflowTracker` 触发"沉淀"时生成 SKILL.md 格式文档而非旧 SOP 格式
- **FR-012**: `SubAgentManager` 空占位实现 MUST 移除，`SubAgentConfig` 和 `SubAgentResult` 模型保留，`AgentOrchestrator` 预留 `spawn_subagent()` 接口
- **FR-013**: `AgentPanel` MUST 复用现有 `AgentTab` 中的消息渲染组件（`_UserMessageWidget`、`_AgentTextWidget`、`_ToolCallCard`、`_TokenUsageLabel`），会话选择和设置入口简化为紧凑布局

**Phase 3: 模块适配**

- **FR-014**: `perfetto_analysis` 模块 MUST 编写 `skills/perfetto-analysis/SKILL.md`，将现有工具调用方法文档化
- **FR-015**: 模块的 `register_agent_tools()` 返回值 MUST 逐步迁移为空列表，能力通过 `register_skills()` 和 `register_local()` MCP 方式暴露
- **FR-016**: `AgentConfig` 中已标注 `[deprecated]` 的 LLM 字段 MUST 清理，完全依赖 `LLMManager` 管理 LLM 配置

### Key Entities

- **ToolEntry**: 单个工具的注册信息。关键属性：name（工具名）、toolset（来源分组：skill/module/mcp-local/mcp-external）、schema（JSON Schema）、handler（可调用方法）、check_fn（可用性检查函数）
- **SkillMetadata**: Skill 文档的元数据。关键属性：name、version、description、tags、triggers（触发关键词）、platforms（操作系统限制）、file_path（SKILL.md 路径）、skill_dir（Skill 目录）
- **MCPConnection**: MCP Server 的连接状态。关键属性：server_name、status（connecting/connected/disconnected/error）、available_tools（已发现工具名列表）
- **AgentOrchestrator**: Agent 生命周期管理者。持有 ToolRegistry、SkillRegistry、MCPRegistry 的引用，负责初始化工具视图和系统提示词
- **SystemPrompt**: 三段式提示词。分为 Stable（稳定层，会话期间不变）、Context（上下文层，含用户文件等）、Volatile（易变层，含 Memory 快照和时间戳）

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Agent 能在用户发出分析请求后 5 秒内开始流式输出首段文本（LLM 响应 + 工具调用决策）
- **SC-002**: Agent 成功发现并加载所有已注册的 Skill（100% 覆盖，无遗漏）
- **SC-003**: Agent 成功连接所有已启用的可用 MCP Server（连接成功率 100% 或提供明确错误信息）
- **SC-004**: `toolkit/core/` 中的任何模块不再 import `modules/agent_chat/`（零反向依赖）
- **SC-005**: 开发者新增一个 Skill（编写 SKILL.md + 在 plugin.py 中注册）可在 10 分钟内完成
- **SC-006**: 重构后所有已有测试保持通过（测试通过率 = 100%）
- **SC-007**: Agent 面板从折叠到展开的过渡动画在 300ms 内完成

## Assumptions

- LLM Provider 已由 `llm_manager` 模块统一管理，Agent 不再自行创建 Provider 实例
- 右侧面板基础设施已在 `toolkit/gui/` 中存在，AgentPanel 可作为其子 widget 嵌入
- `mcp` Python SDK 已在项目依赖中，MCP Client 功能基于此 SDK 实现
- 现有测试覆盖了 agent_chat 的核心功能（289 个测试），重构后测试需更新 import 路径但逻辑不变
- Phase 3 中 `perfetto_analysis` 和 `device_disguise` 的 Skill 文档基于已有代码编写，不涉及新功能开发
- `data/config/mcp_servers.json` 配置文件格式沿用 agent_chat 中已有的 `MCPServerConfig` 模型定义
- 对话历史存储（SQLite）和报告索引功能保持不变，仅路径从模块目录迁移到 `toolkit/agent/`
