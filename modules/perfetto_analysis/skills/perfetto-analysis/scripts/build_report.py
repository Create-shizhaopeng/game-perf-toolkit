# -*- coding: utf-8 -*-
"""Perfetto 分析报告构建器 — 章节渲染 + HTML 组装。

用法:
    python build_report.py init --output-dir <dir> --header '{"trace_name":...}'
    python build_report.py chapter --chapter-id fps --data data.json \
        --chapters-dir templates/chapters/ --fragments-dir templates/fragments/ \
        --output <dir>/chapters/fps.html
    python build_report.py conclusion --data data.json \
        --fragments-dir templates/fragments/ --output <dir>/conclusion.html
    python build_report.py assemble --output-dir <dir> \
        --template templates/base.html --output <dir>/report.html

不依赖 toolkit.core，可独立于框架使用。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, BaseLoader, TemplateNotFound
except ImportError:
    Environment = None  # type: ignore[assignment]


# ──────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────

def _skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file, with fallback for missing PyYAML."""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        pass
    # Pure-Python fallback: YAML files in this project use a simple subset
    # (no anchors, no multi-line scalars with pipes except in 'description')
    return _load_yaml_simple(path)


def _load_yaml_simple(path: Path) -> dict[str, Any]:
    """Minimal YAML parser for the subset used by chapter/*.yaml files."""
    import re

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[Any] | None = None
    list_of_dicts: list[dict[str, Any]] | None = None
    current_dict: dict[str, Any] | None = None
    in_list_item = False
    indent_level = 0

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Count leading spaces
        leading = len(line) - len(line.lstrip(" "))

        # Top-level key: value
        if ":" in stripped and not stripped.startswith("-") and leading == 0:
            in_list_item = False
            current_list = None
            list_of_dicts = None
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val:
                if val in ("true", "false"):
                    result[key] = val == "true"
                elif val.isdigit():
                    result[key] = int(val)
                else:
                    result[key] = val
            else:
                result[key] = {}
                current_key = key
            continue

        # Simple nested key: value
        if ":" in stripped and not stripped.startswith("-") and leading >= 2:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if current_key and isinstance(result.get(current_key), dict):
                if val in ("true", "false"):
                    result[current_key][key] = val == "true"
                elif val.isdigit():
                    result[current_key][key] = int(val)
                elif val:
                    result[current_key][key] = val
                else:
                    result[current_key][key] = {}
            continue

        # List item
        if stripped.startswith("- "):
            item_text = stripped[2:]
            if ":" in item_text:
                key, _, val = item_text.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if current_list is not None:
                    current_list.append({key: val})
                elif list_of_dicts is not None:
                    list_of_dicts.append({key: val})
            else:
                val = item_text.strip().strip('"').strip("'")
                if current_list is not None:
                    current_list.append(val)
            continue

    return result


def _resolve_path(rel: str) -> Path:
    """Resolve a path: absolute paths stay absolute, relative paths are relative to CWD."""
    p = Path(rel)
    if p.is_absolute():
        return p
    return Path.cwd() / rel


def _format_value(value: Any, fmt: str | None) -> str:
    """Format a value according to the field format hint."""
    if value is None:
        return "-"
    if fmt is None:
        return str(value)
    if fmt in ("integer", "compact"):
        return f"{int(value):,}" if isinstance(value, (int, float)) else str(value)
    if fmt == "decimal_1":
        return f"{float(value):.1f}"
    if fmt == "decimal_2":
        return f"{float(value):.2f}"
    if fmt == "decimal_3":
        return f"{float(value):.3f}"
    if fmt == "percentage":
        return f"{float(value)}%"
    if fmt == "duration_ms":
        return f"{float(value)}ms"
    if fmt == "duration_us":
        return f"{float(value)}us"
    if fmt == "duration_s":
        return f"{float(value)}s"
    if fmt == "memory_mb":
        return f"{float(value):.0f}MB"
    if fmt == "fps":
        return f"{int(value)}"
    if fmt == "frequency_khz":
        return f"{int(value)}KHz"
    if fmt == "frequency_mhz":
        return f"{int(value)}MHz"
    if fmt == "timestamp_s":
        return f"{float(value):.3f}s"
    if fmt == "datetime":
        return str(value)
    if fmt == "boolean":
        return "是" if value else "否"
    return str(value)


def _compute_severity(value: Any, thresholds: dict[str, str] | None) -> str:
    """Compute severity level from value and thresholds."""
    if thresholds is None:
        return "normal"
    try:
        fval = float(value)
    except (ValueError, TypeError):
        # String comparison
        sval = str(value)
        for level, expr in thresholds.items():
            if sval == expr:
                return level
        return "normal"
    for level in ("excellent", "good", "warning", "critical"):
        expr = thresholds.get(level)
        if expr is None:
            continue
        if level == "excellent":
            if expr.startswith("<") and fval < float(expr[1:]):
                return level
            if expr.startswith(">=") and fval >= float(expr[2:]):
                return level
        elif level == "good":
            if expr.startswith("<") and fval < float(expr[1:]):
                return level
        elif level == "warning":
            if expr.startswith("<") and fval < float(expr[1:]):
                return level
        elif level == "critical":
            if expr.startswith(">=") and fval >= float(expr[2:]):
                return level
            if expr.startswith(">") and fval > float(expr[1:]):
                return level
    return "normal"


# ──────────────────────────────────────────────
# Jinja2 rendering
# ──────────────────────────────────────────────

def _create_jinja_env(fragments_dir: Path) -> "Environment":
    """Create a Jinja2 environment that loads fragments from disk."""
    from jinja2 import FileSystemLoader

    return Environment(
        loader=FileSystemLoader(str(fragments_dir)),
        autoescape=False,
    )


def _render_fragment(
    env: "Environment",
    fragment_name: str,
    context: dict[str, Any],
) -> str:
    """Render a single fragment by name (without .j2 extension)."""
    template = env.get_template(f"{fragment_name}.j2")
    return template.render(**context)


# ──────────────────────────────────────────────
# public API (importable without argparse)
# ──────────────────────────────────────────────

def init_report(output_dir: str, header: dict[str, Any]) -> None:
    """Initialize report directory with header.json.

    Args:
        output_dir: Path to the report output directory.
        header: Dict with trace_name, analysis_time, etc.
    """
    od = Path(output_dir)
    od.mkdir(parents=True, exist_ok=True)
    (od / "chapters").mkdir(exist_ok=True)
    (od / "chapter_data").mkdir(exist_ok=True)

    with open(od / "header.json", "w", encoding="utf-8") as f:
        json.dump(header, f, ensure_ascii=False, indent=2)
    print(f"OK: header.json written to {od}")


def build_chapter(
    chapter_id: str,
    data: dict[str, Any],
    output_path: str,
    *,
    chapters_dir: str | None = None,
    fragments_dir: str | None = None,
) -> None:
    """Render a single chapter to HTML.

    Args:
        chapter_id: Chapter identifier (fps, cpu, gpu, etc.).
        data: Chapter data dict with 'title' and 'data' keys.
        output_path: Output HTML file path.
        chapters_dir: Path to templates/chapters/ directory.
        fragments_dir: Path to templates/fragments/ directory.
    """
    if Environment is None:
        raise RuntimeError("jinja2 not installed. Run: pip install jinja2")

    skill_root = _skill_root()
    cd = _resolve_path(chapters_dir) if chapters_dir else skill_root / "templates" / "chapters"
    fd = _resolve_path(fragments_dir) if fragments_dir else skill_root / "templates" / "fragments"
    op = Path(output_path)

    # Load render config
    render_path = cd / f"{chapter_id}_render.yaml"
    if not render_path.exists():
        raise FileNotFoundError(f"Render config not found: {render_path}")
    render_cfg = _load_yaml(render_path)

    # Load data schema for field metadata
    data_path = cd / f"{chapter_id}_data.yaml"
    data_schema = {}
    if data_path.exists():
        data_schema = _load_yaml(data_path)

    env = _create_jinja_env(fd)

    html_parts = []
    chapter_title = data.get("title", chapter_id)
    html_parts.append(f'<div class="chapter-header"><h2>{chapter_title}</h2></div>')

    for section in render_cfg.get("render", {}).get("sections", []):
        section_id = section["id"]
        section_data_raw = data.get("data", {}).get(section_id)
        if section_data_raw is None:
            if section.get("optional"):
                continue
            html_parts.append(f'<!-- section "{section_id}": no data -->')
            continue

        field_schema = _find_section_schema(data_schema, section_id)

        if section["fragment"] == "metric_grid":
            metrics = _prepare_metrics(section_data_raw, field_schema)
            section_html = _render_fragment(env, "metric_grid", {"metrics": metrics})
        elif section["fragment"] == "data_table":
            columns = _prepare_columns(section_data_raw, field_schema, data)
            rows = _prepare_rows(section_data_raw, columns)
            section_html = _render_fragment(env, "data_table", {
                "section_title": _section_label(field_schema, section_id),
                "section_note": _section_note(field_schema),
                "columns": columns,
                "rows": rows,
                "show_distribution_bar": section.get("extra", {}).get("show_distribution_bar", False),
            })
        elif section["fragment"] == "root_cause_table":
            items = _prepare_root_causes(section_data_raw)
            section_html = _render_fragment(env, "root_cause_table", {
                "section_title": _section_label(field_schema, section_id),
                "items": items,
            })
        else:
            section_html = f'<!-- unknown fragment: {section["fragment"]} -->'

        html_parts.append(section_html)

    chapter_html = "\n".join(html_parts)

    op.parent.mkdir(parents=True, exist_ok=True)
    with open(op, "w", encoding="utf-8") as f:
        f.write(chapter_html)
    print(f"OK: {op}")


def build_conclusion(
    data: dict[str, Any],
    output_path: str,
    *,
    fragments_dir: str | None = None,
) -> None:
    """Render conclusion HTML.

    Args:
        data: Conclusion data dict with overall_rating, summary, etc.
        output_path: Output HTML file path.
        fragments_dir: Path to templates/fragments/ directory.
    """
    if Environment is None:
        raise RuntimeError("jinja2 not installed. Run: pip install jinja2")

    skill_root = _skill_root()
    fd = _resolve_path(fragments_dir) if fragments_dir else skill_root / "templates" / "fragments"
    op = Path(output_path)

    env = _create_jinja_env(fd)
    section_html = _render_fragment(env, "conclusion_text", data)

    op.parent.mkdir(parents=True, exist_ok=True)
    with open(op, "w", encoding="utf-8") as f:
        f.write(section_html)
    print(f"OK: {op}")


def assemble_report(
    output_dir: str,
    *,
    template_path: str | None = None,
    output_path: str | None = None,
) -> None:
    """Assemble all chapter HTML + conclusion into final report.

    Args:
        output_dir: Report directory containing chapters/, chapter_data/, conclusion.html.
        template_path: Path to base.html template.
        output_path: Output HTML file path. Defaults to <output_dir>/report.html.
    """
    if Environment is None:
        raise RuntimeError("jinja2 not installed. Run: pip install jinja2")

    skill_root = _skill_root()
    od = Path(output_dir)
    tp = _resolve_path(template_path) if template_path else skill_root / "templates" / "base.html"
    op = Path(output_path) if output_path else od / "report.html"

    # Load header
    header = {}
    header_path = od / "header.json"
    if header_path.exists():
        with open(header_path, "r", encoding="utf-8") as f:
            header = json.load(f)

    # Collect chapters in order
    chapters_dir = od / "chapters"
    chapters_html: list[str] = []

    chapter_order = _get_chapter_order(skill_root / "templates" / "chapters")

    for chapter_id in chapter_order:
        chapter_path = chapters_dir / f"{chapter_id}.html"
        if chapter_path.exists():
            with open(chapter_path, "r", encoding="utf-8") as f:
                chapters_html.append(f.read())

    if chapters_dir.exists():
        for f in sorted(chapters_dir.iterdir()):
            if f.suffix == ".html":
                if f.stem not in chapter_order:
                    with open(f, "r", encoding="utf-8") as fh:
                        chapters_html.append(fh.read())

    # Load conclusion
    conclusion_html = ""
    conclusion_path = od / "conclusion.html"
    if conclusion_path.exists():
        with open(conclusion_path, "r", encoding="utf-8") as f:
            conclusion_html = f.read()

    # Read template and replace placeholders
    with open(tp, "r", encoding="utf-8") as f:
        template_src = f.read()

    html = template_src
    html = html.replace("{{ chapters | join('\\n') }}", "\n".join(chapters_html))
    html = html.replace("{{ conclusion }}", conclusion_html)
    html = html.replace("{{ trace_name }}", header.get("trace_name", "Unknown"))
    html = html.replace("{{ analysis_time }}", header.get("analysis_time", ""))

    op.parent.mkdir(parents=True, exist_ok=True)
    with open(op, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK: report assembled -> {op}")


# ──────────────────────────────────────────────
# CLI wrappers (delegate to public API)
# ──────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> None:
    """CLI wrapper for init_report."""
    init_report(args.output_dir, json.loads(args.header))


def cmd_chapter(args: argparse.Namespace) -> None:
    """CLI wrapper for build_chapter."""
    with open(args.data, "r", encoding="utf-8") as f:
        chapter_data = json.load(f)
    build_chapter(
        chapter_id=args.chapter_id,
        data=chapter_data,
        output_path=args.output,
        chapters_dir=args.chapters_dir,
        fragments_dir=args.fragments_dir,
    )


def cmd_conclusion(args: argparse.Namespace) -> None:
    """CLI wrapper for build_conclusion."""
    with open(args.data, "r", encoding="utf-8") as f:
        conclusion_data = json.load(f)
    build_conclusion(
        data=conclusion_data,
        output_path=args.output,
        fragments_dir=args.fragments_dir,
    )


def cmd_assemble(args: argparse.Namespace) -> None:
    """CLI wrapper for assemble_report."""
    assemble_report(
        output_dir=args.output_dir,
        template_path=args.template,
        output_path=args.output,
    )


# ──────────────────────────────────────────────
# data preparation helpers
# ──────────────────────────────────────────────

def _find_section_schema(data_schema: dict, section_id: str) -> dict[str, Any]:
    """Find the schema definition for a section."""
    ds = data_schema.get("data_schema", data_schema)
    if isinstance(ds, dict):
        return ds.get(section_id, {})
    return {}


def _section_label(field_schema: dict, default: str) -> str:
    return field_schema.get("label", default.replace("_", " ").title())


def _section_note(field_schema: dict) -> str | None:
    return field_schema.get("note")


def _prepare_metrics(section_data: dict, field_schema: dict) -> list[dict[str, Any]]:
    """Prepare metrics for metric_grid.j2."""
    metrics = []
    fields = field_schema.get("fields", [])

    if isinstance(section_data, dict):
        for fdef in fields:
            key = fdef.get("key", "")
            if key in section_data:
                value = section_data[key]
                severity = _compute_severity(value, fdef.get("severity"))
                formatted = _format_value(value, fdef.get("format"))
                metrics.append({
                    "label": fdef.get("label", key),
                    "value": value,
                    "_formatted_value": formatted,
                    "_severity": severity,
                    "_unit": fdef.get("unit", ""),
                })
    return metrics


def _prepare_columns(
    section_data: dict,
    field_schema: dict,
    _chapter_data: dict,
) -> list[dict[str, Any]]:
    """Prepare column definitions for data_table.j2."""
    columns = field_schema.get("columns", [])
    if columns:
        return columns

    # Fallback: infer from data
    if isinstance(section_data, list) and section_data:
        first = section_data[0]
        if isinstance(first, dict):
            return [{"key": k, "label": k.replace("_", " ").title()} for k in first]
    return []


def _prepare_rows(
    section_data: list[dict[str, Any]] | dict,
    columns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Prepare row data for data_table.j2 with formatted values."""
    if isinstance(section_data, dict):
        # Single object → wrap in list
        section_data = [section_data]

    rows = []
    for item in section_data or []:
        if isinstance(item, dict):
            row = {}
            for col in columns:
                key = col.get("key", col) if isinstance(col, dict) else col
                raw = item.get(key, "")
                fmt = col.get("format") if isinstance(col, dict) else None
                row[key] = _format_value(raw, fmt)
                # Keep raw for distribution bar
                if key in ("percentage", "count"):
                    row[key + "_raw"] = raw
            rows.append(row)
    return rows


def _prepare_root_causes(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prepare root cause items for root_cause_table.j2."""
    result = []
    for item in items or []:
        result.append({
            "rank": item.get("rank", len(result) + 1),
            "severity": item.get("severity", "INFO"),
            "cause": item.get("cause", ""),
            "evidence": item.get("evidence", ""),
            "impact": item.get("impact", ""),
            "suggestion": item.get("suggestion", ""),
        })
    return result


def _get_chapter_order(chapters_dir: Path) -> list[str]:
    """Get chapter IDs ordered by their order field."""
    ordered: list[tuple[int, str]] = []
    if chapters_dir.exists():
        for f in sorted(chapters_dir.iterdir()):
            if not f.name.endswith("_data.yaml") and not f.name.endswith("_render.yaml"):
                continue
            if f.name.endswith("_data.yaml"):
                chapter_id = f.name.replace("_data.yaml", "")
                cfg = _load_yaml(f)
                order = cfg.get("order", 50)
                ordered.append((order, chapter_id))
    ordered.sort()
    return [cid for _, cid in ordered if cid != "root_causes"] + ["root_causes"]


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Perfetto 分析报告构建器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "子命令:\n"
            "  init        初始化报告目录 + header\n"
            "  chapter     渲染单个章节 HTML\n"
            "  conclusion  渲染结论 HTML\n"
            "  assemble    组装最终 report.html\n\n"
            "示例:\n"
            "  build_report.py init -o out/ --header '{\"trace_name\":\"test\"}'\n"
            "  build_report.py chapter --chapter-id fps --data d.json -o out/chapters/fps.html\n"
            "  build_report.py conclusion --data c.json -o out/conclusion.html\n"
            "  build_report.py assemble -d out/ -t templates/base.html -o out/report.html\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # init
    p_init = sub.add_parser("init", help="初始化报告目录")
    p_init.add_argument("-o", "--output-dir", required=True)
    p_init.add_argument("--header", required=True, help="Header JSON string")

    # chapter
    p_ch = sub.add_parser("chapter", help="渲染单个章节")
    p_ch.add_argument("--chapter-id", required=True)
    p_ch.add_argument("--data", required=True, help="Chapter data JSON file")
    p_ch.add_argument("--chapters-dir", default="templates/chapters/")
    p_ch.add_argument("--fragments-dir", default="templates/fragments/")
    p_ch.add_argument("-o", "--output", required=True, help="Output HTML path")

    # conclusion
    p_conc = sub.add_parser("conclusion", help="渲染结论")
    p_conc.add_argument("--data", required=True, help="Conclusion data JSON file")
    p_conc.add_argument("--fragments-dir", default="templates/fragments/")
    p_conc.add_argument("-o", "--output", required=True, help="Output HTML path")

    # assemble
    p_asm = sub.add_parser("assemble", help="组装最终报告")
    p_asm.add_argument("-d", "--output-dir", required=True)
    p_asm.add_argument("-t", "--template", default="templates/base.html")
    p_asm.add_argument("-o", "--output", required=True, help="Final report.html path")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "chapter":
        cmd_chapter(args)
    elif args.command == "conclusion":
        cmd_conclusion(args)
    elif args.command == "assemble":
        cmd_assemble(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
