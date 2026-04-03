# -*- coding: utf-8 -*-
"""一次性配置迁移 — 将 agent_chat 旧 LLM 配置迁移到框架全局配置。"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_AGENT_CHAT_CONFIG = Path("modules/agent_chat/data/config.json")
_LLM_FIELDS = {
    "provider", "api_key", "model_name", "temperature",
    "smart_switch", "claude_api_key", "glm_api_key",
}
_MIGRATED_KEY = "_llm_migrated_to_global"


def migrate_agent_chat_llm(config_manager: object) -> bool:
    """检测 agent_chat 旧配置，将 LLM 字段迁移到框架全局配置。

    迁移仅执行一次：成功后在旧配置中写入 `_llm_migrated_to_global` 标记。
    Returns True if migration was performed, False otherwise.
    """
    if not _AGENT_CHAT_CONFIG.exists():
        return False

    try:
        raw = json.loads(_AGENT_CHAT_CONFIG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("读取 agent_chat 配置失败: %s", exc)
        return False

    if raw.get(_MIGRATED_KEY):
        return False

    if not hasattr(config_manager, "get_llm_config"):
        return False

    global_llm = config_manager.get_llm_config()  # type: ignore[union-attr]
    if global_llm and global_llm.get("glm_api_key") or global_llm.get("claude_api_key"):
        logger.info("全局 LLM 配置已有 API Key，跳过迁移")
        raw[_MIGRATED_KEY] = True
        _AGENT_CHAT_CONFIG.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return False

    migrated: dict = {}
    for field in _LLM_FIELDS:
        if field in raw and raw[field]:
            migrated[field] = raw[field]

    old_api_key = raw.get("api_key", "")
    if old_api_key and not migrated.get("glm_api_key") and not migrated.get("claude_api_key"):
        provider = raw.get("provider", "glm")
        if provider == "glm":
            migrated["glm_api_key"] = old_api_key
        else:
            migrated["claude_api_key"] = old_api_key

    migrated.pop("api_key", None)

    if not migrated:
        return False

    config_manager.set_llm_config(migrated)  # type: ignore[union-attr]

    raw[_MIGRATED_KEY] = True
    _AGENT_CHAT_CONFIG.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info("已将 agent_chat LLM 配置迁移到全局配置: %s", list(migrated.keys()))
    return True
