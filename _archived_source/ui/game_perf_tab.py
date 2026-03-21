# -*- coding: utf-8 -*-
"""游戏性能配置工具 Tab：解析/编辑 gameperfconfig.xml + 推送到设备，作为 Toolkit 的第二个选项卡。"""

import os
import re
import json
import functools
from collections import defaultdict
from typing import Optional

import pandas as pd
from datetime import datetime
from lxml import etree
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QComboBox, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFrame, QLineEdit, QGridLayout, QTextEdit, QProgressBar, QSizePolicy,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSlot, QMimeData, pyqtSignal, QTimer
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

    def _flatten_element_kv(self, el: etree._Element) -> list:
        """将 XML 子树展平为若干列：表头为路径+@属性名，单元格为属性值或叶子文本（非整段 XML 字符串）。"""
        root_tag = el.tag
        out = []

        def walk(node: etree._Element, segments: list) -> None:
            if segments:
                disp_path = f"{root_tag}/{'/'.join(segments)}"
            else:
                disp_path = root_tag
            for ak, av in sorted(node.attrib.items()):
                out.append({
                    "header": f"{disp_path}@{ak}",
                    "value": str(av),
                    "dom": node,
                    "mode": "attr",
                    "attr": ak,
                })
            if len(node) == 0:
                tx = (node.text or "").strip()
                if tx:
                    out.append({
                        "header": disp_path,
                        "value": tx,
                        "dom": node,
                        "mode": "text",
                        "attr": None,
                    })
                return
            by_tag = defaultdict(list)
            for ch in node:
                by_tag[ch.tag].append(ch)
            for tname, chlist in by_tag.items():
                for i, ch in enumerate(chlist):
                    seg = f"{tname}[{i}]" if len(chlist) > 1 else tname
                    walk(ch, segments + [seg])

        walk(el, [])
        return out

    def _apply_mode_sync_flags(self, mchild: etree._Element, pairs: list) -> None:
        """标记与频率表 df 列同步的单元格（ThermalSceneCode / PerfHint 文本）。"""
        if mchild.tag == "ThermalSceneCode":
            for p in pairs:
                dom = p.get("dom")
                if (
                    p.get("mode") == "text"
                    and dom is not None
                    and getattr(dom, "tag", None) == "ThermalSceneCode"
                ):
                    p["sync_df"] = "ThermalSceneCode"
        elif mchild.tag == "PerfHint":
            for p in pairs:
                dom = p.get("dom")
                if (
                    dom is not None
                    and getattr(dom, "tag", None) == "opcode"
                    and p.get("mode") == "text"
                ):
                    p["sync_df"] = "PerfHint"

    def apply_strategy_kv_edit(self, dom: etree._Element, mode: str, attr: Optional[str], value: str) -> bool:
        """根据展平项写回 XML：属性或叶子文本。"""
        try:
            if mode == "attr" and attr:
                dom.set(attr, value)
                return True
            if mode == "text":
                dom.text = value
                return True
        except Exception:
            return False
        return False

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

        data = self._parse_game_policy_section(root)
        self.df = pd.DataFrame(data)

    def _parse_game_policy_section(self, root: etree._Element) -> list:
        """解析 GamePolicy：更新 game_full_xml / game_level_data / mode_level_data，返回频率表行列表。"""
        data: list = []
        self.game_full_xml = {}
        self.game_level_data = {}
        self.mode_level_data = {}
        try:
            game_policies = root.find("GamePolicy").findall("Game")
            for game in game_policies:
                game_name = game.get("name")
                self.game_full_xml[game_name] = etree.tostring(
                    game, encoding="unicode", pretty_print=True
                ).strip()
                game_level_items = []
                for child in game:
                    if child.tag in ("Mode", "Policy"):
                        continue
                    pairs = self._flatten_element_kv(child)
                    if not pairs:
                        pairs = [{
                            "header": child.tag,
                            "value": "",
                            "dom": child,
                            "mode": "text",
                            "attr": None,
                        }]
                    game_level_items.append({
                        "tag": child.tag,
                        "pairs": pairs,
                        "element": child,
                    })
                self.game_level_data[game_name] = game_level_items

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
                    mode_key = (game_name, mode_name)
                    mode_items = []
                    for mchild in mode:
                        if mchild.tag == "Policy":
                            continue
                        pairs = self._flatten_element_kv(mchild)
                        if not pairs:
                            pairs = [{
                                "header": mchild.tag,
                                "value": "",
                                "dom": mchild,
                                "mode": "text",
                                "attr": None,
                            }]
                        self._apply_mode_sync_flags(mchild, pairs)
                        mode_items.append({
                            "tag": mchild.tag,
                            "pairs": pairs,
                            "element": mchild,
                        })
                    self.mode_level_data[mode_key] = mode_items

                    policy_elem = mode.find("Policy")
                    temp_levels = policy_elem.findall("TempLevel") if policy_elem is not None else []
                    if not temp_levels:
                        continue
                    thermal_scene_elem = mode.find("ThermalSceneCode")
                    thermal_scene_code = (thermal_scene_elem.text or "").strip() if thermal_scene_elem is not None else ""
                    perf_hint_elem = mode.find("PerfHint")
                    perf_hint_value = ""
                    if perf_hint_elem is not None:
                        opcode = perf_hint_elem.find("opcode")
                        if opcode is not None and opcode.text:
                            perf_hint_value = (opcode.text or "").strip()

                    for temp_level in temp_levels:
                        level = temp_level.get("level")
                        temp = temp_level.get("temp")
                        gold_min, gold_max, gold_idx = 0, 0, ""
                        prime_min, prime_max, prime_idx = 0, 0, ""
                        gpu_min, gpu_max, gpu_idx = 0, 0, ""

                        for item in temp_level.findall("item"):
                            item_name = item.get("name")
                            freq_range = (item.text or "").strip()
                            if not freq_range:
                                continue
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
                            "ThermalSceneCode": thermal_scene_code,
                            "PerfHint": perf_hint_value,
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
                            "mode_xml_node": mode,
                        })
        except Exception as e:
            QMessageBox.warning(
                self._parent_or_none(), "解析警告", f"GamePolicy解析异常：{str(e)}"
            )
        return data

    def refresh_game_policy_data(self) -> bool:
        """内存 XML 树发生结构性变更后，重建 GamePolicy 相关结构与频率表（不重新读盘）。"""
        if self.original_tree is None:
            return False
        if not isinstance(self.original_tree, etree._ElementTree):
            return False
        root = self.original_tree.getroot()
        data = self._parse_game_policy_section(root)
        self.df = pd.DataFrame(data)
        return True

    def remove_xml_subtree(self, el: etree._Element) -> bool:
        """从树中移除节点并刷新 GamePolicy 内存数据。"""
        parent = el.getparent()
        if parent is None:
            return False
        parent.remove(el)
        return self.refresh_game_policy_data()

    def append_bindcore_child_row(self, bind_root: etree._Element) -> bool:
        """在 BindCore 下追加一条子节点：标签与同层已有子节点一致（无则默认为 tid），name 与文本为空。"""
        if bind_root is None:
            return False
        if getattr(bind_root, "tag", None) != "BindCore":
            return False
        child_tag = "tid"
        for ch in bind_root:
            child_tag = ch.tag
            break
        el = etree.SubElement(bind_root, child_tag)
        el.set("name", "")
        # 占位文本，便于与 name 合并成「键/值」双列且均可编辑；可改为任意掩码如 c0
        el.text = "0"
        return self.refresh_game_policy_data()

    def recalculate_freq_limits(self, row_label) -> bool:
        """按 DataFrame 行标签（index）重算 Gold/Prime/GPU 频率上下限。"""
        if self.df is None or self.df.empty or row_label not in self.df.index:
            return False
        row = self.df.loc[row_label]
        try:
            gold_idx = row["Gold索引"]
            start_idx, end_idx = map(int, gold_idx.split("_"))
            freq_vals = self.cpu_clusters["Gold"][
                min(start_idx, end_idx) : max(start_idx, end_idx) + 1
            ]
            self.df.at[row_label, "Gold下限(Hz)"] = (
                min(freq_vals) if freq_vals else 0
            )
            self.df.at[row_label, "Gold上限(Hz)"] = (
                max(freq_vals) if freq_vals else 0
            )
            prime_idx = row["Prime索引"]
            start_idx, end_idx = map(int, prime_idx.split("_"))
            freq_vals = self.cpu_clusters["Prime"][
                min(start_idx, end_idx) : max(start_idx, end_idx) + 1
            ]
            self.df.at[row_label, "Prime下限(Hz)"] = (
                min(freq_vals) if freq_vals else 0
            )
            self.df.at[row_label, "Prime上限(Hz)"] = (
                max(freq_vals) if freq_vals else 0
            )
            gpu_idx = row["GPU索引"]
            start_idx, end_idx = map(int, gpu_idx.split("_"))
            freq_vals = self.gpu_cluster["Gpu"][
                min(start_idx, end_idx) : max(start_idx, end_idx) + 1
            ]
            self.df.at[row_label, "GPU下限(Hz)"] = (
                min(freq_vals) if freq_vals else 0
            )
            self.df.at[row_label, "GPU上限(Hz)"] = (
                max(freq_vals) if freq_vals else 0
            )
            return True
        except Exception:
            return False

    def update_xml_node(self, row_label) -> bool:
        """按 DataFrame 行标签（index）把当前行的温控/频点写回 XML 节点。"""
        if self.df is None or self.df.empty or row_label not in self.df.index:
            return False
        row = self.df.loc[row_label]
        try:
            xml_node = row["xml_node"]
            xml_node.set("temp", str(row["触发温度(℃)"]))
            for item in xml_node.findall("item"):
                item_name = item.get("name")
                if item_name == "Gold":
                    item.text = row["Gold索引"]
                elif item_name == "Prime":
                    item.text = row["Prime索引"]
                elif item_name == "Gpu":
                    item.text = row["GPU索引"]
            mode_node = row.get("mode_xml_node")
            if mode_node is not None:
                thermal_elem = mode_node.find("ThermalSceneCode")
                if thermal_elem is not None:
                    thermal_elem.text = str(row.get("ThermalSceneCode", ""))
                perf_elem = mode_node.find("PerfHint")
                if perf_elem is not None:
                    opcode = perf_elem.find("opcode")
                    if opcode is not None:
                        opcode.text = str(row.get("PerfHint", ""))
            return True
        except Exception:
            return False

    def _sync_mode_fields_to_df(self, game_pkg: str, mode_name: str, col_name: str, value: str) -> None:
        """ThermalSceneCode / PerfHint 等与频率表列一致时，同步该模式下所有 TempLevel 行。"""
        if self.df is None or self.df.empty or col_name not in self.df.columns:
            return
        mask = (self.df["原始包名"] == game_pkg) & (self.df["性能模式"] == mode_name)
        for idx in self.df.index[mask]:
            self.df.at[idx, col_name] = value

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

    def write_to_path(self, path: str) -> bool:
        """将当前 original_tree 写入指定路径（用于 push 前保存修改到原文件）。"""
        if not self.original_tree:
            return False
        try:
            if isinstance(self.original_tree, etree._ElementTree):
                self.original_tree.write(
                    path, encoding="utf-8", xml_declaration=True, pretty_print=True
                )
            else:
                with open(path, "wb") as f:
                    f.write(
                        etree.tostring(
                            self.original_tree,
                            encoding="utf-8",
                            pretty_print=True,
                            xml_declaration=True,
                        )
                    )
            return True
        except Exception:
            return False


class GamePerfToolTab(QWidget):
    """游戏性能配置工具的可嵌入 Tab 页：编辑 gameperfconfig.xml + 推送到设备。"""

    refresh_device_requested = pyqtSignal()

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

        self._data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )
        self._push_service = PushPolicyService(adb_manager, self._data_dir)

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

        # 右侧：三列表并排；整体贴顶，高度随内容变化，不随左侧拉满整窗
        right_wrap = QWidget()
        right_wrap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        right_wrap.setFixedWidth(558)
        freq_row = QHBoxLayout(right_wrap)
        freq_row.setContentsMargins(0, 0, 0, 0)
        freq_row.setSpacing(6)
        self._create_freq_lists_section(freq_row)

        right_container = QWidget()
        right_container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        right_container.setFixedWidth(558)
        right_container.setMinimumHeight(200)
        rv = QVBoxLayout(right_container)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(8)
        rv.addWidget(right_wrap, 0, Qt.AlignmentFlag.AlignTop)
        # 整体策略 + 性能模式策略：与频率列表共分右侧纵向空间，避免被压扁
        self._create_strategy_sections(rv)

        layout.addLayout(left_layout, 1)
        layout.addWidget(right_container, 0)

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

        row = QHBoxLayout()
        row.setSpacing(6)
        lbl = QLabel("游戏：")
        lbl.setProperty("class", "fieldLabel")
        row.addWidget(lbl)
        self.game_cbx = QComboBox()
        self.game_cbx.setMinimumWidth(120)
        self.game_cbx.setMaximumWidth(180)
        self.game_cbx.currentTextChanged.connect(self._on_game_changed)
        row.addWidget(self.game_cbx)
        lbl2 = QLabel("性能模式：")
        lbl2.setProperty("class", "fieldLabel")
        row.addWidget(lbl2)
        self.mode_cbx = QComboBox()
        self.mode_cbx.setMinimumWidth(100)
        self.mode_cbx.setMaximumWidth(150)
        self.mode_cbx.currentTextChanged.connect(self._refresh)
        row.addWidget(self.mode_cbx)
        self.save_as_btn = QPushButton("另存为修改后的XML")
        self.save_as_btn.setObjectName("browseButton")
        self.save_as_btn.setFixedHeight(28)
        self.save_as_btn.clicked.connect(self._on_save_as)
        self.save_as_btn.setEnabled(False)
        row.addWidget(self.save_as_btn)
        row.addStretch()
        card_layout.addLayout(row)

        # 当前数据备注说明（push 时随 JSON 一并保存）
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        lbl_adv = QLabel("当前数据备注：")
        lbl_adv.setProperty("class", "fieldLabel")
        row2.addWidget(lbl_adv)
        self._advantage_input = QLineEdit()
        self._advantage_input.setPlaceholderText("可填写本配置的备注说明，push 时随 JSON 一并保存到以游戏包名命名的文件夹")
        self._advantage_input.setObjectName("fileInput")
        self._advantage_input.setFixedHeight(28)
        row2.addWidget(self._advantage_input, 1)
        card_layout.addLayout(row2)
        parent_layout.addWidget(card)

    def _create_strategy_sections(self, parent_layout: QVBoxLayout):
        """右侧：按节点分组，每组标题 + 「键(Key)/值(Value)」竖向表单（与示意图一致）。"""
        def _make_strategy_card(title_text: str, hint_text: str, scroll_attr: str, layout_attr: str):
            card = QFrame()
            card.setProperty("class", "strategyPolicySection")
            card.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 8, 12, 8)
            cl.setSpacing(4)
            t_title = QLabel(title_text)
            t_title.setProperty("class", "sectionTitleBlue")
            cl.addWidget(t_title)
            hint = QLabel(hint_text)
            hint.setProperty("class", "fieldLabel")
            hint.setStyleSheet("font-size: 10px; font-style: italic;")
            hint.setWordWrap(True)
            hint.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            cl.addWidget(hint)
            scroll = QScrollArea()
            scroll.setProperty("class", "strategyPolicyScroll")
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            scroll.setMinimumHeight(96)
            inner = QWidget()
            inner.setProperty("class", "strategyPolicyInner")
            inner.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
            )
            inner_layout = QVBoxLayout(inner)
            inner_layout.setContentsMargins(2, 2, 2, 2)
            inner_layout.setSpacing(10)
            scroll.setWidget(inner)
            cl.addWidget(scroll, 1)
            setattr(self, scroll_attr, scroll)
            setattr(self, layout_attr, inner_layout)
            return card

        self._overall_strategy_card = _make_strategy_card(
            "整体策略",
            "按 XML 节点分组；每组下列出 键(Key) 与可编辑的 值(Value)",
            "_overall_strategy_scroll",
            "_overall_strategy_inner_layout",
        )
        parent_layout.addWidget(self._overall_strategy_card, 1)

        self._mode_strategy_card = _make_strategy_card(
            "性能模式策略",
            "当前性能模式下各节点（如 PerfHint）同上；切换模式后表单会更新",
            "_mode_strategy_scroll",
            "_mode_strategy_inner_layout",
        )
        parent_layout.addWidget(self._mode_strategy_card, 1)

    def _clear_strategy_inner_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                # 子布局一般不会出现；保险处理
                self._clear_strategy_inner_layout(item.layout())

    def _strategy_key_label(self, p: dict) -> str:
        """键列：属性行只写属性名（如 name）；文本/叶子行写元素标签名（如 RenderThread）。

        不再用 XML 属性 name= 的值拼进 Key（否则会显示成 RenderThread·name 等）。"""
        dom = p.get("dom")
        if p.get("mode") == "attr" and p.get("attr"):
            return str(p["attr"])
        if dom is not None and getattr(dom, "tag", None):
            return str(dom.tag)
        h = str(p.get("header", ""))
        if "@" in h:
            return h.rsplit("@", 1)[-1]
        return h.rsplit("/", 1)[-1]

    def _iter_strategy_kv_rows(self, pairs: list):
        """展平后的 pairs 顺序输出；同一元素上 name 属性 + 叶子文本合并为一行（两格均可编辑）。"""
        plist = [
            p
            for p in (pairs or [])
            if isinstance(p, dict) and p.get("dom") is not None
        ]
        skip_text_dom_ids: set = set()
        i, n = 0, len(plist)
        while i < n:
            p = plist[i]
            dom = p.get("dom")
            if p.get("mode") == "text" and id(dom) in skip_text_dom_ids:
                i += 1
                continue
            if (
                p.get("mode") == "attr"
                and p.get("attr") == "name"
                and dom is not None
            ):
                text_p = None
                for j in range(i + 1, n):
                    q = plist[j]
                    if q.get("dom") is dom and q.get("mode") == "text":
                        text_p = q
                        break
                if text_p is not None:
                    skip_text_dom_ids.add(id(dom))
                    yield ("merged_name_text", p, text_p)
                    i += 1
                    continue
            yield ("single", p)
            i += 1

    def _normalize_strategy_pairs(self, rec: dict) -> list:
        """保证每项含 header/value/dom/mode/attr；兼容仅有 tag+value+element 的旧结构。"""
        raw = rec.get("pairs")
        out = []
        if isinstance(raw, list):
            for p in raw:
                if not isinstance(p, dict):
                    continue
                dom = p.get("dom")
                mode = p.get("mode", "text")
                attr = p.get("attr")
                if dom is None:
                    continue
                out.append({
                    "header": str(p.get("header", "")),
                    "value": str(p.get("value", "")),
                    "dom": dom,
                    "mode": mode if mode in ("attr", "text") else "text",
                    "attr": attr,
                    "sync_df": p.get("sync_df"),
                })
        if not out:
            el = rec.get("element")
            tag = rec.get("tag") or (el.tag if el is not None else "?")
            if el is not None:
                out.append({
                    "header": str(tag),
                    "value": str(rec.get("value", "")),
                    "dom": el,
                    "mode": "text",
                    "attr": None,
                    "sync_df": rec.get("sync_df"),
                })
        return out

    def _strategy_block_separator(self) -> QFrame:
        sep = QFrame()
        sep.setProperty("class", "separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        return sep

    def _append_perfhint_wireframe_block(
        self,
        parent_layout: QVBoxLayout,
        title_text: str,
        opcode_el: etree._Element,
        mode_context: bool,
    ) -> None:
        """PerfHint：居中标题 + 横线 + 并排两栏（id / time），下有可选数据文本。"""
        block = QFrame()
        block.setProperty("class", "strategyNodeBlock")
        bl = QVBoxLayout(block)
        bl.setContentsMargins(8, 12, 8, 12)
        bl.setSpacing(8)
        st = QLabel(title_text)
        st.setProperty("class", "sectionTitleBlue")
        st.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        bl.addWidget(st)
        bl.addWidget(self._strategy_block_separator())
        row = QHBoxLayout()
        row.setSpacing(8)
        meta_id = {
            "header": "id",
            "value": str(opcode_el.get("id", "") or ""),
            "dom": opcode_el,
            "mode": "attr",
            "attr": "id",
        }
        ed_id = QLineEdit(meta_id["value"])
        ed_id.setObjectName("fileInput")
        ed_id.setMinimumHeight(28)
        ed_id.editingFinished.connect(
            functools.partial(self._commit_strategy_kv, meta_id, ed_id, mode_context)
        )
        meta_time = {
            "header": "time",
            "value": str(opcode_el.get("time", "") or ""),
            "dom": opcode_el,
            "mode": "attr",
            "attr": "time",
        }
        ed_time = QLineEdit(meta_time["value"])
        ed_time.setObjectName("fileInput")
        ed_time.setMinimumHeight(28)
        ed_time.editingFinished.connect(
            functools.partial(self._commit_strategy_kv, meta_time, ed_time, mode_context)
        )
        row.addWidget(ed_id, 1)
        row.addWidget(ed_time, 1)
        bl.addLayout(row)
        body = (opcode_el.text or "").strip()
        meta_txt = {
            "header": "opcode",
            "value": body,
            "dom": opcode_el,
            "mode": "text",
            "attr": None,
            "sync_df": "PerfHint",
        }
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        lbl_d = QLabel("数据")
        lbl_d.setProperty("class", "fieldLabel")
        ed_body = QLineEdit(body)
        ed_body.setObjectName("fileInput")
        ed_body.setMinimumHeight(28)
        ed_body.editingFinished.connect(
            functools.partial(self._commit_strategy_kv, meta_txt, ed_body, mode_context)
        )
        row2.addWidget(lbl_d)
        row2.addWidget(ed_body, 1)
        bl.addLayout(row2)
        parent_layout.addWidget(block)

    def _bindcore_direct_child_for_dom(
        self,
        dom: Optional[etree._Element],
        bind_root: Optional[etree._Element],
    ) -> Optional[etree._Element]:
        """找到 dom 在 BindCore(bind_root) 下的直接子节点（如 tid），用于删整行。"""
        if dom is None or bind_root is None or dom is bind_root:
            return None
        cur: Optional[etree._Element] = dom
        while cur is not None:
            par = cur.getparent()
            if par is bind_root:
                return cur
            cur = par
        return None

    def _on_bindcore_delete_row(self, target_el: etree._Element, _mode_context: bool) -> None:
        if not self.parser:
            return
        r = QMessageBox.question(
            self.window(),
            "确认删除",
            "删除该条绑核配置（对应 XML 子节点）？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        if self.parser.remove_xml_subtree(target_el):
            self._refresh()
        else:
            QMessageBox.warning(self.window(), "删除失败", "无法从 XML 树中移除该节点。")

    def _on_bindcore_delete_whole(self, root_el: etree._Element, _mode_context: bool) -> None:
        if not self.parser:
            return
        r = QMessageBox.question(
            self.window(),
            "确认删除",
            "删除整个 BindCore 节点及其所有子项？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        if self.parser.remove_xml_subtree(root_el):
            self._refresh()
        else:
            QMessageBox.warning(self.window(), "删除失败", "无法移除 BindCore 节点。")

    def _make_bindcore_delete_row_button(self) -> QPushButton:
        btn = QPushButton("×")
        btn.setObjectName("bindcoreDeleteXBtn")
        btn.setFixedSize(28, 26)
        btn.setToolTip("删除该行")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _on_bindcore_add_row(self, root_el: etree._Element, _mode_context: bool) -> None:
        if not self.parser:
            return
        if self.parser.append_bindcore_child_row(root_el):
            self._refresh()
        else:
            QMessageBox.warning(
                self.window(),
                "添加失败",
                "无法在 BindCore 下添加子项（请确认当前节点为 BindCore）。",
            )

    def _append_kv_node_block(
        self,
        parent_layout: QVBoxLayout,
        node_tag: str,
        pairs: list,
        mode_context: bool,
        root_element: Optional[etree._Element] = None,
    ) -> None:
        """单个节点：居中标题 + 分隔线；PerfHint+opcode 用并排两栏示意，其余用键(Key)/值(Value) 表。

        BindCore：标题栏「添加绑核项」「删除整块」；每行红色 × 删除对应子节点。"""
        if (
            node_tag == "PerfHint"
            and root_element is not None
        ):
            opcode = root_element.find("opcode")
            if opcode is not None:
                self._append_perfhint_wireframe_block(
                    parent_layout, node_tag, opcode, mode_context
                )
                return
        is_bindcore = node_tag == "BindCore" and root_element is not None
        block = QFrame()
        block.setProperty("class", "strategyNodeBlock")
        bl = QVBoxLayout(block)
        bl.setContentsMargins(8, 8, 8, 8)
        bl.setSpacing(6)
        if is_bindcore:
            title_row = QHBoxLayout()
            st = QLabel(node_tag)
            st.setProperty("class", "sectionTitleBlue")
            title_row.addWidget(st)
            title_row.addStretch()
            add_btn = QPushButton("添加绑核项")
            add_btn.setObjectName("browseButton")
            add_btn.setFixedHeight(26)
            add_btn.clicked.connect(
                functools.partial(
                    self._on_bindcore_add_row, root_element, mode_context
                )
            )
            title_row.addWidget(add_btn)
            del_all = QPushButton("删除整块BindCore")
            del_all.setObjectName("browseButton")
            del_all.setFixedHeight(26)
            del_all.clicked.connect(
                functools.partial(
                    self._on_bindcore_delete_whole, root_element, mode_context
                )
            )
            title_row.addWidget(del_all)
            bl.addLayout(title_row)
        else:
            st = QLabel(node_tag)
            st.setProperty("class", "sectionTitleBlue")
            st.setAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )
            bl.addWidget(st)
        bl.addWidget(self._strategy_block_separator())
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)
        hk = QLabel("键(Key)")
        hv = QLabel("值(Value)")
        hk.setProperty("class", "fieldLabel")
        hv.setProperty("class", "fieldLabel")
        if is_bindcore:
            h_del = QLabel("")
            h_del.setFixedWidth(34)
            grid.addWidget(h_del, 0, 0)
            grid.addWidget(hk, 0, 1)
            grid.addWidget(hv, 0, 2)
            grid.setColumnStretch(0, 0)
            grid.setColumnStretch(1, 2)
            grid.setColumnStretch(2, 3)
        else:
            grid.addWidget(hk, 0, 0)
            grid.addWidget(hv, 0, 1)
            grid.setColumnStretch(0, 2)
            grid.setColumnStretch(1, 3)
        row_idx = 1
        kc0, kc1 = (1, 2) if is_bindcore else (0, 1)

        def _add_bindcore_delete_btn(dom_for_row: Optional[etree._Element]) -> None:
            nonlocal row_idx
            tgt = self._bindcore_direct_child_for_dom(dom_for_row, root_element)
            if tgt is not None:
                btn = self._make_bindcore_delete_row_button()
                btn.clicked.connect(
                    functools.partial(self._on_bindcore_delete_row, tgt, mode_context)
                )
                grid.addWidget(btn, row_idx, 0, Qt.AlignmentFlag.AlignCenter)
            else:
                ph = QLabel("")
                ph.setFixedWidth(34)
                grid.addWidget(ph, row_idx, 0)

        for row in self._iter_strategy_kv_rows(pairs):
            if row[0] == "merged_name_text":
                _, name_p, text_p = row
                if is_bindcore:
                    _add_bindcore_delete_btn(name_p.get("dom"))
                ed_key = QLineEdit(str(name_p.get("value", "")))
                ed_key.setObjectName("fileInput")
                ed_key.setMinimumHeight(26)
                ed_val = QLineEdit(str(text_p.get("value", "")))
                ed_val.setObjectName("fileInput")
                ed_val.setMinimumHeight(26)
                grid.addWidget(ed_key, row_idx, kc0)
                grid.addWidget(ed_val, row_idx, kc1)
                ed_key.editingFinished.connect(
                    functools.partial(
                        self._commit_strategy_kv, name_p, ed_key, mode_context
                    )
                )
                ed_val.editingFinished.connect(
                    functools.partial(
                        self._commit_strategy_kv, text_p, ed_val, mode_context
                    )
                )
                row_idx += 1
                continue
            _, p = row
            if is_bindcore:
                _add_bindcore_delete_btn(p.get("dom"))
            kl = QLabel(self._strategy_key_label(p))
            kl.setProperty("class", "fieldLabel")
            kl.setWordWrap(True)
            ed = QLineEdit(str(p.get("value", "")))
            ed.setObjectName("fileInput")
            ed.setMinimumHeight(26)
            grid.addWidget(kl, row_idx, kc0)
            grid.addWidget(ed, row_idx, kc1)
            ed.editingFinished.connect(
                functools.partial(self._commit_strategy_kv, p, ed, mode_context)
            )
            row_idx += 1
        bl.addLayout(grid)
        parent_layout.addWidget(block)

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

    def _create_freq_lists_section(self, parent_layout: QHBoxLayout):
        """Gold / Prime / GPU 三个列表并排一行（与红框示意一致）。"""
        for title_text, attr in [
            ("Gold 频率列表（索引→Hz）", "gold_freq_text"),
            ("Prime 频率列表（索引→Hz）", "prime_freq_text"),
            ("GPU 频率列表（索引→Hz）", "gpu_freq_text"),
        ]:
            card = QFrame()
            card.setProperty("class", "sectionCard")
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 8, 8, 8)
            card_layout.setSpacing(4)
            title = QLabel(title_text)
            title.setProperty("class", "sectionTitleBlue")
            title.setWordWrap(True)
            card_layout.addWidget(title)
            text = QTextEdit()
            text.setReadOnly(True)
            text.setObjectName("logArea")
            text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
            text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            text.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            card_layout.addWidget(text, 0)
            setattr(self, attr, text)
            parent_layout.addWidget(card, 1)

    def _resize_freq_list_edit(self, edit: QTextEdit) -> None:
        """按文档行数自适应列表高度，避免右侧被拉满整窗。"""
        doc = edit.document()
        w = edit.viewport().width()
        if w < 40:
            w = 145
        doc.setTextWidth(w)
        h = int(doc.size().height())
        extra = (
            edit.frameWidth() * 2
            + edit.contentsMargins().top()
            + edit.contentsMargins().bottom()
            + 10
        )
        h = max(72, min(h + extra, 520))
        edit.setFixedHeight(h)

    def _apply_freq_list_heights(self) -> None:
        for attr in ("gold_freq_text", "prime_freq_text", "gpu_freq_text"):
            edit = getattr(self, attr, None)
            if isinstance(edit, QTextEdit):
                self._resize_freq_list_edit(edit)

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

        # 布局后再量高度，避免 viewport 宽度为 0
        QTimer.singleShot(0, self._apply_freq_list_heights)
        QTimer.singleShot(80, self._apply_freq_list_heights)

        self._update_mode_combo()
        self._update_strategy_displays()
        self._refresh()

    def _update_strategy_displays(self):
        self._update_overall_strategy_display()
        self._update_mode_strategy_display()

    def _update_overall_strategy_display(self):
        """整体策略：按节点分块，键(Key)/值(Value) 竖向表单。"""
        if not hasattr(self, "_overall_strategy_inner_layout"):
            return
        lay = self._overall_strategy_inner_layout
        self._clear_strategy_inner_layout(lay)
        if not self.parser or self.parser.df is None or self.parser.df.empty:
            return
        game_alias = self.game_cbx.currentText()
        if not game_alias:
            return
        df = self.parser.df
        pkg_row = df[df["游戏名称"] == game_alias]
        if pkg_row.empty:
            return
        pkg = pkg_row["原始包名"].iloc[0]
        items = getattr(self.parser, "game_level_data", None) or {}
        for rec in items.get(pkg, []):
            if not isinstance(rec, dict):
                continue
            tag = rec.get("tag") or "?"
            pairs = self._normalize_strategy_pairs(rec)
            self._append_kv_node_block(lay, tag, pairs, False, rec.get("element"))
        lay.addStretch(1)

    def _update_mode_strategy_display(self):
        """性能模式策略：同上，随当前模式切换内容。"""
        if not hasattr(self, "_mode_strategy_inner_layout"):
            return
        lay = self._mode_strategy_inner_layout
        self._clear_strategy_inner_layout(lay)
        if not self.parser or self.parser.df is None or self.parser.df.empty:
            return
        game_alias = self.game_cbx.currentText()
        mode_name = self.mode_cbx.currentText()
        if not game_alias or not mode_name:
            return
        pkg_row = self.parser.df[self.parser.df["游戏名称"] == game_alias]
        if pkg_row.empty:
            return
        pkg = pkg_row["原始包名"].iloc[0]
        mdata = getattr(self.parser, "mode_level_data", None) or {}
        for rec in mdata.get((pkg, mode_name), []):
            if not isinstance(rec, dict):
                continue
            tag = rec.get("tag") or "?"
            pairs = self._normalize_strategy_pairs(rec)
            self._append_kv_node_block(lay, tag, pairs, True, rec.get("element"))
        lay.addStretch(1)

    def _commit_strategy_kv(self, meta: dict, edit: QLineEdit, mode_context: bool) -> None:
        """表单中某行 值 编辑完成，写回 XML。"""
        if not self.parser or not isinstance(meta, dict):
            return
        dom = meta.get("dom")
        mode = meta.get("mode", "text")
        if dom is None:
            return
        new_val = edit.text().strip()
        if new_val == str(meta.get("value", "")):
            return
        if not self.parser.apply_strategy_kv_edit(
            dom, mode, meta.get("attr"), new_val
        ):
            edit.setText(str(meta.get("value", "")))
            return
        meta["value"] = new_val
        if not mode_context:
            return
        game_alias = self.game_cbx.currentText()
        mode_name = self.mode_cbx.currentText()
        pkg_row = self.parser.df[self.parser.df["游戏名称"] == game_alias]
        if pkg_row.empty:
            return
        pkg = pkg_row["原始包名"].iloc[0]
        sync_col = meta.get("sync_df")
        if sync_col:
            self.parser._sync_mode_fields_to_df(pkg, mode_name, sync_col, new_val)
        mode_df = self.parser.df[
            (self.parser.df["游戏名称"] == game_alias) & (self.parser.df["性能模式"] == mode_name)
        ]
        if not mode_df.empty and sync_col in ("ThermalSceneCode", "PerfHint"):
            self.parser.update_xml_node(mode_df.index[0])
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
        # push 前将当前编辑内容写回原 gameperfconfig.xml
        if self.parser and self.parser.original_tree and self.parser.xml_path == filepath:
            if not self.parser.write_to_path(filepath):
                QMessageBox.warning(
                    self.window(), "保存失败", "无法将修改写回原文件，请检查文件是否被占用。"
                )
                return
        # push 时自动以 JSON 保存当前数据 + 当前数据备注说明，按游戏包名建文件夹、时间戳命名
        self._save_push_record_json()
        self._log_area.clear()
        self._set_progress(0)
        self._update_push_button_states(False)
        self._push_service.push(filepath)

    def _save_push_record_json(self):
        """push 时自动以 JSON 保存当前数据及「当前数据备注」说明，按游戏包名建文件夹、时间戳命名。"""
        if not self.parser or self.parser.df is None or self.parser.df.empty:
            return
        game_name = self.game_cbx.currentText()
        mode_name = self.mode_cbx.currentText()
        df_sub = self.parser.df[
            (self.parser.df["游戏名称"] == game_name)
            & (self.parser.df["性能模式"] == mode_name)
        ]
        if df_sub.empty:
            return
        package_name = df_sub["原始包名"].iloc[0]
        advantage_note = self._advantage_input.text().strip()

        # 导出表格数据（去掉不可序列化的 xml_node、mode_xml_node）
        cols = [c for c in df_sub.columns if c not in ("xml_node", "mode_xml_node")]
        data_rows = df_sub[cols].to_dict(orient="records")

        payload = {
            "game": game_name,
            "package": package_name,
            "mode": mode_name,
            "advantage_note": advantage_note,
            "saved_at": datetime.now().isoformat(),
            "data": data_rows,
        }
        safe_package = re.sub(r'[\\/:*?"<>|]', "_", package_name)
        record_dir = os.path.join(self._data_dir, "push_records", safe_package)
        os.makedirs(record_dir, exist_ok=True)
        filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
        path = os.path.join(record_dir, filename)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @pyqtSlot()
    def _on_push_clear(self):
        # 仅清空游戏、性能模式、频点配置表、备注；保留配置文件路径，以便仍可 Start/Reset 上一次文件
        self.game_cbx.clear()
        self.mode_cbx.clear()
        self.config_table.setRowCount(0)
        if hasattr(self, "_advantage_input"):
            self._advantage_input.clear()

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
            # 设备重启后需延迟刷新，否则当前设备信息与连接状态不更新
            self.refresh_device_requested.emit()
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
        self._update_strategy_displays()
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
        if not self.parser or self.current_filtered_df is None or self.current_filtered_df.empty:
            return
        if row < 0 or row >= len(self.current_filtered_df):
            return
        item = self.config_table.item(row, col)
        if item is None:
            return
        original_idx = self.current_filtered_df.index[row]
        new_val = item.text().strip()

        if col == 1:
            try:
                t = int(new_val)
                if t < 0 or t > 200:
                    raise ValueError("温度应在 0～200 之间")
            except ValueError:
                QMessageBox.warning(
                    self.window(), "格式错误", "触发温度请填写 0～200 的整数（单位 ℃）"
                )
                self._refresh()
                return
            # 该列可能为 pandas StringDtype，赋 int 会 TypeError，统一存字符串
            self.parser.df.at[original_idx, "触发温度(℃)"] = str(t)
            self.parser.update_xml_node(original_idx)
            self._refresh()
            return

        if col not in [4, 7, 10]:
            self._refresh()
            return
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
            self._update_strategy_displays()
            return

        # 频点按温度等级多行显示
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
                if c in [1, 4, 7, 10]:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.config_table.blockSignals(False)
        self._update_strategy_displays()
