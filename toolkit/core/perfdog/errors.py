"""PerfDog 解析与分析相关异常。"""

from __future__ import annotations


class PerfDogParseError(Exception):
    """文件损坏、非 xlsx、无法定位 Data_v4 等。"""


class PerfDogUnsupportedError(PerfDogParseError):
    """加密工作簿、需执行宏才能读取等不支持场景。"""
