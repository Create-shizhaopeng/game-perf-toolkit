import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from core.config_manager import ConfigManager
from core.profile_manager import ProfileManager
from core.adb_manager import AdbManager, DeviceMonitor
from core.device_service import DeviceService
from ui.main_window import MainWindow
from ui.styles import apply_theme


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Toolkit")

    config_manager = ConfigManager()
    apply_theme(app, config_manager.get_theme())

    profile_manager = ProfileManager()

    adb_path = config_manager.get_adb_path()
    adb_manager = AdbManager(config_adb_path=adb_path)

    device_service = DeviceService(adb_manager)

    window = MainWindow(
        adb_manager=adb_manager,
        device_service=device_service,
        profile_manager=profile_manager,
        config_manager=config_manager,
    )

    monitor = DeviceMonitor(adb_manager)
    window.set_device_monitor(monitor)
    monitor.start()

    window.show()

    exit_code = app.exec()
    monitor.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
