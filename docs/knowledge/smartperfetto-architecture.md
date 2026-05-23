# SmartPerfetto 架构分析

> 来源项目: `C:\WorkSpace\2026\project\SmartPerfetto`
> 分析日期: 2026-05-21
> 目的: 为 lv-game-toolkit perfetto_analysis 模块 Skill 重构提供参考

## 迁移状态

> 更新于 2026-05-21：SmartPerfetto 的 YAML 技能库已迁移到 `modules/perfetto_analysis/skills/perfetto-analysis/` 下。
> 迁移内容：atomic (126) + composite (33) + deep (2) + modules (18) + pipelines (33) + vendors (8) + fragments (3) = 共 223 个文件。
> 执行模型：Agent 自编排（不需要 Python SkillRunner），Agent 通过 SKILL.md 索引定位 YAML → 读取 SQL → 通过 pa_execute_sql 执行。

## 目录

- [项目概览](#项目概览)
- [Skill 执行引擎（核心）](#skill-执行引擎核心)
- [Skill 注册与发现](#skill-注册与发现)
- [YAML 技能体系](#yaml-技能体系)
- [意图检测](#意图检测)
- [管线检测](#管线检测)
- [跨域专家对话](#跨域专家对话)
- [MCP 集成](#mcp-集成)
- [REST API](#rest-api)
- [关键源文件索引](#关键源文件索引)
- [对 lv-game-toolkit 重构的启示](#对-lv-game-toolkit-重构的启示)

## 项目概览

SmartPerfetto 是一个基于 Express 5.x 的 Node.js/TypeScript 后端，提供 Perfetto trace 分析能力。

### 顶层目录结构

| 目录 | 用途 |
|------|------|
| `backend/` | Node.js 后端（Express + TypeScript） |
| `frontend/` | Perfetto UI shell |
| `rust/` | Rust 火焰图分析器 |
| `docs/` | 架构/功能/运维文档 |
| `scripts/` | 构建/部署/工具脚本 |
| `test-traces/` | 测试 trace 样本 |

### 后端模块

| 目录 | 用途 |
|------|------|
| `agent/` | 多 Agent 系统（planner/evaluator/domain agents/cross-domain experts） |
| `agentv3/` | Agent V3 运行时 + MCP 工具注册 + 项目记忆 |
| `services/skillEngine/` | **核心**: Skill 执行引擎 |
| `services/` | 其他服务（pipelineSkillLoader, ragStore, baselineStore 等） |
| `controllers/` | Express 路由控制器 |
| `routes/` | 40+ Express 路由模块 |
| `types/` | 共享类型定义 |

---

## Skill 执行引擎（核心）

位于 `backend/src/services/skillEngine/`，由以下文件组成：

| 文件 | 行数 | 职责 |
|------|------|------|
| `skillExecutor.ts` | ~4616 | 核心执行引擎：表达式求值、步骤分发、诊断规则、迭代器、管线 |
| `skillLoader.ts` | ~950 | YAML 加载、SkillRegistry 单例、供应商覆盖、SQL 片段缓存 |
| `types.ts` | ~760 | 所有类型定义（步骤类型、技能类型、执行上下文、模块专家类型） |
| `skillAnalysisAdapter.ts` | ~896 | HTTP 适配层：意图检测、供应商检测、结果转换 |
| `skillValidator.ts` | -- | 输入验证、条件验证、片段引用检查 |
| `expressionUtils.ts` | ~67 | JS 表达式中变量提取 |

### 执行上下文

执行时维护一个 `SkillExecutionContext`，包含：

```
context = {
  params: {},          # 外部传入参数
  inherited: {},       # 继承的参数（skill ref 调用时）
  variables: {},       # save_as 保存的变量
  results: {},         # 每个步骤的完整结果
  currentItem: null,   # iterator 当前项
}
```

### 步骤类型与执行逻辑

| 步骤类型 | 执行方法 | 说明 |
|---------|---------|------|
| `atomic` | `executeAtomicStep()` | 替换 ${var} → 注入 SQL fragments → 执行 SQL → 返回行数据 |
| `skill` | `executeSkillRefStep()` | 解析 ${} 参数 → 递归调用 `this.execute()` 执行引用的 skill |
| `iterator` | `executeIteratorStep()` | 从 source 获取数组 → 可选 filter → 逐项执行子 skill |
| `parallel` | `executeParallelStep()` | `Promise.all()` 并行执行子步骤 |
| `diagnostic` | `executeDiagnosticStep()` | 评估 rules[].condition → 生成诊断结果 |
| `ai_decision` | `executeAIDecisionStep()` | 构建 prompt → 调用 AI → 解析 JSON decision |
| `ai_summary` | `executeAISummaryStep()` | 同上，提取 summary 字段 |
| `conditional` | `executeConditionalStep()` | 按序评估 when → 第一个匹配执行 then → 否则执行 else |
| `pipeline` | `executePipelineStep()` | 读取管线检测结果 → 组装 teaching + pin 指令 |

### 表达式求值器 (ExpressionEvaluator)

核心能力：
1. **模板替换**: `${var}` 在字符串内替换为变量值
2. **默认值语法**: `${varName|defaultValue}` — 变量未定义时使用默认值
3. **路径解析**: 支持 `a.b.c` 和 `a[0]` 形式的嵌套访问
4. **JS 表达式**: 复杂表达式通过 `new Function()` 求值
5. **SQL 感知**: 在 SQL 引号内的 `${var}` 未定义时返回 `''` 而非 NULL

变量解析优先级：
```
context.currentItem → context.params → context.inherited → context.variables → context.results
```

### SQL 片段注入

`injectSqlFragments()` 逻辑：
1. 查找 `fragmentRegistry` 中的片段内容
2. 替换片段中的 `${var}`
3. 如果步骤 SQL 以 `WITH` 开头 → 在 `WITH` 后插入片段 CTE
4. 否则 → 包装为 `WITH {fragments} {original_sql}`

### save_as 上下文传递

```
step 执行完成
  → context.results[step.id] = stepResult
  → if step.save_as: context.variables[step.save_as] = extractSaveAsValue(stepResult)
  → 下游步骤通过 ${save_as_name} 引用
```

### 供应商覆盖合并

1. 加载 `skills/vendors/{vendorName}/*.override.yaml`
2. 每个 override 声明 `extends: base_skill_id` + `additional_steps`
3. 运行时 `detectVendor()` 通过 SQL 识别设备供应商
4. 匹配的 override 的 `additional_steps` 追加到基础技能步骤中

---

## Skill 注册与发现

`SkillRegistry` (skillLoader.ts 中的单例):

### 加载顺序
```
fragments/*.sql → atomic/ → composite/ → custom/ → deep/ → system/ → comparison/ → modules/(递归) → pipelines/ → vendors/
```

### 加载过程
1. `fs.readFileSync` + `yaml.load()` 读取 YAML
2. `normalizeSkillDefinition()` 标准化（处理遗留格式）
3. `validateAndLogWarnings()` 验证
4. 存入 `skills: Map<string, SkillDefinition>`

### 技能数量统计
- atomic: 126
- composite: 33
- deep: 2
- modules: 18 (含 app/framework/kernel/hardware 子目录)
- pipelines: 32
- vendor overrides: 8
- comparison: 1
- **总计: 216+ .skill.yaml 文件**

---

## YAML 技能体系

### 技能层级

| 层级 | 说明 | 示例 |
|------|------|------|
| atomic | 单一 SQL 查询，原子操作 | `game_fps_analysis`, `cpu_topology_detection` |
| composite | 多步组合，引用其他 skill | `jank_frame_detail`, `cpu_analysis` |
| deep | 深度分析（需 simpleperf/perf 数据） | `callstack_analysis` |
| modules | 跨域专家（dialogue 协议） | `scheduler_module`, `cpu_module` |
| pipelines | 渲染管线检测（31 种） | `hwui_blast`, `flutter_impeller` |
| vendors | 供应商覆盖 | `qualcomm`, `mtk`, `samsung` |
| fragments | 共享 SQL CTE | `target_threads.sql`, `vsync_config.sql` |

### YAML 结构概览

```yaml
name: skill_id
version: "1.0"
type: atomic | composite | deep | pipeline_definition | comparison
category: rendering | hardware | system | binder | ...
tier: S | A | B
priority: high | medium | low

meta:
  display_name: "显示名"
  description: "描述"
  icon: "gamepad"
  tags: [tag1, tag2]

triggers:
  keywords:
    zh: [关键词1, 关键词2]
    en: [keyword1, keyword2]
  patterns: [regex1, regex2]

prerequisites:
  required_tables: [table1, table2]
  optional_tables: [table3]
  modules: [android.frames.timeline]

thresholds:
  metric_name:
    levels:
      excellent: { max: 1 }
      good: { min: 1, max: 5 }
      warning: { min: 5, max: 10 }
      critical: { min: 10 }

inputs:
  - name: param_name
    type: string | timestamp | number
    required: true | false
    default: value

steps:
  - id: step_id
    type: atomic | skill | diagnostic | iterator | conditional | pipeline
    name: "步骤名"
    sql: "SELECT ..."                    # atomic 类型
    skill: referenced_skill_name         # skill 类型
    params: { key: "${var}" }           # skill 类型参数
    save_as: variable_name               # 结果保存到上下文
    condition: "js_expression"           # 条件执行
    optional: true | false               # 可选步骤
    display:
      level: summary | detail | key | hidden
      title: "显示标题"
      columns:
        - name: col_name
          label: "列标签"
          type: number | string
          format: "%.2f"
          unit: "ms"
    for_each:                            # iterator 类型
      source: variable_name
      skill: skill_name
      max_items: 100
    inputs: [var1, var2]                 # diagnostic 类型
    rules:                               # diagnostic 类型
      - condition: "js_expression"
        severity: critical | warning | info
        diagnosis: "诊断模板 ${var}"
        confidence: high | medium | low
        suggestions:
          - "[Owner] ... | [Priority] P1 | [Action] ..."

output:
  format: structured
  fields:
    - name: field_name
      description: "字段描述"
```

### 模块专家对话结构

```yaml
module:
  layer: app | framework | kernel | hardware
  component: scheduler | binder | cpu | ...
  subsystems: [sub1, sub2]
  relatedModules: [module1, module2]

dialogue:
  capabilities:
    - id: cap_id
      questionTemplate: "为什么线程 {thread} 被延迟？"
      requiredParams: [thread]
      optionalParams: [timeRange]
  findingsSchema:
    - id: finding_id
      severity: critical | warning | info
      titleTemplate: "发现模板"
      descriptionTemplate: "描述模板"
      evidenceFields: [field1, field2]
  suggestionsSchema:
    - id: sug_id
      condition: "js_expression"
      targetModule: module_name
      questionTemplate: "跟进问题模板"
      paramsMapping: { key: value }
      priority: high | medium | low
```

---

## 意图检测

`findMatchingSkill(question)` 逻辑（简单实现）：

1. 问题转小写
2. 遍历所有注册技能
3. **关键词匹配**: `triggers.keywords` 中的任何关键词出现在问题中 → 匹配
4. **模式匹配**: `triggers.patterns` 中的正则匹配问题 → 匹配
5. 返回第一个匹配（无排序/评分）

注意：这是简单实现，无 TF-IDF / embedding / 置信度评分。

---

## 管线检测

### 检测流程

1. **信号收集** (YAML skill `rendering_pipeline_detection`): 收集线程/切片信号
2. **评分** (TypeScript 生成器): 从 pipeline YAML 读取 `required_signals` + `scoring_signals`，生成加权评分 SQL
3. **结果**: `primary_pipeline_id` + `primary_confidence` + `candidates_list`

### 7 大管线族 (31 种)

| 族 | 数量 | 类型 |
|----|------|------|
| hwui | 6 | Blast, Legacy, Software, Mixed, Multi-Window, Compose |
| surface | 4 | SurfaceView, TextureView, SurfaceControl, PiP |
| graphics | 3 | OpenGL ES, Vulkan Native, ANGLE |
| flutter | 3 | Impeller, Skia, TextureView |
| webview | 5 | Chrome Viz, GL Functor, SurfaceControl, SurfaceView, TextureView |
| react_native | 3 | Old Arch, New Arch Fabric, Skia |
| specialized | 7 | Game Engine, Camera, Video HWC, HW Buffer, VRR, ImageReader, Software |

每个管线 YAML 包含: `detection` + `teaching` (Mermaid 图) + `auto_pin` + `analysis`

---

## 跨域专家对话

### 架构

```
BaseCrossDomainExpert (抽象基类)
  ├── generateInitialQueries()  # 生成初始查询
  ├── analyzeAndDecide()        # 分析结果，决定下一步
  └── synthesizeConclusion()    # 综合结论

ModuleExpertInvoker (桥接)
  ├── YAML module skill ← → 跨域专家
  ├── extractFindings()         # 从技能结果提取发现
  └── extractSuggestions()      # 从技能结果提取建议
```

### 对话协议

- `DialogueSession` 管理多轮对话
- 每个模块专家可声明 `suggestionsSchema`
- suggestion 的 `condition` 满足时，推荐下一步查询的 `targetModule`
- `HypothesisManager` 维护最多 5 个假设，按置信度排序

---

## MCP 集成

### 独立 MCP Server

`bin/smartperfetto-mcp.ts` — stdio JSON-RPC 服务器，暴露 7 个只读工具：

| 工具 | 用途 |
|------|------|
| `lookup_blog_knowledge` | RAG 搜索 androidperformance.com |
| `lookup_aosp_source` | RAG 搜索 AOSP 源码 |
| `lookup_oem_sdk` | RAG 搜索 OEM SDK 文档 |
| `lookup_baseline` | 获取存储的基线 |
| `compare_baselines` | 对比两个基线 |
| `recall_project_memory` | 基于标签的记忆召回 |
| `recall_similar_case` | 基于标签的案例召回 |

注意：**不暴露** 需要活跃 trace_processor 的工具（execute_sql, invoke_skill）。

### 进程内 MCP Server

`agentv3/mcpToolRegistry.ts` — 工具有曝光级别: `public` / `internal` / `deprecated`

---

## REST API

关键端点：

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/skills` | 列出所有技能 |
| GET | `/api/skills/:skillId` | 获取技能详情 |
| POST | `/api/skills/execute/:skillId` | 执行技能 |
| POST | `/api/skills/analyze` | 自动检测 + 执行 |
| POST | `/api/skills/detect-intent` | 自然语言匹配技能 |
| POST | `/api/skills/detect-vendor` | 检测设备供应商 |

---

## 关键源文件索引

| 文件路径 | 职责 |
|---------|------|
| `backend/src/services/skillEngine/skillExecutor.ts` | **核心引擎**: 表达式求值、步骤分发、诊断规则、迭代器 |
| `backend/src/services/skillEngine/skillLoader.ts` | YAML 加载、Registry、供应商覆盖、SQL 片段 |
| `backend/src/services/skillEngine/types.ts` | 全部类型定义 |
| `backend/src/services/skillEngine/skillAnalysisAdapter.ts` | HTTP 适配、意图检测、结果转换 |
| `backend/src/services/renderingPipelineDetectionSkillGenerator.ts` | 运行时生成管线检测技能 |
| `backend/src/services/pipelineSkillLoader.ts` | 管线 YAML 加载、teaching 内容 |
| `backend/src/agent/experts/crossDomain/baseCrossDomainExpert.ts` | 跨域专家抽象基类 |
| `backend/src/agent/experts/crossDomain/moduleExpertInvoker.ts` | 跨域专家 ↔ YAML 模块技能桥接 |
| `backend/bin/smartperfetto-mcp.ts` | 独立 MCP stdio 服务器 |

---

## 对 lv-game-toolkit 重构的启示

### 核心差异

SmartPerfetto 是一个 **完整的后端服务**（Express + 多 Agent + RAG + MCP），而 lv-game-toolkit 需要的是一个 **嵌入框架的 Skill 执行引擎**。

### 需要移植的核心

1. **SkillExecutor 的 Python 等价实现** — 这是最关键的：
   - 表达式求值器（${var} 替换 + JS 表达式 → Python 表达式）
   - 步骤分发器（atomic/skill/diagnostic/iterator/conditional）
   - SQL 片段注入
   - save_as 上下文传递
   - 供应商覆盖合并

2. **SkillLoader 的 Python 等价实现**：
   - YAML 加载 + 标准化
   - Registry 管理
   - SQL 片段缓存

3. **不需要移植的部分**：
   - Express 路由层（lv-game-toolkit 有自己的 MCP Server）
   - 多 Agent 系统（lv-game-toolkit 用单一 Agent + pa_* 工具）
   - RAG / baseline / case library（超出当前范围）
   - SSE 事件推送（GUI 用 Qt Signal 替代）

### 关键设计决策

| 决策点 | SmartPerfetto 方案 | lv-game-toolkit 建议方案 |
|--------|-------------------|--------------------------|
| 表达式求值 | `new Function()` (JS) | Python `eval()` + 安全沙箱 或 简化解析器 |
| SQL 执行 | HTTP → trace_processor | Python `perfetto.TraceProcessor` 直接调用 |
| 意图检测 | 关键词 + 正则（简单） | 关键词 + 正则（复用），未来可加 LLM 路由 |
| 供应商检测 | SQL 查询设备特征 | 同上 |
| 跨域专家 | 独立 Agent 进程 | 暂不实现，由编排 Agent 处理 |
| 管线检测 | 运行时生成 SQL | 移植 Python 版本 |
