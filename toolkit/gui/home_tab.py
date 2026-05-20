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
from toolkit.gui.theme_colors import THEMES as _THEME_COLORS
from toolkit.gui import strings as s


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

    tab_title = s.HOME_TAB_TITLE
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

        self._welcome = QLabel(s.HOME_WELCOME)
        self._welcome.setObjectName("homeWelcome")
        content_layout.addWidget(self._welcome)

        self._subtitle = QLabel(s.HOME_SUBTITLE)
        self._subtitle.setObjectName("homeSubtitle")
        content_layout.addWidget(self._subtitle)

        self._divider = QFrame()
        self._divider.setFrameShape(QFrame.Shape.HLine)
        content_layout.addWidget(self._divider)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(12)

        self._device_card = StatusCard(s.HOME_CARD_DEVICE, s.HOME_STATUS_DISCONNECTED, "#f38ba8")
        cards_layout.addWidget(self._device_card, 0, 0)

        self._module_card = StatusCard(s.HOME_CARD_MODULES, "0", "#a6e3a1")
        cards_layout.addWidget(self._module_card, 0, 1)

        self._db_card = StatusCard(s.HOME_CARD_DATABASE, s.HOME_STATUS_READY, "#89b4fa")
        cards_layout.addWidget(self._db_card, 0, 2)

        self._theme_card = StatusCard(s.HOME_CARD_THEME, s.HOME_STATUS_DARK, "#fab387")
        cards_layout.addWidget(self._theme_card, 0, 3)

        cards_wrapper = QHBoxLayout()
        cards_wrapper.addLayout(cards_layout)
        cards_wrapper.addStretch()
        content_layout.addLayout(cards_wrapper)

        self._modules_title = QLabel(s.HOME_MODULES_TITLE)
        self._modules_title.setObjectName("homeModulesTitle")
        content_layout.addWidget(self._modules_title)

        self._modules_container = QVBoxLayout()
        self._modules_container.setSpacing(6)
        content_layout.addLayout(self._modules_container)

        self._no_modules_label = QLabel(s.HOME_NO_MODULES)
        self._no_modules_label.setObjectName("noModulesHint")
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
            self._device_card.set_value(s.HOME_STATUS_DISCONNECTED)
        elif len(devices) == 1:
            self._device_card.set_value(devices[0])
        else:
            self._device_card.set_value(s.HOME_DEVICE_COUNT_FMT.format(count=len(devices)))

        self._module_card.set_value(str(module_count))
        self._theme_card.set_value(s.HOME_STATUS_DARK if theme == "dark" else s.HOME_STATUS_LIGHT)

    def set_theme(self, theme: str) -> None:
        """切换主题 — 全局 QSS 处理大部分样式，此处只更新动态组件。"""
        self._theme = theme

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

        for mod in modules:
            card = QFrame()
            card.setObjectName("moduleCard")
            card.setMaximumWidth(756)
            layout = QHBoxLayout(card)
            layout.setContentsMargins(12, 8, 12, 8)

            name_label = QLabel(mod.get("display_name", mod.get("name", "?")))
            name_label.setObjectName("moduleNameLabel")
            layout.addWidget(name_label)

            version_label = QLabel(f"v{mod.get('version', '?')}")
            version_label.setObjectName("moduleVersionLabel")
            layout.addWidget(version_label)

            desc_label = QLabel(mod.get("description", ""))
            desc_label.setObjectName("moduleDescLabel")
            layout.addWidget(desc_label, 1)

            self._modules_container.addWidget(card)
