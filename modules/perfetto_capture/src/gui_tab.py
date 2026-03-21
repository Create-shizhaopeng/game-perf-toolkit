"""Perfetto卡顿抓取 — GUI 页面"""

from toolkit.gui.base_tab import BaseTab


class PerfettoCaptureTab(BaseTab):
    tab_title = "Perfetto卡顿抓取"

    def __init__(self, context=None, parent=None):
        super().__init__(context, parent)
