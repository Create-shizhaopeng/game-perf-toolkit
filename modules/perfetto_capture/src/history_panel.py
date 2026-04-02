"""Perfetto 抓取模块 — 历史记录面板

覆盖式右侧滑出面板，用于浏览和管理历史抓取记录。
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .models import HistorySession, HistoryStats

logger = logging.getLogger(__name__)

PANEL_WIDTH = 320
ANIMATION_DURATION_MS = 250

# Catppuccin 主题色
_THEME_COLORS = {
    "dark": {
        "bg": "#1e1e2e",
        "panel_bg": "#313244",
        "border": "#45475a",
        "fg": "#cdd6f4",
        "fg_dim": "#a6adc8",
        "accent": "#cba6f7",
        "success": "#a6e3a1",
        "error": "#f38ba8",
        "hover": "#45475a",
    },
    "light": {
        "bg": "#eff1f5",
        "panel_bg": "#e6e9ef",
        "border": "#ccd0da",
        "fg": "#333333",
        "fg_dim": "#616161",
        "accent": "#8839ef",
        "success": "#40a02b",
        "error": "#d20f39",
        "hover": "#dce0e8",
    },
}


class OverlayMask(QWidget):
    """半透明遮罩层，点击关闭面板。"""

    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: rgba(0, 0, 0, 0.3)")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide()

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)

    def show_mask(self) -> None:
        """显示遮罩，覆盖父组件。"""
        if self.parent():
            parent = self.parent()
            self.setGeometry(0, 0, parent.width(), parent.height())
        self.show()
        self.raise_()

    def hide_mask(self) -> None:
        """隐藏遮罩。"""
        self.hide()


class SessionTreeWidget(QTreeWidget):
    """历史会话树形列表。"""

    open_directory_requested = pyqtSignal(Path)
    analyze_trace_requested = pyqtSignal(Path)
    delete_session_requested = pyqtSignal(str)
    delete_trace_requested = pyqtSignal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(16)
        self.setAnimated(True)
        self.setExpandsOnDoubleClick(True)
        self.setStyleSheet("""
            QTreeWidget {
                background: transparent;
                border: none;
                outline: none;
                color: #cdd6f4;
            }
            QTreeWidget::item {
                padding: 4px 2px;
                border-radius: 4px;
                color: #cdd6f4;
            }
            QTreeWidget::item:hover {
                background: rgba(255, 255, 255, 0.08);
            }
            QTreeWidget::item:selected {
                background: rgba(203, 166, 247, 0.2);
                color: #cdd6f4;
            }
        """)

    def refresh(self, sessions: list[HistorySession]) -> None:
        """刷新会话列表。"""
        self.clear()

        for session in sessions:
            session_item = self._create_session_item(session)
            self.addTopLevelItem(session_item)

            for trace in session.traces:
                trace_item = self._create_trace_item(trace, session.id)
                session_item.addChild(trace_item)

    def _create_session_item(self, session: HistorySession) -> QTreeWidgetItem:
        """创建会话节点。"""
        # 格式化显示
        time_str = session.created_at.strftime("%Y-%m-%d %H:%M")
        device_str = f"{session.device_model or '?'} · {session.device_soc or '?'}"
        size_str = self._format_size(session.total_size_bytes)

        item = QTreeWidgetItem()
        item.setText(0, f"📁 {time_str} | {device_str} | {session.trace_count} 个 | {size_str}")
        item.setData(0, Qt.ItemDataRole.UserRole, {"type": "session", "id": session.id, "path": session.dir_path})
        return item

    def _create_trace_item(self, trace, session_id: str) -> QTreeWidgetItem:
        """创建 trace 节点。"""
        size_str = self._format_size(trace.file_size_bytes)

        item = QTreeWidgetItem()
        item.setText(0, f"📄 {trace.file_name} ({size_str})")
        item.setData(0, Qt.ItemDataRole.UserRole, {"type": "trace", "session_id": session_id, "path": trace.file_path})
        return item

    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小。"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def filter_by_keyword(self, keyword: str) -> None:
        """根据关键词过滤显示。"""
        keyword_lower = keyword.lower().strip()

        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item:
                text = item.text(0).lower()
                visible = not keyword_lower or keyword_lower in text
                item.setHidden(not visible)


class HistoryPanel(QWidget):
    """历史记录面板（覆盖式右侧滑出）。"""

    close_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    cleanup_requested = pyqtSignal()
    open_directory_requested = pyqtSignal(Path)
    analyze_trace_requested = pyqtSignal(Path)
    delete_session_requested = pyqtSignal(str)
    delete_trace_requested = pyqtSignal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(PANEL_WIDTH)
        self.setAutoFillBackground(True)
        self._setup_ui()
        self._setup_animation()
        self._setup_search_debounce()
        self.hide()

    def paintEvent(self, event) -> None:
        from PyQt6.QtWidgets import QStyleOption, QStyle
        from PyQt6.QtGui import QPainter
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        p.end()

    def _setup_ui(self) -> None:
        """构建 UI。"""
        colors = _THEME_COLORS["dark"]

        self.setStyleSheet(f"""
            HistoryPanel {{
                background: {colors['panel_bg']};
                border-left: 1px solid {colors['border']};
            }}
            QLabel {{
                color: {colors['fg']};
            }}
            QLineEdit {{
                background: {colors['bg']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                padding: 6px 8px;
                color: {colors['fg']};
            }}
            QLineEdit:focus {{
                border-color: {colors['accent']};
            }}
            QPushButton {{
                background: {colors['border']};
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                color: {colors['fg']};
            }}
            QPushButton:hover {{
                background: {colors['hover']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("📂 历史记录")
        title.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {colors['fg']};")
        header.addWidget(title)
        header.addStretch()

        self._btn_refresh = QPushButton("🔄")
        self._btn_refresh.setFixedSize(28, 28)
        self._btn_refresh.setToolTip("刷新")
        self._btn_refresh.clicked.connect(self.refresh_requested.emit)
        header.addWidget(self._btn_refresh)

        self._btn_close = QPushButton("✕")
        self._btn_close.setFixedSize(28, 28)
        self._btn_close.setToolTip("关闭")
        self._btn_close.clicked.connect(self.close_requested.emit)
        header.addWidget(self._btn_close)

        layout.addLayout(header)

        # 搜索框
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 搜索设备、日期...")
        self._search_input.textChanged.connect(self._on_search_text_changed)
        layout.addWidget(self._search_input)

        # 会话列表
        self._session_tree = SessionTreeWidget()
        self._session_tree.itemClicked.connect(self._on_item_clicked)
        self._session_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._session_tree, 1)

        # 操作按钮行
        action_layout = QHBoxLayout()

        self._btn_open_dir = QPushButton("📂 目录")
        self._btn_open_dir.setToolTip("打开所在目录")
        self._btn_open_dir.clicked.connect(self._on_open_directory)
        action_layout.addWidget(self._btn_open_dir)

        self._btn_analyze = QPushButton("📊 分析")
        self._btn_analyze.setToolTip("使用 perfetto_analysis 分析")
        self._btn_analyze.clicked.connect(self._on_analyze)
        action_layout.addWidget(self._btn_analyze)

        self._btn_delete = QPushButton("🗑")
        self._btn_delete.setFixedWidth(36)
        self._btn_delete.setToolTip("删除")
        self._btn_delete.clicked.connect(self._on_delete)
        action_layout.addWidget(self._btn_delete)

        layout.addLayout(action_layout)

        # 底部统计
        self._stats_label = QLabel("💾 0 MB / 0 会话")
        self._stats_label.setStyleSheet(f"color: {colors['fg_dim']}; font-size: 12px;")
        layout.addWidget(self._stats_label)

        # 清理按钮
        self._btn_cleanup = QPushButton("🗑 清理过期")
        self._btn_cleanup.clicked.connect(self.cleanup_requested.emit)
        layout.addWidget(self._btn_cleanup)

        # 初始禁用操作按钮
        self._update_action_buttons_state(None)

    def _setup_animation(self) -> None:
        """设置滑出动画。"""
        self._animation = QPropertyAnimation(self, b"pos")
        self._animation.setDuration(ANIMATION_DURATION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.finished.connect(self._on_animation_finished)
        self._is_hiding = False

    def _setup_search_debounce(self) -> None:
        """设置搜索防抖。"""
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)

    def show_animated(self) -> None:
        """从右侧滑入显示。"""
        if not self.parent():
            return

        parent = self.parent()
        parent_width = parent.width()
        parent_height = parent.height()

        self.setFixedHeight(parent_height)

        start_x = parent_width
        end_x = parent_width - PANEL_WIDTH

        self._animation.setStartValue(QPoint(start_x, 0))
        self._animation.setEndValue(QPoint(end_x, 0))

        self._is_hiding = False
        self.show()
        self.raise_()
        self._animation.start()

    def hide_animated(self) -> None:
        """向右侧滑出隐藏。"""
        if not self.parent():
            self.hide()
            return

        parent = self.parent()
        parent_width = parent.width()

        current_x = self.x()
        end_x = parent_width

        self._animation.setStartValue(QPoint(current_x, 0))
        self._animation.setEndValue(QPoint(end_x, 0))

        self._is_hiding = True
        self._animation.start()

    def _on_animation_finished(self) -> None:
        """动画完成回调。"""
        if self._is_hiding:
            self.hide()

    def refresh(self, sessions: list[HistorySession]) -> None:
        """刷新会话列表。"""
        self._session_tree.refresh(sessions)

    def update_stats(self, stats: HistoryStats) -> None:
        """更新统计信息。"""
        size_str = self._format_size(stats.total_size_bytes)
        self._stats_label.setText(f"💾 {size_str} / {stats.total_sessions} 会话 / {stats.total_traces} 个 trace")

    def set_analysis_available(self, available: bool) -> None:
        """设置分析功能是否可用。"""
        self._btn_analyze.setEnabled(available)
        if not available:
            self._btn_analyze.setToolTip("perfetto_analysis 模块未加载")

    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小。"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def _on_search_text_changed(self, text: str) -> None:
        """搜索框文本变化（防抖）。"""
        self._search_timer.stop()
        self._search_timer.start(300)

    def _do_search(self) -> None:
        """执行搜索过滤。"""
        keyword = self._search_input.text()
        self._session_tree.filter_by_keyword(keyword)

    def _get_selected_item_data(self) -> dict | None:
        """获取当前选中项的数据。"""
        items = self._session_tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.ItemDataRole.UserRole)

    def _update_action_buttons_state(self, item_data: dict | None) -> None:
        """更新操作按钮状态。"""
        has_selection = item_data is not None
        is_trace = bool(item_data and item_data.get("type") == "trace")

        self._btn_open_dir.setEnabled(has_selection)
        self._btn_analyze.setEnabled(is_trace and self._btn_analyze.isEnabled())
        self._btn_delete.setEnabled(has_selection)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """项目点击事件。"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        self._update_action_buttons_state(data)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """项目双击事件（展开/折叠）。"""
        if item.childCount() > 0:
            item.setExpanded(not item.isExpanded())

    def _on_open_directory(self) -> None:
        """打开目录按钮点击。"""
        data = self._get_selected_item_data()
        if not data:
            return

        path = data.get("path")
        if path:
            self.open_directory_requested.emit(Path(path))

    def _on_analyze(self) -> None:
        """分析按钮点击。"""
        data = self._get_selected_item_data()
        if not data or data.get("type") != "trace":
            return

        path = data.get("path")
        if path:
            self.analyze_trace_requested.emit(Path(path))

    def _on_delete(self) -> None:
        """删除按钮点击。"""
        data = self._get_selected_item_data()
        if not data:
            return

        item_type = data.get("type")
        if item_type == "session":
            session_id = data.get("id")
            if session_id:
                self.delete_session_requested.emit(session_id)
        elif item_type == "trace":
            path = data.get("path")
            if path:
                self.delete_trace_requested.emit(Path(path))
