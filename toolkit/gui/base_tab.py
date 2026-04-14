"""模块 Tab 基类 — 所有 GUI 模块页面继承此类"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from toolkit.gui.toolkit_dialog import warning_dialog


class BaseTab(QWidget):
    """所有模块 GUI 页面的抽象基类。

    模块通过 register_gui_tab 钩子返回一个 BaseTab 子类实例，
    由 MainWindow 将其添加到内容区域。

    设备状态感知：MainWindow 在设备列表变化时自动调用
    on_devices_changed()，子类可重写该方法来启用/禁用
    涉及设备操作的按钮。用户当前工作区的数据不会丢失。
    """

    tab_title: str = "未命名"
    tab_icon: str = ""

    def __init__(self, context: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context or {}
        self._device_connected = False

    @property
    def device_connected(self) -> bool:
        """当前是否有设备连接。"""
        return self._device_connected

    def on_activated(self) -> None:
        """当该 Tab 被切换到前台时调用。"""

    def on_deactivated(self) -> None:
        """当该 Tab 被切换到后台时调用。"""

    def on_devices_changed(self, devices: list[str]) -> None:
        """设备列表变化时由 MainWindow 调用。

        子类应重写此方法，根据设备连接状态启用/禁用设备操作按钮。
        用户当前工作区的数据（已填写的内容）不应丢失。
        """
        self._device_connected = len(devices) > 0

    def require_device(self) -> bool:
        """检查设备是否可用。不可用时弹出提示，返回 False。

        模块的设备操作按钮 clicked 回调中可先调用此方法：
            if not self.require_device():
                return
        """
        if self._device_connected:
            return True
        warning_dialog(self, "设备已断开", "当前无可用设备，请连接设备后重试。")
        return False
