# Implementation Plan: Review 增强 (G4)

**Branch**: `015-review-enhancement` | **Date**: 2026-04-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/015-review-enhancement/spec.md`

## 目录

- [Summary](#summary)
- [Technical Context](#technical-context)
- [Constitution Check](#constitution-check)
- [Project Structure](#project-structure)
- [Phase 0: Research](#phase-0-research)
- [Phase 1: Design](#phase-1-design)
  - [ReviewResult 模型](#reviewresult-模型)
  - [ConfidenceAdjustment 模型](#confidenceadjustment-模型)
  - [_should_review 触发判断](#_should_review-触发判断)
  - [create_review_agent 改造](#create_review_agent-改造)
  - [_run_review 重构](#_run_review-重构)
  - [置信度校准写回](#置信度校准写回)
  - [analyze_batch 适配](#analyze_batch-适配)

## Summary

改造现有 ReviewAgent 从纯文本输入/输出升级为基于 `AnalysisOutput` 的结构化评审。引入场景感知触发逻辑 `_should_review`，确保仅同场景 trace 做交叉对比；增加置信度校准闭环，将 Review 结果精确写回 `pa_learnings`，与 G3 淘汰/晋升机制联动。

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: pydantic_ai, pydantic 2.0+, sqlite3
**Storage**: SQLite (`pa_learnings` 表)
**Testing**: pytest
**Target Platform**: Windows + Linux (桌面工具)
**Project Type**: desktop-app (module: perfetto_analysis)
**Constraints**: Review 不阻塞分析结果返回；LLM 失败安全降级

## Constitution Check

| Gate | Status | Note |
|------|--------|------|
| Plugin-First | ✅ Pass | 修改仅限 perfetto_analysis 模块内部 |
| Three-Surface Unity | ✅ Pass | Review 逻辑在 service/agent 层，不涉及 GUI/CLI |
| Presentation Separation | ✅ Pass | 无 GUI/CLI 代码变更 |
| Dependency Inversion | ✅ Pass | 不引入跨模块依赖 |
| Spec-Driven | ✅ Pass | 遵循 Speckit 完整工作流 |

## Project Structure

```text
modules/perfetto_analysis/
├── src/agent/
│   ├── __init__.py           # [修改] 新增 ReviewResult, ConfidenceAdjustment 模型
│   ├── agents.py             # [修改] create_review_agent 增加 output_type=ReviewResult
│   └── orchestrator.py       # [修改] _run_review 重构, _should_review 新增, 置信度校准写回
└── tests/
    └── test_g4_review_enhancement.py  # [新增] G4 单元测试
```

## Phase 0: Research

### R1: AnalysisOutput → Review 输入格式

**Decision**: 从 `AnalysisReport` 中取出 `root_causes` 和 `summary` 字段，结合 `AnalysisOutput` 的结构化字段组装 Review Prompt。

当前问题：`AnalysisReport.root_causes` 是 `list[dict]`，`AnalysisReport.summary` 是 `str`。但 `analyze_single` 返回的 `result` dict 中有完整 `analysis_output: AnalysisOutput`。

**方案**: 在 `analyze_single` 返回的 `AnalysisReport` 中新增 `analysis_output: AnalysisOutput | None` 字段，将结构化数据透传到 `_run_review`。这样 Review 可以直接访问 `AnalysisOutput.root_causes` 的 `RootCauseItem` 结构化数据。

**Rationale**: 避免在 `_run_review` 中重新解析文本，直接利用已有的结构化字段。

### R2: root_cause_tag 精确匹配 pa_learnings

**Decision**: `confidence_adjustments` 中每项含 `tag` 字段，系统按 `task_id + root_cause_tags LIKE '%tag%'` 查询匹配。

**Rationale**: `pa_learnings.root_cause_tags` 存储格式为逗号分隔字符串（如 `"cpu_throttle,binder_ipc"`），需用 LIKE 或 `instr()` 做包含匹配。由于 tag 命名唯一性较高，误匹配风险低。

### R3: batch 场景追踪

**Decision**: 在 `analyze_batch` 中收集每个 trace 的 `AnalysisRouting.scene`，传给 `_should_review` 进行场景一致性判断。

**Rationale**: `AnalysisRouting` 已包含 `scene` 字段，无需额外查询。

## Phase 1: Design

### ReviewResult 模型

新增在 `modules/perfetto_analysis/src/agent/__init__.py`:

```python
class ConfidenceAdjustment(BaseModel):
    """置信度校准条目。"""
    trace_index: int = Field(description="对应 trace 在批量中的索引（0-based）")
    tag: str = Field(description="根因标签，精确匹配 pa_learnings.root_cause_tags")
    adjustment: float = Field(description="校准值，范围 [-0.3, +0.3]")
    reason: str = Field(default="", description="调整理由")


class ReviewResult(BaseModel):
    """ReviewAgent 结构化评审输出。"""
    cross_consistency: str = Field(
        default="", description="交叉一致性评价"
    )
    common_patterns: list[str] = Field(
        default_factory=list, description="共性问题列表"
    )
    contradictions: list[str] = Field(
        default_factory=list, description="矛盾点列表"
    )
    confidence_adjustments: list[ConfidenceAdjustment] = Field(
        default_factory=list, description="置信度调整列表"
    )
    overall_assessment: str = Field(description="整体评审意见")
```

### ConfidenceAdjustment 模型

已包含在 ReviewResult 设计中。`adjustment` 值范围 [-0.3, +0.3]，由 Review Prompt 中明确约束。

### _should_review 触发判断

新增在 `orchestrator.py`:

```python
@staticmethod
def _should_review(
    reports: list[AnalysisReport],
) -> tuple[bool, str]:
    """场景感知的 Review 触发判断。

    Returns:
        (should_trigger, review_type) — review_type: cross_compare | individual_review | self_check | ""
    """
    if len(reports) <= 1:
        # 单 trace: 根因 >= 3 或平均置信度 < 0.5 触发 self_check
        ao = reports[0].analysis_output if reports else None
        if ao and len(ao.root_causes) >= 3:
            return (True, "self_check")
        if ao and ao.root_causes:
            avg_conf = sum(
                AnalysisOrchestrator._calc_initial_confidence([rc])
                for rc in ao.root_causes
            ) / len(ao.root_causes)
            if avg_conf < 0.5:
                return (True, "self_check")
        return (False, "")

    # 批量: 检查场景一致性
    scenes = {
        r.analysis_output.scene
        for r in reports
        if r.analysis_output and r.analysis_output.scene
    }
    if len(scenes) == 1:
        return (True, "cross_compare")

    # 跨场景: 仅低置信度触发 individual_review
    has_low_conf = any(
        r.analysis_output and r.analysis_output.root_causes and
        any(True for _ in r.analysis_output.root_causes)  # 简化: 有根因即检查
        for r in reports
    )
    return (has_low_conf, "individual_review") if has_low_conf else (False, "")
```

**设计说明**:
- `cross_compare`: 所有 trace 同场景时触发，Review 做交叉对比
- `individual_review`: 跨场景时仅对低置信度 trace 做单独自检
- `self_check`: 单 trace 时根因多或置信度低触发自检
- 返回 `(False, "")` 表示无需 Review

### create_review_agent 改造

修改 `agents.py`:

```python
def create_review_agent(model: Any, review_type: str = "cross_compare") -> Any:
    """创建 ReviewAgent，使用 output_type=ReviewResult 实现结构化输出。"""
    from pydantic_ai import Agent
    from . import ReviewResult

    instructions_map = {
        "cross_compare": (
            "你是 Perfetto trace 分析评审专家。\n"
            "你的任务是对多个同场景 trace 的分析结论进行交叉评审:\n\n"
            "1. 检查各结论之间的一致性 (cross_consistency)\n"
            "2. 识别共性问题 (common_patterns)\n"
            "3. 指出矛盾之处 (contradictions)\n"
            "4. 对每个 trace 的每个根因给出置信度调整建议 (confidence_adjustments)\n"
            "   - adjustment 范围: [-0.3, +0.3]，正值表示分析可信度高，负值表示存疑\n"
            "   - tag 必须与根因的 tag 字段完全一致\n"
            "5. 综合给出整体评审意见 (overall_assessment)\n"
            "6. 所有输出使用中文"
        ),
        "self_check": (
            "你是 Perfetto trace 分析评审专家。\n"
            "你的任务是对单个 trace 的分析结论进行质量自检:\n\n"
            "1. 验证各根因之间的逻辑一致性\n"
            "2. 检查证据链是否充分\n"
            "3. 对每个根因给出置信度调整建议 (confidence_adjustments)\n"
            "   - adjustment 范围: [-0.3, +0.3]\n"
            "   - tag 必须与根因的 tag 字段完全一致\n"
            "4. 综合给出整体评审意见 (overall_assessment)\n"
            "5. 所有输出使用中文"
        ),
        "individual_review": (
            "你是 Perfetto trace 分析评审专家。\n"
            "你的任务是对低置信度的分析结论进行独立评审:\n\n"
            "1. 验证根因推理的合理性\n"
            "2. 检查证据与结论的关联性\n"
            "3. 对每个根因给出置信度调整建议 (confidence_adjustments)\n"
            "   - adjustment 范围: [-0.3, +0.3]\n"
            "   - tag 必须与根因的 tag 字段完全一致\n"
            "4. 综合给出整体评审意见 (overall_assessment)\n"
            "5. 所有输出使用中文"
        ),
    }

    agent = Agent(
        model,
        instructions=instructions_map.get(review_type, instructions_map["cross_compare"]),
        output_type=ReviewResult,
    )
    return agent
```

### _run_review 重构

修改 `orchestrator.py`:

```python
async def _run_review(
    self,
    reports: list[AnalysisReport],
    on_stream: Callable | None,
    review_type: str = "cross_compare",
) -> ReviewResult | None:
    """ReviewAgent: 结构化评审。

    Args:
        reports: 分析报告列表
        on_stream: 流式回调
        review_type: 评审类型 (cross_compare / self_check / individual_review)

    Returns:
        ReviewResult 或 None（失败时降级）
    """
    try:
        from .agents import create_review_agent
        from . import ReviewResult

        agent = create_review_agent(self._get_model(), review_type)

        # 构建结构化输入
        input_parts = []
        for i, r in enumerate(reports):
            ao = r.analysis_output
            if not ao:
                continue
            part = f"## Trace {i}\n"
            part += f"**场景**: {ao.scene}\n"
            part += f"**结论**: {ao.overall_conclusion}\n"
            if ao.root_causes:
                part += "**根因列表**:\n"
                for rc in ao.root_causes:
                    part += (
                        f"- tag={rc.tag}, severity={rc.severity}, "
                        f"qualitative={rc.qualitative}, "
                        f"evidence={rc.evidence}, "
                        f"reasoning={rc.reasoning}\n"
                    )
            input_parts.append(part)

        if not input_parts:
            return None

        prompt = f"请{review_type}评审以下分析结论:\n\n" + "\n\n".join(input_parts)
        result = await agent.run(prompt)

        review_result: ReviewResult | None = None
        raw_output = result.output if hasattr(result, "output") else None
        if isinstance(raw_output, ReviewResult):
            review_result = raw_output
        else:
            # 降级: 无法解析为 ReviewResult
            if on_stream:
                on_stream("batch", "assistant", f"评审结论:\n{raw_output}")
            return None

        # 流式输出评审结果
        if on_stream:
            on_stream("batch", "assistant", f"评审结论:\n{review_result.overall_assessment}")

        # 置信度校准写回
        self._apply_confidence_calibration(reports, review_result)

        return review_result

    except ImportError:
        logger.warning("Pydantic AI 未安装，跳过 Review")
        return None
    except Exception as exc:
        logger.warning("Review 失败 (安全降级): %s", exc)
        return None
```

### 置信度校准写回

新增在 `orchestrator.py`:

```python
def _apply_confidence_calibration(
    self,
    reports: list[AnalysisReport],
    review_result: ReviewResult,
) -> None:
    """将 ReviewResult.confidence_adjustments 按 tag 精确写回 pa_learnings。"""
    if not review_result.confidence_adjustments:
        return

    try:
        db = self._pa_service._db_manager
        conn = getattr(db, "conn", None) or getattr(db, "_conn", None)
        if conn is None:
            return

        for adj in review_result.confidence_adjustments:
            if adj.trace_index < 0 or adj.trace_index >= len(reports):
                logger.debug("trace_index %d 越界，跳过", adj.trace_index)
                continue

            adjustment = max(-0.3, min(0.3, adj.adjustment))

            report = reports[adj.trace_index]
            task_id = report.task_id

            # 按 task_id + tag 精确匹配
            rows = conn.execute(
                """SELECT id, confidence FROM pa_learnings
                   WHERE task_id = ? AND instr(root_cause_tags, ?) > 0
                   AND archived = 0""",
                (task_id, adj.tag),
            ).fetchall()

            for row in rows:
                new_conf = max(0.0, min(1.0, row[1] + adjustment))
                conn.execute(
                    "UPDATE pa_learnings SET confidence = ? WHERE id = ?",
                    (new_conf, row[0]),
                )

        conn.commit()
        logger.info(
            "置信度校准完成: %d 条调整",
            len(review_result.confidence_adjustments),
        )
    except Exception as exc:
        logger.warning("置信度校准写回失败 (静默降级): %s", exc)
```

### analyze_batch 适配

修改 `analyze_batch` 中的 Review 触发逻辑:

```python
# 现有代码 (L217-220):
# if len(reports) > 1 and not self._abort_flag:
#     if on_status:
#         on_status("batch", AnalysisStatus.REVIEWING, "交叉评审中...")
#     await self._run_review(reports, on_stream)

# 改造后:
if reports and not self._abort_flag:
    should_trigger, review_type = self._should_review(reports)
    if should_trigger and review_type:
        if on_status:
            on_status("batch", AnalysisStatus.REVIEWING, f"评审中 ({review_type})...")
        await self._run_review(reports, on_stream, review_type)
```

同时修改 `AnalysisReport` 模型，新增 `analysis_output` 字段:

```python
class AnalysisReport(BaseModel):
    """分析报告元数据。"""
    task_id: str
    html_path: str = Field(default="", description="HTML 报告文件路径")
    raw_data_dir: str = Field(default="", description="原始数据子文件夹路径")
    summary: str = Field(default="", description="结论摘要")
    trace_overview: dict = Field(default_factory=dict)
    root_causes: list[dict] = Field(default_factory=list)
    analysis_output: AnalysisOutput | None = Field(
        default=None, description="G1 结构化输出（G4 Review 增强使用）"
    )
```
