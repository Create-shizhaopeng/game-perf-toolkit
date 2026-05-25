# -*- coding: utf-8 -*-
"""通用历史树基类 — 各模块创建历史记录树时继承复用。

提供统一的右键菜单框架、主题样式、send_to_agent 信号、
搜索过滤、多选数据获取、格式化工具等通用能力。
图标统一使用 codicon.ttf 字体系统，禁止 Unicode Emoji。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QTreeWidget, QTreeWidgetItem, QWidget

from toolkit.gui.codicons import codicon_font, icon_char, load_codicons
from toolkit.gui.theme_colors import get_colors


def _make_codicon_pixmap(name: str, color: str = "#cdd6f4", font_size: int = 14, canvas: int = 20) -> QPixmap:
    """将 codicon 字符渲染为 QPixmap（对齐 NavPanel 的 QPainter 方式）。"""
    try:
        font = codicon_font(font_size)
        if not font:
            return QPixmap()
        pixmap = QPixmap(canvas, canvas)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(0, 0, canvas, canvas,
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter,
                         icon_char(name))
        painter.end()
        return pixmap
    except Exception:
        return QPixmap()


def make_codicon_icon(name: str, color: str = "#cdd6f4", font_size: int = 14, canvas: int = 20) -> QIcon:
    """从 codicon 名称创建 QIcon。"""
    return QIcon(_make_codicon_pixmap(name, color, font_size, canvas))


_icon_cache: dict[str, QIcon] = {}


def _cached_icon(name: str, color: str = "#cdd6f4", font_size: int = 14, canvas: int = 20) -> QIcon:
    key = (name, color, font_size, canvas)
    icon = _icon_cache.get(key)
    if icon is None:
        icon = make_codicon_icon(name, color, font_size, canvas)
        _icon_cache[key] = icon
    return icon


class BaseHistoryTreeWidget(QTreeWidget):
    """通用历史树基类。

    子类继承后可获得：
    - 统一的右键菜单框架（_setup_context_menu）
    - send_to_agent_requested 信号
    - 搜索过滤（filter_by_keyword）
    - 多选数据获取（_get_selected_items_data）
    - 格式化工具（_format_size, _format_time）
    - 主题切换（set_theme）
    - codicon 图标支持（_get_codicon, _set_item_icon）
    """

    send_to_agent_requested = pyqtSignal(dict)

    # 子类可覆盖的图标颜色（canvas 16px 白色为佳，稍后在 set_theme 中刷新）
    _ICON_COLOR = "#cdd6f4"
    _icon_cache: dict[str, QIcon] = {}

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = "dark"
        self.setHeaderHidden(True)
        self.setIndentation(16)
        self.setAnimated(True)
        self.setExpandsOnDoubleClick(True)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self._apply_theme()

    # ------------------------------------------------------------------
    # Codicon 图标
    # ------------------------------------------------------------------

    def _get_codicon(self, name: str) -> QIcon:
        """返回当前主题色的 codicon 图标（14px 字体 / 20px 画布，对齐 NavPanel）。"""
        key = (name, self._ICON_COLOR)
        icon = self._icon_cache.get(key)
        if icon is None:
            try:
                icon = make_codicon_icon(name, self._ICON_COLOR, font_size=14, canvas=20)
            except Exception:
                return QIcon()
            self._icon_cache[key] = icon
        return icon

    def _set_item_icon(self, item: QTreeWidgetItem, name: str, column: int = 0) -> None:
        """为树节点设置 codicon 图标。"""
        try:
            item.setIcon(column, self._get_codicon(name))
        except Exception:
            pass  # 图标渲染失败不阻塞 UI

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------

    def set_theme(self, theme: str) -> None:
        """设置主题并刷新样式。"""
        self._theme = theme
        c = get_colors(theme)
        self._ICON_COLOR = c["fg"]
        self._icon_cache.clear()
        self._apply_theme()

    def _apply_theme(self) -> None:
        """主题样式由全局 QSS（styles.py）管理，此处仅确保透明背景。"""
        self.setStyleSheet("QTreeWidget { background: transparent; border: none; }")

    # ------------------------------------------------------------------
    # 右键菜单框架
    # ------------------------------------------------------------------

    def _build_context_menu(self, menu: QMenu, items: list[QTreeWidgetItem]) -> None:
        """构建右键菜单 — 子类重写以添加菜单项。

        默认实现提供"打开所在目录"和"发送到 Agent 对话"两个通用菜单项。
        子类应调用 super()._build_context_menu(menu, items) 保留通用项，
        或在完全不同的场景中完全重写。
        """
        c = get_colors(self._theme)

    def _make_context_menu(self) -> QMenu:
        """创建带主题样式的 QMenu。"""
        c = get_colors(self._theme)
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {c["card_bg"]};
                color: {c["fg"]};
                border: 1px solid {c["border"]};
                border-radius: 4px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 4px 16px;
                border-radius: 3px;
            }}
            QMenu::item:selected {{
                background: {c["accent"]}4D;
            }}
            QMenu::separator {{
                height: 1px;
                background: {c["border"]};
                margin: 4px 8px;
            }}
        """)
        return menu

    def _add_menu_action(
        self,
        menu: QMenu,
        text: str,
        callback: Callable[[], None],
        icon_name: str = "",
    ) -> QAction:
        """添加菜单项，可选 codicon 图标。"""
        action = QAction(text, self)
        if icon_name:
            color = get_colors(self._theme)["fg"]
            action.setIcon(_cached_icon(icon_name, color))
        action.triggered.connect(callback)
        menu.addAction(action)
        return action

    def _on_context_menu(self, position) -> None:
        """右键菜单入口 — 子类可重写。"""
        items = self.selectedItems()
        if not items:
            return
        menu = self._make_context_menu()
        self._build_context_menu(menu, items)
        menu.exec(self.viewport().mapToGlobal(position))

    # ------------------------------------------------------------------
    # 通用操作
    # ------------------------------------------------------------------

    @staticmethod
    def _build_send_payload(path: str, context_type: str = "trace") -> dict:
        """构建发送到 Agent 的标准 payload。"""
        p = Path(path)
        return {
            "file_path": path,
            "file_name": p.name,
            "context_type": context_type,
            "missing": not p.exists(),
        }

    def _open_directory(self, path: str | Path) -> None:
        """在文件管理器中打开目标目录。"""
        dir_path = Path(path)
        if dir_path.is_file():
            dir_path = dir_path.parent
        if not dir_path.exists():
            return
        if sys.platform == "win32":
            subprocess.run(["explorer", str(dir_path)], check=False)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(dir_path)], check=False)
        else:
            subprocess.run(["xdg-open", str(dir_path)], check=False)

    def _open_file(self, path: str | Path) -> None:
        """用默认程序打开文件（通过 Qt，避免 webbrowser.open 的 COM 冲突）。"""
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        file_path = Path(path)
        if file_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path.resolve())))

    # ------------------------------------------------------------------
    # 数据获取
    # ------------------------------------------------------------------

    def _get_selected_items_data(self) -> list[dict]:
        """获取所有选中项的 UserRole 数据。"""
        result = []
        for item in self.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                result.append(data)
        return result

    def _get_first_selected_data(self) -> dict | None:
        """获取第一个选中项的 UserRole 数据。"""
        data_list = self._get_selected_items_data()
        return data_list[0] if data_list else None

    # ------------------------------------------------------------------
    # 搜索过滤
    # ------------------------------------------------------------------

    def filter_by_keyword(self, keyword: str, column: int = 0) -> None:
        """根据关键词过滤顶层项显示（大小写不敏感）。

        Args:
            keyword: 搜索关键词，空字符串显示全部
            column: 要搜索的列索引
        """
        kw = keyword.lower().strip()
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item:
                text = item.text(column).lower()
                item.setHidden(bool(kw and kw not in text))

    # ------------------------------------------------------------------
    # 格式化工具
    # ------------------------------------------------------------------

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """格式化文件大小为人类可读形式。"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    @staticmethod
    def _format_time(dt) -> str:
        """格式化时间为显示字符串。接受 datetime 或 ISO 字符串。"""
        from datetime import datetime as _dt

        if isinstance(dt, _dt):
            return dt.strftime("%Y-%m-%d %H:%M")
        if isinstance(dt, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
                try:
                    return _dt.strptime(dt[:19], fmt).strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    continue
            return dt[:16] if len(dt) >= 16 else dt
        if isinstance(dt, (int, float)):
            # epoch seconds or milliseconds or nanoseconds
            ts = dt
            if ts > 1e15:  # nanoseconds
                ts = ts / 1e9
            elif ts > 1e12:  # microseconds
                ts = ts / 1e6
            return _dt.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        return str(dt)[:16]
