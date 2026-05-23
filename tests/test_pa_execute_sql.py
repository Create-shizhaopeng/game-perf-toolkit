# -*- coding: utf-8 -*-
"""pa_execute_sql 工具测试。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SKILL_DIR = (
    Path(__file__).resolve().parent.parent
    / "modules" / "perfetto_analysis" / "skills" / "perfetto-analysis"
)

# 从 Skill scripts/ 目录加载 sql_executor
_spec = importlib.util.spec_from_file_location(
    "sql_executor", _SKILL_DIR / "scripts" / "sql_executor.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute_sql = _mod.execute_sql


class TestExecuteSql:
    """测试 sql_executor.execute_sql 核心逻辑。"""

    def test_missing_trace_file(self, tmp_path):
        """trace 文件不存在时返回错误。"""
        result = execute_sql(str(tmp_path / "nonexistent.perfetto-trace"), "SELECT 1")
        assert result["success"] is False
        assert "不存在" in result["error"]
        assert result["rows"] == []
        assert result["row_count"] == 0

    def test_invalid_sql(self, tmp_path):
        """SQL 语法错误时返回错误（需要真实 trace 或 mock）。

        此测试验证错误处理路径，使用不存在的 trace 以触发文件检查。
       真实 SQL 错误需要 perfetto 包和真实 trace 文件。
        """
        result = execute_sql("/nonexistent/trace.perfetto-trace", "INVALID SQL")
        assert result["success"] is False
        assert result["row_count"] == 0

    def test_return_structure(self):
        """返回结构必须包含 success/rows/error/row_count 四个字段。"""
        result = execute_sql("/nonexistent/trace.perfetto-trace", "SELECT 1")
        assert "success" in result
        assert "rows" in result
        assert "error" in result
        assert "row_count" in result


class TestPluginRegistration:
    """测试 plugin.py 中 pa_execute_sql 工具注册。"""

    def test_register_agent_tools_single_tool(self):
        """plugin.py 只注册 pa_execute_sql 一个工具。"""
        from modules.perfetto_analysis.src.plugin import PerfettoAnalysisPlugin

        plugin = PerfettoAnalysisPlugin()
        # _service 为 None 时 register_agent_tools 返回空列表
        # 需要模拟 _service 存在的情况
        tools = plugin.register_agent_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "pa_execute_sql"

    def test_pa_execute_sql_parameters(self):
        """pa_execute_sql 工具有完整的参数定义。"""
        from modules.perfetto_analysis.src.plugin import PerfettoAnalysisPlugin

        plugin = PerfettoAnalysisPlugin()
        tools = plugin.register_agent_tools()
        params = tools[0]["parameters"]

        assert params["type"] == "object"
        assert "trace_path" in params["properties"]
        assert "sql" in params["properties"]
        assert params["required"] == ["trace_path", "sql"]

    def test_pa_execute_sql_has_description(self):
        """pa_execute_sql 工具有使用指引描述。"""
        from modules.perfetto_analysis.src.plugin import PerfettoAnalysisPlugin

        plugin = PerfettoAnalysisPlugin()
        tools = plugin.register_agent_tools()
        desc = tools[0]["description"]

        assert "SQL" in desc or "sql" in desc
        assert "${variable}" in desc or "variable" in desc

    def test_execute_sql_method_callable(self):
        """pa_execute_sql 的 method 是可调用的。"""
        from modules.perfetto_analysis.src.plugin import PerfettoAnalysisPlugin

        plugin = PerfettoAnalysisPlugin()
        tools = plugin.register_agent_tools()
        method = tools[0]["method"]

        assert callable(method)
        # 调用不存在的文件应返回错误结构
        result = method(trace_path="/nonexistent/trace.perfetto-trace", sql="SELECT 1")
        assert result["success"] is False


class TestSkillRegistration:
    """测试 SKILL.md 注册。"""

    def test_register_skills_returns_path(self):
        """plugin.py 的 register_skills 返回 SKILL.md 路径。"""
        from modules.perfetto_analysis.src.plugin import PerfettoAnalysisPlugin

        plugin = PerfettoAnalysisPlugin()
        paths = plugin.register_skills()
        assert len(paths) >= 1
        assert any("SKILL.md" in p for p in paths)

    def test_skill_md_exists(self):
        """SKILL.md 文件存在。"""
        from pathlib import Path

        skill_md = Path(__file__).resolve().parent.parent / "modules" / "perfetto_analysis" / "skills" / "perfetto-analysis" / "SKILL.md"
        assert skill_md.exists()

    def test_atomic_directory_exists(self):
        """atomic/ 目录存在且包含 YAML 文件。"""
        from pathlib import Path

        atomic_dir = Path(__file__).resolve().parent.parent / "modules" / "perfetto_analysis" / "skills" / "perfetto-analysis" / "atomic"
        assert atomic_dir.exists()
        yaml_files = list(atomic_dir.glob("*.skill.yaml"))
        assert len(yaml_files) >= 100

    def test_fragments_directory_exists(self):
        """fragments/ 目录存在且包含 .sql 文件。"""
        from pathlib import Path

        frag_dir = Path(__file__).resolve().parent.parent / "modules" / "perfetto_analysis" / "skills" / "perfetto-analysis" / "fragments"
        assert frag_dir.exists()
        sql_files = list(frag_dir.glob("*.sql"))
        assert len(sql_files) >= 3
