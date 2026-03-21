"""游戏性能配置 XML 解析引擎 — 纯 lxml，不依赖 GUI 或 pandas"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from lxml import etree

from .models import ClusterInfo, FreqRow, GameScene, StrategyItem

logger = logging.getLogger(__name__)

GAME_ALIAS_MAP = {
    "com.tencent.tmgp.pubgmhd": "和平精英",
    "com.tencent.tmgp.sgame": "王者荣耀",
    "com.miHoYo.Yuanshen": "原神",
}


class GamePerfParser:
    """解析 gameperfconfig.xml，提供数据查询与编辑能力。

    设计原则：
    - 不依赖任何 GUI 框架
    - 返回 Python 原生数据结构（dataclass / dict / list）
    - XML DOM 编辑通过方法调用，内部维护 lxml tree
    """

    def __init__(self, xml_path: str | Path) -> None:
        self.xml_path = str(xml_path)
        self._tree: etree._ElementTree | None = None
        self._root: etree._Element | None = None

        self.cpu_clusters: dict[str, ClusterInfo] = {}
        self.gpu_cluster: ClusterInfo | None = None
        self.game_scenes: dict[str, list[GameScene]] = {}
        self.freq_rows: list[FreqRow] = []

        self._game_level_data: dict[str, list[StrategyItem]] = {}
        self._mode_level_data: dict[tuple[str, str], list[StrategyItem]] = {}

        self._parse()

    # ------------------------------------------------------------------
    # 解析
    # ------------------------------------------------------------------

    def _parse(self) -> None:
        try:
            self._tree = etree.parse(self.xml_path)
            self._root = self._tree.getroot()
        except Exception:
            with open(self.xml_path, "r", encoding="utf-8", errors="replace") as f:
                xml_content = f.read()
            self._root = etree.fromstring(xml_content.encode("utf-8"))
            self._tree = None

        self._parse_pre_env()
        self._parse_base_info()
        self._parse_game_policy()

    def _parse_pre_env(self) -> None:
        if self._root is None:
            return
        pre_env = self._root.find("PreEnv")
        if pre_env is None:
            return
        cpu_el = pre_env.find("CPU")
        if cpu_el is not None:
            for cluster_el in cpu_el.findall("cluster"):
                name = cluster_el.get("name", "")
                freq_list = [int(f) for f in (cluster_el.text or "").strip().split() if f]
                self.cpu_clusters[name] = ClusterInfo(name=name, frequencies=freq_list)

        gpu_el = pre_env.find("GPU")
        if gpu_el is not None:
            gc = gpu_el.find("cluster")
            if gc is not None:
                freq_list = [int(f) for f in (gc.text or "").strip().split() if f]
                self.gpu_cluster = ClusterInfo(name="Gpu", frequencies=freq_list)

    def _parse_base_info(self) -> None:
        if self._root is None:
            return
        base_info = self._root.find("BaseInfo")
        if base_info is None:
            return
        for game in base_info.findall("Game"):
            game_name = game.get("name", "")
            scenes: list[GameScene] = []
            scene_list = game.find("SceneList")
            if scene_list is not None:
                for sc in scene_list.findall("scene"):
                    sid = (sc.text or "").strip()
                    note = (sc.tail or "").strip().replace("<!--", "").replace("-->", "").strip()
                    scenes.append(GameScene(scene_id=sid, note=note))
            self.game_scenes[game_name] = scenes

    def _parse_game_policy(self) -> None:
        if self._root is None:
            return
        gp = self._root.find("GamePolicy")
        if gp is None:
            return

        self.freq_rows.clear()
        self._game_level_data.clear()
        self._mode_level_data.clear()

        for game in gp.findall("Game"):
            game_name = game.get("name", "")
            game_alias = self._resolve_alias(game_name)

            game_items: list[StrategyItem] = []
            for child in game:
                if child.tag in ("Mode", "Policy"):
                    continue
                pairs = self._flatten_element_kv(child)
                if not pairs:
                    pairs = [{"header": child.tag, "value": "", "dom": child, "mode": "text", "attr": None}]
                game_items.append(StrategyItem(tag=child.tag, pairs=pairs, element=child))
            self._game_level_data[game_name] = game_items

            for mode in game.findall("Mode"):
                mode_name = mode.get("name", "")
                mode_key = (game_name, mode_name)

                mode_items: list[StrategyItem] = []
                for mchild in mode:
                    if mchild.tag == "Policy":
                        continue
                    pairs = self._flatten_element_kv(mchild)
                    if not pairs:
                        pairs = [{"header": mchild.tag, "value": "", "dom": mchild, "mode": "text", "attr": None}]
                    self._apply_mode_sync_flags(mchild, pairs)
                    mode_items.append(StrategyItem(tag=mchild.tag, pairs=pairs, element=mchild))
                self._mode_level_data[mode_key] = mode_items

                policy_elem = mode.find("Policy")
                temp_levels = policy_elem.findall("TempLevel") if policy_elem is not None else []
                if not temp_levels:
                    continue

                thermal_sc_el = mode.find("ThermalSceneCode")
                thermal_sc = (thermal_sc_el.text or "").strip() if thermal_sc_el is not None else ""
                perf_hint_val = ""
                perf_hint_el = mode.find("PerfHint")
                if perf_hint_el is not None:
                    opcode = perf_hint_el.find("opcode")
                    if opcode is not None and opcode.text:
                        perf_hint_val = opcode.text.strip()

                for tl in temp_levels:
                    row = self._build_freq_row(
                        game_alias, game_name, mode_name, thermal_sc, perf_hint_val, tl, mode,
                    )
                    self.freq_rows.append(row)

    def _build_freq_row(
        self,
        alias: str, pkg: str, mode: str,
        thermal_sc: str, perf_hint: str,
        tl: etree._Element, mode_node: etree._Element,
    ) -> FreqRow:
        level = tl.get("level", "")
        temp = tl.get("temp", "")
        gold_min, gold_max, gold_idx = 0, 0, ""
        prime_min, prime_max, prime_idx = 0, 0, ""
        gpu_min, gpu_max, gpu_idx = 0, 0, ""

        for item in tl.findall("item"):
            item_name = item.get("name", "")
            freq_range = (item.text or "").strip()
            if not freq_range or "_" not in freq_range:
                continue
            try:
                start, end = map(int, freq_range.split("_"))
                if item_name == "Gold" and "Gold" in self.cpu_clusters:
                    gold_idx = freq_range
                    gold_min, gold_max = self._resolve_freq_range("Gold", start, end)
                elif item_name == "Prime" and "Prime" in self.cpu_clusters:
                    prime_idx = freq_range
                    prime_min, prime_max = self._resolve_freq_range("Prime", start, end)
                elif item_name == "Gpu" and self.gpu_cluster:
                    gpu_idx = freq_range
                    gpu_min, gpu_max = self._resolve_freq_range("Gpu", start, end)
            except Exception:
                continue

        return FreqRow(
            game_alias=alias, package_name=pkg, mode_name=mode,
            thermal_scene_code=thermal_sc, perf_hint=perf_hint,
            temp_level=level, trigger_temp=temp,
            gold_min=gold_min, gold_max=gold_max, gold_index=gold_idx,
            prime_min=prime_min, prime_max=prime_max, prime_index=prime_idx,
            gpu_min=gpu_min, gpu_max=gpu_max, gpu_index=gpu_idx,
            xml_node=tl, mode_xml_node=mode_node,
        )

    def _resolve_freq_range(self, cluster_name: str, start: int, end: int) -> tuple[int, int]:
        if cluster_name == "Gpu" and self.gpu_cluster:
            freqs = self.gpu_cluster.frequencies
        elif cluster_name in self.cpu_clusters:
            freqs = self.cpu_clusters[cluster_name].frequencies
        else:
            return 0, 0
        lo, hi = min(start, end), max(start, end)
        vals = freqs[lo : hi + 1]
        return (min(vals), max(vals)) if vals else (0, 0)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_game_names(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for r in self.freq_rows:
            if r.game_alias not in seen:
                seen.add(r.game_alias)
                result.append(r.game_alias)
        return result

    def get_modes_for_game(self, game_alias: str) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for r in self.freq_rows:
            if r.game_alias == game_alias and r.mode_name not in seen:
                seen.add(r.mode_name)
                result.append(r.mode_name)
        return result

    def get_filtered_rows(self, game_alias: str, mode_name: str) -> list[FreqRow]:
        return [r for r in self.freq_rows if r.game_alias == game_alias and r.mode_name == mode_name]

    def get_package_for_alias(self, game_alias: str) -> str:
        for r in self.freq_rows:
            if r.game_alias == game_alias:
                return r.package_name
        return ""

    def get_game_level_data(self, package: str) -> list[StrategyItem]:
        return self._game_level_data.get(package, [])

    def get_mode_level_data(self, package: str, mode: str) -> list[StrategyItem]:
        return self._mode_level_data.get((package, mode), [])

    # ------------------------------------------------------------------
    # 编辑
    # ------------------------------------------------------------------

    def update_freq_index(self, row_idx: int, cluster: str, new_index: str) -> bool:
        """更新频率索引并反算 Hz"""
        if row_idx < 0 or row_idx >= len(self.freq_rows):
            return False
        row = self.freq_rows[row_idx]
        try:
            start, end = map(int, new_index.split("_"))
        except (ValueError, AttributeError):
            return False

        if cluster == "Gold":
            row.gold_index = new_index
            row.gold_min, row.gold_max = self._resolve_freq_range("Gold", start, end)
        elif cluster == "Prime":
            row.prime_index = new_index
            row.prime_min, row.prime_max = self._resolve_freq_range("Prime", start, end)
        elif cluster == "Gpu":
            row.gpu_index = new_index
            row.gpu_min, row.gpu_max = self._resolve_freq_range("Gpu", start, end)
        else:
            return False

        self._sync_row_to_xml(row_idx)
        return True

    def update_temperature(self, row_idx: int, new_temp: str) -> bool:
        if row_idx < 0 or row_idx >= len(self.freq_rows):
            return False
        self.freq_rows[row_idx].trigger_temp = new_temp
        self._sync_row_to_xml(row_idx)
        return True

    def apply_strategy_edit(
        self, dom: etree._Element, mode: str, attr: str | None, value: str
    ) -> bool:
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

    def sync_mode_fields_to_freq_rows(
        self, package: str, mode_name: str, col_name: str, value: str
    ) -> None:
        """ThermalSceneCode / PerfHint 编辑后同步到所有对应频率行"""
        for r in self.freq_rows:
            if r.package_name == package and r.mode_name == mode_name:
                if col_name == "ThermalSceneCode":
                    r.thermal_scene_code = value
                elif col_name == "PerfHint":
                    r.perf_hint = value

    def add_bindcore_row(self, bind_root: etree._Element) -> bool:
        if bind_root is None or bind_root.tag != "BindCore":
            return False
        child_tag = "tid"
        for ch in bind_root:
            child_tag = ch.tag
            break
        el = etree.SubElement(bind_root, child_tag)
        el.set("name", "")
        el.text = "0"
        self._refresh_game_policy()
        return True

    def remove_subtree(self, element: etree._Element) -> bool:
        parent = element.getparent()
        if parent is None:
            return False
        parent.remove(element)
        self._refresh_game_policy()
        return True

    def save_as(self, path: str | Path) -> bool:
        return self._write_xml(str(path))

    def write_to_path(self, path: str | Path) -> bool:
        return self._write_xml(str(path))

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _sync_row_to_xml(self, row_idx: int) -> None:
        row = self.freq_rows[row_idx]
        node = row.xml_node
        if node is None:
            return
        node.set("temp", str(row.trigger_temp))
        for item in node.findall("item"):
            name = item.get("name", "")
            if name == "Gold":
                item.text = row.gold_index
            elif name == "Prime":
                item.text = row.prime_index
            elif name == "Gpu":
                item.text = row.gpu_index

        mode_node = row.mode_xml_node
        if mode_node is not None:
            th_el = mode_node.find("ThermalSceneCode")
            if th_el is not None:
                th_el.text = row.thermal_scene_code
            ph_el = mode_node.find("PerfHint")
            if ph_el is not None:
                oc = ph_el.find("opcode")
                if oc is not None:
                    oc.text = row.perf_hint

    def _refresh_game_policy(self) -> None:
        """XML DOM 结构变化后重新解析 GamePolicy 部分"""
        self._parse_game_policy()

    def _write_xml(self, path: str) -> bool:
        try:
            if self._tree is not None:
                self._tree.write(path, encoding="utf-8", xml_declaration=True, pretty_print=True)
            elif self._root is not None:
                with open(path, "wb") as f:
                    f.write(etree.tostring(self._root, encoding="utf-8", pretty_print=True, xml_declaration=True))
            else:
                return False
            return True
        except Exception as e:
            logger.error("保存 XML 失败: %s", e)
            return False

    @staticmethod
    def _resolve_alias(package_name: str) -> str:
        if not package_name.startswith("com."):
            return package_name
        return GAME_ALIAS_MAP.get(package_name, package_name.split(".")[-1])

    @staticmethod
    def _flatten_element_kv(el: etree._Element) -> list[dict[str, Any]]:
        root_tag = el.tag
        out: list[dict[str, Any]] = []

        def walk(node: etree._Element, segments: list[str]) -> None:
            disp_path = f"{root_tag}/{'/'.join(segments)}" if segments else root_tag
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
            by_tag: dict[str, list[etree._Element]] = defaultdict(list)
            for ch in node:
                by_tag[ch.tag].append(ch)
            for tname, chlist in by_tag.items():
                for i, ch in enumerate(chlist):
                    seg = f"{tname}[{i}]" if len(chlist) > 1 else tname
                    walk(ch, segments + [seg])

        walk(el, [])
        return out

    @staticmethod
    def _apply_mode_sync_flags(mchild: etree._Element, pairs: list[dict[str, Any]]) -> None:
        if mchild.tag == "ThermalSceneCode":
            for p in pairs:
                dom = p.get("dom")
                if p.get("mode") == "text" and dom is not None and getattr(dom, "tag", None) == "ThermalSceneCode":
                    p["sync_df"] = "ThermalSceneCode"
        elif mchild.tag == "PerfHint":
            for p in pairs:
                dom = p.get("dom")
                if dom is not None and getattr(dom, "tag", None) == "opcode" and p.get("mode") == "text":
                    p["sync_df"] = "PerfHint"
