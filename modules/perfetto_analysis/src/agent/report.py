"""HTML 报告生成 — 基于 AnalysisOutput 三区块结构 + Jinja2 降级。"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from . import AnalysisOutput, AnalysisReport

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"


_COMPLETION_LABELS = {
    "llm_complete": "LLM 分析完成",
    "llm_partial": "LLM 部分完成（因请求限制）",
    "engine_fallback": "引擎分析（Pydantic AI 不可用）",
}


def generate_html_report(
    task_id: str,
    result_dir: str,
    trace_path: str,
    scene: str,
    process_name: str,
    conclusion: str,
    raw_data: dict,
    analysis_output: AnalysisOutput | None = None,
) -> AnalysisReport:
    """生成 HTML 分析报告。优先使用 AnalysisOutput 三区块结构。"""
    os.makedirs(result_dir, exist_ok=True)
    raw_data_dir = os.path.join(result_dir, "raw_data")
    os.makedirs(raw_data_dir, exist_ok=True)

    _save_raw_data(raw_data_dir, raw_data)

    completion = raw_data.get("completion", "llm_complete")
    completion_label = _COMPLETION_LABELS.get(completion, completion)

    html_path = os.path.join(result_dir, "report.html")

    if analysis_output and analysis_output.root_causes:
        html_content = _render_structured_report(
            trace_path=trace_path,
            scene=scene,
            process_name=process_name,
            analysis_output=analysis_output,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            completion_label=completion_label,
        )
    else:
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
    root_causes_dicts = []
    if analysis_output and analysis_output.root_causes:
        root_causes_dicts = [rc.model_dump() for rc in analysis_output.root_causes]

    return AnalysisReport(
        task_id=task_id,
        html_path=html_path,
        raw_data_dir=raw_data_dir,
        summary=summary,
        trace_overview=raw_data.get("trace_overview", {}),
        root_causes=root_causes_dicts or raw_data.get("root_causes", []),
    )


def _render_structured_report(
    trace_path: str,
    scene: str,
    process_name: str,
    analysis_output: AnalysisOutput,
    timestamp: str,
    completion_label: str = "LLM 分析完成",
) -> str:
    """基于 AnalysisOutput 三区块结构渲染 HTML 报告。"""
    from html import escape

    is_degraded = "降级" in completion_label or "引擎" in completion_label
    badge_color = "#ff9800" if is_degraded else "#4caf50"

    severity_colors = {
        "CRITICAL": "#d32f2f",
        "HIGH": "#f57c00",
        "WARNING": "#fbc02d",
        "INFO": "#1976d2",
    }

    root_cause_rows = ""
    for rc in analysis_output.root_causes:
        sev_color = severity_colors.get(rc.severity, "#757575")
        quant_html = ""
        if rc.quantitative:
            quant_items = "".join(
                f"<li><strong>{escape(str(k))}</strong>: {escape(str(v))}</li>"
                for k, v in rc.quantitative.items()
            )
            quant_html = f'<ul class="quant">{quant_items}</ul>'

        suggestion_html = ""
        if rc.suggestion:
            suggestion_html = f'<div class="suggestion">{escape(rc.suggestion)}</div>'

        root_cause_rows += f"""\
    <tr>
      <td><code>{escape(rc.tag)}</code></td>
      <td><span class="severity" style="background:{sev_color}">{escape(rc.severity)}</span></td>
      <td>{escape(rc.qualitative)}{quant_html}</td>
      <td class="evidence">{escape(rc.evidence)}</td>
      <td>{suggestion_html}</td>
    </tr>
"""

    detailed_html = _markdown_to_html(analysis_output.detailed_report) if analysis_output.detailed_report else ""
    detailed_html = _replace_chart_placeholders(detailed_html)

    return f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Perfetto 分析报告 - {escape(Path(trace_path).name)}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 0; padding: 20px; background: #f5f5f5; color: #333; }}
  .container {{ max-width: 1080px; margin: 0 auto; }}
  .section {{ background: #fff; border-radius: 8px; padding: 24px 32px;
             box-shadow: 0 1px 3px rgba(0,0,0,.08); margin-bottom: 16px; }}
  h1 {{ color: #1a73e8; margin: 0 0 16px; font-size: 24px; }}
  h2 {{ color: #333; margin: 24px 0 12px; font-size: 18px; border-bottom: 1px solid #eee; padding-bottom: 8px; }}
  .meta dl {{ display: grid; grid-template-columns: 120px 1fr; gap: 4px 12px; margin: 0; }}
  .meta dt {{ font-weight: 600; color: #555; }}
  .meta dd {{ margin: 0; }}
  .badge {{ display: inline-block; padding: 3px 10px; border-radius: 10px;
            font-size: 12px; font-weight: 600; color: #fff; background: {badge_color}; }}
  .conclusion-box {{ background: #e8f5e9; padding: 16px 20px; border-radius: 6px;
                    border-left: 4px solid #4caf50; margin: 12px 0; white-space: pre-wrap; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
  th {{ background: #f5f5f5; text-align: left; padding: 10px 12px; font-size: 13px;
       border-bottom: 2px solid #ddd; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #eee; vertical-align: top; font-size: 13px; }}
  .severity {{ display: inline-block; padding: 2px 8px; border-radius: 8px;
              font-size: 11px; font-weight: 700; color: #fff; }}
  .evidence {{ color: #666; font-size: 12px; max-width: 240px; }}
  .suggestion {{ color: #2e7d32; font-size: 12px; margin-top: 4px; }}
  .quant {{ margin: 6px 0 0; padding-left: 16px; font-size: 12px; color: #555; }}
  .chart-placeholder {{ background: #fff3e0; border: 1px dashed #ff9800; border-radius: 6px;
                       padding: 16px; text-align: center; color: #e65100; margin: 12px 0; }}
  .detailed {{ white-space: pre-wrap; line-height: 1.7; }}
  .footer {{ margin-top: 16px; padding: 12px 0; color: #999; font-size: 12px; text-align: center; }}
</style>
</head>
<body>
<div class="container">

  <!-- Section 1: 问题定义 -->
  <div class="section">
    <h1>Perfetto 分析报告</h1>
    <div class="meta">
      <dl>
        <dt>用户问题</dt><dd>{escape(analysis_output.user_intent_summary)}</dd>
        <dt>Trace 文件</dt><dd>{escape(Path(trace_path).name)}</dd>
        <dt>Trace 信息</dt><dd>{escape(analysis_output.trace_info)}</dd>
        <dt>分析场景</dt><dd>{escape(scene)}</dd>
        <dt>目标进程</dt><dd>{escape(process_name or '自动检测')}</dd>
        <dt>分析时间</dt><dd>{escape(timestamp)}</dd>
        <dt>分析方式</dt><dd><span class="badge">{escape(completion_label)}</span></dd>
      </dl>
    </div>
  </div>

  <!-- Section 2: 分析摘要 + 根因表格 -->
  <div class="section">
    <h2>分析结论</h2>
    <div class="conclusion-box">{escape(analysis_output.overall_conclusion)}</div>

    <h2>根因分析 ({len(analysis_output.root_causes)} 项)</h2>
    <table>
      <thead>
        <tr>
          <th>根因标签</th><th>严重度</th><th>定性描述</th><th>证据来源</th><th>建议</th>
        </tr>
      </thead>
      <tbody>
        {root_cause_rows}
      </tbody>
    </table>
  </div>

  <!-- Section 3: 详细分析报告 -->
  <div class="section">
    <h2>详细分析报告</h2>
    <div class="detailed">{detailed_html}</div>
  </div>

  <div class="footer">
    由 LV Game Toolkit Perfetto AI 分析引擎生成 | {escape(timestamp)}
  </div>
</div>
</body>
</html>"""


def _replace_chart_placeholders(html: str) -> str:
    """T015: 识别 {{chart:key_name}} 占位符并替换为占位 HTML。"""
    def _chart_placeholder(match: re.Match) -> str:
        key = match.group(1)
        return (
            f'<div class="chart-placeholder">'
            f'[图表: {key}] — 可视化待实现'
            f'</div>'
        )

    return re.sub(r"\{\{chart:(\w+)\}\}", _chart_placeholder, html)


def _save_raw_data(raw_data_dir: str, data: dict) -> None:
    """保存原始数据为 JSON 文件。"""
    from pydantic import BaseModel

    for key, value in data.items():
        try:
            file_path = os.path.join(raw_data_dir, f"{key}.json")
            if isinstance(value, BaseModel):
                serializable = value.model_dump()
            else:
                serializable = value
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2, default=str)
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
