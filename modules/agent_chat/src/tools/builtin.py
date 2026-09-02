# -*- coding: utf-8 -*-
"""内置 Agent 工具 — 工作目录管理。"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from toolkit.core.app_paths import get_output_dir

logger = logging.getLogger(__name__)


def _resolve_workspace_root() -> Path:
    """解析工作空间根目录。

    Agent 工作目录属于用户产物，走 output 层：
    - frozen: Documents/Game Perf Toolkit/agent_workspace/
    - dev: <data_dir>/output/agent_workspace/（受 LV_TOOLKIT_DATA_DIR 覆盖）
    """
    return get_output_dir("agent_workspace")


def create_workspace(name: str = "") -> str:
    """创建分析工作目录。

    Args:
        name: 工作目录名称前缀（留空则使用 'analysis'）

    Returns:
        创建的工作目录绝对路径
    """
    prefix = name.strip() if name else "analysis"
    prefix = "".join(c if c.isalnum() or c in "-_" else "_" for c in prefix)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"{prefix}_{timestamp}"

    workspace = _resolve_workspace_root() / dir_name
    workspace.mkdir(parents=True, exist_ok=True)

    logger.info("工作目录已创建: %s", workspace)
    return str(workspace)


def list_workspace_files(workspace_path: str) -> list[str]:
    """列出工作目录下的文件。

    Args:
        workspace_path: 工作目录路径

    Returns:
        文件路径列表
    """
    workspace = Path(workspace_path)
    if not workspace.exists():
        return [f"目录不存在: {workspace_path}"]
    if not workspace.is_dir():
        return [f"路径不是目录: {workspace_path}"]

    files: list[str] = []
    for f in sorted(workspace.rglob("*")):
        if f.is_file():
            rel = f.relative_to(workspace)
            size = f.stat().st_size
            if size < 1024:
                size_str = f"{size}B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f}KB"
            else:
                size_str = f"{size / 1024 / 1024:.1f}MB"
            files.append(f"{rel} ({size_str})")

    return files if files else ["(空目录)"]
