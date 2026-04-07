# Feature Specification: MCP 管理、Skills 扩展管理、Sub-agent 支持

**Feature Branch**: `002-mcp-skills-subagent`  
**Spec Location**: `modules/agent_chat/specs/002-mcp-skills-subagent/`  
**Created**: 2026-04-01  
**Status**: Draft  
**Input**: 为 agent_chat 模块添加 MCP 服务器管理、Skills 扩展管理和 Sub-agent 编排能力，使 Agent 能动态发现和调用 MCP 工具、按 Skill 知识路由分析策略、通过子 Agent 实现上下文隔离的复杂任务处理

## 目录

- [User Scenarios & Testing](#user-scenarios--testing-mandatory)
- [Requirements](#requirements-mandatory)
- [Clarifications](#clarifications)
- [Assumptions](#assumptions)
- [Success Criteria](#success-criteria-mandatory)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — MCP 服务器管理 (Priority: P1)

用户可以通过配置文件声明 MCP 服务器，系统自动发现并连接。MCP 工具被统一注册到 ToolRegistry，Agent 调用时与本地工具无差异。用户可通过 GUI/CLI 查看已连接的 MCP 服务器状态和可用工具。

**Why this priority**: MCP 是 Agent 能力扩展的基础通道，Perfetto MCP 等工具依赖此基础设施

**Independent Test**: 配置一个 MCP 服务器后，Agent 能发现并调用其工具

**Acceptance Scenarios**:

1. **Given** `mcp_servers.json` 中配置了一个 MCP 服务器, **When** Agent 启动, **Then** 系统自动连接该服务器并注册其工具到 ToolRegistry
2. **Given** MCP 服务器已连接, **When** 用户发送需要 MCP 工具的请求, **Then** Agent 透明调用 MCP 工具并返回结果
3. **Given** MCP 服务器连接失败, **When** Agent 尝试调用其工具, **Then** 返回明确的错误信息，不影响其他工具的使用
4. **Given** GUI 运行中, **When** 用户打开 MCP 管理面板, **Then** 显示所有已配置的服务器及其连接状态和可用工具列表

---

### User Story 2 — Skills 扩展管理 (Priority: P1)

系统通过搜索路径自动发现各模块提供的 Skill 和用户安装的 Skill。Agent 根据用户意图匹配最相关的 Skill，渐进式注入 Skill 知识到对话上下文。默认预装 `skill-creator`、`perfetto-analysis` 和 `knowledge-curator` 三个 Skill。

**Why this priority**: Skill 是 Agent 领域知识的载体，直接决定分析质量和准确性

**Independent Test**: 安装一个 Skill 后，当用户意图匹配时 Agent 自动加载并遵循 Skill 指导

**Acceptance Scenarios**:

1. **Given** 模块 `perfetto_analysis` 提供了 `perfetto-analysis` Skill, **When** Agent 初始化, **Then** SkillManager 自动发现该 Skill 及其元数据
2. **Given** 用户说"帮我分析这个 trace 的卡顿", **When** SkillRouter 匹配意图, **Then** 将 `perfetto-analysis` Skill 内容注入 system prompt
3. **Given** Skill 中引用了 SOP 子资源（如 `sop/jank-analysis.md`）, **When** Agent 进入具体分析阶段, **Then** 按需加载对应 SOP 内容（渐进式披露）
4. **Given** 用户通过 GUI 查看 Skill 列表, **When** 点击某个 Skill, **Then** 显示其名称、描述、来源模块和包含的资源文件
5. **Given** 用户导入一份原始分析文档, **When** `knowledge-curator` Skill 被激活, **Then** 自动分类内容、匹配目标 Skill，经确认后写入子资源

---

### User Story 3 — Sub-agent 编排 (Priority: P2)

主 Agent 能识别需要委派的复杂任务，创建子 Agent 执行特定分析。子 Agent 有独立的 LLM 会话和上下文，完成后仅返回结构化摘要。支持不同 Provider（需用户开启），默认使用与主 Agent 相同的 Provider。

**Why this priority**: 批量分析和复杂场景需要上下文隔离，避免单一对话上下文膨胀导致分析质量下降

**Independent Test**: 主 Agent 创建子 Agent 分析一个 trace，子 Agent 返回结论摘要而非原始数据

**Acceptance Scenarios**:

1. **Given** 用户请求分析 3 个 trace, **When** 主 Agent 判断需要并行处理, **Then** 为每个 trace 创建独立子 Agent
2. **Given** 子 Agent 正在分析, **When** 分析完成, **Then** 仅返回结论摘要到主 Agent，原始数据不进入主 Agent 上下文
3. **Given** 子 Agent 绑定了 `perfetto-analysis` Skill, **When** 子 Agent 执行分析, **Then** 其 system prompt 包含该 Skill 知识但不包含主 Agent 的其他对话历史
4. **Given** 用户开启了多 Provider 功能, **When** 创建子 Agent, **Then** 可指定不同的 Provider（如主 Agent 用 Claude、子 Agent 用 GLM）

---

### User Story 4 — SOP→Skill 全面迁移 (Priority: P2)

移除现有全部编排类 SOP，用标准 Skill 替代。所有领域知识通过 SkillsManager 统一管理，LLM 获得更大的自主编排权。SOPManager 代码移除，GUI 中的"SOP 管理"入口替换为"Skill 管理"。

**Why this priority**: SOP 的固定编排限制了 LLM 的灵活性，Skill 已覆盖工具路由和使用方式，SOP 成为冗余维护负担

**Independent Test**: 移除所有 SOP 后，Agent 仍能通过 Skill 获取领域知识并自主编排分析流程

**Acceptance Scenarios**:

1. **Given** `perfetto-analysis` Skill 包含 jank-analysis SOP, **When** Agent 需要卡顿分析知识, **Then** 通过 Skill 渐进式加载获取
2. **Given** 旧的 `trace_analysis.md` / `jank_comprehensive.md` / `perfdog_analysis.md` / `strategy_review.md` 已移除, **When** Agent 接收综合分析请求, **Then** 自主匹配相关 Skill 组合并编排工具调用
3. **Given** SOPManager 代码已移除, **When** Agent 初始化, **Then** 仅通过 SkillsManager 加载领域知识
4. **Given** 跨模块综合分析场景, **When** 需要 trace + perfdog + 策略三种数据, **Then** Agent 通过加载多个 Skill（perfetto-analysis + 未来的 perfdog/strategy Skill）自主编排

---

### User Story 5 — 001 缺口修复 + 打包支持 (Priority: P3)

修复 001-agent-core 中已识别但未完全实现的功能缺口，包括：CLI 工具注册、上下文截断优化、PerfDog 报告索引、WorkflowTracker Skill 绑定等。同时修复 build.py 对 Skill .md 文件的打包支持。

**Why this priority**: 基础设施的完善是新功能的前提，但多数缺口不阻塞 MCP/Skill/Sub-agent 的核心流程

**Independent Test**: 各缺口修复后对应的 Checkpoint 应通过

**Acceptance Scenarios**:

1. **Given** CLI 模式下, **When** 用户执行 `agent ask` 命令, **Then** ToolRegistry 包含所有插件工具（不仅限于内置工具）
2. **Given** 对话历史超长, **When** 上下文截断触发, **Then** 按策略保留 Skill 上下文 + 最近 N 轮工具结果 + 最近 M 轮用户消息
3. **Given** PerfDog 分析完成, **When** 扫描报告索引, **Then** PerfDog 报告被正确索引和摘要
4. **Given** 使用 Skill 完成分析, **When** WorkflowTracker 检测沉淀条件, **Then** 正确判断工具调用是否偏离 Skill 指导
5. **Given** 执行 PyInstaller 打包, **When** 打包完成, **Then** 产物中包含所有模块的 `skills/` 目录及其 `.md` 文件

---

### Edge Cases

- MCP 服务器在 Agent 对话中途断开连接时：标记该服务器断开，其工具降级到本地同名工具或标记不可用，不中断对话
- Skill 匹配到多个候选时：自动选择描述匹配度最高的一个（已澄清）
- 子 Agent 超时/失败时：返回错误摘要 + 三次重试策略（已澄清）
- 不同 Provider 工具调用兼容性：通过能力标签约束任务分配（已澄清）
- Skill 搜索路径中同名 Skill：模块提供的 Skill 优先于用户路径中的同名 Skill（模块内容更权威）

## Requirements *(mandatory)*

### Functional Requirements

**MCP 管理**

- **FR-001**: 系统 MUST 支持通过 `mcp_servers.json` 配置文件声明 MCP 服务器（名称、启动命令、连接方式、环境变量）
- **FR-002**: 系统 MUST 使用 Python MCP SDK（`mcp` 包）实现 MCP 客户端，支持 stdio 和 SSE 两种连接方式
- **FR-003**: 系统 MUST 在连接 MCP 服务器后自动提取其工具的 JSON Schema，转换为 `ToolDefinition` 注册到 ToolRegistry。MCP 工具优先使用，与本地同功能工具同名时本地工具加前缀，MCP 不可用时自动降级
- **FR-004**: 系统 MUST 管理 MCP 服务器的生命周期（连接、断开、自动重连、超时处理）。对话中途断开时标记服务器状态，工具降级到本地
- **FR-005**: 系统 MUST 在 MCP 工具调用失败时返回结构化错误信息，不影响其他工具的可用性。SDK 版本锁定 v1.26.0，保留版本检查与升级提醒机制
- **FR-006**: GUI MUST 提供 MCP 管理面板，显示服务器状态（连接中/已连接/断开/错误）和可用工具列表

**Skills 扩展管理**

- **FR-010**: 系统 MUST 通过可配置的搜索路径自动发现 Skill（扫描 SKILL.md 文件并解析 YAML frontmatter）
- **FR-011**: 默认搜索路径 MUST 包含各模块的 `skills/` 目录（`modules/*/skills/*/SKILL.md`）
- **FR-012**: 系统 MUST 支持用户在配置中添加额外的 Skill 搜索路径
- **FR-013**: SkillRouter MUST 基于用户消息和 Skill 的 `description` 关键词进行意图匹配，自动选择最相关的一个 Skill（仿 Cursor 模式）
- **FR-014**: 系统 MUST 实现三级渐进式 Skill 注入：① 初始化时所有 Skill 元数据列表注入 system prompt；② 意图匹配后注入 SKILL.md 完整内容；③ 通过 `skill_load_resource` 工具按需加载子资源
- **FR-015**: Skill 的子资源（SOP、patterns、cases 等）MUST 通过 Agent 工具调用按需加载，不一次性全部注入 system prompt
- **FR-016**: GUI MUST 提供 Skill 管理界面，显示已发现的 Skill 列表和详情

**Sub-agent 编排**

- **FR-020**: 系统 MUST 提供 SubAgentManager，支持创建具有独立 LLM 会话的子 Agent
- **FR-021**: 子 Agent MUST 与主 Agent 上下文隔离，不共享对话历史
- **FR-022**: 子 Agent MUST 支持绑定特定 Skill，其 system prompt 仅包含该 Skill 知识
- **FR-023**: 子 Agent 完成后 MUST 返回结构化摘要，原始数据不进入主 Agent 上下文
- **FR-024**: 系统 MUST 默认使用主 Agent 的 Provider，支持用户配置不同 Provider。Provider 元数据 MUST 声明能力标签（supports_tools、supports_vision 等），SubAgentManager 据此约束可分配的任务类型
- **FR-025**: 子 Agent 失败时 MUST 返回错误摘要给主 Agent。三次重试策略：第 1 次自动重试，第 2 次失败后询问用户是否尝试第 3 次，最多 3 次
- **FR-026**: 系统 MUST 支持并发子 Agent 数量限制（默认最大 3 个）

**SOP→Skill 全面迁移**

- **FR-030**: 系统 MUST 移除全部编排类 SOP 文件（`trace_analysis.md`、`jank_comprehensive.md`、`perfdog_analysis.md`、`strategy_review.md`），其领域知识由对应 Skill 提供
- **FR-031**: 系统 MUST 移除 SOPManager 及相关代码（`src/sop/`、`models.py` 中的 SOPDocument/SOPSource），SkillsManager 承接所有知识管理职责
- **FR-032**: GUI MUST 将左侧面板"SOP 管理"入口替换为"Skill 管理"/"知识管理"，调用 SkillsManager 展示已加载的 Skill 及其子资源
- **FR-033**: 跨模块综合分析场景 MUST 由 LLM 自主匹配并加载多个 Skill 进行编排，不使用固定 SOP 流程

**异步架构改造**

- **FR-035**: `LLMProvider.stream_chat()` MUST 改为返回 `AsyncIterator[StreamChunk]`
- **FR-036**: `AgentService.chat()` MUST 改为 `async def`，支持异步工具调用和 MCP 通信
- **FR-037**: `ToolExecutor` MUST 区分同步和异步工具，同步工具通过 `asyncio.to_thread()` 桥接
- **FR-038**: GUI `_AgentWorker` MUST 在 QThread 中启动独立 event loop 执行异步调用
- **FR-039**: CLI 入口 MUST 通过 `asyncio.run()` 启动异步对话循环

**知识策展**

- **FR-050**: 系统 MUST 预装 `knowledge-curator` Skill，支持用户导入原始分析文档/经验文档
- **FR-051**: `knowledge-curator` MUST 对导入的文档进行内容分类（方法论 SOP、根因模式、案例、SQL 模板），匹配目标 Skill
- **FR-052**: `knowledge-curator` MUST 将分类后的内容格式化为目标 Skill 的子资源结构（含 YAML frontmatter），经用户确认后写入
- **FR-053**: `knowledge-curator` 的作用范围 MUST 覆盖工具自带 Skill 和用户通过搜索路径导入的 Skill

**打包支持**

- **FR-044**: `scripts/build.py` 的 `_collect_modules()` MUST 正确收集 `modules/*/skills/` 下的所有文件（包括 `.md` 文件），确保 Skill 知识资产在 PyInstaller 打包后可用
- **FR-045**: 打包产物中 Skill 目录结构 MUST 保持与开发时一致（`skills/*/SKILL.md`、`skills/*/sop/*.md`、`skills/*/patterns/*.md`、`skills/*/cases/*.md`），SkillDiscovery 在打包环境中能正常扫描

**001 缺口修复**

- **FR-040**: CLI `agent ask` MUST 通过 `PluginManager` 收集所有插件工具
- **FR-041**: 上下文截断策略 MUST 区分消息类型（Skill 上下文、工具结果、用户消息），按优先级保留
- **FR-042**: `ReportIndex` MUST 完善 PerfDog 报告扫描功能
- **FR-043**: `WorkflowTracker` MUST 移除 SOP 绑定逻辑，改为 Skill 绑定

### Key Entities

- **MCPServerConfig**: MCP 服务器配置（name, command, args, env, transport_type, timeout）
- **MCPConnection**: MCP 连接实例（server_config, client, status, available_tools, last_error）
- **SkillMetadata**: Skill 元数据（name, description, source_module, path, sub_resources）
- **SkillContext**: 注入到 LLM 的 Skill 上下文（skill_name, content, loaded_resources）  *(替代原 SOPDocument)*
- **SubAgentConfig**: 子 Agent 配置（task, skill_binding, provider, tools_filter, max_tokens）
- **SubAgentResult**: 子 Agent 执行结果（task_description, summary, confidence, elapsed_ms, provider_used）

## Clarifications

### Session 2026-04-01

- **MCP SDK**：使用 Python MCP SDK 官方稳定版（v1.26.0），锁定版本避免 v2 pre-alpha 变更风险。需保留 SDK 版本检查机制，有新稳定版时提醒用户是否升级
- **异步架构**：agent_chat 模块内部全面转异步（方案 B），影响范围局限在模块内部。`LLMProvider.stream_chat()` 改为 `AsyncIterator`，`AgentService.chat()` 改为 `async def`，`ToolExecutor` 通过 `asyncio.to_thread()` 桥接其他模块的同步工具。其他模块的 `register_agent_tools` 注册的同步函数不受影响
- **Skill 存储**：不分预装/用户目录。SkillManager 通过搜索路径发现 Skill（各模块的 `skills/` + 用户配置的额外路径），不复制 Skill 到 agent_chat 内部
- **SOP 迁移**：~~不删除现有 SOP~~（已更新）见"SOP 全面移除"澄清项
- **Sub-agent Provider**：默认使用主 Agent 的 Provider。用户可开启多 Provider 功能，需对不同 Provider 做能力边界约束（如不支持工具调用时降级处理）
- **Skill 多候选处理**：仿 Cursor 模式，基于 Skill description 关键词自动匹配最相关的一个 Skill，不做多候选列表展示。通过 Skill 描述的精确性来避免冲突
- **MCP/本地工具同名**：MCP 工具优先使用，本地工具加前缀标识。MCP 工具不可用时自动降级到同名本地工具（与 perfetto_analysis 的 MCP/引擎降级策略一致）
- **子 Agent 失败处理**：返回错误摘要给主 Agent。三次重试策略——第 1 次自动重试，第 2 次失败后询问用户是否尝试第 3 次。最多 3 次，避免 token 浪费
- **Provider 能力边界**：在 Provider 元数据中声明能力标签（supports_tools、supports_vision 等），SubAgentManager 据此约束可分配的任务类型
- **Skill 渐进式披露**：三级加载——① 所有 Skill 元数据列表注入 system prompt（~20 行）；② 意图匹配后注入 SKILL.md 完整内容（~190 行）；③ 深度分析时通过 `skill_load_resource` 工具按需加载 SOP/patterns 子资源
- **SOP 全面移除**：移除全部 4 个编排类 SOP（`trace_analysis.md`、`jank_comprehensive.md`、`perfdog_analysis.md`、`strategy_review.md`），移除 SOPManager 代码（`src/sop/`）。理由：Skill 中已包含工具路由和使用方式，固定编排 SOP 限制了 LLM 的灵活性。跨模块综合分析由 LLM 自主加载多个 Skill 编排。原 FR-041 中的"SOP 上下文"改为"Skill 上下文"，FR-043 中的 SOP 绑定改为 Skill 绑定
- **build.py Skill 打包**：`scripts/build.py` 的 `_collect_modules()` 当前 `skip_exts = {".md"}` 会跳过 Skill 的所有 `.md` 文件。需修改为：对 `skills/` 子目录下的文件取消 `.md` 过滤，确保 `SKILL.md`、`sop/*.md`、`patterns/*.md`、`cases/*.md` 等知识资产被正确打包到 PyInstaller 产物中

## Assumptions

- Python MCP SDK（`mcp` 包 v1.26.0）可通过 pip 安装且兼容 Python 3.12+
- MCP 服务器通过标准 stdio 或 SSE 方式通信
- 各模块的 SKILL.md 遵循 YAML frontmatter + Markdown body 的统一格式
- 子 Agent 与主 Agent 使用同一进程内的 LLM Provider 实例（非独立进程）
- 001-agent-core 的核心基础设施（LLM Provider、ToolRegistry、ConversationStore）已可用，SOPManager 将在本迭代中移除
- 全异步改造不影响其他模块（perfetto_analysis、perfdog_insights、game_perf），同步工具通过 `asyncio.to_thread()` 桥接

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 配置 MCP 服务器后，Agent 能在 5 秒内完成连接并注册工具
- **SC-002**: Skill 意图匹配准确率 > 85%（对预定义场景测试集）
- **SC-003**: 子 Agent 结果摘要不超过原始数据量的 20%
- **SC-004**: 批量分析（3 个 trace）使用子 Agent 后，主 Agent 上下文增量 < 单 trace 直接分析的 50%
- **SC-005**: MCP 服务器断开后，系统在 3 次重连失败后正确降级，不影响本地工具使用
- **SC-006**: CLI `agent ask` 命令能调用所有插件工具（含 MCP 工具）
- **SC-007**: SOPManager 移除后，Agent 通过 Skill 完成 trace 分析的质量不低于原 SOP 流程（基于相同测试用例对比）
- **SC-008**: PyInstaller 打包产物中 `modules/*/skills/` 目录完整，`SkillDiscovery` 在打包环境能正常扫描发现 Skill
- **SC-009**: `knowledge-curator` Skill 能将一份原始文档正确分类并写入目标 Skill 的对应子资源目录（端到端验证）
