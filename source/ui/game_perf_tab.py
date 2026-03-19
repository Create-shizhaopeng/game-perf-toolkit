# -*- coding: utf-8 -*-
"""游戏性能配置工具 Tab：解析/编辑 gameperfconfig.xml + 推送到设备，作为 Toolkit 的第二个选项卡。"""

import os
import pandas as pd
from lxml import etree
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QComboBox, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFrame, QLineEdit, QGridLayout, QTextEdit, QProgressBar, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSlot, QMimeData
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat, QFont, QDragEnterEvent, QDropEvent

from core.adb_manager import AdbManager, DeviceMonitor
from core.device_service import DeviceState
from core.push_policy_service import PushPolicyService, XmlErrorContext, is_valid_config_filename
from core.config_manager import ConfigManager


class GamePerfParser:
    """解析 gameperfconfig.xml，提供数据与保存。"""

    def __init__(self, xml_path: str, parent: QWidget = None):
        self.xml_path = xml_path
        self._parent = parent
        self.original_tree = None
        self.df = None
        self.game_scenes = {}
        self.cpu_clusters = {}
        self.gpu_cluster = {}
        self.parse()

    def _parent_or_none(self):
        return self._parent.window() if self._parent else None

    def parse(self):
        try:
            self.original_tree = etree.parse(self.xml_path)
            root = self.original_tree.getroot()
        except Exception:
            with open(self.xml_path, "r", encoding="utf-8", errors="ignore") as f:
                xml_content = f.read()
            root = etree.fromstring(xml_content.encode("utf-8"))

        data = []

        try:
            pre_env = root.find("PreEnv")
            for cpu_cluster in pre_env.find("CPU").findall("cluster"):
                cname = cpu_cluster.get("name")
                freq_list = [int(f) for f in cpu_cluster.text.strip().split()]
                self.cpu_clusters[cname] = freq_list
            gpu_cluster_elem = pre_env.find("GPU").find("cluster")
            gpu_freq_list = [int(f) for f in gpu_cluster_elem.text.strip().split()]
            self.gpu_cluster["Gpu"] = gpu_freq_list
        except Exception as e:
            QMessageBox.warning(
                self._parent_or_none(), "解析警告", f"PreEnv解析异常：{str(e)}"
            )
            return

        try:
            base_info = root.find("BaseInfo")
            for game in base_info.findall("Game"):
                game_name = game.get("name")
                scenes = []
                for scene in game.find("SceneList").findall("scene"):
                    scene_id = scene.text
                    scene_note = (
                        (scene.tail or "").strip().replace("<!--", "").replace("-->", "").strip()
                    )
                    scenes.append({"scene_id": scene_id, "note": scene_note})
                self.game_scenes[game_name] = scenes
        except Exception:
            pass

        try:
            game_policies = root.find("GamePolicy").findall("Game")
            for game in game_policies:
                game_name = game.get("name")
                game_alias = (
                    game_name
                    if not game_name.startswith("com.")
                    else {
                        "com.tencent.tmgp.pubgmhd": "和平精英",
                        "com.tencent.tmgp.sgame": "王者荣耀",
                        "com.miHoYo.Yuanshen": "原神",
                    }.get(game_name, game_name.split(".")[-1])
                )

                for mode in game.findall("Mode"):
                    mode_name = mode.get("name")
                    for temp_level in mode.find("Policy").findall("TempLevel"):
                        level = temp_level.get("level")
                        temp = temp_level.get("temp")

                        gold_min, gold_max, gold_idx = 0, 0, ""
                        prime_min, prime_max, prime_idx = 0, 0, ""
                        gpu_min, gpu_max, gpu_idx = 0, 0, ""

                        for item in temp_level.findall("item"):
                            item_name = item.get("name")
                            freq_range = item.text.strip()
                            try:
                                start_idx, end_idx = map(int, freq_range.split("_"))
                                if item_name == "Gold" and "Gold" in self.cpu_clusters:
                                    gold_idx = freq_range
                                    freq_vals = self.cpu_clusters["Gold"][
                                        min(start_idx, end_idx) : max(start_idx, end_idx) + 1
                                    ]
                                    gold_min = min(freq_vals) if freq_vals else 0
                                    gold_max = max(freq_vals) if freq_vals else 0
                                elif item_name == "Prime" and "Prime" in self.cpu_clusters:
                                    prime_idx = freq_range
                                    freq_vals = self.cpu_clusters["Prime"][
                                        min(start_idx, end_idx) : max(start_idx, end_idx) + 1
                                    ]
                                    prime_min = min(freq_vals) if freq_vals else 0
                                    prime_max = max(freq_vals) if freq_vals else 0
                                elif item_name == "Gpu" and "Gpu" in self.gpu_cluster:
                                    gpu_idx = freq_range
                                    freq_vals = self.gpu_cluster["Gpu"][
                                        min(start_idx, end_idx) : max(start_idx, end_idx) + 1
                                    ]
                                    gpu_min = min(freq_vals) if freq_vals else 0
                                    gpu_max = max(freq_vals) if freq_vals else 0
                            except Exception:
                                continue

                        data.append({
                            "游戏名称": game_alias,
                            "原始包名": game_name,
                            "性能模式": mode_name,
                            "温度等级": level,
                            "触发温度(℃)": temp,
                            "Gold下限(Hz)": gold_min,
                            "Gold上限(Hz)": gold_max,
                            "Prime下限(Hz)": prime_min,
                            "Prime上限(Hz)": prime_max,
                            "GPU下限(Hz)": gpu_min,
                            "GPU上限(Hz)": gpu_max,
                            "Gold索引": gold_idx,
                            "Prime索引": prime_idx,
                            "GPU索引": gpu_idx,
                            "xml_node": temp_level,
                        })
        except Exception as e:
            QMessageBox.warning(
                self._parent_or_none(), "解析警告", f"GamePolicy解析异常：{str(e)}"
            )

        self.df = pd.DataFrame(data)

    def recalculate_freq_limits(self, row_idx: int) -> bool:
        if row_idx < 0 or row_idx >= len(self.df):
            return False
        row = self.df.iloc[row_idx]
        try:
            gold_idx = row["Gold索引"]
            start_idx, end_idx = map(int, gold_idx.split("_"))
            freq_vals = self.cpu_clusters["Gold"][
                min(start_idx, end_idx) : max(start_idx, end_idx) + 1
            ]
            self.df.iloc[row_idx, self.df.columns.get_loc("Gold下限(Hz)")] = (
                min(freq_vals) if freq_vals else 0
            )
            self.df.iloc[row_idx, self.df.columns.get_loc("Gold上限(Hz)")] = (
                max(freq_vals) if freq_vals else 0
            )
            prime_idx = row["Prime索引"]
            start_idx, end_idx = map(int, prime_idx.split("_"))
            freq_vals = self.cpu_clusters["Prime"][
                min(start_idx, end_idx) : max(start_idx, end_idx) + 1
            ]
            self.df.iloc[row_idx, self.df.columns.get_loc("Prime下限(Hz)")] = (
                min(freq_vals) if freq_vals else 0
            )
            self.df.iloc[row_idx, self.df.columns.get_loc("Prime上限(Hz)")] = (
                max(freq_vals) if freq_vals else 0
            )
            gpu_idx = row["GPU索引"]
            start_idx, end_idx = map(int, gpu_idx.split("_"))
            freq_vals = self.gpu_cluster["Gpu"][
                min(start_idx, end_idx) : max(start_idx, end_idx) + 1
            ]
            self.df.iloc[row_idx, self.df.columns.get_loc("GPU下限(Hz)")] = (
                min(freq_vals) if freq_vals else 0
            )
            self.df.iloc[row_idx, self.df.columns.get_loc("GPU上限(Hz)")] = (
                max(freq_vals) if freq_vals else 0
            )
            return True
        except Exception:
            return False

    def update_xml_node(self, row_idx: int) -> bool:
        if row_idx < 0 or row_idx >= len(self.df):
            return False
        row = self.df.iloc[row_idx]
        try:
            xml_node = row["xml_node"]
            for item in xml_node.findall("item"):
                item_name = item.get("name")
                if item_name == "Gold":
                    item.text = row["Gold索引"]
                elif item_name == "Prime":
                    item.text = row["Prime索引"]
                elif item_name == "Gpu":
                    item.text = row["GPU索引"]
            return True
        except Exception:
            return False

    def save_as_new_xml(self, parent: QWidget = None) -> bool:
        if not self.original_tree:
            QMessageBox.warning(
                parent or self._parent_or_none(), "保存失败", "暂无可保存的配置数据！"
            )
            return False
        win = parent or self._parent_or_none()
        original_dir = os.path.dirname(self.xml_path)
        original_name = os.path.splitext(os.path.basename(self.xml_path))[0]
        default_save_name = f"{original_name}_modified.xml"
        default_save_path = os.path.join(original_dir, default_save_name)

        save_path, _ = QFileDialog.getSaveFileName(
            win,
            "另存为修改后的XML",
            default_save_path,
            "XML文件 (*.xml)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not save_path:
            return False

        if os.path.exists(save_path):
            reply = QMessageBox.question(
                win,
                "确认覆盖",
                f"文件 {os.path.basename(save_path)} 已存在，是否覆盖？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return False

        try:
            if isinstance(self.original_tree, etree._ElementTree):
                self.original_tree.write(
                    save_path, encoding="utf-8", xml_declaration=True, pretty_print=True
                )
            else:
                with open(save_path, "wb") as f:
                    f.write(
                        etree.tostring(
                            self.original_tree,
                            encoding="utf-8",
                            pretty_print=True,
                            xml_declaration=True,
                        )
                    )
            QMessageBox.information(win, "另存为成功", f"已保存到：\n{save_path}")
            return True
        except Exception as e:
            QMessageBox.warning(win, "保存失败", f"无法保存XML：{str(e)}")
            return False


class GamePerfToolTab(QWidget):
    """游戏性能配置工具的可嵌入 Tab 页：编辑 gameperfconfig.xml + 推送到设备。"""

    def __init__(
        self,
        adb_manager: AdbManager,
        config_manager: ConfigManager,
        parent=None,
    ):
        super().__init__(parent)
        self._adb = adb_manager
        self._config_manager = config_manager
        self._current_state = DeviceState()
        self.parser = None
        self.current_filtered_df = None

        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )
        self._push_service = PushPolicyService(adb_manager, data_dir)

        self._init_ui()
        self._connect_signals()
        self._update_push_button_states(False)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)

        self._create_device_info_section(left_layout)
        self._create_file_section(left_layout)
        self._create_game_mode_section(left_layout)
        self._create_table_section(left_layout)
        self._create_log_section(left_layout)
        self._create_button_section(left_layout)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(8)
        self._create_freq_lists_section(right_layout)

        layout.addLayout(left_layout, 3)
        layout.addLayout(right_layout, 1)

    def _create_device_info_section(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 10, 16, 10)
        card_layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("当前设备信息")
        title.setProperty("class", "sectionTitleBlue")
        header.addWidget(title)
        header.addStretch()
        self._badge = QLabel()
        self._badge.setProperty("class", "badgeGreen")
        self._badge.setVisible(False)
        header.addWidget(self._badge)
        card_layout.addLayout(header)

        fields = QGridLayout()
        fields.setHorizontalSpacing(8)
        fields.setVerticalSpacing(4)
        labels = ["brand:", "manufacturer:", "model:"]
        self._info_fields = []
        for i, lbl_text in enumerate(labels):
            lbl = QLabel(lbl_text)
            lbl.setProperty("class", "fieldLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            field = QLineEdit()
            field.setReadOnly(True)
            field.setProperty("class", "readonlyField")
            field.setFixedHeight(26)
            fields.addWidget(lbl, 0, i * 2)
            fields.addWidget(field, 0, i * 2 + 1)
            self._info_fields.append(field)
        card_layout.addLayout(fields)

        conn_layout = QHBoxLayout()
        self._conn_dot = QLabel("●")
        self._conn_dot.setProperty("class", "connectionDot")
        self._conn_dot.setVisible(False)
        conn_layout.addWidget(self._conn_dot)
        self._conn_text = QLabel("未连接设备")
        self._conn_text.setProperty("class", "fieldLabel")
        self._conn_text.setStyleSheet("font-size: 11px;")
        conn_layout.addWidget(self._conn_text)
        conn_layout.addStretch()
        card_layout.addLayout(conn_layout)
        parent_layout.addWidget(card)

    def _create_file_section(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card.setAcceptDrops(True)
        card.setMinimumHeight(80)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 10, 16, 10)
        card_layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("配置文件")
        title.setProperty("class", "sectionTitleOrange")
        header.addWidget(title)
        hint = QLabel("选择或拖拽「文件名包含 gameperfconfig」的 .xml；编辑后可另存为或推送至设备")
        hint.setProperty("class", "fieldLabel")
        hint.setStyleSheet("font-size: 10px; font-style: italic;")
        header.addWidget(hint)
        header.addStretch()
        card_layout.addLayout(header)

        row = QHBoxLayout()
        self._file_input = QLineEdit()
        self._file_input.setPlaceholderText("文件路径（如 gameperfconfig.xml）；推送后设备上为 gameperfconfig.xml")
        self._file_input.setFixedHeight(28)
        self._file_input.setObjectName("fileInput")
        row.addWidget(self._file_input, 1)

        self.open_btn = QPushButton("浏览...")
        self.open_btn.setObjectName("browseButton")
        self.open_btn.setFixedHeight(28)
        self.open_btn.setFixedWidth(70)
        self.open_btn.clicked.connect(self._open_file)
        row.addWidget(self.open_btn)
        card_layout.addLayout(row)
        self._file_card = card
        card.dragEnterEvent = self._on_drag_enter
        card.dropEvent = self._on_drop
        parent_layout.addWidget(card)

    def _create_game_mode_section(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 10, 16, 10)
        card_layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("游戏与模式")
        title.setProperty("class", "sectionTitleBlue")
        header.addWidget(title)
        header.addStretch()
        card_layout.addLayout(header)

        row = QGridLayout()
        row.setHorizontalSpacing(12)
        row.setVerticalSpacing(6)
        lbl = QLabel("游戏：")
        lbl.setProperty("class", "fieldLabel")
        row.addWidget(lbl, 0, 0)
        self.game_cbx = QComboBox()
        self.game_cbx.currentTextChanged.connect(self._on_game_changed)
        row.addWidget(self.game_cbx, 0, 1)
        lbl2 = QLabel("性能模式：")
        lbl2.setProperty("class", "fieldLabel")
        row.addWidget(lbl2, 0, 2)
        self.mode_cbx = QComboBox()
        self.mode_cbx.currentTextChanged.connect(self._refresh)
        row.addWidget(self.mode_cbx, 0, 3)
        self.save_as_btn = QPushButton("另存为修改后的XML")
        self.save_as_btn.setObjectName("browseButton")
        self.save_as_btn.setFixedHeight(28)
        self.save_as_btn.clicked.connect(self._on_save_as)
        self.save_as_btn.setEnabled(False)
        row.addWidget(self.save_as_btn, 0, 4)
        card_layout.addLayout(row)
        parent_layout.addWidget(card)

    def _create_table_section(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 10, 16, 10)
        card_layout.setSpacing(6)

        title = QLabel("频率配置表")
        title.setProperty("class", "sectionTitleBlue")
        card_layout.addWidget(title)

        self.config_table = QTableWidget()
        self.config_table.setObjectName("configTable")
        self.config_table.setColumnCount(11)
        self.config_table.setHorizontalHeaderLabels([
            "温度等级", "触发温度(℃)",
            "Gold下限(Hz)", "Gold上限(Hz)", "Gold索引",
            "Prime下限(Hz)", "Prime上限(Hz)", "Prime索引",
            "GPU下限(Hz)", "GPU上限(Hz)", "GPU索引",
        ])
        self.config_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.config_table.cellChanged.connect(self._on_cell_changed)
        card_layout.addWidget(self.config_table, 1)
        parent_layout.addWidget(card, 1)

    def _create_log_section(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 10, 16, 10)
        card_layout.setSpacing(6)

        title = QLabel("执行日志")
        title.setProperty("class", "sectionTitleBlue")
        card_layout.addWidget(title)

        self._log_area = QTextEdit()
        self._log_area.setObjectName("logArea")
        self._log_area.setReadOnly(True)
        card_layout.addWidget(self._log_area, 1)

        bottom = QVBoxLayout()
        bottom.setSpacing(8)
        sep = QFrame()
        sep.setProperty("class", "separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        bottom.addWidget(sep)
        prog_layout = QHBoxLayout()
        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        prog_layout.addWidget(self._progress_bar, 1)
        self._progress_label = QLabel("0%")
        self._progress_label.setStyleSheet("font-size: 10px;")
        self._progress_label.setFixedWidth(36)
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        prog_layout.addWidget(self._progress_label)
        bottom.addLayout(prog_layout)
        card_layout.addLayout(bottom)
        parent_layout.addWidget(card, 1)

    def _create_button_section(self, parent_layout: QVBoxLayout):
        card = QFrame()
        card.setProperty("class", "sectionCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.addStretch()
        self._start_btn = QPushButton("▶ Start")
        self._start_btn.setObjectName("startButton")
        card_layout.addWidget(self._start_btn)
        card_layout.addStretch()
        self._clear_btn = QPushButton("✕ Clear")
        self._clear_btn.setObjectName("clearButton")
        card_layout.addWidget(self._clear_btn)
        card_layout.addStretch()
        self._reset_btn = QPushButton("↺ Reset")
        self._reset_btn.setObjectName("resetButton")
        card_layout.addWidget(self._reset_btn)
        card_layout.addStretch()
        parent_layout.addWidget(card)

    def _create_freq_lists_section(self, parent_layout: QVBoxLayout):
        for title_text, attr in [
            ("Gold 频率列表（索引→Hz）", "gold_freq_text"),
            ("Prime 频率列表（索引→Hz）", "prime_freq_text"),
            ("GPU 频率列表（索引→Hz）", "gpu_freq_text"),
        ]:
            card = QFrame()
            card.setProperty("class", "sectionCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 10, 16, 10)
            card_layout.setSpacing(6)
            title = QLabel(title_text)
            title.setProperty("class", "sectionTitleBlue")
            card_layout.addWidget(title)
            text = QTextEdit()
            text.setReadOnly(True)
            text.setObjectName("logArea")
            card_layout.addWidget(text, 1)
            setattr(self, attr, text)
            parent_layout.addWidget(card, 1)

    def _open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.window(), "选择配置文件", "", "XML文件 (*.xml)"
        )
        if file_path:
            self._file_input.setText(file_path)
            self._open_file_from_path(file_path)

    def _open_file_from_path(self, file_path: str):
        self.parser = GamePerfParser(file_path, parent=self)
        if self.parser.df is None or self.parser.df.empty:
            QMessageBox.warning(self.window(), "解析失败", "未解析到有效配置数据！")
            return

        self.game_cbx.clear()
        self.game_cbx.addItems(self.parser.df["游戏名称"].unique().tolist())
        self.save_as_btn.setEnabled(True)

        if "Gold" in self.parser.cpu_clusters:
            gold_list = [
                f"{i}: {v} Hz" for i, v in enumerate(self.parser.cpu_clusters["Gold"])
            ]
            self.gold_freq_text.setPlainText("\n".join(gold_list))
        if "Prime" in self.parser.cpu_clusters:
            prime_list = [
                f"{i}: {v} Hz" for i, v in enumerate(self.parser.cpu_clusters["Prime"])
            ]
            self.prime_freq_text.setPlainText("\n".join(prime_list))
        if "Gpu" in self.parser.gpu_cluster:
            gpu_list = [
                f"{i}: {v} Hz" for i, v in enumerate(self.parser.gpu_cluster["Gpu"])
            ]
            self.gpu_freq_text.setPlainText("\n".join(gpu_list))

        self._update_mode_combo()
        self._refresh()

    def _connect_signals(self):
        self._start_btn.clicked.connect(self._on_push_start)
        self._clear_btn.clicked.connect(self._on_push_clear)
        self._reset_btn.clicked.connect(self._on_push_reset)
        self._push_service.progress.connect(self._on_push_progress)
        self._push_service.error.connect(self._on_push_error)
        self._push_service.xml_error.connect(self._on_push_xml_error)
        self._push_service.finished_signal.connect(self._on_push_finished)

    def _on_drag_enter(self, event: QDragEnterEvent):
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                if is_valid_config_filename(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def _on_drop(self, event: QDropEvent):
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if is_valid_config_filename(path):
                    self._file_input.setText(path)
                    self._open_file_from_path(path)
                    event.acceptProposedAction()
                    return
            self._append_log(
                "✗ 仅支持「文件名包含 gameperfconfig」的 .xml 文件",
                self._error_color(),
            )
        event.ignore()

    @pyqtSlot()
    def _on_push_start(self):
        filepath = self._file_input.text().strip()
        if not filepath:
            QMessageBox.warning(self.window(), "未选择文件", "请先选择要推送的配置文件")
            return
        if not os.path.isfile(filepath):
            QMessageBox.warning(self.window(), "文件不存在", f"找不到文件:\n{filepath}")
            return
        if not is_valid_config_filename(filepath):
            QMessageBox.warning(
                self.window(),
                "无效的配置文件",
                "文件名须包含 gameperfconfig 且扩展名为 .xml",
            )
            return
        self._log_area.clear()
        self._set_progress(0)
        self._update_push_button_states(False)
        self._push_service.push(filepath)

    @pyqtSlot()
    def _on_push_clear(self):
        self._file_input.clear()

    @pyqtSlot()
    def _on_push_reset(self):
        self._log_area.clear()
        self._set_progress(0)
        self._update_push_button_states(False)
        self._push_service.reset()

    @pyqtSlot(str)
    def _on_push_progress(self, msg: str):
        color = self._progress_color()
        if "✓" in msg:
            color = self._success_color()
        self._append_log(msg, color)
        self._increment_progress()

    @pyqtSlot(str)
    def _on_push_error(self, msg: str):
        self._append_log(f"✗ {msg}", self._error_color())
        self._update_push_button_states(self._current_state.is_connected)

    @pyqtSlot(object)
    def _on_push_xml_error(self, ctx: XmlErrorContext):
        self._append_log(
            f"✗ XML 格式错误（第 {ctx.error_line} 行）: {ctx.error_msg}",
            self._error_color(),
        )
        if ctx.context_lines:
            self._append_log("", "#888888")
            for line_no, line_text, is_err in ctx.context_lines:
                if is_err:
                    self._append_error_context_line(f" → {line_no:>4}| {line_text}", True)
                else:
                    self._append_error_context_line(f"   {line_no:>4}| {line_text}", False)
            self._append_log("", "#888888")

    @pyqtSlot(bool, str)
    def _on_push_finished(self, success: bool, message: str):
        if success:
            self._set_progress(100)
        self._update_push_button_states(self._current_state.is_connected)

    def on_device_connected(self, serial: str, state: DeviceState):
        self._current_state = state
        self._info_fields[0].setText(state.current_brand)
        self._info_fields[1].setText(state.current_manufacturer)
        self._info_fields[2].setText(state.current_model)
        self._conn_dot.setVisible(True)
        self._conn_text.setText(f"设备已连接 · {serial}")
        self._update_push_button_states(True)

    def on_device_disconnected(self):
        self._current_state = DeviceState()
        for field in self._info_fields:
            field.clear()
        self._conn_dot.setVisible(False)
        self._conn_text.setText("未连接设备")
        self._badge.setVisible(False)
        self._update_push_button_states(False)

    def set_device_monitor(self, monitor: DeviceMonitor):
        """由 MainWindow 调用；设备连接/断开由主窗口回调 on_device_connected / on_device_disconnected。"""
        pass

    def _update_push_button_states(self, enabled: bool):
        self._start_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(True)
        self._reset_btn.setEnabled(enabled)

    def _append_log(self, text: str, color: str = "#d4d4d4"):
        cursor = self._log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text + "\n", fmt)
        self._log_area.setTextCursor(cursor)
        self._log_area.ensureCursorVisible()

    def _append_error_context_line(self, text: str, is_error: bool):
        cursor = self._log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        if is_error:
            fmt.setForeground(QColor("#ff6b6b"))
            fmt.setFontWeight(QFont.Weight.Bold)
            fmt.setBackground(QColor("#3d1f1f"))
        else:
            fmt.setForeground(QColor("#888888"))
            fmt.setFont(QFont("Consolas", 10))
        cursor.insertText(text + "\n", fmt)
        self._log_area.setTextCursor(cursor)
        self._log_area.ensureCursorVisible()

    def _set_progress(self, value: int):
        self._progress_bar.setValue(value)
        self._progress_label.setText(f"{value}%")

    def _increment_progress(self):
        val = self._progress_bar.value()
        total_steps = 12
        step = 100 // total_steps
        new_val = min(val + step, 95)
        self._set_progress(new_val)

    def _is_light_theme(self) -> bool:
        return self._config_manager.get_theme() == "light"

    def _error_color(self) -> str:
        return "#d83b3b" if self._is_light_theme() else "#f44747"

    def _success_color(self) -> str:
        return "#22863a" if self._is_light_theme() else "#608b4e"

    def _progress_color(self) -> str:
        return "#0066b8" if self._is_light_theme() else "#dcdcaa"

    def _on_game_changed(self):
        self._update_mode_combo()
        self._refresh()

    def _update_mode_combo(self):
        if not self.parser or self.parser.df is None or self.parser.df.empty:
            return
        game_name = self.game_cbx.currentText()
        if not game_name:
            return
        modes = self.parser.df[self.parser.df["游戏名称"] == game_name]["性能模式"].unique()
        self.mode_cbx.blockSignals(True)
        self.mode_cbx.clear()
        self.mode_cbx.addItems(modes.tolist())
        self.mode_cbx.blockSignals(False)

    def _on_cell_changed(self, row: int, col: int):
        if not self.parser or self.current_filtered_df is None:
            return
        if col not in [4, 7, 10]:
            self._refresh()
            return
        original_idx = self.current_filtered_df.index[row]
        new_val = self.config_table.item(row, col).text()
        if "_" not in new_val:
            QMessageBox.warning(
                self.window(), "格式错误", "索引必须为 start_end 格式（如 2_8）！"
            )
            self._refresh()
            return
        if col == 4:
            self.parser.df.at[original_idx, "Gold索引"] = new_val
        elif col == 7:
            self.parser.df.at[original_idx, "Prime索引"] = new_val
        elif col == 10:
            self.parser.df.at[original_idx, "GPU索引"] = new_val
        self.parser.recalculate_freq_limits(original_idx)
        self.parser.update_xml_node(original_idx)
        self._refresh()

    def _on_save_as(self):
        if self.parser:
            self.parser.save_as_new_xml(parent=self.window())

    def _refresh(self):
        if not self.parser or self.parser.df is None or self.parser.df.empty:
            return
        game_name = self.game_cbx.currentText()
        mode_name = self.mode_cbx.currentText()
        self.current_filtered_df = self.parser.df[
            (self.parser.df["游戏名称"] == game_name)
            & (self.parser.df["性能模式"] == mode_name)
        ]
        if self.current_filtered_df.empty:
            self.config_table.setRowCount(0)
            return

        self.config_table.blockSignals(True)
        self.config_table.setRowCount(len(self.current_filtered_df))
        for row_idx, (original_idx, row) in enumerate(self.current_filtered_df.iterrows()):
            self.config_table.setItem(row_idx, 0, QTableWidgetItem(str(row["温度等级"])))
            self.config_table.setItem(row_idx, 1, QTableWidgetItem(str(row["触发温度(℃)"])))
            self.config_table.setItem(row_idx, 2, QTableWidgetItem(str(row["Gold下限(Hz)"])))
            self.config_table.setItem(row_idx, 3, QTableWidgetItem(str(row["Gold上限(Hz)"])))
            self.config_table.setItem(row_idx, 4, QTableWidgetItem(row["Gold索引"]))
            self.config_table.setItem(row_idx, 5, QTableWidgetItem(str(row["Prime下限(Hz)"])))
            self.config_table.setItem(row_idx, 6, QTableWidgetItem(str(row["Prime上限(Hz)"])))
            self.config_table.setItem(row_idx, 7, QTableWidgetItem(row["Prime索引"]))
            self.config_table.setItem(row_idx, 8, QTableWidgetItem(str(row["GPU下限(Hz)"])))
            self.config_table.setItem(row_idx, 9, QTableWidgetItem(str(row["GPU上限(Hz)"])))
            self.config_table.setItem(row_idx, 10, QTableWidgetItem(row["GPU索引"]))
            for c in range(11):
                item = self.config_table.item(row_idx, c)
                if c in [4, 7, 10]:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.config_table.blockSignals(False)
