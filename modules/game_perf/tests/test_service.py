"""GamePerfService 单元测试"""

from __future__ import annotations

import os
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.game_perf.src.service import GamePerfService, XmlValidationError, is_valid_config_filename
from modules.game_perf.src.models import PushRecord
from toolkit.sdk.exceptions import AdbError

FIXTURE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "fixtures"
)
FIXTURE_XML = os.path.join(FIXTURE_DIR, "test_gameperfconfig.xml")


@pytest.fixture
def mock_adb():
    adb = MagicMock()
    adb.root.return_value = ""
    adb.remount.return_value = ""
    adb.shell.return_value = '<GameOptPolicy version = "5">'
    adb.push.return_value = ""
    adb.reboot.return_value = ""
    adb.wait_for_device.return_value = None
    adb.wait_boot_completed.return_value = None
    adb.pull.return_value = ""
    return adb


@pytest.fixture
def svc(mock_adb, tmp_path):
    return GamePerfService(mock_adb, str(tmp_path))


class TestValidFilename:
    def test_valid_names(self):
        assert is_valid_config_filename("gameperfconfig.xml")
        assert is_valid_config_filename("gameperfconfig（11）.xml")
        assert is_valid_config_filename("aaagameperfconfig.xml")

    def test_invalid_names(self):
        assert not is_valid_config_filename("config.xml")
        assert not is_valid_config_filename("gameperfconfig.txt")
        assert not is_valid_config_filename("game_perf_config.xml")


class TestXmlValidation:
    def test_valid_xml(self):
        result = GamePerfService.validate_xml(FIXTURE_XML)
        assert result is None

    def test_invalid_xml(self, tmp_path):
        bad_file = tmp_path / "bad.xml"
        bad_file.write_text("<root><unclosed>", encoding="utf-8")
        result = GamePerfService.validate_xml(str(bad_file))
        assert result is not None
        assert result.error_line > 0


class TestDeviceVersion:
    def test_reads_version(self, svc, mock_adb):
        mock_adb.shell.return_value = '<?xml version="1.0"?>\n<GameOptPolicy version = "5">'
        ver = svc.get_device_version("DEV001")
        assert ver == 5

    def test_returns_zero_on_error(self, svc, mock_adb):
        mock_adb.shell.side_effect = AdbError("fail")
        ver = svc.get_device_version("DEV001")
        assert ver == 0


class TestGetInfo:
    def test_returns_info(self, svc, mock_adb):
        mock_adb.shell.return_value = '<GameOptPolicy version = "10">'
        info = svc.get_info("DEV001")
        assert info["version"] == 10
        assert info["has_backup"] is False


class TestPushRecord:
    def test_json_save(self, svc, tmp_path):
        record = PushRecord(
            game="王者荣耀", package="com.tencent.tmgp.sgame",
            mode="Normal", notes="test", data=[{"key": "val"}],
        )
        path = svc.save_push_record(record)
        assert os.path.isfile(path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["game"] == "王者荣耀"
        assert data["notes"] == "test"

    def test_db_write(self, svc, tmp_path):
        mock_db = MagicMock()
        record = PushRecord(
            game="test", package="com.test", mode="Normal", notes="n",
        )
        svc.save_push_record(record, db_manager=mock_db)
        mock_db.execute.assert_called_once()
        args = mock_db.execute.call_args
        assert "perf_push_history" in args[0][0]


class TestPushFlow:
    def test_push_validates_filename(self, svc):
        with pytest.raises(AdbError, match="无效的配置文件"):
            svc.push("DEV001", "config.xml")

    def test_push_validates_existence(self, svc):
        with pytest.raises(AdbError, match="不存在"):
            svc.push("DEV001", "/nonexistent/gameperfconfig.xml")

    def test_push_validates_xml(self, svc, tmp_path):
        bad = tmp_path / "gameperfconfig.xml"
        bad.write_text("<root><unclosed>", encoding="utf-8")
        with pytest.raises(XmlValidationError):
            svc.push("DEV001", str(bad))


class TestResetFlow:
    def test_reset_no_backup_raises(self, svc):
        with pytest.raises(AdbError, match="无可用备份"):
            svc.reset("DEV001")
