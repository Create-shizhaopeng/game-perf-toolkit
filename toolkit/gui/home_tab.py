"""首页 Tab — 状态总览和欢迎页"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.base_tab import BaseTab

_THEME_COLORS = {
    "dark": {
        "accent": "#cba6f7",
        "subtitle": "#a6adc8",
        "border": "#313244",
        "muted": "#6c7086",
        "card_title": "#a6adc8",
        "version_fg": "#585b70",
    },
    "light": {
        "accent": "#8839ef",
        "subtitle": "#616161",
        "border": "#ccd0da",
        "muted": "#888888",
        "card_title": "#616161",
        "version_fg": "#888888",
    },
}


class StatusCard(QFrame):
    """状态卡片组件 — 主题自适应"""

    def __init__(self, title: str, value: str, color: str = "#cba6f7", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("statusCard")
        self.setFixedWidth(180)
        self._accent = color
        self._theme = "dark"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        self._title_label = QLabel(title)
        layout.addWidget(self._title_label)

        self._value_label = QLabel(value)
        layout.addWidget(self._value_label)

        self._apply_style()

    def _apply_style(self) -> None:
        c = _THEME_COLORS.get(self._theme, _THEME_COLORS["dark"])
        self.setStyleSheet(f"""
            QFrame#statusCard {{
                border: 1px solid {c['border']};
                border-radius: 8px;
                border-left: 3px solid {self._accent};
            }}
        """)
        self._title_label.setStyleSheet(
            f"font-size: 11px; color: {c['card_title']}; font-weight: bold; background: transparent;"
        )
        self._value_label.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {self._accent}; background: transparent;"
        )

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self._apply_style()

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)


class HomeTab(BaseTab):
    """首页 — 显示系统状态总览"""

    tab_title = "首页"
    tab_icon = "🏠"

    def __init__(self, context: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._cached_modules: list[dict] | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self._theme = "dark"

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(20)

        c = _THEME_COLORS["dark"]

        self._welcome = QLabel("欢迎使用 LV Game Toolkit")
        self._welcome.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['accent']};")
        content_layout.addWidget(self._welcome)

        self._subtitle = QLabel("游戏开发测试工具集 — 集成设备管理、性能分析、日志分析等能力")
        self._subtitle.setStyleSheet(f"font-size: 13px; color: {c['subtitle']};")
        content_layout.addWidget(self._subtitle)

        self._divider = QFrame()
        self._divider.setFrameShape(QFrame.Shape.HLine)
        self._divider.setStyleSheet(f"color: {c['border']};")
        content_layout.addWidget(self._divider)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(12)

        self._device_card = StatusCard("设备状态", "未连接", "#f38ba8")
        cards_layout.addWidget(self._device_card, 0, 0)

        self._module_card = StatusCard("已加载模块", "0", "#a6e3a1")
        cards_layout.addWidget(self._module_card, 0, 1)

        self._db_card = StatusCard("数据库", "就绪", "#89b4fa")
        cards_layout.addWidget(self._db_card, 0, 2)

        self._theme_card = StatusCard("当前主题", "暗色", "#fab387")
        cards_layout.addWidget(self._theme_card, 0, 3)

        cards_wrapper = QHBoxLayout()
        cards_wrapper.addLayout(cards_layout)
        cards_wrapper.addStretch()
        content_layout.addLayout(cards_wrapper)

        self._modules_title = QLabel("已加载模块")
        self._modules_title.setStyleSheet("font-size: 15px; font-weight: bold; margin-top: 8px;")
        content_layout.addWidget(self._modules_title)

        self._modules_container = QVBoxLayout()
        self._modules_container.setSpacing(6)
        content_layout.addLayout(self._modules_container)

        self._no_modules_label = QLabel("暂无已加载模块")
        self._no_modules_label.setObjectName("noModulesHint")
        self._no_modules_label.setStyleSheet(
            f"color: {c['muted']}; font-style: italic; padding: 12px;"
        )
        self._modules_container.addWidget(self._no_modules_label)

        content_layout.addStretch()

        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def update_status(
        self, devices: list[str], module_count: int, theme: str,
    ) -> None:
        """更新首页状态卡片。"""
        if not devices:
            self._device_card.set_value("未连接")
        elif len(devices) == 1:
            self._device_card.set_value(devices[0])
        else:
            self._device_card.set_value(f"{len(devices)} 台")

        self._module_card.set_value(str(module_count))
        self._theme_card.set_value("暗色" if theme == "dark" else "亮色")

    def set_theme(self, theme: str) -> None:
        """切换主题时更新所有内联样式。"""
        self._theme = theme
        c = _THEME_COLORS.get(theme, _THEME_COLORS["dark"])

        self._welcome.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['accent']};")
        self._subtitle.setStyleSheet(f"font-size: 13px; color: {c['subtitle']};")
        self._divider.setStyleSheet(f"color: {c['border']};")
        self._no_modules_label.setStyleSheet(
            f"color: {c['muted']}; font-style: italic; padding: 12px;"
        )

        for card in (self._device_card, self._module_card, self._db_card, self._theme_card):
            card.set_theme(theme)

        if self._cached_modules is not None:
            self.update_modules_list(self._cached_modules)

    def update_modules_list(self, modules: list[dict]) -> None:
        """更新已加载模块列表。"""
        self._cached_modules = modules
        self._no_modules_label.setVisible(not modules)

        while self._modules_container.count() > 1:
            item = self._modules_container.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        c = _THEME_COLORS.get(self._theme, _THEME_COLORS["dark"])

        for mod in modules:
            card = QFrame()
            card.setObjectName("moduleCard")
            card.setMaximumWidth(756)
            card.setStyleSheet(f"""
                QFrame#moduleCard {{
                    border: 1px solid {c['border']};
                    border-radius: 6px;
                }}
                QFrame#moduleCard:hover {{
                    border-color: {'#45475a' if self._theme == 'dark' else '#bcc0cc'};
                }}
            """)
            layout = QHBoxLayout(card)
            layout.setContentsMargins(12, 8, 12, 8)

            name_label = QLabel(mod.get("display_name", mod.get("name", "?")))
            name_label.setStyleSheet("font-weight: bold; font-size: 13px; background: transparent;")
            layout.addWidget(name_label)

            version_label = QLabel(f"v{mod.get('version', '?')}")
            version_label.setStyleSheet(
                f"color: {c['card_title']}; font-size: 11px; background: transparent;"
            )
            layout.addWidget(version_label)

            desc_label = QLabel(mod.get("description", ""))
            desc_label.setStyleSheet(
                f"color: {c['muted']}; font-size: 12px; background: transparent;"
            )
            layout.addWidget(desc_label, 1)

            self._modules_container.addWidget(card)
