# -*- coding: utf-8 -*-
"""G5 Skill 知识层级应用 — 单元测试。"""

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.tools import (
    _build_toc_summary,
    _extract_section_by_anchor,
    _heading_to_anchor,
    _normalize_anchor,
)


# ---------------------------------------------------------------------------
# _heading_to_anchor
# ---------------------------------------------------------------------------
class TestHeadingToAnchor(unittest.TestCase):
    def test_simple_heading(self):
        self.assertEqual(_heading_to_anchor("## Hello World"), "hello-world")

    def test_triple_hash(self):
        self.assertEqual(_heading_to_anchor("### Foo Bar"), "foo-bar")

    def test_chinese_punctuation_removed(self):
        self.assertEqual(
            _heading_to_anchor("## 功能概述：主要说明"),
            "功能概述主要说明",
        )

    def test_em_dash_replaced(self):
        anchor = _heading_to_anchor("### IO Block — 文件未 pin 到内存")
        self.assertIn("io-block", anchor)
        self.assertIn("pin", anchor)
        self.assertNotIn("—", anchor)

    def test_en_dash_replaced(self):
        anchor = _heading_to_anchor("## A–B 测试")
        self.assertNotIn("–", anchor)

    def test_lowercase(self):
        self.assertEqual(_heading_to_anchor("## CPU Freq"), "cpu-freq")

    def test_multiple_spaces(self):
        self.assertEqual(
            _heading_to_anchor("##   multi   space  "),
            "multi-space",
        )


# ---------------------------------------------------------------------------
# _normalize_anchor
# ---------------------------------------------------------------------------
class TestNormalizeAnchor(unittest.TestCase):
    def test_collapse_hyphens(self):
        self.assertEqual(_normalize_anchor("a---b"), "a-b")

    def test_strip_edges(self):
        self.assertEqual(_normalize_anchor("-hello-"), "hello")

    def test_already_clean(self):
        self.assertEqual(_normalize_anchor("abc-def"), "abc-def")

    def test_empty(self):
        self.assertEqual(_normalize_anchor(""), "")


# ---------------------------------------------------------------------------
# _build_toc_summary
# ---------------------------------------------------------------------------
class TestBuildTocSummary(unittest.TestCase):
    def test_h2_with_summary(self):
        md = textwrap.dedent("""\
            # Title
            ## Section One
            First line of section one.
            More text.
            ## Section Two
            Second section content.
        """)
        toc = _build_toc_summary(md)
        self.assertIn("## Section One — First line of section one.", toc)
        self.assertIn("## Section Two — Second section content.", toc)

    def test_h3_included(self):
        md = "### Sub Section\nDetail here."
        toc = _build_toc_summary(md)
        self.assertIn("### Sub Section — Detail here.", toc)

    def test_heading_without_body(self):
        md = "## Empty Heading\n## Next Heading\nContent."
        toc = _build_toc_summary(md)
        self.assertIn("## Empty Heading", toc)
        lines = toc.strip().split("\n")
        empty_line = [l for l in lines if "Empty Heading" in l][0]
        self.assertNotIn("—", empty_line)

    def test_summary_truncated_at_80(self):
        long_line = "A" * 120
        md = f"## Heading\n{long_line}\n"
        toc = _build_toc_summary(md)
        summary_part = toc.split("— ")[1]
        self.assertEqual(len(summary_part), 80)

    def test_empty_content(self):
        self.assertEqual(_build_toc_summary(""), "")

    def test_h1_ignored(self):
        md = "# Title Only\nSome text."
        toc = _build_toc_summary(md)
        self.assertEqual(toc, "")

    def test_blank_lines_skipped(self):
        md = "## Heading\n\n\nFirst real line."
        toc = _build_toc_summary(md)
        self.assertIn("First real line.", toc)


# ---------------------------------------------------------------------------
# _extract_section_by_anchor
# ---------------------------------------------------------------------------
class TestExtractSectionByAnchor(unittest.TestCase):
    SAMPLE_MD = textwrap.dedent("""\
        # Root
        ## Alpha
        Alpha content line 1.
        Alpha content line 2.
        ## Beta
        Beta content.
        ### Beta Sub
        Sub content.
        ## Gamma
        Gamma content.
    """)

    def test_extract_h2(self):
        section = _extract_section_by_anchor(self.SAMPLE_MD, "alpha")
        self.assertIn("## Alpha", section)
        self.assertIn("Alpha content line 1.", section)
        self.assertNotIn("## Beta", section)

    def test_extract_h3(self):
        section = _extract_section_by_anchor(self.SAMPLE_MD, "beta-sub")
        self.assertIn("### Beta Sub", section)
        self.assertIn("Sub content.", section)
        self.assertNotIn("## Gamma", section)

    def test_extract_last_section(self):
        section = _extract_section_by_anchor(self.SAMPLE_MD, "gamma")
        self.assertIn("## Gamma", section)
        self.assertIn("Gamma content.", section)

    def test_anchor_not_found(self):
        section = _extract_section_by_anchor(self.SAMPLE_MD, "nonexistent")
        self.assertEqual(section, "")

    def test_em_dash_fuzzy_match(self):
        md = "### IO Block — 文件未 pin 到内存\nSome IO content."
        section = _extract_section_by_anchor(md, "io-block--文件未-pin-到内存")
        self.assertIn("IO Block", section)
        self.assertIn("Some IO content.", section)

    def test_case_insensitive(self):
        md = "## CPU Freq\nFrequency data."
        section = _extract_section_by_anchor(md, "CPU-FREQ")
        self.assertIn("CPU Freq", section)


# ---------------------------------------------------------------------------
# pa_read_knowledge — integration tests
# ---------------------------------------------------------------------------
class TestPaReadKnowledge(unittest.TestCase):
    """使用临时目录模拟 Skills 目录结构测试 pa_read_knowledge。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._skills = Path(cls._tmpdir.name) / "skills" / "perfetto-analysis"
        patterns_dir = cls._skills / "patterns"
        patterns_dir.mkdir(parents=True)

        (patterns_dir / "root-cause-patterns.md").write_text(
            textwrap.dedent("""\
                # Root Cause Patterns
                ## CPU 调度抢占
                当进程被高优先级任务抢占时…
                ## GPU 负载过高
                GPU 渲染管线瓶颈…
            """),
            encoding="utf-8",
        )

        sop_dir = cls._skills / "sop"
        sop_dir.mkdir(parents=True)
        (sop_dir / "jank-analysis.md").write_text(
            "# Jank SOP\n## Step 1\nDo this.\n## Step 2\nDo that.\n",
            encoding="utf-8",
        )

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    _PATCH_TARGET = "src.agent.tools._SKILLS_DIR"

    def _build_tool(self):
        """构建 pa_read_knowledge 工具，将 _SKILLS_DIR 指向临时目录。"""
        mock_service = MagicMock()
        with patch(self._PATCH_TARGET, self._skills):
            from src.agent.tools import build_analysis_tools
            tools = build_analysis_tools(mock_service)
            read_knowledge = [t for t in tools if getattr(t, "__name__", "") == "pa_read_knowledge"]
            self.assertTrue(read_knowledge, "pa_read_knowledge should be in tools list")
            return read_knowledge[0]

    def test_level1_returns_toc(self):
        tool = self._build_tool()
        with patch(self._PATCH_TARGET, self._skills):
            result = tool("patterns/root-cause-patterns.md")
        self.assertEqual(result.metadata["level"], 1)
        self.assertIn("CPU 调度抢占", result.return_value)
        self.assertIn("GPU 负载过高", result.return_value)

    def test_level2_returns_section(self):
        tool = self._build_tool()
        with patch(self._PATCH_TARGET, self._skills):
            result = tool("patterns/root-cause-patterns.md#cpu-调度抢占")
        self.assertEqual(result.metadata["level"], 2)
        self.assertIn("当进程被高优先级任务抢占时", result.return_value)
        self.assertNotIn("GPU 负载过高", result.return_value)

    def test_file_not_found(self):
        tool = self._build_tool()
        with patch(self._PATCH_TARGET, self._skills):
            result = tool("patterns/nonexistent.md")
        self.assertIn("不存在", result.return_value)

    def test_anchor_not_found(self):
        tool = self._build_tool()
        with patch(self._PATCH_TARGET, self._skills):
            result = tool("patterns/root-cause-patterns.md#不存在的锚点")
        self.assertIn("锚点不存在", result.return_value)

    def test_path_traversal_blocked(self):
        tool = self._build_tool()
        with patch(self._PATCH_TARGET, self._skills):
            result = tool("../../etc/passwd")
        err_msg = result.return_value.lower() if hasattr(result, "return_value") else str(result).lower()
        self.assertTrue("不存在" in err_msg or "越界" in err_msg)

    def test_tool_registered_in_build(self):
        mock_service = MagicMock()
        with patch(self._PATCH_TARGET, self._skills):
            from src.agent.tools import build_analysis_tools
            tools = build_analysis_tools(mock_service)
        names = [getattr(t, "__name__", "") for t in tools]
        self.assertIn("pa_read_knowledge", names)


# ---------------------------------------------------------------------------
# SOP 引用指针可达性验证
# ---------------------------------------------------------------------------
class TestSopReferenceReachability(unittest.TestCase):
    """验证 SOP 文件中 pa_read_knowledge 引用指针指向的文件和锚点均存在。"""

    @classmethod
    def setUpClass(cls):
        cls._skills_dir = (
            Path(__file__).resolve().parents[1] / "skills" / "perfetto-analysis"
        )
        cls._sop_dir = cls._skills_dir / "sop"

    def _collect_references(self):
        """从所有 SOP 文件中提取 pa_read_knowledge("...") 引用。"""
        import re as _re
        refs = []
        if not self._sop_dir.exists():
            return refs
        for sop_file in self._sop_dir.glob("*.md"):
            content = sop_file.read_text(encoding="utf-8")
            for match in _re.finditer(r'pa_read_knowledge\("([^"]+)"\)', content):
                refs.append((sop_file.name, match.group(1)))
        return refs

    def test_all_references_file_exists(self):
        refs = self._collect_references()
        if not refs:
            self.skipTest("No SOP references found")
        for sop_name, resource_path in refs:
            path_part = resource_path.split("#")[0]
            full_path = self._skills_dir / path_part
            self.assertTrue(
                full_path.exists(),
                f"[{sop_name}] 引用的文件不存在: {path_part}",
            )

    def test_all_anchor_references_reachable(self):
        refs = self._collect_references()
        anchor_refs = [(s, r) for s, r in refs if "#" in r]
        if not anchor_refs:
            self.skipTest("No anchor references found")
        for sop_name, resource_path in anchor_refs:
            path_part, _, anchor = resource_path.partition("#")
            full_path = self._skills_dir / path_part
            if not full_path.exists():
                continue
            content = full_path.read_text(encoding="utf-8")
            section = _extract_section_by_anchor(content, anchor)
            self.assertTrue(
                section,
                f"[{sop_name}] 锚点不可达: {resource_path}",
            )


if __name__ == "__main__":
    unittest.main()
