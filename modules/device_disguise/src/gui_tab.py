"""设备伪装工具 — GUI 页面"""

from toolkit.gui.base_tab import BaseTab


class DeviceDisguiseTab(BaseTab):
    tab_title = "设备伪装"

    def __init__(self, context=None, parent=None):
        super().__init__(context, parent)
