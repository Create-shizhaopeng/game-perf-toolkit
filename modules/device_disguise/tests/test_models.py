"""设备伪装工具 — 模型和档案管理器测试"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.device_disguise.src.models import (
    DEVICE_INFO_FILENAME,
    DeviceProfile,
    ProfileManager,
    resolve_device_info_json_path,
)


class TestDeviceProfile:
    def test_unique_key(self):
        p = DeviceProfile(brand="Samsung", manufacturer="Samsung", model="SM-G991B")
        assert p.unique_key() == "samsung|samsung|sm-g991b"

    def test_unique_key_case_insensitive(self):
        p1 = DeviceProfile(brand="Apple", manufacturer="Apple", model="iPhone15")
        p2 = DeviceProfile(brand="apple", manufacturer="APPLE", model="iphone15")
        assert p1.unique_key() == p2.unique_key()

    def test_notes_optional(self):
        p = DeviceProfile(brand="A", manufacturer="B", model="C")
        assert p.notes == ""


class TestProfileManager:
    @pytest.fixture
    def pm(self, tmp_path: Path) -> ProfileManager:
        return ProfileManager(data_path=tmp_path / "profiles.json")

    def test_empty_initially(self, pm: ProfileManager):
        assert pm.get_all() == []

    def test_add_and_get(self, pm: ProfileManager):
        p = DeviceProfile(brand="Samsung", manufacturer="Samsung", model="SM-G991B")
        pm.add(p)
        assert len(pm.get_all()) == 1
        assert pm.get_all()[0].brand == "Samsung"

    def test_add_duplicate_raises(self, pm: ProfileManager):
        p = DeviceProfile(brand="Samsung", manufacturer="Samsung", model="SM-G991B")
        pm.add(p)
        with pytest.raises(ValueError, match="已存在"):
            pm.add(p)

    def test_exists(self, pm: ProfileManager):
        p = DeviceProfile(brand="Samsung", manufacturer="Samsung", model="SM-G991B")
        pm.add(p)
        assert pm.exists("Samsung", "Samsung", "SM-G991B")
        assert not pm.exists("Apple", "Apple", "iPhone")

    def test_find(self, pm: ProfileManager):
        pm.add(DeviceProfile(brand="Samsung", manufacturer="Samsung", model="SM-A"))
        pm.add(DeviceProfile(brand="Apple", manufacturer="Apple", model="iPhone"))
        results = pm.find("brand", "sam")
        assert len(results) == 1
        assert results[0].brand == "Samsung"

    def test_update(self, pm: ProfileManager):
        old = DeviceProfile(brand="A", manufacturer="B", model="C")
        pm.add(old)
        new = DeviceProfile(brand="X", manufacturer="Y", model="Z")
        pm.update(old, new)
        assert len(pm.get_all()) == 1
        assert pm.get_all()[0].brand == "X"

    def test_update_not_found(self, pm: ProfileManager):
        old = DeviceProfile(brand="A", manufacturer="B", model="C")
        new = DeviceProfile(brand="X", manufacturer="Y", model="Z")
        with pytest.raises(ValueError, match="未找到"):
            pm.update(old, new)

    def test_delete(self, pm: ProfileManager):
        p = DeviceProfile(brand="A", manufacturer="B", model="C")
        pm.add(p)
        pm.delete(p)
        assert pm.get_all() == []

    def test_delete_not_found(self, pm: ProfileManager):
        p = DeviceProfile(brand="A", manufacturer="B", model="C")
        with pytest.raises(ValueError, match="未找到"):
            pm.delete(p)

    def test_import_from(self, pm: ProfileManager, tmp_path: Path):
        import_file = tmp_path / "import.json"
        import_file.write_text(
            json.dumps(
                [
                    {"brand": "Samsung", "manufacturer": "Samsung", "model": "SM-A"},
                    {"brand": "Apple", "manufacturer": "Apple", "model": "iPhone"},
                    {"brand": "", "manufacturer": "Bad", "model": ""},
                    "invalid_item",
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = pm.import_from(str(import_file))
        assert result["imported"] == 2
        assert result["skipped"] == 2

    def test_import_duplicate_skipped(self, pm: ProfileManager, tmp_path: Path):
        pm.add(DeviceProfile(brand="Samsung", manufacturer="Samsung", model="SM-A"))
        import_file = tmp_path / "import2.json"
        import_file.write_text(
            json.dumps(
                [{"brand": "Samsung", "manufacturer": "Samsung", "model": "SM-A"}],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = pm.import_from(str(import_file))
        assert result["imported"] == 0
        assert result["skipped"] == 1

    def test_import_requires_json_array_root(
        self, pm: ProfileManager, tmp_path: Path
    ) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text('{"brand":"A"}', encoding="utf-8")
        with pytest.raises(ValueError, match="数组"):
            pm.import_from(str(bad))

    def test_persistence(self, tmp_path: Path):
        path = tmp_path / "profiles.json"
        pm1 = ProfileManager(data_path=path)
        pm1.add(DeviceProfile(brand="A", manufacturer="B", model="C"))

        pm2 = ProfileManager(data_path=path)
        assert len(pm2.get_all()) == 1
        assert pm2.get_all()[0].brand == "A"

    def test_corrupt_file(self, tmp_path: Path):
        path = tmp_path / "profiles.json"
        path.write_text("{invalid", encoding="utf-8")
        pm = ProfileManager(data_path=path)
        assert pm.get_all() == []


class TestResolveDeviceInfoJsonPath:
    def test_dev_points_to_module_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        monkeypatch.setattr(sys, "frozen", False, raising=False)
        p = resolve_device_info_json_path()
        assert p.name == DEVICE_INFO_FILENAME
        assert p.parent.name == "config"
        assert "device_disguise" in p.parts

    def test_frozen_points_next_to_exe(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys

        exe = tmp_path / "Toolkit.exe"
        exe.write_bytes(b"")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(exe))
        p = resolve_device_info_json_path()
        assert p == exe.parent / "data" / DEVICE_INFO_FILENAME


class TestLegacyMigration:
    def test_migrates_device_profiles_in_same_dir(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        legacy = data_dir / "device_profiles.json"
        legacy.write_text(
            '[{"brand":"A","manufacturer":"B","model":"C","notes":""}]',
            encoding="utf-8",
        )
        new_path = data_dir / DEVICE_INFO_FILENAME
        pm = ProfileManager(data_path=new_path)
        assert pm.get_all()[0].brand == "A"
        assert new_path.is_file()

    def test_skips_migration_if_device_info_exists(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        new_path = data_dir / DEVICE_INFO_FILENAME
        new_path.write_text(
            '[{"brand":"X","manufacturer":"Y","model":"Z","notes":""}]',
            encoding="utf-8",
        )
        legacy = data_dir / "device_profiles.json"
        legacy.write_text(
            '[{"brand":"A","manufacturer":"B","model":"C","notes":""}]',
            encoding="utf-8",
        )
        pm = ProfileManager(data_path=new_path)
        assert pm.get_all()[0].brand == "X"
