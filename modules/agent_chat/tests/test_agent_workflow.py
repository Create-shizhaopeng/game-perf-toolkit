# -*- coding: utf-8 -*-
"""agent_chat 模块 — WorkflowTracker + SOP Generator 测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from modules.agent_chat.src.models import ToolCall, ToolCallStatus, ToolResult
from modules.agent_chat.src.workflow.tracker import WorkflowTracker


# ---------------------------------------------------------------------------
# WorkflowTracker
# ---------------------------------------------------------------------------

class TestWorkflowTrackerBasic:

    def test_empty_tracker(self):
        tracker = WorkflowTracker()
        assert tracker.tool_count == 0
        assert tracker.unique_tools_used == set()
        assert not tracker.check_deposit_condition()

    def test_record_single_tool_call(self):
        tracker = WorkflowTracker()
        tc = ToolCall(id="c1", name="pa_analyze", arguments={"path": "/tmp/t.perfetto-trace"})
        tr = ToolResult(tool_call_id="c1", content="分析完成: 3 jank events")
        tracker.record_tool_call(tc, tr, elapsed_ms=1500)

        assert tracker.tool_count == 1
        assert "pa_analyze" in tracker.unique_tools_used
        assert tracker.trace.steps[0].tool_name == "pa_analyze"
        assert "分析完成" in tracker.trace.steps[0].result_summary

    def test_record_multiple_tools(self):
        tracker = WorkflowTracker()
        for name in ["pa_analyze", "pdi_load_report", "gp_analyze_config"]:
            tc = ToolCall(id=f"c_{name}", name=name)
            tr = ToolResult(tool_call_id=tc.id, content="ok")
            tracker.record_tool_call(tc, tr)

        assert tracker.tool_count == 3
        assert len(tracker.unique_tools_used) == 3

    def test_error_result_summary(self):
        tracker = WorkflowTracker()
        tc = ToolCall(id="c1", name="failing")
        tr = ToolResult(tool_call_id="c1", content="文件未找到", is_error=True)
        tracker.record_tool_call(tc, tr)

        assert "[ERROR]" in tracker.trace.steps[0].result_summary

    def test_result_summary_truncation(self):
        tracker = WorkflowTracker()
        tc = ToolCall(id="c1", name="big_tool")
        tr = ToolResult(tool_call_id="c1", content="X" * 500)
        tracker.record_tool_call(tc, tr)

        assert len(tracker.trace.steps[0].result_summary) <= 200

    def test_record_user_decision(self):
        tracker = WorkflowTracker()
        tracker.record_user_decision("选择完整分析模式")
        assert "选择完整分析模式" in tracker.trace.user_decisions


class TestWorkflowDepositCondition:

    def test_no_sop_fewer_than_2_tools_no_deposit(self):
        tracker = WorkflowTracker()
        tc = ToolCall(id="c1", name="pa_analyze")
        tr = ToolResult(tool_call_id="c1", content="ok")
        tracker.record_tool_call(tc, tr)

        assert not tracker.check_deposit_condition()

    def test_no_sop_2_unique_tools_triggers_deposit(self):
        tracker = WorkflowTracker()
        for name in ["pa_analyze", "pdi_summarize"]:
            tc = ToolCall(id=f"c_{name}", name=name)
            tr = ToolResult(tool_call_id=tc.id, content="ok")
            tracker.record_tool_call(tc, tr)

        assert tracker.check_deposit_condition()

    def test_no_sop_duplicate_tool_no_deposit(self):
        tracker = WorkflowTracker()
        for i in range(3):
            tc = ToolCall(id=f"c_{i}", name="pa_analyze")
            tr = ToolResult(tool_call_id=tc.id, content="ok")
            tracker.record_tool_call(tc, tr)

        assert not tracker.check_deposit_condition()

    def test_with_sop_no_deviation_no_deposit(self):
        tracker = WorkflowTracker(sop_name="trace_analysis")
        tracker.set_sop_tools(["pa_analyze"])

        tc = ToolCall(id="c1", name="pa_analyze")
        tr = ToolResult(tool_call_id="c1", content="ok")
        tracker.record_tool_call(tc, tr)

        assert not tracker.check_deposit_condition()

    def test_with_sop_extra_tool_triggers_deposit(self):
        tracker = WorkflowTracker(sop_name="trace_analysis")
        tracker.set_sop_tools(["pa_analyze"])

        for name in ["pa_analyze", "pdi_summarize"]:
            tc = ToolCall(id=f"c_{name}", name=name)
            tr = ToolResult(tool_call_id=tc.id, content="ok")
            tracker.record_tool_call(tc, tr)

        assert tracker.check_deposit_condition()
        assert "额外工具" in tracker.trace.sop_deviation

    def test_with_sop_missing_tool_triggers_deposit(self):
        tracker = WorkflowTracker(sop_name="jank_comprehensive")
        tracker.set_sop_tools(["pa_analyze", "pdi_summarize", "gp_analyze_config"])

        tc = ToolCall(id="c1", name="pa_analyze")
        tr = ToolResult(tool_call_id="c1", content="ok")
        tracker.record_tool_call(tc, tr)

        assert tracker.check_deposit_condition()
        assert "跳过工具" in tracker.trace.sop_deviation

    def test_deviation_empty_when_no_sop_tools_set(self):
        tracker = WorkflowTracker(sop_name="some_sop")
        tc = ToolCall(id="c1", name="pa_analyze")
        tr = ToolResult(tool_call_id="c1", content="ok")
        tracker.record_tool_call(tc, tr)

        assert not tracker.check_deposit_condition()


class TestWorkflowSummary:

    def test_summary_structure(self):
        tracker = WorkflowTracker(sop_name="trace_sop")
        for name in ["pa_analyze", "pdi_summarize"]:
            tc = ToolCall(id=f"c_{name}", name=name, arguments={"path": "/tmp"})
            tr = ToolResult(tool_call_id=tc.id, content="ok")
            tracker.record_tool_call(tc, tr)
        tracker.record_user_decision("确认继续")

        summary = tracker.get_workflow_summary()

        assert summary["original_sop"] == "trace_sop"
        assert summary["total_steps"] == 2
        assert sorted(summary["unique_tools"]) == ["pa_analyze", "pdi_summarize"]
        assert summary["tool_sequence"] == ["pa_analyze", "pdi_summarize"]
        assert "确认继续" in summary["user_decisions"]
        assert len(summary["steps"]) == 2
        assert "path" in summary["steps"][0]["args_keys"]


# ---------------------------------------------------------------------------
# SOP Generator
# ---------------------------------------------------------------------------

from modules.agent_chat.src.workflow.generator import (
    generate_sop_from_trace,
    save_sop,
    _generate_title,
    _extract_keywords,
    _title_to_filename,
    _tool_step_description,
)


class TestSOPGeneration:

    def _make_summary(self, tools: list[str] | None = None) -> dict:
        tools = tools or ["pa_analyze", "pdi_summarize"]
        return {
            "original_sop": "",
            "total_steps": 2,
            "unique_tools": tools,
            "tool_sequence": tools,
            "user_decisions": [],
            "sop_deviation": "",
            "steps": [
                {"tool": t, "args_keys": ["path"], "result_preview": "ok"}
                for t in tools
            ],
        }

    def test_generate_contains_frontmatter(self):
        content = generate_sop_from_trace(self._make_summary())
        assert content.startswith("---")
        assert "title:" in content
        assert "keywords:" in content
        assert "required_tools:" in content
        assert "generated_at:" in content
        assert "source: auto_generated" in content

    def test_generate_contains_steps(self):
        content = generate_sop_from_trace(self._make_summary())
        assert "## 分析步骤" in content
        assert "步骤 1" in content
        assert "pa_analyze" in content

    def test_generate_with_custom_title(self):
        content = generate_sop_from_trace(
            self._make_summary(), title="自定义标题"
        )
        assert "title: 自定义标题" in content
        assert "# 自定义标题" in content

    def test_generate_contains_toc(self):
        content = generate_sop_from_trace(self._make_summary())
        assert "## 目录" in content
        assert "[概述](#概述)" in content

    def test_generate_contains_notice(self):
        content = generate_sop_from_trace(self._make_summary())
        assert "注意事项" in content
        assert "自动生成" in content


class TestSOPSave:

    def test_save_creates_file(self, tmp_path: Path):
        content = "---\ntitle: 测试\n---\n# 测试"
        path = save_sop(content, tmp_path)
        assert path.exists()
        assert path.read_text(encoding="utf-8") == content

    def test_save_with_explicit_filename(self, tmp_path: Path):
        content = "# Test"
        path = save_sop(content, tmp_path, filename="my_sop.md")
        assert path.name == "my_sop.md"

    def test_save_adds_md_extension(self, tmp_path: Path):
        path = save_sop("# Test", tmp_path, filename="no_ext")
        assert path.suffix == ".md"

    def test_save_conflict_renames(self, tmp_path: Path):
        save_sop("first", tmp_path, filename="dup.md")
        path2 = save_sop("second", tmp_path, filename="dup.md")
        assert path2.name == "dup_2.md"

    def test_save_creates_directory(self, tmp_path: Path):
        deep_dir = tmp_path / "a" / "b" / "c"
        path = save_sop("# Test", deep_dir, filename="test.md")
        assert path.exists()

    def test_save_auto_filename_from_title(self, tmp_path: Path):
        content = "---\ntitle: Trace分析 + PerfDog\n---\n# SOP"
        path = save_sop(content, tmp_path)
        assert path.exists()
        assert path.suffix == ".md"


class TestHelperFunctions:

    def test_generate_title_known_tools(self):
        title = _generate_title(["pa_analyze", "pdi_load_report"])
        assert "Trace分析" in title
        assert "PerfDog" in title

    def test_generate_title_unknown_tools(self):
        title = _generate_title(["custom_tool"])
        assert "custom_tool" in title

    def test_generate_title_empty(self):
        title = _generate_title([])
        assert "自定义" in title

    def test_generate_title_truncates_at_3(self):
        tools = ["pa_analyze", "pdi_load_report", "gp_analyze_config", "device_status"]
        title = _generate_title(tools)
        assert "工作流" in title

    def test_extract_keywords_pa(self):
        kws = _extract_keywords(["pa_analyze"])
        assert "trace" in kws
        assert "perfetto" in kws

    def test_extract_keywords_unknown(self):
        kws = _extract_keywords(["unknown_tool"])
        assert kws == ["自定义"]

    def test_title_to_filename(self):
        assert _title_to_filename("Trace分析 + PerfDog") != ""
        assert _title_to_filename("") == "custom_workflow"
        name = _title_to_filename("A" * 100)
        assert len(name) <= 50

    def test_tool_step_description_known(self):
        desc = _tool_step_description("pa_analyze", ["path"])
        assert "Perfetto" in desc or "Trace" in desc

    def test_tool_step_description_unknown(self):
        desc = _tool_step_description("custom_x", [])
        assert "custom_x" in desc
