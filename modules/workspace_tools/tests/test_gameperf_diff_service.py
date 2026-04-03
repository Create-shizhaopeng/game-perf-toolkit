"""GamePerfConfigDiffService 单元测试"""

from __future__ import annotations

import os
import threading
from unittest.mock import MagicMock

import pytest

from modules.workspace_tools.src.gameperf_diff_errors import DiffValidationError, GamePerfDevicePullError
from modules.workspace_tools.src.gameperf_diff_service import GamePerfConfigDiffService
from modules.workspace_tools.src.gameperf_xml import is_valid_gameperf_config_filename
from toolkit.sdk.exceptions import AdbError

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")
DIFF_BASE = os.path.abspath(os.path.join(FIXTURE_DIR, "gameperfconfig_diff_base.xml"))
DIFF_VAR = os.path.abspath(os.path.join(FIXTURE_DIR, "gameperfconfig_diff_variant_a.xml"))


@pytest.fixture
def svc(tmp_path):
    adb = MagicMock()
    return GamePerfConfigDiffService(adb, str(tmp_path))


def test_is_valid_gameperf_config_filename():
    assert is_valid_gameperf_config_filename("gameperfconfig.xml")
    assert is_valid_gameperf_config_filename("aaagameperfconfig.xml")
    assert not is_valid_gameperf_config_filename("other.xml")


def test_diff_fixture_count(svc: GamePerfConfigDiffService):
    svc.load_session(DIFF_BASE)
    svc.add_comparator_local(DIFF_VAR)
    items = svc.run_diff()
    assert len(items) >= 5


def test_apply_merge_version(svc: GamePerfConfigDiffService, tmp_path):
    svc.load_session(DIFF_BASE)
    svc.add_comparator_local(DIFF_VAR)
    svc.run_diff()
    ver_item = next(i for i in svc.get_diff_for_comparator(0) if "version" in i.semantic_path)
    svc.apply_merge(ver_item.id, "comparator", 0)
    assert svc.get_merge_dirty()
    out = tmp_path / "out_gameperfconfig.xml"
    svc.save_merged_as(str(out))
    raw = out.read_text(encoding="utf-8")
    assert 'version="6"' in raw


def test_undo_merge(svc: GamePerfConfigDiffService):
    svc.load_session(DIFF_BASE)
    svc.add_comparator_local(DIFF_VAR)
    svc.run_diff()
    ver_item = next(i for i in svc.get_diff_for_comparator(0) if "version" in i.semantic_path)
    svc.apply_merge(ver_item.id, "comparator", 0)
    ok, detail = svc.undo_merge()
    assert ok is True
    assert "GameOptPolicy" in detail or "version" in detail
    assert not svc.get_merge_dirty()


def test_reset_merge(svc: GamePerfConfigDiffService):
    svc.load_session(DIFF_BASE)
    svc.add_comparator_local(DIFF_VAR)
    svc.run_diff()
    ver_item = next(i for i in svc.get_diff_for_comparator(0) if "version" in i.semantic_path)
    svc.apply_merge(ver_item.id, "comparator", 0)
    svc.reset_merge()
    assert not svc.get_merge_dirty()


def test_bad_local_skipped(svc: GamePerfConfigDiffService, tmp_path):
    wrong_name = tmp_path / "not_gameperf.xml"
    wrong_name.write_text("<GameOptPolicy version='1'/>", encoding="utf-8")
    svc.load_session(DIFF_BASE)
    svc.add_comparator_local(str(wrong_name))
    assert svc.comparator_count == 0
    assert svc.get_parse_errors()

    bad_xml = tmp_path / "gameperfconfig_bad.xml"
    bad_xml.write_text("<<<", encoding="utf-8")
    svc.clear_parse_errors()
    svc.add_comparator_local(str(bad_xml))
    assert svc.comparator_count == 0
    assert svc.get_parse_errors()


def test_identical_no_diff(svc: GamePerfConfigDiffService):
    svc.load_session(DIFF_BASE)
    svc.add_comparator_local(DIFF_BASE)
    items = svc.run_diff()
    assert items == []


def test_multi_comparator_switch(svc: GamePerfConfigDiffService):
    svc.load_session(DIFF_BASE)
    svc.add_comparator_local(DIFF_BASE)
    svc.add_comparator_local(DIFF_VAR)
    svc.run_diff()
    assert len(svc.get_diff_for_comparator(0)) == 0
    assert len(svc.get_diff_for_comparator(1)) >= 5
    svc.set_active_comparator(1)
    assert len(svc.get_diff_for_comparator(1)) >= 5


def test_save_preserves_utf8_in_comments(svc: GamePerfConfigDiffService, tmp_path):
    """lxml 默认 tostring 会把注释里的中文变成 &#…; 且无法再解析回汉字，克隆/保存须用 utf-8。"""
    src = tmp_path / "gameperfconfig_comment.xml"
    src.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<GameOptPolicy version="1">\n'
        "  <!-- 游戏启动说明 -->\n"
        "  <PreEnv><CPU/></PreEnv>\n"
        "</GameOptPolicy>\n",
        encoding="utf-8",
    )
    svc.load_session(str(src))
    out = tmp_path / "out_gameperfconfig.xml"
    svc.save_merged_as(str(out))
    text = out.read_text(encoding="utf-8")
    assert "游戏启动说明" in text
    assert "&#28216;" not in text


def test_save_cancel_no_file(svc: GamePerfConfigDiffService, tmp_path):
    svc.load_session(DIFF_BASE)
    target = tmp_path / "new_gameperfconfig.xml"
    assert not target.exists()
    svc.save_merged_as(str(target))
    assert target.exists()


def test_atomic_save_replace(svc: GamePerfConfigDiffService, tmp_path):
    svc.load_session(DIFF_BASE)
    target = tmp_path / "gameperfconfig.xml"
    target.write_text("old", encoding="utf-8")
    svc.save_merged_as(str(target), atomic=True)
    assert "GameOptPolicy" in target.read_text(encoding="utf-8")


def test_device_pull_success(svc: GamePerfConfigDiffService, tmp_path):
    svc.load_session(DIFF_BASE)
    adb = svc._adb
    adb.root = MagicMock()
    adb.remount = MagicMock()
    adb.shell = MagicMock()
    adb.pull = MagicMock()

    def pull_side(serial, remote, local):
        os.makedirs(os.path.dirname(local), exist_ok=True)
        with open(local, "wb") as f:
            f.write(open(DIFF_VAR, "rb").read())

    adb.pull.side_effect = pull_side
    svc.add_comparator_from_device("SERIAL123")
    assert svc.comparator_count == 1
    prov = svc.get_session()
    assert prov is not None
    assert prov.comparators[0][0].kind == "device_pull"


def test_device_pull_missing_remote(svc: GamePerfConfigDiffService):
    svc.load_session(DIFF_BASE)
    svc._adb.pull.side_effect = AdbError(
        "adb: error: remote object '/system/etc/gameperfconfig.xml' does not exist"
    )
    with pytest.raises(GamePerfDevicePullError) as ei:
        svc.add_comparator_from_device("DEV")
    assert ei.value.failure_kind == "missing"


def test_run_diff_cancel(svc: GamePerfConfigDiffService):
    svc.load_session(DIFF_BASE)
    svc.add_comparator_local(DIFF_VAR)
    ev = threading.Event()
    ev.set()
    with pytest.raises(DiffValidationError):
        svc.run_diff(cancel_event=ev)
