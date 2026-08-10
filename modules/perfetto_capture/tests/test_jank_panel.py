"""Jank 配置面板组件测试 — AppSelector 应用选择逻辑"""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from modules.perfetto_capture.src.jank_panel import AppSelector
from modules.perfetto_capture.src.models import AppInfo


@pytest.fixture(scope="session")
def qapp():
    """全局共享 QApplication 实例（避免重复创建）。"""
    app = QApplication.instance() or QApplication([])
    yield app


def _apps(foreground_pkg: str) -> list[AppInfo]:
    return [
        AppInfo(package_name="com.tencent.tmgp.pubgm"),
        AppInfo(package_name="com.tencent.tmgp.sgame"),
        AppInfo(
            package_name=foreground_pkg,
            is_foreground=True,
        ),
    ]


class TestAppSelectorSelectForeground:
    """测试 set_apps 的前台应用选中逻辑。"""

    def test_select_foreground_true_selects_foreground_app(self, qapp):
        selector = AppSelector()
        apps = _apps(foreground_pkg="com.tencent.tmgp.sgame")

        selector.set_apps(apps, select_foreground=True)

        assert selector.selected_package == "com.tencent.tmgp.sgame"

    def test_select_foreground_true_updates_hot_switch(self, qapp):
        """前台应用切换后刷新，自动切换到新前台应用（热切换场景）。"""
        selector = AppSelector()
        # 第一次：和平精英在前台
        selector.set_apps(
            _apps(foreground_pkg="com.tencent.tmgp.pubgm"),
            select_foreground=True,
        )
        assert selector.selected_package == "com.tencent.tmgp.pubgm"

        # 停止后切到王者荣耀（前台），重新启动监测时再次刷新
        selector.set_apps(
            _apps(foreground_pkg="com.tencent.tmgp.sgame"),
            select_foreground=True,
        )
        assert selector.selected_package == "com.tencent.tmgp.sgame"

    def test_select_foreground_false_keeps_current_selection(self, qapp):
        """默认（False）保留当前选中项，不强制切换。"""
        selector = AppSelector()
        selector.set_apps(_apps(foreground_pkg="com.tencent.tmgp.pubgm"))

        # 用户手动选中后台应用后刷新，保持用户选择
        selector._combo.setCurrentIndex(
            selector._combo.findData("com.tencent.tmgp.sgame")
        )
        selector.set_apps(_apps(foreground_pkg="com.tencent.tmgp.pubgm"))

        assert selector.selected_package == "com.tencent.tmgp.sgame"

    def test_select_foreground_false_default_behavior(self, qapp):
        """未传 select_foreground 时默认保留当前选中项。"""
        selector = AppSelector()
        apps = _apps(foreground_pkg="com.tencent.tmgp.sgame")

        selector.set_apps(apps)

        assert selector.selected_package == ""

    def test_empty_apps_clears_selection(self, qapp):
        selector = AppSelector()
        selector.set_apps(
            _apps(foreground_pkg="com.tencent.tmgp.pubgm"),
            select_foreground=True,
        )
        assert selector.selected_package == "com.tencent.tmgp.pubgm"

        selector.set_apps([], select_foreground=True)

        assert selector.selected_package == ""
