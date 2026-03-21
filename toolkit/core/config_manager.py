"""全局配置管理 — JSON 配置的读写与管理"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG: dict[str, Any] = {
    "theme": "dark",
    "adb_path": "",
    "language": "zh-CN",
    "log_level": "INFO",
    "window": {"width": 1200, "height": 800},
}


class ConfigManager:
    """分层配置管理器。

    全局配置存储在 data/config.json。
    """

    def __init__(self, config_path: Path | None = None) -> None:
        if config_path is None:
            config_path = Path("data/config.json")
        self._path = config_path
        self._config: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._config = json.loads(self._path.read_text("utf-8"))
                logger.info("配置已加载: %s", self._path)
            except (json.JSONDecodeError, OSError):
                logger.warning("配置文件读取失败，使用默认配置")
                self._config = dict(_DEFAULT_CONFIG)
        else:
            self._config = dict(_DEFAULT_CONFIG)
            self._save()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的嵌套键。"""
        parts = key.split(".")
        value: Any = self._config
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """设置配置值并持久化。"""
        parts = key.split(".")
        target = self._config
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value
        self._save()

    def get_theme(self) -> str:
        return self.get("theme", "dark")

    def set_theme(self, theme: str) -> None:
        self.set("theme", theme)

    def get_adb_path(self) -> str:
        return self.get("adb_path", "")

    def set_adb_path(self, path: str) -> None:
        self.set("adb_path", path)

    def to_dict(self) -> dict:
        return dict(self._config)
