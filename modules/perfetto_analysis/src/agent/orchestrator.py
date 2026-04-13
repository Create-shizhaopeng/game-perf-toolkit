"""分析编排器 — 管理 Main/Sub/Review Agent 生命周期。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from . import (
    AnalysisOutput,
    AnalysisReport,
    AnalysisRouting,
    AnalysisStatus,
    AnalysisTask,
    AgentRole,
    OrchestrationConfig,
    RootCauseItem,
    SceneMeta,
)

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str, AnalysisStatus, str], None]
StreamCallback = Callable[[str, str, str], None]


class AnalysisOrchestrator:
    """编排 Main → Sub × N → Review 分析流程。

    非 Agent 类——纯 Python 编排器，管理 Pydantic AI Agent 实例。
    """

    def __init__(
        self,
        llm_manager: Any,
        pa_service: Any,
        config: OrchestrationConfig | None = None,
        output_base: str = "",
        package_db: Any = None,
    ) -> None:
        self._llm_manager = llm_manager
        self._pa_service = pa_service
        self._config = config or OrchestrationConfig()
        self._output_base = output_base or self._detect_output_base()
        self._abort_flag = False
        self._package_db = package_db

    def _detect_output_base(self) -> str:
        """检测分析输出根目录。"""
        import sys

        if getattr(sys, "frozen", False):
            return str(Path(sys.executable).parent / "output" / "analysis")
        return str(
            Path(__file__).resolve().parents[3] / "data" / "output" / "analysis"
        )

    def request_abort(self) -> None:
        """请求中止当前分析。"""
        self._abort_flag = True

    def reset_abort(self) -> None:
        self._abort_flag = False

    async def analyze_single(
        self,
        trace_path: str,
        user_intent: str,
        process_name: str = "",
        on_status: StatusCallback | None = None,
        on_stream: StreamCallback | None = None,
    ) -> AnalysisReport:
        """单条 trace 的完整分析流程。

        1. MainAgent 路由场景
        2. 创建 SubAgent 执行分析
        3. 生成 HTML 报告
        """
        task_id = str(uuid.uuid4())
        self._abort_flag = False

        def _notify_status(status: AnalysisStatus, detail: str = "") -> None:
            if on_status:
                on_status(task_id, status, detail)

        def _notify_stream(role: str, content: str) -> None:
            if on_stream:
                on_stream(task_id, role, content)

        try:
            _notify_status(AnalysisStatus.ROUTING, "分析意图识别中...")
            _notify_stream("system", f"开始分析: {os.path.basename(trace_path)}")

            if self._abort_flag:
                _notify_status(AnalysisStatus.CANCELLED)
                return AnalysisReport(task_id=task_id)

            routing = await asyncio.wait_for(
                self._route_scene(trace_path, user_intent, process_name, _notify_stream),
                timeout=self._config.analysis_timeout_sec,
            )

            if self._abort_flag:
                _notify_status(AnalysisStatus.CANCELLED)
                return AnalysisReport(task_id=task_id)

            self._pa_service.clear_cache()

            prefetch_context = await self._prefetch(
                trace_path, routing, _notify_stream,
            )

            auto_context = self._load_auto_capture_context(trace_path)
            if auto_context:
                prefetch_context.update(auto_context)

            injected_ids = self._search_similar_cases(
                routing, prefetch_context, _notify_stream,
            )

            _notify_status(AnalysisStatus.ANALYZING, f"场景: {routing.scene}")

            result = await asyncio.wait_for(
                self._run_sub_agent(
                    trace_path,
                    routing,
                    _notify_stream,
                    prefetch_context=prefetch_context,
                ),
                timeout=self._config.analysis_timeout_sec,
            )

            if self._abort_flag:
                _notify_status(AnalysisStatus.CANCELLED)
                return AnalysisReport(task_id=task_id)

            _notify_status(AnalysisStatus.REPORTING, "生成报告中...")
            _notify_stream("system", "📝 分析完成，正在生成 HTML 报告...")
            report = await self._generate_report(task_id, trace_path, routing, result)

            _notify_status(AnalysisStatus.COMPLETED, report.html_path)
            _notify_stream("assistant", f"分析完成，报告已生成: {report.html_path}")

            self._record_tokens(result.get("token_used", 0))
            self._learn_package(trace_path, routing.process_name)
            self._extract_and_save_learnings(
                task_id, trace_path, routing, result.get("analysis_output"),
            )
            self._update_injected_hit_counts(
                injected_ids, result.get("analysis_output"),
            )
            self._record_telemetry(task_id, trace_path, routing, result)

            await self._maybe_trigger_maintenance()

            return report

        except asyncio.TimeoutError:
            _notify_status(AnalysisStatus.TIMEOUT, "分析超时")
            _notify_stream("system", "⚠ 分析超时，已自动中止")
            return AnalysisReport(task_id=task_id)

        except Exception as exc:
            logger.exception("分析失败: %s", exc)
            _notify_status(AnalysisStatus.FAILED, str(exc))
            _notify_stream("system", f"❌ 分析失败: {exc}")
            return AnalysisReport(task_id=task_id)

    async def analyze_batch(
        self,
        tasks: list[AnalysisTask],
        on_status: StatusCallback | None = None,
        on_stream: StreamCallback | None = None,
    ) -> list[AnalysisReport]:
        """批量分析：为每个 trace 创建独立 SubAgent。"""
        reports: list[AnalysisReport] = []
        parallel = self._config.parallel_count

        if parallel <= 1:
            for task in tasks:
                if self._abort_flag:
                    break
                report = await self.analyze_single(
                    task.trace_path,
                    task.user_intent,
                    task.process_name,
                    on_status,
                    on_stream,
                )
                reports.append(report)
        else:
            for i in range(0, len(tasks), parallel):
                if self._abort_flag:
                    break
                batch = tasks[i : i + parallel]
                batch_results = await asyncio.gather(
                    *(
                        self.analyze_single(
                            t.trace_path, t.user_intent, t.process_name,
                            on_status, on_stream,
                        )
                        for t in batch
                    ),
                    return_exceptions=True,
                )
                for r in batch_results:
                    if isinstance(r, Exception):
                        reports.append(AnalysisReport(task_id=str(uuid.uuid4())))
                    else:
                        reports.append(r)

        if reports and not self._abort_flag:
            should_trigger, review_type = self._should_review(reports)
            if should_trigger and review_type:
                if on_status:
                    on_status(
                        "batch", AnalysisStatus.REVIEWING,
                        f"评审中 ({review_type})...",
                    )
                await self._run_review(reports, on_stream, review_type)

        return reports

    async def _route_scene(
        self,
        trace_path: str,
        user_intent: str,
        process_name: str,
        on_stream: Callable | None,
    ) -> AnalysisRouting:
        """MainAgent: 意图分析 + 场景路由。"""
        if on_stream:
            on_stream("system", "🔀 正在分析用户意图，确定分析场景...")

        try:
            from .agents import create_main_agent

            model = self._get_model()
            if model is None:
                raise ImportError("LLM 模型不可用")

            agent = create_main_agent(model)

            trace_info = ""
            try:
                overview = self._pa_service.get_trace_overview(trace_path, process_name or None)
                if overview:
                    processes = getattr(overview, "processes", []) or []
                    trace_info = (
                        f"\nTrace 概览:\n"
                        f"- 时长: {getattr(overview, 'duration_s', '?')}s\n"
                        f"- 帧数: {getattr(overview, 'frame_count', '?')}\n"
                        f"- 刷新率: {getattr(overview, 'refresh_rate_hz', '?')}Hz\n"
                        f"- 进程列表: {', '.join(processes[:10]) if processes else '未检测到'}\n"
                    )
            except Exception as exc:
                logger.debug("预获取 trace 概览失败: %s", exc)

            prompt = (
                f"用户意图: {user_intent}\n"
                f"Trace 路径: {trace_path}\n"
                f"目标进程: {process_name or '未指定'}\n"
                f"{trace_info}"
                "请分析用户意图并路由到合适的分析场景。"
            )
            result = await agent.run(prompt)
            routing = result.output

            if on_stream:
                on_stream(
                    "assistant",
                    f"📋 意图识别完成:\n"
                    f"- 分析场景: {routing.scene}\n"
                    f"- 目标进程: {routing.process_name or '自动检测'}\n"
                    f"- 路由理由: {routing.reasoning}",
                )
            return routing

        except ImportError:
            logger.warning("Pydantic AI 未安装，使用默认路由")
            routing = AnalysisRouting(
                scene="jank",
                sop_name="jank-analysis.md",
                process_name=process_name,
                reasoning="Pydantic AI 未安装，默认路由到卡顿分析",
            )
            if on_stream:
                on_stream("system", f"⚠ Pydantic AI 未安装，使用默认路由: {routing.scene}")
            return routing

    @staticmethod
    def _fallback_output(raw_text: str, scene: str = "unknown") -> AnalysisOutput:
        """解析失败 / 截断时将原始文本包装为 AnalysisOutput（不触发经验提取）。"""
        return AnalysisOutput(
            user_intent_summary="（结构化解析失败，以下为原始输出）",
            trace_info="",
            scene=scene,
            overall_conclusion=raw_text[:2000] if raw_text else "分析未生成结论。",
            root_causes=[],
            detailed_report=raw_text or "",
        )

    @staticmethod
    def _is_context_overflow(exc: Exception) -> bool:
        """判断异常是否为上下文超限。"""
        msg = str(exc).lower()
        overflow_keywords = ["max length", "context", "too long", "token limit", "exceeds"]
        return any(kw in msg for kw in overflow_keywords)

    async def _run_sub_agent(
        self,
        trace_path: str,
        routing: AnalysisRouting,
        on_stream: Callable | None,
        prefetch_context: dict[str, Any] | None = None,
    ) -> dict:
        """SubAgent: 使用 pa_* 工具执行分析。

        降级策略:
        - ImportError (Pydantic AI 不可用): 降级到 engine 分析
        - UsageLimitExceeded / 上下文超限: 返回部分结论 (llm_partial)
        - Model 不可用 (None): 降级到 engine 分析
        """
        try:
            from .agents import create_sub_agent
            from .prompts import load_sop

            if on_stream:
                on_stream("system", f"🔬 正在加载 {routing.scene} 场景 SOP...")

            sop_content = load_sop(routing.scene, routing.sop_name)
            if not sop_content and on_stream:
                on_stream("system", "⚠ 未找到匹配的分析 SOP，LLM 将自主分析")

            from ..result_compressor import ResultCompressor
            compressor = ResultCompressor()

            from .tools import set_tool_stream_callback
            set_tool_stream_callback(on_stream)

            model = self._get_model()
            if model is None:
                raise ImportError("LLM 模型不可用")

            from .prompts import get_scene_meta as _get_scene_meta
            scene_meta = _get_scene_meta(routing.scene)

            agent = create_sub_agent(
                model, sop_content, self._pa_service, compressor,
                scene_meta=scene_meta,
            )

            if on_stream:
                on_stream("system", "🔧 SubAgent 已创建，开始分析...")

            known_info = self._build_known_info_block(prefetch_context or {})

            prompt = (
                f"请分析以下 trace，并输出**人类可读的中文分析报告**:\n"
                f"- Trace 路径: {trace_path}\n"
                f"- 目标进程: {routing.process_name or '自动检测'}\n"
                f"- 分析场景: {routing.scene}\n\n"
                f"{known_info}"
                f"报告格式要求:\n"
                f"1. **问题概述**: 简要描述发现的问题\n"
                f"2. **根因分析**: 列出每个根因的详细分析和证据\n"
                f"3. **关键数据**: 提供支撑结论的量化数据\n"
                f"4. **优化建议**: 给出具体可操作的优化方案\n"
                f"\n注意：调用工具后请尽快归纳结论，避免过多重复调用。"
            )
            from pydantic_ai.usage import UsageLimits
            result = await agent.run(
                prompt,
                usage_limits=UsageLimits(request_limit=50),
            )

            analysis_output: AnalysisOutput | None = None
            raw_output = result.output if hasattr(result, "output") else None
            if isinstance(raw_output, AnalysisOutput):
                analysis_output = raw_output
            elif raw_output is not None:
                analysis_output = self._fallback_output(
                    str(raw_output), routing.scene,
                )
            else:
                analysis_output = self._fallback_output(
                    "分析完成，未生成结论。", routing.scene,
                )

            conclusion = analysis_output.overall_conclusion

            token_used = 0
            if hasattr(result, "usage") and result.usage:
                usage = result.usage
                if hasattr(usage, "total_tokens"):
                    token_used = usage.total_tokens
                elif isinstance(usage, dict):
                    token_used = usage.get("total_tokens", 0)

            tool_calls_history = self._extract_tool_history(result)

            set_tool_stream_callback(None)

            quality_warnings = self._check_conclusion_quality(conclusion, analysis_output)
            if quality_warnings and on_stream:
                on_stream("system", f"⚠ 结论质量自检: {'; '.join(quality_warnings)}")

            if on_stream and conclusion:
                preview = conclusion[:600]
                if len(conclusion) > 600:
                    preview += "...\n(完整结论见报告)"
                on_stream("assistant", f"📊 分析结论:\n\n{preview}")

            return {
                "analysis_output": analysis_output,
                "conclusion": conclusion,
                "token_used": token_used,
                "completion": "llm_complete",
                "quality_warnings": quality_warnings,
                "tool_calls": tool_calls_history,
            }

        except ImportError:
            logger.warning("Pydantic AI 未安装，使用引擎直接分析")
            if on_stream:
                on_stream("system", "⚠ Pydantic AI 未安装，降级为引擎分析")
            result = await self._fallback_engine_analysis(trace_path, routing)
            result["completion"] = "engine_fallback"
            return result

        except Exception as exc:
            from .tools import set_tool_stream_callback
            set_tool_stream_callback(None)

            exc_name = type(exc).__name__
            is_usage_limit = exc_name == "UsageLimitExceeded" or "request_limit" in str(exc)
            is_overflow = self._is_context_overflow(exc)

            if is_usage_limit or is_overflow:
                reason = "LLM 请求次数已达上限" if is_usage_limit else "模型上下文不足"
                logger.warning("%s，分析未完成: %s", reason, exc)
                if on_stream:
                    on_stream("system", f"⚠ {reason}，已基于已有数据生成报告")
                fallback_text = f"分析因 {reason} 未完整完成。请查看原始数据获取更多信息。"
                fallback_ao = self._fallback_output(fallback_text, routing.scene)
                return {
                    "analysis_output": fallback_ao,
                    "conclusion": fallback_text,
                    "token_used": 0,
                    "completion": "llm_partial",
                }
            raise

    async def _fallback_engine_analysis(
        self, trace_path: str, routing: AnalysisRouting
    ) -> dict:
        """Pydantic AI 不可用时的降级分析方案。"""
        logger.info("使用引擎直接分析: %s", trace_path)
        analysis_result = self._pa_service.analyze(trace_path, routing.process_name)

        if isinstance(analysis_result, dict):
            parts = []
            if "summary" in analysis_result:
                parts.append(f"## 问题概述\n{analysis_result['summary']}")
            if "jank_info" in analysis_result:
                jank = analysis_result["jank_info"]
                parts.append(
                    f"## 卡顿检测\n- Jank 数: {jank.get('jank_count', 'N/A')}\n"
                    f"- BigJank 数: {jank.get('big_jank_count', 'N/A')}"
                )
            if "dimensions" in analysis_result:
                dims = analysis_result["dimensions"]
                for dim_name, dim_data in dims.items():
                    parts.append(f"## {dim_name} 维度分析\n{self._format_dimension(dim_data)}")
            if "report_path" in analysis_result:
                parts.append(f"\n引擎报告路径: {analysis_result['report_path']}")

            conclusion = "\n\n".join(parts) if parts else str(analysis_result)
        else:
            conclusion = str(analysis_result)

        return {"conclusion": conclusion, "token_used": 0}

    @staticmethod
    def _extract_tool_history(result: Any) -> list[dict]:
        """从 Pydantic AI RunResult 提取工具调用历史。"""
        tool_calls: list[dict] = []
        try:
            messages = result.all_messages() if hasattr(result, "all_messages") else []
            for msg in messages:
                parts = getattr(msg, "parts", [])
                for part in parts:
                    kind = getattr(part, "part_kind", "")
                    if kind == "tool-call":
                        tool_calls.append({
                            "type": "call",
                            "tool_name": getattr(part, "tool_name", ""),
                            "args": getattr(part, "args", {}),
                            "tool_call_id": getattr(part, "tool_call_id", ""),
                        })
                    elif kind == "tool-return":
                        entry: dict[str, Any] = {
                            "type": "return",
                            "tool_name": getattr(part, "tool_name", ""),
                            "content": str(getattr(part, "content", ""))[:500],
                            "tool_call_id": getattr(part, "tool_call_id", ""),
                        }
                        metadata = getattr(part, "metadata", None)
                        if metadata and isinstance(metadata, dict):
                            raw = metadata.get("raw")
                            if raw is not None:
                                entry["raw_data"] = raw
                        tool_calls.append(entry)
        except Exception as exc:
            logger.debug("提取工具调用历史失败: %s", exc)
        return tool_calls

    @staticmethod
    def _check_conclusion_quality(
        conclusion: str,
        analysis_output: AnalysisOutput | None = None,
    ) -> list[str]:
        """对 SubAgent 结论做轻量规则自检。优先使用 AnalysisOutput 结构化字段。"""
        warnings: list[str] = []

        if analysis_output and analysis_output.root_causes:
            if not analysis_output.overall_conclusion or len(analysis_output.overall_conclusion.strip()) < 20:
                warnings.append("overall_conclusion 过短")
            for i, rc in enumerate(analysis_output.root_causes):
                if not rc.evidence:
                    warnings.append(f"root_cause[{i}].tag={rc.tag} 缺少 evidence")
            return warnings

        if not conclusion or len(conclusion.strip()) < 50:
            warnings.append("结论过短，可能未充分分析")
        if conclusion and "分析完成" in conclusion and len(conclusion) < 100:
            warnings.append("结论缺少具体分析内容")
        expected_sections = ["问题概述", "根因分析", "优化建议"]
        found = sum(1 for s in expected_sections if s in conclusion)
        if found == 0 and len(conclusion) > 100:
            warnings.append("结论缺少结构化章节（问题概述/根因分析/优化建议）")
        return warnings

    @staticmethod
    def _format_dimension(data: Any) -> str:
        """将维度分析数据格式化为人类可读的文本。"""
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            lines = []
            for k, v in data.items():
                if isinstance(v, (list, dict)):
                    import json
                    lines.append(f"- **{k}**: {json.dumps(v, ensure_ascii=False, indent=2)[:500]}")
                else:
                    lines.append(f"- **{k}**: {v}")
            return "\n".join(lines)
        return str(data)

    # ------------------------------------------------------------------
    # G4: 场景感知 Review 触发
    # ------------------------------------------------------------------

    @classmethod
    def _should_review(
        cls,
        reports: list[AnalysisReport],
    ) -> tuple[bool, str]:
        """场景感知的 Review 触发判断。

        Returns:
            (should_trigger, review_type)
            review_type: cross_compare | individual_review | self_check | ""
        """
        valid = [r for r in reports if r.analysis_output]
        if not valid:
            return (False, "")

        if len(valid) == 1:
            ao = valid[0].analysis_output
            if ao and len(ao.root_causes) >= 3:
                return (True, "self_check")
            if ao and ao.root_causes:
                avg_conf = sum(
                    cls._calc_initial_confidence([rc])
                    for rc in ao.root_causes
                ) / len(ao.root_causes)
                if avg_conf < 0.5:
                    return (True, "self_check")
            return (False, "")

        scenes = {
            r.analysis_output.scene
            for r in valid
            if r.analysis_output and r.analysis_output.scene
        }
        if len(scenes) == 1:
            return (True, "cross_compare")

        has_low_conf = False
        for r in valid:
            ao = r.analysis_output
            if ao and ao.root_causes:
                avg_conf = sum(
                    cls._calc_initial_confidence([rc])
                    for rc in ao.root_causes
                ) / len(ao.root_causes)
                if avg_conf < 0.5:
                    has_low_conf = True
                    break

        return (True, "individual_review") if has_low_conf else (False, "")

    async def _run_review(
        self,
        reports: list[AnalysisReport],
        on_stream: Callable | None,
        review_type: str = "cross_compare",
    ) -> "ReviewResult | None":
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

            input_parts: list[str] = []
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
                if on_stream:
                    on_stream("batch", "assistant", f"评审结论:\n{raw_output}")
                return None

            if on_stream:
                on_stream(
                    "batch", "assistant",
                    f"评审结论:\n{review_result.overall_assessment}",
                )

            self._apply_confidence_calibration(reports, review_result)

            return review_result

        except ImportError:
            logger.warning("Pydantic AI 未安装，跳过 Review")
            return None
        except Exception as exc:
            logger.warning("Review 失败 (安全降级): %s", exc)
            return None

    def _apply_confidence_calibration(
        self,
        reports: list[AnalysisReport],
        review_result: "ReviewResult",
    ) -> None:
        """将 ReviewResult.confidence_adjustments 按 tag 精确写回 pa_learnings。"""
        from . import ReviewResult as _RR  # noqa: F811 — type hint only

        if not review_result.confidence_adjustments:
            return

        try:
            db = self._pa_service._db_manager
            conn = getattr(db, "conn", None) or getattr(db, "_conn", None)
            if conn is None:
                return

            updated = 0
            for adj in review_result.confidence_adjustments:
                if adj.trace_index < 0 or adj.trace_index >= len(reports):
                    logger.debug("trace_index %d 越界，跳过", adj.trace_index)
                    continue

                adjustment = max(-0.3, min(0.3, adj.adjustment))
                task_id = reports[adj.trace_index].task_id

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
                    updated += 1

            conn.commit()
            if updated:
                logger.info("置信度校准完成: %d 条记录更新", updated)
        except Exception as exc:
            logger.warning("置信度校准写回失败 (静默降级): %s", exc)

    async def _generate_report(
        self,
        task_id: str,
        trace_path: str,
        routing: AnalysisRouting,
        result: dict,
    ) -> AnalysisReport:
        """生成 HTML 报告，优先使用 AnalysisOutput 结构化数据。"""
        from .report import generate_html_report

        trace_stem = Path(trace_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = os.path.join(self._output_base, f"{trace_stem}_{timestamp}")

        analysis_output: AnalysisOutput | None = result.get("analysis_output")

        report = generate_html_report(
            task_id=task_id,
            result_dir=result_dir,
            trace_path=trace_path,
            scene=routing.scene,
            process_name=routing.process_name,
            conclusion=result.get("conclusion", ""),
            raw_data=result,
            analysis_output=analysis_output,
        )
        report.analysis_output = analysis_output
        return report

    def _get_model(self) -> Any:
        """从 LLMManager 获取 Pydantic AI 可用的模型实例。"""
        try:
            from pydantic_ai_litellm import LiteLLMModel

            config = self._llm_manager.get_config()
            model_name = self._to_litellm_model(config.provider, config.model_name)
            return LiteLLMModel(
                model_name=model_name,
                api_key=config.get_api_key(),
            )
        except (ImportError, Exception) as exc:
            logger.warning("无法创建 LiteLLMModel: %s", exc)
            return None

    @staticmethod
    def _to_litellm_model(provider: str, model: str) -> str:
        """将内部模型名称转为 LiteLLM 路由格式。"""
        prefix_map = {"glm": "zai/", "claude": ""}
        prefix = prefix_map.get(provider, "")
        if prefix and not model.startswith(prefix):
            return f"{prefix}{model}"
        return model

    def _record_tokens(self, count: int) -> None:
        """记录 token 消耗到 LLMManager。"""
        if count > 0 and hasattr(self._llm_manager, "record_tokens"):
            try:
                self._llm_manager.record_tokens(count)
            except Exception:
                pass

    def _record_telemetry(
        self,
        task_id: str,
        trace_path: str,
        routing: AnalysisRouting,
        result: dict,
    ) -> None:
        """T021-T023: 采集遥测数据并写入 pa_telemetry 表。"""
        try:
            from ..engine.storage import insert_telemetry

            db = self._pa_service._db_manager
            conn = getattr(db, "conn", None) or getattr(db, "_conn", None)
            if conn is None:
                return

            tool_calls = result.get("tool_calls", [])
            call_count = sum(1 for t in tool_calls if t.get("type") == "call")

            tool_detail = json.dumps(
                [
                    {"tool": t.get("tool_name", ""), "type": t.get("type", "")}
                    for t in tool_calls[:100]
                ],
                ensure_ascii=False,
            )

            quality_warnings = result.get("quality_warnings", [])
            conclusion_quality = json.dumps(quality_warnings, ensure_ascii=False)

            token_used = result.get("token_used", 0)

            model_name = ""
            try:
                cfg = self._llm_manager.get_config()
                model_name = cfg.model_name
            except Exception:
                pass

            insert_telemetry(
                conn=conn,
                task_id=task_id,
                trace_id=Path(trace_path).stem,
                scene=routing.scene,
                model_name=model_name,
                tool_call_count=call_count,
                tool_calls_detail=tool_detail,
                total_prompt_tokens=0,
                total_completion_tokens=token_used,
                conclusion_quality=conclusion_quality,
                elapsed_sec=0.0,
            )
        except Exception as exc:
            logger.debug("写入遥测数据失败: %s", exc)

    def _learn_package(self, trace_path: str, process_name: str) -> None:
        """分析完成后学习包名映射。"""
        if not self._package_db or not process_name:
            return
        try:
            package = process_name.split(":")[0]
            self._package_db.learn(package, process_name)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # T008/T009/T011/T012 预取与已知信息注入
    # ------------------------------------------------------------------

    async def _prefetch(
        self,
        trace_path: str,
        routing: AnalysisRouting,
        on_stream: Callable | None,
    ) -> dict[str, Any]:
        """Phase 1 预取：根据场景元数据配置执行预取并写入缓存。"""
        from .prompts import get_scene_meta

        scene_meta = get_scene_meta(routing.scene)
        if not scene_meta or not scene_meta.prefetch:
            return {}

        if on_stream:
            on_stream("system", f"📦 预取 {len(scene_meta.prefetch)} 项数据...")

        prefetch_results: dict[str, Any] = {}
        tool_dispatch = self._build_prefetch_dispatch(trace_path, routing.process_name)

        for spec in scene_meta.prefetch:
            if self._abort_flag:
                break
            try:
                handler = tool_dispatch.get(spec.tool)
                if handler is None:
                    logger.warning("预取工具 '%s' 无对应处理器，跳过", spec.tool)
                    continue

                result = handler(**spec.args)
                if result is not None:
                    prefetch_results[spec.inject_as] = result
                    cache_key = self._pa_service.cache_key(
                        trace_path, spec.tool, process_name=routing.process_name,
                    )
                    self._pa_service.set_cached(cache_key, result)
                    if on_stream:
                        on_stream("system", f"  ✅ 预取 {spec.tool} → {spec.inject_as}")
            except Exception as exc:
                logger.warning("预取 %s 失败 (降级跳过): %s", spec.tool, exc)
                if on_stream:
                    on_stream("system", f"  ⚠ 预取 {spec.tool} 失败，降级跳过")

        return prefetch_results

    def _build_prefetch_dispatch(
        self, trace_path: str, process_name: str,
    ) -> dict[str, Callable]:
        """构建预取工具名到实际调用的映射。"""
        dispatch: dict[str, Callable] = {}

        def _detect_jank(**kwargs: Any) -> Any:
            raw = self._pa_service.parse_only(trace_path, process_name)
            if isinstance(raw, dict):
                return raw
            if hasattr(raw, "parse_result"):
                return {
                    "jank_times": getattr(raw, "jank_times", 0),
                    "frame_count": getattr(raw, "frame_count", 0),
                    "detected_process": getattr(raw, "detected_process", ""),
                    "parse_result": raw.parse_result,
                }
            return {"data": str(raw)}

        def _trace_overview(**kwargs: Any) -> Any:
            return self._pa_service.get_trace_overview(trace_path, process_name or None)

        def _analyze_dimension(**kwargs: Any) -> Any:
            dim = kwargs.get("dimension", "cpu")
            return self._pa_service.analyze_dimensions(trace_path, process_name, [dim])

        dispatch["detect_jank"] = _detect_jank
        dispatch["trace_overview"] = _trace_overview
        dispatch["analyze_dimension"] = _analyze_dimension

        return dispatch

    def _load_auto_capture_context(self, trace_path: str) -> dict[str, Any] | None:
        """T011: 自动抓取场景 — 从 pa_analysis_tasks 表读取预填字段。"""
        if not self._pa_service._db_manager:
            return None
        try:
            db = self._pa_service._db_manager
            conn = getattr(db, "conn", None) or getattr(db, "_conn", None)
            if conn is None:
                return None
            cursor = conn.execute(
                "SELECT jank_count, process_name, dimensions FROM pa_analysis_tasks "
                "WHERE trace_path = ? ORDER BY created_at DESC LIMIT 1",
                (trace_path,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            ctx: dict[str, Any] = {}
            if row[0] is not None:
                ctx["db_jank_count"] = row[0]
            if row[1]:
                ctx["db_process_name"] = row[1]
            if row[2]:
                try:
                    ctx["db_dimensions"] = json.loads(row[2])
                except (json.JSONDecodeError, TypeError):
                    ctx["db_dimensions"] = row[2]
            return ctx if ctx else None
        except Exception as exc:
            logger.debug("读取自动抓取预填字段失败: %s", exc)
            return None

    # ------------------------------------------------------------------
    # T009-T012 经验自动提取
    # ------------------------------------------------------------------

    def _extract_and_save_learnings(
        self,
        task_id: str,
        trace_path: str,
        routing: AnalysisRouting,
        analysis_output: AnalysisOutput | None,
    ) -> None:
        """T011/T012: 分析完成后自动提取经验并写入 DB（静默降级）。"""
        if not analysis_output or not analysis_output.root_causes:
            return
        try:
            from ..engine.storage import insert_learning

            db = self._pa_service._db_manager
            conn = getattr(db, "conn", None) or getattr(db, "_conn", None)
            if conn is None:
                return

            device_model = self._resolve_device_model(trace_path, conn)

            embedder = self._get_embedder()

            for rc in analysis_output.root_causes:
                learning = self._extract_single_learning(rc, analysis_output)
                confidence = self._calc_initial_confidence([rc])

                row_id = insert_learning(
                    conn=conn,
                    task_id=task_id,
                    trace_id=Path(trace_path).stem,
                    scene=analysis_output.scene or routing.scene,
                    root_cause_tags=learning["root_cause_tags"],
                    insight=learning["insight"],
                    device_model=device_model,
                    process_name=routing.process_name or None,
                    key_metrics=learning["key_metrics"],
                    confidence=confidence,
                )

                if embedder is not None and row_id:
                    self._save_learning_embedding(
                        conn, row_id, learning["insight"], embedder,
                    )

            logger.info(
                "经验提取完成: %d 条根因写入 pa_learnings",
                len(analysis_output.root_causes),
            )
        except Exception as exc:
            logger.debug("经验提取失败 (静默降级): %s", exc)

    @staticmethod
    def _get_embedder() -> Any:
        """尝试获取 embedder 实例（静默降级）。"""
        try:
            from .learnings_search import try_init_embedder
            return try_init_embedder()
        except Exception:
            return None

    @staticmethod
    def _save_learning_embedding(
        conn: Any, learning_id: int, text: str, embedder: Any,
    ) -> None:
        """生成 embedding 并写入 pa_learning_embeddings。"""
        try:
            from ..engine.storage import insert_learning_embedding
            from sqlite_vec import serialize_float32

            vec = embedder.encode(text)
            blob = serialize_float32(vec.tolist())
            insert_learning_embedding(conn, learning_id, blob)
        except Exception as exc:
            logger.debug("保存 embedding 失败 (静默降级): %s", exc)

    @staticmethod
    def _extract_single_learning(
        rc: RootCauseItem, ao: AnalysisOutput,
    ) -> dict[str, str]:
        """T009: 从单条 RootCauseItem 提取经验字段。"""
        tags = rc.tag
        insight = f"[{rc.severity}] {rc.qualitative}"
        if rc.reasoning:
            insight += f" | 推理: {rc.reasoning}"
        key_metrics = json.dumps(rc.quantitative, ensure_ascii=False) if rc.quantitative else None
        return {
            "root_cause_tags": tags,
            "insight": insight,
            "key_metrics": key_metrics or "",
        }

    @staticmethod
    def _calc_initial_confidence(root_causes: list[RootCauseItem]) -> float:
        """T010: 基于 severity 和 evidence 完整性计算初始置信度。"""
        if not root_causes:
            return 0.1
        severity_weights = {"CRITICAL": 0.9, "HIGH": 0.7, "WARNING": 0.5, "INFO": 0.3}
        max_severity = max(
            severity_weights.get(rc.severity, 0.3) for rc in root_causes
        )
        has_evidence = all(rc.evidence for rc in root_causes)
        return min(max_severity + (0.1 if has_evidence else 0), 1.0)

    @staticmethod
    def _resolve_device_model(
        trace_path: str, conn: Any = None,
    ) -> str | None:
        """从 trace 文件名解析设备型号，回退到 pa_analysis_tasks 表。

        文件名约定: {device}_{soc}_{date}_{time}.perfetto-trace
        """
        import re

        stem = Path(trace_path).stem
        match = re.match(r"^([A-Za-z0-9]+)_", stem)
        if match:
            candidate = match.group(1)
            if len(candidate) >= 3 and not candidate.isdigit():
                return candidate

        if conn is not None:
            try:
                cursor = conn.execute(
                    "SELECT device_model FROM pa_analysis_tasks "
                    "WHERE trace_path = ? ORDER BY created_at DESC LIMIT 1",
                    (trace_path,),
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return row[0]
            except Exception:
                pass
        return None

    @staticmethod
    def _build_known_info_block(prefetch_context: dict[str, Any]) -> str:
        """T009: 将预取结果格式化为 SubAgent prompt 中的"已知信息"区块。"""
        if not prefetch_context:
            return ""

        lines = ["## 已知信息（编排器预取）\n"]
        lines.append("以下数据已预先获取，无需重复调用对应工具：\n")

        for key, value in prefetch_context.items():
            if isinstance(value, dict):
                summary_parts = []
                for k, v in list(value.items())[:8]:
                    if isinstance(v, (list, dict)):
                        summary_parts.append(f"  - {k}: {json.dumps(v, ensure_ascii=False)[:200]}")
                    else:
                        summary_parts.append(f"  - {k}: {v}")
                lines.append(f"### {key}\n" + "\n".join(summary_parts))
            elif isinstance(value, (int, float, str)):
                lines.append(f"- **{key}**: {value}")
            else:
                lines.append(f"- **{key}**: {str(value)[:200]}")

        lines.append("")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # G2: 相似案例检索与注入
    # ------------------------------------------------------------------

    def _search_similar_cases(
        self,
        routing: AnalysisRouting,
        prefetch_context: dict[str, Any],
        on_stream: Callable | None,
    ) -> list[int]:
        """T012/T014: 检索相似案例，格式化后注入 prefetch_context。返回 injected_ids。"""
        try:
            db = self._pa_service._db_manager
            conn = getattr(db, "conn", None) or getattr(db, "_conn", None)
            if conn is None:
                return []

            from .learnings_search import LearningsSearcher, try_init_embedder

            embedder = try_init_embedder()
            searcher = LearningsSearcher(conn, embedder)

            issue_tags = self._extract_issue_tags_from_prefetch(prefetch_context)

            results = searcher.search(
                scene=routing.scene,
                process_name=routing.process_name,
                issue_tags=issue_tags,
                limit=3,
            )

            if not results:
                return []

            if on_stream:
                on_stream("system", f"📚 检索到 {len(results)} 条历史分析参考")

            learnings_block = self._format_learnings_block(results)
            prefetch_context["historical_learnings"] = learnings_block

            return [r["id"] for r in results]

        except Exception as exc:
            logger.debug("相似案例检索失败 (静默降级): %s", exc)
            return []

    @staticmethod
    def _extract_issue_tags_from_prefetch(
        prefetch_context: dict[str, Any],
    ) -> list[str]:
        """T011: 从预取结果中提取 issue 标签。"""
        tags: list[str] = []

        jank_data = prefetch_context.get("jank_frames") or prefetch_context.get("jank_detect")
        if isinstance(jank_data, dict):
            jank_records = (
                jank_data.get("jank_records")
                or jank_data.get("parse_result", {}).get("jank_records", [])
            )
            if isinstance(jank_records, list):
                for jr in jank_records[:5]:
                    jt = jr.get("jank_type", "") if isinstance(jr, dict) else ""
                    if jt and jt not in tags:
                        tags.append(jt)

        for key, value in prefetch_context.items():
            if isinstance(value, dict) and "issues" in value:
                issues = value["issues"]
                if isinstance(issues, list):
                    for issue in issues[:5]:
                        tag = ""
                        if isinstance(issue, dict):
                            tag = issue.get("type") or issue.get("tag", "")
                        if tag and tag not in tags:
                            tags.append(tag)

        return tags

    @staticmethod
    def _format_learnings_block(learnings: list[dict]) -> str:
        """T013: 格式化历史案例为 Markdown 注入区块。"""
        if not learnings:
            return ""

        lines = [
            "### 历史分析参考（仅供参考，以当前 trace 数据为准）\n",
        ]
        for i, lr in enumerate(learnings, 1):
            conf = lr.get("confidence", 0)
            hits = lr.get("hit_count", 0)
            method = lr.get("retrieval_method", "exact")
            method_label = " (语义召回)" if method == "semantic" else ""

            promoted_label = " [已验证]" if lr.get("promoted") else ""
            lines.append(f"#### 案例 {i}{promoted_label} (置信度 {conf:.1f}, 命中 {hits} 次{method_label})")
            lines.append(f"- 场景: {lr.get('scene', '')} | 进程: {lr.get('process_name', '')}")
            lines.append(f"- 根因: {lr.get('root_cause_tags', '')}")

            insight = lr.get("insight", "")
            if len(insight) > 500:
                insight = insight[:500] + "..."
            lines.append(f"- 经验: {insight}")

            metrics = lr.get("key_metrics", "")
            if metrics:
                lines.append(f"- 关键指标: {metrics}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # G3: 经验库自动维护
    # ------------------------------------------------------------------

    async def _maybe_trigger_maintenance(self) -> None:
        """T006/T012: 每 20 次分析后自动触发淘汰 + 晋升。"""
        try:
            db = self._pa_service._db_manager
            conn = getattr(db, "conn", None) or getattr(db, "_conn", None)
            if conn is None:
                return

            from .learnings_manager import (
                evict_low_score_learnings,
                promote_learnings,
                record_maintenance_telemetry,
                should_trigger_maintenance,
            )

            if not should_trigger_maintenance(conn):
                return

            logger.info("触发经验库自动维护 (auto_20)")
            evict_result = evict_low_score_learnings(conn)

            promote_result: dict = {"promoted": 0, "merged": 0, "archived": 0}
            if hasattr(self, "_llm_manager") and self._llm_manager:
                promote_result = await promote_learnings(conn, self._llm_manager)

            record_maintenance_telemetry(conn, "auto_20", evict_result, promote_result)
            logger.info(
                "经验库维护完成: 淘汰 %d, 晋升 %d, 合并 %d",
                evict_result.get("archived", 0),
                promote_result.get("promoted", 0),
                promote_result.get("merged", 0),
            )
        except Exception as exc:
            logger.warning("经验库自动维护失败 (静默降级): %s", exc)

    def _update_injected_hit_counts(
        self,
        injected_ids: list[int],
        analysis_output: AnalysisOutput | None,
    ) -> None:
        """T015/T016: 分析完成后更新被引用案例的 hit_count。"""
        if not injected_ids or not analysis_output or not analysis_output.root_causes:
            return
        try:
            db = self._pa_service._db_manager
            conn = getattr(db, "conn", None) or getattr(db, "_conn", None)
            if conn is None:
                return

            from .learnings_search import LearningsSearcher

            searcher = LearningsSearcher(conn)
            conclusion_tags = {rc.tag for rc in analysis_output.root_causes}
            updated = searcher.update_hit_counts(injected_ids, conclusion_tags)
            if updated > 0:
                logger.info("更新 %d 条历史案例的 hit_count", updated)
        except Exception as exc:
            logger.debug("更新 hit_count 失败 (静默降级): %s", exc)
