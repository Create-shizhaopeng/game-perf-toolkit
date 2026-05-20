# -*- coding: utf-8 -*-
"""Perfetto 解析分析引擎 — 从 perfettoAnalysisByPython 迁移的核心逻辑。"""
from __future__ import annotations

import logging

__version__ = "0.2.0"

# 引擎统一日志（通过 logging 桥接到 loguru 统一日志系统）
logger = logging.getLogger("perfetto_analysis.engine")
