"""Perfetto 抓取模块 — 配置管理

归一化为单配置文件：仅从 ``config/config.json`` 加载，不存在时从代码默认值自动生成。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from toolkit.core.app_paths import get_config_path

from .models import CaptureConfig

logger = logging.getLogger(__name__)

MODULE_NAME = "perfetto_capture"


def get_user_config_path() -> Path:
    """用户配置路径（唯一配置源）。"""
    return get_config_path(MODULE_NAME, "config.json")


def load_config(config_path: Path | None = None) -> CaptureConfig:
    """加载配置：优先指定路径 > 用户配置 > 代码默认值（首次运行自动生成）。"""
    if config_path and config_path.is_file():
        return _load_from_file(config_path)

    user_path = get_user_config_path()
    if user_path.is_file():
        return _load_from_file(user_path)

    logger.info("未找到配置文件，从代码默认值生成: %s", user_path)
    cfg = CaptureConfig()
    save_config(cfg, user_path)
    return cfg


def _load_from_file(path: Path) -> CaptureConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cfg = CaptureConfig.model_validate(raw)
    cfg.validate_semantics()
    logger.info("已加载配置: %s", path)
    return cfg


def save_config(cfg: CaptureConfig, path: Path | None = None) -> Path:
    """保存配置到用户路径。"""
    target = path or get_user_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        cfg.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    logger.info("配置已保存: %s", target)
    return target


def reset_config() -> CaptureConfig:
    """重置为代码默认配置（删除用户自定义文件并重新生成）。"""
    user_path = get_user_config_path()
    if user_path.is_file():
        user_path.unlink()
        logger.info("已删除用户配置: %s", user_path)
    cfg = CaptureConfig()
    save_config(cfg, user_path)
    return cfg
