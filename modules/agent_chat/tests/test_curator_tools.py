# -*- coding: utf-8 -*-
"""knowledge-curator 工具测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from modules.agent_chat.src.skills.curator_tools import (
    check_duplicate,
    classify_document,
    format_resource,
    match_skill,
    write_resource,
)


class TestClassifyDocument:
    def test_sop_content(self) -> None:
        content = "# 分析流程\n\n## 步骤一\n\n按照操作指引执行以下流程\n\n## 步骤二\n\n检查结果"
        results = classify_document(content)
        assert len(results) >= 1
        sop_items = [r for r in results if r["category"] == "sop"]
        assert len(sop_items) > 0

    def test_case_content(self) -> None:
        content = "# 分析案例\n\n## 设备信息\n\n设备: Pixel 7\ntrace 时间戳: 2026-03-20\n\n## 结论\n\n主线程 Binder 阻塞"
        results = classify_document(content)
        assert len(results) >= 1
        case_items = [r for r in results if r["category"] == "cases"]
        assert len(case_items) > 0

    def test_pattern_content(self) -> None:
        content = "# 根因模式\n\n当 SurfaceFlinger 超时发生时，原因可能是 GPU 渲染过载，方案是降低分辨率"
        results = classify_document(content)
        assert len(results) >= 1
        pattern_items = [r for r in results if r["category"] == "patterns"]
        assert len(pattern_items) > 0

    def test_empty_content(self) -> None:
        results = classify_document("")
        assert len(results) >= 1

    def test_mixed_content(self) -> None:
        content = (
            "# 步骤一\n\n操作流程指引\n\n"
            "# 案例\n\n设备 trace 分析结论"
        )
        results = classify_document(content)
        assert len(results) >= 2


class TestMatchSkill:
    def test_user_override(self) -> None:
        items = [{"summary": "test", "category": "sop"}]
        skills = [{"name": "perfetto-analysis", "description": "分析", "tags": ["trace"]}]
        result = match_skill(items, skills, user_override="my-skill")
        assert result[0]["matched_skill"] == "my-skill"
        assert result[0]["score"] == 1.0

    def test_auto_match(self) -> None:
        items = [{"summary": "trace 性能分析 perfetto", "category": "sop"}]
        skills = [
            {"name": "perfetto-analysis", "description": "Perfetto trace 分析", "tags": ["trace", "perfetto"]},
            {"name": "knowledge-curator", "description": "知识策展", "tags": ["知识"]},
        ]
        result = match_skill(items, skills)
        assert result[0]["matched_skill"] == "perfetto-analysis"

    def test_no_skills(self) -> None:
        items = [{"summary": "test", "category": "sop"}]
        result = match_skill(items, [])
        assert result[0]["matched_skill"] == ""


class TestFormatResource:
    def test_format_sop(self) -> None:
        result = format_resource("# My SOP\n\n步骤一二三", "sop", "raw.md")
        assert "My SOP" in result
        assert "category: sop" in result
        assert "source: raw.md" in result

    def test_format_pattern(self) -> None:
        result = format_resource("# GPU 阻塞\n\n根因分析", "patterns")
        assert "category: pattern" in result

    def test_format_case(self) -> None:
        result = format_resource("# Case 1\n\n分析结论", "cases")
        assert "category: case" in result


class TestCheckDuplicate:
    def test_no_duplicates(self, tmp_path: Path) -> None:
        existing = tmp_path / "existing.md"
        existing.write_text("完全不同的内容", encoding="utf-8")
        dups = check_duplicate("全新的内容", [existing])
        assert dups == []

    def test_high_similarity(self, tmp_path: Path) -> None:
        content = "这是一段测试内容用于检测重复度"
        existing = tmp_path / "existing.md"
        existing.write_text(content, encoding="utf-8")
        dups = check_duplicate(content, [existing])
        assert len(dups) == 1
        assert dups[0]["similarity"] >= 0.70

    def test_empty_directory(self) -> None:
        dups = check_duplicate("test", [])
        assert dups == []


class TestWriteResource:
    def test_write_creates_file(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "test-skill"
        result = write_resource("# New SOP", skill_dir, "sop", "new-sop")
        assert Path(result).exists()
        assert "new-sop.md" in result

    def test_write_creates_directory(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "test-skill"
        write_resource("content", skill_dir, "patterns", "p1.md")
        assert (skill_dir / "patterns").is_dir()


class TestCuratorAgentTools:
    """通过 SkillsManager 集成测试 curator 工具。"""

    @pytest.fixture
    def skills_dir(self, tmp_path: Path) -> Path:
        skill = tmp_path / "skills" / "test-skill"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: 测试\ntags:\n  - test\n---\n\n# Test",
            encoding="utf-8",
        )
        sop_dir = skill / "sop"
        sop_dir.mkdir()
        (sop_dir / "existing.md").write_text("已有内容", encoding="utf-8")
        return tmp_path / "skills"

    def test_curator_tools_registered(self, skills_dir: Path) -> None:
        from modules.agent_chat.src.skills.manager import SkillsManager

        mgr = SkillsManager([skills_dir])
        mgr.scan()
        tools = mgr.create_agent_tools()
        names = {t.name for t in tools}
        assert "kc_classify_document" in names
        assert "kc_match_skill" in names
        assert "kc_format_resource" in names
        assert "kc_check_duplicate" in names
        assert "kc_write_resource" in names

    def test_kc_classify_via_tool(self, skills_dir: Path) -> None:
        from modules.agent_chat.src.skills.manager import SkillsManager

        mgr = SkillsManager([skills_dir])
        mgr.scan()
        tools = mgr.create_agent_tools()
        classify_tool = next(t for t in tools if t.name == "kc_classify_document")
        result = classify_tool.method(content="步骤一：操作流程指引")
        assert "sop" in result.lower() or len(result) > 0

    def test_kc_write_via_tool(self, skills_dir: Path) -> None:
        from modules.agent_chat.src.skills.manager import SkillsManager

        mgr = SkillsManager([skills_dir])
        mgr.scan()
        tools = mgr.create_agent_tools()
        write_tool = next(t for t in tools if t.name == "kc_write_resource")
        result = write_tool.method(
            content="# New Doc\n\n内容",
            skill_name="test-skill",
            category="sop",
            filename="new-doc",
        )
        assert "new-doc.md" in result
        assert Path(result).exists()
