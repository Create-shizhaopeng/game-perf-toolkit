# -*- coding: utf-8 -*-
"""Skills 管理层测试 — 发现、路由、加载、Manager。"""
from __future__ import annotations

from pathlib import Path

import pytest

from modules.agent_chat.src.models import SkillContext, SkillMetadata


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def skill_dir(tmp_path: Path) -> Path:
    """创建一个包含 SKILL.md 的测试 Skill 目录。"""
    skill = tmp_path / "skills" / "test-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: test-skill\n"
        "version: 1.2.0\n"
        "description: 测试 Skill\n"
        "tags:\n  - testing\n  - demo\n"
        "triggers:\n  - 测试分析\n  - test analysis\n"
        "tools:\n  - tool_a\n  - tool_b\n"
        "priority: 10\n"
        "---\n\n"
        "# Test Skill\n\n"
        "这是测试 Skill 的主内容。\n",
        encoding="utf-8",
    )
    sop_dir = skill / "sop"
    sop_dir.mkdir()
    (sop_dir / "basic.md").write_text("# Basic SOP\n\n步骤一", encoding="utf-8")
    (sop_dir / "advanced.md").write_text("# Advanced SOP\n\n步骤二", encoding="utf-8")

    patterns_dir = skill / "patterns"
    patterns_dir.mkdir()
    (patterns_dir / "p1.md").write_text("# Pattern 1", encoding="utf-8")

    return tmp_path / "skills"


@pytest.fixture
def multi_skills_dir(tmp_path: Path) -> Path:
    """创建多个 Skill 目录。"""
    base = tmp_path / "skills"

    s1 = base / "perfetto-analysis"
    s1.mkdir(parents=True)
    (s1 / "SKILL.md").write_text(
        "---\n"
        "name: perfetto-analysis\n"
        "description: Perfetto trace 性能分析\n"
        "tags:\n  - perfetto\n  - 性能\n  - trace\n"
        "triggers:\n  - trace 分析\n  - 卡顿分析\n  - perfetto\n"
        "---\n\n# Perfetto Analysis\n",
        encoding="utf-8",
    )

    s2 = base / "knowledge-curator"
    s2.mkdir(parents=True)
    (s2 / "SKILL.md").write_text(
        "---\n"
        "name: knowledge-curator\n"
        "description: 知识策展与文档导入\n"
        "tags:\n  - 知识管理\n  - 文档\n"
        "triggers:\n  - 导入文档\n  - 知识整理\n"
        "---\n\n# Knowledge Curator\n",
        encoding="utf-8",
    )

    disabled = base / "disabled-skill"
    disabled.mkdir(parents=True)
    (disabled / "SKILL.md").write_text(
        "---\nname: disabled-skill\nenabled: false\n---\n",
        encoding="utf-8",
    )

    return base


# ── SkillDiscovery ────────────────────────────────────────────────────


class TestSkillDiscovery:
    def test_scan_finds_skills(self, skill_dir: Path) -> None:
        from modules.agent_chat.src.skills.discovery import SkillDiscovery

        disc = SkillDiscovery([skill_dir])
        result = disc.scan()
        assert "test-skill" in result
        meta, path = result["test-skill"]
        assert meta.version == "1.2.0"
        assert "testing" in meta.tags

    def test_scan_skips_disabled(self, multi_skills_dir: Path) -> None:
        from modules.agent_chat.src.skills.discovery import SkillDiscovery

        disc = SkillDiscovery([multi_skills_dir])
        result = disc.scan()
        assert "disabled-skill" not in result
        assert "perfetto-analysis" in result

    def test_scan_empty_dir(self, tmp_path: Path) -> None:
        from modules.agent_chat.src.skills.discovery import SkillDiscovery

        disc = SkillDiscovery([tmp_path / "nonexistent"])
        result = disc.scan()
        assert result == {}

    def test_get_all_metadata(self, multi_skills_dir: Path) -> None:
        from modules.agent_chat.src.skills.discovery import SkillDiscovery

        disc = SkillDiscovery([multi_skills_dir])
        disc.scan()
        all_meta = disc.get_all_metadata()
        names = {m.name for m in all_meta}
        assert "perfetto-analysis" in names
        assert "knowledge-curator" in names

    def test_get_skill_path(self, skill_dir: Path) -> None:
        from modules.agent_chat.src.skills.discovery import SkillDiscovery

        disc = SkillDiscovery([skill_dir])
        disc.scan()
        path = disc.get_skill_path("test-skill")
        assert path is not None
        assert (path / "SKILL.md").exists()


class TestFrontmatterParsing:
    def test_valid_frontmatter(self) -> None:
        from modules.agent_chat.src.skills.discovery import parse_yaml_frontmatter

        text = "---\nname: foo\nversion: 2.0\n---\n\n# Body"
        fm = parse_yaml_frontmatter(text)
        assert fm["name"] == "foo"

    def test_no_frontmatter(self) -> None:
        from modules.agent_chat.src.skills.discovery import parse_yaml_frontmatter

        fm = parse_yaml_frontmatter("# Just a heading")
        assert fm == {}

    def test_invalid_yaml(self) -> None:
        from modules.agent_chat.src.skills.discovery import parse_yaml_frontmatter

        fm = parse_yaml_frontmatter("---\n: invalid: yaml:\n---\n")
        assert isinstance(fm, dict)


# ── SkillRouter ───────────────────────────────────────────────────────


class TestSkillRouter:
    def test_match_by_trigger(self, multi_skills_dir: Path) -> None:
        from modules.agent_chat.src.skills.discovery import SkillDiscovery
        from modules.agent_chat.src.skills.router import SkillRouter

        disc = SkillDiscovery([multi_skills_dir])
        entries = disc.scan()
        all_meta = [m for m, _ in entries.values()]

        router = SkillRouter()
        router.update_index(all_meta)

        results = router.match("帮我分析这个 trace 的卡顿问题")
        assert len(results) > 0
        assert results[0][0].name == "perfetto-analysis"

    def test_match_by_keyword(self, multi_skills_dir: Path) -> None:
        from modules.agent_chat.src.skills.discovery import SkillDiscovery
        from modules.agent_chat.src.skills.router import SkillRouter

        disc = SkillDiscovery([multi_skills_dir])
        entries = disc.scan()
        all_meta = [m for m, _ in entries.values()]

        router = SkillRouter()
        router.update_index(all_meta)

        results = router.match("导入文档进行知识整理")
        assert len(results) > 0
        assert results[0][0].name == "knowledge-curator"

    def test_match_empty_query(self) -> None:
        from modules.agent_chat.src.skills.router import SkillRouter

        router = SkillRouter()
        router.update_index([SkillMetadata(name="test")])
        results = router.match("")
        assert results == []


# ── SkillLoader ───────────────────────────────────────────────────────


class TestSkillLoader:
    def test_load_metadata(self, skill_dir: Path) -> None:
        from modules.agent_chat.src.skills.loader import SkillLoader

        loader = SkillLoader()
        ctx = loader.load_metadata(skill_dir / "test-skill")
        assert ctx is not None
        assert ctx.metadata is not None
        assert ctx.metadata.name == "test-skill"
        assert ctx.load_level == 0

    def test_load_skill_content(self, skill_dir: Path) -> None:
        from modules.agent_chat.src.skills.loader import SkillLoader

        loader = SkillLoader()
        ctx = loader.load_metadata(skill_dir / "test-skill")
        assert ctx is not None
        loader.load_skill_content(ctx)
        assert ctx.load_level == 1
        assert "Test Skill" in ctx.loaded_content

    def test_load_resource(self, skill_dir: Path) -> None:
        from modules.agent_chat.src.skills.loader import SkillLoader

        loader = SkillLoader()
        ctx = loader.load_metadata(skill_dir / "test-skill")
        assert ctx is not None
        content = loader.load_resource(ctx, "sop/basic.md")
        assert "Basic SOP" in content
        assert ctx.load_level == 2

    def test_load_resource_not_found(self, skill_dir: Path) -> None:
        from modules.agent_chat.src.skills.loader import SkillLoader

        loader = SkillLoader()
        ctx = loader.load_metadata(skill_dir / "test-skill")
        assert ctx is not None
        result = loader.load_resource(ctx, "nonexistent.md")
        assert "不存在" in result

    def test_list_resources(self, skill_dir: Path) -> None:
        from modules.agent_chat.src.skills.loader import SkillLoader

        loader = SkillLoader()
        ctx = loader.load_metadata(skill_dir / "test-skill")
        assert ctx is not None
        resources = loader.list_resources(ctx)
        assert "sop" in resources
        assert "basic.md" in resources["sop"]
        assert "patterns" in resources


# ── SkillsManager ────────────────────────────────────────────────────


class TestSkillsManager:
    def test_scan_and_list(self, multi_skills_dir: Path) -> None:
        from modules.agent_chat.src.skills.manager import SkillsManager

        mgr = SkillsManager([multi_skills_dir])
        meta_list = mgr.scan()
        names = {m.name for m in meta_list}
        assert "perfetto-analysis" in names

    def test_load_skill(self, skill_dir: Path) -> None:
        from modules.agent_chat.src.skills.manager import SkillsManager

        mgr = SkillsManager([skill_dir])
        mgr.scan()
        ctx = mgr.load_skill("test-skill", level=1)
        assert ctx is not None
        assert "Test Skill" in ctx.loaded_content

    def test_load_resource(self, skill_dir: Path) -> None:
        from modules.agent_chat.src.skills.manager import SkillsManager

        mgr = SkillsManager([skill_dir])
        mgr.scan()
        content = mgr.load_resource("test-skill", "sop/basic.md")
        assert "Basic SOP" in content

    def test_match_skills(self, multi_skills_dir: Path) -> None:
        from modules.agent_chat.src.skills.manager import SkillsManager

        mgr = SkillsManager([multi_skills_dir])
        mgr.scan()
        matches = mgr.match_skills("perfetto trace 分析")
        assert len(matches) > 0
        assert matches[0][0].name == "perfetto-analysis"

    def test_create_agent_tools(self, skill_dir: Path) -> None:
        from modules.agent_chat.src.skills.manager import SkillsManager

        mgr = SkillsManager([skill_dir])
        mgr.scan()
        tools = mgr.create_agent_tools()
        names = {t.name for t in tools}
        assert "skill_list" in names
        assert "skill_load" in names
        assert "skill_load_resource" in names
        assert "skill_list_resources" in names

    def test_agent_tool_skill_list(self, skill_dir: Path) -> None:
        from modules.agent_chat.src.skills.manager import SkillsManager

        mgr = SkillsManager([skill_dir])
        mgr.scan()
        tools = mgr.create_agent_tools()
        list_tool = next(t for t in tools if t.name == "skill_list")
        result = list_tool.method()
        assert "test-skill" in result

    def test_agent_tool_skill_load(self, skill_dir: Path) -> None:
        from modules.agent_chat.src.skills.manager import SkillsManager

        mgr = SkillsManager([skill_dir])
        mgr.scan()
        tools = mgr.create_agent_tools()
        load_tool = next(t for t in tools if t.name == "skill_load")
        result = load_tool.method(name="test-skill")
        assert "Test Skill" in result

    def test_agent_tool_load_missing_skill(self, skill_dir: Path) -> None:
        from modules.agent_chat.src.skills.manager import SkillsManager

        mgr = SkillsManager([skill_dir])
        mgr.scan()
        tools = mgr.create_agent_tools()
        load_tool = next(t for t in tools if t.name == "skill_load")
        result = load_tool.method(name="nonexistent")
        assert "不存在" in result
