# Implementation Plan: SubAgent 推理链重构

**Branch**: `011-subagent-reasoning-chain` | **Date**: 2026-04-09 | **Spec**: [spec.md](spec.md)

## 目录

- [Summary](#summary)
- [Technical Context](#technical-context)
- [Constitution Check](#constitution-check)
- [Project Structure](#project-structure)
- [Phase 0 Research](#phase-0-research)
- [Phase 1 Design](#phase-1-design)

## Summary

重构 Perfetto 分析模块的 SubAgent 推理链，将当前的"无引导自由探索"模式改为"场景感知预取 → 结构化推理 → 工具级压缩 → 插桩观测"的分层架构。核心改进：LLM 动态路由替代固定 SCENE_CONFIG、基于引擎 `degraded` 标记的工具级压缩策略替代 300 token 一刀切、推理链 Phase A/B/C 引导结构化分析、遥测插桩为后续优化提供数据基础。

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: pydantic-ai, pydantic, litellm  
**Storage**: SQLite (perfetto_analysis.db, 新增 pa_telemetry 表)  
**Testing**: pytest + unittest.mock  
**Target Platform**: Windows 10+ (GUI/CLI)  
**Project Type**: desktop-app (模块化插件架构)  
**Performance Goals**: 单 trace 分析时间 <5 分钟（含 LLM 调用）  
**Constraints**: 单次分析 token 消耗控制在合理范围内（插桩后量化优化）  
**Scale/Scope**: 单用户本地运行，每次分析 1-N 个 trace 文件

## Constitution Check

| 原则 | 检查结果 | 说明 |
|------|---------|------|
| I. Plugin-First | ✅ Pass | 所有改动在 `modules/perfetto_analysis/` 内 |
| II. Three-Surface Unity | ✅ Pass | 改动在 service/agent 层，GUI/CLI 入口不变 |
| III. Agent-Driven Design | ✅ Pass | 增强 Agent 编排能力，符合原则 |
| IV. Dependency Inversion | ✅ Pass | 不新增跨模块依赖 |
| V. Presentation Separation | ✅ Pass | 推理链/压缩/插桩均在 service/agent 层 |
| VI. Open-Closed | ✅ Pass | 不修改 toolkit/ 框架代码 |
| VII. Spec-Driven | ✅ Pass | 当前正在走 speckit 流程 |

## Project Structure

### Documentation (this feature)

```text
specs/011-subagent-reasoning-chain/
├── spec.md              # 功能规格
├── plan.md              # 本文件
├── checklists/
│   └── requirements.md  # Spec 质量检查清单
└── tasks.md             # Task 分解（speckit.tasks 生成）
```

### Source Code (affected files)

```text
modules/perfetto_analysis/
├── src/
│   ├── agent/
│   │   ├── orchestrator.py   # 编排器: 预取流程、prompt 组装、插桩
│   │   ├── agents.py         # Agent 工厂: 推理链 prompt 注入
│   │   ├── tools.py          # 工具: 压缩策略注册表、Bug 修复
│   │   ├── prompts.py        # SOP 加载: 场景元数据提取
│   │   └── __init__.py       # 数据模型: SCENE_CONFIG (→ 动态 SOP 元数据)
│   ├── result_compressor.py  # 压缩器: 工具级结构化压缩
│   ├── service.py            # Service: 缓存机制
│   └── engine/
│       └── storage.py        # DB: pa_telemetry 表
├── tests/
│   ├── test_compression.py   # 压缩策略测试
│   ├── test_orchestrator.py  # 预取流程测试
│   └── test_telemetry.py     # 插桩测试
└── docs/
    └── agent-memory-evolution.md  # 设计文档（已有）
```

## Phase 0 Research

### R1: 引擎 `degraded` 字段覆盖情况

**调研结论**：引擎各分析维度通过 `degraded` (bool) + `degraded_reason` (str) 标记异常。`ResultCompressor._extract_issues_from_data` 从 `data["issues"]` 提取，但引擎实际不产出 `issues` 字段。

**决策**：压缩策略基于 `degraded` 字段而非 `issues`/`severity`。

### R2: 工具返回数据结构

**调研结论**：详见 clarify 记录。各工具返回结构差异大，无法统一为 `issues` 格式。

**决策**：采用工具级压缩策略注册表（`COMPRESSION_PROFILES`），每个工具注册自己的压缩策略。

### R3: LLM 动态路由 vs 固定 SCENE_CONFIG

**调研结论**：固定 SCENE_CONFIG 无法适应多样化的 Perfetto 分析场景。

**决策**：MainAgent 分析用户意图后匹配 SOP 场景，动态加载该场景的元数据（优先维度、预取策略）组装 SubAgent prompt。SOP 文件增加 YAML frontmatter 声明场景元数据。

### R4: 发现的代码 Bug

| Bug | 影响 | 修复方案 |
|-----|------|---------|
| `pa_detect_jank` 将 AnalysisResult 转 str() | 丢失 jank_records 结构化数据 | 改为提取 parse_result dict |
| `pa_analyze_dimension` compact=True 误传到 on_progress | compact 语义未生效 | 修正参数位置或使用关键字参数 |

## Phase 1 Design

### 1.1 SOP 场景元数据（LLM 动态路由基础）

每个 SOP 文件增加 YAML frontmatter：

```yaml
---
scene: jank
display_name: 卡顿分析
priority_dims: [cpu, thread, binder]
secondary_dims: [gpu, sf, io]
optional_dims: [gc, input, lock]
prefetch:
  - tool: detect_jank
    inject_as: jank_frames
  - tool: trace_overview
    inject_as: trace_info
---
```

`prompts.py` 解析 SOP frontmatter，生成场景元数据注册表供编排器使用。

### 1.2 编排器预取流程

```
Phase 0:
  MainAgent(intent + trace_overview) → AnalysisRouting(scene, process_name)

Phase 1 (新增):
  scene_meta = sop_registry[routing.scene]
  for prefetch_spec in scene_meta.prefetch:
      result = call_tool(prefetch_spec.tool, ...)
      cache[cache_key] = result
      prefetch_context[prefetch_spec.inject_as] = result

Prompt 组装:
  推理链模板
  + 精简 SOP 规则
  + prefetch_context（已知信息）
  + [G2] injected_cases（历史案例，后续迭代）

SubAgent 创建:
  Agent(instructions=assembled_prompt, request_limit=50)
```

### 1.3 工具级压缩策略

```python
COMPRESSION_PROFILES: dict[str, CompressionProfile] = {
    "pa_analyze_dimension": CompressionProfile(
        strategy="degraded_aware",
        # degraded=True → 保留完整 data dict，degraded_reason 作为摘要首行
        # degraded=False → 一句话: "{dimension}: 无异常, stats: {key_stats}"
        # degraded 字段不存在 → 按 500 token 通用截断（兼容未适配维度）
    ),
    "pa_detect_jank": CompressionProfile(
        strategy="jank_records",
        # 保留 jank_records 完整，精简 vsync_cycles
    ),
    "pa_trace_overview": CompressionProfile(strategy="keep_all"),
    "pa_list_dimensions": CompressionProfile(strategy="keep_all"),
    "pa_execute_sql": CompressionProfile(strategy="truncate", max_tokens=500),
    "pa_find_slices": CompressionProfile(strategy="truncate", max_tokens=500),
    "pa_get_history": CompressionProfile(strategy="truncate", max_tokens=300),
    "pa_analyze_anr": CompressionProfile(strategy="keep_all"),
    "pa_analyze_memory": CompressionProfile(strategy="keep_all"),
}
```

### 1.4 推理链 prompt 模板

SubAgent 的 instructions 由以下部分组装：

1. **角色定义 + 推理链框架**（固定模板）
2. **已知信息**（编排器注入的预取结果）
3. **场景特化规则**（精简 SOP：判断条件 + 阈值 + 引用指针）
4. **维度优先级**（从 SOP frontmatter 加载）
5. **行为约束**（不重复调用、收敛引导）

### 1.5 缓存机制

`PerfettoAnalysisService` 增加 `_analysis_cache: dict[str, Any]`：
- key: `{trace_path}:{tool_name}:{args_hash}`
- 写入时机：Phase 1 预取 + SubAgent 工具调用
- 读取时机：工具执行前先查缓存
- 生命周期：单次分析会话

### 1.6 遥测插桩

新增 `pa_telemetry` 表（schema 见设计文档）：
- 写入时机：每次分析完成后（`_finalize` 阶段）
- 数据来源：pydantic-ai Agent 运行时的 usage/messages
- 用途：后续分析工具调用模式和 token 消耗分布

### 1.7 数据模型

新增 Pydantic 模型：

```python
class CompressionProfile(BaseModel):
    strategy: Literal["degraded_aware", "jank_records", "keep_all", "truncate"]
    max_tokens: int = 500

class SceneMeta(BaseModel):
    scene: str
    display_name: str
    priority_dims: list[str]
    secondary_dims: list[str] = []
    optional_dims: list[str] = []
    prefetch: list[PrefetchSpec] = []

class PrefetchSpec(BaseModel):
    tool: str
    inject_as: str
    args: dict[str, Any] = {}
```
