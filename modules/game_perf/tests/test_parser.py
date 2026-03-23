"""GamePerfParser 单元测试"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from modules.game_perf.src.parser import GamePerfParser

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")
FIXTURE_XML = os.path.join(FIXTURE_DIR, "test_gameperfconfig.xml")


@pytest.fixture
def parser():
    return GamePerfParser(FIXTURE_XML)


@pytest.fixture
def parser_copy(tmp_path):
    """可写的副本用于编辑测试"""
    copy_path = tmp_path / "gameperfconfig.xml"
    shutil.copy2(FIXTURE_XML, copy_path)
    return GamePerfParser(str(copy_path))


class TestPreEnvParsing:
    def test_cpu_clusters_parsed(self, parser):
        assert "Gold" in parser.cpu_clusters
        assert "Prime" in parser.cpu_clusters
        assert len(parser.cpu_clusters["Gold"].frequencies) == 16
        assert len(parser.cpu_clusters["Prime"].frequencies) == 19

    def test_gpu_cluster_parsed(self, parser):
        assert parser.gpu_cluster is not None
        assert parser.gpu_cluster.name == "Gpu"
        assert len(parser.gpu_cluster.frequencies) == 6

    def test_gold_frequencies_values(self, parser):
        gold = parser.cpu_clusters["Gold"].frequencies
        assert gold[0] == 300000
        assert gold[2] == 518400


class TestGamePolicyParsing:
    def test_freq_rows_count(self, parser):
        assert len(parser.freq_rows) == 3  # 2 Normal + 1 HighPerf

    def test_game_names(self, parser):
        names = parser.get_game_names()
        assert "王者荣耀" in names

    def test_modes_for_game(self, parser):
        modes = parser.get_modes_for_game("王者荣耀")
        assert "Normal" in modes
        assert "HighPerf" in modes

    def test_freq_row_values(self, parser):
        rows = parser.get_filtered_rows("王者荣耀", "Normal")
        assert len(rows) == 2
        r0 = rows[0]
        assert r0.temp_level == "0"
        assert r0.trigger_temp == "36"
        assert r0.gold_index == "2_8"
        assert r0.gold_min == 518400
        assert r0.gold_max == 1094400

    def test_thermal_scene_code(self, parser):
        rows = parser.get_filtered_rows("王者荣耀", "Normal")
        assert rows[0].thermal_scene_code == "4000"

    def test_perf_hint(self, parser):
        rows = parser.get_filtered_rows("王者荣耀", "Normal")
        assert rows[0].perf_hint == "1234 5678"


class TestFreqIndexEdit:
    def test_update_gold_index(self, parser_copy):
        ok = parser_copy.update_freq_index(0, "Gold", "3_10")
        assert ok
        row = parser_copy.freq_rows[0]
        assert row.gold_index == "3_10"
        assert row.gold_min == 614400
        assert row.gold_max == 1305600

    def test_update_prime_index(self, parser_copy):
        ok = parser_copy.update_freq_index(0, "Prime", "5_15")
        assert ok
        row = parser_copy.freq_rows[0]
        assert row.prime_index == "5_15"
        assert row.prime_min > 0

    def test_update_gpu_index(self, parser_copy):
        ok = parser_copy.update_freq_index(0, "Gpu", "0_3")
        assert ok
        row = parser_copy.freq_rows[0]
        assert row.gpu_index == "0_3"
        assert row.gpu_min == 315000
        assert row.gpu_max == 720000

    def test_invalid_index_format(self, parser_copy):
        ok = parser_copy.update_freq_index(0, "Gold", "invalid")
        assert not ok

    def test_update_gold_index_order_preserved(self, parser_copy):
        """大_小 按界面顺序原样写入；Hz 仍按 min..max 下标连续区间计算。"""
        ok = parser_copy.update_freq_index(0, "Gold", "10_3")
        assert ok
        row = parser_copy.freq_rows[0]
        assert row.gold_index == "10_3"
        lo, hi = 3, 10
        assert row.gold_min == min(parser_copy.cpu_clusters["Gold"].frequencies[lo : hi + 1])
        assert row.gold_max == max(parser_copy.cpu_clusters["Gold"].frequencies[lo : hi + 1])

    def test_update_gpu_index_order_preserved(self, parser_copy):
        """Gpu 与 Gold/Prime 相同：串为 下限下标_上限下标，顺序原样保留。"""
        ok = parser_copy.update_freq_index(0, "Gpu", "1_4")
        assert ok
        row = parser_copy.freq_rows[0]
        assert row.gpu_index == "1_4"
        lo, hi = 1, 4
        vals = parser_copy.gpu_cluster.frequencies[lo : hi + 1]
        assert row.gpu_min == min(vals)
        assert row.gpu_max == max(vals)

    def test_format_freq_index_preserves_order(self):
        assert GamePerfParser.format_freq_index_str(" 10_3 ") == "10_3"
        assert GamePerfParser.parse_freq_index_pair("10_3") == (10, 3)


class TestTemperatureEdit:
    def test_update_temperature(self, parser_copy):
        ok = parser_copy.update_temperature(0, "42")
        assert ok
        assert parser_copy.freq_rows[0].trigger_temp == "42"


class TestSaveAs:
    def test_save_as_creates_file(self, parser_copy, tmp_path):
        out = tmp_path / "output.xml"
        ok = parser_copy.save_as(str(out))
        assert ok
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "GameOptPolicy" in content


class TestStrategyData:
    def test_game_level_data(self, parser):
        pkg = parser.get_package_for_alias("王者荣耀")
        items = parser.get_game_level_data(pkg)
        assert len(items) >= 1
        assert items[0].tag == "ThermalSceneCode"

    def test_mode_level_data(self, parser):
        pkg = parser.get_package_for_alias("王者荣耀")
        items = parser.get_mode_level_data(pkg, "Normal")
        tags = [it.tag for it in items]
        assert "ThermalSceneCode" in tags
        assert "PerfHint" in tags


class TestSerializable:
    def test_freq_row_to_dict(self, parser):
        row = parser.freq_rows[0]
        d = row.to_dict()
        assert "game_alias" in d
        assert "xml_node" not in d
        assert d["gold_index"] == "2_8"
