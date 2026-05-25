# -*- coding: utf-8 -*-
"""PerfettoSQL 执行器 — 独立于框架，只依赖 perfetto Python 包。

用法:
    python sql_executor.py --help   查看使用说明

本文件不提供 CLI 执行入口，仅通过 execute_sql() 函数供程序调用。
如需执行 SQL，请在 Python 代码中 import 后调用 execute_sql(trace_path, sql)。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _discover_bin_path() -> str | None:
    """按优先级自动发现 trace_processor_shell 二进制路径。

    优先级:
    1. perfetto 预置缓存 ~/.local/share/perfetto/prebuilts/
    2. skill 同级目录 trace_processor_shell(.exe)
    3. 返回 None（由 perfetto 包自动下载）
    """
    import platform

    is_win = platform.system() == "Windows"
    exe_suffix = ".exe" if is_win else ""
    bin_name = f"trace_processor_shell{exe_suffix}"

    # 1. perfetto 包默认缓存位置
    candidates = [
        Path.home() / ".local" / "share" / "perfetto" / "prebuilts" / bin_name,
    ]

    # 2. skill 同级目录
    if "__file__" in dir():
        try:
            skill_scripts = Path(__file__).resolve().parent
            candidates.append(skill_scripts / bin_name)
        except NameError:
            pass

    for p in candidates:
        if p.is_file():
            return str(p)

    return None


def execute_sql(
    trace_path: str,
    sql: str,
    bin_path: str | None = None,
    load_timeout: int = 30,
) -> dict[str, Any]:
    """对 Perfetto trace 文件执行 SQL 查询，返回结果。

    不依赖 toolkit.core，可独立于框架使用。

    Args:
        trace_path: Perfetto trace 文件路径（.perfetto-trace / .perfetto-trace.gz）
        sql: PerfettoSQL 查询语句
        bin_path: trace_processor_shell 二进制路径。
                  不传则按优先级自动发现，最终兜底 perfetto 包自动下载。
        load_timeout: trace_processor 启动超时秒数（默认 30）

    Returns:
        dict 包含:
        - success: bool — 是否执行成功
        - rows: list[dict] — 查询结果行（成功时）
        - error: str — 错误信息（失败时）
        - row_count: int — 结果行数
    """
    trace = Path(trace_path)
    if not trace.is_file():
        return {
            "success": False,
            "rows": [],
            "error": f"trace 文件不存在: {trace_path}",
            "row_count": 0,
        }

    try:
        from perfetto.trace_processor import TraceProcessor, TraceProcessorConfig
    except ImportError:
        return {
            "success": False,
            "rows": [],
            "error": "perfetto 包未安装，请执行: pip install perfetto>=0.16.0",
            "row_count": 0,
        }

    if bin_path is None:
        bin_path = _discover_bin_path()

    tp = None
    try:
        config = TraceProcessorConfig(
            bin_path=bin_path,
            load_timeout=load_timeout,
        )
        tp = TraceProcessor(trace=str(trace.resolve()), config=config)
        result = tp.query(sql)

        rows = []
        for row in result:
            row_dict = {}
            for col_name in result.column_names:
                val = getattr(row, col_name, None)
                row_dict[col_name] = _serialize_value(val)
            rows.append(row_dict)

        return {
            "success": True,
            "rows": rows,
            "row_count": len(rows),
        }
    except Exception as exc:
        logger.error("PerfettoSQL 执行失败: %s", exc)
        return {
            "success": False,
            "rows": [],
            "error": str(exc),
            "row_count": 0,
        }
    finally:
        if tp is not None:
            try:
                tp.close()
            except Exception:
                pass


def _serialize_value(val: Any) -> Any:
    """将 Perfetto 返回值序列化为 JSON 兼容类型。"""
    if val is None:
        return None
    if isinstance(val, (int, float, bool, str)):
        return val
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val)


_HELP_TEXT = """\
PerfettoSQL 执行器 — Skill 内部脚本

功能:
  对 Perfetto trace 文件执行 PerfettoSQL 查询，返回 JSON 结构化结果。

调用方式:
  from sql_executor import execute_sql
  result = execute_sql(trace_path="/path/to/trace.perfetto-trace", sql="SELECT 1")

参数:
  trace_path   (str, 必填): Perfetto trace 文件路径
  sql          (str, 必填): PerfettoSQL 查询语句
  bin_path     (str, 可选): trace_processor_shell 二进制路径，不传则自动下载
  load_timeout (int, 可选): 启动超时秒数，默认 30

返回结构:
  {
    "success": bool,      # 是否执行成功
    "rows": list[dict],   # 查询结果行
    "row_count": int,     # 结果行数
    "error": str | null   # 错误信息（失败时）
  }

依赖:
  仅依赖 perfetto Python 包 (pip install perfetto>=0.16.0)
  不依赖任何框架代码 (toolkit.core 等)
"""


if __name__ == "__main__":
    print(_HELP_TEXT)
