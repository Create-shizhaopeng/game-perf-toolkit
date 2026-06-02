"""agent/skill_tools 单元测试 — 验证 Skill 工具生成与 SkillRouter。

测试文档: tests/doc/test_agent_skill_tools.md
关联 Spec: openspec/changes/agent-wiring-fix/specs/agent-skill-tools/spec.md
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from toolkit.core.skill_registry import SkillRegistry
from toolkit.core.models import ToolDefinition


# ── Fixtures ────────────────────────────────────────────────────────────

def _make_skill(base: Path, name: str, description: str, tags: str, triggers: str, body: str) -> None:
    """Helper: create a SKILL.md in a subdirectory."""
    d = base / name
    d.mkdir()
    frontmatter = (
        f"---\nname: {name}\ndescription: {description}\n"
        f"tags: [{tags}]\ntriggers: [{triggers}]\n---\n{body}\n"
    )
    (d / "SKILL.md").write_text(frontmatter, encoding="utf-8")


@pytest.fixture
def skill_registry_with_skills() -> Generator[SkillRegistry, None, None]:
    """创建含 2 个测试 Skill 的 SkillRegistry。

    用 yield 保证临时目录在测试期间存活，测试结束后清理。
    """
    registry = SkillRegistry()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        _make_skill(base, "perfetto-analysis",
                    "Perfetto trace 分析",
                    "trace, jank",
                    "分析trace, 卡顿",
                    "# Perfetto Analysis\n\n分析 trace 文件的卡顿问题。")

        _make_skill(base, "device-disguise",
                    "Android 设备伪装",
                    "device, disguise",
                    "伪装",
                    "# Device Disguise\n\n修改设备 ODM 属性。")

        registry.add_search_path(base)
        registry.scan()
        yield registry


# ── build_skill_tools ────────────────────────────────────────────────────

class TestBuildSkillTools:
    """测试 skill_tools.build_skill_tools() 函数。"""

    def test_returns_at_least_4_tools(self, skill_registry_with_skills: SkillRegistry) -> None:
        """输入含 2 个 Skill 的 registry，应返回 ≥4 个 ToolDefinition。"""
        from toolkit.agent.skill_tools import build_skill_tools

        tools = build_skill_tools(skill_registry_with_skills)
        assert len(tools) >= 4, f"Expected >=4 tools, got {len(tools)}"
        for t in tools:
            assert isinstance(t, ToolDefinition), f"{t.name} is not ToolDefinition"

    def test_skill_list_returns_skill_names(self, skill_registry_with_skills: SkillRegistry) -> None:
        """skill_list 应列出所有已注册 Skill 的 name + description。"""
        from toolkit.agent.skill_tools import build_skill_tools

        tools = build_skill_tools(skill_registry_with_skills)
        skill_list = next(t for t in tools if t.name == "skill_list")
        result = skill_list.method()
        assert "perfetto-analysis" in result
        assert "device-disguise" in result

    def test_skill_load_returns_full_content(self, skill_registry_with_skills: SkillRegistry) -> None:
        """skill_load 应返回指定 Skill 的 SKILL.md 全文（Level 1）。"""
        from toolkit.agent.skill_tools import build_skill_tools

        tools = build_skill_tools(skill_registry_with_skills)
        skill_load = next(t for t in tools if t.name == "skill_load")
        result = skill_load.method("perfetto-analysis")
        assert "Perfetto Analysis" in result
        assert "卡顿问题" in result

    def test_skill_load_missing_skill(self, skill_registry_with_skills: SkillRegistry) -> None:
        """skill_load 对不存在的 Skill 应返回错误提示，不抛异常。"""
        from toolkit.agent.skill_tools import build_skill_tools

        tools = build_skill_tools(skill_registry_with_skills)
        skill_load = next(t for t in tools if t.name == "skill_load")
        result = skill_load.method("nonexistent-skill")
        assert isinstance(result, str)
        assert "不存在" in result or "加载失败" in result

    def test_skill_list_resources_returns_string(self, skill_registry_with_skills: SkillRegistry) -> None:
        """skill_list_resources 应返回字符串（可能为空或含目录列表）。"""
        from toolkit.agent.skill_tools import build_skill_tools

        tools = build_skill_tools(skill_registry_with_skills)
        list_res = next(t for t in tools if t.name == "skill_list_resources")
        result = list_res.method("perfetto-analysis")
        assert isinstance(result, str)

    def test_skill_load_resource_nonexistent(self, skill_registry_with_skills: SkillRegistry) -> None:
        """skill_load_resource 对不存在的子资源应返回错误提示（Level 2 错误路径）。"""
        from toolkit.agent.skill_tools import build_skill_tools

        tools = build_skill_tools(skill_registry_with_skills)
        load_res = next(t for t in tools if t.name == "skill_load_resource")
        result = load_res.method("perfetto-analysis", "nonexistent/file.md")
        assert isinstance(result, str)
        assert result != ""

    def test_empty_registry_graceful(self) -> None:
        """空 SkillRegistry 应仍返回工具，skill_list 输出提示无可用 Skill。"""
        from toolkit.agent.skill_tools import build_skill_tools

        empty = SkillRegistry()
        tools = build_skill_tools(empty)
        assert len(tools) >= 4
        skill_list = next(t for t in tools if t.name == "skill_list")
        result = skill_list.method()
        assert isinstance(result, str)


# ── SkillRouter ─────────────────────────────────────────────────────────

class TestSkillRouter:
    """测试从旧模块移植的 SkillRouter。"""

    def test_import_and_instantiate(self) -> None:
        """验证 SkillRouter 可从 toolkit.agent.skill_router 导入并实例化。"""
        from toolkit.agent.skill_router import SkillRouter

        router = SkillRouter()
        assert router is not None

    def test_match_returns_ranked_results(self, skill_registry_with_skills: SkillRegistry) -> None:
        """用关键词查询应返回按相关度降序的匹配结果。"""
        from toolkit.agent.skill_router import SkillRouter

        router = SkillRouter()
        skills = skill_registry_with_skills.get_skills()
        router.update_index(skills)
        results = router.match("trace 卡顿分析", top_k=2)
        assert len(results) > 0, "Expected at least 1 match"
        # Each result is (SkillMetadata, score)
        meta, _score = results[0]
        assert meta.name == "perfetto-analysis", (
            f"Expected perfetto-analysis as top match, got {meta.name}"
        )

    def test_empty_query_returns_empty_list(self, skill_registry_with_skills: SkillRegistry) -> None:
        """空查询应返回空列表，不抛异常。"""
        from toolkit.agent.skill_router import SkillRouter

        router = SkillRouter()
        skills = skill_registry_with_skills.get_skills()
        router.update_index(skills)
        results = router.match("", top_k=2)
        assert results == [], f"Expected empty list for empty query, got {results}"
