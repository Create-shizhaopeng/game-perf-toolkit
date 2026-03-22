"""Perfetto 抓取模块 — 配置管理"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .models import CaptureConfig

logger = logging.getLogger(__name__)


def _get_module_dir() -> Path:
    """返回模块根目录（src/ 的父目录）。"""
    return Path(__file__).parent.parent


def get_default_config_path() -> Path:
    """默认配置模板路径。"""
    return _get_module_dir() / "assets" / "config.json"


def get_user_config_path() -> Path:
    """用户自定义配置路径。"""
    return _get_module_dir() / "data" / "config.json"


def load_config(config_path: Path | None = None) -> CaptureConfig:
    """加载配置：优先用户自定义 > 默认模板 > 内置默认值。"""
    if config_path and config_path.is_file():
        return _load_from_file(config_path)

    user_path = get_user_config_path()
    if user_path.is_file():
        return _load_from_file(user_path)

    default_path = get_default_config_path()
    if default_path.is_file():
        return _load_from_file(default_path)

    logger.info("未找到配置文件，使用内置默认配置")
    return CaptureConfig()


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
    """重置为默认配置（删除用户自定义文件）。"""
    user_path = get_user_config_path()
    if user_path.is_file():
        user_path.unlink()
        logger.info("已删除用户配置: %s", user_path)
    return load_config()
