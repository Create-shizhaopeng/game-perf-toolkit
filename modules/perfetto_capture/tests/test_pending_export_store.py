"""待导出清单存储 — 单元测试"""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.perfetto_capture.src.pending_export_store import (
    PendingExportItem,
    PendingExportStore,
)


@pytest.fixture
def store(tmp_path: Path) -> PendingExportStore:
    return PendingExportStore(tmp_path / "output" / "trace" / ".pending_exports.json")


def _item(serial: str = "DEV001", filename: str = "a.pb", device_path: str = "/data/current_1.pb") -> PendingExportItem:
    return PendingExportItem(
        serial=serial,
        device_path=device_path,
        export_filename=filename,
        session_dir="2026_08_08-10_00_00",
        device_model="SM8750P",
    )


class TestAddAndLoad:
    def test_add_then_all(self, store) -> None:
        store.add(_item())
        assert len(store.all()) == 1
        assert store.all()[0].serial == "DEV001"
        assert store.all()[0].device_model == "SM8750P"

    def test_load_from_disk(self, store) -> None:
        store.add(_item(serial="DEV001", filename="a.pb"))
        store.add(_item(serial="DEV002", filename="b.pb"))
        # 新实例从磁盘重载
        store2 = PendingExportStore(store.path)
        store2.load()
        assert len(store2.all()) == 2
        assert store2.all()[0].created_at  # 往返保留字段

    def test_file_is_atomic_json(self, store) -> None:
        store.add(_item())
        data = store.path.read_text(encoding="utf-8")
        import json
        parsed = json.loads(data)
        assert parsed["version"] == 1
        assert len(parsed["pending"]) == 1
        assert not store.path.with_suffix(".tmp").exists()  # 无残留临时文件

    def test_missing_file_returns_empty(self, store) -> None:
        store.load()
        assert store.all() == []

    def test_corrupt_file_tolerated(self, store) -> None:
        store.path.parent.mkdir(parents=True, exist_ok=True)
        store.path.write_text("{ not json", encoding="utf-8")
        store.load()
        assert store.all() == []


class TestSerialFilter:
    def test_get_for_serial(self, store) -> None:
        store.add(_item(serial="DEV001", filename="a.pb"))
        store.add(_item(serial="DEV002", filename="b.pb"))
        store.add(_item(serial="DEV001", filename="c.pb"))
        dev1 = store.get_for_serial("DEV001")
        assert len(dev1) == 2
        assert all(i.serial == "DEV001" for i in dev1)

    def test_has_pending(self, store) -> None:
        assert not store.has_pending("DEV001")
        store.add(_item())
        assert store.has_pending("DEV001")
        assert not store.has_pending("OTHER")


class TestRemove:
    def test_remove_matching(self, store) -> None:
        store.add(_item(serial="DEV001", filename="a.pb"))
        store.add(_item(serial="DEV001", filename="b.pb"))
        assert store.remove("DEV001", "a.pb")
        remaining = [i.export_filename for i in store.all()]
        assert remaining == ["b.pb"]

    def test_remove_serial_scoped(self, store) -> None:
        """同文件名但不同 serial 的项不受影响（跨设备不串扰）。"""
        store.add(_item(serial="DEV001", filename="a.pb"))
        store.add(_item(serial="DEV002", filename="a.pb"))
        assert store.remove("DEV001", "a.pb")
        assert len(store.all()) == 1
        assert store.all()[0].serial == "DEV002"

    def test_remove_absent_returns_false(self, store) -> None:
        assert not store.remove("DEV001", "missing.pb")


class TestClearSerial:
    def test_clear_serial(self, store) -> None:
        store.add(_item(serial="DEV001", filename="a.pb"))
        store.add(_item(serial="DEV002", filename="b.pb"))
        assert store.clear_serial("DEV001") == 1
        remaining = [i.serial for i in store.all()]
        assert remaining == ["DEV002"]

    def test_clear_absent_returns_zero(self, store) -> None:
        assert store.clear_serial("NOPE") == 0
