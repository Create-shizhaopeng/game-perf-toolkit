"""游戏性能配置 — GUI 页面"""

from toolkit.gui.base_tab import BaseTab


class GamePerfTab(BaseTab):
    tab_title = "性能配置"

    def __init__(self, context=None, parent=None):
        super().__init__(context, parent)
