from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt

from core.profile_manager import ProfileManager, DeviceProfile


class SaveDialog(QDialog):
    """Save/Edit device profile dialog."""

    def __init__(
        self,
        profile_manager: ProfileManager,
        brand: str = "",
        manufacturer: str = "",
        model: str = "",
        notes: str = "",
        edit_mode: bool = False,
        original_profile: DeviceProfile = None,
        parent=None,
    ):
        super().__init__(parent)
        self._pm = profile_manager
        self._edit_mode = edit_mode
        self._original_profile = original_profile
        self._saved_profile: DeviceProfile = None

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(400, 320)
        self.resize(380, 340)
        self.setModal(True)

        self._init_ui(brand, manufacturer, model, notes)

    def _init_ui(self, brand: str, manufacturer: str, model: str, notes: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        title_bar = QWidget()
        title_bar.setObjectName("dialogTitleBar")
        title_bar.setFixedHeight(36)
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(12, 0, 8, 0)

        title_text = "编辑设备信息" if self._edit_mode else "保存设备信息"
        title = QLabel(title_text)
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        tb_layout.addWidget(title)
        tb_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 22)
        close_btn.setStyleSheet(
            "border: none; font-size: 14px; color: #858585;"
            "QPushButton:hover { color: #ffffff; background-color: #c94a4a; }"
        )
        close_btn.clicked.connect(self.reject)
        tb_layout.addWidget(close_btn)

        layout.addWidget(title_bar)

        # Form area
        form = QWidget()
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(24, 16, 24, 16)
        form_layout.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        field_data = [
            ("Brand:", brand),
            ("Manufacturer:", manufacturer),
            ("Model:", model),
        ]
        self._inputs: list[QLineEdit] = []
        for row, (label_text, value) in enumerate(field_data):
            lbl = QLabel(label_text)
            lbl.setProperty("class", "fieldLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl.setFixedWidth(100)

            inp = QLineEdit(value)
            inp.setObjectName("dialogInput")
            inp.setFixedHeight(28)
            grid.addWidget(lbl, row, 0)
            grid.addWidget(inp, row, 1)
            self._inputs.append(inp)

        # Notes
        notes_lbl = QLabel("Notes:")
        notes_lbl.setProperty("class", "fieldLabel")
        notes_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        notes_lbl.setFixedWidth(100)

        self._notes_input = QTextEdit()
        self._notes_input.setObjectName("notesInput")
        self._notes_input.setFixedHeight(68)
        self._notes_input.setPlaceholderText("请描述此设备信息对应哪些高帧游戏")
        if notes:
            self._notes_input.setPlainText(notes)

        grid.addWidget(notes_lbl, 3, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(self._notes_input, 3, 1)

        form_layout.addLayout(grid)
        form_layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("Save")
        save_btn.setObjectName("startButton")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        btn_layout.addSpacing(16)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("clearButton")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        form_layout.addLayout(btn_layout)

        layout.addWidget(form, 1)

    def _on_save(self):
        brand = self._inputs[0].text().strip()
        manufacturer = self._inputs[1].text().strip()
        model = self._inputs[2].text().strip()
        notes = self._notes_input.toPlainText().strip()

        if not brand or not manufacturer or not model:
            QMessageBox.warning(self, "输入不完整", "Brand、Manufacturer、Model 均为必填项")
            return

        profile = DeviceProfile(
            brand=brand,
            manufacturer=manufacturer,
            model=model,
            notes=notes,
        )

        try:
            if self._edit_mode and self._original_profile:
                self._pm.update(self._original_profile, profile)
            else:
                self._pm.add(profile)
            self._saved_profile = profile
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "保存失败", str(e))

    def get_saved_profile(self) -> DeviceProfile:
        return self._saved_profile
