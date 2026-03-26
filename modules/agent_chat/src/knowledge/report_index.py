# -*- coding: utf-8 -*-
"""历史报告索引 — 扫描输出目录提取报告摘要。"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MAX_REPORTS = 20


class ReportIndex:
    """扫描和索引历史分析报告。"""

    def __init__(self, max_reports: int = _MAX_REPORTS) -> None:
        self._max_reports = max_reports

    def get_recent_summaries(self, top_n: int = 5) -> list[dict[str, Any]]:
        """获取最近 N 份报告摘要。"""
        all_reports = self._scan_all_reports()
        all_reports.sort(key=lambda r: r.get("mtime", 0), reverse=True)
        return all_reports[:top_n]

    def get_context_text(self, top_n: int = 5) -> str:
        """生成可注入 system prompt 的历史报告上下文。"""
        reports = self.get_recent_summaries(top_n)
        if not reports:
            return ""

        lines = ["最近分析报告:"]
        for i, r in enumerate(reports, 1):
            source = r.get("source", "unknown")
            name = r.get("name", "")
            date = r.get("date", "")
            summary = r.get("summary", "")
            lines.append(f"  {i}. [{source}] {name} ({date}): {summary}")

        return "\n".join(lines)

    def _scan_all_reports(self) -> list[dict[str, Any]]:
        """扫描所有模块的报告目录。"""
        reports: list[dict[str, Any]] = []
        reports.extend(self._scan_trace_reports())
        reports.extend(self._scan_perfdog_reports())
        return reports[:self._max_reports]

    def _scan_trace_reports(self) -> list[dict[str, Any]]:
        """扫描 Perfetto trace 分析报告。"""
        report_dir = self._get_trace_report_dir()
        if not report_dir or not report_dir.exists():
            return []

        results: list[dict[str, Any]] = []
        for trace_dir in report_dir.iterdir():
            if not trace_dir.is_dir():
                continue

            summary = self._parse_trace_summary(trace_dir)
            if summary:
                results.append(summary)

        return results

    def _parse_trace_summary(self, trace_dir: Path) -> dict[str, Any] | None:
        """从 trace 报告目录提取摘要。"""
        summary_file = trace_dir / "summary_data.json"
        report_md = None
        for f in trace_dir.glob("*_report.md"):
            report_md = f
            break

        if not report_md and not summary_file.exists():
            return None

        mtime = trace_dir.stat().st_mtime
        date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

        info: dict[str, Any] = {
            "source": "perfetto",
            "name": trace_dir.name,
            "date": date_str,
            "mtime": mtime,
            "path": str(trace_dir),
        }

        if summary_file.exists():
            try:
                data = json.loads(summary_file.read_text(encoding="utf-8"))
                jank = data.get("jank_count", data.get("jank_times", "?"))
                frames = data.get("frame_count", data.get("frame_num", "?"))
                dims = data.get("dimensions_completed", [])
                info["summary"] = f"丢帧{jank}/{frames}帧, 维度:{','.join(dims) if dims else 'N/A'}"
            except Exception:
                info["summary"] = "有分析报告"
        else:
            info["summary"] = "有分析报告"

        return info

    def _scan_perfdog_reports(self) -> list[dict[str, Any]]:
        """PerfDog 报告不写入独立目录，此处占位留待扩展。"""
        return []

    def _get_trace_report_dir(self) -> Path | None:
        """获取 trace 报告目录路径。"""
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent / "output" / "trace_report"

        candidates = [
            Path(__file__).resolve().parent.parent.parent.parent.parent
            / "data" / "output" / "trace_report",
            Path(__file__).resolve().parent.parent.parent.parent.parent.parent
            / "data" / "output" / "trace_report",
        ]
        for c in candidates:
            if c.exists():
                return c

        return candidates[0] if candidates else None
