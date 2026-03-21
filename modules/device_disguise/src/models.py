"""设备伪装工具 — 数据模型与档案管理"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DeviceProfile(BaseModel):
    """设备档案记录"""

    brand: str
    manufacturer: str
    model: str
    notes: str = ""

    def unique_key(self) -> str:
        return f"{self.brand}|{self.manufacturer}|{self.model}".lower()


class ProfileManager:
    """设备档案 CRUD 管理器（JSON 文件持久化）"""

    def __init__(self, data_path: str | Path | None = None) -> None:
        if data_path is None:
            data_path = (
                Path(__file__).parent.parent / "data" / "device_profiles.json"
            )
        self._path = Path(data_path)
        self._profiles: list[DeviceProfile] = []
        self.load()

    def load(self) -> None:
        if not self._path.exists():
            self._profiles = []
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self._profiles = [
                DeviceProfile(**item) for item in data if isinstance(item, dict)
            ]
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("档案文件损坏，已重置: %s", self._path)
            self._profiles = []

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(
                    [p.model_dump() for p in self._profiles],
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
            os.replace(tmp_path, str(self._path))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def get_all(self) -> list[DeviceProfile]:
        return list(self._profiles)

    def exists(self, brand: str, manufacturer: str, model: str) -> bool:
        key = f"{brand}|{manufacturer}|{model}".lower()
        return any(p.unique_key() == key for p in self._profiles)

    def find(self, field_name: str, value: str) -> list[DeviceProfile]:
        value_lower = value.lower()
        return [
            p
            for p in self._profiles
            if value_lower in getattr(p, field_name, "").lower()
        ]

    def add(self, profile: DeviceProfile) -> None:
        if self.exists(profile.brand, profile.manufacturer, profile.model):
            raise ValueError(
                f"设备档案已存在: {profile.brand}/{profile.manufacturer}/{profile.model}"
            )
        self._profiles.append(profile)
        self.save()

    def update(
        self, old_profile: DeviceProfile, new_profile: DeviceProfile
    ) -> None:
        if old_profile.unique_key() != new_profile.unique_key():
            if self.exists(
                new_profile.brand, new_profile.manufacturer, new_profile.model
            ):
                raise ValueError(
                    f"设备档案已存在: "
                    f"{new_profile.brand}/{new_profile.manufacturer}/{new_profile.model}"
                )
        idx = self._find_index(old_profile)
        if idx < 0:
            raise ValueError("未找到要更新的档案")
        self._profiles[idx] = new_profile
        self.save()

    def delete(self, profile: DeviceProfile) -> None:
        idx = self._find_index(profile)
        if idx < 0:
            raise ValueError("未找到要删除的档案")
        self._profiles.pop(idx)
        self.save()

    def import_from(self, path: str | Path) -> dict[str, int]:
        """从 JSON 文件批量导入档案，返回 {'imported': N, 'skipped': M}"""
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)

        imported = 0
        skipped = 0
        for item in data:
            if not isinstance(item, dict):
                skipped += 1
                continue
            try:
                profile = DeviceProfile(
                    brand=item.get("brand", ""),
                    manufacturer=item.get("manufacturer", ""),
                    model=item.get("model", ""),
                    notes=item.get("notes", ""),
                )
                if not profile.brand or not profile.manufacturer or not profile.model:
                    skipped += 1
                    continue
                self.add(profile)
                imported += 1
            except (ValueError, TypeError):
                skipped += 1

        return {"imported": imported, "skipped": skipped}

    def _find_index(self, profile: DeviceProfile) -> int:
        key = profile.unique_key()
        for i, p in enumerate(self._profiles):
            if p.unique_key() == key:
                return i
        return -1
