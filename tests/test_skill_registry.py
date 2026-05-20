"""Skill Registry 基本测试。"""

import tempfile
from pathlib import Path

from toolkit.core.skill_registry import SkillRegistry, SkillMetadata


def _write_tmp_skill(content: str, suffix: str = ".md") -> Path:
    """写入临时 Skill 文件并返回路径。"""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


def test_skill_registry_empty_initial():
    """初始状态为空。"""
    reg = SkillRegistry()
    assert reg.get_skills() == []


def test_skill_registry_load_valid_skill():
    """加载合法的 SKILL.md 文件。"""
    content = (
        "---\n"
        "name: test-skill\n"
        "description: A test skill\n"
        "category: test\n"
        "triggers:\n"
        "  keywords: [\"test\"]\n"
        "---\n\n# Test Skill\n\nBody content.\n"
    )
    path = _write_tmp_skill(content)
    try:
        reg = SkillRegistry()
        reg.load_skills([str(path)])

        skills = reg.get_skills()
        assert len(skills) == 1
        assert skills[0].name == "test-skill"
        assert skills[0].description == "A test skill"
        assert skills[0].category == "test"
        assert skills[0].triggers == {"keywords": ["test"]}
        assert "Body content." in reg.get_skill_content("test-skill")
    finally:
        path.unlink()


def test_skill_registry_get_skill_by_name():
    """按名称获取 Skill 元数据。"""
    content = "---\nname: my-skill\ndescription: My skill desc\n---\n\nContent.\n"
    path = _write_tmp_skill(content)
    try:
        reg = SkillRegistry()
        reg.load_skills([str(path)])

        skill = reg.get_skill("my-skill")
        assert skill is not None
        assert skill.name == "my-skill"

        assert reg.get_skill("nonexistent") is None
    finally:
        path.unlink()


def test_skill_registry_load_nonexistent_file():
    """不存在的文件应被跳过，不抛出异常。"""
    reg = SkillRegistry()
    reg.load_skills(["/nonexistent/path/to/SKILL.md"])
    assert reg.get_skills() == []


def test_skill_registry_get_skill_content_nonexistent():
    """获取不存在的 Skill 内容返回 None。"""
    reg = SkillRegistry()
    assert reg.get_skill_content("nonexistent") is None


def test_skill_registry_parse_all_frontmatter_fields():
    """解析 frontmatter 中所有字段。"""
    content = (
        "---\n"
        "name: full-skill\n"
        "description: Full description\n"
        "category: device-operation\n"
        "icon: device\n"
        "tags: [\"android\", \"adb\"]\n"
        "triggers:\n"
        "  keywords: [\"伪装\"]\n"
        "  patterns: [\"伪装.*品牌\"]\n"
        "---\n\n# Full Skill\n"
    )
    path = _write_tmp_skill(content)
    try:
        reg = SkillRegistry()
        reg.load_skills([str(path)])

        skill = reg.get_skill("full-skill")
        assert skill is not None
        assert skill.name == "full-skill"
        assert skill.description == "Full description"
        assert skill.category == "device-operation"
        assert skill.icon == "device"
        assert skill.tags == ["android", "adb"]
        assert skill.triggers == {
            "keywords": ["伪装"],
            "patterns": ["伪装.*品牌"],
        }
    finally:
        path.unlink()


def test_skill_registry_load_multiple():
    """批量加载多个 Skill 文件。"""
    files = []
    try:
        for i in range(3):
            content = (
                f"---\nname: skill-{i}\ndescription: Desc {i}\n---\n\nContent {i}.\n"
            )
            files.append(str(_write_tmp_skill(content)))

        reg = SkillRegistry()
        reg.load_skills(files)

        assert len(reg.get_skills()) == 3
        for i in range(3):
            assert reg.get_skill(f"skill-{i}") is not None
    finally:
        for fp in files:
            Path(fp).unlink()


def test_skill_registry_to_dict():
    """SkillMetadata.to_dict() 返回完整字段。"""
    content = "---\nname: dict-skill\ndescription: Desc\n---\n\nBody.\n"
    path = _write_tmp_skill(content)
    try:
        reg = SkillRegistry()
        reg.load_skills([str(path)])

        skill = reg.get_skill("dict-skill")
        d = skill.to_dict()
        assert "name" in d
        assert "description" in d
        assert "triggers" in d
        assert "category" in d
        assert "file_path" in d
        assert d["name"] == "dict-skill"
    finally:
        path.unlink()
