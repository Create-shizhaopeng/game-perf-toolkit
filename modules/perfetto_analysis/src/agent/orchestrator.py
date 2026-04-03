"""分析编排器 — 管理 Main/Sub/Review Agent 生命周期。"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from . import (
    AnalysisConfig,
    AnalysisReport,
    AnalysisRouting,
    AnalysisStatus,
    AnalysisTask,
    AgentRole,
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
        config: AnalysisConfig | None = None,
        output_base: str = "",
        package_db: Any = None,
    ) -> None:
        self._llm_manager = llm_manager
        self._pa_service = pa_service
        self._config = config or AnalysisConfig()
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

            _notify_status(AnalysisStatus.ANALYZING, f"场景: {routing.scene}")

            result = await asyncio.wait_for(
                self._run_sub_agent(
                    trace_path,
                    routing,
                    _notify_stream,
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

        if len(reports) > 1 and not self._abort_flag:
            if on_status:
                on_status("batch", AnalysisStatus.REVIEWING, "交叉评审中...")
            await self._run_review(reports, on_stream)

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

            agent = create_main_agent(self._get_model())
            prompt = (
                f"用户意图: {user_intent}\n"
                f"Trace 路径: {trace_path}\n"
                f"目标进程: {process_name or '未指定'}\n"
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

    async def _run_sub_agent(
        self,
        trace_path: str,
        routing: AnalysisRouting,
        on_stream: Callable | None,
    ) -> dict:
        """SubAgent: 使用 pa_* 工具执行分析。"""
        try:
            from .agents import create_sub_agent
            from .prompts import load_sop

            if on_stream:
                on_stream("system", f"🔬 正在加载 {routing.scene} 场景 SOP...")

            sop_content = load_sop(routing.scene)

            from .tools import set_tool_stream_callback
            set_tool_stream_callback(on_stream)

            agent = create_sub_agent(self._get_model(), sop_content, self._pa_service)

            if on_stream:
                on_stream("system", "🔧 SubAgent 已创建，开始分析...")

            prompt = (
                f"请按照 SOP 分析以下 trace，并输出**人类可读的中文分析报告**:\n"
                f"- Trace 路径: {trace_path}\n"
                f"- 目标进程: {routing.process_name or '自动检测'}\n"
                f"- 分析场景: {routing.scene}\n\n"
                f"报告格式要求:\n"
                f"1. **问题概述**: 简要描述发现的问题\n"
                f"2. **根因分析**: 列出每个根因的详细分析和证据\n"
                f"3. **关键数据**: 提供支撑结论的量化数据\n"
                f"4. **优化建议**: 给出具体可操作的优化方案\n"
            )
            result = await agent.run(prompt)

            output = result.output if hasattr(result, "output") else str(result)
            conclusion = str(output) if output else "分析完成，未生成结论。"

            token_used = 0
            if hasattr(result, "usage") and result.usage:
                usage = result.usage
                if hasattr(usage, "total_tokens"):
                    token_used = usage.total_tokens
                elif isinstance(usage, dict):
                    token_used = usage.get("total_tokens", 0)

            set_tool_stream_callback(None)

            if on_stream and conclusion:
                preview = conclusion[:600]
                if len(conclusion) > 600:
                    preview += "...\n(完整结论见报告)"
                on_stream("assistant", f"📊 分析结论:\n\n{preview}")

            return {"conclusion": conclusion, "token_used": token_used}

        except ImportError:
            logger.warning("Pydantic AI 未安装，使用引擎直接分析")
            return await self._fallback_engine_analysis(trace_path, routing)

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

    async def _run_review(
        self,
        reports: list[AnalysisReport],
        on_stream: Callable | None,
    ) -> None:
        """ReviewAgent: 对多个分析结论做交叉评审。"""
        try:
            from .agents import create_review_agent

            agent = create_review_agent(self._get_model())
            summaries = "\n\n".join(
                f"## Trace {i+1}\n{r.summary}" for i, r in enumerate(reports) if r.summary
            )
            if not summaries:
                return
            result = await agent.run(f"请交叉评审以下分析结论:\n{summaries}")
            if on_stream:
                review_text = result.output if hasattr(result, "output") else str(result)
                on_stream("batch", "assistant", f"📋 评审结论:\n{review_text}")
        except ImportError:
            logger.warning("Pydantic AI 未安装，跳过 Review")

    async def _generate_report(
        self,
        task_id: str,
        trace_path: str,
        routing: AnalysisRouting,
        result: dict,
    ) -> AnalysisReport:
        """生成 HTML 报告。"""
        from .report import generate_html_report

        trace_stem = Path(trace_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = os.path.join(self._output_base, f"{trace_stem}_{timestamp}")

        report = generate_html_report(
            task_id=task_id,
            result_dir=result_dir,
            trace_path=trace_path,
            scene=routing.scene,
            process_name=routing.process_name,
            conclusion=result.get("conclusion", ""),
            raw_data=result,
        )
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

    def _learn_package(self, trace_path: str, process_name: str) -> None:
        """分析完成后学习包名映射。"""
        if not self._package_db or not process_name:
            return
        try:
            package = process_name.split(":")[0]
            self._package_db.learn(package, process_name)
        except Exception:
            pass
