# -*- coding: utf-8 -*-
"""MCP 管理层 — 服务器发现、连接和工具桥接。"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..models import MCPServerConfig

logger = logging.getLogger(__name__)

MCP_MIN_VERSION = "1.26.0"


def check_mcp_available() -> tuple[bool, str]:
    """检查 MCP SDK 是否已安装且版本满足要求。

    Returns:
        (available, message)
    """
    try:
        import mcp  # noqa: F811
        version = getattr(mcp, "__version__", "0.0.0")
        from packaging.version import Version
        if Version(version) < Version(MCP_MIN_VERSION):
            return False, f"MCP SDK 版本过低: {version}（需要 >= {MCP_MIN_VERSION}）"
        return True, f"MCP SDK v{version}"
    except ImportError:
        return False, "MCP SDK 未安装 (pip install 'mcp>=1.26.0')"
    except Exception as exc:
        return False, f"MCP SDK 检查异常: {exc}"


def load_mcp_config(config_path: Path) -> dict[str, MCPServerConfig]:
    """从 mcp_servers.json 加载 MCP 服务器配置。

    Returns:
        dict: name → MCPServerConfig 映射
    """
    if not config_path.exists():
        logger.debug("MCP 配置文件不存在: %s", config_path)
        return {}

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("MCP 配置文件解析失败: %s", exc)
        return {}

    servers: dict[str, MCPServerConfig] = {}
    raw_servers = raw.get("servers", {})

    for name, cfg_data in raw_servers.items():
        try:
            cfg_data["name"] = name
            server = MCPServerConfig(**cfg_data)
            if server.enabled:
                servers[name] = server
            else:
                logger.debug("MCP 服务器 '%s' 已禁用，跳过", name)
        except Exception as exc:
            logger.warning("MCP 服务器 '%s' 配置无效: %s", name, exc)

    logger.info("已加载 %d 个 MCP 服务器配置", len(servers))
    return servers


def save_mcp_config(servers: dict[str, MCPServerConfig], config_path: Path) -> None:
    """保存 MCP 服务器配置到文件。"""
    data: dict[str, Any] = {"servers": {}}
    for name, cfg in servers.items():
        d = cfg.model_dump(exclude={"name"})
        data["servers"][name] = d

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
