from PyQt6.QtWidgets import QMenu, QFileDialog, QMessageBox
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QAction

from core.profile_manager import ProfileManager
from core.config_manager import ConfigManager


class SettingsMenu(QObject):
    theme_changed = pyqtSignal(str)
    data_imported = pyqtSignal()

    def __init__(
        self,
        profile_manager: ProfileManager,
        config_manager: ConfigManager,
        parent=None,
    ):
        super().__init__(parent)
        self._pm = profile_manager
        self._cm = config_manager
        self._menu = QMenu(parent)
        self._parent_widget = parent
        self._build_menu()

    def _build_menu(self):
        self._menu.clear()

        import_action = self._menu.addAction("📁 Import Device Data")
        import_action.triggered.connect(self._on_import)

        self._menu.addSeparator()

        current = self._cm.get_theme()
        dark_action = self._menu.addAction("🌙 Dark Theme")
        dark_action.setCheckable(True)
        dark_action.setChecked(current == "dark")
        dark_action.triggered.connect(lambda: self._on_theme("dark"))

        light_action = self._menu.addAction("☀️ Light Theme")
        light_action.setCheckable(True)
        light_action.setChecked(current == "light")
        light_action.triggered.connect(lambda: self._on_theme("light"))

    def show_at(self, pos):
        self._build_menu()
        self._menu.popup(pos)

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self._parent_widget,
            "导入设备档案",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return

        try:
            result = self._pm.import_from(path)
            QMessageBox.information(
                self._parent_widget,
                "导入完成",
                f"成功导入 {result['imported']} 条记录，跳过 {result['skipped']} 条重复记录",
            )
            if result['imported'] > 0:
                self.data_imported.emit()
        except Exception as e:
            QMessageBox.warning(
                self._parent_widget,
                "导入失败",
                f"导入设备档案失败: {e}",
            )

    def _on_theme(self, theme: str):
        self._cm.set_theme(theme)
        self.theme_changed.emit(theme)
