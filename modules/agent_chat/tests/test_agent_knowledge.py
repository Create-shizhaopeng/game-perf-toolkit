# -*- coding: utf-8 -*-
"""agent_chat 模块 — ReportIndex 测试。"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.agent_chat.src.knowledge.report_index import ReportIndex


# ---------------------------------------------------------------------------
# ReportIndex
# ---------------------------------------------------------------------------

class TestReportIndexEmpty:

    def test_no_reports_returns_empty(self):
        ri = ReportIndex()
        with patch.object(ri, "_scan_all_reports", return_value=[]):
            assert ri.get_recent_summaries() == []
            assert ri.get_context_text() == ""


class TestReportIndexScanTrace:

    def _setup_trace_dir(self, tmp_path: Path, name: str = "test_trace", summary_data: dict | None = None) -> Path:
        trace_dir = tmp_path / name
        trace_dir.mkdir()
        if summary_data is not None:
            (trace_dir / "summary_data.json").write_text(
                json.dumps(summary_data, ensure_ascii=False), encoding="utf-8"
            )
        else:
            (trace_dir / "test_report.md").write_text("# Report", encoding="utf-8")
        return trace_dir

    def test_scan_trace_with_summary_json(self, tmp_path: Path):
        self._setup_trace_dir(tmp_path, summary_data={
            "jank_count": 5,
            "frame_count": 1000,
            "dimensions_completed": ["cpu", "binder"],
        })

        ri = ReportIndex()
        with patch.object(ri, "_get_trace_report_dir", return_value=tmp_path):
            reports = ri._scan_trace_reports()

        assert len(reports) == 1
        assert reports[0]["source"] == "perfetto"
        assert "5" in reports[0]["summary"]
        assert "1000" in reports[0]["summary"]

    def test_scan_trace_with_report_md_only(self, tmp_path: Path):
        self._setup_trace_dir(tmp_path)

        ri = ReportIndex()
        with patch.object(ri, "_get_trace_report_dir", return_value=tmp_path):
            reports = ri._scan_trace_reports()

        assert len(reports) == 1
        assert reports[0]["summary"] == "有分析报告"

    def test_scan_trace_empty_dir(self, tmp_path: Path):
        ri = ReportIndex()
        with patch.object(ri, "_get_trace_report_dir", return_value=tmp_path):
            assert ri._scan_trace_reports() == []

    def test_scan_trace_nonexistent_dir(self):
        ri = ReportIndex()
        with patch.object(ri, "_get_trace_report_dir", return_value=None):
            assert ri._scan_trace_reports() == []

    def test_scan_trace_bad_json(self, tmp_path: Path):
        trace_dir = tmp_path / "bad_trace"
        trace_dir.mkdir()
        (trace_dir / "summary_data.json").write_text("NOT JSON", encoding="utf-8")

        ri = ReportIndex()
        with patch.object(ri, "_get_trace_report_dir", return_value=tmp_path):
            reports = ri._scan_trace_reports()

        assert len(reports) == 1
        assert reports[0]["summary"] == "有分析报告"

    def test_scan_skips_files_not_dirs(self, tmp_path: Path):
        (tmp_path / "random_file.txt").write_text("hi", encoding="utf-8")
        ri = ReportIndex()
        with patch.object(ri, "_get_trace_report_dir", return_value=tmp_path):
            assert ri._scan_trace_reports() == []

    def test_scan_trace_alternative_keys(self, tmp_path: Path):
        """summary_data.json 可能使用不同的键名。"""
        self._setup_trace_dir(tmp_path, summary_data={
            "jank_times": 8,
            "frame_num": 2000,
        })

        ri = ReportIndex()
        with patch.object(ri, "_get_trace_report_dir", return_value=tmp_path):
            reports = ri._scan_trace_reports()

        assert "8" in reports[0]["summary"]


class TestReportIndexContextText:

    def test_context_text_format(self):
        ri = ReportIndex()
        fake_reports = [
            {
                "source": "perfetto",
                "name": "trace_001",
                "date": "2026-03-20 10:00",
                "summary": "丢帧5/1000帧",
                "mtime": 1000,
            }
        ]
        with patch.object(ri, "_scan_all_reports", return_value=fake_reports):
            text = ri.get_context_text(top_n=5)

        assert "最近分析报告" in text
        assert "perfetto" in text
        assert "trace_001" in text

    def test_context_text_respects_top_n(self):
        ri = ReportIndex()
        fake_reports = [
            {"source": "p", "name": f"r{i}", "date": "d", "summary": "s", "mtime": i}
            for i in range(10)
        ]
        with patch.object(ri, "_scan_all_reports", return_value=fake_reports):
            text = ri.get_context_text(top_n=3)

        assert text.count(". [") == 3


class TestReportIndexMaxReports:

    def test_max_reports_limit(self, tmp_path: Path):
        ri = ReportIndex(max_reports=3)
        for i in range(5):
            td = tmp_path / f"trace_{i}"
            td.mkdir()
            (td / "test_report.md").write_text("# R", encoding="utf-8")

        with patch.object(ri, "_get_trace_report_dir", return_value=tmp_path):
            reports = ri._scan_all_reports()

        assert len(reports) <= 3


class TestReportIndexSorting:

    def test_recent_summaries_sorted_by_mtime(self):
        ri = ReportIndex()
        fake = [
            {"source": "p", "name": "old", "date": "d", "summary": "s", "mtime": 100},
            {"source": "p", "name": "new", "date": "d", "summary": "s", "mtime": 999},
            {"source": "p", "name": "mid", "date": "d", "summary": "s", "mtime": 500},
        ]
        with patch.object(ri, "_scan_all_reports", return_value=fake):
            result = ri.get_recent_summaries(top_n=2)

        assert result[0]["name"] == "new"
        assert result[1]["name"] == "mid"
