from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QFrame, QMenu, QMessageBox, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QFont, QCursor

from core.profile_manager import ProfileManager, DeviceProfile
from ui.save_dialog import SaveDialog


class DevicePopup(QWidget):
    profile_selected = pyqtSignal(object)

    def __init__(self, profile_manager: ProfileManager, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._pm = profile_manager
        self._hovered_item: QListWidgetItem = None

        self.setMinimumSize(400, 280)
        self.resize(480, 340)
        self.setObjectName("devicePopup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left panel - device list
        left = QWidget()
        left.setFixedWidth(200)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 0, 8)
        left_layout.setSpacing(4)

        left_title = QLabel("已保存的设备型号")
        left_title.setProperty("class", "fieldLabel")
        left_layout.addWidget(left_title)

        self._list = QListWidget()
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setMouseTracking(True)
        self._list.itemEntered.connect(self._on_item_hovered)
        left_layout.addWidget(self._list, 1)

        layout.addWidget(left)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setProperty("class", "separator")
        layout.addWidget(sep)

        # Right panel - notes
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 8, 8, 8)
        right_layout.setSpacing(4)

        right_title = QLabel("备注")
        right_title.setProperty("class", "fieldLabel")
        right_layout.addWidget(right_title)

        self._note_model_label = QLabel()
        self._note_model_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        self._note_model_label.setWordWrap(True)
        right_layout.addWidget(self._note_model_label)

        note_sep = QFrame()
        note_sep.setFrameShape(QFrame.Shape.HLine)
        note_sep.setProperty("class", "separator")
        right_layout.addWidget(note_sep)

        self._note_content = QLabel()
        self._note_content.setWordWrap(True)
        self._note_content.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_layout.addWidget(self._note_content, 1)

        layout.addWidget(right, 1)

    def show_at(self, pos: QPoint):
        self._refresh_list()
        self.move(pos)
        self.show()

    def _refresh_list(self):
        self._list.clear()
        self._note_model_label.clear()
        self._note_content.clear()

        for profile in self._pm.get_all():
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, profile)
            item.setText(f"{profile.model}\n{profile.brand} · {profile.manufacturer}")
            item.setSizeHint(item.sizeHint().__class__(item.sizeHint().width(), 36))
            self._list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem):
        profile: DeviceProfile = item.data(Qt.ItemDataRole.UserRole)
        self.profile_selected.emit(profile)
        self.close()

    def _on_item_hovered(self, item: QListWidgetItem):
        self._hovered_item = item
        self._show_notes()

    def _show_notes(self):
        if not self._hovered_item:
            return
        profile: DeviceProfile = self._hovered_item.data(Qt.ItemDataRole.UserRole)
        if not profile:
            return

        theme_color = "#ce9178"
        self._note_model_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {theme_color};"
        )
        self._note_model_label.setText(f"{profile.brand} {profile.model}")
        self._note_content.setText(profile.notes if profile.notes else "无备注")

    def _show_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return

        profile: DeviceProfile = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)

        edit_action = menu.addAction("📝 编辑")
        delete_action = menu.addAction("🗑️ 删除")

        action = menu.exec(self._list.mapToGlobal(pos))
        if action == edit_action:
            self._edit_profile(profile)
        elif action == delete_action:
            self._delete_profile(profile)

    def _edit_profile(self, profile: DeviceProfile):
        # parent 设为主窗口而非 Popup，避免 Popup 失焦自动关闭导致异常
        main_window = self.window() if self.parent() is None else self.parent().window()
        self.close()

        dlg = SaveDialog(
            self._pm,
            brand=profile.brand,
            manufacturer=profile.manufacturer,
            model=profile.model,
            notes=profile.notes,
            edit_mode=True,
            original_profile=profile,
            parent=main_window,
        )
        dlg.exec()

    def _delete_profile(self, profile: DeviceProfile):
        main_window = self.window() if self.parent() is None else self.parent().window()
        self.close()

        reply = QMessageBox.question(
            main_window, "确认删除",
            f"确定要删除 {profile.brand}/{profile.model} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._pm.delete(profile)
            except ValueError as e:
                QMessageBox.warning(main_window, "删除失败", str(e))
