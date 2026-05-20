"""日志服务 — 向后兼容接口（已迁移到 unified_logger.py）"""

from __future__ import annotations

import logging
from pathlib import Path

from toolkit.core.unified_logger import (
    UnifiedLogger,
    resolve_log_level,
    setup_logging,
)

__all__ = ["setup_logging", "resolve_log_level", "UnifiedLogger"]
