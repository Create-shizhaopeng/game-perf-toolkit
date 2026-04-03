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
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .models import HistorySession, HistoryStats

logger = logging.getLogger(__name__)

PANEL_MIN_WIDTH = 600
LEFT_COL_MIN_WIDTH = 280
RIGHT_COL_MIN_WIDTH = 320
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
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
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

    def _show_context_menu(self, position) -> None:
        """右键菜单。"""
        items = self.selectedItems()
        if not items:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 4px; padding: 4px;
            }
            QMenu::item { padding: 4px 16px; border-radius: 3px; }
            QMenu::item:selected { background: rgba(203, 166, 247, 0.3); }
        """)

        act_open = QAction("📂 打开所在目录", self)
        act_open.triggered.connect(self._ctx_open_directory)
        menu.addAction(act_open)

        menu.addSeparator()

        count = len(items)
        delete_text = f"🗑 删除 {count} 项" if count > 1 else "🗑 删除"
        act_delete = QAction(delete_text, self)
        act_delete.triggered.connect(self._ctx_delete)
        menu.addAction(act_delete)

        menu.exec(self.viewport().mapToGlobal(position))

    def _ctx_open_directory(self) -> None:
        items = self.selectedItems()
        if not items:
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if data and data.get("path"):
            self.open_directory_requested.emit(Path(data["path"]))

    def _ctx_delete(self) -> None:
        """右键删除选中项。"""
        items = self.selectedItems()
        if not items:
            return

        selected_data = []
        for item in items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                selected_data.append(data)

        sessions = [d for d in selected_data if d.get("type") == "session"]
        traces = [d for d in selected_data if d.get("type") == "trace"]

        parts: list[str] = []
        if sessions:
            parts.append(f"{len(sessions)} 个会话")
        if traces:
            parts.append(f"{len(traces)} 个 trace")
        summary = "、".join(parts)

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除 {summary} 吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for s in sessions:
            sid = s.get("id")
            if sid:
                self.delete_session_requested.emit(sid)
        for t in traces:
            path = t.get("path")
            if path:
                self.delete_trace_requested.emit(Path(path))


class AnalysisHistoryTree(QTreeWidget):
    """分析历史记录树形列表。"""

    open_report_requested = pyqtSignal(str)
    delete_analysis_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(16)
        self.setAnimated(True)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setStyleSheet("""
            QTreeWidget {
                background: transparent;
                border: none;
                outline: none;
                color: #cdd6f4;
            }
            QTreeWidget::item {
                padding: 3px 2px;
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
        self.itemDoubleClicked.connect(self._on_double_click)

        header_item = QTreeWidgetItem()
        header_item.setText(0, "📊 分析历史")
        self.setHeaderItem(header_item)
        self.setHeaderHidden(False)
        self.header().setStyleSheet(
            "QHeaderView::section { background: transparent; color: #a6adc8; "
            "border: none; padding: 4px; font-size: 12px; }"
        )

    def refresh(self, tasks: list[dict]) -> None:
        """刷新分析任务列表。"""
        self.clear()
        status_icons = {
            "COMPLETED": "✅",
            "FAILED": "❌",
            "PENDING": "⏳",
            "ROUTING": "🔀",
            "ANALYZING": "🔬",
            "REVIEWING": "📋",
            "TIMEOUT": "⏰",
            "CANCELLED": "🚫",
        }
        for task in tasks:
            item = QTreeWidgetItem()
            status = task.get("status", "PENDING")
            icon = status_icons.get(status, "⏳")
            trace_name = Path(task.get("trace_path", "")).name
            created = task.get("created_at", "")[:16]
            item.setText(0, f"{icon} {trace_name} — {created}")
            item.setData(0, Qt.ItemDataRole.UserRole, task)
            self.addTopLevelItem(item)

    def _on_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        result_dir = data.get("result_dir", "")
        if result_dir:
            report_path = str(Path(result_dir) / "report.html")
            self.open_report_requested.emit(report_path)


class HistoryPanel(QWidget):
    """历史记录面板（覆盖式右侧滑出）。"""

    close_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    cleanup_requested = pyqtSignal()
    open_directory_requested = pyqtSignal(Path)
    analyze_trace_requested = pyqtSignal(Path)
    delete_session_requested = pyqtSignal(str)
    delete_trace_requested = pyqtSignal(Path)
    file_dropped = pyqtSignal(Path)
    import_package_db = pyqtSignal()
    export_package_db = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(PANEL_MIN_WIDTH)
        self._panel_width = PANEL_MIN_WIDTH
        self.setAutoFillBackground(True)
        self._chat_widget: QWidget | None = None
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
        """构建左右双栏 UI。"""
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
            QSplitter::handle {{
                background: {colors['border']};
                width: 2px;
            }}
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 顶部标题栏（跨双栏）
        header_bar = QHBoxLayout()
        header_bar.setContentsMargins(12, 8, 12, 8)
        title = QLabel("📂 历史记录 & 分析")
        title.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {colors['fg']};")
        header_bar.addWidget(title)
        header_bar.addStretch()

        self._btn_refresh = QPushButton("🔄")
        self._btn_refresh.setFixedSize(28, 28)
        self._btn_refresh.setToolTip("刷新")
        self._btn_refresh.clicked.connect(self.refresh_requested.emit)
        header_bar.addWidget(self._btn_refresh)

        self._btn_close = QPushButton("✕")
        self._btn_close.setFixedSize(28, 28)
        self._btn_close.setToolTip("关闭")
        self._btn_close.clicked.connect(self.close_requested.emit)
        header_bar.addWidget(self._btn_close)

        root_layout.addLayout(header_bar)

        # ── 左右双栏 QSplitter ──────────────────────
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setChildrenCollapsible(False)

        # ── 左栏：trace 列表 + 操作 ──────────────────
        left_col = QWidget()
        left_col.setMinimumWidth(LEFT_COL_MIN_WIDTH)
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(12, 4, 4, 12)
        left_layout.setSpacing(8)

        from .drag_drop_area import DragDropArea

        self._drag_drop = DragDropArea()
        self._drag_drop.file_dropped.connect(self.file_dropped.emit)
        left_layout.addWidget(self._drag_drop)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 搜索设备、日期...")
        self._search_input.textChanged.connect(self._on_search_text_changed)
        left_layout.addWidget(self._search_input)

        self._session_tree = SessionTreeWidget()
        self._session_tree.itemClicked.connect(self._on_item_clicked)
        self._session_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._session_tree.itemSelectionChanged.connect(self._update_action_buttons_state)
        self._session_tree.open_directory_requested.connect(self.open_directory_requested.emit)
        self._session_tree.delete_session_requested.connect(self.delete_session_requested.emit)
        self._session_tree.delete_trace_requested.connect(self.delete_trace_requested.emit)
        left_layout.addWidget(self._session_tree, 1)

        # 操作按钮已集成到右键菜单，此处仅保留统计和清理

        self._stats_label = QLabel("💾 0 MB / 0 会话")
        self._stats_label.setStyleSheet(f"color: {colors['fg_dim']}; font-size: 12px;")
        left_layout.addWidget(self._stats_label)

        bottom_actions = QHBoxLayout()
        self._btn_cleanup = QPushButton("🗑 清理")
        self._btn_cleanup.clicked.connect(self.cleanup_requested.emit)
        bottom_actions.addWidget(self._btn_cleanup)

        self._btn_import_pkg = QPushButton("📥 导入包名")
        self._btn_import_pkg.setToolTip("导入包名配置 (JSON)")
        self._btn_import_pkg.clicked.connect(self._on_import_package_db)
        bottom_actions.addWidget(self._btn_import_pkg)

        self._btn_export_pkg = QPushButton("📤 导出包名")
        self._btn_export_pkg.setToolTip("导出包名配置 (JSON)")
        self._btn_export_pkg.clicked.connect(self._on_export_package_db)
        bottom_actions.addWidget(self._btn_export_pkg)

        left_layout.addLayout(bottom_actions)

        # ── 左栏上下 QSplitter（上: trace 列表, 下: 分析历史） ──
        self._left_splitter = QSplitter(Qt.Orientation.Vertical)
        self._left_splitter.setChildrenCollapsible(False)

        upper_widget = QWidget()
        upper_layout = QVBoxLayout(upper_widget)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(4)

        left_layout.removeWidget(self._drag_drop)
        left_layout.removeWidget(self._search_input)
        left_layout.removeWidget(self._session_tree)

        upper_layout.addWidget(self._drag_drop)
        upper_layout.addWidget(self._search_input)
        upper_layout.addWidget(self._session_tree, 1)
        self._left_splitter.addWidget(upper_widget)

        self._analysis_history_tree = AnalysisHistoryTree()
        self._left_splitter.addWidget(self._analysis_history_tree)
        self._left_splitter.setSizes([300, 150])

        left_layout.insertWidget(0, self._left_splitter, 1)

        self._main_splitter.addWidget(left_col)

        # ── 右栏：AI 对话区域（占位） ────────────────
        self._right_col_placeholder = QWidget()
        self._right_col_placeholder.setMinimumWidth(RIGHT_COL_MIN_WIDTH)
        right_placeholder_layout = QVBoxLayout(self._right_col_placeholder)
        right_placeholder_layout.setContentsMargins(4, 4, 12, 12)
        placeholder_label = QLabel("💬 选择 trace 后可在此进行 AI 分析对话")
        placeholder_label.setStyleSheet(f"color: {colors['fg_dim']}; font-size: 13px;")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setWordWrap(True)
        right_placeholder_layout.addWidget(placeholder_label)
        self._main_splitter.addWidget(self._right_col_placeholder)

        self._main_splitter.setSizes([LEFT_COL_MIN_WIDTH, RIGHT_COL_MIN_WIDTH])
        root_layout.addWidget(self._main_splitter, 1)

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
        self.setFixedWidth(self._panel_width)

        start_x = parent_width
        end_x = parent_width - self._panel_width

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

    def refresh_analysis_history(self, tasks: list[dict]) -> None:
        """刷新分析历史区域。"""
        self._analysis_history_tree.refresh(tasks)

    def set_chat_widget(self, widget: QWidget) -> None:
        """设置右栏的 AI 对话组件，替换占位区域。"""
        if self._chat_widget is not None:
            return
        self._chat_widget = widget
        idx = self._main_splitter.indexOf(self._right_col_placeholder)
        self._right_col_placeholder.setParent(None)
        self._right_col_placeholder.deleteLater()
        self._main_splitter.insertWidget(idx, widget)
        widget.setMinimumWidth(RIGHT_COL_MIN_WIDTH)
        self._main_splitter.setSizes([LEFT_COL_MIN_WIDTH, RIGHT_COL_MIN_WIDTH])

    def set_panel_width(self, width: int) -> None:
        """设置面板宽度（下次打开生效）。"""
        self._panel_width = max(PANEL_MIN_WIDTH, width)

    def set_analysis_available(self, available: bool) -> None:
        """设置分析功能是否可用（保留接口兼容性）。"""
        pass

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
        """获取当前选中项的数据（单选兼容）。"""
        items = self._get_selected_items_data()
        return items[0] if items else None

    def _get_selected_items_data(self) -> list[dict]:
        """获取所有选中项的数据（支持多选）。"""
        items = self._session_tree.selectedItems()
        result = []
        for item in items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                result.append(data)
        return result

    def _update_action_buttons_state(self, _item_data: dict | None = None) -> None:
        """多选状态变更回调（操作已移入右键菜单）。"""
        pass

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """项目点击事件。"""
        self._update_action_buttons_state()

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """项目双击事件（展开/折叠）。"""
        if item.childCount() > 0:
            item.setExpanded(not item.isExpanded())

    def _on_import_package_db(self) -> None:
        self.import_package_db.emit()

    def _on_export_package_db(self) -> None:
        self.export_package_db.emit()
