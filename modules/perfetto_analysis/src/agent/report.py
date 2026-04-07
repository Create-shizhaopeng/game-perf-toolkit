"""HTML 报告生成 — 使用 Jinja2 模板。"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from . import AnalysisReport

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"


_COMPLETION_LABELS = {
    "llm_complete": "LLM 分析完成",
    "llm_partial": "LLM 部分完成（因请求限制）",
    "engine_fallback": "引擎分析（Pydantic AI 不可用）",
    "engine_degraded": "引擎降级分析（因上下文超限）",
}


def generate_html_report(
    task_id: str,
    result_dir: str,
    trace_path: str,
    scene: str,
    process_name: str,
    conclusion: str,
    raw_data: dict,
) -> AnalysisReport:
    """生成 HTML 分析报告并保存原始数据。"""
    os.makedirs(result_dir, exist_ok=True)
    raw_data_dir = os.path.join(result_dir, "raw_data")
    os.makedirs(raw_data_dir, exist_ok=True)

    _save_raw_data(raw_data_dir, raw_data)

    completion = raw_data.get("completion", "llm_complete")
    completion_label = _COMPLETION_LABELS.get(completion, completion)

    html_path = os.path.join(result_dir, "report.html")
    html_content = _render_report(
        trace_path=trace_path,
        scene=scene,
        process_name=process_name,
        conclusion=conclusion,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        raw_data=raw_data,
        completion_label=completion_label,
    )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info("HTML 报告已生成: %s", html_path)

    summary = conclusion[:200] if conclusion else ""

    return AnalysisReport(
        task_id=task_id,
        html_path=html_path,
        raw_data_dir=raw_data_dir,
        summary=summary,
        trace_overview=raw_data.get("trace_overview", {}),
        root_causes=raw_data.get("root_causes", []),
    )


def _save_raw_data(raw_data_dir: str, data: dict) -> None:
    """保存原始数据为 JSON 文件。"""
    for key, value in data.items():
        try:
            file_path = os.path.join(raw_data_dir, f"{key}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False, indent=2, default=str)
        except Exception as exc:
            logger.warning("保存原始数据 '%s' 失败: %s", key, exc)


def _render_report(
    trace_path: str,
    scene: str,
    process_name: str,
    conclusion: str,
    timestamp: str,
    raw_data: dict,
    completion_label: str = "LLM 分析完成",
) -> str:
    """渲染 HTML 报告。优先使用 Jinja2 模板，降级使用内嵌模板。"""
    try:
        import jinja2

        template_path = _TEMPLATE_DIR / "report.html"
        if template_path.exists():
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
                autoescape=True,
            )
            template = env.get_template("report.html")
            return template.render(
                trace_path=trace_path,
                trace_name=Path(trace_path).name,
                scene=scene,
                process_name=process_name or "自动检测",
                conclusion=conclusion,
                timestamp=timestamp,
                raw_data=raw_data,
                completion_label=completion_label,
            )
    except ImportError:
        logger.debug("Jinja2 不可用，使用内嵌模板")
    except Exception as exc:
        logger.warning("Jinja2 渲染失败: %s，使用内嵌模板", exc)

    return _fallback_render(
        trace_path, scene, process_name, conclusion, timestamp, completion_label
    )


def _markdown_to_html(text: str) -> str:
    """简易 Markdown 转 HTML（标题、列表、加粗、段落）。"""
    import re
    from html import escape

    lines = escape(text).split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            result.append(f"<h3>{stripped[3:]}</h3>")
        elif stripped.startswith("# "):
            result.append(f"<h2>{stripped[2:]}</h2>")
        elif stripped.startswith("- "):
            content = stripped[2:]
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
            result.append(f"<li>{content}</li>")
        elif stripped:
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)
            result.append(f"<p>{content}</p>")
        else:
            result.append("<br/>")
    return "\n".join(result)


def _fallback_render(
    trace_path: str,
    scene: str,
    process_name: str,
    conclusion: str,
    timestamp: str,
    completion_label: str = "LLM 分析完成",
) -> str:
    """内嵌 HTML 模板（Jinja2 不可用时的降级方案）。"""
    from html import escape

    is_degraded = "降级" in completion_label or "引擎" in completion_label
    badge_color = "#ff9800" if is_degraded else "#4caf50"

    return f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Perfetto 分析报告 — {escape(Path(trace_path).name)}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 0; padding: 20px; background: #f5f5f5; color: #333; }}
  .container {{ max-width: 960px; margin: 0 auto; background: #fff;
               border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
  h1 {{ color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 12px; }}
  h2 {{ color: #333; margin-top: 28px; }}
  .meta {{ background: #f8f9fa; padding: 16px; border-radius: 6px; margin: 16px 0; }}
  .meta dt {{ font-weight: 600; color: #555; }}
  .meta dd {{ margin: 0 0 8px 0; }}
  .badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px;
            font-size: 13px; font-weight: 600; color: #fff; background: {badge_color}; }}
  .conclusion {{ background: #e8f5e9; padding: 20px; border-radius: 6px;
                border-left: 4px solid #4caf50; white-space: pre-wrap; }}
  .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #eee;
            color: #999; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
  <h1>Perfetto 分析报告</h1>
  <div class="meta">
    <dl>
      <dt>Trace 文件</dt><dd>{escape(Path(trace_path).name)}</dd>
      <dt>分析场景</dt><dd>{escape(scene)}</dd>
      <dt>目标进程</dt><dd>{escape(process_name or '自动检测')}</dd>
      <dt>分析时间</dt><dd>{escape(timestamp)}</dd>
      <dt>分析方式</dt><dd><span class="badge">{escape(completion_label)}</span></dd>
    </dl>
  </div>
  <h2>分析结论</h2>
  <div class="conclusion">{_markdown_to_html(conclusion)}</div>
  <h2>原始数据</h2>
  <p>原始分析数据已保存在 <code>raw_data/</code> 子目录中。</p>
  <div class="footer">
    由 LV Game Toolkit Perfetto AI 分析引擎生成 | {escape(timestamp)}
  </div>
</div>
</body>
</html>"""
