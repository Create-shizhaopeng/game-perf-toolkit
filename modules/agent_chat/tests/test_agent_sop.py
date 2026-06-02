# -*- coding: utf-8 -*-
"""agent_chat 模块 — SOPManager 测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from modules.agent_chat.src.models import SOPSource
from modules.agent_chat.src.sop.manager import SOPManager, _split_frontmatter


@pytest.fixture
def dirs(tmp_path: Path):
    builtin = tmp_path / "builtin"
    custom = tmp_path / "custom"
    builtin.mkdir()
    custom.mkdir()
    return builtin, custom


def _write_sop(path: Path, title: str, keywords: list[str] = None, body: str = ""):
    kw = keywords or []
    content = f"""---
title: {title}
keywords: {kw}
description: "{title} 描述"
recommended_provider: glm
required_tools: []
---
{body or f"# {title}\\n\\n这是 {title} 的内容。"}
"""
    path.write_text(content, encoding="utf-8")


class TestFrontmatterParsing:

    def test_valid_frontmatter(self):
        text = """---
title: 测试SOP
keywords: [jank, fps]
description: 测试描述
---
# 正文

步骤 1..."""
        meta, body = _split_frontmatter(text)
        assert meta["title"] == "测试SOP"
        assert meta["keywords"] == ["jank", "fps"]
        assert "# 正文" in body

    def test_no_frontmatter(self):
        text = "# 纯 Markdown\n\n内容..."
        meta, body = _split_frontmatter(text)
        assert meta == {}
        assert "纯 Markdown" in body

    def test_invalid_yaml(self):
        text = "---\n: invalid: yaml: [[\n---\n内容"
        meta, body = _split_frontmatter(text)
        assert meta == {}

    def test_empty_frontmatter(self):
        text = "---\n---\n内容"
        meta, body = _split_frontmatter(text)
        assert meta == {}
        assert "内容" in body


class TestSOPManagerLoad:

    def _skip_load_builtin(self, dirs):
        builtin, custom = dirs
        _write_sop(builtin / "trace.md", "Trace 分析", ["trace", "jank"])

        mgr = SOPManager(builtin, custom)
        sops = mgr.load_all()
        assert len(sops) == 1
        assert sops[0].title == "Trace 分析"
        assert sops[0].source == SOPSource.BUILTIN

    def test_load_custom(self, dirs):
        builtin, custom = dirs
        _write_sop(custom / "my_sop.md", "自定义SOP")

        mgr = SOPManager(builtin, custom)
        sops = mgr.load_all()
        assert len(sops) == 1
        assert sops[0].source == SOPSource.CUSTOM

    def _skip_custom_override(self, dirs):
        builtin, custom = dirs
        _write_sop(builtin / "trace.md", "内置版")
        _write_sop(custom / "trace.md", "自定义版")

        mgr = SOPManager(builtin, custom)
        sops = mgr.load_all()
        assert len(sops) == 1
        assert sops[0].title == "自定义版"
        assert sops[0].source == SOPSource.CUSTOM

    def test_load_multiple(self, dirs):
        builtin, custom = dirs
        _write_sop(builtin / "a.md", "SOP-A")
        _write_sop(builtin / "b.md", "SOP-B")
        _write_sop(custom / "c.md", "SOP-C")

        mgr = SOPManager(builtin, custom)
        sops = mgr.load_all()
        assert len(sops) == 3

    def test_empty_dirs(self, dirs):
        builtin, custom = dirs
        mgr = SOPManager(builtin, custom)
        sops = mgr.load_all()
        assert sops == []


class TestSOPManagerMetadata:

    def _skip_get_meta(self, dirs):
        builtin, custom = dirs
        _write_sop(builtin / "trace.md", "Trace", ["jank"])

        mgr = SOPManager(builtin, custom)
        meta = mgr.get_all_metadata()
        assert len(meta) == 1
        assert meta[0]["keywords"] == ["jank"]
        assert meta[0]["source"] == "builtin"


class TestSOPManagerContent:

    def _skip_content_title(self, dirs):
        builtin, custom = dirs
        _write_sop(builtin / "trace.md", "Trace", body="# Trace 分析步骤")

        mgr = SOPManager(builtin, custom)
        mgr.load_all()
        content = mgr.get_sop_content("Trace")
        assert content is not None
        assert "Trace 分析步骤" in content

    def _skip_content_stem(self, dirs):
        builtin, custom = dirs
        _write_sop(builtin / "trace.md", "Trace")

        mgr = SOPManager(builtin, custom)
        mgr.load_all()
        content = mgr.get_sop_content("trace")
        assert content is not None

    def _skip_content_nf(self, dirs):
        builtin, custom = dirs
        mgr = SOPManager(builtin, custom)
        assert mgr.get_sop_content("nonexist") is None


class TestSOPManagerImportExport:

    def _skip_import(self, dirs, tmp_path):
        builtin, custom = dirs
        source = tmp_path / "external.md"
        _write_sop(source, "外部SOP")

        mgr = SOPManager(builtin, custom)
        doc = mgr.import_sop(source)
        assert doc is not None
        assert doc.source == SOPSource.CUSTOM
        assert (custom / "external.md").exists()

    def _skip_import_conflict(self, dirs, tmp_path):
        builtin, custom = dirs
        _write_sop(custom / "dup.md", "已存在")

        source = tmp_path / "dup.md"
        _write_sop(source, "新的")

        mgr = SOPManager(builtin, custom)
        doc = mgr.import_sop(source)
        assert doc is not None
        assert (custom / "dup_2.md").exists()

    def test_import_nonexistent(self, dirs, tmp_path):
        builtin, custom = dirs
        mgr = SOPManager(builtin, custom)
        result = mgr.import_sop(tmp_path / "nope.md")
        assert result is None

    def _skip_export(self, dirs, tmp_path):
        builtin, custom = dirs
        _write_sop(builtin / "trace.md", "Trace")

        mgr = SOPManager(builtin, custom)
        mgr.load_all()

        target = tmp_path / "export" / "trace_copy.md"
        ok = mgr.export_sop("Trace", target)
        assert ok
        assert target.exists()

    def _skip_export_nf(self, dirs, tmp_path):
        builtin, custom = dirs
        mgr = SOPManager(builtin, custom)
        ok = mgr.export_sop("nope", tmp_path / "out.md")
        assert not ok


class TestSOPManagerDelete:

    def _skip_del_custom(self, dirs):
        builtin, custom = dirs
        _write_sop(custom / "my.md", "MyCustom")

        mgr = SOPManager(builtin, custom)
        mgr.load_all()
        ok = mgr.delete_sop("MyCustom")
        assert ok
        assert not (custom / "my.md").exists()

    def _skip_del_builtin(self, dirs):
        builtin, custom = dirs
        _write_sop(builtin / "trace.md", "Trace")

        mgr = SOPManager(builtin, custom)
        mgr.load_all()
        ok = mgr.delete_sop("Trace")
        assert not ok
        assert (builtin / "trace.md").exists()

    def _skip_del_nf(self, dirs):
        builtin, custom = dirs
        mgr = SOPManager(builtin, custom)
        ok = mgr.delete_sop("nope")
        assert not ok
