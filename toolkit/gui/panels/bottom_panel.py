"""底部日志面板 — VS Code 风格的统一日志输出区域。"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QTextCharFormat
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.codicons import codicon_font, icon_char
from toolkit.gui.log_manager import LogManager
from toolkit.gui.theme_colors import get_colors

_ALL_TAB = "全部"
_CONSOLE_TAB = "控制台"
_CONSOLE_SOURCE = "控制台"


class _FilterButton(QPushButton):
    """日志级别过滤切换按钮。"""

    def __init__(self, label: str, level: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.setObjectName("logFilterBtn")
        self.setCheckable(True)
        self.setChecked(True)
        self.level = level
        self.setFixedHeight(20)


class BottomPanel(QWidget):
    """底部日志面板 — 聚合所有模块日志。

    Header: [搜索] [计数] [频道Tabs] [控制台] --- [级别过滤] [清除]
    Content: QTextEdit + 结构化详情区域
    """

    def __init__(self, log_manager: LogManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("bottomPanel")
        self._log_manager = log_manager
        self._theme = "dark"
        self._current_source: str | None = None  # None = 全部
        self._search_text: str = ""
        self._show_console = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("bottomPanelHeader")
        header.setFixedHeight(28)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 0, 4, 0)
        h_layout.setSpacing(4)

        # 搜索框
        self._search_input = QLineEdit()
        self._search_input.setObjectName("logSearchInput")
        self._search_input.setPlaceholderText("搜索日志...")
        self._search_input.setFixedWidth(160)
        self._search_input.setFixedHeight(22)
        self._search_input.textChanged.connect(self._on_search_changed)
        h_layout.addWidget(self._search_input)

        # 匹配计数
        self._count_label = QLabel("0 / 0")
        self._count_label.setObjectName("logCountLabel")
        self._count_label.setFixedWidth(60)
        h_layout.addWidget(self._count_label)

        # 导出按钮
        export_btn = QPushButton("导出", self)
        export_btn.setObjectName("logExportBtn")
        export_btn.setFixedHeight(22)
        export_btn.clicked.connect(self._on_export)
        h_layout.addWidget(export_btn)
        self._export_btn = export_btn

        # 频道 Tabs
        self._tab_bar = QTabBar()
        self._tab_bar.setObjectName("logChannelBar")
        self._tab_bar.setDrawBase(False)
        self._tab_bar.setExpanding(False)
        self._tab_bar.addTab(_ALL_TAB)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        h_layout.addWidget(self._tab_bar)

        # 控制台源切换
        self._console_btn = QPushButton("控制台", self)
        self._console_btn.setObjectName("logConsoleBtn")
        self._console_btn.setFixedHeight(22)
        self._console_btn.setCheckable(True)
        self._console_btn.setChecked(False)
        self._console_btn.toggled.connect(self._on_console_toggled)
        h_layout.addWidget(self._console_btn)

        h_layout.addStretch()

        self._filters: dict[str, _FilterButton] = {}
        for label, level in [("Error", "error"), ("Warning", "warning"), ("Info", "info")]:
            btn = _FilterButton(label, level, self)
            btn.toggled.connect(self._on_filter_changed)
            self._filters[level] = btn
            h_layout.addWidget(btn)

        clear_icon = icon_char("clear-all")
        clear_btn = QPushButton(clear_icon, self)
        clear_btn.setObjectName("logClearBtn")
        clear_btn.setFixedSize(24, 20)
        clear_btn.setToolTip("清除日志")
        font = codicon_font(12)
        if font:
            clear_btn.setFont(font)
        clear_btn.clicked.connect(self._on_clear)
        self._clear_btn = clear_btn
        h_layout.addWidget(clear_btn)

        root.addWidget(header)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setObjectName("bottomPanelLog")
        root.addWidget(self._log_view)

        log_manager.log_added.connect(self._on_log_added)
        log_manager.source_registered.connect(self._on_source_registered)

    # --- public ---

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self._refresh_view()

    # --- 搜索 / 过滤 / 导出 ---

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.strip().lower()
        self._refresh_view()

    def _on_console_toggled(self, checked: bool) -> None:
        self._show_console = checked
        self._refresh_view()

    def _on_export(self) -> None:
        entries = self._filtered_entries()
        if not entries:
            return
        fname, _ = QFileDialog.getSaveFileName(
            self, "导出日志", "logs_export.log", "日志文件 (*.log);;所有文件 (*.*)"
        )
        if not fname:
            return
        with open(fname, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(f"[{e.timestamp}] [{e.source}] {e.message}\n")
                if e.details:
                    for k, v in e.details.items():
                        f.write(f"  [{k}] {v}\n")

    # --- 频道切换 ---

    def _on_source_registered(self, source: str) -> None:
        if source == _CONSOLE_SOURCE:
            return
        self._tab_bar.addTab(source)

    def _on_tab_changed(self, index: int) -> None:
        if index == 0:
            self._current_source = None
        else:
            self._current_source = self._tab_bar.tabText(index)
        self._refresh_view()

    # --- 过滤 ---

    def _on_filter_changed(self) -> None:
        self._refresh_view()

    def _on_clear(self) -> None:
        self._log_manager.clear(self._current_source)
        self._refresh_view()

    def _active_levels(self) -> set[str]:
        levels = set()
        for level, btn in self._filters.items():
            if btn.isChecked():
                levels.add(level)
        levels.add("success")
        return levels

    # --- 日志接入 ---

    def _on_log_added(self, ts: str, source: str, msg: str, level: str) -> None:
        if not self._passes_filter(source, msg, level):
            return
        self._append_line(ts, source, msg, level)
        self._update_count()

    def _passes_filter(self, source: str, msg: str, level: str) -> bool:
        if level not in self._active_levels():
            return False
        if self._show_console:
            if source != _CONSOLE_SOURCE:
                return False
        elif self._current_source is not None:
            if source != self._current_source:
                return False
        if self._search_text:
            if self._search_text not in source.lower() and self._search_text not in msg.lower():
                return False
        return True

    # --- 渲染 ---

    def _append_line(self, ts: str, source: str, msg: str, level: str) -> None:
        c = get_colors(self._theme)
        color_map = {
            "error": c["error"],
            "warning": c["warning"],
            "success": c["success"],
            "info": c["fg"],
        }
        fg = color_map.get(level, c["fg"])

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(fg))

        src_fmt = QTextCharFormat()
        src_fmt.setForeground(QColor(c["fg_muted"]))

        cursor = self._log_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        if self._current_source is None and not self._show_console:
            cursor.insertText(f"[{ts}] ", src_fmt)
            cursor.insertText(f"[{source}] ", src_fmt)
            cursor.insertText(f"{msg}\n", fmt)
        else:
            cursor.insertText(f"[{ts}] ", src_fmt)
            cursor.insertText(f"{msg}\n", fmt)

        self._log_view.setTextCursor(cursor)
        self._log_view.ensureCursorVisible()

    def _refresh_view(self) -> None:
        """重绘全部内容（频道/过滤切换时）。"""
        self._log_view.clear()
        entries = self._filtered_entries()
        for e in entries:
            self._append_line(e.timestamp, e.source, e.message, e.level)
        self._update_count()

    def _filtered_entries(self):
        levels = self._active_levels()
        all_entries = self._log_manager.get_entries(
            source=self._current_source,
            levels=levels,
        )
        result = []
        for e in all_entries:
            if not self._passes_filter(e.source, e.message, e.level):
                continue
            result.append(e)
        return result

    def _update_count(self) -> None:
        total = len(self._log_manager.get_entries())
        visible = len(self._filtered_entries())
        self._count_label.setText(f"{visible} / {total}")
