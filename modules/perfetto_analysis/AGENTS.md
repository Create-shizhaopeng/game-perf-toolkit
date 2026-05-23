# Perfetto 解析分析 — AI 开发规则

> 继承项目根 Constitution（`.specify/memory/constitution.md`），以下为模块级补充约束。

## 目录

- [模块概述](#模块概述)
- [Agent 工具集](#agent-工具集)
  - [Pydantic AI 工具](#pydantic-ai-工具subagent-可调用)
  - [压缩策略说明](#压缩策略说明)
  - [缓存机制](#缓存机制)
- [Skills 管理](#skills-管理)
- [继承的全局规则](#继承的全局规则)
- [模块边界约束](#模块边界约束)
- [Agent 编排引擎](#agent-编排引擎)
  - [结构化输出 G1](#结构化输出-g1)
  - [经验自动提取 G1](#经验自动提取-g1)
  - [HTML 报告三区块 G1](#html-报告三区块-g1)
  - [相似案例注入 G2](#相似案例注入-g2)
  - [经验淘汰与晋升 G3](#经验淘汰与晋升-g3)
  - [Review 增强 G4](#review-增强-g4)
  - [Skill 知识层级应用 G5](#skill-知识层级应用-g5)
- [模块特有规则](#模块特有规则)
- [GUI 开发注意事项](#gui-开发注意事项)
- [数据库相关规则](#数据库相关规则)
- [Spec 索引](#spec-索引)
- [测试要求](#测试要求)

## 模块概述

Perfetto trace 丢帧解析与多维度卡顿归因分析模块。基于 Android 丢帧 SOP 执行 Phase 1（丢帧定位）和 Phase 2（结构化数据拆解），支持 9 个分析维度（CPU/Thread/Binder/IO/GC/GPU/SF/Input/Lock）+ 全 Trace 整体分析（Summary），生成 Markdown 报告和 JSON 数据。

## Agent 工具集

本模块为 Agent 注册了 **1 个核心工具** `pa_execute_sql`，所有 Perfetto 分析能力通过 YAML 技能库 + 此工具实现。

**完整工具文档**：`skills/perfetto-analysis/tool-catalog.md`

### pa_execute_sql(trace_path, sql)

执行 PerfettoSQL 查询。SQL 来源于 YAML 技能文件（atomic/composite/deep/modules/pipelines/vendors/），Agent 通过 SKILL.md 场景索引定位到对应 YAML，读取 SQL，替换 ${variable} 后调用此工具。

**返回结构**：`{success: bool, rows: list[dict], row_count: int, error: str|null}`

**YAML 技能库规模**：atomic (126) + composite (33) + deep (2) + modules (18) + pipelines (33) + vendors (8) + fragments (3)

| 工具 | 数据源 | 说明 | 压缩策略 |
|------|--------|------|----------|
| `pa_trace_overview` | 引擎 | trace 元数据概览（时长、帧数、进程） | `keep_all` |
| `pa_detect_jank` | 引擎 | 卡顿帧检测（⚠️ 游戏 trace 可能为空，见下文） | `jank_records` |
| `pa_analyze_dimension` | MCP/引擎 | 单维度分析（cpu/thread/binder/io/gc/gpu/sf/input/lock/summary） | `degraded_aware` |
| `pa_list_dimensions` | 本地 | 列出 10 个可用分析维度 | `keep_all` |
| `pa_get_history` | 引擎 | 查询分析历史记录 | `truncate(300)` |
| `pa_find_slices` | MCP/引擎 | 按名称搜索 slice | `truncate(400)` |
| `pa_execute_sql` | MCP/引擎 | 任意 Perfetto SQL 查询 | `truncate(500)` |
| `pa_analyze_anr` | MCP/引擎 | ANR 检测与根因分析（降级: thread+binder+lock） | `degraded_aware` |
| `pa_analyze_memory` | MCP/引擎 | 内存泄漏与堆分析（降级: gc 维度） | `degraded_aware` |
| `pa_read_knowledge` | 本地 Skill | 两级加载 Skill 知识库（L1 目录概览 / L2 锚点章节） | `keep_all` |

### 压缩策略说明

| 策略 | 行为 |
|------|------|
| `keep_all` | 数据量小，完整保留（最大 2000 token） |
| `jank_records` | 保留 jank_records/parse_result 完整，精简 vsync_cycles 等大数据 |
| `degraded_aware` | `degraded=True` 维度完整保留，正常维度精简为摘要 |
| `truncate(N)` | 通用截断至 N token |

### 缓存机制

工具查询结果自动写入 `PerfettoAnalysisService._analysis_cache`，避免同一分析会话中重复查询 trace。编排器在每次 `analyze_single` 开始时清空缓存。

### 已移除的工具

以下工具在 010-prompt-budget-management 迭代中移除，其功能由现有工具覆盖：

| 原工具 | 替代方案 |
|--------|----------|
| `pa_analyze_full` | `pa_analyze_dimension` 按需调用多个维度 |
| `pa_cpu_overview` | `pa_analyze_dimension(dimension="cpu")` |
| `pa_compress_results` | 工具内置 `ResultCompressor` 自动压缩 |

### 关键注意事项

- **游戏 trace 帧检测**：`pa_detect_jank` 依赖 VSync/FrameTimeline，游戏进程（Unity/Unreal）绕过 Choreographer，此数据为空。引擎的 `frame_boundary.py` 支持通过 `eglSwapBuffers`/`vkQueuePresentKHR` 识别游戏帧边界，但当前未接入 `detect_jank_frames` 主流程。替代方案：`pa_find_slices("eglSwapBuffers")` + `pa_execute_sql` 计算帧间隔
- **ToolReturn 机制**：所有工具返回 `ToolReturn(return_value=压缩摘要, metadata=原始数据)`，按 `COMPRESSION_PROFILES` 注册表的策略压缩
- **SOP frontmatter**：每个 SOP 文件头部 YAML frontmatter 定义场景元数据（scene、priority_dims、prefetch），由 `prompts.py` 解析构建场景注册表
- **MCP 独有能力**：hotspot（主线程热点）维度、ANR、内存分析（当前 MCP Client 为桩实现，自动降级到引擎）
- **引擎独有能力**：io、gc、gpu、sf、input、lock 维度分析
- **分析模式**：通过 `config.json` 的 `analysis_mode` 控制（mcp_preferred / engine_only / mcp_only）
- **SOP 文档**：`skills/perfetto-analysis/sop/` 下有卡顿、通用、ANR、内存、IO 阻塞、响应时延、输入时延、启动、转屏分析的标准操作流程

## Skills 管理

本模块的 Cursor Skills 源文件位于 `skills/` 目录下，通过 `scripts/sync_skills.py` 同步到 `.cursor/skills/` 供 Cursor IDE 自动发现。

| 路径 | 说明 |
|------|------|
| `skills/perfetto-analysis/SKILL.md` | Perfetto 全场景性能分析（卡顿/ANR/内存/启动/CPU） |

**工作流程**：
1. 在 `skills/` 目录下编辑 SKILL.md（源文件，Git 追踪）
2. 运行 `python scripts/sync_skills.py` 同步到 `.cursor/skills/`
3. Cursor 自动发现更新后的 Skill

修改 Skill 后 MUST 运行同步脚本以生效。同步副本由 `.cursor/skills/.gitignore` 排除，不入库。

## 继承的全局规则

> 本模块遵循项目全局编码规范（详见项目根 `.cursor/rules/`）
> - Python 3.12+，类型注解覆盖所有公共方法
> - 数据模型：公共 API 用 Pydantic，模块内部用 dataclass
> - 中文注释和文档字符串
> - CLI 输出 SHOULD 支持 JSON 格式（渐进落地）
> - 插件 context 键名使用 `pa_` 前缀（如 `pa_service`、`pa_adb`、`pa_data_dir`）。`pa_` 取自 **p**erfetto **a**nalysis 缩写，不可使用 `pe_`（已被 perfetto_capture 占用，详见 P01 踩坑记录）
> - 开发前 MUST 阅读 `docs/experience/development-pitfalls.md`

## 模块边界约束

- 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`
- 禁止修改：`toolkit/`、其他模块目录、项目根配置文件
- 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`
- 禁止导入：`toolkit.core` 内部实现、其他模块的 `src/`

## Agent 编排引擎

本模块包含基于 Pydantic AI 的多 Agent 编排引擎，位于 `src/agent/` 目录。

| 文件 | 说明 |
|------|------|
| `__init__.py` | 数据模型（AnalysisTask, AnalysisStatus, AnalysisReport, AnalysisRouting, AgentRole, OrchestrationConfig, SceneMeta, PrefetchSpec, CompressionProfile, RootCauseItem, AnalysisOutput） |
| `agents.py` | Pydantic AI Agent 工厂（MainAgent 动态路由 / SubAgent 推理链+结构化输出 / ReviewAgent） |
| `orchestrator.py` | 编排器，管理 Phase 0(预填) → Phase 1(预取) → SubAgent → 经验提取 → 遥测 流程 |
| `tools.py` | pa_* 工具封装 + COMPRESSION_PROFILES 压缩策略注册表 + 缓存命中逻辑 |
| `prompts.py` | SOP frontmatter 解析 + 场景元数据注册表 + 推理链 prompt 模板构建 |
| `report.py` | AnalysisOutput 三区块 HTML 报告生成 + 占位符替换 + 降级 fallback |
| `package_db.py` | 包名↔进程名映射数据库（自动学习 + JSON 导入/导出） |

### 关键约束

- `AnalysisOrchestrator` 是编排器（非 Agent），管理 Agent 实例生命周期
- 编排流程: Phase 0(自动抓取预填) → MainAgent 路由 → Phase 1(场景预取) → SubAgent(推理链) → 经验提取 → 遥测写入
- SubAgent `output_type=AnalysisOutput`，`retries=1`，输出结构化分析结果
- SubAgent `request_limit=50`，超限后通过 `_fallback_output` 生成空 AnalysisOutput
- SubAgent 使用 Phase A/B/C 推理链结构：排查 → 验证 → 结论
- 预取结果注入 SubAgent prompt 的"已知信息"区块，避免重复工具调用
- 分析完成后自动从 AnalysisOutput.root_causes 提取经验写入 `pa_learnings` 表（静默降级）
- 遥测数据自动写入 `pa_telemetry` 表（工具调用次数/明细、token 消耗）
- `device_model` 来源优先级: trace 文件名解析 > `pa_analysis_tasks` 表 > 留空
- 每个 trace 的分析在独立 SubAgent 中执行，上下文完全隔离
- 通过 `pydantic-ai-litellm` 适配 LiteLLM，复用全局 LLMManager 配置
- 分析结果存放路径：`output/analysis/<trace_stem>_<YYYYMMDD_HHmmss>/`
- GUI 层通过 `AnalysisWorker(QThread)` 调用编排器，使用 `asyncio.run()` 驱动异步流程

### 结构化输出 (G1)

SubAgent 设置 `output_type=AnalysisOutput`，输出包含：
- `user_intent_summary`: 用户问题归纳
- `overall_conclusion`: 整体结论
- `root_causes: list[RootCauseItem]`: 根因列表（tag/severity/qualitative/evidence/reasoning）
- `detailed_report`: 详细报告（支持 `{{chart:key}}` 占位符）

解析失败时通过 `_fallback_output` 生成兜底 AnalysisOutput（root_causes=[]，不触发经验提取）。

### 经验自动提取 (G1)

分析完成后，如果 `root_causes` 非空，自动提取经验写入 `pa_learnings` 表：
- 每条 `RootCauseItem` 生成一条经验记录
- 置信度基于 `severity` 权重 + `evidence` 完整性计算
- 写入失败静默降级，不中断主流程

### HTML 报告三区块 (G1)

基于 AnalysisOutput 的报告结构：
| 区块 | 数据来源 | 内容 |
|------|---------|------|
| Section 1 | `user_intent_summary` + `trace_info` | 问题定义 |
| Section 2 | `overall_conclusion` + `root_causes[]` | 根因表格 |
| Section 3 | `detailed_report` | 详细分析（占位符替换） |

无 AnalysisOutput 时降级到原有文本报告。

### 相似案例注入 (G2)

分析前自动从 `pa_learnings` 检索历史相似案例注入 SubAgent prompt。

**两级检索**：
| 级别 | 方式 | 依赖 |
|------|------|------|
| L1 | SQL 精确匹配 (scene+process) + 标签交叉 | 无（SQLite 内置） |
| L2 | 向量语义搜索 (cosine distance) | sentence-transformers + sqlite-vec（可选） |

**流程**: 预取完成后 → 提取 issue_tags → L1 检索 → (L1 < 2 条时) L2 补充 → 格式化为"历史分析参考"注入 prompt → 分析完成后比对根因标签更新 hit_count

**降级链**: L1+L2 → 纯 L1 → 无案例注入（零报错）

**关键文件**: `src/agent/learnings_search.py`（LearningsSearcher 类）

### 经验淘汰与晋升 (G3)

基于 OpenClaw `memory_score = recency × importance × frequency` 公式自动管理经验库。

**评分公式**: `recency(0.95^days) × importance(confidence) × frequency(log(hit_count+1))`

**淘汰流程**:
| 条件 | 操作 |
|------|------|
| `score < 0.05` 且过冷却期(7天) | `archived = 1`（软删除） |
| 剩余 < 20 条 | 停止淘汰（最低保留数量） |

**晋升流程**: `hit_count ≥ 3 AND confidence ≥ 0.6` → top 10 候选 → LLM 评审 → promote/merge/archive

**触发时机**: 每 20 次分析自动触发（`pa_telemetry` COUNT % 20）+ CLI `review-learnings` 手动触发

**关键文件**: `src/agent/learnings_manager.py`

### Review 增强 (G4)

ReviewAgent 从纯文本输入/输出升级为基于 `AnalysisOutput` 的结构化评审，输出 `ReviewResult` Pydantic 模型。

**结构化输入**: `AnalysisReport.analysis_output` 透传 `AnalysisOutput`（含 `root_causes: list[RootCauseItem]`）到 Review 阶段。

**场景感知触发** (`_should_review`):
| 场景 | 触发类型 | 说明 |
|------|----------|------|
| 批量同场景 | `cross_compare` | 交叉对比一致性和矛盾 |
| 批量跨场景 + 低置信度 | `individual_review` | 仅低置信度 trace 做独立评审 |
| 单 trace + 根因 ≥ 3 或置信度 < 0.5 | `self_check` | 质量自检 |

**置信度校准闭环**: `ReviewResult.confidence_adjustments` 按 `tag`(root_cause_tag) 精确匹配 `pa_learnings` 记录，adjustment 范围 [-0.3, +0.3]，写回 `pa_learnings.confidence`，与 G3 淘汰/晋升机制联动。

**关键文件**: `src/agent/agents.py`（`create_review_agent`）、`src/agent/orchestrator.py`（`_should_review`、`_run_review`、`_apply_confidence_calibration`）

### Skill 知识层级应用 (G5)

SubAgent 通过 `pa_read_knowledge` 工具按需拉取 Skill 知识库中的 L2/L3 知识资产。

**两级加载**:
| 级别 | 触发条件 | 返回内容 |
|------|---------|---------|
| L1 | 无锚点（如 `patterns/root-cause-patterns.md`） | 章节目录 + 每章首句摘要 |
| L2 | 带锚点（如 `patterns/root-cause-patterns.md#cpu-调度抢占`） | 指定章节完整内容（≤2000 字符） |

**SOP 引用指针**: 所有 SOP 文件末尾添加了"深入分析资源"章节，包含场景相关的 `pa_read_knowledge` 引用指针，指向 patterns、SQL 模板和案例库。

**路径安全**: `pa_read_knowledge` 限制路径在 `skills/perfetto-analysis/` 内，拒绝路径遍历。

**关键文件**: `src/agent/tools.py`（`pa_read_knowledge`、`_heading_to_anchor`、`_build_toc_summary`、`_extract_section_by_anchor`）

## 模块特有规则

- 分析引擎核心逻辑放在 `src/engine/` 子包中，从源项目 `perfettoAnalysisByPython` 迁移而来
- `src/engine/` 内部使用相对导入（`from . import parser`），外层通过 `from .engine import ...` 访问
- `service.py` 封装 `engine/` 的能力，提供 `on_progress` 回调，MUST NOT 直接依赖 GUI 框架
- 模块使用独立 SQLite 数据库（`data/perfetto_analysis.db`），通过 `src/engine/storage.py` 管理
- 共享 DB 中创建 `pa_analysis_tasks` 索引表用于跨模块发现（含 process_name、mode、dimensions 字段）
- 依赖 `perfetto` Python 包（TraceProcessor），需在项目虚拟环境中安装
- 事件联动：监听 `perfetto_capture.trace_ready`，通过配置 `auto_analyze_on_capture` 控制是否自动分析
- 报告文件存放目录：
  - 开发环境：`data/output/trace_report/<trace_stem>/`（相对项目根）
  - 打包后（PyInstaller）：`<exe_dir>/output/trace_report/<trace_stem>/`
- Top N / Binder 阈值 / 调度延迟等参数在 `config.json` 中配置，不在 GUI 中暴露
- "重新生成报告"功能从 DB 已有数据生成 Markdown，不重新分析 trace
- 进程名未指定时自动从 trace 中检测并展示（纯包名，去掉 PID/SurfaceView 前缀）

## GUI 开发注意事项

- 左侧面板使用 `setFixedWidth(580px)`，不随窗口缩放
- 维度多选控件使用 QPushButton + _PersistentMenu（QMenu 子类），**不可使用 QComboBox 自定义 popup**（Windows 下会导致 COM 线程崩溃 `0x8001010d`）
- 删除/刷新历史表后 MUST 使用 `QTimer.singleShot(100ms)` 延迟刷新，避免 use-after-free 竞态
- 工作线程（_AnalysisWorker）中 MUST NOT 直接操作 UI 控件，通过 pyqtSignal 通信
- 按钮图标使用 `QStyle.StandardPixmap` 系统图标（跨平台兼容）

## 数据库相关规则

- 共享 DB 写入 MUST 使用独立 `sqlite3.connect()` 连接（工作线程安全）
- 主线程读取共享 DB 可使用 `db_manager.connection` 属性
- `_ensure_extra_columns()` 提供向后兼容的字段检测与动态添加
- 迁移脚本位于 `src/migrations/`，按序号命名（001, 002, 003...）
- 去重策略：`trace_path + mode` 组合唯一，重新分析时 DELETE+INSERT 覆盖
- 删除记录时检查同一 trace_path 是否还有其他模式记录，据此决定是否清理磁盘文件

## Spec 索引

当前无活跃 Spec。完整索引见 [specs/INDEX.md](specs/INDEX.md)。

## 测试要求

- `service.py` 中每个公共方法至少一个测试用例
- `engine/parser.py` 的核心解析逻辑需有单独测试
- 测试数据放在 `fixtures/` 目录
- 使用 `unittest.mock` 模拟 TraceProcessor 查询结果
- 测试不得依赖真实 trace 文件（除 fixtures 中的测试数据外）
