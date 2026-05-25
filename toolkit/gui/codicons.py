# -*- coding: utf-8 -*-
"""Codicons 字体集成 — 加载 VS Code 官方图标字体并提供 Unicode 映射。

字体来源: https://github.com/microsoft/vscode-codicons
许可: CC-BY-4.0
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QFont, QFontDatabase

_FONT_FAMILY: str | None = None

# 常用图标 Unicode 映射（从 codicon.css 提取）
ICONS = {
    # 窗口控制
    "chrome-close": "\ueab8",
    "chrome-maximize": "\ueab9",
    "chrome-minimize": "\ueaba",
    "chrome-restore": "\ueabb",
    # 功能图标
    "settings-gear": "\ueb51",
    "gear": "\ueaf8",
    "home": "\ueb06",
    "search": "\uea6d",
    "comment": "\uea6b",
    "comment-discussion": "\ueac7",
    "robot": "\uec20",
    "terminal": "\uea85",
    "device-mobile": "\ueadb",
    "graph": "\ueb03",
    "graph-line": "\uebe2",
    "play": "\ueb2c",
    "pulse": "\ueb31",
    "history": "\uea82",
    "file-code": "\ueae9",
    "tools": "\ueb6d",
    "dashboard": "\ueacd",
    "debug": "\uead8",
    # 导航 / 通用
    "folder": "\uea83",
    "record": "\uea8c",
    "eye": "\uea70",
    "shield": "\uea82",
    "beaker": "\uea79",
    "flame": "\ueb16",
    "rocket": "\ueb44",
    "close": "\uea76",
    "wand": "\uebcf",
    "git-compare": "\ueafd",
    "eye-closed": "\ueae7",
    "diff": "\ueae1",
    "arrow-swap": "\uebcb",
    # 布局面板
    "layout-sidebar-left": "\uebf3",
    "layout-sidebar-left-off": "\uec02",
    "layout-panel": "\uebf2",
    "layout-panel-off": "\uec01",
    "layout-sidebar-right": "\uebf4",
    "layout-sidebar-right-off": "\uec00",
    # 折叠/展开
    "chevron-down": "\ueab4",
    "chevron-right": "\ueab6",
    "chevron-up": "\ueab5",
    # 日志面板
    "clear-all": "\ueabf",
    "filter": "\uea91",
    "filter-filled": "\ueb6e",
    "output": "\ueb7d",
    # \u5386\u53f2\u9762\u677f / \u6587\u4ef6\u64cd\u4f5c
    "file": "\uea7b",
    "folder-opened": "\ueaf7",
    "trash": "\uea81",
    "refresh": "\ueb37",
    "check": "\ueab2",
    "error": "\uea87",
    "watch": "\ueb7c",
    "circle-slash": "\ueabd",
    "cloud-download": "\ueac2",
    "save": "\ueb4b",
    "database": "\ueace",
    "circle-outline": "\ueaad",
    "warning": "\uea6a",
    "info": "\uea74",
    "export": "\uebac",
    "link-external": "\ueb1e",
    "list-tree": "\ueb20",
    "report": "\ueb45",
    "send": "\ueb51",
    "close-all": "\ueab7",
    "add": "\uea60",
    "symbol-namespace": "\ueaea",
}


def load_codicons() -> str | None:
    """加载 codicon.ttf 字体。返回字体族名称，加载失败返回 None。"""
    global _FONT_FAMILY
    if _FONT_FAMILY is not None:
        return _FONT_FAMILY

    font_path = Path(__file__).parent.parent.parent / "assets" / "codicon.ttf"
    if not font_path.exists():
        return None

    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id < 0:
        return None

    families = QFontDatabase.applicationFontFamilies(font_id)
    if families:
        _FONT_FAMILY = families[0]
    return _FONT_FAMILY


def codicon_font(size: int = 14) -> QFont | None:
    """获取指定大小的 Codicons 字体实例。"""
    family = load_codicons()
    if not family:
        return None
    return QFont(family, size)


def icon_char(name: str) -> str:
    """获取图标字符，名称不存在时返回 '?'。"""
    return ICONS.get(name, "?")
