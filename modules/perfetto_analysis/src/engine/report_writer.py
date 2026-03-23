# -*- coding: utf-8 -*-
"""报告文件写入器：目录管理 + JSON/MD 写入 + DB 路径记录。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _trace_stem(trace_path: str | Path) -> str:
    """从 trace 完整路径提取不含扩展名的文件名。"""
    p = Path(trace_path)
    stem = p.stem
    if stem.endswith(".perfetto"):
        stem = Path(stem).stem
    return stem


def ensure_report_dir(
    trace_path: str | Path,
    output_dir: str | Path | None = None,
) -> Path:
    """
    创建报告目录并返回路径。
    output_dir 非空时: <output_dir>/<trace_stem>/
    output_dir 为空时: report/<trace_stem>/（相对于 cwd）
    """
    stem = _trace_stem(trace_path)
    if output_dir:
        base = Path(output_dir) / stem
    else:
        base = Path("output") / "trace_report" / stem
    base.mkdir(parents=True, exist_ok=True)
    data_dir = base / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return base


def write_analysis_file(
    report_dir: Path,
    dimension: str,
    data: dict[str, Any],
    fmt: str = "md",
    trace_path: str = "",
    process_name: str = "",
) -> Path:
    """将分析结果写入文件，返回文件路径。覆盖已有文件。"""
    if fmt == "json":
        file_path = report_dir / f"{dimension}_analysis.json"
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        file_path = report_dir / f"{dimension}_analysis.md"
        content = _build_dimension_md(dimension, data, trace_path, process_name)
        file_path.write_text(content, encoding="utf-8")
    return file_path


def _build_dimension_md(
    dimension: str,
    data: dict[str, Any],
    trace_path: str = "",
    process_name: str = "",
) -> str:
    """构建自包含的独立分析 Markdown 报告。"""
    from . import dimension_registry as dim_reg

    dim_info = dim_reg.DIMENSIONS.get(dimension, {})
    desc = dim_info.get("desc", dimension)

    lines = [f"# {desc} 分析报告", ""]
    lines.append("## 基础信息")
    lines.append("")
    if trace_path:
        lines.append(f"- **Trace**: `{trace_path}`")
    if process_name:
        lines.append(f"- **目标进程**: {process_name}")
    lines.append(f"- **分析维度**: {dimension}")
    lines.append("")

    lines.append("## 分析结果")
    lines.append("")

    actual_data = data.get("data", data)

    if isinstance(actual_data, list):
        for i, item in enumerate(actual_data):
            if isinstance(item, dict):
                idx = item.get("jank_index", i)
                jnum = item.get("jank_num", 0)
                lines.append(f"### Jank #{idx + 1}（丢帧数: {jnum}）")
                lines.append("")
                dim_content = item.get(dimension, {})
                if isinstance(dim_content, dict):
                    _dict_to_md(dim_content, lines, depth=0)
                lines.append("")
    elif isinstance(actual_data, dict):
        _dict_to_md(actual_data, lines, depth=0)

    lines.append("")
    return "\n".join(lines)


def _dict_to_md(d: dict, lines: list[str], depth: int = 0) -> None:
    """将 dict 递归转换为 Markdown 列表。"""
    indent = "  " * depth
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{indent}- **{k}**:")
            _dict_to_md(v, lines, depth + 1)
        elif isinstance(v, list):
            if not v:
                lines.append(f"{indent}- **{k}**: (空)")
            elif len(v) <= 5 and all(not isinstance(item, (dict, list)) for item in v):
                lines.append(f"{indent}- **{k}**: {v}")
            else:
                lines.append(f"{indent}- **{k}**: {len(v)} 条记录")
        else:
            lines.append(f"{indent}- **{k}**: {v}")


def write_jank_data_file(
    report_dir: Path,
    jank_index: int,
    data: dict[str, Any],
) -> Path:
    """将逐帧分析 JSON 写入 data/ 子目录。"""
    data_dir = report_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    file_path = data_dir / f"jank_{jank_index}_analysis.json"
    file_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return file_path


def write_summary_data_file(
    report_dir: Path,
    data: dict[str, Any],
) -> Path:
    """将整体分析 JSON 写入 data/ 子目录。"""
    data_dir = report_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    file_path = data_dir / "summary_analysis.json"
    file_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return file_path


def write_full_report(
    report_dir: Path,
    content: str,
) -> Path:
    """写入完整合并报告 (jank_report.md)。"""
    file_path = report_dir / "jank_report.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def record_report_path(
    conn: Any,
    trace_run_id: str,
    report_type: str,
    dimension: str,
    file_path: str,
    fmt: str = "md",
) -> None:
    """在 analysis_report 表中记录文件路径（INSERT OR REPLACE）。"""
    from . import storage
    storage.insert_analysis_report(
        conn, trace_run_id, report_type, dimension, file_path, fmt,
    )
